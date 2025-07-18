import { useState, useEffect } from 'react';
import './DraftingSettingsModal.css';

export default function ProcessedEmailModal({ isOpen, onClose, email, onSend }) {
  const [systemPrompt, setSystemPrompt] = useState('');
  const [draftPrompt, setDraftPrompt] = useState('');
  const [userPrompt, setUserPrompt] = useState('');
  const [llmPrompt, setLlmPrompt] = useState('');
  const [emailDraft, setEmailDraft] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    if (email && isOpen) {
      // Set the user prompt (email content)
      const emailContent = `Subject: ${email.subject}\nFrom: ${email.from}\n\n${email.body}`;
      setUserPrompt(emailContent);
      
      // If email was sent, show the draft that was sent
      // If email was not sent (like "reviewed (no action needed)"), start with empty or existing draft
      setEmailDraft(email.drafted_response || '');
      
      // Set the LLM prompt (what was actually sent to the AI)
      setLlmPrompt(email.llm_prompt || 'No LLM prompt available');
      
      // Fetch current system and draft prompts, but with defaults that encourage drafting
      fetch('/api/prompt')
        .then((res) => res.json())
        .then((data) => setSystemPrompt(data.prompt || 'You are an email assistant. Always draft responses to emails that could benefit from a reply. Return JSON with a draft field containing a helpful response.'))
        .catch(() => setSystemPrompt('You are an email assistant. Always draft responses to emails that could benefit from a reply. Return JSON with a draft field containing a helpful response.'));
        
      fetch('/api/draft_prompt')
        .then((res) => res.json())
        .then((data) => setDraftPrompt(data.prompt || 'Always create a helpful, professional response unless the email is clearly spam or automated. Focus on being helpful and engaging.'))
        .catch(() => setDraftPrompt('Always create a helpful, professional response unless the email is clearly spam or automated. Focus on being helpful and engaging.'));
    }
  }, [email, isOpen]);

  if (!isOpen || !email) return null;

  const handleGenerate = async () => {
    setIsGenerating(true);
    console.log('Generating draft for email:', email.message_id);
    console.log('System prompt:', systemPrompt);
    console.log('Draft prompt:', draftPrompt);
    
    try {
      const response = await fetch('/api/rerun_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email_id: email.message_id,
          system_prompt: systemPrompt,
          draft_prompt: draftPrompt
        }),
      });
      
      console.log('Response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Response data:', data);
        setEmailDraft(data.draft || '');
        setLlmPrompt(data.llm_prompt || 'No LLM prompt available');
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Failed to generate draft:', response.status, errorData);
      }
    } catch (error) {
      console.error('Error generating draft:', error);
    } finally {
      setIsGenerating(false);
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

  // Check if this was a sent email (read-only mode)
  const isSentEmail = email.action === 'sent';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal processed-email-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{isSentEmail ? 'Sent Email' : 'Draft Email'}</h2>
          <div className="email-info">
            <div className="subject">Subject: {email.subject}</div>
            <div className="from">From: {email.from}</div>
            <div className="action">Action: {email.state.join(' | ')}</div>
          </div>
        </div>
        
        {isSentEmail ? (
          // Read-only view for sent emails
          <div className="modal-content">
            <div className="left-col">
              <div className="email-display-section">
                <label>Original Email Content</label>
                <textarea 
                  value={email.body || 'No content available'} 
                  readOnly 
                  className="readonly"
                />
              </div>
              <div className="draft-compose-section">
                <label>Sent Message</label>
                <textarea
                  value={emailDraft}
                  readOnly
                  className="readonly"
                  placeholder="No message content available"
                />
              </div>
            </div>
            <div className="right-col">
              {/* The right column is intentionally empty for this read-only view */}
            </div>
          </div>
        ) : (
          // Interactive view for non-sent emails
          <div className="modal-content">
            <div className="left-col">
              <div className="email-display-section">
                <label>Full Email Content</label>
                <textarea 
                  value={userPrompt} 
                  readOnly 
                  className="readonly"
                />
              </div>
              <div className="draft-compose-section">
                <label>Generated Draft</label>
                <textarea
                  value={emailDraft}
                  onChange={(e) => setEmailDraft(e.target.value)}
                  placeholder="Email draft will appear here..."
                />
              </div>
            </div>
            <div className="right-col">
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
          </div>
        )}
        
        <div className="modal-actions">
          {!isSentEmail && (
            <>
              <button 
                onClick={handleGenerate} 
                disabled={isGenerating || isSending}
                className="rerun-btn"
              >
                {isGenerating ? 'Generating...' : 'Generate Draft'}
              </button>
              <button 
                onClick={handleSend}
                disabled={isSending || !emailDraft.trim()}
                className="send-btn"
              >
                {isSending ? 'Sending...' : 'Send Email'}
              </button>
            </>
          )}
          <button onClick={onClose} disabled={isSending || isGenerating}>Close</button>
        </div>
      </div>
    </div>
  );
} 