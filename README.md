<p align="center">
    <picture>
      <source srcset="assets/wordmarkpreferdark.png" media="(prefers-color-scheme: dark)">
      <source srcset="assets/wordmark.png" media="(prefers-color-scheme: light)">
      <img src="assets/wordmark.png" alt="DISPATCH MAIL">
    </picture>
  </a>
</p>

<p align="center">AI-native Email Inbox</p>

DispatchMail is an open source locally run (though currently using OpenAI for queries) AI-powered email assistant that helps you manage your inbox. It monitors your email, processes it with an AI agent based on your prompts, and provides a (locally run) web interface for managing drafts/responses, and instructions.

## Features

- 🤖 AI-powered email processing through OpenAI
- 📱 Web interface for inbox management
- 🎯 Customizable email filtering and whitelist rules to only give the AI access to specific types of emails
- 📝 Draft generation and email composition
- 🏷️ Automatic Email labeling and organization (including archival)
- 🗄️ Local SQLite database (no cloud dependencies for storage)
- 🕵️‍♂️ Customizable LLM powered deep research on sender profiles

## Planned Roadmap + Current Readiness
This is an early alpha/prototype project. It's made to run locally for developers who want to tinker. We welcome feedback and plan to improve and expand based on user feedback and interest. We would love to offer a managed, more polished version of this if there is interest as we believe the future of AI Agents working with Humans is collaborative and will require more Human/Agent "multiplayer" spaces.

Long run, we want to not just give AI Agents a place to work in your inbox, but their own AI-native email as well as our colleagues. For now, this is a helpful babystep, and we welcome feedback, contributions, and discussion.

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+ (for web interface)
- Gmail account with 2FA enabled
- OpenAI API key (required for AI features)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/dbish/DispatchMail.git
   cd DispatchMail
   ```

2. Run the setup script:
   ```bash
   python setup.py
   ```

   This will:
   - Install all dependencies
   - Initialize the SQLite database
   - Create a sample configuration file
   - Guide you through account setup

3. Configure your credentials:
   - Edit `web-app/api/credentials.py` with your OpenAI API key
   - For Gmail, create an App Password: https://support.google.com/mail/answer/185833 (add a feature request for login with Google if you'd prefer that :) )

4. Start the services:
   ```bash
   # Option A: Use the startup script (recommended)
   python start.py
   
   # Option B: Start manually
   # Terminal 1: Start the web API
   cd web-app
   python api/api.py
   
   # Terminal 2: Start the frontend (in another terminal)
   cd web-app
   npm run dev
   ```

5. Open http://localhost:5173 in your browser and set up your email account

## Manual Setup

If you prefer to set up manually:

### 1. Install Dependencies

```bash
# Backend dependencies
cd web-app/api
pip install -r requirements.txt

# Frontend dependencies
cd ../
npm install
```

### 2. Configure Credentials

Create `web-app/api/credentials.py`:
```python
# OpenAI API Key
OPENAI_API_KEY = 'your-openai-api-key'
```

### 3. Initialize Database

```bash
python -c "from database import db; print('Database initialized!')"
```

### 4. Add User Account

You can add user accounts through the web interface or programmatically:
```bash
python -c "
from database import db
db.put_user('your-email@gmail.com', 'imap.gmail.com', 'your-app-password')
print('User added!')
"
```

## Gmail Setup

For Gmail accounts, you need:

1. **Enable 2FA**: Go to your Google Account settings and enable 2-factor authentication
2. **Generate App Password**: 
   - Go to Google Account > Security > App passwords
   - Generate a new app password for "Mail"
   - Use this password when setting up your account in the web interface

## Configuration

### Email Filtering

Configure whitelist rules via the web interface to control which emails are processed:

- **Sender-based rules**: Filter by sender email address
- **Subject-based rules**: Filter by keywords in subject line
- **AI-based rules**: Use natural language to describe filtering criteria

### AI Prompts

Customize the AI behavior by setting:

- **Reading Prompt**: Instructions for how the AI should analyze emails
- **Draft Prompt**: Instructions for how the AI should generate responses

## Database Schema

The SQLite database contains three main tables:

- `emails`: Stores email content and processing status
- `metadata`: Stores configuration, prompts, and user preferences
- `users`: Stores IMAP account credentials

## API Endpoints

The web API provides REST endpoints for:

- `GET /api/emails` - List emails
- `GET /api/emails/<id>` - Get specific email
- `POST /api/emails/<id>/draft` - Update draft
- `GET/POST /api/prompts/reading` - Manage reading prompt
- `GET/POST /api/prompts/draft` - Manage draft prompt
- `GET/POST /api/whitelist` - Manage whitelist rules
- `GET/POST /api/users` - Manage user accounts
- `GET /api/process_emails` - Process unprocessed emails
- `GET /api/get_updates` - Retrieve new emails from server

## Security Notes

- All data is stored locally in SQLite
- Email credentials are stored in the database
- OpenAI API key is stored in `web-app/api/credentials.py`
- Consider using environment variables for production deployments
- The application binds to `0.0.0.0:5000` by default

## Troubleshooting

### Common Issues

1. **Authentication Failed**: 
   - Make sure you're using an App Password, not your regular password
   - Verify 2FA is enabled on your Google account

2. **Database Errors**:
   - Delete `dmail.db` and restart to reset the database
   - Check file permissions in the project directory

3. **Port Conflicts**:
   - Web API runs on port 5000
   - Frontend runs on port 5173
   - Make sure these ports are available

4. **OpenAI API Errors**:
   - Verify your API key is correct in `web-app/api/credentials.py`
   - Check your OpenAI account has sufficient credits

### Debug Mode

Check logs in the `logs/` directory:
```bash
# View API logs
tail -f logs/api.log

# View frontend logs
tail -f logs/frontend.log
```

## Development

### Project Structure

```
DispatchMail/
├── database.py             # SQLite database interface
├── start.py                # Service startup script
├── setup.py                # Setup script
├── web-app/                # Frontend and API
│   ├── api/
│   │   ├── api.py          # Flask web API
│   │   ├── inbox.py        # Email processing logic
│   │   ├── agent.py        # AI processing
│   │   ├── gmail.py        # Gmail IMAP integration
│   │   ├── credentials.py  # API keys and credentials
│   │   └── requirements.txt # Python dependencies
│   ├── src/                # React frontend
│   └── package.json        # Node.js dependencies
└── logs/                   # Application logs
```

### How It Works

1. **Email Retrieval**: The API connects to your Gmail via IMAP to fetch new emails
2. **Filtering**: Emails are filtered based on whitelist rules you configure
3. **AI Processing**: Filtered emails are processed by OpenAI GPT for classification and draft generation
4. **Web Interface**: The React frontend provides a UI for managing emails and drafts
5. **Local Storage**: All data is stored locally in SQLite for privacy

### Adding Features

1. **New AI Prompts**: Modify `web-app/api/agent.py`
2. **New Filters**: Extend `web-app/api/inbox.py`
3. **New API Endpoints**: Add to `web-app/api/api.py`
4. **Frontend Changes**: Modify files in `web-app/src/`

## License

Apache-2.0 - see LICENSE file for details

## Copyright

Copyright (c) 2025 Datadog https://www.datadoghq.com

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the console logs for error messages
3. Check the logs in the `logs/` directory
4. Open an issue in the repository
