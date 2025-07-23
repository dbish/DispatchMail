import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Import here to avoid circular imports
            from config_reader import DATABASE_PATH
            db_path = DATABASE_PATH
        
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_db()
    
    def init_db(self):
        """Initialize the SQLite database with required tables."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create emails table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS emails (
                    message_id TEXT PRIMARY KEY,
                    subject TEXT,
                    body TEXT,
                    full_body TEXT,
                    html TEXT,
                    from_ TEXT,
                    to_ TEXT,
                    date TEXT,
                    processed BOOLEAN DEFAULT FALSE,
                    state TEXT,
                    drafted_response TEXT,
                    sent_response TEXT,
                    sent_date TEXT,
                    sent_to TEXT,
                    sent_subject TEXT,
                    sent_body TEXT,
                    account TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    user TEXT PRIMARY KEY,
                    data TEXT,
                    last_processed TEXT,
                    prompt TEXT,
                    rules TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user TEXT PRIMARY KEY,
                    host TEXT,
                    password TEXT,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
                        
            conn.commit()
            conn.close()
    
    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def dict_factory(self, cursor, row):
        """Convert row to dictionary."""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def reset_emails(self, user: str):
        """Reset all emails for a user."""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM emails WHERE account = ?', (user,))
            conn.commit()
            conn.close()


    # Email operations
    def put_email(self, email_data: Dict[str, Any], account: str) -> bool:
        """Store an email in the database."""
        try:
            with self.lock:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO emails 
                    (message_id, subject, body, full_body, html, from_, to, date, processed, state, drafted_response, sent_response, sent_date, sent_to, sent_subject, sent_body, account)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    email_data.get('message_id', ''),
                    email_data.get('subject', ''),
                    email_data.get('body', ''),
                    email_data.get('full_body', ''),
                    email_data.get('html', ''),
                    email_data.get('from', ''),
                    email_data.get('to', ''),
                    email_data.get('date', ''),
                    email_data.get('processed', False),
                    email_data.get('state', ''),
                    email_data.get('drafted_response', ''),
                    email_data.get('sent_response', ''),
                    email_data.get('sent_date', ''),
                    email_data.get('sent_to', ''),
                    email_data.get('sent_subject', ''),
                    email_data.get('sent_body', ''),
                    account
                ))
                
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            print(f"Error storing email: {e}")
            return False

    def bulk_put_emails(self, emails: List[Dict[str, Any]], account: str) -> bool:
        """Bulk store emails in the database."""
        try:
            with self.lock:
                conn = self.get_connection()
                cursor = conn.cursor()

                # Create a list of tuples for bulk insertion
                values = []
                for email in emails:
                    values.append((
                        email['message_id'] or '',
                        email['subject'] or '',
                        email['body'] or '',
                        email['full_body'] or '',
                        email['html'] or '',
                        email['from_'] or '',
                        email['to_'] or '',
                        email['date'] or '',
                        email['processed'] or False,
                        email['state'] or '',
                        email['drafted_response'] or '',
                        email['sent_response'] or '',
                        email['sent_date'] or '',
                        email['sent_to'] or '',
                        email['sent_subject'] or '',
                        email['sent_body'] or '',
                        account
                    ))
                
                # Execute the bulk insert
                cursor.executemany('''
                    INSERT OR REPLACE INTO emails 
                    (message_id, subject, body, full_body, html, from_, to_, date, processed, state, drafted_response, sent_response, sent_date, sent_to, sent_subject, sent_body, account)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', values)
                
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            print(f"Error storing emails: {e}")
            return False
    
    def get_email(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get an email by message_id."""
        try:
            with self.lock:
                conn = self.get_connection()
                conn.row_factory = self.dict_factory
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM emails WHERE message_id = ?', (message_id,))
                result = cursor.fetchone()
                conn.close()
                return result
        except Exception as e:
            print(f"Error getting email: {e}")
            return None
    
    def scan_emails(self, filter_condition: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Get all emails with optional filtering."""
        try:
            with self.lock:
                conn = self.get_connection()
                conn.row_factory = self.dict_factory
                cursor = conn.cursor()
                
                if filter_condition:
                    # Simple filtering support (can be extended)
                    where_clause = " AND ".join([f"{k} = ?" for k in filter_condition.keys()])
                    cursor.execute(f'SELECT * FROM emails WHERE {where_clause}', tuple(filter_condition.values()))
                else:
                    cursor.execute('SELECT * FROM emails')
                
                results = cursor.fetchall()
                conn.close()
                return results
        except Exception as e:
            print(f"Error scanning emails: {e}")
            return []
    
    def update_email(self, message_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an email record."""
        try:
            with self.lock:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Automatically set updated_at timestamp
                update_data_with_timestamp = update_data.copy()
                update_data_with_timestamp['updated_at'] = datetime.now().isoformat()
                
                set_clause = ", ".join([f"{k} = ?" for k in update_data_with_timestamp.keys()])
                values = list(update_data_with_timestamp.values()) + [message_id]
                
                cursor.execute(f'UPDATE emails SET {set_clause} WHERE message_id = ?', values)
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            print(f"Error updating email: {e}")
            return False
    
    # Metadata operations
    def get_metadata(self, user: str, key: str = None) -> Optional[Any]:
        """Get metadata for a user."""
        try:
            with self.lock:
                conn = self.get_connection()
                conn.row_factory = self.dict_factory
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM metadata WHERE user = ?', (user,))
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    if key:
                        return result.get(key)
                    return result
                return None
        except Exception as e:
            print(f"Error getting metadata: {e}")
            return None
    
    def put_metadata(self, user: str, data: Dict[str, Any]) -> bool:
        """Store metadata for a user."""
        try:
            with self.lock:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # First, get existing metadata to preserve values not being updated
                cursor.execute('SELECT * FROM metadata WHERE user = ?', (user,))
                existing = cursor.fetchone()
                
                if existing:
                    # Merge with existing data, preserving fields not being updated
                    existing_data = {
                        'data': existing[1] or '',
                        'last_processed': existing[2] or '',
                        'prompt': existing[3] or '',
                        'rules': existing[4] or ''
                    }
                    # Update only the fields provided in the data parameter
                    existing_data.update(data)
                    final_data = existing_data
                else:
                    # No existing data, use provided data with empty defaults
                    final_data = {
                        'data': data.get('data', ''),
                        'last_processed': data.get('last_processed', ''),
                        'prompt': data.get('prompt', ''),
                        'rules': data.get('rules', '')
                    }
                
                cursor.execute('''
                    INSERT OR REPLACE INTO metadata 
                    (user, data, last_processed, prompt, rules, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user,
                    final_data['data'],
                    final_data['last_processed'],
                    final_data['prompt'],
                    final_data['rules'],
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            print(f"Error storing metadata: {e}")
            return False
    
    # Users operations
    def get_users(self) -> List[Dict[str, Any]]: 
        """Get all users."""
        try:
            with self.lock:
                conn = self.get_connection()
                conn.row_factory = self.dict_factory
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM users')
                results = cursor.fetchall()
                conn.close()
                return results
        except Exception as e:
            print(f"Error getting users: {e}")
            return []
    
    def put_user(self, user: str, host: str, password: str) -> bool:
        """Store a user account."""
        try:
            with self.lock:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user, host, password, active)
                    VALUES (?, ?, ?, TRUE)
                ''', (user, host, password))
                
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            print(f"Error storing user: {e}")
            return False

# Global database instance
db = DatabaseManager() 