import { useState, useEffect } from 'react';
import './DraftingSettingsModal.css';

export default function EmailDraftModal({ isOpen, onClose, email, onSend }) {
  const [text, setText] = useState('');

  useEffect(() => {
    if (email) {
      setText(email.draft || '');
    }
  }, [email]);

  if (!isOpen || !email) return null;

  const handleSend = () => {
    onSend(text);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal sidepanel email-draft-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2>Email Draft</h2>
          <div className="email-info">
            <div className="subject">Subject: {email.subject}</div>
            <div className="from">From: {email.from}</div>
          </div>
        </div>

        <div className="modal-content">
          <div className="left-col">
            <div className="email-display-section">
              <label>Original Email</label>
              <textarea value={email.body || ''} readOnly className="readonly" />
            </div>
            <div className="draft-compose-section">
              <label>Your Response</label>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Write your response..."
              />
            </div>
          </div>
          <div className="right-col" />
        </div>

        <div className="modal-actions">
          <button onClick={handleSend}>Send</button>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
