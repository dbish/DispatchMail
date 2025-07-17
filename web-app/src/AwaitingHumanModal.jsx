import { useState, useEffect } from 'react';

export default function AwaitingHumanModal({ isOpen, onClose, email, onSend, onDelete, onRerun }) {
  const [draftPrompt, setDraftPrompt] = useState('');
  const [llmPrompt, setLlmPrompt] = useState('');
  const [emailDraft, setEmailDraft] = useState('');
  const [isRerunning, setIsRerunning] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isSettingsPanelExpanded, setIsSettingsPanelExpanded] = useState(false);

  useEffect(() => {
    if (email && isOpen) {
      setEmailDraft(email.draft || '');
      
      // Set the LLM prompt (what was actually sent to the AI)
      setLlmPrompt(email.llm_prompt || 'No LLM prompt available');
      
      // Fetch current draft prompt
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
      // Update draft prompt if it was changed
      const requests = [];
      
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

  const toggleSettingsPanel = () => {
    setIsSettingsPanelExpanded(!isSettingsPanelExpanded);
  };

  const formatEmailBody = (body) => {
    if (!body) return '';
    return body.replace(/<[^>]*>/g, '').trim();
  };

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
            <span className="text-sm text-gray-400">Re:</span>
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
              <div className="whitespace-pre-wrap">{formatEmailBody(email.body)}</div>
            </div>
          </div>

          <div className="border-t border-gray-700 p-4 bg-gray-900 space-y-2 overflow-y-auto">
            <textarea
              className="w-full h-32 p-2 rounded bg-gray-700 text-sm text-gray-200"
              value={emailDraft}
              onChange={(e) => setEmailDraft(e.target.value)}
              placeholder="Generated email draft will appear here..."
            />

            {isSettingsPanelExpanded && (
              <div className="space-y-2">
                <textarea
                  className="w-full p-2 rounded bg-gray-700 text-sm"
                  value={draftPrompt}
                  onChange={(e) => setDraftPrompt(e.target.value)}
                  placeholder="Customize how the AI should write responses..."
                  rows={4}
                />
                <textarea
                  className="w-full p-2 rounded bg-gray-700 text-sm text-gray-400"
                  value={llmPrompt}
                  readOnly
                  placeholder="The actual content sent to the LLM..."
                  rows={6}
                />
              </div>
            )}

            <div className="flex justify-between items-center pt-2">
              <div className="flex gap-2">
                <button
                  className="bg-gray-700 hover:bg-gray-600 text-sm px-3 py-1 rounded"
                  onClick={handleRerun}
                  disabled={isRerunning || isSending}
                >
                  {isRerunning ? 'Regenerating...' : 'Regenerate'}
                </button>
                <button
                  className="bg-red-600 hover:bg-red-700 text-sm px-3 py-1 rounded"
                  onClick={handleDelete}
                  disabled={isSending}
                >
                  Delete Draft
                </button>
                <button
                  className="bg-gray-700 hover:bg-gray-600 text-sm px-3 py-1 rounded"
                  onClick={toggleSettingsPanel}
                >
                  {isSettingsPanelExpanded ? 'Hide Settings' : 'Show Settings'}
                </button>
              </div>
              <button
                className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded disabled:opacity-50"
                onClick={handleSend}
                disabled={isSending || !emailDraft.trim()}
              >
                {isSending ? 'Sending...' : 'Send Email'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 