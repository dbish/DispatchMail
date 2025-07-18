from datetime import datetime, timedelta, timezone
import time
from agent import Agent
import asyncio
import json
import uuid

class Email:
    def __init__(self, id, subject, body, full_body, html, from_, to, date):
        self.id = id
        self.subject = subject
        self.body = body
        self.full_body = full_body
        self.html = html
        self.from_ = from_
        self.to = to
        self.date = date
        self.processed = False
        self.state = [] #list of states to show
        self.drafted_response = None
        self.sent_response = None
        self.sent_date = None
        self.sent_to = None
        self.sent_subject = None
        self.sent_body = None
        self.action = 'drafted' #testing
        
    async def update(self):
        pass

    def __str__(self):
        #create a nice string representation of the email
        #make it look like a gmail email in a terminal format
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
        #update the whitelist from a json object
        self.filters = {}
        rules = json_data['rules']
        if rules:
            for rule in rules:
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
        print('Updating')
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
        print(f"Found {num_new_emails} new emails")
        return num_new_emails

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