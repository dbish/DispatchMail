from inbox import Inbox
from gmail import retrieve_emails, send_email
import asyncio
import os

USER = 'diamond@diamondbishop.email'
PASSWORD = 'kyue bahg icsu crjc'



inbox = Inbox()
inbox.user = USER
inbox.app_password = PASSWORD
inbox.retrieve_function = retrieve_emails
inbox.send_function = send_email

#inbox.whitelist.create_from_filter('diamondbishop@gmail.com')
#inbox.whitelist.create_subject_filter('test')

async def run_update():
    async for batch_result in inbox.update():
        print(f"Processing: {batch_result}")
        print(f"retrieved {len(batch_result['batch'])} emails")
        print(f"state: {batch_result['state']}")

asyncio.run(run_update())

latest = inbox.get_latest_email()
if latest:
    print(latest)
else:
    print("No emails found")
