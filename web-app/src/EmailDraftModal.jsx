import { useState, useEffect } from 'react';

export default function EmailDraftModal({ isOpen, onClose, email, onSend }) {
  const [text, setText] = useState('');

  useEffect(() => {
    if (email) {
      setText(email.draft || '');
    }
  }, [email]);

  if (!isOpen || !email) return null;

  const handleSend = () => {
    onSend(text);
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

          <div className="border-t border-gray-700 p-4 bg-gray-900">
            <textarea
              className="w-full h-32 p-2 rounded bg-gray-700 text-sm text-gray-200"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Write your response..."
            />
            <div className="mt-2 flex justify-end">
              <button
                className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded disabled:opacity-50"
                onClick={handleSend}
                disabled={!text.trim()}
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
