from dotenv import load_dotenv
import os
import importlib.util
import sys

# Load the local secrets.py file explicitly
secrets_path = os.path.join(os.path.dirname(__file__), 'secrets.py')
spec = importlib.util.spec_from_file_location('local_secrets', secrets_path)
secrets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(secrets)

load_dotenv()

HOST = os.getenv('HOST') or secrets.HOST
USER = os.getenv('USER') or secrets.USER
PASSWORD = os.getenv('PASSWORD') or secrets.PASSWORD

# AWS configuration for DynamoDB
AWS_REGION = os.getenv('AWS_REGION') or secrets.AWS_REGION
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID') or secrets.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY') or secrets.AWS_SECRET_ACCESS_KEY

# Set AWS credentials as environment variables so boto3 can find them
os.environ.setdefault('AWS_ACCESS_KEY_ID', AWS_ACCESS_KEY_ID)
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', AWS_SECRET_ACCESS_KEY)
os.environ.setdefault('AWS_DEFAULT_REGION', AWS_REGION)

DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'diamond_dmail_emails')

# Table used for storing metadata such as the last processed
# email timestamp for the IMAP user.
DYNAMODB_META_TABLE = os.getenv('DYNAMODB_META_TABLE', 'diamond_dmail_metadata')

# Table that contains IMAP account credentials
DYNAMODB_USERS_TABLE = os.getenv('DYNAMODB_USERS_TABLE', 'diamond_dmail_users')

# Number of days to look back when fetching emails on startup
# if no previous timestamp is stored.
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '5'))

# OpenAI API Key
OPENAI_API_KEY = secrets.OPENAI_API_KEY