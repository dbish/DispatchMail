import asyncio
import json
import os
from typing import Optional

from openai import OpenAI
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import boto3
from config_reader import AWS_REGION, DYNAMODB_META_TABLE, DYNAMODB_TABLE

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
TOKEN_DIR = os.getenv('GMAIL_TOKEN_DIR', os.path.join(os.path.dirname(__file__), 'gmail_tokens'))
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DEFAULT_PROMPT = (
    "You are an email triage agent. You may apply Gmail labels, archive the email, or draft a reply. "
    "Use JSON like {'label': 'LabelName'}, {'archive': true}, or {'draft': 'Reply text'} in any combination."
)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
meta_table = dynamodb.Table(DYNAMODB_META_TABLE)
email_table = dynamodb.Table(DYNAMODB_TABLE)


def get_prompt() -> str:
    """Fetch the latest prompt from DynamoDB or use default."""
    try:
        resp = meta_table.get_item(Key={"user": "reading_prompt"})
        item = resp.get("Item")
        if item and item.get("prompt"):
            return item["prompt"]
    except Exception as e:
        print(f"Error fetching prompt: {e}")
    return DEFAULT_PROMPT


def get_draft_prompt() -> str:
    """Fetch the drafting prompt from DynamoDB or provide a default."""
    try:
        resp = meta_table.get_item(Key={"user": "draft_prompt"})
        item = resp.get("Item")
        if item and item.get("prompt"):
            return item["prompt"]
    except Exception as e:
        print(f"Error fetching draft prompt: {e}")
    return "Write a concise and professional reply to the email."


def get_gmail_service(user: str):
    token_path = os.path.join(TOKEN_DIR, f"{user}.json")
    if not os.path.exists(token_path):
        print(f"Gmail token not found for {user}: {token_path}")
        return None
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    return build("gmail", "v1", credentials=creds)


def ensure_label(service, name: str) -> Optional[str]:
    try:
        labels_resp = service.users().labels().list(userId="me").execute()
        for lbl in labels_resp.get("labels", []):
            if lbl.get("name", "").lower() == name.lower():
                return lbl["id"]
        new_label = (
            service.users()
            .labels()
            .create(userId="me", body={"name": name})
            .execute()
        )
        return new_label.get("id")
    except Exception as e:
        print(f"Error ensuring label {name}: {e}")
        return None


def find_message(service, rfc822_msgid: str) -> Optional[str]:
    try:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=f"rfc822msgid:{rfc822_msgid}")
            .execute()
        )
        msgs = resp.get("messages", [])
        if not msgs:
            return None
        return msgs[0]["id"]
    except Exception as e:
        print(f"Error locating message {rfc822_msgid}: {e}")
        return None


def record_action(message_id: str, action: str) -> None:
    """Mark an email as processed and store the action taken."""
    try:
        email_table.update_item(
            Key={"message_id": message_id},
            UpdateExpression="SET processed = :p, action = :a",
            ExpressionAttributeValues={":p": True, ":a": action},
        )
    except Exception as e:
        print(f"Error updating email {message_id}: {e}")


async def handle_email(user: str, parsed_email) -> None:
    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY not set, skipping AI processing")
        return

    body = parsed_email.text_plain[0] if parsed_email.text_plain else ""
    content = f"Subject: {parsed_email.subject}\nFrom: {parsed_email.from_}\n\n{body}"

    def run_openai():
        return client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"{get_prompt()}\nDrafting instructions: {get_draft_prompt()}",
                },
                {"role": "user", "content": content},
            ],
            temperature=0,
        )

    try:
        resp = await asyncio.to_thread(run_openai)
    except Exception as e:
        print(f"OpenAI request failed: {e}")
        return

    text = resp.choices[0].message.content.strip()
    try:
        data = json.loads(text)
    except Exception:
        print(f"Unable to parse LLM response: {text}")
        return

    label_name = data.get("label")
    draft_text = data.get("draft")
    archive_flag = data.get("archive")

    if draft_text:
        try:
            email_table.update_item(
                Key={"message_id": parsed_email.message_id},
                UpdateExpression="SET draft = :d",
                ExpressionAttributeValues={":d": draft_text},
            )
        except Exception as e:
            print(f"Failed to store draft: {e}")

    acted = any([label_name, archive_flag, draft_text])
    if not acted:
        return

    service = get_gmail_service(user)
    if not service:
        return
    msg_id = find_message(service, parsed_email.message_id)
    if not msg_id:
        print("Could not find Gmail message to modify")
        return

    if label_name:
        label_id = ensure_label(service, label_name)
        if not label_id:
            return
        try:
            service.users().messages().modify(
                userId="me", id=msg_id, body={"addLabelIds": [label_id]}
            ).execute()
            print(
                f"Applied label '{label_name}' to message {parsed_email.message_id}"
            )
            record_action(parsed_email.message_id, f"added label '{label_name}'")
        except Exception as e:
            print(f"Failed to label message: {e}")

    if archive_flag:
        try:
            service.users().messages().modify(
                userId="me", id=msg_id, body={"removeLabelIds": ["INBOX"]}
            ).execute()
            print(f"Archived message {parsed_email.message_id}")
            record_action(parsed_email.message_id, "archived")
        except Exception as e:
            print(f"Failed to archive message: {e}")

    # Mark the message as read if any action was taken
    try:
        service.users().messages().modify(
            userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        print(f"Marked message {parsed_email.message_id} as read")
    except Exception as e:
        print(f"Failed to mark message as read: {e}")
