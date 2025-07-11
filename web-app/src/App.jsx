import { useEffect, useState } from 'react';
import './App.css';

function App() {
  const [emails, setEmails] = useState([]);

  useEffect(() => {
    fetch('/api/emails')
      .then((res) => res.json())
      .then((data) => setEmails(data))
      .catch((err) => console.error('Failed to fetch emails', err));
  }, []);

  return (
    <div className="app">
      <header className="header">
        <h1>dMail</h1>
        <div className="profile">
          <img className="avatar" src="/vite.svg" alt="Profile" />
          <span className="name">John Doe</span>
        </div>
      </header>
      <main className="email-list">
        {emails.map((email) => (
          <div key={email.id} className="email-item">
            <div className="subject">{email.subject}</div>
            <div className="meta">
              <span className="from">{email.from}</span>
              <span className="timestamp">
                {new Date(email.timestamp * 1000).toLocaleString()}
              </span>
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}

export default App;
