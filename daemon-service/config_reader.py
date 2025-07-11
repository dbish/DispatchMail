from dotenv import load_dotenv
import os
import secrets

load_dotenv()

HOST = os.getenv('HOST') or secrets.HOST
USER = os.getenv('USER') or secrets.USER
PASSWORD = os.getenv('PASSWORD') or secrets.PASSWORD