#!/usr/bin/env python3
"""
Add User Utility
Simple script to add email accounts to the dMail database.
"""

import sys
import os
import getpass
from pathlib import Path

def add_user():
    """Add a user to the database."""
    print("📧 Add User to dMail")
    print("===================")
    
    # Add daemon-service to path
    daemon_dir = Path("daemon-service")
    if not daemon_dir.exists():
        print("❌ daemon-service directory not found")
        print("   Make sure you're running this from the dMail root directory")
        return False
    
    sys.path.insert(0, str(daemon_dir))
    
    try:
        from database import db
    except ImportError as e:
        print(f"❌ Failed to import database module: {e}")
        print("   Run 'python setup.py' first to install dependencies")
        return False
    
    # Get user input
    email = input("Enter email address: ").strip()
    if not email:
        print("❌ Email is required")
        return False
    
    password = getpass.getpass("Enter app password: ").strip()
    if not password:
        print("❌ Password is required")
        return False
    
    host = input("Enter IMAP host (default: imap.gmail.com): ").strip()
    if not host:
        host = "imap.gmail.com"
    
    # Test the credentials (basic validation)
    if "@" not in email:
        print("❌ Invalid email format")
        return False
    
    # Add user to database
    try:
        success = db.put_user(email, host, password)
        if success:
            print(f"✅ User {email} added successfully")
            return True
        else:
            print("❌ Failed to add user to database")
            return False
    except Exception as e:
        print(f"❌ Error adding user: {e}")
        return False

def list_users():
    """List all users in the database."""
    print("👥 Current Users")
    print("================")
    
    # Add daemon-service to path
    daemon_dir = Path("daemon-service")
    if not daemon_dir.exists():
        print("❌ daemon-service directory not found")
        return False
    
    sys.path.insert(0, str(daemon_dir))
    
    try:
        from database import db
        users = db.get_users()
        
        if not users:
            print("No users found in database")
            return True
        
        for user in users:
            print(f"📧 {user.get('user', 'Unknown')} ({user.get('host', 'Unknown host')})")
        
        return True
    except Exception as e:
        print(f"❌ Error listing users: {e}")
        return False

def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        list_users()
    else:
        add_user()

if __name__ == "__main__":
    main() 