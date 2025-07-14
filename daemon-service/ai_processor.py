import asyncio
import json
import os
from typing import Optional

from openai import OpenAI
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from config_reader import DATABASE_PATH, OPENAI_API_KEY
from database import db
from email_reply_parser import EmailReplyParser

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
TOKEN_DIR = os.getenv('GMAIL_TOKEN_DIR', os.path.join(os.path.dirname(__file__), 'gmail_tokens'))
OPENAI_API_KEY = OPENAI_API_KEY
DEFAULT_PROMPT = (
    "You are an email reading assistant. Your primary task is to draft responses to emails that look like they expect a response. "
    "You must respond with valid JSON only. Use these EXACT formats:\n"
    "- For drafting a response: {\"draft\": \"Your reply text here\"}\n"
    "- For labeling an email: {\"label\": \"LabelName\"}\n"
    "- For archiving an email: {\"archive\": true}\n"
    "- For multiple actions: {\"draft\": \"Reply text\", \"label\": \"Important\"}\n"
    "- If no action needed: {\"reviewed\": true}\n"
    "IMPORTANT: Use 'draft' not 'response' for email replies. Always return valid JSON. Do not include any other text or explanations."
)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def get_prompt() -> str:
    """Fetch the latest prompt from database or use default."""
    try:
        metadata = db.get_metadata("reading_prompt")
        if metadata and metadata.get("prompt"):
            return metadata["prompt"]
    except Exception as e:
        print(f"Error fetching prompt: {e}")
    return DEFAULT_PROMPT


def get_draft_prompt() -> str:
    """Fetch the drafting prompt from database or provide a default."""
    try:
        metadata = db.get_metadata("draft_prompt")
        if metadata and metadata.get("prompt"):
            return metadata["prompt"]
    except Exception as e:
        print(f"Error fetching draft prompt: {e}")
    return "Write a concise and professional reply to the email."


def get_gmail_service(account: str):
    """Get Gmail service for the given account."""
    try:
        token_path = os.path.join(TOKEN_DIR, f'{account}_token.json')
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            service = build('gmail', 'v1', credentials=creds)
            return service
    except Exception as e:
        print(f"Error getting Gmail service for {account}: {e}")
    return None


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


def find_message(service, message_id: str) -> Optional[str]:
    """Find Gmail message ID by our message ID."""
    try:
        results = service.users().messages().list(userId="me", q=f"rfc822msgid:{message_id}").execute()
        messages = results.get("messages", [])
        if messages:
            return messages[0]["id"]
    except Exception as e:
        print(f"Error finding message {message_id}: {e}")
    return None


def record_action(message_id: str, action: str) -> None:
    """Mark an email as processed and store the action taken."""
    try:
        db.update_email(message_id, {"processed": True, "action": action})
    except Exception as e:
        print(f"Error updating email {message_id}: {e}")


def extract_key_content(parsed_email) -> str:
    """Extract the most important content from an email for AI processing."""
    subject = parsed_email.subject or ""
    from_email = str(parsed_email.from_) if parsed_email.from_ else ""
    
    # Get the email body
    body = ""
    if parsed_email.text_plain:
        body = parsed_email.text_plain[0] if isinstance(parsed_email.text_plain, list) else str(parsed_email.text_plain)
    
    # Use EmailReplyParser to extract just the new content
    if body:
        reply_content = EmailReplyParser.parse_reply(body)
        if reply_content and reply_content.strip():
            body = reply_content
    
    # Create a concise representation
    content = f"Subject: {subject}\n"
    content += f"From: {from_email}\n"
    content += f"Body: {body[:1000]}..."  # Limit body to 1000 chars
    
    return content


async def handle_email(user: str, parsed_email) -> None:
    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY not set, skipping AI processing")
        return

    # Extract key content instead of using the full email
    key_content = extract_key_content(parsed_email)
    
    def run_openai():
        return client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"{get_prompt()}\nDrafting instructions: {get_draft_prompt()}",
                },
                {
                    "role": "user", 
                    "content": f"Email content:\n{key_content}\n\nRespond with ONLY a JSON object. No other text or explanation."
                },
            ],
            temperature=0,
        )

    try:
        resp = await asyncio.to_thread(run_openai)
    except Exception as e:
        print(f"OpenAI request failed: {e}")
        return

    text = resp.choices[0].message.content.strip()
    print(f"Raw LLM response: {text}")
    
    # Clean up the response - remove markdown code blocks if present
    if text.startswith('```json'):
        text = text[7:]  # Remove ```json
    if text.startswith('```'):
        text = text[3:]  # Remove ```
    if text.endswith('```'):
        text = text[:-3]  # Remove trailing ```
    text = text.strip()
    
    # Parse the JSON response
    try:
        response_data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Response was: {text}")
        return
    
    # Extract actions from the response
    draft_text = response_data.get("draft", "")
    label_name = response_data.get("label", "")
    archive_flag = response_data.get("archive", False)
    
    print(f"Parsed response - Draft: {bool(draft_text)}, Label: {label_name}, Archive: {archive_flag}")

    # Store draft and the actual prompt sent to LLM if generated
    if draft_text:
        print(f"Storing draft for email {parsed_email.message_id}: {draft_text}")
        try:
            db.update_email(parsed_email.message_id, {
                "draft": draft_text,
                "llm_prompt": key_content  # Store what was actually sent to LLM
            })
            print(f"Successfully stored draft and LLM prompt for email {parsed_email.message_id}")
        except Exception as e:
            print(f"Failed to store draft: {e}")
    else:
        print(f"No draft generated for email {parsed_email.message_id}")

    # Check if we have any Gmail actions to perform
    has_gmail_actions = any([label_name, archive_flag])
    
    # If we have Gmail actions, get the service and message ID
    service = None
    msg_id = None
    if has_gmail_actions:
        service = get_gmail_service(user)
        if service:
            msg_id = find_message(service, parsed_email.message_id)
            if not msg_id:
                print("Could not find Gmail message to modify")

    # Perform Gmail actions if available
    if service and msg_id:
        if label_name:
            label_id = ensure_label(service, label_name)
            if label_id:
                try:
                    service.users().messages().modify(
                        userId="me", id=msg_id, body={"addLabelIds": [label_id]}
                    ).execute()
                    print(f"Applied label '{label_name}' to message {parsed_email.message_id}")
                except Exception as e:
                    print(f"Failed to label message: {e}")

        if archive_flag:
            try:
                service.users().messages().modify(
                    userId="me", id=msg_id, body={"removeLabelIds": ["INBOX"]}
                ).execute()
                print(f"Archived message {parsed_email.message_id}")
            except Exception as e:
                print(f"Failed to archive message: {e}")

        # Mark the message as read if any Gmail action was taken
        try:
            service.users().messages().modify(
                userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            print(f"Marked message {parsed_email.message_id} as read")
        except Exception as e:
            print(f"Failed to mark message as read: {e}")

    # Always mark as processed and record the action taken (or lack thereof)
    action_taken = []
    if draft_text:
        action_taken.append("drafted")
    if label_name:
        action_taken.append(f"labeled '{label_name}'")
    if archive_flag:
        action_taken.append("archived")
    
    if action_taken:
        action_description = ", ".join(action_taken)
    else:
        action_description = "reviewed (no action needed)"
    
    record_action(parsed_email.message_id, action_description)
    print(f"Processed email {parsed_email.message_id}: {action_description}")
