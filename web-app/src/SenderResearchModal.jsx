import { useState } from 'react';
import './EmailModals.css';

export default function SenderResearchModal({ isOpen, onClose, senderEmail, senderName }) {
  const [isLoading, setIsLoading] = useState(false);
  const [researchData, setResearchData] = useState(null);
  const [error, setError] = useState('');
  
  // Default research prompt
  const defaultPrompt = `You are an expert people researcher. You'll be provided an email and your goal is to create a snippet to summarize information about the sender. you can use the domain to understand the organization if it isn't a large email provider, and you can use web search to get info on them.

Email: ${senderEmail}
Name: ${senderName || 'Unknown'}`;

  const [researchPrompt, setResearchPrompt] = useState(defaultPrompt);
  const [isEditingPrompt, setIsEditingPrompt] = useState(false);

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
          sender_name: senderName || '',
          research_prompt: researchPrompt // Include the custom prompt
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

  const handlePromptUpdate = () => {
    // For now, this is a no-op as requested
    // In the future, this could save the prompt to user preferences
    setIsEditingPrompt(false);
  };

  const handlePromptReset = () => {
    setResearchPrompt(defaultPrompt);
    setIsEditingPrompt(false);
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
      <div className="research-modal-redesigned" onClick={(e) => e.stopPropagation()}>
        {/* Enhanced Header with Better Information Hierarchy */}
        <div className="research-modal-header">
          <div className="research-header-content">
            <div className="research-title-section">
              <h2 className="research-title">Sender Research</h2>
              <p className="research-subtitle">Get context and background information</p>
            </div>
            
            <div className="sender-card">
              <div className="sender-avatar">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                </svg>
              </div>
              <div className="sender-details">
                <div className="sender-name-primary">{senderName || 'Unknown Sender'}</div>
                <div className="sender-email-primary">{senderEmail}</div>
              </div>
            </div>
          </div>
          
          <button className="research-close-btn" onClick={onClose} aria-label="Close research">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>
        
        {/* Main Content Area with Better UX Flow */}
        <div className="research-modal-body">
          {/* Initial State: Clear Call to Action */}
          {!researchData && !isLoading && !error && (
            <div className="research-empty-state">
              <div className="empty-state-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
                </svg>
              </div>
              <h3 className="empty-state-title">Research This Sender</h3>
              <p className="empty-state-description">
                Get background information, company details, and context about this email sender to help you make informed decisions.
              </p>
              
              {/* Start Research Button - Moved above the prompt */}
              <button 
                className="research-cta-btn"
                onClick={handleResearch}
                disabled={isLoading}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
                </svg>
                Start Research
              </button>
              
              {/* Research Prompt Section - Now below the button */}
              <div className="research-prompt-section">
                <div className="prompt-header">
                  <h4 className="prompt-title">Research Prompt</h4>
                  <div className="prompt-controls">
                    <button 
                      className="prompt-edit-btn"
                      onClick={() => setIsEditingPrompt(!isEditingPrompt)}
                      title={isEditingPrompt ? "Cancel editing" : "Edit prompt"}
                    >
                      {isEditingPrompt ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
                        </svg>
                      )}
                    </button>
                    <button 
                      className="prompt-reset-btn"
                      onClick={handlePromptReset}
                      title="Reset to default prompt"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                      </svg>
                    </button>
                  </div>
                </div>
                
                {isEditingPrompt ? (
                  <div className="prompt-editor">
                    <textarea
                      className="prompt-textarea"
                      value={researchPrompt}
                      onChange={(e) => setResearchPrompt(e.target.value)}
                      placeholder="Enter your research prompt..."
                      rows="6"
                    />
                    <div className="prompt-editor-actions">
                      <button 
                        className="prompt-save-btn"
                        onClick={handlePromptUpdate}
                      >
                        Save Changes
                      </button>
                      <button 
                        className="prompt-cancel-btn"
                        onClick={() => setIsEditingPrompt(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="prompt-display">
                    <pre className="prompt-text">{researchPrompt}</pre>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Loading State: Enhanced with Progress Indication */}
          {isLoading && (
            <div className="research-loading-state">
              <div className="loading-animation">
                <div className="loading-spinner-modern"></div>
              </div>
              <div className="loading-content">
                <h3 className="loading-title">Researching Sender</h3>
                <p className="loading-description">Gathering information from multiple sources...</p>
                <div className="loading-steps">
                  <div className="loading-step active">
                    <div className="step-dot"></div>
                    <span>Searching public records</span>
                  </div>
                  <div className="loading-step active">
                    <div className="step-dot"></div>
                    <span>Analyzing social presence</span>
                  </div>
                  <div className="loading-step">
                    <div className="step-dot"></div>
                    <span>Compiling results</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {/* Error State: User-Friendly with Clear Next Steps */}
          {error && (
            <div className="research-error-state">
              <div className="error-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
              </div>
              <h3 className="error-title">Research Unavailable</h3>
              <p className="error-description">
                We couldn't gather information about this sender right now. This might be due to network issues or limited public information.
              </p>
              <div className="error-actions">
                <button 
                  className="retry-btn"
                  onClick={handleResearch}
                  disabled={isLoading}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                  </svg>
                  Try Again
                </button>
                <button 
                  className="skip-btn"
                  onClick={onClose}
                >
                  Continue Without Research
                </button>
              </div>
            </div>
          )}
          
          {/* Results State: Enhanced Information Architecture */}
          {researchData && (
            <div className="research-results-redesigned">
              {/* Search Query - More Subtle */}
              <div className="search-metadata">
                <div className="search-query-redesigned">
                  <span className="query-label-new">Search performed:</span>
                  <code className="query-text-new">"{researchData.search_query}"</code>
                </div>
              </div>
              
              {/* Primary Summary - Hero Content */}
              <div className="summary-section-redesigned">
                <div className="section-header">
                  <h3 className="section-title">Research Summary</h3>
                  <div className="section-subtitle">Key information about this sender</div>
                </div>
                <div className="summary-content">
                  {renderTextWithLinks(researchData.summary)}
                </div>
              </div>
              
              {/* Sources - Enhanced Presentation */}
              {researchData.annotations && researchData.annotations.length > 0 && (
                <div className="sources-section-redesigned">
                  <div className="section-header">
                    <h3 className="section-title">Sources & References</h3>
                    <div className="section-subtitle">{researchData.annotations.length} sources found</div>
                  </div>
                  <div className="sources-grid">
                    {researchData.annotations.map((annotation, index) => (
                      <button
                        key={index}
                        className="source-card"
                        onClick={() => handleAnnotationClick(annotation)}
                      >
                        <div className="source-header">
                          <div className="source-favicon">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                            </svg>
                          </div>
                          <div className="source-domain">
                            {new URL(annotation.url).hostname.replace('www.', '')}
                          </div>
                          <div className="external-link-icon">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                              <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.11 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
                            </svg>
                          </div>
                        </div>
                        <div className="source-content">
                          <div className="source-title">
                            {annotation.title || annotation.description || 'View source'}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Action Bar */}
              <div className="research-actions-redesigned">
                <button 
                  className="refresh-research-btn"
                  onClick={handleResearch}
                  disabled={isLoading}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                  </svg>
                  Refresh Research
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 