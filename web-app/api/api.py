from inbox import Inbox
from flask import Flask, jsonify, request
from gmail import retrieve_emails, send_email
from flask_cors import CORS
import asyncio
import os
import sys
import importlib.util

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import database
database_path = os.path.join(BASE_DIR, 'database.py')
spec_db = importlib.util.spec_from_file_location('database', database_path)
database = importlib.util.module_from_spec(spec_db)
spec_db.loader.exec_module(database)
db = database.db

app = Flask(__name__)
CORS(app)

inbox = None

def before_first_request():
    global inbox
    inbox = Inbox()
    inbox.retrieve_function = retrieve_emails
    inbox.send_function = send_email
    inbox.db = db

with app.app_context():
    before_first_request()

@app.route('/api/get_updates', methods=['GET'])
def get_updates():

    print(inbox.state)
    print('getting updates')
    inbox.update_state(inbox.State.UPDATING)
    print('updates done')

    return jsonify([email.to_dict() for email in inbox.emails.values()])

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users."""
    try:
        users = db.get_users()
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/emails', methods=['GET'])
def get_emails():
    return jsonify([email.to_dict() for email in inbox.emails.values()])

@app.route('/api/process_emails', methods=['GET'])
def process_emails():
    paging = request.args.get('paging')
    if paging == 'false':
        inbox.clear_all_processed()
    result = asyncio.run(inbox.continue_processing())
    return jsonify(result)

@app.route('/api/emails/<message_id>', methods=['GET'])
def get_email(message_id):
    return jsonify(inbox.emails[message_id].to_dict())

@app.route('/api/send', methods=['POST'])
def send_email():
    data = request.get_json()
    email_id = data.get('id')
    draft_text = data.get('draft')
    print(f"Sending email: {email_id} {draft_text}")
    inbox.send(email_id, draft_text)
    return jsonify({'success': True})


# Additional endpoints needed by frontend
@app.route('/api/user_profile', methods=['GET'])
def get_user_profile():
    """Get user profile information."""
    try:
        email = request.args.get('email')
        if not email:
            return jsonify({'error': 'Email parameter required'}), 400
        
        # Check if user exists
        users = db.get_users()
        user = None
        for u in users:
            if u.get('user') == email:
                user = u
                print(f"User found -- breaking: {user}")
                break

        if not user:
            print(f"User not found")
            return jsonify({'error': 'User not found'}), 404

        # Get user metadata
        inbox.user = email
        inbox.app_password = user.get('password')
        metadata = db.get_metadata(email)
                
        profile = {
            'email': email,
            'host': user.get('host', 'imap.gmail.com'),
            'active': user.get('active', True),
            'last_processed': metadata.get('last_processed') if metadata else None,
            'created_at': user.get('created_at')
        }

        if metadata:
            if metadata.get('rules'):
                inbox.whitelist.update_from_json(metadata.get('rules'))
        inbox.update_state(inbox.State.HYDRATING)
        return jsonify(profile)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/update_user_profile', methods=['POST'])
def update_user_profile():
    """Update user profile."""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        # For now, just return success as we don't have much to update
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/draft_prompt', methods=['GET'])
def get_draft_prompt_alias():
    """Get the draft prompt (alias for /api/prompts/draft)."""
    try:
        return jsonify({'prompt': 'test'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompt', methods=['GET', 'POST'])
def get_prompt_endpoint():
    """Get the reading prompt (alias for /api/prompts/reading)."""
    if request.method == 'POST':
        data = request.json
        print(f"Received prompt: {data}")
        inbox.agent.instructions = data['prompt']
        return jsonify({'success': True})
    else:
        try:
            return jsonify({'prompt': inbox.agent.instructions})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/whitelist', methods=['GET', 'POST'])
def get_whitelist():
    if request.method == 'POST':
        data = request.json
        print(f"Received whitelist: {data}")
        inbox.whitelist.update_from_json(data)
        inbox.save_whitelist()
        return jsonify({'success': True})
    else:
        print(len(inbox.whitelist.filters))
        print(f"Getting whitelist: {inbox.whitelist.to_json()}")
        try:
            return jsonify({'whitelist': inbox.whitelist.to_json()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/reprocess_all', methods=['GET'])
def reprocess_all():
    asyncio.run(inbox.reretrieve_all())
    return jsonify({'success': True})

@app.route('/api/research_sender', methods=['POST'])
def research_sender():
    """Research information about an email sender."""
    try:
        data = request.get_json()
        sender_email = data.get('sender_email')
        sender_name = data.get('sender_name', '')
        
        if not sender_email:
            return jsonify({'error': 'Sender email required'}), 400
        
        # Format input exactly like the example
        if sender_name:
            user_input = f"{sender_name},{sender_email}\n\n"
        else:
            user_input = f"{sender_email}\n\n"
        
        # Use OpenAI to research the sender
        from openai import OpenAI
        import config_reader
        
        client = OpenAI(api_key=config_reader.OPENAI_API_KEY)
        
        # Stick strictly to the example
        response = client.responses.create(
            model="gpt-4.1",
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "You are an expert people researcher. You'll be provided an email and your goal is to create a snippet to summarize information about the sender. you can use the domain to understand the organization if it isn't a large email provider, and you can use web search to get info on them."
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_input
                        }
                    ]
                }
            ],
            text={
                "format": {
                    "type": "text"
                }
            },
            reasoning={},
            tools=[
                {
                    "type": "web_search_preview",
                    "user_location": {
                        "type": "approximate"
                    },
                    "search_context_size": "medium"
                }
            ],
            temperature=1,
            max_output_tokens=2048,
            top_p=1
        )
        # Process the response to extract summary and annotations
        summary = ""
        annotations = []
        
        for output in response.output:
            if output.type == "message":
                # Extract the text content
                if hasattr(output, 'content') and output.content:
                    for content in output.content:
                        if hasattr(content, 'text'):
                            summary = content.text
                        # Extract URL citations/annotations
                        if hasattr(content, 'annotations'):
                            for annotation in content.annotations:
                                if annotation.type == "url_citation":
                                    annotations.append({
                                        'url': annotation.url,
                                        'title': getattr(annotation, 'title', ''),
                                        'description': getattr(annotation, 'title', '')
                                    })
        
        return jsonify({
            'success': True,
            'summary': summary,
            'annotations': annotations,
            'search_query': user_input.strip()
        })
        
    except Exception as e:
        print(f"Error in research_sender: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def get_emails_status():
    """Get email update status."""
    try:
        # Get all emails
        emails = inbox.emails.values()
        
        if not emails:
            return jsonify({
                'last_modified': '', 
                'total_count': 0,
                'unprocessed_count': 0,
                'awaiting_human_count': 0,
                'processed_count': 0
            })
        
        # Calculate last modified time based on all emails (same logic as /api/emails)
        last_modified = inbox.get_last_modified()
        
        return jsonify({
            'last_modified': last_modified,
            'total_count': len(emails),
            'unprocessed_count': len(inbox.unprocessed_message_ids),
            'awaiting_human_count': len(inbox.awaiting_human_message_ids),
            'processed_count': len(inbox.processed_message_ids)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/signout', methods=['POST'])
def signout():
    """Sign out user."""
    try:
        # For local SQLite version, just return success
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)