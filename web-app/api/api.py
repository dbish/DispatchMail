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
from dateutil import tz
from email_reply_parser import EmailReplyParser
from openai import OpenAI

import boto3
from boto3.dynamodb.conditions import Attr
from flask import Flask, jsonify, request
from flask_cors import CORS

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

# Get OpenAI API key from config_reader (which reads from secrets file)
OPENAI_API_KEY = config_reader.OPENAI_API_KEY

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

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def get_prompt():
    """Get the reading prompt from the database."""
    try:
        resp = meta_table.get_item(Key={'user': 'reading_prompt'})
        return resp.get('Item', {}).get('prompt', '')
    except:
        return ''

def get_draft_prompt():
    """Get the draft prompt from the database."""
    try:
        resp = meta_table.get_item(Key={'user': 'draft_prompt'})
        return resp.get('Item', {}).get('prompt', '')
    except:
        return ''

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
            dt = datetime.fromisoformat(item["last_processed"])
            # Ensure the datetime is timezone-aware and in UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz.UTC)
            elif dt.tzinfo != tz.UTC:
                dt = dt.astimezone(tz.UTC)
            return dt
    except Exception as e:
        print(f"Error getting last processed date: {e}")
    return None


def update_last_processed_date(user, dt):
    if not dt:
        return
    try:
        # Convert to UTC if timezone-aware, otherwise assume UTC
        if dt.tzinfo is not None:
            dt_utc = dt.astimezone(tz.UTC)
        else:
            dt_utc = dt.replace(tzinfo=tz.UTC)
        
        current = get_last_processed_date(user)
        if not current or dt_utc > current:
            meta_table.put_item(Item={"user": user, "last_processed": dt_utc.isoformat()})
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
        # Convert email date to UTC before storing
        utc_date = None
        if parsed_email.date:
            if parsed_email.date.tzinfo is not None:
                utc_date = parsed_email.date.astimezone(tz.UTC)
            else:
                utc_date = parsed_email.date.replace(tzinfo=tz.UTC)
        
        email_table.put_item(
            Item={
                "message_id": parsed_email.message_id or "",
                "subject": parsed_email.subject or "",
                "to": json.dumps(parsed_email.to),
                "from": json.dumps(from_email),
                "body": body,
                "date": utc_date.isoformat() if utc_date else "",
                "processed": False,
                "action": "",
                "draft": "",
                "account": current_user,
            }
        )
        if utc_date:
            update_last_processed_date(current_user, utc_date)
    except Exception as e:
        print(f"Error saving email: {e}")
        return

    # Enable automatic AI processing for whitelisted emails
    if OPENAI_API_KEY and client:
        try:
            # Process the email with AI immediately using the same logic as manual processing
            process_email_with_ai_sync(current_user, parsed_email)
            print(f"Automatically processed email with AI: {parsed_email.message_id}")
        except Exception as e:
            print(f"Error in automatic AI processing for email {parsed_email.message_id}: {e}")
    else:
        print("OpenAI API key not configured, skipping AI processing")


