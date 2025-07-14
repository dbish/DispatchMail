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
    AWS_REGION,
    DYNAMODB_TABLE,
    DYNAMODB_META_TABLE,
    DYNAMODB_USERS_TABLE,
    LOOKBACK_DAYS,
)
from datetime import datetime, timedelta
import json
from string import Template
from email_reply_parser import EmailReplyParser
import boto3
from dateutil import tz

import smtplib
# Import the email modules we'll need
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import filter_utils

# DynamoDB setup
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
email_table = dynamodb.Table(DYNAMODB_TABLE)
meta_table = dynamodb.Table(DYNAMODB_META_TABLE)
users_table = dynamodb.Table(DYNAMODB_USERS_TABLE)

emails_to_process = []

# Track processed message IDs to avoid reprocessing
processed_message_ids = set()


def get_last_processed_date(user):
    """Retrieve the last processed email timestamp for a user."""
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
            meta_table.put_item(Item={"user": user, "last_processed": dt_utc.isoformat()})
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


    # Store into DynamoDB
    try:
        # Convert email date to UTC before storing
        utc_date = None
        if date:
            if date.tzinfo is not None:
                utc_date = date.astimezone(tz.UTC)
            else:
                utc_date = date.replace(tzinfo=tz.UTC)
        
        email_table.put_item(
            Item={
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
        )
        if utc_date:
            update_last_processed_date(current_user, utc_date)
    except Exception as e:
        print(f'Error saving email to DynamoDB: {e}')

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
        
    except aioimaplib.IMAP4Error as e:
        print(f"IMAP Error during connection/login for {user}: {str(e)}")
        if "authentication failed" in str(e).lower():
            print("Authentication failed - check your app password!")
            print("Make sure:")
            print("1. 2FA is enabled on your Google account")
            print("2. You're using an App Password (not your regular password)")
            print("3. The app password is correct")
        raise
    except Exception as e:
        print(f"Unexpected error during connection/login for {user}: {str(e)}")
        raise

    while True:
        last_processed = get_last_processed_date(user)
        if last_processed:
            since_dt = last_processed
        else:
            since_dt = datetime.now(tz.UTC) - timedelta(days=LOOKBACK_DAYS)
        
        # Use the day before to ensure we catch all emails due to timezone issues
        search_dt = since_dt - timedelta(days=1)
        since_str = search_dt.strftime('%d-%b-%Y')
        print(f"Searching for emails since (UTC): {since_dt} -> searching from {since_str}")

        response = await imap_client.search(f'(SINCE {since_str})')
        search_uids = response.lines[0].split()
        search_uids = [uid.decode() for uid in search_uids]
        if len(search_uids) > 0:
            # fetch any emails since the desired date
            response = await imap_client.uid('fetch', ','.join(search_uids), 'RFC822')
            
            # start is: 2 FETCH (UID 18 RFC822 {42}
            # middle is the actual email content
            # end is simply ")"
            # the last line is removed as it's only "success"-ish information
            # the iter + zip tricks is to iterate three by three
            iterator = iter(response.lines[:-1])
            for start, middle, _end in zip(iterator, iterator, iterator):
                try:
                    parsed_email = mailparser.parse_from_bytes(middle)

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
                    allow = await asyncio.to_thread(filter_utils.should_store, parsed_email)
                    if not allow:
                        print("Email filtered by whitelist rules")
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
        except aioimaplib.IMAP4Error as e:
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
        except Exception as e:
            connection_failures += 1
            print(f'Exception for {user} (connection failure #{connection_failures}): {str(e)}')
            # Shorter wait for general exceptions
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
        response = users_table.scan()
        return response.get('Items', [])
    except Exception as e:
        print(f'Error fetching accounts: {e}')
        return []


async def main():
    await monitor_accounts()


if __name__ == '__main__':
    asyncio.run(main())
