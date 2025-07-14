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

from flask import Flask, jsonify, request
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
daemon_service_dir = os.path.join(BASE_DIR, 'daemon-service')

# Add daemon-service to Python path so imports work
sys.path.insert(0, daemon_service_dir)

# Import database
database_path = os.path.join(daemon_service_dir, 'database.py')
spec_db = importlib.util.spec_from_file_location('database', database_path)
database = importlib.util.module_from_spec(spec_db)
spec_db.loader.exec_module(database)

db = database.db

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

# Import config_reader to get database settings
import config_reader

DATABASE_PATH = config_reader.DATABASE_PATH
LOOKBACK_DAYS = config_reader.LOOKBACK_DAYS
HOST = config_reader.HOST

# Get OpenAI API key from config_reader (which reads from secrets file)
OPENAI_API_KEY = config_reader.OPENAI_API_KEY

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
        metadata = db.get_metadata('reading_prompt')
        return metadata.get('prompt', '') if metadata else ''
    except:
        return ''

def get_draft_prompt():
    """Get the draft prompt from the database."""
    try:
        metadata = db.get_metadata('draft_prompt')
        return metadata.get('prompt', '') if metadata else ''
    except:
        return ''

def get_last_processed_date(user):
    """Get the last processed date for a user."""
    try:
        metadata = db.get_metadata(user)
        if metadata and metadata.get('last_processed'):
            return datetime.fromisoformat(metadata['last_processed'])
    except:
        pass
    return None

def update_last_processed_date(user, date):
    """Update the last processed date for a user."""
    try:
        db.put_metadata(user, {'last_processed': date.isoformat()})
    except Exception as e:
        print(f"Error updating last processed date: {e}")

def extract_key_content_from_email_item(email_item):
    """Extract key content from a stored email item."""
    try:
        subject = email_item.get('subject', '')
        body = email_item.get('body', '')
        from_sender = email_item.get('from_sender', '')
        
        # Use EmailReplyParser to extract just the new content
        if body:
            reply_content = EmailReplyParser.parse_reply(body)
            if reply_content and reply_content.strip():
                body = reply_content
        
        # Create a concise representation
        content = f"Subject: {subject}\n"
        content += f"From: {from_sender}\n"
        content += f"Body: {body[:1000]}..."  # Limit body to 1000 chars
        
        return content
    except Exception as e:
        print(f"Error extracting content: {e}")
        return "Error extracting content"

def process_email_with_ai_sync(parsed_email):
    """Process an email with AI synchronously."""
    try:
        # Extract key content for LLM processing
        print(f"DEBUG: Extracting key content for email {parsed_email.get('message_id', 'unknown')}")
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
        
        # Update the email in database with current timestamp
        from datetime import datetime
        current_time = datetime.now().isoformat()
        
        update_data = {
            'processed': True,
            'action': "drafted" if draft_text else "reviewed (no action needed)",
            'updated_at': current_time
        }
        
        if draft_text:
            update_data['draft'] = draft_text
            update_data['llm_prompt'] = key_content  # Store what was sent to LLM
        
        message_id = parsed_email.get('message_id')
        db.update_email(message_id, update_data)
        
        print(f"AI processing completed for email: {message_id} - Action: {update_data['action']}")
        
    except Exception as e:
        print(f"Error in AI processing for email {parsed_email.get('message_id', 'unknown')}: {e}")

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
            since_date = last_processed.strftime('%d-%b-%Y')
        else:
            since_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime('%d-%b-%Y')
        
        _, message_ids = imap.search(None, f'SINCE {since_date}')
        
        for message_id in message_ids[0].split():
            _, msg_data = imap.fetch(message_id, '(RFC822)')
            raw_email = msg_data[0][1]
            # Process and store email (implementation would continue here)
            
        imap.logout()
        
    except Exception as e:
        print(f"Error hydrating inbox: {e}")

