import { useEffect, useState } from 'react';
import './App.css';
import EmailReadingModal from './EmailReadingModal.jsx';
import ThinDraftingSettingsModal from './ThinDraftingSettingsModal.jsx';
import ThinWhitelistModal from './ThinWhitelistModal.jsx';
import EmailDraftModal from './EmailDraftModal.jsx';
import AwaitingHumanModal from './AwaitingHumanModal.jsx';
import ProcessedEmailModal from './ProcessedEmailModal.jsx';
import ProcessingModal from './ProcessingModal.jsx';
import Onboarding from './Onboarding.jsx';
import UserSelector from './UserSelector.jsx';
import UserProfileDropdown from './UserProfileDropdown.jsx';

// Component to handle tag display with +N indicator
const TagsList = ({ tags, maxVisible = 1 }) => {
  const [showAll, setShowAll] = useState(false);
  
  if (!tags || tags.length === 0) return null;
  
  const visibleTags = showAll ? tags : tags.slice(0, maxVisible);
  const remainingCount = tags.length - maxVisible;
  
  return (
    <div 
      className="email-tags"
      onMouseEnter={() => setShowAll(true)}
      onMouseLeave={() => setShowAll(false)}
    >
      {visibleTags.map((tag, index) => (
        <span key={index} className="email-tag">{tag}</span>
      ))}
      {!showAll && remainingCount > 0 && (
        <span className="email-tag email-tag-more">+{remainingCount}</span>
      )}
    </div>
  );
};

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
  const [showProcessingModal, setShowProcessingModal] = useState(false);

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

  // Tab state for email filtering
  const [activeTab, setActiveTab] = useState('inbox');
  
  // Filter state
  const [showFilterDropdown, setShowFilterDropdown] = useState(false);
  const [activeFilter, setActiveFilter] = useState('all');

  // Close filter dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showFilterDropdown && !event.target.closest('.filter-container')) {
        setShowFilterDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showFilterDropdown]);

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
    const fetchEmails = async () => {
      setIsRefreshing(true);
      try {
        const response = await fetch('/api/emails');
        const data = await response.json();
        console.log('Data:', data);
        const emailsData = data || [];
        console.log('Emails data:', emailsData);
        updateEmailsAndCounts(emailsData, data.last_modified);
        console.log('Last updated:', new Date());
        setLastUpdated(new Date());
      } catch (err) {
        console.error('Failed to fetch emails', err);
      } finally {
        setIsRefreshing(false);
      }
    };

    if (currentUser) {
      fetchUserProfile();
      fetchEmails();//manualSync();
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
      console.log('Fetching emails');
      setIsRefreshing(true);
      try {
        const response = await fetch('/api/emails');
        console.log('Response:', response);
        const data = await response.json();
        console.log('Data:', data);
        const emailsData = data || [];
        console.log('Emails data:', emailsData);
        updateEmailsAndCounts(emailsData, data.last_modified);
        console.log('Last updated:', new Date());
        setLastUpdated(new Date());
      } catch (err) {
        console.error('Failed to fetch emails', err);
      } finally {
        setIsRefreshing(false);
      }
    };

    const _checkForUpdates = async () => {
      console.log('Checking for updates');
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
    //const intervalId = setInterval(_checkForUpdates, 120000); // 2 minutes
    
    // Cleanup interval on unmount
    return () => {
      //clearInterval(intervalId);
    };
  }, [currentUser]);



  useEffect(() => {
    // Load the reading system prompt
    fetch('/api/custom_prompt?type=processing')
      .then((res) => res.json())
      .then((data) => setSystemPrompt(data.prompt || ''))
      .catch(() => {});
  }, []);

  // Static dark theme - no theme switching needed

  // Helper function to update emails and counts consistently
  const updateEmailsAndCounts = (emailsData, lastModifiedValue) => {
    console.log('Updating emails and counts');
    console.log(emailsData);
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

  const deltaUpdateEmails = (emailsData, lastModifiedValue) => {
    console.log('Delta updating emails and counts');
    console.log(emailsData);
    //update emails
    for (const email of emailsData) {
      const index = emails.findIndex(e => e.id === email.id);
      if (index !== -1) {
        emails[index] = email;
      }
    }
    setLastModified(lastModifiedValue || '');
  };

  // Get available filters based on email data
  const getAvailableFilters = () => {
    const filters = [
      { id: 'all', label: 'All Emails', count: emails.length },
      { id: 'unprocessed', label: 'Unprocessed', count: emails.filter(e => !e.processed).length },
      { id: 'awaiting_review', label: 'Awaiting Review', count: emails.filter(e => e.processed && e.state && e.state.includes('drafted_response')).length },
      { id: 'sent', label: 'Sent', count: emails.filter(e => e.state && e.state.includes('sent')).length },
      { id: 'archived', label: 'Archived', count: emails.filter(e => e.state && e.state.includes('archived')).length },
      { id: 'tagged', label: 'Tagged', count: emails.filter(e => e.state && e.state.includes('tagged')).length }
    ];

    // Add custom action-based filters
    const customActions = new Set();
    emails.forEach(email => {
      if (email.action && typeof email.action === 'string' && email.action.trim()) {
        customActions.add(email.action.toLowerCase());
      }
    });

    customActions.forEach(action => {
      const count = emails.filter(e => e.action && e.action.toLowerCase() === action).length;
      if (count > 0) {
        filters.push({
          id: `action_${action}`,
          label: action.charAt(0).toUpperCase() + action.slice(1),
          count: count
        });
      }
    });

    return filters;
  };

  // Filter emails based on active tab and filter
  const getFilteredEmails = () => {
    const sortedEmails = emails.sort((a, b) => {
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

    // First apply tab filtering
    let tabFilteredEmails;
    switch (activeTab) {
      case 'inbox':
        // Inbox: everything except Promotion, Ignore, or Archived
        tabFilteredEmails = sortedEmails.filter(email => {
          const action = (email.action && typeof email.action === 'string') ? email.action.toLowerCase() : '';
          const isArchived = email.state && email.state.includes('archived');
          return !action.includes('promotion') && !action.includes('ignore') && !isArchived;
        });
        break;
      case 'all':
        // All Mail: show everything
        tabFilteredEmails = sortedEmails;
        break;
      case 'meh':
        // Filtered: Promotion, Ignore, and Archived emails
        tabFilteredEmails = sortedEmails.filter(email => {
          const action = (email.action && typeof email.action === 'string') ? email.action.toLowerCase() : '';
          const isArchived = email.state && email.state.includes('archived');
          return action.includes('promotion') || action.includes('ignore') || isArchived;
        });
        break;
      default:
        tabFilteredEmails = sortedEmails;
    }

    // Then apply additional filter
    if (activeFilter === 'all') {
      return tabFilteredEmails;
    }

    return tabFilteredEmails.filter(email => {
      switch (activeFilter) {
        case 'unprocessed':
          return !email.processed;
        case 'awaiting_review':
          return email.processed && email.state && email.state.includes('drafted_response');
        case 'sent':
          return email.state && email.state.includes('sent');
        case 'archived':
          return email.state && email.state.includes('archived');
        case 'tagged':
          return email.state && email.state.includes('tagged');
        default:
          // Handle custom action filters
          if (activeFilter.startsWith('action_')) {
            const actionName = activeFilter.replace('action_', '');
            return email.action && email.action.toLowerCase() === actionName;
          }
          return true;
      }
    });
  };

  const allEmails = getFilteredEmails();

  const saveSystemPrompt = async () => {
    try {
      const response = await fetch('/api/custom_prompt?type=processing', {
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

  const processUnprocessedEmails = async (shouldContinue = false) => {
    console.log('Processing emails');
    setIsProcessing(true);
    
    try {
      const response = await fetch(`/api/process_emails?paging=${shouldContinue ? 'true' : 'false'}`);
      const data = await response.json();
      console.log('Data:', data);

      if (data.state === 'done') {
        setIsProcessing(false);
        setShowProcessingModal(false);
      } else {
        const emailData = data.batch;
        deltaUpdateEmails(emailData || [], '');
        setLastUpdated(new Date());
        processUnprocessedEmails(true);
      }
    } catch (error) {
      console.error('Failed to process emails:', error);
      setIsProcessing(false);
      setShowProcessingModal(false);
    }
  };

  const handleProcessAllEmails = async () => {
    // This is a no-op for now as requested
    setIsProcessing(true);
    setShowProcessingModal(false);
    try {
      const response = await fetch('/api/reprocess_all');
      const data = await response.json();
      console.log('Data:', data);
      if (data.state === 'done') {
        setIsProcessing(false);
        setShowProcessingModal(false);
      } else {
        const emailData = data.batch;
        deltaUpdateEmails(emailData || [], '');
        setLastUpdated(new Date());
        processUnprocessedEmails(true);
      }
    } catch (error) {
      console.error('Failed to reprocess all emails:', error);
    } finally {
      setIsProcessing(false);
    }
    
  };

  const manualSync = async () => {
    setIsSyncing(true);
    setSyncMessage('');
    
    try {
      const emailResponse = await fetch('/api/get_updates');
      console.log('Email response:', emailResponse);
      const emailData = await emailResponse.json();
      console.log('Email data:', emailData);
      updateEmailsAndCounts(emailData || [], '');
      setLastUpdated(new Date());
        // Clear message after 3 seconds
      setTimeout(() => setSyncMessage(''), 3000);
    } catch (error) {
      console.error('Failed to sync emails:', error);
      setSyncMessage('Sync failed');
      setTimeout(() => setSyncMessage(''), 3000);
    } finally {
      setIsSyncing(false);
    }
  };

  const getActionTag = (email) => {
    if (email.state && email.state.length > 0) {
      if (email.state.includes('sent')) return 'sent';
      if (email.state.includes('archived')) return 'archived';
      if (email.state.includes('drafted_response')) return 'drafted';
      if (email.state.includes('reviewed (no action needed)')) return 'reviewed';
      if (email.state.includes('labeled')) return email.state;
    }
    return null;
  };

  const EmailItem = ({ email }) => {
    const isProcessingEmail = email.processing === true;
    const isDrafted = email.state.includes('drafted_response');
    const isSent = email.state.includes('sent');
    const isAwaitingHuman = email.processed && isDrafted && !isSent;
    const isProcessed = email.processed && !isDrafted;
    const isUnprocessed = !email.processed;
    
    const handleClick = () => {
      if (isAwaitingHuman) {
        setSelectedAwaitingHuman(email);
      } else if (isProcessed) {
        setSelectedProcessedEmail(email);
      } else if (email.drafted_response && !email.processed) {
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
    
    // Get preview of message content
    const getMessagePreview = () => {
      if (email.body && typeof email.body === 'string') {
        const text = email.body.replace(/<[^>]*>/g, '').trim();
        return text.length > 100 ? text.substring(0, 100) + '...' : text;
      }
      return '';
    };
    
    return (
      <div
        className={`email-item-compact ${status.type} ${isProcessingEmail ? 'processing' : ''}`}
        onClick={handleClick}
      >
        <div className="email-content">
          <span className="sender-name">{email.from || 'Unknown'}</span>
          <span className="email-separator">•</span>
          <span className="email-subject">{email.subject || 'No Subject'}</span>
          {getMessagePreview() && (
            <span className="email-preview">{getMessagePreview()}</span>
          )}
        </div>
        <TagsList tags={email.tags} maxVisible={1} />
        <div className="email-status">
          <span className={`status-tag-compact ${status.type}`}>{status.text}</span>
        </div>
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
        <h1>Dispatch Mail</h1>
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
        <aside className="left-panel-narrow">
          <h2>Email Reading Agent System Prompt</h2>
          <textarea
            className="system-input"
            rows={8}
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder="Enter instructions for how the AI should read and respond to emails..."
          />
          <button onClick={saveSystemPrompt} style={{ marginTop: '0.5rem' }}>
            Save Prompt
          </button>
          <button 
            onClick={() => setShowProcessingModal(true)} 
            disabled={isProcessing}
            className="secondary-cta-btn"
            style={{ marginTop: '0.5rem', marginLeft: '0.5rem' }}
          >
            {isProcessing ? 'Processing...' : 'Process Emails'}
          </button>
          <h3 style={{ marginTop: '1.5rem' }}>Available Tools</h3>
          <ul className="tools-list">
            <li>labelemail</li>
            <li>archiveemail</li>
            <li>draftemail</li>
          </ul>
        </aside>
        <section className="right-panel">
          <div className="inbox-header">
            <div className="inbox-actions">
              <div className="filter-container">
                <button 
                  className={`action-icon ${activeFilter !== 'all' ? 'active' : ''}`} 
                  title={`Filter (${showFilterDropdown ? 'Open' : 'Closed'})`}
                  onClick={() => {
                    console.log('Filter clicked, current state:', showFilterDropdown, 'emails count:', emails.length);
                    setShowFilterDropdown(!showFilterDropdown);
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="22,3 2,3 10,12.46 10,19 14,21 14,12.46"/>
                  </svg>
                </button>
                {showFilterDropdown && (
                  <div className="filter-dropdown">
                    {getAvailableFilters().map(filter => (
                      <button
                        key={filter.id}
                        className={`filter-option ${activeFilter === filter.id ? 'active' : ''}`}
                        onClick={() => {
                          setActiveFilter(filter.id);
                          setShowFilterDropdown(false);
                        }}
                      >
                        <span className="filter-label">{filter.label}</span>
                        <span className="filter-count">({filter.count})</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
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
          
          {/* Email Tabs */}
          <div className="email-tabs">
            <button 
              className={`tab-button ${activeTab === 'inbox' ? 'active' : ''}`}
              onClick={() => setActiveTab('inbox')}
            >
              Inbox ({emails.filter(email => {
                const action = (email.action && typeof email.action === 'string') ? email.action.toLowerCase() : '';
                const isArchived = email.state && email.state.includes('archived');
                return !action.includes('promotion') && !action.includes('ignore') && !isArchived;
              }).length})
            </button>
            <button 
              className={`tab-button ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              All Mail ({emails.length})
            </button>
            <button 
              className={`tab-button ${activeTab === 'meh' ? 'active' : ''}`}
              onClick={() => setActiveTab('meh')}
            >
              Filtered ({emails.filter(email => {
                const action = (email.action && typeof email.action === 'string') ? email.action.toLowerCase() : '';
                const isArchived = email.state && email.state.includes('archived');
                return action.includes('promotion') || action.includes('ignore') || isArchived;
              }).length})
            </button>
          </div>
          
          {/* Email List */}
          <div className="inbox-section">
            <div className="email-list">
              {allEmails.map((email) => (
                <EmailItem key={email.id} email={email} />
              ))}
              {allEmails.length === 0 && (
                <div className="empty-state">No emails found</div>
              )}
            </div>
          </div>
        </section>
      </div>
      
      {showDraftModal && (
        <ThinDraftingSettingsModal
          isOpen={showDraftModal}
          onClose={() => setShowDraftModal(false)}
          onResetSuccess={() => {
            // Force refresh after saving settings
            const fetchEmails = async () => {
              console.log('Fetching emails after settings update');
              const response = await fetch('/api/get_updates');
              const data = await response.json();
              updateEmailsAndCounts(data || [], data.last_modified);
              setLastUpdated(new Date());
            };
            fetchEmails();
          }}
        />
      )}
      {showWhitelistModal && (
        <ThinWhitelistModal
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
                console.log('Fetching emails after reset');
                const response = await fetch('/api/emails');
                const data = await response.json();
                updateEmailsAndCounts(data || [], data.last_modified);
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
            console.log('Fetching emails after sending');
            const response = await fetch('/api/emails');
            const data = await response.json();
            updateEmailsAndCounts(data || [], data.last_modified);
            setLastUpdated(new Date());
          }}
          onDelete={async (emailId) => {
            // Mark as processed with no action and remove draft
            await fetch('/api/delete_draft', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ email_id: emailId }),
            });
            setSelectedDraft(null);
            
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
            updateEmailsAndCounts(data || [], data.last_modified);
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
              body: JSON.stringify({ id: selectedProcessedEmail.id, draft: draftText }),
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
      
      {showProcessingModal && (
        <ProcessingModal
          isOpen={showProcessingModal}
          onClose={() => setShowProcessingModal(false)}
          onProcessUnprocessed={() => processUnprocessedEmails(false)}
          onProcessAll={handleProcessAllEmails}
        />
      )}
    </div>
  );
}

export default App;
