import { useEffect, useState } from 'react';
import './App.css';
import DraftingSettingsModal from './DraftingSettingsModal.jsx';
import WhitelistSettingsModal from './WhitelistSettingsModal.jsx';
import EmailDraftModal from './EmailDraftModal.jsx';
import AwaitingHumanModal from './AwaitingHumanModal.jsx';
import ProcessedEmailModal from './ProcessedEmailModal.jsx';
import Onboarding from './Onboarding.jsx';
import UserSelector from './UserSelector.jsx';
import UserProfileDropdown from './UserProfileDropdown.jsx';

function App() {
  const [currentUser, setCurrentUser] = useState(() => {
    const stored = localStorage.getItem('userEmail');
    return stored || '';
  });
  const [userProfile, setUserProfile] = useState(null);
  const [showUserDropdown, setShowUserDropdown] = useState(false);
  const [emails, setEmails] = useState([]);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [showDraftModal, setShowDraftModal] = useState(false);
  const [showWhitelistModal, setShowWhitelistModal] = useState(false);
  // Static dark theme - no theme switching
  const theme = 'dark';
  const [draftPrompts, setDraftPrompts] = useState([
    {
      name: 'default',
      prompt: 'Provide concise and polite email drafts.',
    },
  ]);
  const [selectedDraft, setSelectedDraft] = useState(null);
  const [selectedAwaitingHuman, setSelectedAwaitingHuman] = useState(null);
  const [selectedProcessedEmail, setSelectedProcessedEmail] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [lastModified, setLastModified] = useState('');
  const [lastCounts, setLastCounts] = useState({
    unprocessed_count: 0,
    awaiting_human_count: 0,
    processed_count: 0
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [isCheckingForUpdates, setIsCheckingForUpdates] = useState(false);
  
  // New state for user selection flow
  const [availableUsers, setAvailableUsers] = useState([]);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [usersLoaded, setUsersLoaded] = useState(false);

  // Fetch available users when there's no current user
  useEffect(() => {
    if (!currentUser && !usersLoaded) {
      fetchAvailableUsers();
    }
  }, [currentUser, usersLoaded]);

  const fetchAvailableUsers = async () => {
    try {
      const response = await fetch('/api/users');
      if (response.ok) {
        const userData = await response.json();
        setAvailableUsers(userData);
        setUsersLoaded(true);
        
        // If no users exist, show onboarding immediately
        if (userData.length === 0) {
          setShowOnboarding(true);
        }
      } else {
        console.error('Failed to fetch users');
        setShowOnboarding(true); // Fallback to onboarding
      }
    } catch (error) {
      console.error('Error fetching users:', error);
      setShowOnboarding(true); // Fallback to onboarding
    }
  };

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
        setLastCounts({
          unprocessed_count: 0,
          awaiting_human_count: 0,
          processed_count: 0
        });
        setShowOnboarding(false);
        setUsersLoaded(false); // Reset to refetch users
      } else {
        console.error('Failed to sign out');
      }
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  const handleOnboardingComplete = (email) => {
    setCurrentUser(email);
    setShowOnboarding(false);
    setUsersLoaded(false); // Reset to refetch users
  };

  const handleAddNewAccount = () => {
    setShowOnboarding(true);
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
        const emailsData = data.emails || [];
        updateEmailsAndCounts(emailsData, data.last_modified);
        setLastUpdated(new Date());
      } catch (err) {
        console.error('Failed to fetch emails', err);
      } finally {
        setIsRefreshing(false);
      }
    };

    const checkForUpdates = async () => {
      // Prevent multiple concurrent update checks
      if (isRefreshing || isCheckingForUpdates) {
        return;
      }
      
      setIsCheckingForUpdates(true);
      
      try {
        const response = await fetch('/api/emails/status');
        
        // If the status endpoint doesn't exist, just skip this check
        if (!response.ok) {
          console.log('Status endpoint not available, skipping update check');
          return;
        }
        
        const status = await response.json();
        
        // Check if there are actual changes in the counts that matter
        const countsChanged = (
          status.unprocessed_count !== lastCounts.unprocessed_count ||
          status.awaiting_human_count !== lastCounts.awaiting_human_count ||
          status.processed_count !== lastCounts.processed_count
        );
        
        // Add debugging to understand when false positives occur
        if (countsChanged) {
          console.log('Count comparison:', {
            current: {
              unprocessed: status.unprocessed_count,
              awaiting: status.awaiting_human_count,
              processed: status.processed_count
            },
            previous: {
              unprocessed: lastCounts.unprocessed_count,
              awaiting: lastCounts.awaiting_human_count,
              processed: lastCounts.processed_count
            }
          });
        }
        
        // Only refresh if there are meaningful changes AND we have valid previous counts
        // (avoid false positives on first load when lastCounts might be zero)
        const hasValidPreviousCounts = (
          lastCounts.unprocessed_count + lastCounts.awaiting_human_count + lastCounts.processed_count > 0
        );
        
        if (countsChanged && hasValidPreviousCounts) {
          console.log('Email counts changed, refreshing...');
          await fetchEmails();
        } else if (!lastModified) {
          // Only refresh on empty lastModified if we don't have valid counts yet
          console.log('No lastModified, doing initial refresh...');
          await fetchEmails();
        }
      } catch (err) {
        console.error('Failed to check email status:', err);
        // Don't fallback to full refresh on error - just skip this check
      } finally {
        setIsCheckingForUpdates(false);
      }
    };

    // Initial fetch
    fetchEmails();
    
    // Set up smart polling every 2 minutes, but only if we have a current user
    const intervalId = setInterval(checkForUpdates, 120000); // 2 minutes
    
    // Cleanup interval on unmount
    return () => clearInterval(intervalId);
  }, [currentUser]);

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

  // Static dark theme - no theme switching needed

  // Helper function to update emails and counts consistently
  const updateEmailsAndCounts = (emailsData, lastModifiedValue) => {
    setEmails(emailsData);
    setLastModified(lastModifiedValue || '');
    
    // Update counts for comparison
    const unprocessedCount = emailsData.filter(e => !e.processed).length;
    const awaitingHumanCount = emailsData.filter(e => e.processed && e.action === 'drafted').length;
    const processedCount = emailsData.filter(e => e.processed && e.action !== 'drafted').length;
    
    setLastCounts({
      unprocessed_count: unprocessedCount,
      awaiting_human_count: awaitingHumanCount,
      processed_count: processedCount
    });
  };

  // Single inbox with all emails, sorted by priority and date
  const allEmails = emails.sort((a, b) => {
    // First priority: unprocessed emails come first
    const aUnprocessed = !a.processed;
    const bUnprocessed = !b.processed;
    
    if (aUnprocessed && !bUnprocessed) return -1; // a comes first
    if (!aUnprocessed && bUnprocessed) return 1;  // b comes first
    
    // Second priority: within same processed status, sort by date (newest first)
    const dateA = new Date(a.date);
    const dateB = new Date(b.date);
    return dateB - dateA; // Reverse chronological order (newest first)
  });

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
    
    try {
      const response = await fetch('/api/process_unprocessed_emails', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (response.ok) {
        console.log(`Processed ${data.processed_count} emails (batch of ${data.batch_size})`);
        console.log(`Remaining unprocessed: ${data.remaining_unprocessed || 0}`);
        
        // Refresh emails after processing
        const emailResponse = await fetch('/api/emails');
        const emailData = await emailResponse.json();
        updateEmailsAndCounts(emailData.emails || [], emailData.last_modified);
        setLastUpdated(new Date());
      } else {
        // Handle API errors
        console.error('API Error:', data.error);
      }
    } catch (error) {
      console.error('Failed to process emails:', error);
    } finally {
      setIsProcessing(false);
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
          updateEmailsAndCounts(emailData.emails || [], emailData.last_modified);
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
    if (email.action === 'sent') return 'sent';
    if (email.action === 'archived') return 'archived';
    if (email.action === 'drafted') return 'drafted';
    if (email.action === 'reviewed (no action needed)') return 'reviewed';
    if (email.action && email.action.startsWith('labeled')) return email.action;
    if (email.action && email.action.includes('labeled')) return email.action;
    // Show any other action that exists
    if (email.action && email.action.trim()) return email.action;
    return null;
  };

  const EmailItem = ({ email }) => {
    const isProcessingEmail = email.processing === true;
    const isAwaitingHuman = email.processed && email.action === 'drafted';
    const isProcessed = email.processed && email.action !== 'drafted';
    const isUnprocessed = !email.processed;
    
    const handleClick = () => {
      if (isAwaitingHuman) {
        setSelectedAwaitingHuman(email);
      } else if (isProcessed) {
        setSelectedProcessedEmail(email);
      } else if (email.draft && !email.processed) {
        setSelectedDraft(email);
      }
    };

    const getStatusLabel = () => {
      if (isProcessingEmail) return { text: 'Processing...', type: 'processing' };
      if (isUnprocessed) return { text: 'Unprocessed', type: 'unprocessed' };
      if (isAwaitingHuman) return { text: 'Awaiting Review', type: 'awaiting' };
      if (isProcessed) return { text: getActionTag(email) || 'Processed', type: 'processed' };
      return { text: 'Unknown', type: 'unknown' };
    };

    const status = getStatusLabel();
    
    return (
      <div
        className={`email-item ${status.type} ${isProcessingEmail ? 'processing' : ''}`}
        onClick={handleClick}
      >
        <div className="email-header">
          <div className="subject">{email.subject}</div>
          <div className="status-label">
            <span className={`status-tag ${status.type}`}>{status.text}</span>
          </div>
        </div>
        <div className="meta">
          <span className="from">{email.from}</span>
          <span className="timestamp">
            {new Date(email.date).toLocaleString()}
          </span>
        </div>
        {email.draft && isAwaitingHuman && (
          <div className="email-actions">
            <span className="action-tag awaiting-tag">Draft Available</span>
          </div>
        )}
      </div>
    );
  };

  // Show onboarding if explicitly requested or if no users exist
  if (showOnboarding || (!currentUser && usersLoaded && availableUsers.length === 0)) {
    return (
      <div className="app">
        <Onboarding onComplete={handleOnboardingComplete} />
      </div>
    );
  }

  // Show user selector if no current user but users exist
  if (!currentUser && usersLoaded && availableUsers.length > 0) {
    return (
      <div className="app">
        <UserSelector 
          onComplete={setCurrentUser} 
          onAddNew={handleAddNewAccount}
        />
      </div>
    );
  }

  // Show loading while fetching users
  if (!currentUser && !usersLoaded) {
    return (
      <div className="app">
        <div className="loading">Loading...</div>
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
            <span className="name">{userProfile?.name || userProfile?.email || 'Loading...'}</span>
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
            {isProcessing ? 'Processing...' : 
             allEmails.filter(e => !e.processed).length > 0 ? 
               `Process Next ${Math.min(5, allEmails.filter(e => !e.processed).length)} Emails` : 
               'Process Unprocessed Emails'}
          </button>
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
          
          {/* Single Inbox Section */}
          <div className="inbox-section">
            <h3>Inbox ({allEmails.length})</h3>
            <div className="email-list">
              {allEmails.map((email) => (
                <EmailItem key={email.message_id} email={email} />
              ))}
              {allEmails.length === 0 && (
                <div className="empty-state">No emails found</div>
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
                      onResetSuccess={() => {
              // Clear lastModified state and counts after successful reset
              setLastModified('');
              setLastCounts({
                unprocessed_count: 0,
                awaiting_human_count: 0,
                processed_count: 0
              });
              // Force immediate refresh
              const fetchEmails = async () => {
                const response = await fetch('/api/emails');
                const data = await response.json();
                updateEmailsAndCounts(data.emails || [], data.last_modified);
                setLastUpdated(new Date());
              };
              fetchEmails();
            }}
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
            updateEmailsAndCounts(data.emails || [], data.last_modified);
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
              body: JSON.stringify({ id: selectedAwaitingHuman.message_id, draft: draftText }),
            });
            setSelectedAwaitingHuman(null);
            
            // Force refresh after sending
            setLastModified('');
            const response = await fetch('/api/emails');
            const data = await response.json();
            updateEmailsAndCounts(data.emails || [], data.last_modified);
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
            updateEmailsAndCounts(data.emails || [], data.last_modified);
            setLastUpdated(new Date());
          }}
          onRerun={async () => {
            // Force refresh after rerunning
            setLastModified('');
            const response = await fetch('/api/emails');
            const data = await response.json();
            updateEmailsAndCounts(data.emails || [], data.last_modified);
            setLastUpdated(new Date());
          }}
        />
      )}
      {selectedProcessedEmail && (
        <ProcessedEmailModal
          isOpen={!!selectedProcessedEmail}
          onClose={() => setSelectedProcessedEmail(null)}
          email={selectedProcessedEmail}
          onSend={async (draftText) => {
            await fetch('/api/send', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: selectedProcessedEmail.message_id, draft: draftText }),
            });
            setSelectedProcessedEmail(null);
            
            // Force refresh after sending
            setLastModified('');
            const response = await fetch('/api/emails');
            const data = await response.json();
            updateEmailsAndCounts(data.emails || [], data.last_modified);
            setLastUpdated(new Date());
          }}
        />
      )}
    </div>
  );
}

export default App;
