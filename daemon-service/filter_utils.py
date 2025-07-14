import json
import os

from database import db
from mailparser import MailParser

try:
    from openai import OpenAI
except ImportError:  # openai optional
    OpenAI = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OpenAI and OPENAI_API_KEY else None


def get_rules(user: str):
    """Retrieve whitelist rules from database."""
    try:
        metadata = db.get_metadata(user, "rules")
        if metadata:
            return json.loads(metadata)
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


def should_store(parsed_email: MailParser, user: str) -> bool:
    """Check if an email should be stored based on whitelist rules."""
    rules = get_rules(user)
    
    # If no rules, allow everything
    if not rules:
        return True
    
    # Check each rule
    for rule in rules:
        rule_type = rule.get("type", "")
        
        if rule_type == "email" or rule_type == "sender":
            sender_email = str(parsed_email.from_).lower()
            if rule.get("value", "").lower() in sender_email:
                return True
        
        elif rule_type == "subject":
            subject = (parsed_email.subject or "").lower()
            if rule.get("value", "").lower() in subject:
                return True
        
        elif rule_type == "llm":
            description = rule.get("description", "")
            if llm_allows(parsed_email, description):
                return True
    
    # If no rules match, block the email
    return False
