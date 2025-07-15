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

# SQLite configuration - use absolute path so both daemon and API use the same database
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(PROJECT_ROOT, 'dmail.db'))

# Number of days to look back when fetching emails on startup
# if no previous timestamp is stored.
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '1'))

# OpenAI API Key
OPENAI_API_KEY = secrets.OPENAI_API_KEY