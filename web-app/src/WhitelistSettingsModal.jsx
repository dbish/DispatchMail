import { useEffect, useState } from 'react';
import './WhitelistSettingsModal.css';

function WhitelistSettingsModal({ isOpen, onClose }) {
  const [rules, setRules] = useState([]);

  useEffect(() => {
    if (!isOpen) return;
    fetch('/api/whitelist')
      .then((res) => res.json())
      .then((data) => setRules(data.rules || []))
      .catch((err) => console.error('Failed to fetch whitelist', err));
  }, [isOpen]);

  if (!isOpen) return null;

  const updateRule = (idx, field, value) => {
    const newRules = [...rules];
    newRules[idx] = { ...newRules[idx], [field]: value };
    setRules(newRules);
  };

  const addRule = () => {
    setRules([...rules, { type: 'email', value: '' }]);
  };

  const saveRules = async () => {
    await fetch('/api/whitelist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules }),
    });
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Whitelist Settings</h2>
        {rules.map((rule, idx) => (
          <div key={idx} className="rule-row">
            <select
              value={rule.type}
              onChange={(e) => updateRule(idx, 'type', e.target.value)}
            >
              <option value="email">Email</option>
              <option value="subject">Subject</option>
              <option value="classification">Classification</option>
            </select>
            <input
              type="text"
              value={rule.value}
              onChange={(e) => updateRule(idx, 'value', e.target.value)}
            />
          </div>
        ))}
        <button onClick={addRule}>Add Rule</button>
        <div className="modal-actions">
          <button onClick={saveRules}>Save</button>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

export default WhitelistSettingsModal;
