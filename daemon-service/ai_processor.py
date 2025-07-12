import asyncio
import json
import os
from typing import Optional

import openai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import boto3
from config_reader import AWS_REGION, DYNAMODB_META_TABLE

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
TOKEN_DIR = os.getenv('GMAIL_TOKEN_DIR', os.path.join(os.path.dirname(__file__), 'gmail_tokens'))
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DEFAULT_PROMPT = (
    "You are an email triage agent. Decide if a Gmail label should be applied. "
    "Respond with JSON like {'label': \"LabelName\"} or {'label': null}."
)

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
openai.api_key = OPENAI_API_KEY
meta_table = dynamodb.Table(DYNAMODB_META_TABLE)


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


async def handle_email(user: str, parsed_email) -> None:
    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY not set, skipping AI processing")
        return

    body = parsed_email.text_plain[0] if parsed_email.text_plain else ""
    content = f"Subject: {parsed_email.subject}\nFrom: {parsed_email.from_}\n\n{body}"

    def run_openai():
        return openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": get_prompt()},
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
    if not label_name:
        return

    service = get_gmail_service(user)
    if not service:
        return
    msg_id = find_message(service, parsed_email.message_id)
    if not msg_id:
        print("Could not find Gmail message to label")
        return
    label_id = ensure_label(service, label_name)
    if not label_id:
        return
    try:
        service.users().messages().modify(
            userId="me", id=msg_id, body={"addLabelIds": [label_id]}
        ).execute()
        print(f"Applied label '{label_name}' to message {parsed_email.message_id}")
    except Exception as e:
        print(f"Failed to label message: {e}")
