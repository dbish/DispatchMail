import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            try:
                # Try to import config_reader (when running from API context)
                import sys
                import os
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web-app', 'api'))
                from config_reader import DATABASE_PATH
                db_path = DATABASE_PATH
            except ImportError:
                # Fallback for setup script and other contexts
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dmail.db')
        
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
                    tags TEXT,
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
                    research_prompt TEXT,
                    writing_prompt TEXT,
                    processing_prompt TEXT,
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
                    (message_id, subject, body, full_body, html, from_, to_, date, processed, state, drafted_response, sent_response, sent_date, sent_to, sent_subject, sent_body, tags, account)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                        email_data['message_id'] or '',
                        email_data['subject'] or '',
                        email_data['body'] or '',
                        email_data['full_body'] or '',
                        email_data['html'] or '',
                        email_data['from_'] or '',
                        email_data['to_'] or '',
                        email_data['date'] or '',
                        email_data['processed'] or False,
                        email_data['state'] or '',
                        email_data['drafted_response'] or '',
                        email_data['sent_response'] or '',
                        email_data['sent_date'] or '',
                        email_data['sent_to'] or '',
                        email_data['sent_subject'] or '',
                        email_data['sent_body'] or '',
                        email_data['tags'] or '',
                        account
                ))
                
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            print(f"Error storing email: {e}")
            return False

    def bulk_delete_emails(self, message_ids: List[str], account: str) -> bool:
        """Bulk delete emails from the database."""
        try:
            with self.lock:
                conn = self.get_connection()
                cursor = conn.cursor()
                for message_id in message_ids:
                    cursor.execute('DELETE FROM emails WHERE message_id = ? AND account = ?', (message_id, account))
                conn.commit()
                conn.close()
            return True
        except Exception as e:
            print(f"Error deleting emails: {e}")

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
                        email['tags'] or '',
                        account
                    ))
                # Execute the bulk insert
                try:
                    cursor.executemany('''
                        INSERT OR REPLACE INTO emails 
                        (message_id, subject, body, full_body, html, from_, to_, date, processed, state, drafted_response, sent_response, sent_date, sent_to, sent_subject, sent_body, tags, account)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', values)
                except Exception as e:
                    print(f"Error executing bulk insert: {e}")
                    print(f"Values: {values}")
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
    
    def save_prompt(self, user: str, prompt_type: str, prompt: str) -> bool:
        """Store a prompt for a user."""
        print(f"Saving {prompt_type} prompt: {prompt} to db for user {user}")
        field_name = f"{prompt_type}_prompt"
        self.put_metadata(user, {field_name: prompt})
        print('saved prompt')

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
                        'research_prompt': existing[3] or '',
                        'writing_prompt': existing[4] or '',
                        'processing_prompt': existing[5] or '',
                        'rules': existing[6] or ''
                    }
                    # Update only the fields provided in the data parameter
                    existing_data.update(data)
                    final_data = existing_data
                else:
                    # No existing data, use provided data with empty defaults
                    final_data = {
                        'data': data.get('data', ''),
                        'last_processed': data.get('last_processed', ''),
                        'research_prompt': data.get('research_prompt', ''),
                        'writing_prompt': data.get('writing_prompt', ''),
                        'processing_prompt': data.get('processing_prompt', ''),
                        'rules': data.get('rules', '')
                    }

                cursor.execute('''
                    INSERT OR REPLACE INTO metadata 
                    (user, data, last_processed, research_prompt, writing_prompt, processing_prompt, rules, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user,
                    final_data['data'],
                    final_data['last_processed'],
                    final_data['research_prompt'],
                    final_data['writing_prompt'],
                    final_data['processing_prompt'],
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