import { useEffect, useState } from 'react';
import './App.css';
import DraftingSettingsModal from './DraftingSettingsModal.jsx';
import WhitelistSettingsModal from './WhitelistSettingsModal.jsx';
import EmailDraftModal from './EmailDraftModal.jsx';
import Onboarding from './Onboarding.jsx';

function App() {
  const [currentUser, setCurrentUser] = useState(
    localStorage.getItem('userEmail') || ''
  );
  const [emails, setEmails] = useState([]);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [showDraftModal, setShowDraftModal] = useState(false);
  const [showWhitelistModal, setShowWhitelistModal] = useState(false);
  const [theme, setTheme] = useState(
    localStorage.getItem('theme') || 'dark'
  );
  const [draftPrompts, setDraftPrompts] = useState([
    {
      name: 'default',
      prompt: 'Provide concise and polite email drafts.',
    },
  ]);
  const [selectedDraft, setSelectedDraft] = useState(null);

  useEffect(() => {
    if (!currentUser) return;
    fetch('/api/emails')
      .then((res) => res.json())
      .then((data) => setEmails(data))
      .catch((err) => console.error('Failed to fetch emails', err));
  }, [currentUser]);

  useEffect(() => {
    fetch('/api/draft_prompt')
      .then((res) => res.json())
      .then((data) =>
        setDraftPrompts([{ name: 'default', prompt: data.prompt || '' }])
      )
      .catch(() => {});
  }, []);

  useEffect(() => {
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(theme === 'light' ? 'theme-light' : 'theme-dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  const unprocessedCount = emails.filter((e) => !e.processed).length;

  if (!currentUser) {
    return (
      <div className="app">
        <Onboarding onComplete={setCurrentUser} />
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <h1>dMail</h1>
        <div className="profile">
          <img className="avatar" src="/vite.svg" alt="Profile" />
          <span className="name">John Doe</span>
          <button onClick={() => setShowDraftModal(true)}>Drafting Settings</button>
          <button onClick={() => setShowWhitelistModal(true)}>Whitelist Settings</button>
          <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
            {theme === 'light' ? 'Dark' : 'Light'} Theme
          </button>
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
            <li>draftemail</li>
          </ul>
        </aside>
        <section className="right-panel">
          <h2>Inbox ({unprocessedCount})</h2>
          <div className="email-list">
            {emails.map((email) => (
              <div
                key={email.id}
                className={`email-item ${email.processed ? 'processed' : 'unprocessed'}`}
              >
                <div className="subject">{email.subject}</div>
                <div className="meta">
                  <span className="from">{email.from}</span>
                  <span className="timestamp">
                    {new Date(email.date).toLocaleString()}
                  </span>
                </div>
                {email.processed && (
                  <div className="email-action">Action: {email.action || 'none'}</div>
                )}
              </div>
            ))}
          </div>
          <h2>Awaiting Human</h2>
          <div className="email-list">
            {emails
              .filter((e) => e.draft && !e.processed)
              .map((email) => (
                <div
                  key={email.id}
                  className="email-item"
                  onClick={() => setSelectedDraft(email)}
                >
                  <div className="subject">{email.subject}</div>
                  <div className="meta">
                    <span className="from">{email.from}</span>
                    <span className="timestamp">
                      {new Date(email.date).toLocaleString()}
                    </span>
                  </div>
                </div>
              ))}
          </div>
        </section>
      </div>
      {showDraftModal && (
        <DraftingSettingsModal
          isOpen={showDraftModal}
          onClose={() => setShowDraftModal(false)}
          prompts={draftPrompts}
          setPrompts={setDraftPrompts}
        />
      )}
      {showWhitelistModal && (
        <WhitelistSettingsModal
          isOpen={showWhitelistModal}
          onClose={() => setShowWhitelistModal(false)}
        />
      )}
      {selectedDraft && (
        <EmailDraftModal
          isOpen={!!selectedDraft}
          onClose={() => setSelectedDraft(null)}
          email={selectedDraft}
          onSend={async (text) => {
            await fetch('/api/send', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: selectedDraft.id, draft: text }),
            });
            setSelectedDraft(null);
            const data = await (await fetch('/api/emails')).json();
            setEmails(data);
          }}
        />
      )}
    </div>
  );
}

export default App;
