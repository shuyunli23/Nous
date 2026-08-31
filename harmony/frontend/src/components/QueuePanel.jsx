import React from 'react';
import { motion } from 'framer-motion';
import { X, Music } from 'lucide-react';

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
    <div className="w-10 h-10 rounded bg-zinc-700 flex items-center justify-center shrink-0">
      <Music className="w-4 h-4 text-zinc-500" />
    </div>
  );
};

export default function QueuePanel({ tracks, currentTrack, onClose, onPlay }) {
  return (
    <motion.div 
      initial={{ x: 320, opacity: 0 }} 
      animate={{ x: 0, opacity: 1 }} 
      exit={{ x: 320, opacity: 0 }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="fixed right-0 top-0 bottom-24 md:bottom-28 w-full sm:w-80 bg-zinc-900/95 backdrop-blur-xl border-l border-white/10 z-40 flex flex-col"
    >
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <h2 className="font-semibold">Queue</h2>
        <button 
          onClick={onClose} 
          className="p-2 rounded-full hover:bg-white/10 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-2">
        {tracks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500">
            <Music className="w-12 h-12 mb-4 opacity-50" />
            <p>Queue is empty</p>
          </div>
        ) : (
          tracks.map((track, i) => (
            <motion.div 
              key={track.id} 
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              className={`
                flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors
                ${track.id === currentTrack?.id 
                  ? 'bg-emerald-500/10 border border-emerald-500/20' 
                  : 'hover:bg-white/5'
                }
              `} 
              onClick={() => onPlay(track)}
            >
              <span className="w-6 text-center text-sm text-zinc-500">
                {i + 1}
              </span>
              <TrackCover track={track} />
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium truncate ${
                  track.id === currentTrack?.id ? 'text-emerald-400' : ''
                }`}>
                  {track.title}
                </p>
                <p className="text-xs text-zinc-400 truncate">{track.artist}</p>
              </div>
            </motion.div>
          ))
        )}
      </div>
    </motion.div>
  );
}