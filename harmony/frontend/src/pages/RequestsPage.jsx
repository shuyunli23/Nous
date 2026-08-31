import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Bell, Clock, Check, Trash2, X } from 'lucide-react';
import api from '../api/client';

export default function RequestsPage({ requests, setRequests, isAdmin }) {
  const [tab, setTab] = useState('pending');
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ music_name: '', artist_name: '', notes: '' });
  const [submitting, setSubmitting] = useState(false);

  const submitRequest = async () => {
    if (!formData.music_name.trim()) return;
    setSubmitting(true);
    try {
      const res = await api.post('/requests', formData);
      setRequests([res.data, ...requests]);
      setFormData({ music_name: '', artist_name: '', notes: '' });
      setShowForm(false);
    } catch (err) { 
      console.error(err); 
    } finally { 
      setSubmitting(false); 
    }
  };

  const processRequest = async (id) => {
    try { 
      await api.post(`/requests/${id}/process`); 
      setRequests(requests.map(r => r.id === id ? { ...r, status: 'processed' } : r)); 
    } catch (err) { 
      console.error(err); 
    }
  };

  const deleteRequest = async (id) => {
    try { 
      await api.delete(`/requests/${id}`); 
      setRequests(requests.filter(r => r.id !== id)); 
    } catch (err) { 
      console.error(err); 
    }
  };

  const filtered = requests.filter(r => 
    tab === 'pending' ? r.status === 'pending' : r.status === 'processed'
  );
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0 }} 
      className="p-4 md:p-8"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl md:text-2xl font-bold">
            {isAdmin ? 'Music Requests' : 'My Requests'}
          </h1>
          <p className="text-zinc-400 text-sm mt-1">
            {isAdmin ? 'Review user submissions' : 'Request music from admin'}
          </p>
        </div>
        {!isAdmin && (
          <button 
            onClick={() => setShowForm(true)} 
            className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-black font-medium rounded-full transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Request
          </button>
        )}
      </div>
      
      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button 
          onClick={() => setTab('pending')} 
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
            tab === 'pending' ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white'
          }`}
        >
          Pending 
          <span className="ml-2 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-xs">
            {requests.filter(r => r.status === 'pending').length}
          </span>
        </button>
        <button 
          onClick={() => setTab('processed')} 
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
            tab === 'processed' ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white'
          }`}
        >
          Processed
        </button>
      </div>

      {/* Request form modal */}
      <AnimatePresence>
        {showForm && (
          <motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" 
            onClick={() => setShowForm(false)}
          >
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }} 
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full max-w-md" 
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold">Request Music</h2>
                <button 
                  onClick={() => setShowForm(false)}
                  className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-zinc-400 mb-1">Song Name *</label>
                  <input 
                    className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-emerald-500" 
                    placeholder="Enter song name" 
                    value={formData.music_name} 
                    onChange={(e) => setFormData({ ...formData, music_name: e.target.value })} 
                  />
                </div>
                <div>
                  <label className="block text-sm text-zinc-400 mb-1">Artist</label>
                  <input 
                    className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-emerald-500" 
                    placeholder="Enter artist name" 
                    value={formData.artist_name} 
                    onChange={(e) => setFormData({ ...formData, artist_name: e.target.value })} 
                  />
                </div>
                <div>
                  <label className="block text-sm text-zinc-400 mb-1">Notes</label>
                  <textarea 
                    className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-emerald-500 resize-none h-20" 
                    placeholder="Additional info..." 
                    value={formData.notes} 
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })} 
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <button 
                    onClick={() => setShowForm(false)} 
                    className="flex-1 px-4 py-2 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={submitRequest} 
                    disabled={submitting} 
                    className="flex-1 px-4 py-2 bg-emerald-500 text-black font-medium rounded-lg hover:bg-emerald-400 disabled:opacity-50 transition-colors"
                  >
                    {submitting ? 'Submitting...' : 'Submit'}
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Request list */}
      <div className="space-y-3">
        {filtered.length === 0 ? (
          <div className="text-center py-12">
            <Bell className="w-12 h-12 mx-auto mb-4 text-zinc-600" />
            <p className="text-zinc-400">No {tab} requests</p>
          </div>
        ) : filtered.map(request => (
          <motion.div 
            key={request.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-4 bg-zinc-900/50 border border-zinc-800/50 rounded-xl"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <h3 className="font-semibold">{request.music_name}</h3>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    request.status === 'pending' 
                      ? 'bg-amber-500/20 text-amber-400' 
                      : 'bg-emerald-500/20 text-emerald-400'
                  }`}>
                    {request.status === 'pending' ? 'Pending' : 'Processed'}
                  </span>
                </div>
                {request.artist_name && (
                  <p className="text-sm text-zinc-400">{request.artist_name}</p>
                )}
                {request.notes && (
                  <p className="text-sm text-zinc-500 mt-2">"{request.notes}"</p>
                )}
                <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-zinc-500">
                  {isAdmin && <span>From: {request.username}</span>}
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(request.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                {isAdmin && request.status === 'pending' && (
                  <button 
                    onClick={() => processRequest(request.id)} 
                    className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                )}
                {request.status === 'processed' && (
                  <button 
                    onClick={() => deleteRequest(request.id)} 
                    className="p-2 rounded-lg bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
