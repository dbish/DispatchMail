import smtplib
import aioimaplib
import mailparser
import asyncio
from inbox import Email
from email.message import EmailMessage


PORT = 993
HOST = 'imap.gmail.com' 
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587

async def retrieve_emails(query, user, password):
    imap_client = aioimaplib.IMAP4_SSL(host=HOST)
    await imap_client.wait_hello_from_server()

    await imap_client.login(user, password)
    await imap_client.select('INBOX')

    #imap_client = await initialize_imap_client(user, password)
    print("imap client retrieved")

    search_result = await imap_client.search(query)
    print("search result retrieved")
    emails = []
    
    if search_result.result == 'OK':
        email_ids = search_result.lines[0].split()
        if email_ids:
            
            # Fetch and parse each email
            for email_id in email_ids:
                try:
                    # Convert bytes to string if needed
                    if isinstance(email_id, bytes):
                        email_id = email_id.decode('utf-8')
                    
                    fetch_result = await imap_client.fetch(email_id, 'BODY.PEEK[]')
                    if fetch_result.result == 'OK':
                        email_data = fetch_result.lines[1]
                        
                        # Parse the email
                        parsed_email = mailparser.parse_from_bytes(email_data)
                        # Create Email object
                        email_obj = Email(
                            id=parsed_email.id or email_id,
                            subject=parsed_email.subject or '',
                            body=parsed_email.text_plain[0] if parsed_email.text_plain else '',
                            full_body=parsed_email.body,
                            html=parsed_email.text_html,
                            from_=parsed_email.from_,
                            to=parsed_email.to,
                            date=parsed_email.date
                        )
                        emails.append(email_obj)
                        
                except Exception as e:
                    print(f'Error processing email {email_id}: {e}')
                    continue
        else:
            print("No emails found matching the query")
    else:
        print(f"Search failed: {search_result.result}")
    
    print("logging out")
    try:
        await imap_client.logout()
    except (OSError, ConnectionResetError, asyncio.TimeoutError) as e:
        print(f"Note: Connection cleanup warning (harmless): {type(e).__name__}")
    except Exception as e:
        print(f"Warning: Unexpected error during logout: {e}")
    return emails

def send_email(email, draft_text, user, password):
    print(f"Sending email: {email.id} {draft_text}")
    from_data = email.from_
    reply_to_email = from_data[0][1]
    reply_subject = email.subject
    if not reply_subject.startswith('Re: '):
        reply_subject = f"Re: {reply_subject}"
    msg = EmailMessage()
    msg['From'] = user
    msg['To'] = reply_to_email
    msg['Subject'] = reply_subject
    msg['In-Reply-To'] = email.id
    msg['References'] = email.id
    msg.set_content(draft_text)
    
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        print(f"Email sent successfully from {user} to {reply_to_email}")
    except Exception as e:
        print(f"Error sending email: {e}")

    email.state = ['sent']
    email.drafted_response = draft_text
