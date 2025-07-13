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
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Email Draft</h2>
        <div className="subject">{email.subject}</div>
        <textarea
          rows={10}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="modal-actions">
          <button onClick={handleSend}>Send</button>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
