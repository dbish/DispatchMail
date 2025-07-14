import time
import json
import os
import asyncio
import imaplib
import threading
import importlib.util
import sys
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage

import boto3
from boto3.dynamodb.conditions import Attr
from flask import Flask, jsonify, request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
daemon_service_dir = os.path.join(BASE_DIR, 'daemon-service')

# Add daemon-service to Python path so imports work
sys.path.insert(0, daemon_service_dir)

observer_path = os.path.join(daemon_service_dir, 'observer.py')
spec = importlib.util.spec_from_file_location('observer', observer_path)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)

filter_path = os.path.join(daemon_service_dir, 'filter_utils.py')
spec_f = importlib.util.spec_from_file_location('filter_utils', filter_path)
filter_utils = importlib.util.module_from_spec(spec_f)
spec_f.loader.exec_module(filter_utils)

# Load MCP server utilities
# mcp_path = os.path.join(daemon_service_dir, 'mcp', 'server.py')
# spec_mcp = importlib.util.spec_from_file_location('mcp_server', mcp_path)
# mcp_server = importlib.util.module_from_spec(spec_mcp)
# spec_mcp.loader.exec_module(mcp_server)

# Temporary placeholder for MCP functions
class MockMCPServer:
    def draft_email(self, message_id, draft):
        return {'error': 'MCP server not available'}
    def add_label(self, message_id, label):
        return {'error': 'MCP server not available'}
    def archive_email(self, message_id):
        return {'error': 'MCP server not available'}

mcp_server = MockMCPServer()

# Import config_reader to get AWS settings
import config_reader

AWS_REGION = config_reader.AWS_REGION
DYNAMODB_TABLE = config_reader.DYNAMODB_TABLE
DYNAMODB_META_TABLE = config_reader.DYNAMODB_META_TABLE
DYNAMODB_USERS_TABLE = config_reader.DYNAMODB_USERS_TABLE
LOOKBACK_DAYS = config_reader.LOOKBACK_DAYS
HOST = config_reader.HOST

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
email_table = dynamodb.Table(DYNAMODB_TABLE)
meta_table = dynamodb.Table(DYNAMODB_META_TABLE)
users_table = dynamodb.Table(DYNAMODB_USERS_TABLE)

# Track running observer threads to avoid duplicates
observer_threads = {}

# Track reprocessing status
reprocessing_status = {
    'is_reprocessing': False,
    'start_time': None,
    'message': ''
}


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


