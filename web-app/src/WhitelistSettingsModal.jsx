import { useEffect, useState } from 'react';
import './WhitelistSettingsModal.css';

function WhitelistSettingsModal({ isOpen, onClose, onResetSuccess }) {
  const [rules, setRules] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [reprocessingStatus, setReprocessingStatus] = useState({
    is_reprocessing: false,
    message: ''
  });
  const [isResetting, setIsResetting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    console.log('Fetching whitelist');
    fetch('/api/whitelist')
      .then((res) => res.json())
      .then((data) => {
        console.log('Whitelist fetched:', data);
        console.log('Rules:', data.whitelist.rules);
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
        const response = await fetch('/api/reprocess_all');

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
        setMessage('Rules saved successfully!');
        onResetSuccess();
        setReprocessingStatus({
          is_reprocessing: true,
          message: 'Reprocessing emails...'
        });
      } else {
        setMessage('Failed to save rules. Please try again.');
      }
    } catch (error) {
      setMessage('Error saving rules. Please try again.');
    } finally {
      setIsLoading(false);
      //clear the message after 3 seconds
      setTimeout(() => {
        setMessage('');
      }, 3000);
    }
  };

  const resetInbox = async () => {
    if (!confirm('Are you sure you want to reset the inbox? This will permanently delete all emails from the database and reset the processing timestamp. Your whitelist rules will be preserved. This action cannot be undone.')) {
      return;
    }

    setIsResetting(true);
    setMessage('');
    
    try {
      const response = await fetch('/api/reset_inbox', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      const result = await response.json();
      
      if (result.success) {
        setMessage(`Inbox reset successfully! ${result.emails_deleted} emails deleted.`);
        // Notify parent component that reset was successful
        if (onResetSuccess) {
          onResetSuccess();
        }
        setTimeout(() => {
          setMessage('');
          onClose();
        }, 3000);
      } else {
        setMessage(`Error: ${result.error}`);
      }
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Whitelist Settings</h2>
        <p>Configure which emails should be imported into your AI inbox.</p>
        
        {message && (
          <div className={`message ${message.includes('Error') || message.includes('Failed') ? 'error' : 'success'}`}>
            {message}
          </div>
        )}
        
        {rules.map((rule, idx) => (
          <div key={idx} className="rule-row">
            <select
              value={rule.type}
              onChange={(e) => updateRule(idx, 'type', e.target.value)}
              disabled={isLoading || reprocessingStatus.is_reprocessing || isResetting}
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
              disabled={isLoading || reprocessingStatus.is_reprocessing || isResetting}
            />
            <button 
              type="button" 
              onClick={() => removeRule(idx)}
              disabled={isLoading || reprocessingStatus.is_reprocessing || isResetting}
            >
              Remove
            </button>
          </div>
        ))}
        
        <button 
          onClick={addRule} 
          disabled={isLoading || reprocessingStatus.is_reprocessing || isResetting}
        >
          Add Rule
        </button>
        
        <div className="modal-actions">
          <button 
            onClick={saveRules} 
            disabled={isLoading || reprocessingStatus.is_reprocessing || isResetting}
          >
            {isLoading ? 'Saving...' : reprocessingStatus.is_reprocessing ? 'Reprocessing...' : 'Save & Reprocess'}
          </button>
          <button 
            onClick={onClose} 
            disabled={isLoading || reprocessingStatus.is_reprocessing || isResetting}
          >
            {reprocessingStatus.is_reprocessing ? 'Processing...' : 'Cancel'}
          </button>
        </div>
        
        <div className="modal-debug-section">
          <hr style={{ margin: '20px 0', borderColor: '#e0e0e0' }} />
          <p style={{ fontSize: '14px', color: '#666', marginBottom: '10px' }}>
            <strong>Debug Options:</strong>
          </p>
          <button 
            onClick={resetInbox}
            disabled={isLoading || reprocessingStatus.is_reprocessing || isResetting}
            style={{ 
              backgroundColor: '#ff4444', 
              color: 'white', 
              border: 'none', 
              padding: '8px 16px',
              borderRadius: '4px',
              cursor: isLoading || reprocessingStatus.is_reprocessing || isResetting ? 'not-allowed' : 'pointer',
              opacity: isLoading || reprocessingStatus.is_reprocessing || isResetting ? 0.6 : 1
            }}
          >
                         {isResetting ? 'Resetting...' : 'Reset Inbox (Delete All Emails)'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default WhitelistSettingsModal;
