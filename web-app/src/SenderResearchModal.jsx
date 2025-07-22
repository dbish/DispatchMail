import { useState } from 'react';
import './EmailModals.css';

export default function SenderResearchModal({ isOpen, onClose, senderEmail, senderName }) {
  const [isLoading, setIsLoading] = useState(false);
  const [researchData, setResearchData] = useState(null);
  const [error, setError] = useState('');

  const handleResearch = async () => {
    setIsLoading(true);
    setError('');
    setResearchData(null);
    
    try {
      const response = await fetch('/api/research_sender', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sender_email: senderEmail,
          sender_name: senderName || ''
        }),
      });
      
      if (response.ok) {
        const data = await response.json();
        setResearchData(data);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to research sender');
      }
    } catch (error) {
      setError('Network error occurred');
      console.error('Error researching sender:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnnotationClick = (annotation) => {
    if (annotation.url) {
      window.open(annotation.url, '_blank');
    }
  };

  // Function to render markdown-style links in text
  const renderTextWithLinks = (text) => {
    if (!text) return text;
    
    // Regex to match markdown-style links: [text](url)
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = linkRegex.exec(text)) !== null) {
      // Add text before the link
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      
      // Add the link
      parts.push(
        <a 
          key={match.index}
          href={match[2]} 
          target="_blank" 
          rel="noopener noreferrer"
          className="summary-link"
        >
          {match[1]}
        </a>
      );
      
      lastIndex = match.index + match[0].length;
    }
    
    // Add remaining text after the last link
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }
    
    return parts.length > 1 ? parts : text;
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal research-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="research-header">
            <h3>Research Sender</h3>
            <div className="sender-info">
              <span className="sender-name">{senderName || 'Unknown'}</span>
              <span className="sender-email">{senderEmail}</span>
            </div>
          </div>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/>
            </svg>
          </button>
        </div>
        
        <div className="modal-content">
          <div className="research-content">
            {!researchData && !isLoading && (
              <div className="research-prompt">
                <p>Click the button below to research information about this sender.</p>
                <button 
                  className="research-btn primary"
                  onClick={handleResearch}
                  disabled={isLoading}
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/>
                  </svg>
                  Research Sender
                </button>
              </div>
            )}
            
            {isLoading && (
              <div className="research-loading">
                <div className="loading-spinner"></div>
                <p>Researching sender...</p>
              </div>
            )}
            
            {error && (
              <div className="research-error">
                <p>Error: {error}</p>
                <button 
                  className="research-btn"
                  onClick={handleResearch}
                  disabled={isLoading}
                >
                  Try Again
                </button>
              </div>
            )}
            
            {researchData && (
              <div className="research-results">
                <div className="search-query">
                  <span className="query-label">Search Query:</span>
                  <span className="query-text">"{researchData.search_query}"</span>
                </div>
                
                <div className="summary-section">
                  <h4>Summary</h4>
                  <div className="summary-text">
                    {renderTextWithLinks(researchData.summary)}
                  </div>
                </div>
                
                {researchData.annotations && researchData.annotations.length > 0 && (
                  <div className="annotations-section">
                    <h4>Sources</h4>
                    <div className="annotation-tiles">
                      {researchData.annotations.map((annotation, index) => (
                        <button
                          key={index}
                          className="annotation-tile"
                          onClick={() => handleAnnotationClick(annotation)}
                        >
                          <div className="tile-content">
                            <div className="tile-domain">
                              {new URL(annotation.url).hostname}
                            </div>
                            <div className="tile-title">
                              {annotation.title || annotation.description || 'Visit source'}
                            </div>
                          </div>
                          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                            <path d="M8 4.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7ZM8 1a.75.75 0 0 1 .75.75v.75a.75.75 0 0 1-1.5 0V1.75A.75.75 0 0 1 8 1Zm0 12a.75.75 0 0 1 .75.75v.75a.75.75 0 0 1-1.5 0v-.75A.75.75 0 0 1 8 13Zm5.657-10.243a.75.75 0 0 1 0 1.061l-.53.53a.75.75 0 0 1-1.061-1.061l.53-.53a.75.75 0 0 1 1.061 0Zm-9.9 9.9a.75.75 0 0 1 0 1.061l-.53.53a.75.75 0 0 1-1.061-1.061l.53-.53a.75.75 0 0 1 1.061 0ZM15 8a.75.75 0 0 1-.75.75h-.75a.75.75 0 0 1 0-1.5h.75A.75.75 0 0 1 15 8ZM3 8a.75.75 0 0 1-.75.75H1.5a.75.75 0 0 1 0-1.5h.75A.75.75 0 0 1 3 8Zm10.243 5.657a.75.75 0 0 1-1.061 0l-.53-.53a.75.75 0 0 1 1.061-1.061l.53.53a.75.75 0 0 1 0 1.061Zm-9.9-9.9a.75.75 0 0 1-1.061 0l-.53-.53a.75.75 0 0 1 1.061-1.061l.53.53a.75.75 0 0 1 0 1.061Z"/>
                          </svg>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                
                <div className="research-actions">
                  <button 
                    className="research-btn"
                    onClick={handleResearch}
                    disabled={isLoading}
                  >
                    Research Again
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 