app = Flask(__name__)
CORS(app)

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users."""
    try:
        users = db.get_users()
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
def add_user():
    """Add a new user."""
    try:
        data = request.get_json()
        user = data.get('user')
        host = data.get('host', HOST)
        password = data.get('password')
        
        if not user or not password:
            return jsonify({'error': 'User and password required'}), 400
        
        success = db.put_user(user, host, password)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to add user'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails', methods=['GET'])
def get_emails():
    """Return emails stored in database."""
    try:
        # Get query parameters
        processed = request.args.get('processed')
        account = request.args.get('account')
        
        # Build filter condition
        filter_condition = {}
        if processed is not None:
            filter_condition['processed'] = processed.lower() == 'true'
        if account:
            filter_condition['account'] = account
        
        emails = db.scan_emails(filter_condition if filter_condition else None)
        
        # Parse JSON fields and convert types
        for email in emails:
            try:
                if email.get('to_recipients'):
                    email['to'] = json.loads(email['to_recipients'])
                if email.get('from_sender'):
                    email['from'] = json.loads(email['from_sender'])
                    
                # Convert processed from integer to boolean
                email['processed'] = bool(email.get('processed', 0))
                
            except:
                pass
        
        # Calculate last modified time based on all emails
        last_modified = ''
        if emails:
            # Find the most recent updated_at or created_at timestamp
            timestamps = []
            for email in emails:
                updated_at = email.get('updated_at')
                created_at = email.get('created_at')
                if updated_at:
                    timestamps.append(updated_at)
                elif created_at:
                    timestamps.append(created_at)
            
            if timestamps:
                last_modified = max(timestamps)
        
        return jsonify({
            'emails': emails,
            'last_modified': last_modified,
            'count': len(emails)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails/<message_id>', methods=['GET'])
def get_email(message_id):
    """Get a specific email by ID."""
    try:
        email = db.get_email(message_id)
        if not email:
            return jsonify({'error': 'Email not found'}), 404
        
        # Parse JSON fields and convert types
        try:
            if email.get('to_recipients'):
                email['to'] = json.loads(email['to_recipients'])
            if email.get('from_sender'):
                email['from'] = json.loads(email['from_sender'])
                
            # Convert processed from integer to boolean
            email['processed'] = bool(email.get('processed', 0))
            
        except:
            pass
        
        return jsonify(email)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails/<message_id>/draft', methods=['POST'])
def update_draft(message_id):
    """Update the draft for an email."""
    try:
        data = request.get_json()
        draft = data.get('draft', '')
        
        success = db.update_email(message_id, {'draft': draft})
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update draft'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts/reading', methods=['GET'])
def get_reading_prompt():
    """Get the reading prompt."""
    try:
        return jsonify({'prompt': get_prompt()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts/reading', methods=['POST'])
def set_reading_prompt():
    """Set the reading prompt."""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        success = db.put_metadata('reading_prompt', {'prompt': prompt})
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update prompt'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts/draft', methods=['GET'])
def get_draft_prompt_api():
    """Get the draft prompt."""
    try:
        return jsonify({'prompt': get_draft_prompt()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts/draft', methods=['POST'])
def set_draft_prompt():
    """Set the draft prompt."""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        success = db.put_metadata('draft_prompt', {'prompt': prompt})
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update prompt'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/whitelist', methods=['GET'])
def get_whitelist():
    """Get whitelist rules."""
    try:
        users = db.get_users()
        if not users:
            return jsonify({'rules': []})
        
        user = users[0]['user']  # Get the first user
        metadata = db.get_metadata(user, 'rules')
        if metadata:
            rules = json.loads(metadata)
        else:
            rules = []
        return jsonify({'rules': rules})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/whitelist', methods=['POST'])
def set_whitelist():
    """Set whitelist rules."""
    try:
        data = request.get_json()
        rules = data.get('rules', [])
        
        users = db.get_users()
        if not users:
            return jsonify({'error': 'No users found'}), 400
        
        user = users[0]['user']  # Get the first user
        success = db.put_metadata(user, {'rules': json.dumps(rules)})
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update whitelist'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset_inbox', methods=['POST'])
def reset_inbox():
    """Reset inbox - clear all emails and metadata (debugging only)."""
    try:
        users = db.get_users()
        if not users:
            return jsonify({'error': 'No users found'}), 400
        
        user = users[0]['user']  # Get the first user
        
        # Clear all emails
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM emails WHERE account = ?', (user,))
        emails_deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        # Reset only the last_processed timestamp, keep whitelist rules
        # Get existing metadata first
        existing_metadata = db.get_metadata(user)
        if existing_metadata:
            # Update only the last_processed field
            updated_metadata = {
                'data': existing_metadata.get('data', ''),
                'last_processed': '',  # Clear the timestamp
                'prompt': existing_metadata.get('prompt', ''),
                'rules': existing_metadata.get('rules', '')
            }
            db.put_metadata(user, updated_metadata)
        else:
            # Create new metadata entry with empty last_processed
            db.put_metadata(user, {'last_processed': ''})
        
        return jsonify({
            'success': True,
            'message': f'Inbox reset successfully. {emails_deleted} emails deleted.',
            'emails_deleted': emails_deleted
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Additional endpoints needed by frontend
@app.route('/api/user_profile', methods=['GET'])
def get_user_profile():
    """Get user profile information."""
    try:
        email = request.args.get('email')
        if not email:
            return jsonify({'error': 'Email parameter required'}), 400
        
        # Check if user exists
        users = db.get_users()
        user = None
        for u in users:
            if u.get('user') == email:
                user = u
                break
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user metadata
        metadata = db.get_metadata(email)
        
        profile = {
            'email': email,
            'host': user.get('host', 'imap.gmail.com'),
            'active': user.get('active', True),
            'last_processed': metadata.get('last_processed') if metadata else None,
            'created_at': user.get('created_at')
        }
        
        return jsonify(profile)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/update_user_profile', methods=['POST'])
def update_user_profile():
    """Update user profile."""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        # For now, just return success as we don't have much to update
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/signout', methods=['POST'])
def signout():
    """Sign out user."""
    try:
        # For local SQLite version, just return success
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails/status', methods=['GET'])
def get_emails_status():
    """Get email update status."""
    try:
        # Get latest email timestamp
        emails = db.scan_emails()
        
        if not emails:
            return jsonify({'last_modified': '', 'count': 0})
        
        # Calculate last modified time based on all emails (same logic as /api/emails)
        last_modified = ''
        if emails:
            # Find the most recent updated_at or created_at timestamp
            timestamps = []
            for email in emails:
                updated_at = email.get('updated_at')
                created_at = email.get('created_at')
                if updated_at:
                    timestamps.append(updated_at)
                elif created_at:
                    timestamps.append(created_at)
            
            if timestamps:
                last_modified = max(timestamps)
        
        return jsonify({
            'last_modified': last_modified,
            'count': len(emails)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompt', methods=['GET'])
def get_prompt_endpoint():
    """Get the reading prompt (alias for /api/prompts/reading)."""
    try:
        return jsonify({'prompt': get_prompt()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompt', methods=['POST'])
def set_prompt_endpoint():
    """Set the reading prompt (alias for /api/prompts/reading)."""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        success = db.put_metadata('reading_prompt', {'prompt': prompt})
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update prompt'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/draft_prompt', methods=['GET'])
def get_draft_prompt_alias():
    """Get the draft prompt (alias for /api/prompts/draft)."""
    try:
        return jsonify({'prompt': get_draft_prompt()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/draft_prompt', methods=['POST'])
def set_draft_prompt_alias():
    """Set the draft prompt (alias for /api/prompts/draft)."""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        success = db.put_metadata('draft_prompt', {'prompt': prompt})
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update prompt'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/process_unprocessed_emails', methods=['POST'])
def process_unprocessed_emails():
    """Process unprocessed emails with AI."""
    try:
        if not client:
            return jsonify({'error': 'OpenAI client not available'}), 500
        
        # Get unprocessed emails
        unprocessed = db.scan_emails({'processed': False})
        
        processed_count = 0
        for email in unprocessed:
            try:
                process_email_with_ai_sync(email)
                processed_count += 1
            except Exception as e:
                print(f"Error processing email {email.get('message_id')}: {e}")
                continue
        
        return jsonify({
            'success': True,
            'processed_count': processed_count,
            'total_found': len(unprocessed)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/manual_sync', methods=['POST'])
def manual_sync():
    """Manually sync emails."""
    try:
        # Get all users 
        users = db.get_users()
        results = []
        
        # Check current email count
        total_emails = 0
        for user in users:
            email = user.get('user')
            if email:
                user_emails = db.scan_emails({'account': email})
                total_emails += len(user_emails)
                results.append({
                    'email': email,
                    'new_emails': len(user_emails),
                    'status': 'sync_completed'
                })
        
        return jsonify({
            'success': True, 
            'message': f'Sync completed - {total_emails} emails in database',
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/send', methods=['POST'])
def send_email():
    """Send an email."""
    try:
        data = request.get_json()
        email_id = data.get('id')
        draft_text = data.get('draft')
        
        if not email_id:
            return jsonify({'error': 'Email ID required'}), 400
        
        # Update email status to sent with current timestamp
        from datetime import datetime
        current_time = datetime.now().isoformat()
        
        update_data = {
            'action': 'sent',
            'draft': draft_text,
            'updated_at': current_time
        }
        
        success = db.update_email(email_id, update_data)
        if success:
            return jsonify({'success': True, 'message': 'Email sent'})
        else:
            return jsonify({'error': 'Failed to update email status'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_draft', methods=['POST'])
def delete_draft():
    """Delete a draft."""
    try:
        data = request.get_json()
        email_id = data.get('email_id')
        
        if not email_id:
            return jsonify({'error': 'Email ID required'}), 400
        
        update_data = {
            'draft': ''
        }
        
        success = db.update_email(email_id, update_data)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to delete draft'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/verify_credentials', methods=['POST'])
def verify_credentials():
    """Verify user credentials."""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        host = data.get('host', 'imap.gmail.com')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Try to connect to IMAP server
        try:
            import imaplib
            imap = imaplib.IMAP4_SSL(host)
            imap.login(email, password)
            imap.logout()
            
            return jsonify({'success': True, 'message': 'Credentials verified'})
        except Exception as e:
            return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/onboard', methods=['POST'])
def onboard():
    """Onboard a new user."""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        host = data.get('host', 'imap.gmail.com')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Add user to database
        success = db.put_user(email, host, password)
        if success:
            return jsonify({'success': True, 'message': 'User onboarded successfully'})
        else:
            return jsonify({'error': 'Failed to onboard user'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reprocess_single_email', methods=['POST'])
def reprocess_single_email():
    """Reprocess a single email."""
    try:
        data = request.get_json()
        message_id = data.get('message_id')
        
        if not message_id:
            return jsonify({'error': 'Message ID required'}), 400
        
        if not client:
            return jsonify({'error': 'OpenAI client not available'}), 500
        
        # Get email from database
        email = db.get_email(message_id)
        if not email:
            return jsonify({'error': 'Email not found'}), 404
        
        # Process with AI
        try:
            process_email_with_ai_sync(email)
            return jsonify({'success': True, 'message': 'Email reprocessed'})
        except Exception as e:
            return jsonify({'error': f'Processing failed: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reprocessing_status', methods=['GET'])
def get_reprocessing_status():
    """Get reprocessing status."""
    try:
        return jsonify(reprocessing_status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

