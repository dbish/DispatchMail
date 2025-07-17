import { useState, useEffect } from 'react';
import './EmailDraftModal.css';

export default function EmailDraftModal({ isOpen, onClose, email, onSend }) {
  const [text, setText] = useState('');
  const [promptText, setPromptText] = useState('');
  const [isAiPanelExpanded, setIsAiPanelExpanded] = useState(false);

  useEffect(() => {
    if (email) {
      setText(email.draft || '');
    }
  }, [email]);

  if (!isOpen || !email) return null;

  const handleSend = () => {
    onSend(text);
  };

  const formatEmailBody = (body) => {
    if (!body) return '';
    return body.replace(/<[^>]*>/g, '').trim();
  };

  const toggleAiPanel = () => {
    setIsAiPanelExpanded(!isAiPanelExpanded);
  };

  const handleQuickPrompt = (prompt) => {
    setPromptText(prompt);
    // Auto-expand if collapsed
    if (!isAiPanelExpanded) {
      setIsAiPanelExpanded(true);
    }
  };

  return (
    <div className="email-draft-overlay" onClick={onClose}>
      <div className="email-draft-modal" onClick={(e) => e.stopPropagation()}>
        {/* Minimal Header */}
        <div className="email-draft-header">
          <div className="email-draft-subject">
            <span className="subject-label">Re:</span>
            <span className="subject-text">{email.subject}</span>
          </div>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/>
            </svg>
          </button>
        </div>

        {/* Main Content */}
        <div className="email-draft-content">
          {/* Main Email Area */}
          <div className="email-main-area">
            {/* Email Thread */}
            <div className="email-thread">
              {/* Original Email */}
              <div className="email-message original">
                <div className="message-header">
                  <div className="sender-info">
                    <span className="sender">{email.from}</span>
                    <span className="timestamp">{new Date(email.date || new Date()).toLocaleString()}</span>
                  </div>
                </div>
                <div className="message-body">
                  {formatEmailBody(email.body)}
                </div>
              </div>
            </div>

            {/* Draft Compose Area */}
            <div className="draft-compose-area">
              <div className="compose-header">
                <span className="compose-label">Your Response</span>
                <div className="compose-actions">
                  <button 
                    className="ai-toggle-btn" 
                    onClick={toggleAiPanel}
                    aria-label={isAiPanelExpanded ? "Hide AI Assistant" : "Show AI Assistant"}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm6.5-.25A.75.75 0 0 1 7.25 7h1.5a.75.75 0 0 1 .75.75v2.75h.25a.75.75 0 0 1 0 1.5h-2a.75.75 0 0 1 0-1.5h.25V8.5H7.25a.75.75 0 0 1-.75-.75ZM8 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"/>
                    </svg>
                    AI Assistant
                  </button>
                </div>
              </div>
              
              <div className="compose-content">
                <textarea
                  className="draft-textarea"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Write your response..."
                />
              </div>

              {/* Seamless Action Bar */}
              <div className="compose-footer">
                <div className="compose-footer-left">
                  <button 
                    className="quick-action-btn"
                    onClick={() => handleQuickPrompt("Make this response more professional")}
                  >
                    More Professional
                  </button>
                  <button 
                    className="quick-action-btn"
                    onClick={() => handleQuickPrompt("Make this response shorter and more concise")}
                  >
                    Make Shorter
                  </button>
                  <button 
                    className="quick-action-btn"
                    onClick={() => handleQuickPrompt("Add a clear call to action")}
                  >
                    Add CTA
                  </button>
                </div>
                <div className="compose-footer-right">
                  <button className="send-btn" onClick={handleSend} disabled={!text.trim()}>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M1.724 1.053a.5.5 0 0 1 .6-.08l13 6.5a.5.5 0 0 1 0 .894l-13 6.5a.5.5 0 0 1-.724-.447L2.382 8 1.6 1.5a.5.5 0 0 1 .124-.447Z"/>
                    </svg>
                    Send
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Collapsible AI Panel */}
          <div className={`ai-prompt-panel ${isAiPanelExpanded ? 'expanded' : 'collapsed'}`}>
            <div className="ai-panel-content">
              <div className="prompt-section">
                <div className="ai-header">
                  <h3>AI Assistant</h3>
                  <button 
                    className="panel-collapse-btn"
                    onClick={toggleAiPanel}
                    aria-label="Collapse AI panel"
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M12.78 5.22a.749.749 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.06 0L3.22 6.28a.749.749 0 1 1 1.06-1.06L8 8.939l3.72-3.719a.749.749 0 0 1 1.06 0Z"/>
                    </svg>
                  </button>
                </div>
                
                <textarea
                  className="prompt-textarea"
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  placeholder="Describe how you'd like to improve your response..."
                  rows={4}
                />
                <button className="prompt-btn">Improve Draft</button>
              </div>
              
              <div className="prompt-suggestions">
                <h4>Quick Improvements</h4>
                <button 
                  className="suggestion-btn"
                  onClick={() => setPromptText("Make this response more professional and formal")}
                >
                  More Professional
                </button>
                <button 
                  className="suggestion-btn"
                  onClick={() => setPromptText("Make this response shorter and more concise")}
                >
                  Make Shorter
                </button>
                <button 
                  className="suggestion-btn"
                  onClick={() => setPromptText("Add a clear call to action to this response")}
                >
                  Add Call to Action
                </button>
                <button 
                  className="suggestion-btn"
                  onClick={() => setPromptText("Make this response more friendly and approachable")}
                >
                  More Friendly
                </button>
                <button 
                  className="suggestion-btn"
                  onClick={() => setPromptText("Fix any grammar or spelling issues")}
                >
                  Fix Grammar
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
