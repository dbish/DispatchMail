import asyncio
from asyncio import wait_for
import mailparser
import aiohttp
import aioimaplib
import ai_processor
from config_reader import (
    HOST,
    USER,
    PASSWORD,
    DATABASE_PATH,
    LOOKBACK_DAYS,
)
from datetime import datetime, timedelta
import json
from string import Template
from email_reply_parser import EmailReplyParser
from database import db
from dateutil import tz

import smtplib
# Import the email modules we'll need
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import filter_utils

emails_to_process = []

# Track processed message IDs to avoid reprocessing
processed_message_ids = set()


def get_last_processed_date(user):
    """Retrieve the last processed email timestamp for a user."""
    try:
        metadata = db.get_metadata(user)
        if metadata and metadata.get("last_processed"):
            dt = datetime.fromisoformat(metadata["last_processed"])
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
    """Store the latest processed timestamp for a user."""
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
            db.put_metadata(user, {"last_processed": dt_utc.isoformat()})
    except Exception as e:
        print(f"Error updating last processed date: {e}")


def processUnread(current_user, to, user_info, body, subject, message_id, date=None):
    # Handle empty user_info (from_email) gracefully
    if not user_info or len(user_info) == 0:
        name = "Unknown Sender"
        print(f"Warning: Empty from_email for message, using default name: {name}")
    else:
        # Handle case where user_info[0] might not have a name
        if len(user_info[0]) > 0:
            name = user_info[0][0]
        else:
            name = "Unknown Sender"
            print(f"Warning: No name in from_email, using default name: {name}")
    
    # Handle empty body gracefully
    if not body or len(body) == 0:
        all_body = ""
        print("Warning: Empty email body")
    else:
        all_body = body[0]

    reply = EmailReplyParser.parse_reply(all_body)
    thread_history = all_body[len(reply)::]

    print(f'to: {to}')
    print(f'user_info: {user_info}')
    print(f'body: {body}')

    # Store into SQLite
    try:
        # Convert email date to UTC before storing
        utc_date = None
        if date:
            if date.tzinfo is not None:
                utc_date = date.astimezone(tz.UTC)
            else:
                utc_date = date.replace(tzinfo=tz.UTC)
        
        email_data = {
            'message_id': message_id or '',
            'subject': subject or '',
            'to': json.dumps(to),
            'from': json.dumps(user_info),
            'body': all_body,
            'date': utc_date.isoformat() if utc_date else '',
            'processed': False,
            'action': '',
            'draft': '',
            'account': current_user,
        }
        
        db.put_email(email_data)
        if utc_date:
            update_last_processed_date(current_user, utc_date)
    except Exception as e:
        print(f'Error saving email to database: {e}')

    emails_to_process.append({
        'to': to,
        'user_info': user_info,
        'body': body,
        'subject': subject,
        'message_id': message_id
    })


