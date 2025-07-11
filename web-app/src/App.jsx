import { useEffect, useState } from 'react';
import './App.css';

function App() {
  const [emails, setEmails] = useState([]);
  const [systemPrompt, setSystemPrompt] = useState('');

  useEffect(() => {
    fetch('/api/emails')
      .then((res) => res.json())
      .then((data) =>
        setEmails(
          data.map((email) => ({
            ...email,
            processed: false,
          }))
        )
      )
      .catch((err) => console.error('Failed to fetch emails', err));
  }, []);

  const unprocessedCount = emails.filter((e) => !e.processed).length;

  return (
    <div className="app">
      <header className="header">
        <h1>dMail</h1>
        <div className="profile">
          <img className="avatar" src="/vite.svg" alt="Profile" />
          <span className="name">John Doe</span>
        </div>
      </header>
      <div className="main-container">
        <aside className="left-panel">
          <h2>Email Reading Agent System Prompt</h2>
          <textarea
            className="system-input"
            rows={10}
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
          />
          <h3>Available Tools</h3>
          <ul className="tools-list">
            <li>labelemail</li>
            <li>archiveemail</li>
            <li>draftreply</li>
          </ul>
        </aside>
        <section className="right-panel">
          <h2>Inbox ({unprocessedCount})</h2>
          <div className="email-list">
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
          </div>
        </section>
      </div>
    </div>
  );
}

export default App;