def process_email_with_ai_sync(user, parsed_email):
    """Process an email with AI synchronously."""
    try:
        # Extract key content for LLM processing
        print(f"DEBUG: Extracting key content for email {parsed_email.message_id}")
        key_content = extract_key_content_from_email_item(parsed_email)
        print(f"DEBUG: Key content extracted: {len(key_content)} characters")
        
        # Get the prompts before the API call to avoid scoping issues
        system_prompt = get_prompt()
        draft_instructions = get_draft_prompt()
        print(f"DEBUG: Got system_prompt: {system_prompt}")
        print(f"DEBUG: Got draft_instructions: {draft_instructions}")
        
        # Process with AI
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"{system_prompt}\nDrafting instructions: {draft_instructions}",
                },
                {
                    "role": "user",
                    "content": f"Email content:\n{key_content}\n\nRespond with ONLY a JSON object. No other text or explanation."
                },
            ],
            temperature=0,
        )
        
        response_text = completion.choices[0].message.content.strip()
        
        # Clean up the response - remove markdown code blocks if present
        if response_text.startswith('```json'):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith('```'):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith('```'):
            response_text = response_text[:-3]  # Remove trailing ```
        response_text = response_text.strip()
        
        # Parse the JSON response
        try:
            ai_response = json.loads(response_text)
        except json.JSONDecodeError:
            ai_response = {"reviewed": True}  # Default fallback
        
        # Extract draft if present
        draft_text = ai_response.get('draft') or ai_response.get('response')
        
        # Update the email in DynamoDB
        update_expr = "SET #processed = :p, #action = :a"
        expr_values = {
            ":p": True,
            ":a": "drafted" if draft_text else "reviewed (no action needed)"
        }
        
        expr_names = {
            "#processed": "processed",
            "#action": "action"
        }
        
        if draft_text:
            update_expr += ", draft = :d, llm_prompt = :lp"
            expr_values[":d"] = draft_text
            expr_values[":lp"] = key_content  # Store what was sent to LLM
        
        email_table.update_item(
            Key={'message_id': parsed_email.message_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        
        print(f"AI processing completed for email: {parsed_email.message_id} - Action: {expr_values[':a']}")
        
    except Exception as e:
        print(f"Error in AI processing for email {parsed_email.message_id}: {e}")


async def process_email_with_ai(user, parsed_email):
    """Process an email with AI asynchronously."""
    try:
        # Import here to avoid circular imports
        sys.path.insert(0, daemon_service_dir)
        import ai_processor
        
        # Process the email with AI
        await ai_processor.handle_email(user, parsed_email)
        print(f"AI processing completed for email: {parsed_email.message_id}")
    except Exception as e:
        print(f"Error in AI processing for email {parsed_email.message_id}: {e}")


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
            since_dt = datetime.now(tz.UTC) - timedelta(days=LOOKBACK_DAYS)
        
        # Use the day before to ensure we catch all emails due to timezone issues
        search_dt = since_dt - timedelta(days=1)
        since_str = search_dt.strftime("%d-%b-%Y")
        print(f"Hydrating inbox since (UTC): {since_dt} -> searching from {since_str}")
        typ, data = imap.search(None, f"(SINCE {since_str})")
        ids = data[0].split()
        for msg_id in ids:
            typ, msg_data = imap.fetch(msg_id, "(RFC822)")
            for part in msg_data:
                if isinstance(part, tuple):
                    parsed = observer.mailparser.parse_from_bytes(part[1])
                    # Filter out emails that are actually older than our target date
                    if parsed.date and since_dt:
                        # Ensure both dates are timezone-aware for comparison
                        email_date = parsed.date
                        if email_date.tzinfo is None:
                            email_date = email_date.replace(tzinfo=tz.UTC)
                        elif email_date.tzinfo != tz.UTC:
                            email_date = email_date.astimezone(tz.UTC)
                        
                        if email_date <= since_dt:
                            continue
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
            since_dt = datetime.now(tz.UTC) - timedelta(days=LOOKBACK_DAYS)
            
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
                print(f"Reprocessing emails since (UTC): {since_dt} -> {since_str}")
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
CORS(app)  # Enable CORS for all routes

def initialize_observers():
    """Start observer threads for all existing users on startup."""
    try:
        print("Initializing observers for existing users...")
        users_response = users_table.scan()
        users = users_response.get('Items', [])
        
        for user_item in users:
            user_email = user_item.get('user')
            host = user_item.get('host')
            password = user_item.get('password')
            
            if all([user_email, host, password]):
                print(f"Starting observer for user: {user_email}")
                start_observer(host, user_email, password)
            else:
                print(f"Skipping user with incomplete credentials: {user_email}")
                
        print(f"Initialized observers for {len(users)} users")
    except Exception as e:
        print(f"Error initializing observers: {e}")

# Initialize observer threads for existing users
initialize_observers()

def periodic_sync():
    """Periodic backup sync to catch emails IDLE might miss."""
    while True:
        try:
            time.sleep(120)  # Wait 2 minutes between syncs
            print("Running periodic backup sync...")
            
            # Get all users
            users_response = users_table.scan()
            users = users_response.get('Items', [])
            
            for user_item in users:
                user_email = user_item.get('user')
                host = user_item.get('host')
                password = user_item.get('password')
                
                if not all([user_email, host, password]):
                    continue
                
                try:
                    # Check if observer thread is still alive
                    thread = observer_threads.get(user_email)
                    if not thread or not thread.is_alive():
                        print(f"Observer thread for {user_email} is dead, restarting...")
                        start_observer(host, user_email, password)
                    
                    # Connect to IMAP and check for new emails since last processed
                    imap = imaplib.IMAP4_SSL(host)
                    imap.login(user_email, password)
                    imap.select("INBOX")
                    
                    # Get last processed date
                    last_processed = get_last_processed_date(user_email)
                    if last_processed:
                        since_dt = last_processed
                    else:
                        since_dt = datetime.now(tz.UTC) - timedelta(days=LOOKBACK_DAYS)
                    
                    # Use the day before to ensure we catch all emails due to timezone issues
                    search_dt = since_dt - timedelta(days=1)
                    since_str = search_dt.strftime("%d-%b-%Y")
                    print(f"Periodic sync since (UTC): {since_dt} -> searching from {since_str}")
                    
                    # Search for emails
                    typ, data = imap.search(None, f"(SINCE {since_str})")
                    ids = data[0].split()
                    
                    new_emails_count = 0
                    
                    for msg_id in ids:
                        typ, msg_data = imap.fetch(msg_id, "(RFC822)")
                        for part in msg_data:
                            if isinstance(part, tuple):
                                parsed = observer.mailparser.parse_from_bytes(part[1])
                                
                                # Check if this email is newer than last processed
                                if last_processed and parsed.date:
                                    # Ensure both dates are timezone-aware for comparison
                                    email_date = parsed.date
                                    if email_date.tzinfo is None:
                                        email_date = email_date.replace(tzinfo=tz.UTC)
                                    elif email_date.tzinfo != tz.UTC:
                                        email_date = email_date.astimezone(tz.UTC)
                                    
                                    if email_date <= last_processed:
                                        continue
                                
                                # Check if email already exists
                                existing = email_table.get_item(Key={'message_id': parsed.message_id})
                                if existing.get('Item'):
                                    continue
                                
                                # Apply whitelist filtering
                                if not filter_utils.should_store(parsed):
                                    continue
                                
                                # Process the email
                                print(f"Periodic sync found new email: {parsed.subject} from {parsed.from_}")
                                process_email(user_email, parsed)
                                new_emails_count += 1
                    
                    if new_emails_count > 0:
                        print(f"Periodic sync processed {new_emails_count} new emails for {user_email}")
                    
                    imap.logout()
                    
                except Exception as e:
                    print(f"Error in periodic sync for {user_email}: {e}")
                    
        except Exception as e:
            print(f"Error in periodic sync loop: {e}")

# Start periodic sync in background thread
periodic_thread = threading.Thread(target=periodic_sync, daemon=True)
periodic_thread.start()
print("Started periodic backup sync (every 2 minutes)")

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
                'llm_prompt': item.get('llm_prompt', ''),
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
        print(f"Error getting email: {e}")
        return jsonify({'error': str(e)}), 500
    if not item:
        return jsonify({'error': 'email not found'}), 404
    account = item.get('account')
    try:
        u = users_table.get_item(Key={'user': account}).get('Item')
    except Exception as e:
        print(f"Error getting user: {e}")
        return jsonify({'error': str(e)}), 500
    if not u:
        return jsonify({'error': 'account not found'}), 404
    password = u.get('password')
    
    # Parse the 'from' field to get the reply-to address
    from_field = item.get('from', '[]')
    try:
        to_addrs = json.loads(from_field)
        print(f"Parsed from field: {to_addrs}")
        
        # Handle different formats of the from field
        if isinstance(to_addrs, list) and len(to_addrs) > 0:
            first = to_addrs[0]
            if isinstance(first, (list, tuple)) and len(first) > 1:
                # Format: [["Name", "email@domain.com"]]
                to_addr = first[1]
            elif isinstance(first, str):
                # Format: ["email@domain.com"]
                to_addr = first
            else:
                print(f"Unexpected from field format: {first}")
                to_addr = str(first)
        else:
            print(f"Empty or invalid from field: {to_addrs}")
            return jsonify({'error': 'No reply address found'}), 400
            
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Error parsing from field: {e}")
        return jsonify({'error': 'Invalid from field format'}), 400
    
    if not to_addr:
        return jsonify({'error': 'No reply address found'}), 400
        
    print(f"Sending email to: {to_addr}")
    
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
        
        # Update the email record with proper ExpressionAttributeNames
        email_table.update_item(
            Key={'message_id': msg_id},
            UpdateExpression='SET draft = :d, #processed = :p, #action = :a',
            ExpressionAttributeNames={
                '#processed': 'processed',
                '#action': 'action'
            },
            ExpressionAttributeValues={':d': draft, ':p': True, ':a': 'sent'}
        )
        print(f"Email sent successfully to {to_addr}")
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return jsonify({'error': f'Failed to send email: {str(e)}'}), 500
    
    return jsonify({'status': 'sent'})


@app.route('/api/reprocessing_status')
def get_reprocessing_status():
    """Return the current reprocessing status."""
    return jsonify(reprocessing_status)


def extract_key_content_from_email_item(email_item) -> str:
    """Extract the key content from a stored email item for more focused LLM processing."""
    body = email_item.get('body', '')
    subject = email_item.get('subject', '')
    
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
    prompt_content = f"Subject: {subject}\n\n{key_content}"
    
    return prompt_content


@app.route('/api/reprocess_single_email', methods=['POST'])
def reprocess_single_email():
    """Reprocess a single email with the current prompts."""
    print(f"DEBUG: reprocess_single_email function called")
    try:
        data = request.get_json() or {}
        email_id = data.get('email_id')
        
        print(f"DEBUG: Processing email_id: {email_id}")
        
        if not email_id:
            return jsonify({'error': 'email_id required'}), 400
        
        # Get the email from DynamoDB
        response = email_table.get_item(Key={'message_id': email_id})
        email_item = response.get('Item')
        
        if not email_item:
            return jsonify({'error': 'Email not found'}), 404
        
        # Extract key content for LLM processing
        print(f"DEBUG: Extracting key content for email {email_item.get('message_id')}")
        key_content = extract_key_content_from_email_item(email_item)
        print(f"DEBUG: Key content extracted: {len(key_content)} characters")
        
        # Create a mock parsed email object for compatibility
        print(f"DEBUG: Creating MockParsedEmail object")
        class MockParsedEmail:
            def __init__(self, email_item):
                self.message_id = email_item.get('message_id')
                self.subject = email_item.get('subject', '')
                self.from_ = json.loads(email_item.get('from', '[]'))
                self.text_plain = [email_item.get('body', '')]
                self.date = None
                if email_item.get('date'):
                    try:
                        self.date = datetime.fromisoformat(email_item['date'])
                    except:
                        pass
        
        print(f"DEBUG: About to call OpenAI API for email {email_item.get('message_id')}")
        print(f"DEBUG: get_prompt exists: {callable(get_prompt)}")
        print(f"DEBUG: get_draft_prompt exists: {callable(get_draft_prompt)}")
        
        # Get the prompts before the API call to avoid scoping issues
        system_prompt = get_prompt()
        draft_instructions = get_draft_prompt()
        print(f"DEBUG: Got system_prompt: {system_prompt}")
        print(f"DEBUG: Got draft_instructions: {draft_instructions}")
        
        # Process with AI
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"{system_prompt}\nDrafting instructions: {draft_instructions}",
                },
                {
                    "role": "user",
                    "content": f"Email content:\n{key_content}\n\nRespond with ONLY a JSON object. No other text or explanation."
                },
            ],
            temperature=0,
        )
        
        response_text = completion.choices[0].message.content.strip()
        
        # Clean up the response - remove markdown code blocks if present
        if response_text.startswith('```json'):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith('```'):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith('```'):
            response_text = response_text[:-3]  # Remove trailing ```
        response_text = response_text.strip()
        
        # Parse the JSON response
        try:
            ai_response = json.loads(response_text)
        except json.JSONDecodeError:
            ai_response = {"reviewed": True}  # Default fallback
        
        # Extract draft if present
        draft_text = ai_response.get('draft') or ai_response.get('response')
        
        # Update the email in DynamoDB
        update_expr = "SET #processed = :p, #action = :a"
        expr_values = {
            ":p": True,
            ":a": "drafted" if draft_text else "reviewed (no action needed)"
        }
        
        expr_names = {
            "#processed": "processed",
            "#action": "action"
        }
        
        if draft_text:
            update_expr += ", draft = :d, llm_prompt = :lp"
            expr_values[":d"] = draft_text
            expr_values[":lp"] = key_content  # Store what was sent to LLM
        
        email_table.update_item(
            Key={'message_id': email_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        
        return jsonify({
            'status': 'success',
            'new_draft': draft_text,
            'llm_prompt': key_content,
            'action': "drafted" if draft_text else "reviewed (no action needed)"
        })
        
    except Exception as e:
        print(f"Error in reprocess_single_email: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/process_unprocessed_emails', methods=['POST'])
def process_unprocessed_emails():
    """Process all unprocessed emails with AI."""
    print("DEBUG: process_unprocessed_emails called")
    try:
        # Get all unprocessed emails
        response = email_table.scan(
            FilterExpression="#processed = :processed",
            ExpressionAttributeNames={"#processed": "processed"},
            ExpressionAttributeValues={":processed": False}
        )
        
        unprocessed_emails = response['Items']
        print(f"DEBUG: Found {len(unprocessed_emails)} unprocessed emails")
        
        if not OPENAI_API_KEY:
            return jsonify({'error': 'OpenAI API key not configured'}), 500
        
        print("DEBUG: OpenAI API key is configured")
        processed_count = 0
        
        for i, email_item in enumerate(unprocessed_emails):
            print(f"DEBUG: Processing email {i+1}/{len(unprocessed_emails)}: {email_item.get('message_id')}")
            try:
                # Extract key content for LLM processing
                print(f"DEBUG: Extracting key content for email {email_item.get('message_id')}")
                key_content = extract_key_content_from_email_item(email_item)
                print(f"DEBUG: Key content extracted: {len(key_content)} characters")
                
                # Create a mock parsed email object for compatibility
                print(f"DEBUG: Creating MockParsedEmail object")
                class MockParsedEmail:
                    def __init__(self, email_item):
                        self.message_id = email_item.get('message_id')
                        self.subject = email_item.get('subject', '')
                        self.from_ = json.loads(email_item.get('from', '[]'))
                        self.text_plain = [email_item.get('body', '')]
                        self.date = None
                        if email_item.get('date'):
                            try:
                                self.date = datetime.fromisoformat(email_item['date'])
                            except:
                                pass
                
                print(f"DEBUG: About to call OpenAI API for email {email_item.get('message_id')}")
                print(f"DEBUG: get_prompt exists: {callable(get_prompt)}")
                print(f"DEBUG: get_draft_prompt exists: {callable(get_draft_prompt)}")
                
                # Get the prompts before the API call to avoid scoping issues
                system_prompt = get_prompt()
                draft_instructions = get_draft_prompt()
                print(f"DEBUG: Got system_prompt: {system_prompt}")
                print(f"DEBUG: Got draft_instructions: {draft_instructions}")
                
                # Process with AI
                completion = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": f"{system_prompt}\nDrafting instructions: {draft_instructions}",
                        },
                        {
                            "role": "user",
                            "content": f"Email content:\n{key_content}\n\nRespond with ONLY a JSON object. No other text or explanation."
                        },
                    ],
                    temperature=0,
                )
                
                response_text = completion.choices[0].message.content.strip()
                
                # Clean up the response - remove markdown code blocks if present
                if response_text.startswith('```json'):
                    response_text = response_text[7:]  # Remove ```json
                if response_text.startswith('```'):
                    response_text = response_text[3:]  # Remove ```
                if response_text.endswith('```'):
                    response_text = response_text[:-3]  # Remove trailing ```
                response_text = response_text.strip()
                
                # Parse the JSON response
                try:
                    ai_response = json.loads(response_text)
                except json.JSONDecodeError:
                    ai_response = {"reviewed": True}  # Default fallback
                
                # Extract draft if present
                draft_text = ai_response.get('draft') or ai_response.get('response')
                
                # Update the email in DynamoDB
                update_expr = "SET #processed = :p, #action = :a"
                expr_values = {
                    ":p": True,
                    ":a": "drafted" if draft_text else "reviewed (no action needed)"
                }
                
                expr_names = {
                    "#processed": "processed",
                    "#action": "action"
                }
                
                if draft_text:
                    update_expr += ", draft = :d, llm_prompt = :lp"
                    expr_values[":d"] = draft_text
                    expr_values[":lp"] = key_content  # Store what was sent to LLM
                
                email_table.update_item(
                    Key={'message_id': email_item['message_id']},
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames=expr_names,
                    ExpressionAttributeValues=expr_values
                )
                
                processed_count += 1
                
            except Exception as e:
                print(f"Error processing email {email_item.get('message_id')}: {e}")
                print(f"Error type: {type(e)}")
                print(f"Error details: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        return jsonify({
            'status': 'success',
            'processed_count': processed_count,
            'total_count': len(unprocessed_emails)
        })
        
    except Exception as e:
        print(f"Error in process_unprocessed_emails: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/debug/observers')
def debug_observers():
    """Debug endpoint to check observer thread status."""
    try:
        # Get all registered users
        users_response = users_table.scan()
        users = users_response.get('Items', [])
        
        observer_status = []
        for user_item in users:
            user_email = user_item.get('user')
            thread = observer_threads.get(user_email)
            
            observer_status.append({
                'user': user_email,
                'has_thread': thread is not None,
                'thread_alive': thread.is_alive() if thread else False
            })
        
        return jsonify({
            'total_users': len(users),
            'total_threads': len(observer_threads),
            'observers': observer_status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/manual_sync', methods=['POST'])
def manual_sync():
    """Manually sync emails for all users, bypassing IMAP IDLE."""
    try:
        # Get all users
        users_response = users_table.scan()
        users = users_response.get('Items', [])
        
        sync_results = []
        
        for user_item in users:
            user_email = user_item.get('user')
            host = user_item.get('host')
            password = user_item.get('password')
            
            if not all([user_email, host, password]):
                continue
            
            try:
                print(f"Manual sync for user: {user_email}")
                
                # Connect to IMAP and check for new emails
                imap = imaplib.IMAP4_SSL(host)
                imap.login(user_email, password)
                imap.select("INBOX")
                
                # Get last processed date
                last_processed = get_last_processed_date(user_email)
                if last_processed:
                    since_dt = last_processed
                    print(f"Looking for emails since: {since_dt}")
                else:
                    since_dt = datetime.now(tz.UTC) - timedelta(days=LOOKBACK_DAYS)
                    print(f"No last processed date, looking since: {since_dt}")
                
                # Use the day before to ensure we catch all emails due to timezone issues
                search_dt = since_dt - timedelta(days=1)
                since_str = search_dt.strftime("%d-%b-%Y")
                print(f"Manual sync since (UTC): {since_dt} -> searching from {since_str}")
                
                # Search for emails
                typ, data = imap.search(None, f"(SINCE {since_str})")
                ids = data[0].split()
                
                print(f"Found {len(ids)} emails since {since_str}")
                
                new_emails_count = 0
                
                for msg_id in ids:
                    typ, msg_data = imap.fetch(msg_id, "(RFC822)")
                    for part in msg_data:
                        if isinstance(part, tuple):
                            parsed = observer.mailparser.parse_from_bytes(part[1])
                            
                            # Check if this email is newer than last processed
                            if last_processed and parsed.date:
                                # Ensure both dates are timezone-aware for comparison
                                email_date = parsed.date
                                if email_date.tzinfo is None:
                                    email_date = email_date.replace(tzinfo=tz.UTC)
                                elif email_date.tzinfo != tz.UTC:
                                    email_date = email_date.astimezone(tz.UTC)
                                
                                if email_date <= last_processed:
                                    continue
                            
                            # Check if email already exists
                            existing = email_table.get_item(Key={'message_id': parsed.message_id})
                            if existing.get('Item'):
                                continue
                            
                            # Apply whitelist filtering
                            if not filter_utils.should_store(parsed):
                                print(f"Email filtered: {parsed.subject} from {parsed.from_}")
                                continue
                            
                            # Process the email
                            print(f"Processing new email: {parsed.subject} from {parsed.from_}")
                            process_email(user_email, parsed)
                            new_emails_count += 1
                
                imap.logout()
                
                sync_results.append({
                    'user': user_email,
                    'new_emails': new_emails_count,
                    'status': 'success'
                })
                
            except Exception as e:
                print(f"Error syncing user {user_email}: {e}")
                sync_results.append({
                    'user': user_email,
                    'error': str(e),
                    'status': 'error'
                })
        
        return jsonify({
            'message': 'Manual sync completed',
            'results': sync_results
        })
        
    except Exception as e:
        print(f"Error during manual sync: {e}")
        return jsonify({'error': f'Failed to sync: {str(e)}'}), 500


@app.route('/api/debug/imap_search', methods=['POST'])
def debug_imap_search():
    """Debug endpoint to show what emails are actually in the inbox and test different search queries."""
    try:
        # Get all users
        users_response = users_table.scan()
        users = users_response.get('Items', [])
        
        debug_results = []
        
        for user_item in users:
            user_email = user_item.get('user')
            host = user_item.get('host')
            password = user_item.get('password')
            
            if not all([user_email, host, password]):
                continue
            
            try:
                print(f"Debug IMAP search for user: {user_email}")
                
                # Connect to IMAP
                imap = imaplib.IMAP4_SSL(host)
                imap.login(user_email, password)
                imap.select("INBOX")
                
                # Get last processed date
                last_processed = get_last_processed_date(user_email)
                current_time = datetime.now(tz.UTC)
                
                # Test different search queries
                search_results = {}
                
                # 1. Search all emails from today
                today_str = current_time.strftime("%d-%b-%Y")
                typ, data = imap.search(None, f"(SINCE {today_str})")
                today_ids = data[0].split()
                search_results['today'] = {
                    'query': f"(SINCE {today_str})",
                    'count': len(today_ids),
                    'ids': [id.decode() for id in today_ids[:10]]  # Show first 10
                }
                
                # 2. Search emails from yesterday
                yesterday = current_time - timedelta(days=1)
                yesterday_str = yesterday.strftime("%d-%b-%Y")
                typ, data = imap.search(None, f"(SINCE {yesterday_str})")
                yesterday_ids = data[0].split()
                search_results['yesterday'] = {
                    'query': f"(SINCE {yesterday_str})",
                    'count': len(yesterday_ids),
                    'ids': [id.decode() for id in yesterday_ids[:10]]
                }
                
                # 3. Search using last processed date
                if last_processed:
                    since_str = last_processed.strftime("%d-%b-%Y")
                    typ, data = imap.search(None, f"(SINCE {since_str})")
                    since_ids = data[0].split()
                    search_results['since_last_processed'] = {
                        'query': f"(SINCE {since_str})",
                        'last_processed': last_processed.isoformat(),
                        'count': len(since_ids),
                        'ids': [id.decode() for id in since_ids[:10]]
                    }
                
                # 4. Get the most recent 10 emails to see their actual timestamps
                typ, data = imap.search(None, "ALL")
                all_ids = data[0].split()
                recent_ids = all_ids[-10:]  # Last 10 emails
                
                recent_emails = []
                for msg_id in recent_ids:
                    try:
                        typ, msg_data = imap.fetch(msg_id, "(RFC822)")
                        for part in msg_data:
                            if isinstance(part, tuple):
                                parsed = observer.mailparser.parse_from_bytes(part[1])
                                recent_emails.append({
                                    'id': msg_id.decode(),
                                    'subject': parsed.subject,
                                    'from': parsed.from_,
                                    'date': parsed.date.isoformat() if parsed.date else None,
                                    'date_utc': parsed.date.astimezone(tz.UTC).isoformat() if parsed.date else None,
                                    'message_id': parsed.message_id
                                })
                    except Exception as e:
                        print(f"Error parsing email {msg_id}: {e}")
                        continue
                
                # Sort by date descending
                recent_emails.sort(key=lambda x: x['date_utc'] or '', reverse=True)
                
                imap.logout()
                
                debug_results.append({
                    'user': user_email,
                    'current_time_utc': current_time.isoformat(),
                    'last_processed': last_processed.isoformat() if last_processed else None,
                    'search_results': search_results,
                    'recent_emails': recent_emails,
                    'status': 'success'
                })
                
            except Exception as e:
                print(f"Error in debug search for {user_email}: {e}")
                debug_results.append({
                    'user': user_email,
                    'error': str(e),
                    'status': 'error'
                })
        
        return jsonify({
            'debug_results': debug_results
        })
        
    except Exception as e:
        print(f"Error in debug IMAP search: {e}")
        return jsonify({'error': f'Failed to debug IMAP search: {str(e)}'}), 500


@app.route('/api/delete_draft', methods=['POST'])
def delete_draft():
    """Delete a draft and mark email as processed with no action."""
    try:
        data = request.get_json() or {}
        email_id = data.get('email_id')
        
        if not email_id:
            return jsonify({'error': 'email_id required'}), 400
        
        # Update the email to remove draft and mark as processed
        email_table.update_item(
            Key={'message_id': email_id},
            UpdateExpression='SET #processed = :p, #action = :a, draft = :d',
            ExpressionAttributeNames={
                '#processed': 'processed',
                '#action': 'action'
            },
            ExpressionAttributeValues={
                ':p': True, 
                ':a': 'reviewed (no action needed)', 
                ':d': ''
            }
        )
        
        return jsonify({'message': 'Draft deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': f'Failed to delete draft: {str(e)}'}), 500


@app.route('/api/user_profile', methods=['GET'])
def get_user_profile():
    """Get user profile information."""
    try:
        # Get the current user's email from query parameter or session
        user_email = request.args.get('email')
        if not user_email:
            return jsonify({'error': 'User email required'}), 400
            
        # Check if we have stored user profile information
        try:
            resp = users_table.get_item(Key={'user': user_email})
            user_item = resp.get('Item')
            if user_item:
                display_name = user_item.get('display_name')
                if display_name:
                    return jsonify({
                        'email': user_email,
                        'name': display_name,
                        'avatar_url': None  # Could be implemented later
                    })
        except Exception as e:
            print(f"Error fetching user profile from database: {e}")
        
        # If no stored name, extract name from email or use fallback
        if '@' in user_email:
            # Extract name from email prefix (e.g., "john.doe@gmail.com" -> "John Doe")
            name_part = user_email.split('@')[0]
            # Replace dots/underscores with spaces and capitalize
            display_name = ' '.join(word.capitalize() for word in name_part.replace('.', ' ').replace('_', ' ').split())
        else:
            display_name = user_email
            
        return jsonify({
            'email': user_email,
            'name': display_name,
            'avatar_url': None
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/update_user_profile', methods=['POST'])
def update_user_profile():
    """Update user profile information."""
    try:
        data = request.get_json() or {}
        user_email = data.get('email')
        display_name = data.get('name')
        
        if not user_email:
            return jsonify({'error': 'User email required'}), 400
            
        if not display_name:
            return jsonify({'error': 'Display name required'}), 400
        
        # Update the user record with display name
        users_table.update_item(
            Key={'user': user_email},
            UpdateExpression='SET display_name = :name',
            ExpressionAttributeValues={':name': display_name}
        )
        
        return jsonify({'status': 'success', 'message': 'Profile updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/signout', methods=['POST'])
def signout():
    """Sign out the current user."""
    try:
        data = request.get_json() or {}
        user_email = data.get('email')
        
        if not user_email:
            return jsonify({'error': 'User email required'}), 400
        
        # Stop the observer thread for this user
        if user_email in observer_threads:
            # We can't directly stop the thread, but we can remove it from tracking
            # The thread will eventually stop on its own
            observer_threads.pop(user_email, None)
            print(f"Removed observer thread tracking for {user_email}")
        
        return jsonify({'status': 'success', 'message': 'Signed out successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/test_debug')
def test_debug():
    """Test endpoint to verify debug output works."""
    print("DEBUG: test_debug endpoint called")
    print(f"DEBUG: get_prompt function exists: {callable(get_prompt)}")
    print(f"DEBUG: get_prompt() returns: {get_prompt()}")
    return jsonify({'status': 'debug test complete'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

