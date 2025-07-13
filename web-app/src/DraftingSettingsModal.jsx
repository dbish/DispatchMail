import { useState } from 'react';
import './DraftingSettingsModal.css';

function DraftingSettingsModal({ isOpen, onClose, prompts, setPrompts }) {
  const [selectedName, setSelectedName] = useState(prompts[0]?.name || 'default');
  const [systemText, setSystemText] = useState(prompts[0]?.prompt || '');
  const [newPromptName, setNewPromptName] = useState('');
  const [testUserPrompt, setTestUserPrompt] = useState('');
  const [testEmailDraft, setTestEmailDraft] = useState('');

  if (!isOpen) return null;

  const handlePromptChange = (name) => {
    setSelectedName(name);
    const found = prompts.find((p) => p.name === name);
    setSystemText(found ? found.prompt : '');
  };

  const addPrompt = () => {
    if (!newPromptName.trim()) return;
    if (!prompts.find((p) => p.name === newPromptName)) {
      setPrompts([...prompts, { name: newPromptName, prompt: '' }]);
      setSelectedName(newPromptName);
      setSystemText('');
      setNewPromptName('');
    }
  };

  const saveCurrentPrompt = () => {
    setPrompts(
      prompts.map((p) =>
        p.name === selectedName ? { ...p, prompt: systemText } : p
      )
    );
    fetch('/api/draft_prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: systemText }),
    });
  };

  const generateTest = () => {
    saveCurrentPrompt();
    setTestEmailDraft(
      `Draft generated with "${selectedName}" prompt.\nUser Prompt: ${testUserPrompt}`
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Drafting Settings</h2>
        <div className="prompt-select">
          <label>System Prompt: </label>
          <select
            value={selectedName}
            onChange={(e) => handlePromptChange(e.target.value)}
          >
            {prompts.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="New prompt name"
            value={newPromptName}
            onChange={(e) => setNewPromptName(e.target.value)}
          />
          <button onClick={addPrompt}>Add</button>
        </div>
        <div className="modal-content">
          <div className="left-col">
            <textarea
              rows={10}
              value={systemText}
              onChange={(e) => setSystemText(e.target.value)}
              placeholder="System prompt instructions"
            />
            <label>Test User Prompt</label>
            <textarea
              rows={4}
              value={testUserPrompt}
              onChange={(e) => setTestUserPrompt(e.target.value)}
              placeholder="User prompt for test"
            />
          </div>
          <div className="right-col">
            <label>Test Email Draft</label>
            <textarea rows={14} value={testEmailDraft} readOnly />
          </div>
        </div>
        <div className="modal-actions">
          <button onClick={generateTest}>Generate Test</button>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

export default DraftingSettingsModal;
