import time
import json
import os
import asyncio
import imaplib
import threading
import importlib.util
from datetime import datetime, timedelta

import boto3
from flask import Flask, jsonify, request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
observer_path = os.path.join(BASE_DIR, 'daemon-service', 'observer.py')
spec = importlib.util.spec_from_file_location('observer', observer_path)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'dmail_emails')
HOST = os.getenv('HOST', 'imap.gmail.com')
DYNAMODB_META_TABLE = os.getenv('DYNAMODB_META_TABLE', 'dmail_metadata')
DYNAMODB_USERS_TABLE = os.getenv('DYNAMODB_USERS_TABLE', 'dmail_users')
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '5'))

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
email_table = dynamodb.Table(DYNAMODB_TABLE)
meta_table = dynamodb.Table(DYNAMODB_META_TABLE)
users_table = dynamodb.Table(DYNAMODB_USERS_TABLE)

# Track running observer threads to avoid duplicates
observer_threads = {}


def start_observer(host, user, password):
    """Start background monitoring for a user's inbox."""
    if user in observer_threads:
        return

    def run():
        asyncio.run(observer.loop_and_retry(host, user, password))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    observer_threads[user] = thread


def get_last_processed_date(user):
    try:
        response = meta_table.get_item(Key={"user": user})
        item = response.get("Item")
        if item and item.get("last_processed"):
            return datetime.fromisoformat(item["last_processed"])
    except Exception as e:
        print(f"Error getting last processed date: {e}")
    return None


def update_last_processed_date(user, dt):
    if not dt:
        return
    try:
        current = get_last_processed_date(user)
        if not current or dt > current:
            meta_table.put_item(Item={"user": user, "last_processed": dt.isoformat()})
    except Exception as e:
        print(f"Error updating last processed date: {e}")


def process_email(current_user, parsed_email):
    from_email = parsed_email.from_
    if len(parsed_email.reply_to) > 0:
        from_email = parsed_email.reply_to

    body = parsed_email.text_plain[0] if parsed_email.text_plain else ""

    try:
        email_table.put_item(
            Item={
                "message_id": parsed_email.message_id or "",
                "subject": parsed_email.subject or "",
                "to": json.dumps(parsed_email.to),
                "from": json.dumps(from_email),
                "body": body,
                "date": parsed_email.date.isoformat() if parsed_email.date else "",
                "processed": False,
                "action": "",
            }
        )
        if parsed_email.date:
            update_last_processed_date(current_user, parsed_email.date)
    except Exception as e:
        print(f"Error saving email: {e}")


def hydrate_inbox(host, user, password):
    """Fetch recent emails and store them."""
    try:
        imap = imaplib.IMAP4_SSL(host)
        imap.login(user, password)
        imap.select("INBOX")
        last_processed = get_last_processed_date(user)
        if last_processed:
            since_dt = last_processed
        else:
            since_dt = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
        since_str = since_dt.strftime("%d-%b-%Y")
        typ, data = imap.search(None, f"(SINCE {since_str})")
        ids = data[0].split()
        for msg_id in ids:
            typ, msg_data = imap.fetch(msg_id, "(RFC822)")
            for part in msg_data:
                if isinstance(part, tuple):
                    parsed = observer.mailparser.parse_from_bytes(part[1])
                    process_email(user, parsed)
        imap.logout()
    except Exception as e:
        print(f"Error during hydration for {user}: {e}")

app = Flask(__name__)

@app.route('/api/time')
def get_current_time():
    return {'time': time.time()}


@app.route('/api/emails')
def get_emails():
    """Return emails stored in DynamoDB."""
    try:
        response = email_table.scan()
        items = response.get('Items', [])
        # convert stringified fields back
        emails = []
        for item in items:
            emails.append({
                'id': item.get('message_id'),
                'from': json.loads(item.get('from', '[]')),
                'subject': item.get('subject', ''),
                'to': json.loads(item.get('to', '[]')),
                'body': item.get('body', ''),
                'date': item.get('date', ''),
                'processed': item.get('processed', False),
                'action': item.get('action', '')
            })
        return jsonify(emails)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/onboard', methods=['POST'])
def onboard():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'email and password required'}), 400

    # verify credentials with Gmail
    try:
        imap = imaplib.IMAP4_SSL(HOST)
        imap.login(email, password)
        imap.logout()
    except Exception:
        return jsonify({'error': 'Invalid IMAP credentials'}), 401

    try:
        users_table.put_item(Item={'user': email, 'host': HOST, 'password': password})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    hydrate_inbox(HOST, email, password)
    start_observer(HOST, email, password)

    return jsonify({'status': 'success'})


@app.route('/api/prompt', methods=['GET', 'POST'])
def reading_prompt():
    """Get or update the system prompt for the reading agent."""
    if request.method == 'POST':
        data = request.get_json() or {}
        prompt = data.get('prompt')
        if not prompt:
            return jsonify({'error': 'prompt required'}), 400
        try:
            meta_table.put_item(Item={'user': 'reading_prompt', 'prompt': prompt})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        return jsonify({'status': 'saved'})
    else:
        try:
            resp = meta_table.get_item(Key={'user': 'reading_prompt'})
            prompt = resp.get('Item', {}).get('prompt', '')
            return jsonify({'prompt': prompt})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

