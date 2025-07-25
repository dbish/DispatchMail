import { useState, useEffect } from 'react';
import './EmailReadingModal.css';

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

export default function EmailReadingModal({ isOpen, onClose, email, onSend, onDelete, onRerun }) {
  const [emailDraft, setEmailDraft] = useState('');
  const [isRerunning, setIsRerunning] = useState(false);
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    if (email && isOpen) {
      setEmailDraft(email.draft || '');
    }
  }, [email, isOpen]);

  if (!isOpen || !email) return null;

  const handleRerun = async () => {
    setIsRerunning(true);
    try {
      const response = await fetch('/api/reprocess_single_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: email.message_id }),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.new_draft) setEmailDraft(data.new_draft);
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
                <div className="reading-message-body">
                  <div dangerouslySetInnerHTML={{ __html: cleanEmailHtml(email.html) }} />
                </div>
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