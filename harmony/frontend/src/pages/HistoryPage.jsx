import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { History, Music, Play, Trash2, Clock, Loader2 } from 'lucide-react';
import api from '../api/client';
import { formatTime } from '../utils/helpers';
import { PlaylistSelector } from '../components';

const TrackCover = ({ track }) => {
  const [imageError, setImageError] = React.useState(false);
  const token = localStorage.getItem('token');
  
  if (track.cover_path && !imageError) {
    return (
      <img 
        src={`/api/music/${track.id}/cover?token=${encodeURIComponent(token)}`}
        alt={track.title}
        className="w-12 h-12 rounded object-cover"
        onError={() => setImageError(true)}
      />
    );
  }
  
  return (
    <div className="w-12 h-12 rounded bg-zinc-800 flex items-center justify-center shrink-0">
      <Music className="w-5 h-5 text-zinc-600" />
    </div>
  );
};

const formatDateTime = (dateString) => {
  // The backend returns UTC time. Add the 'Z' suffix to allow the browser to automatically convert to local time.
  let isoString = dateString;
  if (!dateString.endsWith('Z') && !dateString.includes('+')) {
    isoString = dateString + 'Z';
  }
  
  const date = new Date(isoString);
  
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  
  return `${year}-${month}-${day} ${hours}:${minutes}`;
};

export default function HistoryPage({ playlists, onPlay, onAddToPlaylist }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);

  const fetchHistory = async () => {
    try {
      const res = await api.get('/history');
      setHistory(res.data);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleClearHistory = async () => {
    if (!confirm('Clear all play history? This cannot be undone.')) return;
    
    setClearing(true);
    try {
      await api.delete('/history');
      setHistory([]);
    } catch (err) {
      console.error('Failed to clear history:', err);
    } finally {
      setClearing(false);
    }
  };

  const handleDeleteItem = async (historyId) => {
    try {
      await api.delete(`/history/${historyId}`);
      setHistory(history.filter(h => h.id !== historyId));
    } catch (err) {
      console.error('Failed to delete history item:', err);
    }
  };

  const handlePlayTrack = (track) => {
    // Create a list of unique tracks from history for queue
    const uniqueTracks = [];
    const seenIds = new Set();
    for (const h of history) {
      if (!seenIds.has(h.track.id)) {
        seenIds.add(h.track.id);
        uniqueTracks.push(h.track);
      }
    }
    onPlay(track, uniqueTracks);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0 }} 
      className="p-4 md:p-8"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4 md:gap-6 mb-6 md:mb-8">
        <div className="w-32 h-32 md:w-48 md:h-48 rounded-2xl bg-gradient-to-br from-purple-500 via-violet-500 to-indigo-600 flex items-center justify-center shadow-2xl">
          <History className="w-16 h-16 md:w-24 md:h-24 text-white/90" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-zinc-400 uppercase tracking-wider mb-2">Your Activity</p>
          <h1 className="text-3xl md:text-5xl font-bold mb-2 md:mb-4">Recently Played</h1>
          <p className="text-zinc-400">{history.length} track{history.length !== 1 ? 's' : ''}</p>
        </div>
        {history.length > 0 && (
          <button
            onClick={handleClearHistory}
            disabled={clearing}
            className="flex items-center gap-2 px-4 py-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors disabled:opacity-50"
          >
            <Trash2 className="w-4 h-4" />
            {clearing ? 'Clearing...' : 'Clear All'}
          </button>
        )}
      </div>

      {/* Play all button */}
      {history.length > 0 && (
        <button 
          onClick={() => handlePlayTrack(history[0].track)} 
          className="w-12 h-12 md:w-14 md:h-14 rounded-full bg-emerald-500 flex items-center justify-center hover:scale-105 transition-transform mb-6"
        >
          <Play className="w-5 h-5 md:w-6 md:h-6 text-black ml-1" />
        </button>
      )}

      {/* History list */}
      {history.length === 0 ? (
        <div className="text-center py-12">
          <History className="w-16 h-16 mx-auto mb-4 text-zinc-600" />
          <p className="text-zinc-400 mb-2">No play history yet</p>
          <p className="text-zinc-500 text-sm">Start listening to build your history</p>
        </div>
      ) : (
        <div className="space-y-1">
          <AnimatePresence>
            {history.map((item, i) => (
              <motion.div 
                key={item.id}
                initial={{ opacity: 0, x: -20 }} 
                animate={{ opacity: 1, x: 0 }} 
                exit={{ opacity: 0, x: 20 }}
                transition={{ delay: i * 0.02 }} 
                className="flex items-center gap-3 md:gap-4 p-2 md:p-3 rounded-lg hover:bg-white/5 transition-colors group"
              >
                {/* Track info */}
                <div 
                  className="flex flex-1 items-center gap-3 md:gap-4 min-w-0 cursor-pointer"
                  onClick={() => handlePlayTrack(item.track)}
                >
                  <TrackCover track={item.track} />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate text-sm md:text-base">{item.track.title}</p>
                    <p className="text-xs md:text-sm text-zinc-400 truncate">
                      {item.track.artist}
                      {item.track.album && ` • ${item.track.album}`}
                    </p>
                  </div>
                </div>

                {/* Time played */}
                <div className="hidden sm:flex items-center gap-1 text-xs text-zinc-500 shrink-0">
                  <Clock className="w-3 h-3" />
                  <span>{formatDateTime(item.played_at)}</span>
                </div>

                {/* Duration */}
                <span className="text-xs md:text-sm text-zinc-500 shrink-0">
                  {formatTime(item.track.duration)}
                </span>

                {/* Actions */}
                <div className="flex items-center gap-1 shrink-0">
                  <div className="hidden md:block opacity-0 group-hover:opacity-100 transition-opacity">
                    <PlaylistSelector 
                      playlists={playlists}
                      trackId={item.track.id}
                      onAddToPlaylist={onAddToPlaylist}
                    />
                  </div>
                  <button
                    onClick={() => handleDeleteItem(item.id)}
                    className="p-2 text-zinc-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                    title="Remove from history"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}