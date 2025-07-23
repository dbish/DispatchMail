import { useState, useEffect } from 'react';
import './ThinDraftingSettingsModal.css';

function ThinDraftingSettingsModal({ isOpen, onClose, onResetSuccess }) {
  const [draftPrompt, setDraftPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    fetch('/api/custom_prompt?type=writing')
      .then((res) => res.json())
      .then((data) => {
        setDraftPrompt(data.prompt || '');
      })
      .catch((err) => console.error('Failed to fetch draft prompt', err));
  }, [isOpen]);

  if (!isOpen) return null;

  const saveDraftPrompt = async () => {
    setIsLoading(true);
    setMessage('');
    
    try {
      const response = await fetch('/api/custom_prompt?type=writing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: draftPrompt }),
      });
      
      if (response.ok) {
        setMessage('Draft prompt saved successfully!');
        if (onResetSuccess) {
          onResetSuccess();
        }
      } else {
        setMessage('Failed to save draft prompt. Please try again.');
      }
    } catch {
      setMessage('Error saving draft prompt. Please try again.');
    } finally {
      setIsLoading(false);
      setTimeout(() => {
        setMessage('');
      }, 5000);
    }
  };

  return (
    <div className="thin-modal-overlay" onClick={onClose}>
      <div className="thin-modal" onClick={(e) => e.stopPropagation()}>
        <div className="thin-modal-header">
          <h2>Drafting Settings</h2>
          <button className="thin-close-btn" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/>
            </svg>
          </button>
        </div>
        
        <div className="thin-modal-content">
          <p className="thin-description">
            Configure how the AI generates email drafts. This prompt instructs the AI on the tone, style, and approach to use when creating responses.
          </p>
          
          {message && (
            <div className={`thin-message ${message.includes('Error') || message.includes('Failed') ? 'error' : 'success'}`}>
              {message}
            </div>
          )}
          
          <div className="thin-draft-prompt-container">
            <label className="thin-prompt-label">Draft Generation Instructions</label>
            <textarea
              value={draftPrompt}
              onChange={(e) => setDraftPrompt(e.target.value)}
              placeholder="Enter instructions for how the AI should generate email drafts..."
              disabled={isLoading}
              className="thin-prompt-textarea"
              rows={8}
            />
            <p className="thin-prompt-help">
              Examples: "Write concise, professional responses" or "Use a friendly, casual tone"
            </p>
          </div>
        </div>
        
        <div className="thin-modal-footer">
          <div className="thin-footer-right">
            <button 
              onClick={onClose} 
              disabled={isLoading}
              className="thin-cancel-btn"
            >
              Cancel
            </button>
            <button 
              onClick={saveDraftPrompt} 
              disabled={isLoading}
              className="thin-save-btn"
            >
              {isLoading ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ThinDraftingSettingsModal; 