async def imap_loop(host, user, password) -> None:
    # Gmail requires port 993 for SSL connections
    port = 993 if 'gmail.com' in host else 993  # Default to 993 for most secure IMAP
    
    print(f"Connecting to {host}:{port} for user {user}")
    
    try:
        imap_client = aioimaplib.IMAP4_SSL(host=host, port=port, timeout=30)
        await imap_client.wait_hello_from_server()
        print(f"Successfully connected to {host}")
        
        # Try to login with better error handling
        print(f"Attempting to login as {user}")
        await imap_client.login(user, password)
        print(f"Successfully logged in as {user}")
        
        await imap_client.select('INBOX')
        print("Successfully selected INBOX")
        
    except Exception as e:
        print(f"IMAP Error during connection/login for {user}: {str(e)}")
        if "authentication failed" in str(e).lower():
            print("Authentication failed - check your app password!")
            print("Make sure:")
            print("1. 2FA is enabled on your Google account")
            print("2. You're using an App Password (not your regular password)")
            print("3. The app password is correct")
        raise

    # Get the last processed date for this user
    last_processed_date = get_last_processed_date(user)
    
    if last_processed_date:
        # Search for emails since the last processed date
        since_dt = last_processed_date
        since_str = since_dt.strftime('%d-%b-%Y')
        print(f"Searching for emails since {since_str}")
        search_criteria = f'SINCE "{since_str}"'
    else:
        # If no last processed date, look back a few days
        since_dt = datetime.now(tz.UTC) - timedelta(days=LOOKBACK_DAYS)
        since_str = since_dt.strftime('%d-%b-%Y')
        print(f"No previous processing date found, looking back {LOOKBACK_DAYS} days to {since_str}")
        search_criteria = f'SINCE "{since_str}"'
    
    # Start monitoring loop
    while True:
        try:
            # Search for unread emails
            await imap_client.search(search_criteria)
            
            # First, get all email IDs
            search_result = await imap_client.search('ALL')
            if search_result.result == 'OK':
                email_ids = search_result.lines[0].split()
                if email_ids:
                    print(f"Found {len(email_ids)} emails to process")
                    
                    # Process emails in batches of 3
                    for i in range(0, len(email_ids), 3):
                        batch = email_ids[i:i+3]
                        
                        # Fetch the emails
                        for email_id in batch:
                            try:
                                # Convert bytes to string if needed
                                if isinstance(email_id, bytes):
                                    email_id = email_id.decode('utf-8')
                                
                                fetch_result = await imap_client.fetch(email_id, '(RFC822)')
                                if fetch_result.result == 'OK':
                                    email_data = fetch_result.lines[1]
                                    
                                    try:
                                        parsed_email = mailparser.parse_from_bytes(email_data)

                                        # Filter out emails that are actually older than our target date
                                        if parsed_email.date and since_dt:
                                            # Ensure both dates are timezone-aware for comparison
                                            email_date = parsed_email.date
                                            if email_date.tzinfo is None:
                                                email_date = email_date.replace(tzinfo=tz.UTC)
                                            elif email_date.tzinfo != tz.UTC:
                                                email_date = email_date.astimezone(tz.UTC)
                                            
                                            if email_date <= since_dt:
                                                continue

                                        # Apply whitelist filtering
                                        is_whitelisted = await asyncio.to_thread(filter_utils.should_store, parsed_email, user)
                                        if is_whitelisted:
                                            print("Email is whitelisted - storing without AI processing")
                                            # Store whitelisted email directly without AI processing
                                            message_id = parsed_email.message_id
                                            if message_id and message_id not in processed_message_ids:
                                                processed_message_ids.add(message_id)
                                                
                                                # Store whitelisted email as already processed
                                                email_data = {
                                                    'message_id': message_id or '',
                                                    'subject': parsed_email.subject or '',
                                                    'to': json.dumps(parsed_email.to),
                                                    'from': json.dumps(parsed_email.from_),
                                                    'body': parsed_email.text_plain[0] if parsed_email.text_plain else '',
                                                    'date': email_date.isoformat() if email_date else '',
                                                    'processed': True,
                                                    'action': 'whitelisted',
                                                    'draft': '',
                                                    'account': user,
                                                }
                                                db.put_email(email_data)
                                            continue

                                        # Check if we've already processed this message
                                        message_id = parsed_email.message_id
                                        if message_id in processed_message_ids:
                                            print(f"Skipping already processed message: {message_id}")
                                            continue
                                        
                                        # Add to processed set (only if message_id is not None/empty)
                                        if message_id:
                                            processed_message_ids.add(message_id)
                                        else:
                                            print("Warning: Message has no ID, processing anyway")
                                        
                                        print(parsed_email.to)
                                        print(parsed_email.subject)
                                        from_email = parsed_email.from_
                                        if len(parsed_email.reply_to) > 0:
                                            from_email = parsed_email.reply_to
                                        print('from email::::')
                                        print(from_email)
                                        print(parsed_email.text_plain)
                                        print('message id::::')
                                        print(parsed_email.message_id)
                                        processUnread(
                                            user,
                                            parsed_email.to,
                                            from_email,
                                            parsed_email.text_plain,
                                            parsed_email.subject,
                                            parsed_email.message_id,
                                            parsed_email.date
                                        )
                                        # Enable automatic AI processing for new emails
                                        try:
                                            asyncio.create_task(ai_processor.handle_email(user, parsed_email))
                                            print(f"Queued AI processing for email: {parsed_email.message_id}")
                                        except Exception as e:
                                            print(f"Error queuing AI processing for email {parsed_email.message_id}: {e}")
                                        print(f"Total processed messages tracked: {len(processed_message_ids)}")
                                    except Exception as e:
                                        print(f'Error processing individual email: {str(e)}')
                                        print(f'Skipping this email and continuing with the next one')
                                        continue
                            except Exception as e:
                                print(f'Error fetching email {email_id}: {str(e)}')
                                continue
                                
        except Exception as e:
            print(f'Error in email processing loop: {str(e)}')
            
        try:
            idle_task = await imap_client.idle_start(timeout=30)  # Reduced from 60 to 30 seconds
            await imap_client.wait_server_push()
            imap_client.idle_done()
            await wait_for(idle_task, timeout=3)  # Reduced from 5 to 3 seconds
        except asyncio.TimeoutError:
            print(f"IDLE timeout for {user}, continuing...")
            try:
                imap_client.idle_done()
            except:
                pass  # Ignore errors when stopping IDLE
        except Exception as e:
            print(f"IDLE error for {user}: {e}")
            # Break out of the loop to reconnect
            break

async def loop_and_retry(host, user, password):
    consecutive_auth_failures = 0
    max_auth_failures = 3
    connection_failures = 0
    
    while True:
        try:
            print(f"Starting IMAP loop for {user} (attempt #{connection_failures + 1})")
            await imap_loop(host, user, password)
            # Reset failure count on successful connection
            consecutive_auth_failures = 0
            connection_failures = 0
        except Exception as e:
            error_str = str(e).lower()
            if "authentication failed" in error_str or "login failed" in error_str:
                consecutive_auth_failures += 1
                print(f'Authentication failed for {user} (attempt {consecutive_auth_failures}/{max_auth_failures}): {str(e)}')
                
                if consecutive_auth_failures >= max_auth_failures:
                    print(f'Max authentication failures reached for {user}. Stopping retries.')
                    print('Please check your Gmail app password and configuration.')
                    return
                
                # Wait longer for auth failures to avoid getting blocked
                await asyncio.sleep(30)
            else:
                connection_failures += 1
                print(f'IMAP Error for {user} (connection failure #{connection_failures}): {str(e)}')
                # Shorter wait for connection issues
                await asyncio.sleep(min(connection_failures * 2, 15))  # Exponential backoff, max 15 seconds


async def monitor_accounts():
    active_tasks = {}
    while True:
        accounts = await asyncio.to_thread(fetch_accounts)
        for account in accounts:
            acct_user = account.get('user')
            if not acct_user:
                continue
            if acct_user not in active_tasks:
                host = account.get('host', HOST)
                password = account.get('password')
                if not password:
                    continue
                task = asyncio.create_task(loop_and_retry(host, acct_user, password))
                active_tasks[acct_user] = task
                print(f'Started monitoring {acct_user}')
        await asyncio.sleep(60)


def fetch_accounts():
    try:
        return db.get_users()
    except Exception as e:
        print(f'Error fetching accounts: {e}')
        return []


if __name__ == '__main__':
    asyncio.run(monitor_accounts())
