import time
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/time')
def get_current_time():
    return {'time': time.time()}


@app.route('/api/emails')
def get_emails():
    """Return a list of fake email data."""
    now = time.time()
    emails = [
        {
            "id": 1,
            "from": "alice@example.com",
            "subject": "Welcome to dMail!",
            "timestamp": now - 3600,
        },
        {
            "id": 2,
            "from": "bob@example.com",
            "subject": "Meeting schedule",
            "timestamp": now - 7200,
        },
        {
            "id": 3,
            "from": "carol@example.com",
            "subject": "Re: Vacation plans",
            "timestamp": now - 86400,
        },
        {
            "id": 4,
            "from": "dan@example.com",
            "subject": "Newsletter - July",
            "timestamp": now - 172800,
        },
    ]
    return jsonify(emails)