def reprocess_emails_with_new_rules():
    """Reprocess emails from the last LOOKBACK_DAYS period with new whitelist rules."""
    global reprocessing_status
    
    reprocessing_status['is_reprocessing'] = True
    reprocessing_status['start_time'] = datetime.utcnow().isoformat()
    reprocessing_status['message'] = 'Starting email reprocessing...'
    
    print("Starting email reprocessing with new whitelist rules...")
    
    try:
        # Get all users to reprocess their emails
        users_response = users_table.scan()
        users = users_response.get('Items', [])
        
        total_users = len(users)
        
        for i, user_item in enumerate(users):
            user_email = user_item.get('user')
            host = user_item.get('host')
            password = user_item.get('password')
            
            if not all([user_email, host, password]):
                continue
                
            reprocessing_status['message'] = f'Processing user {i+1}/{total_users}: {user_email}'
            print(f"Reprocessing emails for user: {user_email}")
            
            # Get the reprocessing time window
            since_dt = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
            
            # Get all emails from this user in the time window
            response = email_table.scan(
                FilterExpression=Attr('account').eq(user_email) & 
                                Attr('date').gte(since_dt.isoformat())
            )
            stored_emails = response.get('Items', [])
            
            # Create a set of message IDs that are currently stored
            stored_message_ids = {email.get('message_id') for email in stored_emails}
            
            # Re-evaluate stored emails against new rules
            emails_to_remove = []
            for email in stored_emails:
                # Reconstruct a mailparser-like object to test against rules
                class MockParsedEmail:
                    def __init__(self, email_item):
                        self.message_id = email_item.get('message_id')
                        self.subject = email_item.get('subject')
                        self.from_ = json.loads(email_item.get('from', '[]'))
                        self.to = json.loads(email_item.get('to', '[]'))
                        self.reply_to = []  # Not stored in our DB currently
                        self.date = datetime.fromisoformat(email_item.get('date')) if email_item.get('date') else None
                
                mock_email = MockParsedEmail(email)
                
                # Check if email still passes the new rules
                if not filter_utils.should_store(mock_email):
                    emails_to_remove.append(email['message_id'])
                    print(f"Email {email['message_id']} no longer passes whitelist rules - will be removed")
            
            # Remove emails that no longer pass the rules
            if emails_to_remove:
                reprocessing_status['message'] = f'Removing {len(emails_to_remove)} emails that no longer match rules...'
            
            for message_id in emails_to_remove:
                try:
                    email_table.delete_item(Key={'message_id': message_id})
                    print(f"Removed email {message_id}")
                except Exception as e:
                    print(f"Error removing email {message_id}: {e}")
            
            # Now fetch emails from Gmail to find any that now pass the rules
            reprocessing_status['message'] = f'Fetching emails from Gmail for {user_email}...'
            
            try:
                imap = imaplib.IMAP4_SSL(host)
                imap.login(user_email, password)
                imap.select("INBOX")
                
                since_str = since_dt.strftime("%d-%b-%Y")
                typ, data = imap.search(None, f"(SINCE {since_str})")
                ids = data[0].split()
                
                newly_processed = 0
                total_emails = len(ids)
                
                for j, msg_id in enumerate(ids):
                    if j % 10 == 0:  # Update status every 10 emails
                        reprocessing_status['message'] = f'Processing email {j+1}/{total_emails} for {user_email}...'
                    
                    typ, msg_data = imap.fetch(msg_id, "(RFC822)")
                    for part in msg_data:
                        if isinstance(part, tuple):
                            parsed = observer.mailparser.parse_from_bytes(part[1])
                            
                            # Skip if we already have this email stored
                            if parsed.message_id in stored_message_ids:
                                continue
                            
                            # Check if this email now passes the new rules
                            if filter_utils.should_store(parsed):
                                process_email(user_email, parsed)
                                newly_processed += 1
                                print(f"Email {parsed.message_id} now passes whitelist rules - added to inbox")
                
                imap.logout()
                print(f"Processed {newly_processed} new emails for {user_email}")
                
            except Exception as e:
                print(f"Error reprocessing emails from Gmail for {user_email}: {e}")
                
    except Exception as e:
        print(f"Error during email reprocessing: {e}")
        reprocessing_status['message'] = f'Error during reprocessing: {str(e)}'
    
    finally:
        reprocessing_status['is_reprocessing'] = False
        reprocessing_status['message'] = 'Email reprocessing completed.'
        print("Email reprocessing completed.")


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
        
        # Add a timestamp for change detection
        last_modified = max([email.get('date', '') for email in emails] + [''])
        
        return jsonify({
            'emails': emails,
            'last_modified': last_modified,
            'count': len(emails)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/emails/status')
def get_emails_status():
    """Return just the count and last modified timestamp for efficient polling."""
    try:
        response = email_table.scan()
        items = response.get('Items', [])
        
        # Get the most recent email date as last modified
        last_modified = ''
        if items:
            dates = [item.get('date', '') for item in items if item.get('date')]
            if dates:
                last_modified = max(dates)
        
        unprocessed_count = sum(1 for item in items if not item.get('processed', False))
        
        return jsonify({
            'count': len(items),
            'unprocessed_count': unprocessed_count,
            'last_modified': last_modified
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify_credentials', methods=['POST'])
def verify_credentials():
    """Verify Gmail credentials without starting email processing."""
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
        return jsonify({'status': 'verified'})
    except Exception as e:
        return jsonify({'error': 'Invalid IMAP credentials'}), 401


@app.route('/api/onboard', methods=['POST'])
def onboard():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'email and password required'}), 400

    # verify credentials with Gmail (again for safety)
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

    # Only start email processing after whitelist rules are configured
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
            
            # Trigger reprocessing of emails with new rules
            print("Whitelist rules updated, triggering email reprocessing...")
            reprocessing_thread = threading.Thread(target=reprocess_emails_with_new_rules, daemon=True)
            reprocessing_thread.start()
            
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


@app.route('/api/reprocessing_status')
def get_reprocessing_status():
    """Return the current reprocessing status."""
    return jsonify(reprocessing_status)

