import json
import os

import boto3
from mailparser import MailParser

from config_reader import AWS_REGION, DYNAMODB_META_TABLE

try:
    from openai import OpenAI
except ImportError:  # openai optional
    OpenAI = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OpenAI and OPENAI_API_KEY else None

# DynamoDB meta table

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
meta_table = dynamodb.Table(DYNAMODB_META_TABLE)


def get_rules():
    """Retrieve whitelist rules from DynamoDB."""
    try:
        resp = meta_table.get_item(Key={"user": "whitelist_rules"})
        item = resp.get("Item")
        if item and item.get("rules"):
            return json.loads(item["rules"])
    except Exception as e:
        print(f"Error fetching whitelist rules: {e}")
    return []


def llm_allows(parsed_email: MailParser, description: str) -> bool:
    """Use an LLM to decide if an email matches a rule."""
    if not client:
        return False
    body = parsed_email.text_plain[0] if parsed_email.text_plain else ""
    content = f"Subject: {parsed_email.subject}\nFrom: {parsed_email.from_}\n\n{body}"
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": description},
                {"role": "user", "content": content},
            ],
            temperature=0,
        )
        text = resp.choices[0].message.content.strip().lower()
        return "allow" in text
    except Exception as e:
        print(f"OpenAI classification failed: {e}")
        return False


def matches_rule(parsed_email: MailParser, rule: dict) -> bool:
    rtype = rule.get("type")
    value = str(rule.get("value", "")).lower()
    if rtype == "email":
        addresses = [addr.lower() for _name, addr in parsed_email.from_]
        if parsed_email.reply_to:
            addresses += [addr.lower() for _name, addr in parsed_email.reply_to]
        
        # Debug logging
        print(f"DEBUG: Checking email rule '{value}' against addresses: {addresses}")
        
        return any(value == addr for addr in addresses)
    if rtype == "subject":
        subject = (parsed_email.subject or "").lower()
        
        # Debug logging
        print(f"DEBUG: Checking subject rule '{value}' against subject: '{subject}'")
        
        return value in subject
    if rtype == "classification":
        return llm_allows(parsed_email, value)
    return False


def should_store(parsed_email: MailParser) -> bool:
    """Return True if email should be stored based on whitelist rules."""
    rules = get_rules()
    if not rules:
        return True
    for rule in rules:
        if matches_rule(parsed_email, rule):
            return True
    return False
