from __future__ import annotations

from typing import Any, Dict, Tuple

import boto3
import importlib.util
import os
from mcp.server.fastmcp import FastMCP

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ai_path = os.path.join(BASE_DIR, 'ai_processor.py')
spec_ai = importlib.util.spec_from_file_location('ai_processor', ai_path)
ai_processor = importlib.util.module_from_spec(spec_ai)
spec_ai.loader.exec_module(ai_processor)

config_path = os.path.join(BASE_DIR, 'config_reader.py')
spec_cfg = importlib.util.spec_from_file_location('config_reader', config_path)
config_reader = importlib.util.module_from_spec(spec_cfg)
spec_cfg.loader.exec_module(config_reader)

AWS_REGION = config_reader.AWS_REGION
DYNAMODB_TABLE = config_reader.DYNAMODB_TABLE
DYNAMODB_USERS_TABLE = config_reader.DYNAMODB_USERS_TABLE


dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
email_table = dynamodb.Table(DYNAMODB_TABLE)
users_table = dynamodb.Table(DYNAMODB_USERS_TABLE)


def list_emails() -> list[Dict[str, Any]]:
    """Return all stored emails."""
    resp = email_table.scan()
    return resp.get('Items', [])


def draft_email(message_id: str, draft: str) -> Dict[str, Any]:
    """Store a draft reply for the given email."""
    email_table.update_item(
        Key={'message_id': message_id},
        UpdateExpression='SET draft = :d',
        ExpressionAttributeValues={':d': draft},
    )
    return {'status': 'draft stored'}


def _get_gmail_service_for_message(message_id: str) -> Tuple[Any, Dict[str, Any] | None]:
    resp = email_table.get_item(Key={'message_id': message_id})
    item = resp.get('Item')
    if not item:
        return None, None
    account = item.get('account')
    service = ai_processor.get_gmail_service(account)
    return service, item


def add_label(message_id: str, label: str) -> Dict[str, Any]:
    """Apply a Gmail label to the email."""
    service, _ = _get_gmail_service_for_message(message_id)
    if not service:
        return {'error': 'message or gmail service not found'}
    gm_id = ai_processor.find_message(service, message_id)
    if not gm_id:
        return {'error': 'gmail message not found'}
    label_id = ai_processor.ensure_label(service, label)
    if not label_id:
        return {'error': 'failed to ensure label'}
    service.users().messages().modify(
        userId='me', id=gm_id, body={'addLabelIds': [label_id]}
    ).execute()
    email_table.update_item(
        Key={'message_id': message_id},
        UpdateExpression='SET processed = :p, action = :a',
        ExpressionAttributeValues={':p': True, ':a': f"label:{label}"},
    )
    return {'status': 'labeled'}


def archive_email(message_id: str) -> Dict[str, Any]:
    """Archive the Gmail message by removing it from the inbox."""
    service, _ = _get_gmail_service_for_message(message_id)
    if not service:
        return {'error': 'message or gmail service not found'}
    gm_id = ai_processor.find_message(service, message_id)
    if not gm_id:
        return {'error': 'gmail message not found'}
    service.users().messages().modify(
        userId='me', id=gm_id, body={'removeLabelIds': ['INBOX']}
    ).execute()
    email_table.update_item(
        Key={'message_id': message_id},
        UpdateExpression='SET processed = :p, action = :a',
        ExpressionAttributeValues={':p': True, ':a': 'archived'},
    )
    return {'status': 'archived'}


server = FastMCP(
    name='dmail-mcp',
    instructions='Expose email management tools for external AIs.'
)


@server.tool(name='list_emails', description='List stored emails for the AI inbox')
def tool_list_emails() -> list[Dict[str, Any]]:
    return list_emails()


@server.tool(name='draft_email', description='Store a draft reply for an email')
def tool_draft_email(message_id: str, draft: str) -> Dict[str, Any]:
    return draft_email(message_id, draft)


@server.tool(name='tag_email', description='Apply a Gmail label to the email')
def tool_tag_email(message_id: str, label: str) -> Dict[str, Any]:
    return add_label(message_id, label)


@server.tool(name='archive_email', description='Archive the email')
def tool_archive_email(message_id: str) -> Dict[str, Any]:
    return archive_email(message_id)


if __name__ == '__main__':
    server.run('stdio')
