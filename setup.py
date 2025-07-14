#!/usr/bin/env python3
"""
dMail Setup Script
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
    
    # Install daemon service dependencies
    daemon_requirements = Path("daemon-service/requirements.txt")
    if daemon_requirements.exists():
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(daemon_requirements)], 
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
        sys.path.insert(0, 'daemon-service')
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
# Copy this to daemon-service/secrets.py and update with your credentials

# IMAP Configuration
HOST = 'imap.gmail.com'
USER = 'your-email@gmail.com'
PASSWORD = 'your-app-password'  # Gmail App Password, not your regular password

# OpenAI API Key (optional, for AI processing)
OPENAI_API_KEY = 'your-openai-api-key'

# Note: For Gmail, you need to:
# 1. Enable 2FA on your Google account
# 2. Generate an App Password for this application
# 3. Use the App Password in the PASSWORD field above
"""
    
    try:
        with open("daemon-service/secrets.py.sample", "w") as f:
            f.write(config_content)
        print("✅ Sample configuration created at daemon-service/secrets.py.sample")
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
    
    password = getpass.getpass("Enter your app password: ").strip()
    if not password:
        print("❌ Password is required")
        return False
    
    host = input(f"Enter IMAP host (default: imap.gmail.com): ").strip() or "imap.gmail.com"
    
    try:
        sys.path.insert(0, 'daemon-service')
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
    """Start the dMail services."""
    print("🚀 Starting dMail services...")
    
    print("\nTo start the services manually:")
    print("1. Backend daemon:")
    print("   cd daemon-service && python observer.py")
    print("\n2. Web API (in another terminal):")
    print("   cd web-app && python api/api.py")
    print("\n3. Frontend (in another terminal):")
    print("   cd web-app && npm run dev")
    print("\nThen open http://localhost:5173 in your browser")

def main():
    """Main setup function."""
    print("🔧 dMail Setup Script")
    print("====================")
    
    # Check if we're in the right directory
    if not os.path.exists("daemon-service") or not os.path.exists("web-app"):
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
    secrets_file = Path("daemon-service/secrets.py")
    if not secrets_file.exists():
        print("\n⚠️  Configuration required:")
        print("   1. Copy daemon-service/secrets.py.sample to daemon-service/secrets.py")
        print("   2. Update the credentials in secrets.py")
        print("   3. For Gmail, create an App Password: https://support.google.com/mail/answer/185833")
        
        create_now = input("\nWould you like to create the configuration now? (y/n): ").lower().strip()
        if create_now == 'y':
            # Copy sample to actual file
            try:
                with open("daemon-service/secrets.py.sample", "r") as sample:
                    content = sample.read()
                with open("daemon-service/secrets.py", "w") as actual:
                    actual.write(content)
                print("✅ Created daemon-service/secrets.py - please edit it with your credentials")
            except Exception as e:
                print(f"❌ Failed to create secrets.py: {e}")
    
    # Step 5: Optionally set up user account
    if secrets_file.exists():
        setup_user = input("\nWould you like to set up a user account now? (y/n): ").lower().strip()
        if setup_user == 'y':
            setup_user_account()
    
    # Step 6: Show how to start services
    start_services()
    
    print("\n✅ Setup complete!")
    print("📖 For more information, see the README.md file")

if __name__ == "__main__":
    main() 