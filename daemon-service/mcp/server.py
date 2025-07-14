from __future__ import annotations

from typing import Any, Dict, Tuple

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

# Import database
database_path = os.path.join(BASE_DIR, 'database.py')
spec_db = importlib.util.spec_from_file_location('database', database_path)
database = importlib.util.module_from_spec(spec_db)
spec_db.loader.exec_module(database)

db = database.db


def list_emails() -> list[Dict[str, Any]]:
    """Return all stored emails."""
    return db.scan_emails()


def draft_email(message_id: str, draft: str) -> Dict[str, Any]:
    """Store a draft reply for the given email."""
    success = db.update_email(message_id, {'draft': draft})
    if success:
        return {'status': 'draft stored'}
    return {'error': 'failed to store draft'}


def _get_gmail_service_for_message(message_id: str) -> Tuple[Any, Dict[str, Any] | None]:
    email_data = db.get_email(message_id)
    if not email_data:
        return None, None
    account = email_data.get('account')
    service = ai_processor.get_gmail_service(account)
    return service, email_data


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
    db.update_email(message_id, {'processed': True, 'action': f"label:{label}"})
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
    db.update_email(message_id, {'processed': True, 'action': 'archived'})
    return {'status': 'archived'}


server = FastMCP(
    name='dmail-mcp',
    instructions='Expose email management tools for external AIs.'
)


@server.tool(name='list_emails', description='List stored emails for the AI inbox')
def tool_list_emails() -> list[Dict[str, Any]]:
    return list_emails()


@server.tool(name='draft_email', description='Draft a reply for a specific email')
def tool_draft_email(message_id: str, draft: str) -> Dict[str, Any]:
    return draft_email(message_id, draft)


@server.tool(name='add_label', description='Add a Gmail label to an email')
def tool_add_label(message_id: str, label: str) -> Dict[str, Any]:
    return add_label(message_id, label)


@server.tool(name='archive_email', description='Archive an email in Gmail')
def tool_archive_email(message_id: str) -> Dict[str, Any]:
    return archive_email(message_id)


if __name__ == '__main__':
    server.run()
