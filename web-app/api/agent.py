from openai import OpenAI
import config_reader

OPENAI_API_KEY = config_reader.OPENAI_API_KEY

import asyncio
import json
from string import Template
PROMPT_TEMPLATE = Template("""
You are a helpful assistant that can help with email.
You are given an email, instructions, and a set of tools to use to act 
on the email where applicable.

INSTRUCTIONS:
$instructions

EMAIL:
$email

TOOL USAGE INSTRUCTIONS:
- If the email is a marketing email or spam, respond with NO ACTION.
- If the email is not asking for a response, respond with NO ACTION.
- If the email is asking for a response, draft a response and use the draft_response tool to draft a response.
- When drafting a response follow the following principles:
    $response_prompt
- When drafting a response do not include placeholders, this includes the user's name, the company's name, or any other placeholder.
- When drafting a response do not include a subject line, this is just the body of the email.

Choose the appropriate tool to use to act on the email or respond with NO ACTION.
""")

DEFAULT_INSTRUCTIONS = """
Create a draft response to any email that is specifically asking for a response and is not a marketing email or spam.
"""

DEFAULT_RESPONSE_PROMPT = """
Write a concise but friendly response.
"""

DEFAULT_TOOLS = [
    {
      "type": "function",
      "name": "draft_response",
      "description": "Draft a response to the email",
      "parameters": {
        "type": "object",
        "properties": {
          "draft_email_body": {
            "type": "string",
            "description": "The body of the draft response to the email"
          }
        },
        "additionalProperties": False,
        "required": [
          "draft_email_body"
        ]
      },
      "strict": True
    }, 
    {
      "type": "function",
      "name": "add_tags",
      "description": "Add tags to the email",
      "parameters": {
        "type": "object",
        "properties": {
          "tags": {
            "type": "array",
            "description": "The tags to add to the email",
            "items": {
                "type": "string"
            }
          }
        },
        "additionalProperties": False,
        "required": [
          "tags"
        ]
      },
      "strict": True
    },
    {
      "type": "function",
      "name": "archive_email",
      "description": "Archive the email",
      "parameters": {
        "type": "object",
        "properties": {
          "archive": {
            "type": "boolean",
            "description": "Whether to archive the email"
          }
        },
        "additionalProperties": False,
        "required": [
          "archive"
        ]
      },
      "strict": True    
    }
  ]

class Agent:
    def __init__(self, client_type):
        if client_type == "openai":
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        else:
            raise ValueError(f"Invalid client type: {client_type}")
        
        self.instructions = DEFAULT_INSTRUCTIONS
        self.response_prompt = DEFAULT_RESPONSE_PROMPT

    async def process_email(self, email):
        #get the email content
        email_content = email.body
        prompt = PROMPT_TEMPLATE.substitute(instructions=self.instructions, email=email_content, response_prompt=self.response_prompt)

        response = await self.get_openai_response(prompt)
        email.processed = True
        if response:
            for action in response["tool_calls"]:
                if action["name"] == "draft_response":
                    email.state.append('drafted_response')
                    email.drafted_response = action["arguments"]["draft_email_body"]
                elif action["name"] == "add_tags":
                    email.state.append('tagged')
                    email.tags = action["arguments"]["tags"]
                elif action["name"]== "archive_email":
                    email.state.append('archived')
        return email
        
    async def get_openai_response(self, prompt):
        model = "gpt-4o-mini"
        messages = [
            {"role": "system", "content": "You are a helpful assistant that can help with email."},
            {"role": "user", "content": prompt}
        ]

        #wrap in asyncio to_thread
        response = self.client.responses.create(
                model=model,
                input = messages,
                text = {
                    "format": {
                        "type": "text"
                    }
                },
                tools=DEFAULT_TOOLS,
            )
        
        

        print("--------------------------------")
        print(len(response.output))
        
        for output in response.output:
            if output.type == "function_call":
                print('Using tool: ', output.name)
                print('--> args: ', output.arguments)
            else:
                try:
                    print('Text response: ', output.text)
                except:
                    print('Text response: ', '')
        print("--------------------------------")
        action = {
          "tool_calls": [],
          "text": ""
        }
        
        for output in response.output:
            if output.type == "function_call":
                action["tool_calls"].append({
                    "name": output.name,
                    "arguments": json.loads(output.arguments)
                })
            else:
                try:
                    action["text"] = output.text 
                except:
                    action["text"] = ''
        return action

