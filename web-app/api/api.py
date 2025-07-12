import time
import json
from flask import Flask, jsonify
import boto3
import os

AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'dmail_emails')

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
email_table = dynamodb.Table(DYNAMODB_TABLE)

app = Flask(__name__)

@app.route('/api/time')
def get_current_time():
    return {'time': time.time()}


@app.route('/api/emails')
def get_emails():
    """Return emails stored in DynamoDB."""
    try:
        response = email_table.scan()
        items = response.get('Items', [])
        # convert stringified fields back
        emails = []
        for item in items:
            emails.append({
                'id': item.get('message_id'),
                'from': json.loads(item.get('from', '[]')),
                'subject': item.get('subject', ''),
                'to': json.loads(item.get('to', '[]')),
                'body': item.get('body', ''),
                'date': item.get('date', '')
            })
        return jsonify(emails)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

