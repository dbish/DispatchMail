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

export default function EmailDraftModal({ isOpen, onClose, email, onSend, onDelete, onRerun }) {
  const [emailDraft, setEmailDraft] = useState('');
  const [isRerunning, setIsRerunning] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [showResearchModal, setShowResearchModal] = useState(false);

  useEffect(() => {
    if (email && isOpen) {
      setEmailDraft(email.draft || '');
    }
  }, [email, isOpen]);

  if (!isOpen || !email) return null;

  const handleRerun = async () => {
    setIsRerunning(true);
    try {
      const response = await fetch('/api/generate_draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_id: email.id }),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.draft) setEmailDraft(data.draft);
        if (onRerun) onRerun(email.id);
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
        <div className="modal" onClick={(e) => e.stopPropagation()}>
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
                  <span className="compose-label">Generated Response</span>
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
                  <textarea className="draft-textarea" value={emailDraft} onChange={(e) => setEmailDraft(e.target.value)} placeholder="Generated email draft will appear here..." />
                </div>
              </div>
            </div>
          </div>
          <div className="modal-footer">
            <div className="compose-footer-left">
              <button className="quick-action-btn" onClick={handleRerun} disabled={isRerunning || isSending}>{isRerunning ? 'Regenerating...' : 'Regenerate'}</button>
              <button className="quick-action-btn delete-action" onClick={handleDelete} disabled={isSending}>Delete Draft</button>
            </div>
            <div className="compose-footer-right">
              <button className="send-btn" onClick={handleSend} disabled={isSending || !emailDraft.trim()}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M1.724 1.053a.5.5 0 0 1 .6-.08l13 6.5a.5.5 0 0 1 0 .894l-13 6.5a.5.5 0 0 1-.724-.447L2.382 8 1.6 1.5a.5.5 0 0 1 .124-.447Z"/></svg>
                {isSending ? 'Sending...' : 'Send Email'}
              </button>
            </div>
          </div>
        </div>
      </div>
      
      {showResearchModal && (
        <SenderResearchModal
          isOpen={showResearchModal}
          onClose={() => setShowResearchModal(false)}
          senderEmail={senderEmail}
          senderName={senderName}
        />
      )}
    </>
  );
}
