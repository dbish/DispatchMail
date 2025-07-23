import { useState } from 'react';
import './EmailModals.css';

export default function ProcessingModal({ isOpen, onClose, onProcessUnprocessed, onProcessAll }) {
  const [isProcessing, setIsProcessing] = useState(false);

  if (!isOpen) return null;

  const handleProcessUnprocessed = async () => {
    setIsProcessing(true);
    try {
      await onProcessUnprocessed();
    } finally {
      setIsProcessing(false);
    }
  };

  const handleProcessAll = async () => {
    setIsProcessing(true);
    try {
      console.log('Process All Emails - Not yet implemented');
      // This will be a no-op for now as requested
      await onProcessAll();
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal processing-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="email-subject">
            <span className="subject-text">Process Emails</span>
          </div>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/>
            </svg>
          </button>
        </div>
        
        <div className="processing-modal-content">
          <div className="processing-info">
            <h3>Email Processing Options</h3>
            <p>Choose how you would like to process your emails:</p>
            
            <div className="processing-options">
              <div className="processing-option">
                <div className="option-info">
                  <h4>Process Unprocessed Emails</h4>
                  <p>Only process emails that haven't been analyzed yet. This is the recommended option for regular use.</p>
                </div>
                <button 
                  className="processing-btn primary"
                  onClick={handleProcessUnprocessed}
                  disabled={isProcessing}
                >
                  {isProcessing ? 'Processing...' : 'Process Unprocessed'}
                </button>
              </div>
              
              <div className="processing-option">
                <div className="option-info">
                  <h4>Process All Emails</h4>
                  <p>Re-process all emails in your inbox, including previously processed ones. Use this if you've made significant changes to your AI settings.</p>
                </div>
                <button 
                  className="processing-btn secondary"
                  onClick={handleProcessAll}
                  disabled={isProcessing}
                >
                  {isProcessing ? 'Processing...' : 'Process All (Coming Soon)'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 