import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, KeyRound, X, Eye, EyeOff, AlertCircle, Check, Settings, Shield } from 'lucide-react';
import api from '../api/client';

/**
 * Profile Settings - Full screen centered overlay
 * Rendered at App level to ensure it's centered on screen
 */
export default function ProfileSettings({ user, onClose, onUpdate }) {
  const [activeTab, setActiveTab] = useState('username');
  
  // Username change state
  const [newUsername, setNewUsername] = useState(user.username);
  const [usernamePassword, setUsernamePassword] = useState('');
  const [showUsernamePassword, setShowUsernamePassword] = useState(false);
  
  // Password change state
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  
  // Common state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleChangeUsername = async () => {
    setError('');
    setSuccess('');
    
    if (!newUsername.trim()) {
      setError('Username is required');
      return;
    }
    
    if (newUsername.trim().length < 3) {
      setError('Username must be at least 3 characters');
      return;
    }
    
    if (!usernamePassword) {
      setError('Please enter your current password to confirm');
      return;
    }
    
    if (newUsername === user.username) {
      setError('New username is the same as current');
      return;
    }

    setSaving(true);
    try {
      const res = await api.put('/auth/profile/username', {
        new_username: newUsername.trim(),
        current_password: usernamePassword
      });
      setSuccess('Username changed successfully!');
      setUsernamePassword('');
      
      setTimeout(() => {
        onUpdate(res.data);
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to change username');
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    setError('');
    setSuccess('');
    
    if (!oldPassword) {
      setError('Current password is required');
      return;
    }
    
    if (!newPassword) {
      setError('New password is required');
      return;
    }
    
    if (newPassword.length < 4) {
      setError('New password must be at least 4 characters');
      return;
    }
    
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match');
      return;
    }
    
    if (oldPassword === newPassword) {
      setError('New password must be different from current password');
      return;
    }

    setSaving(true);
    try {
      await api.put('/auth/profile/password', {
        current_password: oldPassword,
        new_password: newPassword
      });
      setSuccess('Password changed successfully!');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to change password');
    } finally {
      setSaving(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-md flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div 
        initial={{ scale: 0.9, opacity: 0 }} 
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="w-full max-w-lg bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <Settings className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Profile Settings</h2>
              <p className="text-sm text-zinc-400">Manage your account</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content - scrollable */}
        <div className="p-5 max-h-[70vh] overflow-y-auto">
          {/* User info */}
          <div className="flex items-center gap-3 p-4 bg-zinc-800/50 rounded-xl mb-5">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-lg font-bold">
              {user.username[0].toUpperCase()}
            </div>
            <div>
              <p className="font-semibold">{user.username}</p>
              <p className="text-sm text-zinc-400">Regular User</p>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-2 mb-5">
            <button
              onClick={() => { setActiveTab('username'); setError(''); setSuccess(''); }}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium transition-all ${
                activeTab === 'username'
                  ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
                  : 'bg-zinc-800 text-zinc-400 hover:text-white'
              }`}
            >
              <User className="w-4 h-4" />
              Username
            </button>
            <button
              onClick={() => { setActiveTab('password'); setError(''); setSuccess(''); }}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium transition-all ${
                activeTab === 'password'
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                  : 'bg-zinc-800 text-zinc-400 hover:text-white'
              }`}
            >
              <KeyRound className="w-4 h-4" />
              Password
            </button>
          </div>

          {/* Messages */}
          <AnimatePresence>
            {error && (
              <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center gap-2"
              >
                <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
                <p className="text-sm text-red-400">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {success && (
              <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-center gap-2"
              >
                <Check className="w-5 h-5 text-emerald-400 shrink-0" />
                <p className="text-sm text-emerald-400">{success}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Forms */}
          <AnimatePresence mode="wait">
            {activeTab === 'username' && (
              <motion.div
                key="username"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm text-zinc-400 mb-2">New Username</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                    <input 
                      type="text"
                      value={newUsername}
                      onChange={(e) => setNewUsername(e.target.value)}
                      className="w-full pl-11 pr-4 py-3 bg-zinc-800 border border-zinc-700 rounded-xl focus:outline-none focus:border-purple-500 transition-colors"
                      placeholder="Enter new username"
                      disabled={!!success}
                    />
                  </div>
                  <p className="mt-1.5 text-xs text-zinc-500">Minimum 3 characters</p>
                </div>

                <div>
                  <label className="block text-sm text-zinc-400 mb-2">Current Password</label>
                  <div className="relative">
                    <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                    <input 
                      type={showUsernamePassword ? 'text' : 'password'}
                      value={usernamePassword}
                      onChange={(e) => setUsernamePassword(e.target.value)}
                      className="w-full pl-11 pr-11 py-3 bg-zinc-800 border border-zinc-700 rounded-xl focus:outline-none focus:border-purple-500 transition-colors"
                      placeholder="Enter current password"
                      disabled={!!success}
                    />
                    <button
                      type="button"
                      onClick={() => setShowUsernamePassword(!showUsernamePassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
                    >
                      {showUsernamePassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                  <p className="mt-1.5 text-xs text-zinc-500">Required to verify your identity</p>
                </div>

                <div className="flex gap-3 pt-2">
                  <button 
                    onClick={onClose}
                    className="flex-1 py-3 border border-zinc-700 rounded-xl hover:bg-zinc-800 transition-colors font-medium"
                    disabled={saving}
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={handleChangeUsername}
                    disabled={saving || !!success}
                    className="flex-1 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold rounded-xl hover:opacity-90 disabled:opacity-50 transition-all"
                  >
                    {saving ? 'Saving...' : success ? 'Done!' : 'Save'}
                  </button>
                </div>
              </motion.div>
            )}

            {activeTab === 'password' && (
              <motion.div
                key="password"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm text-zinc-400 mb-2">Current Password</label>
                  <div className="relative">
                    <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                    <input 
                      type={showPasswords ? 'text' : 'password'}
                      value={oldPassword}
                      onChange={(e) => setOldPassword(e.target.value)}
                      className="w-full pl-11 pr-11 py-3 bg-zinc-800 border border-zinc-700 rounded-xl focus:outline-none focus:border-emerald-500 transition-colors"
                      placeholder="Enter current password"
                      disabled={!!success}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPasswords(!showPasswords)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
                    >
                      {showPasswords ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-zinc-400 mb-2">New Password</label>
                  <div className="relative">
                    <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                    <input 
                      type={showPasswords ? 'text' : 'password'}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="w-full pl-11 pr-4 py-3 bg-zinc-800 border border-zinc-700 rounded-xl focus:outline-none focus:border-emerald-500 transition-colors"
                      placeholder="Enter new password"
                      disabled={!!success}
                    />
                  </div>
                  <p className="mt-1.5 text-xs text-zinc-500">Minimum 4 characters</p>
                </div>

                <div>
                  <label className="block text-sm text-zinc-400 mb-2">Confirm New Password</label>
                  <div className="relative">
                    <Check className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                    <input 
                      type={showPasswords ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full pl-11 pr-4 py-3 bg-zinc-800 border border-zinc-700 rounded-xl focus:outline-none focus:border-emerald-500 transition-colors"
                      placeholder="Confirm new password"
                      disabled={!!success}
                    />
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button 
                    onClick={onClose}
                    className="flex-1 py-3 border border-zinc-700 rounded-xl hover:bg-zinc-800 transition-colors font-medium"
                    disabled={saving}
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={handleChangePassword}
                    disabled={saving || !!success}
                    className="flex-1 py-3 bg-gradient-to-r from-emerald-500 to-cyan-500 text-black font-semibold rounded-xl hover:opacity-90 disabled:opacity-50 transition-all"
                  >
                    {saving ? 'Saving...' : success ? 'Done!' : 'Save'}
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </motion.div>
  );
}