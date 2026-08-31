import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Check } from 'lucide-react';

/**
 * Playlist selector dropdown component
 * Allows adding tracks to playlists
 */
export default function PlaylistSelector({ 
  playlists, 
  trackId, 
  onAddToPlaylist,
  className = "" 
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [adding, setAdding] = useState(null);

  const handleAdd = async (playlistId) => {
    setAdding(playlistId);
    try {
      await onAddToPlaylist(playlistId, trackId);
      setTimeout(() => setIsOpen(false), 500);
    } catch (err) {
      console.error(err);
    } finally {
      setTimeout(() => setAdding(null), 1000);
    }
  };

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        className="p-2 rounded-lg hover:bg-white/10 transition-colors"
        title="Add to playlist"
      >
        <Plus className="w-4 h-4" />
      </button>

      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <div 
              className="fixed inset-0 z-40" 
              onClick={() => setIsOpen(false)} 
            />
            
            {/* Dropdown */}
            <motion.div
              initial={{ opacity: 0, y: -10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 mt-2 w-56 bg-zinc-800 border border-zinc-700 rounded-xl shadow-xl z-50 overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="p-2 border-b border-zinc-700">
                <p className="text-xs text-zinc-400 px-2 py-1">Add to playlist</p>
              </div>
              
              <div className="max-h-64 overflow-y-auto">
                {playlists.length === 0 ? (
                  <div className="p-4 text-center text-sm text-zinc-500">
                    No playlists yet
                  </div>
                ) : (
                  playlists.map((playlist) => (
                    <button
                      key={playlist.id}
                      onClick={() => handleAdd(playlist.id)}
                      disabled={adding === playlist.id}
                      className="w-full px-3 py-2 text-left hover:bg-white/5 transition-colors flex items-center justify-between disabled:opacity-50"
                    >
                      <span className="text-sm truncate">{playlist.name}</span>
                      {adding === playlist.id && (
                        <Check className="w-4 h-4 text-emerald-400" />
                      )}
                    </button>
                  ))
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}