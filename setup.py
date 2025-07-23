#!/usr/bin/env python3
"""
DispatchMail Setup Script
This script helps you set up and run the dMail application locally.
"""

import os
import sys
import subprocess
import sqlite3
import json
import getpass
from pathlib import Path

def install_dependencies():
    """Install required Python dependencies."""
    print("📦 Installing dependencies...")
    
    # Install API dependencies
    api_requirements = Path("web-app/api/requirements.txt")
    if api_requirements.exists():
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(api_requirements)], 
                         check=True, capture_output=True, text=True)
            print("✅ Backend dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install backend dependencies: {e}")
            return False
    
    # Install web app dependencies (Node.js)
    web_app_dir = Path("web-app")
    if web_app_dir.exists() and (web_app_dir / "package.json").exists():
        try:
            subprocess.run(["npm", "install"], cwd=web_app_dir, check=True, capture_output=True, text=True)
            print("✅ Frontend dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install frontend dependencies: {e}")
            print("   Make sure Node.js and npm are installed")
            return False
    
    return True

def initialize_database():
    """Initialize the SQLite database."""
    print("🗄️  Initializing database...")
    
    try:
        # Import and initialize the database
        from database import db
        
        # The database is automatically initialized when the module is imported
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return False

def create_sample_config():
    """Create a sample configuration file."""
    print("📝 Creating sample configuration...")
    
    config_content = """# dMail Configuration
# This file contains your email credentials and API keys

# OpenAI API Key (required for AI processing)
OPENAI_API_KEY = 'your-openai-api-key-here'

# Gmail Setup Instructions:
# 1. Enable 2FA on your Google account
# 2. Generate an App Password for this application
# 3. Use your email and App Password when setting up user accounts through the web interface
"""
    
    try:
        sample_path = Path("web-app/api/secrets.py.sample")
        with open(sample_path, "w") as f:
            f.write(config_content)
        print(f"✅ Sample configuration created at {sample_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to create sample configuration: {e}")
        return False

def setup_user_account():
    """Set up a user account interactively."""
    print("👤 Setting up user account...")
    
    email = input("Enter your email: ").strip()
    if not email:
        print("❌ Email is required")
        return False
    
    password = getpass.getpass("Enter your Gmail app password: ").strip()
    if not password:
        print("❌ Password is required")
        return False
    
    host = input(f"Enter IMAP host (default: imap.gmail.com): ").strip() or "imap.gmail.com"
    
    try:
        from database import db
        
        success = db.put_user(email, host, password)
        if success:
            print("✅ User account created successfully")
            return True
        else:
            print("❌ Failed to create user account")
            return False
    except Exception as e:
        print(f"❌ Failed to create user account: {e}")
        return False

def start_services():
    """Show how to start the dMail services."""
    print("🚀 Starting dMail services...")
    
    print("\nTo start the services:")
    print("\n1. Option A - Use the startup script (recommended):")
    print("   python start.py")
    
    print("\n2. Option B - Start services manually:")
    print("   Terminal 1 - API server:")
    print("   cd web-app && python api/api.py")
    print("\n   Terminal 2 - Frontend (in another terminal):")
    print("   cd web-app && npm run dev")
    
    print("\n📱 Once started, open http://localhost:5173 in your browser")
    print("🔗 API will be available at http://localhost:5000")

def main():
    """Main setup function."""
    print("🔧 DispatchMail Setup Script")
    print("============================")
    
    # Check if we're in the right directory
    if not os.path.exists("web-app") or not os.path.exists("database.py"):
        print("❌ Please run this script from the dMail root directory")
        sys.exit(1)
    
    # Step 1: Install dependencies
    if not install_dependencies():
        print("❌ Setup failed at dependency installation")
        sys.exit(1)
    
    # Step 2: Initialize database
    if not initialize_database():
        print("❌ Setup failed at database initialization")
        sys.exit(1)
    
    # Step 3: Create sample configuration
    if not create_sample_config():
        print("⚠️  Warning: Could not create sample configuration")
    
    # Step 4: Check if secrets file exists
    secrets_file = Path("web-app/api/secrets.py")
    if not secrets_file.exists():
        print("\n⚠️  Configuration required:")
        print("   1. Copy web-app/api/secrets.py.sample to web-app/api/secrets.py")
        print("   2. Update the OPENAI_API_KEY in secrets.py")
        print("   3. For Gmail, create an App Password: https://support.google.com/mail/answer/185833")
        
        create_now = input("\nWould you like to create the configuration now? (y/n): ").lower().strip()
        if create_now == 'y':
            # Copy sample to actual file
            try:
                sample_file = Path("web-app/api/secrets.py.sample")
                if sample_file.exists():
                    with open(sample_file, "r") as sample:
                        content = sample.read()
                    with open(secrets_file, "w") as actual:
                        actual.write(content)
                    print(f"✅ Created {secrets_file} - please edit it with your API key")
                else:
                    # Create a basic secrets file
                    with open(secrets_file, "w") as f:
                        f.write("# OpenAI API Key\nOPENAI_API_KEY = 'your-openai-api-key-here'\n")
                    print(f"✅ Created {secrets_file} - please edit it with your API key")
            except Exception as e:
                print(f"❌ Failed to create secrets.py: {e}")
    
    # Step 5: Optionally set up user account
    if secrets_file.exists():
        setup_user = input("\nWould you like to set up a user account now? (y/n): ").lower().strip()
        if setup_user == 'y':
            if not setup_user_account():
                print("⚠️  You can set up user accounts later through the web interface")
    
    # Step 6: Show how to start services
    start_services()
    
    print("\n✅ Setup complete!")
    print("\n📋 Next steps:")
    print("   1. Edit web-app/api/secrets.py with your OpenAI API key")
    print("   2. Run 'python start.py' to start all services")
    print("   3. Open http://localhost:5173 and set up your email account")
    print("   4. Configure whitelist rules for email filtering")
    print("\n📖 For more information, see the README.md file")

if __name__ == "__main__":
    main() 