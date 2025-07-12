from asyncio import run, wait_for
import mailparser
import aiohttp
import aioimaplib
from config_reader import HOST, USER, PASSWORD, AWS_REGION, DYNAMODB_TABLE
import json
from string import Template
from email_reply_parser import EmailReplyParser
import boto3

import smtplib
# Import the email modules we'll need
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# DynamoDB setup
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
email_table = dynamodb.Table(DYNAMODB_TABLE)

emails_to_process = []

# Track processed message IDs to avoid reprocessing
processed_message_ids = set()


def processUnread(to, user_info, body, subject, message_id, date=None):
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
        email_table.put_item(
            Item={
                'message_id': message_id or '',
                'subject': subject or '',
                'to': json.dumps(to),
                'from': json.dumps(user_info),
                'body': all_body,
                'date': date.isoformat() if date else ''
            }
        )
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
    imap_client = aioimaplib.IMAP4_SSL(host=host, timeout=30)
    await imap_client.wait_hello_from_server()

    await imap_client.login(user, password)
    await imap_client.select('INBOX')

    while True:
        response = await imap_client.search('(UNSEEN)')
        unread_uids = response.lines[0].split()
        unread_uids = [uid.decode() for uid in unread_uids]
        if len(unread_uids) > 0:
            #fetch any unread
            response = await imap_client.uid('fetch', ','.join(unread_uids), 'RFC822')
            
            # start is: 2 FETCH (UID 18 RFC822 {42}
            # middle is the actual email content
            # end is simply ")"
            # the last line is removed as it's only "success"-ish information
            # the iter + zip tricks is to iterate three by three
            iterator = iter(response.lines[:-1])
            for start, middle, _end in zip(iterator, iterator, iterator):
                try:
                    parsed_email = mailparser.parse_from_bytes(middle)
                    
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
                        parsed_email.to,
                        from_email,
                        parsed_email.text_plain,
                        parsed_email.subject,
                        parsed_email.message_id,
                        parsed_email.date
                    )
                    print(f"Total processed messages tracked: {len(processed_message_ids)}")
                except Exception as e:
                    print(f'Error processing individual email: {str(e)}')
                    print(f'Skipping this email and continuing with the next one')
                    continue
        idle_task = await imap_client.idle_start(timeout=60)
        await imap_client.wait_server_push()
        imap_client.idle_done()
        await wait_for(idle_task, timeout=5)

def loop_and_retry():
    try:
        run(imap_loop(HOST, USER, PASSWORD))
    except Exception as e:
        print('Exception : ' + str(e))
        loop_and_retry()

if __name__ == '__main__':
    loop_and_retry()
