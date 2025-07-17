import { useState, useEffect } from 'react';
import './DraftingSettingsModal.css';

export default function ProcessedEmailModal({ isOpen, onClose, email, onSend }) {
  const [systemPrompt, setSystemPrompt] = useState('');
  const [draftPrompt, setDraftPrompt] = useState('');
  const [llmPrompt, setLlmPrompt] = useState('');
  const [emailDraft, setEmailDraft] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isSettingsPanelExpanded, setIsSettingsPanelExpanded] = useState(false);

  useEffect(() => {
    if (email && isOpen) {
      setEmailDraft(email.draft || '');
      setLlmPrompt(email.llm_prompt || 'No LLM prompt available');
      
      fetch('/api/prompt')
        .then((res) => res.json())
        .then((data) => setSystemPrompt(data.prompt || ''))
        .catch(() => setSystemPrompt(''));
        
      fetch('/api/draft_prompt')
        .then((res) => res.json())
        .then((data) => setDraftPrompt(data.prompt || ''))
        .catch(() => setDraftPrompt(''));
    }
  }, [email, isOpen]);

  if (!isOpen || !email) return null;

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const response = await fetch('/api/rerun_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email_id: email.message_id,
          system_prompt: systemPrompt,
          draft_prompt: draftPrompt
        }),
      });
      
      if (response.ok) {
        const data = await response.json();
        setEmailDraft(data.draft || '');
        setLlmPrompt(data.llm_prompt || 'No LLM prompt available');
      } else {
        console.error('Failed to generate draft:', response.status);
      }
    } catch (error) {
      console.error('Error generating draft:', error);
    } finally {
      setIsGenerating(false);
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

  const toggleSettingsPanel = () => {
    setIsSettingsPanelExpanded(!isSettingsPanelExpanded);
  };

  const formatEmailBody = (body) => {
    if (!body) return '';
    return body.replace(/<[^>]*>/g, '').trim();
  };
  
  const isSentEmail = email.action === 'sent';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal awaiting-human-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="email-subject">
            <span className="subject-label">Re:</span>
            <span className="subject-text">{email.subject}</span>
          </div>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/></svg>
          </button>
        </div>
        
        <div className="modal-content">
          <div className="email-main-area">
            <div className="email-thread">
              <div className="email-message original">
                <div className="message-header">
                  <div className="sender-info">
                    <span className="sender">{email.from}</span>
                    <span className="timestamp">{new Date(email.date || new Date()).toLocaleString()}</span>
                  </div>
                </div>
                <div className="message-body">{formatEmailBody(email.body)}</div>
              </div>
            </div>
            
            <div className="draft-compose-area">
              <div className="compose-header">
                <span className="compose-label">{isSentEmail ? 'Sent Response' : 'Generated Response'}</span>
              </div>
              <div className="compose-content">
                <textarea 
                  className="draft-textarea"
                  value={emailDraft}
                  onChange={(e) => setEmailDraft(e.target.value)}
                  readOnly={isSentEmail}
                  placeholder={isSentEmail ? "No message content available" : "Generated email draft will appear here..."}
                />
              </div>
            </div>
          </div>

          <div className={`settings-panel ${isSettingsPanelExpanded ? 'expanded' : 'collapsed'}`}>
            <div className="settings-panel-content">
              <div className="settings-section">
                <div className="settings-header">
                  <h3>AI Settings</h3>
                  <button className="panel-collapse-btn" onClick={toggleSettingsPanel} aria-label="Collapse settings panel">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M12.78 5.22a.749.749 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.06 0L3.22 6.28a.749.749 0 1 1 1.06-1.06L8 8.939l3.72-3.719a.749.749 0 0 1 1.06 0Z"/></svg>
                  </button>
                </div>
                <div className="settings-field">
                  <label>System Prompt</label>
                  <textarea
                    className="settings-textarea"
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    placeholder="System prompt for AI..."
                    rows={4}
                  />
                </div>
                <div className="settings-field">
                  <label>Drafting Instructions</label>
                  <textarea
                    className="settings-textarea"
                    value={draftPrompt}
                    onChange={(e) => setDraftPrompt(e.target.value)}
                    placeholder="Customize how the AI should write responses..."
                    rows={4}
                  />
                </div>
                <div className="settings-field">
                  <label>Actual LLM Prompt (Debug)</label>
                  <textarea
                    className="settings-textarea readonly"
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
        
        <div className="modal-footer">
          <div className="compose-footer-left">
            {!isSentEmail && (
              <button 
                className="quick-action-btn"
                onClick={handleGenerate}
                disabled={isGenerating || isSending}
              >
                {isGenerating ? 'Regenerating...' : 'Regenerate'}
              </button>
            )}
          </div>
          <div className="compose-footer-right">
            {!isSentEmail && (
              <button 
                className="settings-toggle-btn"
                onClick={toggleSettingsPanel}
                aria-label={isSettingsPanelExpanded ? "Hide Settings" : "Show Settings"}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 4.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7ZM8 1a.75.75 0 0 1 .75.75v.75a.75.75 0 0 1-1.5 0V1.75A.75.75 0 0 1 8 1Zm0 12a.75.75 0 0 1 .75.75v.75a.75.75 0 0 1-1.5 0v-.75A.75.75 0 0 1 8 13Zm5.657-10.243a.75.75 0 0 1 0 1.061l-.53.53a.75.75 0 0 1-1.061-1.061l.53-.53a.75.75 0 0 1 1.061 0Zm-9.9 9.9a.75.75 0 0 1 0 1.061l-.53.53a.75.75 0 0 1-1.061-1.061l.53-.53a.75.75 0 0 1 1.061 0ZM15 8a.75.75 0 0 1-.75.75h-.75a.75.75 0 0 1 0-1.5h.75A.75.75 0 0 1 15 8ZM3 8a.75.75 0 0 1-.75.75H1.5a.75.75 0 0 1 0-1.5h.75A.75.75 0 0 1 3 8Zm10.243 5.657a.75.75 0 0 1-1.061 0l-.53-.53a.75.75 0 0 1 1.061-1.061l.53.53a.75.75 0 0 1 0 1.061Zm-9.9-9.9a.75.75 0 0 1-1.061 0l-.53-.53a.75.75 0 0 1 1.061-1.061l.53.53a.75.75 0 0 1 0 1.061Z"/></svg>
                Settings
              </button>
            )}
            <button 
              className="send-btn" 
              onClick={isSentEmail ? onClose : handleSend} 
              disabled={isSending || (!isSentEmail && !emailDraft.trim())}
            >
              {isSentEmail ? 'Close' : (isSending ? 'Sending...' : 'Send Email')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
} 