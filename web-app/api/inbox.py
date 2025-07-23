from datetime import datetime, timedelta, timezone
import time
from agent import Agent
import asyncio
import json
import uuid
import asyncio

class Email:
    def __init__(self, id, subject, body, full_body='', html='', from_='', to='', date='', processed=False, state=[], drafted_response=None):
        self.id = id
        self.subject = subject
        self.body = body
        self.full_body = full_body
        self.html = html
        self.from_ = from_
        self.to = to
        self.date = date
        self.processed = processed
        self.state = state #list of states to show
        self.drafted_response = drafted_response
        self.sent_response = None
        self.sent_date = None
        self.sent_to = None
        self.sent_subject = None
        self.sent_body = None
        self.action = 'drafted' #testing
        
    async def update(self):
        pass

    def __str__(self):
        email_str = f'''
        From: {self.from_}
        To: {self.to}
        Subject: {self.subject}
        Date: {self.date}
        Body: {self.body}
        HTML: {self.html}
        Processed: {self.processed}
        State: {self.state}
        Drafted Response: {self.drafted_response}
        Sent Response: {self.sent_response}
        Sent Date: {self.sent_date}
        '''
        return email_str

    #jsonify the email
    def to_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "body": self.body,
            "html": self.html,
            "full_body": self.full_body,
            "from": self.from_,
            "to": self.to,
            "date": self.date,
            "processed": self.processed,
            "state": self.state,
            "drafted_response": self.drafted_response,
        }

    def to_db_dict(self):
        return {
            "message_id": self.id,
            "subject": self.subject,
            "body": self.body,
            "full_body": self.full_body or '',
            "html": json.dumps(self.html) or '',
            "from_": json.dumps(self.from_) or '',
            "to_": json.dumps(self.to) or '',
            "date": self.date or '',
            "processed": self.processed,
            "state": json.dumps(self.state),
            "drafted_response": self.drafted_response or '',
            "sent_response": self.sent_response or '',
            "sent_date": self.sent_date or '',
            "sent_to": self.sent_to or '',
            "sent_subject": self.sent_subject or '',
            "sent_body": self.sent_body or '',
        }

class FilterList:
    def __init__(self):
        self.filters = {}
    
    def add_filter(self, filter):
        print(f"Adding filter {filter.uid}")
        print(type(filter))
        self.filters[filter.uid] = filter
    
    def remove_filter(self, filter_uid):
        del self.filters[filter_uid]

    async def filter(self, email):
        tasks = []
        if len(self.filters) == 0:
            return True
        for filter in self.filters.values():
            tasks.append(filter.matches(email))
        results = await asyncio.gather(*tasks)
        return any(results)
    
    def update_from_json(self, json_data):
        print('updating whitelist from json')
        #update the whitelist from a json object
        self.filters = {}
        #json_data is a string, so we need to load it
        if isinstance(json_data, str):
            rules = json.loads(json_data)['rules']
        else:
            rules = json_data['rules']
        print(rules)
        if rules:
            for rule in rules:
                #trim whitespace from any values
                rule['value'] = rule['value'].strip()
                if rule['type'] == 'email':
                    self.create_from_filter(rule['value'])
                elif rule['type'] == 'subject':
                    self.create_subject_filter(rule['value'])
                elif rule['type'] == 'classification':
                    self.create_ai_filter(rule['value'])
        print(f"Updating whitelist from json: {json_data}")


    def create_from_filter(self, from_filter):
        async def filter_func(email):
            for from_ in email.from_:
                #from is a tupple of (name, email)
                if from_[1] == from_filter:
                    return True
            return False
        filter = Filter(filter_func, 'email', from_filter)
        print(filter_func)
        print(f"Created filter from {from_filter}")
        print(filter.uid)
        self.add_filter(filter)

    def create_subject_filter(self, subject_filter):
        async def filter_func(email):
            return subject_filter.lower() in email.subject.lower()
        filter = Filter(filter_func, 'subject', subject_filter)
        self.add_filter(filter)

    def create_ai_filter(self, prompt):
        #create a filter that uses the ai to filter the email
        #the filter should be a function that takes an email and returns a boolean
        async def filter_func(email):
            instructions = prompt
            filter_template = """
                You are a helpful assistant that can help with email. 
                You are given an email and instructions to determine if the email should be whitelist (True) or filtered out (False).
                The email is a string.
                The instructions are a string.
                The output should be a boolean.
                The email is:
                $email
                The instructions are:
                $instructions
            """
            filter_prompt = filter_template.format(email=email, instructions=instructions)
            response = await self.agent.get_openai_response(filter_prompt)
            #make the response a boolean
            if response.lower() == "true":
                return True
            else:
                return False
        filter = Filter(filter_func, 'classification', prompt)
        self.add_filter(filter)

    def to_json(self):
        return {
            "rules": [
                filter.to_json()
                for filter in self.filters.values()
            ]
        }
    
