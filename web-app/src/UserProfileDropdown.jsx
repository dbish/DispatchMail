import { useState, useEffect, useRef } from 'react';
import './UserProfileDropdown.css';

export default function UserProfileDropdown({ userProfile, onClose, onSignOut, onUpdateProfile }) {
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState(userProfile?.name || '');
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [onClose]);

  const handleSaveName = () => {
    if (editedName.trim() && editedName !== userProfile?.name) {
      onUpdateProfile(editedName.trim());
    }
    setIsEditingName(false);
  };

  const handleCancelEdit = () => {
    setEditedName(userProfile?.name || '');
    setIsEditingName(false);
  };

  if (!userProfile) return null;

  return (
    <div className="user-profile-dropdown" ref={dropdownRef}>
      <div className="profile-header">
        <img className="profile-avatar" src="/vite.svg" alt="Profile" />
        <div className="profile-info">
          {isEditingName ? (
            <div className="name-edit">
              <input
                type="text"
                value={editedName}
                onChange={(e) => setEditedName(e.target.value)}
                className="name-input"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveName();
                  if (e.key === 'Escape') handleCancelEdit();
                }}
              />
              <div className="name-edit-buttons">
                <button className="save-btn" onClick={handleSaveName}>
                  ✓
                </button>
                <button className="cancel-btn" onClick={handleCancelEdit}>
                  ✕
                </button>
              </div>
            </div>
          ) : (
            <div className="name-display" onClick={() => setIsEditingName(true)}>
              <span className="profile-name">{userProfile.name}</span>
              <span className="edit-icon">✎</span>
            </div>
          )}
          <div className="profile-email">{userProfile.email}</div>
        </div>
      </div>
      
      <div className="profile-actions">
        <button className="action-btn profile-btn" onClick={() => setIsEditingName(true)}>
          Edit Name
        </button>
        <button className="action-btn signout-btn" onClick={onSignOut}>
          Sign Out
        </button>
      </div>
    </div>
  );
} 