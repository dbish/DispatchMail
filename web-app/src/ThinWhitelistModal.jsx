import { useEffect, useState } from 'react';
import './ThinWhitelistModal.css';

function ThinWhitelistModal({ isOpen, onClose, onResetSuccess }) {
  const [rules, setRules] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [reprocessingStatus, setReprocessingStatus] = useState({
    is_reprocessing: false,
    message: ''
  });

  useEffect(() => {
    if (!isOpen) return;
    fetch('/api/whitelist')
      .then((res) => res.json())
      .then((data) => {
        setRules(data.whitelist.rules || []);
      })
      .catch((err) => console.error('Failed to fetch whitelist', err));
  }, [isOpen]);

  // Poll for reprocessing status
  useEffect(() => {
    if (!reprocessingStatus.is_reprocessing) return;
    
    const interval = setInterval(async () => {
      try {
        setReprocessingStatus({
          is_reprocessing: true,
          message: 'Reprocessing emails...'
        });
        await fetch('/api/reprocess_all');
        onResetSuccess();

        setReprocessingStatus({
          is_reprocessing: false,
          message: 'Email reprocessing completed! Your inbox has been updated.'
        });
      } catch (err) {
        console.error('Failed to check reprocessing status:', err);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [reprocessingStatus.is_reprocessing, onClose]);

  if (!isOpen) return null;

  const updateRule = (idx, field, value) => {
    const newRules = [...rules];
    newRules[idx] = { ...newRules[idx], [field]: value };
    setRules(newRules);
  };

  const addRule = () => {
    setRules([...rules, { type: 'email', value: '' }]);
  };

  const removeRule = (idx) => {
    const newRules = rules.filter((_, i) => i !== idx);
    setRules(newRules);
  };

  const saveRules = async () => {
    setIsLoading(true);
    setMessage('');
    
    try {
      const response = await fetch('/api/whitelist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules }),
      });
      
      if (response.ok) {
        setMessage('Rules saved successfully! Changes will apply to new incoming emails.');
        onResetSuccess();
      } else {
        setMessage('Failed to save rules. Please try again.');
      }
    } catch {
      setMessage('Error saving rules. Please try again.');
    } finally {
      setIsLoading(false);
      //clear the message after 5 seconds
      setTimeout(() => {
        setMessage('');
      }, 5000);
    }
  };



  const applyToAllMailStub = async () => {
    console.log('Apply to All Mail - Not yet implemented');
    // This is a no-op for now as requested
    setMessage('Apply to All Mail feature coming soon!');
    setTimeout(() => {
      setMessage('');
    }, 3000);
  };

  return (
    <div className="thin-modal-overlay" onClick={onClose}>
      <div className="thin-modal" onClick={(e) => e.stopPropagation()}>
        <div className="thin-modal-header">
          <h2>Whitelist Settings</h2>
          <button className="thin-close-btn" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/>
            </svg>
          </button>
        </div>
        
        <div className="thin-modal-content">
          <p className="thin-description">Configure which emails should be imported into your AI inbox. Changes will automatically apply to new incoming emails.</p>
          
          {message && (
            <div className={`thin-message ${message.includes('Error') || message.includes('Failed') ? 'error' : 'success'}`}>
              {message}
            </div>
          )}
          
          <div className="thin-rules-container">
            {rules.length === 0 ? (
              <div className="thin-empty-state">
                <div className="thin-empty-icon">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                  </svg>
                </div>
                <h3 className="thin-empty-title">No whitelist rules yet</h3>
                <p className="thin-empty-description">
                  Add rules to control which emails are imported into your AI inbox. 
                  Only emails matching your rules will be processed.
                </p>
              </div>
            ) : (
              rules.map((rule, idx) => (
                <div key={idx} className="thin-rule-row">
                  <select
                    value={rule.type}
                    onChange={(e) => updateRule(idx, 'type', e.target.value)}
                    disabled={isLoading || reprocessingStatus.is_reprocessing}
                    className="thin-rule-select"
                  >
                    <option value="email">Email Address</option>
                    <option value="subject">Subject Contains</option>
                    <option value="classification">AI Classification</option>
                  </select>
                  <input
                    type="text"
                    value={rule.value}
                    onChange={(e) => updateRule(idx, 'value', e.target.value)}
                    placeholder={
                      rule.type === 'email' ? 'someone@example.com' :
                      rule.type === 'subject' ? '[agent]' :
                      'Describe emails to allow'
                    }
                    disabled={isLoading || reprocessingStatus.is_reprocessing}
                    className="thin-rule-input"
                  />
                  <button 
                    type="button" 
                    onClick={() => removeRule(idx)}
                    disabled={isLoading || reprocessingStatus.is_reprocessing}
                    className="thin-remove-btn"
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
          
          <button 
            onClick={addRule} 
            disabled={isLoading || reprocessingStatus.is_reprocessing}
            className="thin-add-rule-btn"
          >
            + Add Rule
          </button>
        </div>
        
        <div className="thin-modal-footer">
          <div className="thin-footer-left">
            <button 
              onClick={applyToAllMailStub} 
              disabled={isLoading || reprocessingStatus.is_reprocessing}
              className="thin-secondary-btn"
            >
              {reprocessingStatus.is_reprocessing ? 'Processing...' : 'Apply to All Mail (Coming Soon)'}
            </button>
          </div>
          <div className="thin-footer-right">
            <button 
              onClick={onClose} 
              disabled={isLoading || reprocessingStatus.is_reprocessing}
              className="thin-cancel-btn"
            >
              {reprocessingStatus.is_reprocessing ? 'Processing...' : 'Cancel'}
            </button>
            <button 
              onClick={saveRules} 
              disabled={isLoading || reprocessingStatus.is_reprocessing}
              className="thin-save-btn"
            >
              {isLoading ? 'Saving...' : 'Save Rules'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ThinWhitelistModal; 