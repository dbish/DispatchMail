import { useState, useEffect } from 'react';
import './EmailModals.css';
import SenderResearchModal from './SenderResearchModal.jsx';

// Function to clean HTML email content and remove excessive whitespace
function cleanEmailHtml(html) {
  if (!html) return '';
  
  let cleaned = html;
  
  // If html is an array (like in your data), join it
  if (Array.isArray(html)) {
    cleaned = html.join('');
  }
  
  // Remove elements that are just whitespace
  cleaned = cleaned.replace(/<(\w+)[^>]*>\s*<\/\1>/g, '');
  
  // Remove excessive whitespace between tags
  cleaned = cleaned.replace(/>\s+</g, '><');
  
  // Remove multiple consecutive line breaks
  cleaned = cleaned.replace(/(<br\s*\/?>){3,}/gi, '<br><br>');
  
  // Remove empty paragraphs and divs with just whitespace
  cleaned = cleaned.replace(/<(p|div)[^>]*>\s*<\/(p|div)>/gi, '');
  
  // Remove multiple consecutive whitespace
  cleaned = cleaned.replace(/\s{3,}/g, ' ');
  
  // Clean up table cells with just whitespace
  cleaned = cleaned.replace(/<(td|th)[^>]*>\s*<\/(td|th)>/gi, '');
  
  return cleaned;
}

export default function ProcessedEmailModal({ isOpen, onClose, email, onSend }) {
  const [systemPrompt, setSystemPrompt] = useState('');
  const [draftPrompt, setDraftPrompt] = useState('');
  const [llmPrompt, setLlmPrompt] = useState('');
  const [emailDraft, setEmailDraft] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isSettingsPanelExpanded, setIsSettingsPanelExpanded] = useState(false);
  const [showResearchModal, setShowResearchModal] = useState(false);

  useEffect(() => {
    if (email && isOpen) {
      setEmailDraft(email.drafted_response || '');
      setLlmPrompt(email.llm_prompt || 'No LLM prompt available');
      
      fetch('/api/custom_prompt?type=processing')
        .then((res) => res.json())
        .then((data) => setSystemPrompt(data.prompt || ''))
        .catch(() => setSystemPrompt(''));
        
      fetch('/api/custom_prompt?type=writing')
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
  
  const isSentEmail = email.action === 'sent';

  // Extract sender information
  const extractSenderInfo = () => {
    const from = email.from || '';
    
    // Handle array structure: [['Name', 'email@domain.com']]
    if (Array.isArray(from) && from.length > 0) {
      const senderData = from[0];
      if (Array.isArray(senderData) && senderData.length >= 2) {
        return {
          senderEmail: senderData[1],
          senderName: senderData[0]
        };
      }
    }
    
    // Fallback to string parsing if not array format
    const fromString = typeof from === 'string' ? from : String(from);
    const emailMatch = fromString.match(/<(.+?)>/);
    const nameMatch = fromString.match(/^(.+?)\s*</);
    
    const senderEmail = emailMatch ? emailMatch[1] : fromString;
    const senderName = nameMatch ? nameMatch[1].trim() : '';
    
    return { senderEmail, senderName };
  };

  const { senderEmail, senderName } = extractSenderInfo();

  return (
    <>
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal awaiting-human-modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <div className="email-subject">
              <span className="subject-label">Re:</span>
              <span className="subject-text">{email.subject}</span>
            </div>
            <button className="close-btn" onClick={onClose} aria-label="Close">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/>
              </svg>
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
                  <div className="message-body">
                    <div dangerouslySetInnerHTML={{ __html: cleanEmailHtml(email.html) }} />
                  </div>
                </div>
              </div>
              
              <div className="draft-compose-area">
                <div className="compose-header">
                  <span className="compose-label">{isSentEmail ? 'Sent Response' : 'Generated Response'}</span>
                  <div className="compose-actions">
                    <button 
                      className="research-sender-btn"
                      onClick={() => setShowResearchModal(true)}
                      title="Research Sender"
                    >
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/>
                      </svg>
                      Research Sender
                    </button>
                  </div>
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
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M12.78 5.22a.749.749 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.06 0L3.22 6.28a.749.749 0 1 1 1.06-1.06L8 8.939l3.72-3.719a.749.749 0 0 1 1.06 0Z"/>
                      </svg>
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
                <button className="quick-action-btn" onClick={handleGenerate} disabled={isGenerating || isSending}>
                  {isGenerating ? 'Generating...' : 'Generate Draft'}
                </button>
              )}
            </div>
            <div className="compose-footer-right">
              <button className="settings-toggle-btn" onClick={toggleSettingsPanel} aria-label={isSettingsPanelExpanded ? "Hide Settings" : "Show Settings"}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 4.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7ZM8 1a.75.75 0 0 1 .75.75v.75a.75.75 0 0 1-1.5 0V1.75A.75.75 0 0 1 8 1Zm0 12a.75.75 0 0 1 .75.75v.75a.75.75 0 0 1-1.5 0v-.75A.75.75 0 0 1 8 13Zm5.657-10.243a.75.75 0 0 1 0 1.061l-.53.53a.75.75 0 0 1-1.061-1.061l.53-.53a.75.75 0 0 1 1.061 0Zm-9.9 9.9a.75.75 0 0 1 0 1.061l-.53.53a.75.75 0 0 1-1.061-1.061l.53-.53a.75.75 0 0 1 1.061 0ZM15 8a.75.75 0 0 1-.75.75h-.75a.75.75 0 0 1 0-1.5h.75A.75.75 0 0 1 15 8ZM3 8a.75.75 0 0 1-.75.75H1.5a.75.75 0 0 1 0-1.5h.75A.75.75 0 0 1 3 8Zm10.243 5.657a.75.75 0 0 1-1.061 0l-.53-.53a.75.75 0 0 1 1.061-1.061l.53.53a.75.75 0 0 1 0 1.061Zm-9.9-9.9a.75.75 0 0 1-1.061 0l-.53-.53a.75.75 0 0 1 1.061-1.061l.53.53a.75.75 0 0 1 0 1.061Z"/>
                </svg>
                Settings
              </button>
              {!isSentEmail && (
                <button className="send-btn" onClick={handleSend} disabled={isSending || !emailDraft.trim()}>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M1.724 1.053a.5.5 0 0 1 .6-.08l13 6.5a.5.5 0 0 1 0 .894l-13 6.5a.5.5 0 0 1-.724-.447L2.382 8 1.6 1.5a.5.5 0 0 1 .124-.447Z"/>
                  </svg>
                  {isSending ? 'Sending...' : 'Send Email'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
      
      <SenderResearchModal
        isOpen={showResearchModal}
        onClose={() => setShowResearchModal(false)}
        senderEmail={senderEmail}
        senderName={senderName}
      />
    </>
  );
} 