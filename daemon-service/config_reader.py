from dotenv import load_dotenv
import os
import secrets

load_dotenv()

HOST = os.getenv('HOST') or secrets.HOST
USER = os.getenv('USER') or secrets.USER
PASSWORD = os.getenv('PASSWORD') or secrets.PASSWORD

# AWS configuration for DynamoDB
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'dmail_emails')

# Table used for storing metadata such as the last processed
# email timestamp for the IMAP user.
DYNAMODB_META_TABLE = os.getenv('DYNAMODB_META_TABLE', 'dmail_metadata')

# Table that contains IMAP account credentials
DYNAMODB_USERS_TABLE = os.getenv('DYNAMODB_USERS_TABLE', 'dmail_users')

# Number of days to look back when fetching emails on startup
# if no previous timestamp is stored.
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '5'))