class Filter:
    def __init__(self, filter_func, filter_type, text_value=None):
        #create uid for the filter
        self.uid = str(uuid.uuid4())
        self.filter_func = filter_func
        self.type = filter_type
        self.text_value = text_value

    async def matches(self, email):
        return await self.filter_func(email)

    def to_json(self):
        match self.type:
            case 'email':
                return {
                    "type": "email",
                    "value": self.text_value
                }
            case 'subject':
                return {
                    "type": "subject",
                    "value": self.text_value
                }
            case 'classification':
                return {
                    "type": "classification",
                    "value": self.text_value
                }
            case _:
                raise ValueError(f"Invalid filter type: {self.type}")
    

class Inbox:

    class State:
        UNINITIALIZED = 'uninitialized'
        HYDRATING = 'hydrating'
        HYDRATED = 'hydrated'
        UPDATING = 'updating'
        UPDATED = 'updated'
        PROCESSING = 'processing'
        DONE = 'done'

    def __init__(self):
        self.LOOKBACK_DAYS = 1
        self.BATCH_SIZE = 5
        #key is the message id, value is the email object
        self.emails = {}
        self.agent = None
        self.whitelist = FilterList()
        self.unprocessed_message_ids = []
        self.retrieve_function = None
        self.send_function = None
        self.last_retrieved_date = None
        self.user = None
        self.app_password = None
        self.agent = Agent("openai")
        self.state = self.State.UNINITIALIZED
        self.db = None

    def update_state(self, new_state):
        print(f"Updating state from {self.state} to {new_state}")
        if new_state == self.State.HYDRATING:
            if self.state == self.State.UNINITIALIZED:
                self.hydrate()
        elif new_state == self.State.HYDRATED:
            self.state = self.State.HYDRATED
        elif new_state == self.State.UPDATING:
            if self.state != self.State.UPDATING and self.state != self.State.HYDRATING and self.state != self.State.UNINITIALIZED:
                asyncio.run(self.update())
            else:
                print('already updating')
        elif new_state == self.State.UPDATED:
            self.state = self.State.UPDATED
        elif new_state == self.State.PROCESSING:
            self.state = self.State.PROCESSING
        elif new_state == self.State.DONE:
            self.state = self.State.DONE
    

    def hydrate(self):
        print('hydrating inbox')
        #in hydrating state, we load all emails from the db
        #this is a reset of the local inbox, pulling from save state
        self.state = self.State.HYDRATING
        self.emails = {}
        self.unprocessed_message_ids = []
        self.last_retrieved_date = None
        print(f"Scanning emails for {self.user}")
        results = self.db.scan_emails({'account': self.user})
        print(f"Found {len(results)} emails")
        for email in results:
            try:
                self.emails[email['message_id']] = Email(
                    id=email['message_id'],
                    subject=email['subject'],
                    body=email['body'],
                    full_body=email['full_body'],
                    html=json.loads(email['html']),
                    from_=json.loads(email['from_']),
                    to=json.loads(email['to_']),
                    date=email['date'],
                    processed=email['processed'],
                    state=json.loads(email['state']),
                    drafted_response=email['drafted_response'],
                    )
                if not email['processed']:
                    self.unprocessed_message_ids.append(email['message_id'])
            except Exception as e:
                print(f"Error adding email to inbox: {e}")
                print(email)
        self.update_state(self.State.HYDRATED)

    def update_writing_prompt(self, prompt):
        self.agent.response_prompt = prompt
    
    def update_instructions(self, instructions):
        self.agent.instructions = instructions

    async def reretrieve_all(self):
        self.last_retrieved_date = None
        self.emails = {}
        self.unprocessed_message_ids = []
        await self.update()

    async def update(self):
        print('Updating update')
        self.state = self.State.UPDATING
        #get new emails (get inputs/changes)
        if self.retrieve_function is None:
            raise ValueError("retrieve_function is not set")

        if self.last_retrieved_date is None:
            since_dt = datetime.now() - timedelta(days=self.LOOKBACK_DAYS)
        else:
            since_dt = self.last_retrieved_date
        since_str = since_dt.strftime('%d-%b-%Y')
        query = f'SINCE "{since_str}"'
        print(f"Retrieving emails since {since_str}")
        new_emails = await self.retrieve_function(query, self.user, self.app_password)
        num_new_emails = 0
        for email in new_emails:
            print(self.whitelist)
            if await self.whitelist.filter(email): 
                if email.id not in self.emails:
                    self.emails[email.id] = email
                    self.unprocessed_message_ids.append(email.id)
                    num_new_emails += 1
        # Only update last_retrieved_date if we have emails
        if self.emails:
            self.last_retrieved_date = self.get_latest_email().date
        self.save_emails()
        self.update_state(self.State.UPDATED)
        return num_new_emails

    def save_emails(self):
        emails_to_put = [email.to_db_dict() for email in self.emails.values()]
        if len(emails_to_put) > 0:
            self.db.bulk_put_emails(emails_to_put, self.user)

    def save_whitelist(self):
        whitelist_to_put = self.whitelist.to_json()
        whitelist_to_put = json.dumps(whitelist_to_put)
        self.db.put_metadata(self.user, {'rules': whitelist_to_put})

    def clear_all_processed(self):
        #reprocess all emails
        for email_id in self.emails:
            email = self.emails[email_id]
            email.processed = False
            email.state = []
            email.drafted_response = None
        self.unprocessed_message_ids = list(self.emails.keys())

    async def continue_processing(self):
        #create the next batch of emails to process
        if len(self.unprocessed_message_ids) == 0:
            return {"batch": [], "state": "done"}
        batch = self.unprocessed_message_ids[:self.BATCH_SIZE]
        await self.process_batch(batch)
        self.unprocessed_message_ids = self.unprocessed_message_ids[self.BATCH_SIZE:]
        email_data = []
        for email_id in batch:
            email = self.emails[email_id]
            email_data.append(email.to_dict())
        return {"batch": email_data, "state": "processed"}

    def get_latest_email(self):
        #get the latest email
        if not self.emails:
            return None
        return max(self.emails.values(), key=lambda x: x.date)

    def send(self, email_id, draft_text):
        email = self.emails[email_id]
        self.send_function(email, draft_text, self.user, self.app_password)
        email.sent_response = draft_text
        email.sent_date = datetime.now()
        email.sent_to = email.to
        email.sent_subject = email.subject
        email.sent_body = email.body

    async def process_batch(self, batch):
        #process the batch of emails
        #create a list of tasks and run them in parallel
        tasks = []
        for email_id in batch:
            email = self.emails[email_id]
            tasks.append(self.agent.process_email(email))
        await asyncio.gather(*tasks)
        print('saving emails')
        self.save_emails()
        print('emails saved')

    def bulk_load_emails(self, emails):
        #bulk load emails into the inbox
        for email in emails:
            self.emails[email['message_id']] = Email(
                id=email['message_id'],
                subject=email['subject'] or '',
                body=email['body'] or '',
                full_body=email['full_body'] or '',
                html=email['html'] or '',
                from_=email['from_sender'] or '',
                to=email['to_recipients'] or '',
                date=email['date'] or '',
                processed=email['processed'] or False,
                state=email['action'] or [],
                drafted_response=email['draft'] or None,
                llm_prompt=email['llm_prompt'] or '',
                processing=email['processing'] or False
            )