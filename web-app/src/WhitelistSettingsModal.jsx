import { useEffect, useState } from 'react';
import './WhitelistSettingsModal.css';

function WhitelistSettingsModal({ isOpen, onClose }) {
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
      .then((data) => setRules(data.rules || []))
      .catch((err) => console.error('Failed to fetch whitelist', err));
  }, [isOpen]);

  // Poll for reprocessing status
  useEffect(() => {
    if (!reprocessingStatus.is_reprocessing) return;
    
    const interval = setInterval(async () => {
      try {
        const response = await fetch('/api/reprocessing_status');
        const status = await response.json();
        setReprocessingStatus(status);
        
        if (!status.is_reprocessing) {
          setMessage('Email reprocessing completed! Your inbox has been updated.');
          setTimeout(() => {
            setMessage('');
            onClose();
          }, 3000);
        }
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
        setMessage('Rules saved successfully! Starting email reprocessing...');
        setReprocessingStatus({ is_reprocessing: true, message: 'Starting...' });
      } else {
        setMessage('Failed to save rules. Please try again.');
      }
    } catch (error) {
      setMessage('Error saving rules. Please try again.');
    } finally {
      setIsLoading(false);
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
        
        {reprocessingStatus.is_reprocessing && (
          <div className="reprocessing-status">
            <div className="reprocessing-header">
              <span className="loading-spinner">🔄</span>
              <strong>Reprocessing emails...</strong>
            </div>
            <div className="reprocessing-message">{reprocessingStatus.message}</div>
            <p className="reprocessing-note">
              This may take a few moments. The modal will close automatically when complete.
            </p>
          </div>
        )}
        
        {rules.map((rule, idx) => (
          <div key={idx} className="rule-row">
            <select
              value={rule.type}
              onChange={(e) => updateRule(idx, 'type', e.target.value)}
              disabled={isLoading || reprocessingStatus.is_reprocessing}
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
            />
            <button 
              type="button" 
              onClick={() => removeRule(idx)}
              disabled={isLoading || reprocessingStatus.is_reprocessing}
            >
              Remove
            </button>
          </div>
        ))}
        
        <button 
          onClick={addRule} 
          disabled={isLoading || reprocessingStatus.is_reprocessing}
        >
          Add Rule
        </button>
        
        <div className="modal-actions">
          <button 
            onClick={saveRules} 
            disabled={isLoading || reprocessingStatus.is_reprocessing}
          >
            {isLoading ? 'Saving...' : reprocessingStatus.is_reprocessing ? 'Reprocessing...' : 'Save & Reprocess'}
          </button>
          <button 
            onClick={onClose} 
            disabled={isLoading || reprocessingStatus.is_reprocessing}
          >
            {reprocessingStatus.is_reprocessing ? 'Processing...' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default WhitelistSettingsModal;
