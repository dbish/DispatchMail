import { useState, useEffect } from 'react';
import './DraftingSettingsModal.css';

export default function AwaitingHumanModal({ isOpen, onClose, email, onSend, onDelete, onRerun }) {
  const [systemPrompt, setSystemPrompt] = useState('');
  const [draftPrompt, setDraftPrompt] = useState('');
  const [userPrompt, setUserPrompt] = useState('');
  const [llmPrompt, setLlmPrompt] = useState('');
  const [emailDraft, setEmailDraft] = useState('');
  const [isRerunning, setIsRerunning] = useState(false);
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    if (email && isOpen) {
      // Set the user prompt (email content)
      const emailContent = `Subject: ${email.subject}\nFrom: ${email.from}\n\n${email.body}`;
      setUserPrompt(emailContent);
      setEmailDraft(email.draft || '');
      
      // Set the LLM prompt (what was actually sent to the AI)
      setLlmPrompt(email.llm_prompt || 'No LLM prompt available');
      
      // Fetch current system and draft prompts
      fetch('/api/prompt')
        .then((res) => res.json())
        .then((data) => setSystemPrompt(data.prompt || ''))
        .catch(() => {});
        
      fetch('/api/draft_prompt')
        .then((res) => res.json())
        .then((data) => setDraftPrompt(data.prompt || ''))
        .catch(() => {});
    }
  }, [email, isOpen]);

  if (!isOpen || !email) return null;

  const handleRerun = async () => {
    setIsRerunning(true);
    try {
      // Update prompts if they were changed
      const requests = [];
      
      // Only update prompt if it's not empty
      if (systemPrompt && systemPrompt.trim()) {
        requests.push(
          fetch('/api/prompt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: systemPrompt }),
          })
        );
      }
      
      // Only update draft prompt if it's not empty
      if (draftPrompt && draftPrompt.trim()) {
        requests.push(
          fetch('/api/draft_prompt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: draftPrompt }),
          })
        );
      }
      
      // Wait for all prompt updates to complete
      if (requests.length > 0) {
        await Promise.all(requests);
      }

      // Trigger reprocessing of this specific email
      const response = await fetch('/api/reprocess_single_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: email.message_id }),
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.new_draft) {
          setEmailDraft(data.new_draft);
        }
        if (data.llm_prompt) {
          setLlmPrompt(data.llm_prompt);
        }
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
      setIsSending(false); // Only reset on error, success will close modal
    }
  };

  const handleDelete = () => {
    onDelete(email.message_id);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal awaiting-human-modal" onClick={(e) => e.stopPropagation()}>
        <h2>Email Draft Review</h2>
        <div className="email-info">
          <div className="subject">Subject: {email.subject}</div>
          <div className="from">From: {email.from}</div>
        </div>
        
        <div className="modal-content">
          <div className="left-col">
            <label>System Prompt</label>
            <textarea
              rows={4}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Email reading system prompt..."
            />
            
            <label>Drafting Instructions</label>
            <textarea
              rows={3}
              value={draftPrompt}
              onChange={(e) => setDraftPrompt(e.target.value)}
              placeholder="Drafting prompt instructions..."
            />
            
            <label>Actual LLM Prompt (Debug)</label>
            <textarea
              rows={4}
              value={llmPrompt}
              readOnly
              className="readonly"
              placeholder="The actual content sent to the LLM..."
            />
          </div>
          <div className="right-col">
            <label>Full Email Content</label>
            <textarea 
              rows={6} 
              value={userPrompt} 
              readOnly 
              className="readonly"
            />
            
            <label>Generated Draft</label>
            <textarea
              rows={9}
              value={emailDraft}
              onChange={(e) => setEmailDraft(e.target.value)}
              placeholder="Email draft will appear here..."
            />
          </div>
        </div>
        
        <div className="modal-actions">
          <button 
            onClick={handleRerun} 
            disabled={isRerunning || isSending}
            className="rerun-btn"
          >
            {isRerunning ? 'Rerunning...' : 'Rerun'}
          </button>
          <button 
            onClick={handleDelete}
            disabled={isSending}
            className="delete-btn"
          >
            Delete Draft
          </button>
          <button 
            onClick={handleSend}
            disabled={isSending}
            className="send-btn"
          >
            {isSending ? 'Sending...' : 'Send Email'}
          </button>
          <button onClick={onClose} disabled={isSending}>Close</button>
        </div>
      </div>
    </div>
  );
} 