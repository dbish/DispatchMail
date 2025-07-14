import { useEffect, useState } from 'react';
import './App.css';
import DraftingSettingsModal from './DraftingSettingsModal.jsx';
import WhitelistSettingsModal from './WhitelistSettingsModal.jsx';
import EmailDraftModal from './EmailDraftModal.jsx';
import AwaitingHumanModal from './AwaitingHumanModal.jsx';
import Onboarding from './Onboarding.jsx';
import UserProfileDropdown from './UserProfileDropdown.jsx';

function App() {
  const [currentUser, setCurrentUser] = useState(
    localStorage.getItem('userEmail') || ''
  );
  const [userProfile, setUserProfile] = useState(null);
  const [showUserDropdown, setShowUserDropdown] = useState(false);
  const [emails, setEmails] = useState([]);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [showDraftModal, setShowDraftModal] = useState(false);
  const [showWhitelistModal, setShowWhitelistModal] = useState(false);
  const [theme, setTheme] = useState(
    localStorage.getItem('theme') || 'dark'
  );
  const [draftPrompts, setDraftPrompts] = useState([
    {
      name: 'default',
      prompt: 'Provide concise and polite email drafts.',
    },
  ]);
  const [selectedDraft, setSelectedDraft] = useState(null);
  const [selectedAwaitingHuman, setSelectedAwaitingHuman] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [lastModified, setLastModified] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingEmails, setProcessingEmails] = useState(new Set());
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');

  // Fetch user profile when currentUser changes
  useEffect(() => {
    if (currentUser) {
      fetchUserProfile();
    }
  }, [currentUser]);

  const fetchUserProfile = async () => {
    try {
      const response = await fetch(`/api/user_profile?email=${encodeURIComponent(currentUser)}`);
      if (response.ok) {
        const profile = await response.json();
        setUserProfile(profile);
      } else {
        console.error('Failed to fetch user profile');
      }
    } catch (error) {
      console.error('Error fetching user profile:', error);
    }
  };

  const handleSignOut = async () => {
    try {
      const response = await fetch('/api/signout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: currentUser }),
      });
      
      if (response.ok) {
        localStorage.removeItem('userEmail');
        setCurrentUser('');
        setUserProfile(null);
        setShowUserDropdown(false);
        setEmails([]);
      } else {
        console.error('Failed to sign out');
      }
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  const updateUserProfile = async (newName) => {
    try {
      const response = await fetch('/api/update_user_profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: currentUser, name: newName }),
      });
      
      if (response.ok) {
        setUserProfile(prev => ({ ...prev, name: newName }));
        setShowUserDropdown(false);
      } else {
        console.error('Failed to update profile');
      }
    } catch (error) {
      console.error('Error updating profile:', error);
    }
  };

  useEffect(() => {
    if (!currentUser) return;
    
    const fetchEmails = async () => {
      setIsRefreshing(true);
      try {
        const response = await fetch('/api/emails');
        const data = await response.json();
        setEmails(data.emails || []);
        setLastModified(data.last_modified || '');
        setLastUpdated(new Date());
      } catch (err) {
        console.error('Failed to fetch emails', err);
      } finally {
        setIsRefreshing(false);
      }
    };

    const checkForUpdates = async () => {
      try {
        const response = await fetch('/api/emails/status');
        
        // If the status endpoint doesn't exist, fall back to full refresh
        if (!response.ok) {
          console.log('Status endpoint not available, falling back to full refresh');
          await fetchEmails();
          return;
        }
        
        const status = await response.json();
        
        // Only fetch full emails if there are changes
        if (status.last_modified !== lastModified) {
          console.log('New emails detected, refreshing...');
          await fetchEmails();
        }
      } catch (err) {
        console.error('Failed to check email status, falling back to full refresh:', err);
        // Fallback to full refresh if status check fails
        await fetchEmails();
      }
    };

    // Initial fetch
    fetchEmails();
    
    // Set up smart polling every 5 seconds
    const intervalId = setInterval(checkForUpdates, 5000);
    
    // Cleanup interval on unmount
    return () => clearInterval(intervalId);
  }, [currentUser, lastModified]);

  useEffect(() => {
    fetch('/api/draft_prompt')
      .then((res) => res.json())
      .then((data) =>
        setDraftPrompts([{ name: 'default', prompt: data.prompt || '' }])
      )
      .catch(() => {});
  }, []);

  useEffect(() => {
    // Load the reading system prompt
    fetch('/api/prompt')
      .then((res) => res.json())
      .then((data) => setSystemPrompt(data.prompt || ''))
      .catch(() => {});
  }, []);

  useEffect(() => {
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(theme === 'light' ? 'theme-light' : 'theme-dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  const unprocessedEmails = emails.filter((e) => !e.processed);
  const awaitingHumanEmails = emails.filter((e) => e.processed && e.draft && e.action !== 'sent');
  const processedEmails = emails.filter((e) => e.processed && (!e.draft || e.action === 'sent'));

  const saveSystemPrompt = async () => {
    try {
      const response = await fetch('/api/prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: systemPrompt }),
      });
      if (response.ok) {
        console.log('System prompt saved successfully');
      }
    } catch (error) {
      console.error('Failed to save system prompt:', error);
    }
  };

  const processUnprocessedEmails = async () => {
    setIsProcessing(true);
    
    // Mark all unprocessed emails as being processed
    const emailsToProcess = unprocessedEmails.map(e => e.id);
    setProcessingEmails(new Set(emailsToProcess));
    
    try {
      const response = await fetch('/api/process_unprocessed_emails', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (response.ok) {
        console.log(`Processed ${data.processed_count} emails`);
        console.log(`Remaining unprocessed: ${data.remaining_unprocessed || 0}`);
        
        // Refresh emails after processing
        const emailResponse = await fetch('/api/emails');
        const emailData = await emailResponse.json();
        setEmails(emailData.emails || []);
        setLastModified(emailData.last_modified || '');
        setLastUpdated(new Date());
      } else {
        // Handle API errors
        console.error('API Error:', data.error);
      }
    } catch (error) {
      console.error('Failed to process emails:', error);
    } finally {
      setIsProcessing(false);
      setProcessingEmails(new Set());
    }
  };

  const manualSync = async () => {
    setIsSyncing(true);
    setSyncMessage('');
    
    try {
      const response = await fetch('/api/manual_sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (response.ok) {
        const newEmailsCount = data.results.reduce((total, result) => total + (result.new_emails || 0), 0);
        if (newEmailsCount > 0) {
          setSyncMessage(`Found ${newEmailsCount} new email${newEmailsCount === 1 ? '' : 's'}!`);
          
          // Refresh emails after sync
          const emailResponse = await fetch('/api/emails');
          const emailData = await emailResponse.json();
          setEmails(emailData.emails || []);
          setLastModified(emailData.last_modified || '');
          setLastUpdated(new Date());
        } else {
          setSyncMessage('No new emails found');
        }
        
        // Clear message after 3 seconds
        setTimeout(() => setSyncMessage(''), 3000);
      } else {
        setSyncMessage('Sync failed');
        setTimeout(() => setSyncMessage(''), 3000);
      }
    } catch (error) {
      console.error('Failed to sync emails:', error);
      setSyncMessage('Sync failed');
      setTimeout(() => setSyncMessage(''), 3000);
    } finally {
      setIsSyncing(false);
    }
  };

  const getActionTag = (email) => {
    if (!email.action) return null;
    
    const action = email.action;
    
    // Handle individual action types
    if (action === 'sent') {
      return 'sent email';
    }
    if (action === 'archived') {
      return 'archived email';
    }
    if (action === 'reviewed (no action needed)') {
      return 'reviewed';
    }
    
    // Handle combined actions (e.g., "drafted, labeled 'work'")
    if (action.includes(',')) {
      const parts = action.split(',').map(part => part.trim());
      const tags = parts.map(part => {
        if (part === 'drafted') return 'drafted email';
        if (part === 'archived') return 'archived email';
        if (part.startsWith('labeled ')) return part.replace('labeled ', 'labeled: ');
        return part;
      });
      return tags.join(', ');
    }
    
    // Handle single actions
    if (action === 'drafted') {
      return 'drafted email';
    }
    if (action.startsWith('labeled ')) {
      return action.replace('labeled ', 'labeled: ');
    }
    if (action.startsWith('label:')) {
      return `labeled: ${action.substring(6)}`;
    }
    if (action.startsWith('added label')) {
      return action;
    }
    
    // Default case - return the action as-is
    return action;
  };

  const EmailItem = ({ email, showActions = false, isAwaitingHuman = false, onAwaitingHumanClick }) => {
    const isProcessingEmail = processingEmails.has(email.id);
    
    const handleClick = () => {
      if (isAwaitingHuman && onAwaitingHumanClick) {
        onAwaitingHumanClick(email);
      } else if (email.draft && !email.processed) {
        setSelectedDraft(email);
      }
    };
    
    return (
      <div
        className={`email-item ${email.processed ? 'processed' : 'unprocessed'} ${isProcessingEmail ? 'processing' : ''} ${isAwaitingHuman ? 'awaiting-human' : ''}`}
        onClick={handleClick}
      >
        <div className="email-header">
          <div className="subject">{email.subject}</div>
          {isProcessingEmail && (
            <div className="processing-indicator">
              <span className="loader">⏳</span>
              <span>Processing...</span>
            </div>
          )}
        </div>
        <div className="meta">
          <span className="from">{email.from}</span>
          <span className="timestamp">
            {new Date(email.date).toLocaleString()}
          </span>
        </div>
        {showActions && email.processed && (
          <div className="email-actions">
            {getActionTag(email) && (
              <span className="action-tag">{getActionTag(email)}</span>
            )}
            {email.draft && !email.action?.includes('drafted') && (
              <span className="action-tag">drafted email</span>
            )}
          </div>
        )}
        {isAwaitingHuman && (
          <div className="email-actions">
            {email.draft && (
              <span className="action-tag awaiting-tag">email drafted</span>
            )}
          </div>
        )}
      </div>
    );
  };

  if (!currentUser) {
    return (
      <div className="app">
        <Onboarding onComplete={setCurrentUser} />
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <h1>AgentMail</h1>
        <div className="profile">
          <div className="avatar">🤖</div>
          <div className="user-info" onClick={() => setShowUserDropdown(!showUserDropdown)}>
            <span className="name">{userProfile?.name || 'Loading...'}</span>
            <span className="dropdown-arrow">▼</span>
          </div>
          {showUserDropdown && (
            <UserProfileDropdown
              userProfile={userProfile}
              onClose={() => setShowUserDropdown(false)}
              onSignOut={handleSignOut}
              onUpdateProfile={updateUserProfile}
            />
          )}
          <button onClick={() => setShowDraftModal(true)}>Drafting Settings</button>
          <button onClick={() => setShowWhitelistModal(true)}>Whitelist Settings</button>
          <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
            {theme === 'light' ? 'Dark' : 'Light'} Theme
          </button>
        </div>
      </header>
      <div className="main-container">
        <aside className="left-panel">
          <h2>Email Reading Agent System Prompt</h2>
          <textarea
            className="system-input"
            rows={10}
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder="Enter instructions for how the AI should read and respond to emails..."
          />
          <button onClick={saveSystemPrompt} style={{ marginTop: '0.5rem' }}>
            Save Prompt
          </button>
          <button 
            onClick={processUnprocessedEmails} 
            disabled={isProcessing}
            style={{ marginTop: '0.5rem', marginLeft: '0.5rem' }}
          >
            {isProcessing ? 'Processing...' : 'Process Unprocessed Emails'}
          </button>
          <button 
            onClick={manualSync} 
            disabled={isSyncing}
            style={{ marginTop: '0.5rem', marginLeft: '0.5rem' }}
          >
            {isSyncing ? 'Syncing...' : 'Manual Sync'}
          </button>
          {syncMessage && (
            <div className="sync-message" style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: syncMessage.includes('Found') ? '#28a745' : '#666' }}>
              {syncMessage}
            </div>
          )}
          <h3>Available Tools</h3>
          <ul className="tools-list">
            <li>labelemail</li>
            <li>archiveemail</li>
            <li>draftemail</li>
          </ul>
        </aside>
        <section className="right-panel">
          <div className="inbox-header">
            <h2>Email Processing Dashboard</h2>
            <div className="inbox-status">
              {isRefreshing && <span className="refreshing">🔄 Refreshing...</span>}
              {isSyncing && <span className="refreshing">📬 Syncing...</span>}
              {syncMessage && !isSyncing && (
                <span className="sync-message" style={{ color: syncMessage.includes('Found') ? '#28a745' : '#666', fontSize: '0.85rem' }}>
                  {syncMessage}
                </span>
              )}
              {lastUpdated && (
                <span className="last-updated">
                  Last updated: {lastUpdated.toLocaleTimeString()}
                </span>
              )}
              <button 
                onClick={manualSync} 
                disabled={isSyncing}
                style={{ fontSize: '0.85rem', padding: '0.25rem 0.5rem' }}
              >
                {isSyncing ? 'Syncing...' : 'Get Updates'}
              </button>
            </div>
          </div>
          
          {/* Unprocessed Inbox Section */}
          <div className="inbox-section">
            <h3>Unprocessed Inbox ({unprocessedEmails.length})</h3>
            <div className="email-list">
              {unprocessedEmails.map((email) => (
                <EmailItem key={email.id} email={email} />
              ))}
              {unprocessedEmails.length === 0 && (
                <div className="empty-state">No unprocessed emails</div>
              )}
            </div>
          </div>

          {/* Awaiting Human Section */}
          <div className="inbox-section">
            <h3>Awaiting Human ({awaitingHumanEmails.length})</h3>
            <div className="email-list">
              {awaitingHumanEmails.map((email) => (
                <EmailItem key={email.id} email={email} isAwaitingHuman={true} onAwaitingHumanClick={(e) => setSelectedAwaitingHuman(e)} />
              ))}
              {awaitingHumanEmails.length === 0 && (
                <div className="empty-state">No emails awaiting human review</div>
              )}
            </div>
          </div>

          {/* Processed Inbox Section */}
          <div className="inbox-section">
            <h3>Processed Inbox ({processedEmails.length})</h3>
            <div className="email-list">
              {processedEmails.map((email) => (
                <EmailItem key={email.id} email={email} showActions={true} />
              ))}
              {processedEmails.length === 0 && (
                <div className="empty-state">No processed emails</div>
              )}
            </div>
          </div>
        </section>
      </div>
      
      {showDraftModal && (
        <DraftingSettingsModal
          isOpen={showDraftModal}
          onClose={() => setShowDraftModal(false)}
          prompts={draftPrompts}
          setPrompts={setDraftPrompts}
        />
      )}
      {showWhitelistModal && (
        <WhitelistSettingsModal
          isOpen={showWhitelistModal}
          onClose={() => setShowWhitelistModal(false)}
        />
      )}
      {selectedDraft && (
        <EmailDraftModal
          isOpen={!!selectedDraft}
          onClose={() => setSelectedDraft(null)}
          email={selectedDraft}
          onSend={async (text) => {
            await fetch('/api/send', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: selectedDraft.id, draft: text }),
            });
            setSelectedDraft(null);
            
            // Force refresh after sending
            setLastModified('');
            const response = await fetch('/api/emails');
            const data = await response.json();
            setEmails(data.emails || []);
            setLastModified(data.last_modified || '');
            setLastUpdated(new Date());
          }}
        />
      )}
      {selectedAwaitingHuman && (
        <AwaitingHumanModal
          isOpen={!!selectedAwaitingHuman}
          onClose={() => setSelectedAwaitingHuman(null)}
          email={selectedAwaitingHuman}
          onSend={async (draftText) => {
            await fetch('/api/send', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: selectedAwaitingHuman.id, draft: draftText }),
            });
            setSelectedAwaitingHuman(null);
            
            // Force refresh after sending
            setLastModified('');
            const response = await fetch('/api/emails');
            const data = await response.json();
            setEmails(data.emails || []);
            setLastModified(data.last_modified || '');
            setLastUpdated(new Date());
          }}
          onDelete={async (emailId) => {
            // Mark as processed with no action and remove draft
            await fetch('/api/delete_draft', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ email_id: emailId }),
            });
            setSelectedAwaitingHuman(null);
            
            // Force refresh after deleting
            setLastModified('');
            const response = await fetch('/api/emails');
            const data = await response.json();
            setEmails(data.emails || []);
            setLastModified(data.last_modified || '');
            setLastUpdated(new Date());
          }}
          onRerun={async (emailId) => {
            // Force refresh after rerunning
            setLastModified('');
            const response = await fetch('/api/emails');
            const data = await response.json();
            setEmails(data.emails || []);
            setLastModified(data.last_modified || '');
            setLastUpdated(new Date());
          }}
        />
      )}
    </div>
  );
}

export default App;
