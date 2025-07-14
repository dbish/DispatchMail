import asyncio
import json
import os
from typing import Optional

from openai import OpenAI
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import boto3
from config_reader import AWS_REGION, DYNAMODB_META_TABLE, DYNAMODB_TABLE, OPENAI_API_KEY
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
            UpdateExpression="SET #processed = :p, #action = :a",
            ExpressionAttributeNames={
                "#processed": "processed",
                "#action": "action"
            },
            ExpressionAttributeValues={":p": True, ":a": action},
        )
    except Exception as e:
        print(f"Error updating email {message_id}: {e}")


def extract_key_content(parsed_email) -> str:
    """Extract the key content from an email for more focused LLM processing."""
    body = parsed_email.text_plain[0] if parsed_email.text_plain else ""
    
    # Use EmailReplyParser to get just the new content (remove quoted replies)
    clean_body = EmailReplyParser.parse_reply(body)
    
    # If the cleaned body is very short, might be just a greeting - use full body
    if len(clean_body.strip()) < 20:
        clean_body = body
    
    # Extract key information based on email length and content
    lines = clean_body.strip().split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    
    # For short emails (< 5 lines), use the full content
    if len(lines) <= 5:
        key_content = clean_body.strip()
    else:
        # For longer emails, try to extract the key parts
        key_lines = []
        
        # Look for question indicators
        question_indicators = ['?', 'please', 'could you', 'would you', 'can you', 'need', 'urgent', 'asap']
        
        for line in lines:
            line_lower = line.lower()
            # Include lines with questions or requests
            if any(indicator in line_lower for indicator in question_indicators):
                key_lines.append(line)
            # Include short lines that might be key points
            elif len(line.split()) <= 10:
                key_lines.append(line)
        
        # If we found key lines, use them. Otherwise, use first few lines + last few lines
        if key_lines:
            key_content = '\n'.join(key_lines)
        else:
            # Use first 3 and last 2 lines as fallback
            selected_lines = lines[:3] + (lines[-2:] if len(lines) > 5 else [])
            key_content = '\n'.join(selected_lines)
    
    # Create a concise prompt that includes subject for context
    prompt_content = f"Subject: {parsed_email.subject}\n\n{key_content}"
    
    return prompt_content


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
    
    # Try to parse JSON with better error handling
    try:
        data = json.loads(text)
        print(f"Parsed JSON successfully: {data}")
    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        print(f"Cleaned response was: '{text}'")
        
        # Try to extract JSON from the response if it's wrapped in text
        import re
        # Look for JSON objects with various patterns
        patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Basic JSON object
            r'\{.*?\}',  # Simple JSON match
            r'(\{[\s\S]*\})',  # Multi-line JSON
        ]
        
        for pattern in patterns:
            json_match = re.search(pattern, text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group().strip())
                    print(f"Extracted and parsed JSON: {data}")
                    break
                except json.JSONDecodeError:
                    continue
        else:
            print("Could not extract valid JSON from response")
            # Default to marking as reviewed if we can't parse
            data = {"reviewed": True}
    except Exception as e:
        print(f"Unexpected error parsing response: {e}")
        # Default to marking as reviewed if we can't parse
        data = {"reviewed": True}

    label_name = data.get("label")
    draft_text = data.get("draft") or data.get("response")  # Handle both 'draft' and 'response' keys
    archive_flag = data.get("archive")
    reviewed_flag = data.get("reviewed")

    # Store draft and the actual prompt sent to LLM if generated
    if draft_text:
        print(f"Storing draft for email {parsed_email.message_id}: {draft_text}")
        try:
            email_table.update_item(
                Key={"message_id": parsed_email.message_id},
                UpdateExpression="SET draft = :d, llm_prompt = :p",
                ExpressionAttributeValues={
                    ":d": draft_text,
                    ":p": key_content  # Store what was actually sent to LLM
                },
            )
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
