import { useState } from 'react';
import './App.css';

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rules, setRules] = useState([
    { type: 'subject', value: '[agent]' } // Default rule for [agent] subject
  ]);
  const [error, setError] = useState('');

  const handleCredentialsSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch('/api/verify_credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.error || 'Failed to verify credentials');
        return;
      }
      setStep(2); // Move to whitelist rules step
    } catch {
      setError('Failed to connect to server');
    }
  };

  const handleWhitelistSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      // Save whitelist rules
      const whitelistRes = await fetch('/api/whitelist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules }),
      });
      if (!whitelistRes.ok) {
        const data = await whitelistRes.json();
        setError(data.error || 'Failed to save whitelist rules');
        return;
      }

      // Complete onboarding
      const onboardRes = await fetch('/api/onboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!onboardRes.ok) {
        const data = await onboardRes.json();
        setError(data.error || 'Failed to complete onboarding');
        return;
      }

      localStorage.setItem('userEmail', email);
      onComplete(email);
    } catch {
      setError('Failed to connect to server');
    }
  };

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

  if (step === 1) {
    return (
      <form className="onboarding" onSubmit={handleCredentialsSubmit}>
        <h2>Step 1: Connect Gmail</h2>
        <p>Enter your Gmail credentials to connect your account.</p>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Gmail App Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button type="submit">Next</button>
        {error && <div className="error">{error}</div>}
      </form>
    );
  }

  if (step === 2) {
    return (
      <form className="onboarding" onSubmit={handleWhitelistSubmit}>
        <h2>Step 2: Configure Email Rules</h2>
        <p>Set up rules to control which emails are imported into your AI inbox.</p>
        <p><strong>Default:</strong> Only emails with "[agent]" in the subject will be imported.</p>
        
        <div className="whitelist-rules">
          {rules.map((rule, idx) => (
            <div key={idx} className="rule-row">
              <select
                value={rule.type}
                onChange={(e) => updateRule(idx, 'type', e.target.value)}
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
              />
              {rules.length > 1 && (
                <button type="button" onClick={() => removeRule(idx)}>Remove</button>
              )}
            </div>
          ))}
          <button type="button" onClick={addRule}>Add Rule</button>
        </div>
        
        <div className="onboarding-actions">
          <button type="button" onClick={() => setStep(1)}>Back</button>
          <button type="submit">Complete Setup</button>
        </div>
        {error && <div className="error">{error}</div>}
      </form>
    );
  }

  return null;
}
