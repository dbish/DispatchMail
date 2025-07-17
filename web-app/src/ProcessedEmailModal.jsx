import { useState, useEffect } from 'react';

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
      setEmailDraft(email.draft || '');
      
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-80 p-2"
      onClick={onClose}
    >
      <div
        className="bg-gray-800 text-gray-200 rounded-lg w-full max-w-5xl h-full max-h-[95vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center px-4 py-2 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">{isSentEmail ? 'Sent:' : 'Draft:'}</span>
            <span className="text-sm font-semibold">{email.subject}</span>
          </div>
          <button onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-gray-200">
            <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 11-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z" />
            </svg>
          </button>
        </div>

        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div>
              <div className="mb-2 text-sm text-gray-400">
                <span className="font-semibold">{email.from}</span> · {new Date(email.date || new Date()).toLocaleString()}
              </div>
              <div className="whitespace-pre-wrap">{userPrompt}</div>
            </div>
          </div>

          <div className="border-t border-gray-700 p-4 bg-gray-900 space-y-2 overflow-y-auto">
            {isSentEmail ? (
              <textarea
                className="w-full h-32 p-2 rounded bg-gray-700 text-sm text-gray-300"
                value={emailDraft}
                readOnly
              />
            ) : (
              <>
                <textarea
                  className="w-full h-32 p-2 rounded bg-gray-700 text-sm text-gray-200"
                  value={emailDraft}
                  onChange={(e) => setEmailDraft(e.target.value)}
                  placeholder="Email draft will appear here..."
                />
                <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2">
                  <textarea
                    className="w-full p-2 rounded bg-gray-700 text-sm"
                    rows={3}
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    placeholder="Email reading system prompt..."
                  />
                  <textarea
                    className="w-full p-2 rounded bg-gray-700 text-sm"
                    rows={3}
                    value={draftPrompt}
                    onChange={(e) => setDraftPrompt(e.target.value)}
                    placeholder="Drafting prompt instructions..."
                  />
                  <textarea
                    className="w-full p-2 rounded bg-gray-700 text-sm text-gray-400"
                    rows={3}
                    value={llmPrompt}
                    readOnly
                    placeholder="The actual content sent to the LLM..."
                  />
                </div>
                <div className="mt-2 flex justify-end gap-2">
                  <button
                    className="bg-gray-700 hover:bg-gray-600 text-sm px-4 py-2 rounded"
                    onClick={handleGenerate}
                    disabled={isGenerating || isSending}
                  >
                    {isGenerating ? 'Generating...' : 'Generate Draft'}
                  </button>
                  <button
                    className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded disabled:opacity-50"
                    onClick={handleSend}
                    disabled={isSending || !emailDraft.trim()}
                  >
                    {isSending ? 'Sending...' : 'Send Email'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 