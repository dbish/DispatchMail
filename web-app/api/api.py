import time
import json
import os
import asyncio
import imaplib
import threading
import importlib.util
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage

import boto3
from flask import Flask, jsonify, request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
observer_path = os.path.join(BASE_DIR, 'daemon-service', 'observer.py')
spec = importlib.util.spec_from_file_location('observer', observer_path)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)

filter_path = os.path.join(BASE_DIR, 'daemon-service', 'filter_utils.py')
spec_f = importlib.util.spec_from_file_location('filter_utils', filter_path)
filter_utils = importlib.util.module_from_spec(spec_f)
spec_f.loader.exec_module(filter_utils)

# Load MCP server utilities
mcp_path = os.path.join(BASE_DIR, 'daemon-service', 'mcp', 'server.py')
spec_mcp = importlib.util.spec_from_file_location('mcp_server', mcp_path)
mcp_server = importlib.util.module_from_spec(spec_mcp)
spec_mcp.loader.exec_module(mcp_server)


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
    if not filter_utils.should_store(parsed_email):
        print("Email filtered by whitelist rules")
        return
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
                "draft": "",
                "account": current_user,
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
                'action': item.get('action', ''),
                'draft': item.get('draft', ''),
                'account': item.get('account', ''),
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


@app.route('/api/draft_prompt', methods=['GET', 'POST'])
def draft_prompt():
    """Get or update the drafting system prompt."""
    if request.method == 'POST':
        data = request.get_json() or {}
        prompt = data.get('prompt')
        if not prompt:
            return jsonify({'error': 'prompt required'}), 400
        try:
            meta_table.put_item(Item={'user': 'draft_prompt', 'prompt': prompt})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        return jsonify({'status': 'saved'})
    else:
        try:
            resp = meta_table.get_item(Key={'user': 'draft_prompt'})
            prompt = resp.get('Item', {}).get('prompt', '')
            return jsonify({'prompt': prompt})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/whitelist', methods=['GET', 'POST'])
def whitelist_rules():
    """Get or update whitelist rules."""
    if request.method == 'POST':
        data = request.get_json() or {}
        rules = data.get('rules')
        if not isinstance(rules, list):
            return jsonify({'error': 'rules must be a list'}), 400
        try:
            meta_table.put_item(
                Item={'user': 'whitelist_rules', 'rules': json.dumps(rules)}
            )
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        return jsonify({'status': 'saved'})
    else:
        try:
            resp = meta_table.get_item(Key={'user': 'whitelist_rules'})
            rules = json.loads(resp.get('Item', {}).get('rules', '[]'))
            return jsonify({'rules': rules})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/email/<msg_id>')
def get_email(msg_id):
    """Return a single email by message id."""
    try:
        resp = email_table.get_item(Key={'message_id': msg_id})
        item = resp.get('Item')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if not item:
        return jsonify({'error': 'not found'}), 404
    return jsonify({
        'id': item.get('message_id'),
        'from': json.loads(item.get('from', '[]')),
        'subject': item.get('subject', ''),
        'to': json.loads(item.get('to', '[]')),
        'body': item.get('body', ''),
        'date': item.get('date', ''),
        'processed': item.get('processed', False),
        'action': item.get('action', ''),
        'draft': item.get('draft', ''),
        'account': item.get('account', ''),
    })


@app.route('/api/draft', methods=['POST'])
def save_draft():
    """Save a draft reply without sending."""
    data = request.get_json() or {}
    msg_id = data.get('id')
    draft = data.get('draft', '')
    if not msg_id:
        return jsonify({'error': 'id required'}), 400
    try:
        result = mcp_server.draft_email(msg_id, draft)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(result)


@app.route('/api/label', methods=['POST'])
def label_email():
    """Apply a label to an email."""
    data = request.get_json() or {}
    msg_id = data.get('id')
    label = data.get('label')
    if not msg_id or not label:
        return jsonify({'error': 'id and label required'}), 400
    try:
        result = mcp_server.add_label(msg_id, label)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route('/api/archive', methods=['POST'])
def archive_email():
    """Archive an email."""
    data = request.get_json() or {}
    msg_id = data.get('id')
    if not msg_id:
        return jsonify({'error': 'id required'}), 400
    try:
        result = mcp_server.archive_email(msg_id)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route('/api/send', methods=['POST'])
def send_draft():
    """Send a drafted email."""
    data = request.get_json() or {}
    msg_id = data.get('id')
    draft = data.get('draft', '')
    if not msg_id:
        return jsonify({'error': 'id required'}), 400
    try:
        resp = email_table.get_item(Key={'message_id': msg_id})
        item = resp.get('Item')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if not item:
        return jsonify({'error': 'email not found'}), 404
    account = item.get('account')
    try:
        u = users_table.get_item(Key={'user': account}).get('Item')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if not u:
        return jsonify({'error': 'account not found'}), 404
    password = u.get('password')
    to_addrs = json.loads(item.get('from', '[]'))
    if isinstance(to_addrs, list) and len(to_addrs) > 0:
        first = to_addrs[0]
        if isinstance(first, list) or isinstance(first, tuple):
            to_addr = first[1]
        else:
            to_addr = first
    else:
        to_addr = ''
    try:
        msg = EmailMessage()
        msg['Subject'] = 'Re: ' + item.get('subject', '')
        msg['From'] = account
        msg['To'] = to_addr
        msg.set_content(draft)
        smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        smtp.login(account, password)
        smtp.send_message(msg)
        smtp.quit()
        email_table.update_item(
            Key={'message_id': msg_id},
            UpdateExpression='SET draft = :d, processed = :p, action = :a',
            ExpressionAttributeValues={':d': draft, ':p': True, ':a': 'sent'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'status': 'sent'})

