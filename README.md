# DispatchMail - Local Email AI Assistant

dMail is an AI-powered email assistant that helps you manage your inbox locally using SQLite. It monitors your email, processes it with AI, and provides a web interface for managing drafts and responses.

## Features

- 🔄 Real-time email monitoring via IMAP
- 🤖 AI-powered email processing with OpenAI GPT
- 📱 Modern web interface for inbox management
- 🎯 Customizable email filtering and whitelist rules
- 📝 Draft generation and email composition
- 🏷️ Email labeling and organization
- 🗄️ Local SQLite database (no cloud dependencies)

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+ (for web interface)
- Gmail account with 2FA enabled
- OpenAI API key (optional, for AI features)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd dMail
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
   - Edit `daemon-service/secrets.py` with your email credentials
   - For Gmail, create an App Password: https://support.google.com/mail/answer/185833

4. Start the services:
   ```bash
   # Terminal 1: Start the email daemon
   cd daemon-service
   python observer.py
   
   # Terminal 2: Start the web API
   cd web-app
   python api/api.py
   
   # Terminal 3: Start the frontend
   cd web-app
   npm run dev
   ```

5. Open http://localhost:5173 in your browser

## Manual Setup

If you prefer to set up manually:

### 1. Install Dependencies

```bash
# Backend dependencies
cd daemon-service
pip install -r requirements.txt

# Frontend dependencies
cd ../web-app
npm install
```

### 2. Configure Secrets

Create `daemon-service/secrets.py`:
```python
# IMAP Configuration
HOST = 'imap.gmail.com'
USER = 'your-email@gmail.com'
PASSWORD = 'your-app-password'  # Gmail App Password

# OpenAI API Key (optional)
OPENAI_API_KEY = 'your-openai-api-key'
```

### 3. Initialize Database

```bash
cd daemon-service
python -c "from database import db; print('Database initialized!')"
```

### 4. Add User Account

```bash
cd daemon-service
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
   - Use this password in your `secrets.py` file

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

## Security Notes

- All data is stored locally in SQLite
- Email credentials are stored in plain text in `secrets.py`
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

### Debug Mode

Run with debug output:
```bash
cd daemon-service
python observer.py --debug
```

## Development

### Project Structure

```
dMail/
├── daemon-service/          # Backend email processing
│   ├── database.py         # SQLite database interface
│   ├── observer.py         # Email monitoring daemon
│   ├── ai_processor.py     # AI processing logic
│   ├── config_reader.py    # Configuration management
│   ├── filter_utils.py     # Email filtering
│   └── secrets.py          # Credentials (create from sample)
├── web-app/                # Frontend and API
│   ├── api/api.py          # Flask web API
│   ├── src/                # React frontend
│   └── package.json        # Node.js dependencies
└── setup.py                # Setup script
```

### Adding Features

1. **New AI Prompts**: Add to `ai_processor.py`
2. **New Filters**: Extend `filter_utils.py`
3. **New API Endpoints**: Add to `web-app/api/api.py`
4. **Frontend Changes**: Modify files in `web-app/src/`

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the console logs for error messages
3. Open an issue in the repository
