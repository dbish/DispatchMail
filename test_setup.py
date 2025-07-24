#!/usr/bin/env python3
"""
Test Script for dMail SQLite Setup
This script verifies that the SQLite database and all components are working correctly.
"""

import sys
import os
from pathlib import Path

def test_database():
    """Test database connectivity and basic operations."""
    print("🧪 Testing database...")
    
    # Add daemon-service to path
    daemon_dir = Path("daemon-service")
    if not daemon_dir.exists():
        print("❌ daemon-service directory not found")
        return False
    
    sys.path.insert(0, str(daemon_dir))
    
    try:
        from database import db
        
        # Test database initialization
        print("✅ Database module imported successfully")
        
        # Test user operations
        test_email = "test@example.com"
        test_host = "imap.gmail.com"
        test_password = "test-password"
        
        # Add test user
        success = db.put_user(test_email, test_host, test_password)
        if not success:
            print("❌ Failed to add test user")
            return False
        
        print("✅ Test user added successfully")
        
        # Get test user
        users = db.get_users()
        found_user = False
        for user in users:
            if user.get('user') == test_email:
                found_user = True
                break
        
        if not found_user:
            print("❌ Test user not found")
            return False
        
        print("✅ Test user retrieved successfully")
        
        # Test metadata operations
        test_metadata = {"test_key": "test_value"}
        success = db.put_metadata("test_user", test_metadata)
        if not success:
            print("❌ Failed to add test metadata")
            return False
        
        print("✅ Test metadata added successfully")
        
        # Get test metadata
        metadata = db.get_metadata("test_user")
        if not metadata:
            print("❌ Test metadata not found")
            return False
        
        print("✅ Test metadata retrieved successfully")
        
        # Test email operations
        test_email_data = {
            'message_id': 'test-123',
            'subject': 'Test Subject',
            'to': 'test@example.com',
            'from': 'sender@example.com',
            'body': 'Test body',
            'date': '2024-01-01T00:00:00Z',
            'processed': False,
            'action': '',
            'draft': '',
            'account': test_email,
        }
        
        success = db.put_email(test_email_data)
        if not success:
            print("❌ Failed to add test email")
            return False
        
        print("✅ Test email added successfully")
        
        # Get test email
        email = db.get_email('test-123')
        if not email:
            print("❌ Test email not found")
            return False
        
        print("✅ Test email retrieved successfully")
        
        # Update test email
        success = db.update_email('test-123', {'processed': True, 'action': 'tested'})
        if not success:
            print("❌ Failed to update test email")
            return False
        
        print("✅ Test email updated successfully")
        
        # Scan emails
        emails = db.scan_emails()
        if not emails:
            print("❌ No emails found in scan")
            return False
        
        print("✅ Email scan working successfully")
        
        # Clean up test data
        # (In a real implementation, you might want to add delete methods)
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_config():
    """Test configuration loading."""
    print("🧪 Testing configuration...")
    
    # Add daemon-service to path
    daemon_dir = Path("daemon-service")
    if not daemon_dir.exists():
        print("❌ daemon-service directory not found")
        return False
    
    sys.path.insert(0, str(daemon_dir))
    
    try:
        import config_reader
        
        # Test config values
        database_path = getattr(config_reader, 'DATABASE_PATH', None)
        if not database_path:
            print("❌ DATABASE_PATH not found in config")
            return False
        
        print(f"✅ DATABASE_PATH: {database_path}")
        
        lookback_days = getattr(config_reader, 'LOOKBACK_DAYS', None)
        if lookback_days is None:
            print("❌ LOOKBACK_DAYS not found in config")
            return False
        
        print(f"✅ LOOKBACK_DAYS: {lookback_days}")
        
        # Test secrets loading
        host = getattr(config_reader, 'HOST', None)
        if not host:
            print("❌ HOST not found in config")
            return False
        
        print(f"✅ HOST: {host}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_imports():
    """Test that all required modules can be imported."""
    print("🧪 Testing imports...")
    
    # Add daemon-service to path
    daemon_dir = Path("daemon-service")
    if not daemon_dir.exists():
        print("❌ daemon-service directory not found")
        return False
    
    sys.path.insert(0, str(daemon_dir))
    
    modules_to_test = [
        'database',
        'config_reader',
        'filter_utils',
        'ai_processor',
    ]
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ {module_name} imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import {module_name}: {e}")
            return False
    
    return True

def main():
    """Main test function."""
    print("🧪 dMail SQLite Setup Test")
    print("==========================")
    
    # Run all tests
    tests = [
        ("Import Test", test_imports),
        ("Configuration Test", test_config),
        ("Database Test", test_database),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
            failed += 1
    
    print(f"\n📊 Test Results:")
    print(f"✅ Passed: {passed}")   
    print(f"❌ Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Your dMail setup is working correctly.")
        return True
    else:
        print(f"\n💥 {failed} test(s) failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 