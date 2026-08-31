import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, UserPlus, Trash2, KeyRound, X, Eye, EyeOff, AlertCircle, Check, Copy, Link2 } from 'lucide-react';
import api from '../api/client';

// Password Reset Dialog Component
function PasswordResetDialog({ user, onClose, onSuccess }) {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    setError('');
    
    // Validation
    if (!newPassword) {
      setError('Password is required');
      return;
    }
    
    if (newPassword.length < 4) {
      setError('Password must be at least 4 characters');
      return;
    }
    
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setSaving(true);
    try {
      await api.put(`/admin/users/${user.id}/password`, { 
        new_password: newPassword 
      });
      setSuccess(true);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reset password');
    } finally {
      setSaving(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" 
      onClick={onClose}
    >
      <motion.div 
        initial={{ scale: 0.95, opacity: 0 }} 
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full max-w-md" 
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
              <KeyRound className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Reset Password</h2>
              <p className="text-sm text-zinc-400">{user.username}</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Security Notice */}
        <div className="mb-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
          <p className="text-xs text-amber-400">
            <strong>Note:</strong> For security reasons, passwords are encrypted and cannot be viewed. 
            You can only set a new password for this user.
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 bg-emerald-500/20 border border-emerald-500/30 rounded-lg flex items-center gap-2">
            <Check className="w-5 h-5 text-emerald-400" />
            <p className="text-sm text-emerald-400">Password reset successfully!</p>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">New Password *</label>
            <div className="relative">
              <input 
                type={showPassword ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-4 py-2 pr-10 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-amber-500"
                placeholder="Enter new password"
                disabled={success}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1">Confirm Password *</label>
            <input 
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-amber-500"
              placeholder="Confirm new password"
              disabled={success}
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button 
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
              disabled={saving}
            >
              Cancel
            </button>
            <button 
              onClick={handleSave}
              disabled={saving || success}
              className="flex-1 px-4 py-2 bg-amber-500 text-black font-medium rounded-lg hover:bg-amber-400 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving...' : success ? 'Done!' : 'Reset Password'}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default function UsersPage({ users, setUsers }) {
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState({ username: '', password: '' });
  const [creating, setCreating] = useState(false);
  const [resetUser, setResetUser] = useState(null);
  const [shareUrl, setShareUrl] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get('/auth/share-url')
      .then((res) => setShareUrl(res.data.url || ''))
      .catch(() => setShareUrl(`${window.location.origin}/harmony/`));
  }, []);

  const createUser = async () => {
    if (!formData.username || !formData.password) return;
    setCreating(true);
    try {
      const res = await api.post('/admin/users', formData);
      setUsers([res.data, ...users]);
      setFormData({ username: '', password: '' });
      setShowCreate(false);
    } catch (err) { 
      alert(err.response?.data?.detail || 'Failed to create user'); 
    } finally { 
      setCreating(false); 
    }
  };

  const deleteUser = async (id) => {
    if (!confirm('Delete this user?')) return;
    try { 
      await api.delete(`/admin/users/${id}`); 
      setUsers(users.filter(u => u.id !== id)); 
    } catch (err) { 
      alert(err.response?.data?.detail || 'Failed to delete'); 
    }
  };
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0 }} 
      className="p-4 md:p-8"
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-6">
        <Shield className="w-5 h-5 text-amber-400" />
        <h1 className="text-xl md:text-2xl font-bold">User Manager</h1>
        <span className="px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-400">Admin</span>
      </div>

      {shareUrl && (
        <div className="mb-6 p-4 bg-zinc-900/50 border border-emerald-500/20 rounded-xl">
          <div className="flex items-center gap-2 mb-2 text-sm text-emerald-400">
            <Link2 className="w-4 h-4" />
            Guest link (Harmony only — sign-in required)
          </div>
          <p className="text-xs text-zinc-500 mb-3">
            Share this address. Guests cannot open Nous; after login they only get the music player.
          </p>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              readOnly
              value={shareUrl}
              className="flex-1 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200"
            />
            <button
              type="button"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(shareUrl);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1600);
                } catch {
                  /* ignore */
                }
              }}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-emerald-500/20 text-emerald-300 rounded-lg hover:bg-emerald-500/30 transition-colors"
            >
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      )}

      <button 
        onClick={() => setShowCreate(true)} 
        className="flex items-center gap-2 px-4 py-2 bg-amber-500 text-black font-medium rounded-lg hover:bg-amber-400 mb-6 transition-colors"
      >
        <UserPlus className="w-4 h-4" />
        Create User
      </button>

      {/* Create user form */}
      {showCreate && (
        <motion.div 
          initial={{ opacity: 0, y: -10 }} 
          animate={{ opacity: 1, y: 0 }} 
          className="mb-6 p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl"
        >
          <h3 className="font-medium mb-3">Create New User</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm text-zinc-400 mb-1">Username *</label>
              <input 
                type="text" 
                value={formData.username} 
                onChange={(e) => setFormData({ ...formData, username: e.target.value })} 
                className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-amber-500" 
                placeholder="Username" 
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-400 mb-1">Password *</label>
              <input 
                type="password" 
                value={formData.password} 
                onChange={(e) => setFormData({ ...formData, password: e.target.value })} 
                className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-amber-500" 
                placeholder="Password" 
              />
            </div>
          </div>
          <div className="flex gap-3">
            <button 
              onClick={createUser} 
              disabled={creating} 
              className="px-4 py-2 bg-amber-500 text-black font-medium rounded-lg hover:bg-amber-400 disabled:opacity-50 transition-colors"
            >
              {creating ? 'Creating...' : 'Create'}
            </button>
            <button 
              onClick={() => setShowCreate(false)} 
              className="px-4 py-2 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
            >
              Cancel
            </button>
          </div>
        </motion.div>
      )}
      
      {/* Users table */}
      <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl overflow-hidden">
        {/* Desktop table */}
        <div className="hidden md:block">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="px-6 py-4 text-left text-sm font-medium text-zinc-400">Username</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-zinc-400">Role</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-zinc-400">Created</th>
                <th className="px-6 py-4 text-right text-sm font-medium text-zinc-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(user => (
                <tr key={user.id} className="border-b border-zinc-800/50 hover:bg-white/5 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-sm font-bold">
                        {user.username[0].toUpperCase()}
                      </div>
                      <span>{user.username}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-full text-xs ${
                      user.role === 'admin' 
                        ? 'bg-amber-500/20 text-amber-400' 
                        : 'bg-zinc-700 text-zinc-300'
                    }`}>
                      {user.role === 'admin' ? 'Admin' : 'User'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-zinc-400">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {user.role !== 'admin' && (
                        <>
                          <button 
                            onClick={() => setResetUser(user)} 
                            className="p-2 rounded-lg text-amber-400 hover:bg-amber-500/20 transition-colors"
                            title="Reset Password"
                          >
                            <KeyRound className="w-4 h-4" />
                          </button>
                          <button 
                            onClick={() => deleteUser(user.id)} 
                            className="p-2 rounded-lg text-red-400 hover:bg-red-500/20 transition-colors"
                            title="Delete User"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Mobile list */}
        <div className="md:hidden divide-y divide-zinc-800">
          {users.map(user => (
            <div key={user.id} className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-sm font-bold shrink-0">
                {user.username[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{user.username}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    user.role === 'admin' 
                      ? 'bg-amber-500/20 text-amber-400' 
                      : 'bg-zinc-700 text-zinc-300'
                  }`}>
                    {user.role === 'admin' ? 'Admin' : 'User'}
                  </span>
                  <span className="text-xs text-zinc-500">
                    {new Date(user.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              {user.role !== 'admin' && (
                <div className="flex gap-1">
                  <button 
                    onClick={() => setResetUser(user)} 
                    className="p-2 rounded-lg text-amber-400 hover:bg-amber-500/20 transition-colors"
                    title="Reset Password"
                  >
                    <KeyRound className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={() => deleteUser(user.id)} 
                    className="p-2 rounded-lg text-red-400 hover:bg-red-500/20 transition-colors"
                    title="Delete User"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Password Reset Dialog */}
      <AnimatePresence>
        {resetUser && (
          <PasswordResetDialog
            user={resetUser}
            onClose={() => setResetUser(null)}
            onSuccess={() => {
              // Optionally refresh user list or show notification
            }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}