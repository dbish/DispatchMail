import { useState, useEffect } from 'react';
import './EmailReadingModal.css';

export default function EmailReadingModal({ isOpen, onClose, email, onSend, onDelete, onRerun }) {
  const [draftPrompt, setDraftPrompt] = useState('');
  const [llmPrompt, setLlmPrompt] = useState('');
  const [emailDraft, setEmailDraft] = useState('');
  const [isRerunning, setIsRerunning] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isSettingsPanelExpanded, setIsSettingsPanelExpanded] = useState(false);

  useEffect(() => {
    if (email && isOpen) {
      setEmailDraft(email.draft || '');
      setLlmPrompt(email.llm_prompt || 'No LLM prompt available');
      fetch('/api/draft_prompt')
        .then((res) => res.json())
        .then((data) => setDraftPrompt(data.prompt || ''))
        .catch(() => {});
    }
  }, [email, isOpen]);

  if (!isOpen || !email) return null;

  const handleRerun = async () => {
    setIsRerunning(true);
    try {
      if (draftPrompt && draftPrompt.trim()) {
        await fetch('/api/draft_prompt', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: draftPrompt }),
        });
      }
      const response = await fetch('/api/reprocess_single_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: email.message_id }),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.new_draft) setEmailDraft(data.new_draft);
        if (data.llm_prompt) setLlmPrompt(data.llm_prompt);
        if (onRerun) onRerun(email.message_id);
      } else {
        console.error('Failed to rerun email processing');
      }
    } catch (error) {
      console.error('Error rerunning email processing:', error);
    } finally {
      setIsRerunning(false);
    }
  };

  const handleSend = async () => {
    setIsSending(true);
    try {
      await onSend(emailDraft);
    } catch (error) {
      console.error('Error sending email:', error);
      setIsSending(false);
    }
  };

  const handleDelete = () => onDelete(email.message_id);
  const toggleSettingsPanel = () => setIsSettingsPanelExpanded(!isSettingsPanelExpanded);
  const formatEmailBody = (body) => body ? body.replace(/<[^>]*>/g, '').trim() : '';

  return (
    <div className="reading-modal-overlay" onClick={onClose}>
      <div className="reading-modal" onClick={(e) => e.stopPropagation()}>
        <div className="reading-modal-header">
          <div className="reading-email-subject">
            <span className="reading-subject-label">Re:</span>
            <span className="reading-subject-text">{email.subject}</span>
          </div>
          <button className="reading-close-btn" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/>
            </svg>
          </button>
        </div>
        
        <div className="reading-modal-content">
          <div className="reading-email-main-area">
            <div className="reading-email-thread">
              <div className="reading-email-message original">
                <div className="reading-message-header">
                  <div className="reading-sender-info">
                    <span className="reading-sender">{email.from}</span>
                    <span className="reading-timestamp">{new Date(email.date || new Date()).toLocaleString()}</span>
                  </div>
                </div>
                <div className="reading-message-body">{formatEmailBody(email.body)}</div>
              </div>
            </div>
            
            <div className="reading-draft-compose-area">
              <div className="reading-compose-header">
                <span className="reading-compose-label">Generated Response</span>
              </div>
              <div className="reading-compose-content">
                <textarea 
                  className="reading-draft-textarea" 
                  value={emailDraft} 
                  onChange={(e) => setEmailDraft(e.target.value)} 
                  placeholder="Generated email draft will appear here..." 
                />
              </div>
            </div>
          </div>
          
          <div className={`reading-settings-panel ${isSettingsPanelExpanded ? 'expanded' : 'collapsed'}`}>
            <div className="reading-settings-panel-content">
              <div className="reading-settings-section">
                <div className="reading-settings-header">
                  <h3>AI Settings</h3>
                  <button className="reading-panel-collapse-btn" onClick={toggleSettingsPanel} aria-label="Collapse settings panel">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M12.78 5.22a.749.749 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.06 0L3.22 6.28a.749.749 0 1 1 1.06-1.06L8 8.939l3.72-3.719a.749.749 0 0 1 1.06 0Z"/>
                    </svg>
                  </button>
                </div>
                <div className="reading-settings-field">
                  <label>Drafting Instructions</label>
                  <textarea 
                    className="reading-settings-textarea" 
                    value={draftPrompt} 
                    onChange={(e) => setDraftPrompt(e.target.value)} 
                    placeholder="Customize how the AI should write responses..." 
                    rows={4} 
                  />
                </div>
                <div className="reading-settings-field">
                  <label>Actual LLM Prompt (Debug)</label>
                  <textarea 
                    className="reading-settings-textarea readonly" 
                    value={llmPrompt} 
                    readOnly 
                    placeholder="The actual content sent to the LLM..." 
                    rows={6} 
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div className="reading-modal-footer">
          <div className="reading-compose-footer-left">
            <button 
              className="reading-quick-action-btn" 
              onClick={handleRerun} 
              disabled={isRerunning || isSending}
            >
              {isRerunning ? 'Regenerating...' : 'Regenerate'}
            </button>
            <button 
              className="reading-quick-action-btn reading-delete-action" 
              onClick={handleDelete} 
              disabled={isSending}
            >
              Delete Draft
            </button>
          </div>
          <div className="reading-compose-footer-right">
            <button 
              className="reading-settings-toggle-btn" 
              onClick={toggleSettingsPanel} 
              aria-label={isSettingsPanelExpanded ? "Hide Settings" : "Show Settings"}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 4.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7ZM8 1a.75.75 0 0 1 .75.75v.75a.75.75 0 0 1-1.5 0V1.75A.75.75 0 0 1 8 1Zm0 12a.75.75 0 0 1 .75.75v.75a.75.75 0 0 1-1.5 0v-.75A.75.75 0 0 1 8 13Zm5.657-10.243a.75.75 0 0 1 0 1.061l-.53.53a.75.75 0 0 1-1.061-1.061l.53-.53a.75.75 0 0 1 1.061 0Zm-9.9 9.9a.75.75 0 0 1 0 1.061l-.53.53a.75.75 0 0 1-1.061-1.061l.53-.53a.75.75 0 0 1 1.061 0ZM15 8a.75.75 0 0 1-.75.75h-.75a.75.75 0 0 1 0-1.5h.75A.75.75 0 0 1 15 8ZM3 8a.75.75 0 0 1-.75.75H1.5a.75.75 0 0 1 0-1.5h.75A.75.75 0 0 1 3 8Zm10.243 5.657a.75.75 0 0 1-1.061 0l-.53-.53a.75.75 0 0 1 1.061-1.061l.53.53a.75.75 0 0 1 0 1.061Zm-9.9-9.9a.75.75 0 0 1-1.061 0l-.53-.53a.75.75 0 0 1 1.061-1.061l.53.53a.75.75 0 0 1 0 1.061Z"/>
              </svg>
              Settings
            </button>
            <button 
              className="reading-send-btn" 
              onClick={handleSend} 
              disabled={isSending || !emailDraft.trim()}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M1.724 1.053a.5.5 0 0 1 .6-.08l13 6.5a.5.5 0 0 1 0 .894l-13 6.5a.5.5 0 0 1-.724-.447L2.382 8 1.6 1.5a.5.5 0 0 1 .124-.447Z"/>
              </svg>
              {isSending ? 'Sending...' : 'Send Email'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
} 