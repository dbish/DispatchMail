import { useState, useEffect } from 'react';
import './App.css';

export default function UserSelector({ onComplete, onAddNew }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await fetch('/api/users');
      if (response.ok) {
        const userData = await response.json();
        setUsers(userData);
      } else {
        setError('Failed to fetch users');
      }
    } catch (err) {
      setError('Failed to connect to server');
    } finally {
      setLoading(false);
    }
  };

  const handleUserSelect = (userEmail) => {
    localStorage.setItem('userEmail', userEmail);
    onComplete(userEmail);
  };

  if (loading) {
    return (
      <div className="user-selector">
        <h2>Loading...</h2>
      </div>
    );
  }

  if (error) {
    return (
      <div className="user-selector">
        <h2>Error</h2>
        <p>{error}</p>
        <button onClick={fetchUsers}>Retry</button>
      </div>
    );
  }

  return (
    <div className="user-selector">
      <h2>Select Email Account</h2>
      <p>Choose an email account to access your inbox:</p>
      
      <div className="user-list">
        {users.map((user) => (
          <div 
            key={user.user} 
            className="user-item"
            onClick={() => handleUserSelect(user.user)}
          >
            <div className="user-avatar">📧</div>
            <div className="user-info">
              <div className="user-email">{user.user}</div>
              <div className="user-host">{user.host}</div>
              {user.last_processed && (
                <div className="user-last-processed">
                  Last processed: {new Date(user.last_processed).toLocaleString()}
                </div>
              )}
            </div>
            <div className="user-select-arrow">→</div>
          </div>
        ))}
      </div>

      <div className="user-actions">
        <button 
          className="add-new-btn"
          onClick={onAddNew}
        >
          Add New Email Account
        </button>
      </div>
    </div>
  );
} 