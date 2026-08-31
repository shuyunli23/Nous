import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Music, Library, Trash2, Play, GripVertical, X, Search } from 'lucide-react';
import api from '../api/client';
import { formatTime } from '../utils/helpers';

const TrackCover = ({ track }) => {
  const [imageError, setImageError] = React.useState(false);
  const token = localStorage.getItem('token');
  
  if (track.cover_path && !imageError) {
    return (
      <img 
        src={`/api/music/${track.id}/cover?token=${encodeURIComponent(token)}`}
        alt={track.title}
        className="w-10 h-10 rounded object-cover"
        onError={() => setImageError(true)}
      />
    );
  }
  
  return (
    <div className="w-10 h-10 rounded bg-zinc-800 flex items-center justify-center shrink-0">
      <Music className="w-4 h-4 text-zinc-600" />
    </div>
  );
};

export default function LibraryPage({ playlists, setPlaylists, tracks, onPlay, onRefresh }) {
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [playlistTracks, setPlaylistTracks] = useState([]);
  const [showAddMusic, setShowAddMusic] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [draggedIndex, setDraggedIndex] = useState(null);

  const createPlaylist = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const res = await api.post('/playlists', { name: newName });
      setPlaylists([...playlists, res.data]);
      setNewName('');
      setShowCreate(false);
    } catch (err) { 
      console.error(err); 
    } finally { 
      setCreating(false); 
    }
  };

  const deletePlaylist = async (id) => {
    if (!confirm('Delete this playlist?')) return;
    try { 
      await api.delete(`/playlists/${id}`); 
      setPlaylists(playlists.filter(p => p.id !== id));
      if (selectedPlaylist?.id === id) {
        setSelectedPlaylist(null);
        setPlaylistTracks([]);
      }
    } catch (err) { 
      console.error(err); 
    }
  };

  const loadPlaylist = async (playlist) => {
    try {
      const res = await api.get(`/playlists/${playlist.id}`);
      setSelectedPlaylist(playlist);
      setPlaylistTracks(res.data.tracks || []);
    } catch (err) {
      console.error(err);
    }
  };

  const addTrackToPlaylist = async (trackId) => {
    if (!selectedPlaylist) return;
    try {
      await api.post(`/playlists/${selectedPlaylist.id}/tracks/${trackId}`);
      await loadPlaylist(selectedPlaylist);
      onRefresh();
    } catch (err) {
      if (err.response?.status === 400) {
        alert('Track already in playlist');
      }
    }
  };

  const removeTrackFromPlaylist = async (trackId) => {
    if (!selectedPlaylist) return;
    try {
      await api.delete(`/playlists/${selectedPlaylist.id}/tracks/${trackId}`);
      await loadPlaylist(selectedPlaylist);
      onRefresh();
    } catch (err) {
      console.error(err);
    }
  };

  const reorderTracks = async (newOrder) => {
    if (!selectedPlaylist) return;
    const trackIds = newOrder.map(t => t.id);
    try {
      await api.put(`/playlists/${selectedPlaylist.id}/reorder`, trackIds);
      setPlaylistTracks(newOrder);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDragStart = (index) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;
    
    const newTracks = [...playlistTracks];
    const draggedTrack = newTracks[draggedIndex];
    newTracks.splice(draggedIndex, 1);
    newTracks.splice(index, 0, draggedTrack);
    
    setPlaylistTracks(newTracks);
    setDraggedIndex(index);
  };

  const handleDragEnd = () => {
    if (draggedIndex !== null) {
      reorderTracks(playlistTracks);
    }
    setDraggedIndex(null);
  };

  const filteredTracks = tracks.filter(t => 
    t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.artist.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0 }} 
      className="p-4 md:p-8"
    >
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl md:text-2xl font-bold">My Library</h1>
        <button 
          onClick={() => setShowCreate(true)} 
          className="flex items-center gap-2 px-3 md:px-4 py-2 bg-white/10 hover:bg-white/20 rounded-full text-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">New Playlist</span>
        </button>
      </div>
      
      {/* Create playlist form */}
      {showCreate && (
        <motion.div 
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl"
        >
          <h3 className="font-medium mb-3">Create Playlist</h3>
          <div className="flex flex-col sm:flex-row gap-3">
            <input 
              type="text" 
              value={newName} 
              onChange={(e) => setNewName(e.target.value)} 
              placeholder="Playlist name" 
              className="flex-1 px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-emerald-500" 
            />
            <div className="flex gap-2">
              <button 
                onClick={createPlaylist} 
                disabled={creating} 
                className="flex-1 sm:flex-initial px-4 py-2 bg-emerald-500 text-black font-medium rounded-lg hover:bg-emerald-400 disabled:opacity-50 transition-colors"
              >
                {creating ? 'Creating...' : 'Create'}
              </button>
              <button 
                onClick={() => { setShowCreate(false); setNewName(''); }} 
                className="flex-1 sm:flex-initial px-4 py-2 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </motion.div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Playlists grid */}
        <div className="lg:col-span-1">
          {playlists.length === 0 ? (
            <div className="text-center py-12">
              <Library className="w-12 h-12 mx-auto mb-4 text-zinc-600" />
              <p className="text-zinc-400">No playlists yet</p>
              <p className="text-zinc-500 text-sm mt-1">Create one to get started</p>
            </div>
          ) : (
            <div className="space-y-2">
              {playlists.map((playlist) => (
                <motion.div 
                  key={playlist.id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className={`group p-4 rounded-xl cursor-pointer transition-all ${
                    selectedPlaylist?.id === playlist.id 
                      ? 'bg-emerald-500/20 border border-emerald-500/30' 
                      : 'bg-zinc-900/50 hover:bg-zinc-800/70 border border-transparent'
                  }`}
                  onClick={() => loadPlaylist(playlist)}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center shrink-0">
                      <Music className="w-6 h-6 text-zinc-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold truncate">{playlist.name}</h3>
                      <p className="text-sm text-zinc-400">{playlist.track_count} tracks</p>
                    </div>
                    <button 
                      onClick={(e) => { e.stopPropagation(); deletePlaylist(playlist.id); }} 
                      className="p-2 rounded-lg bg-red-500/20 text-red-400 opacity-0 group-hover:opacity-100 hover:bg-red-500/30 transition-all"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Playlist details */}
        <div className="lg:col-span-2">
          {selectedPlaylist ? (
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold">{selectedPlaylist.name}</h2>
                <button 
                  onClick={() => setShowAddMusic(true)}
                  className="flex items-center gap-2 px-3 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 rounded-lg transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  <span className="text-sm">Add Music</span>
                </button>
              </div>

              {playlistTracks.length === 0 ? (
                <div className="text-center py-12">
                  <Music className="w-12 h-12 mx-auto mb-4 text-zinc-600" />
                  <p className="text-zinc-400 mb-2">No tracks yet</p>
                  <button 
                    onClick={() => setShowAddMusic(true)}
                    className="text-emerald-400 hover:text-emerald-300"
                  >
                    Add some music
                  </button>
                </div>
              ) : (
                <>
                  <button 
                    onClick={() => onPlay(playlistTracks[0], playlistTracks, selectedPlaylist.id)}
                    className="w-12 h-12 rounded-full bg-emerald-500 flex items-center justify-center hover:scale-105 transition-transform mb-4"
                  >
                    <Play className="w-5 h-5 text-black ml-0.5" />
                  </button>

                  <div className="space-y-1">
                    {playlistTracks.map((track, index) => (
                      <motion.div 
                        key={track.id}
                        draggable
                        onDragStart={() => handleDragStart(index)}
                        onDragOver={(e) => handleDragOver(e, index)}
                        onDragEnd={handleDragEnd}
                        className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 cursor-move group"
                      >
                        <GripVertical className="w-4 h-4 text-zinc-600 shrink-0" />
                        <span className="w-6 text-center text-sm text-zinc-500">{index + 1}</span>
                        <TrackCover track={track} />
                        <div 
                          className="flex-1 min-w-0 cursor-pointer"
                          onClick={() => onPlay(track, playlistTracks, selectedPlaylist.id)}
                        >
                          <p className="font-medium truncate text-sm">{track.title}</p>
                          <p className="text-xs text-zinc-400 truncate">{track.artist}</p>
                        </div>
                        <span className="text-sm text-zinc-500">{formatTime(track.duration)}</span>
                        <button 
                          onClick={() => removeTrackFromPlaylist(track.id)}
                          className="p-2 rounded-lg text-red-400 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </motion.div>
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-zinc-500">
              <div className="text-center">
                <Library className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>Select a playlist to view tracks</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Add music modal */}
      <AnimatePresence>
        {showAddMusic && selectedPlaylist && (
          <motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" 
            onClick={() => setShowAddMusic(false)}
          >
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }} 
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col" 
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold">Add Music to {selectedPlaylist.name}</h2>
                <button 
                  onClick={() => setShowAddMusic(false)}
                  className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
                <input 
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search tracks..."
                  className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex-1 overflow-y-auto space-y-1">
                {filteredTracks.map(track => (
                  <div 
                    key={track.id}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 cursor-pointer"
                    onClick={() => addTrackToPlaylist(track.id)}
                  >
                    <TrackCover track={track} />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate text-sm">{track.title}</p>
                      <p className="text-xs text-zinc-400 truncate">{track.artist}</p>
                    </div>
                    <Plus className="w-5 h-5 text-emerald-400" />
                  </div>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}