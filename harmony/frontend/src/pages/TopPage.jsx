import React from 'react';
import { motion } from 'framer-motion';
import { Crown, Music, Play } from 'lucide-react';
import { formatTime, formatPlayCount } from '../utils/helpers';
import { PlaylistSelector } from '../components';

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

export default function TopPage({ tracks, playlists, onPlay, onAddToPlaylist }) {
  // Limit to top 100 tracks
  const sorted = [...tracks]
    .sort((a, b) => b.play_count - a.play_count)
    .slice(0, 100);
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0 }} 
      className="p-4 md:p-8"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4 md:gap-6 mb-6 md:mb-8">
        <div className="w-32 h-32 md:w-48 md:h-48 rounded-2xl bg-gradient-to-br from-orange-500 via-red-500 to-pink-600 flex items-center justify-center shadow-2xl">
          <Crown className="w-16 h-16 md:w-24 md:h-24 text-white/90" />
        </div>
        <div>
          <p className="text-sm text-zinc-400 uppercase tracking-wider mb-2">Charts</p>
          <h1 className="text-3xl md:text-5xl font-bold mb-2 md:mb-4">Top 100</h1>
          <p className="text-zinc-400">{sorted.length} tracks</p>
        </div>
      </div>
      
      {/* Play button */}
      {sorted.length > 0 && (
        <button 
          onClick={() => onPlay(sorted[0], sorted)} 
          className="w-12 h-12 md:w-14 md:h-14 rounded-full bg-emerald-500 flex items-center justify-center hover:scale-105 transition-transform mb-6"
        >
          <Play className="w-5 h-5 md:w-6 md:h-6 text-black ml-1" />
        </button>
      )}
      
      {/* Track list */}
      <div className="space-y-1">
        {sorted.map((track, i) => (
          <motion.div 
            key={track.id} 
            initial={{ opacity: 0, x: -20 }} 
            animate={{ opacity: 1, x: 0 }} 
            transition={{ delay: i * 0.02 }} 
            className="grid grid-cols-[32px_1fr_60px] md:grid-cols-[40px_1fr_1fr_80px_80px_40px] gap-2 md:gap-4 px-2 md:px-4 py-3 rounded-lg hover:bg-white/5 items-center group" 
          >
            <span 
              className={`text-base md:text-lg font-bold text-center cursor-pointer ${
                i < 3 ? 'text-transparent bg-gradient-to-r from-amber-400 to-orange-500 bg-clip-text' : 'text-zinc-500'
              }`}
              onClick={() => onPlay(track, sorted)}
            >
              {i + 1}
            </span>
            
            <div 
              className="flex items-center gap-2 md:gap-3 min-w-0 cursor-pointer"
              onClick={() => onPlay(track, sorted)}
            >
              <div className="hidden sm:block">
                <TrackCover track={track} />
              </div>
              <div className="min-w-0">
                <p className="font-medium truncate text-sm md:text-base">{track.title}</p>
                <p className="text-xs md:text-sm text-zinc-400 truncate">{track.artist}</p>
              </div>
            </div>
            
            <span className="text-sm text-zinc-400 truncate hidden md:block">
              {track.album || '-'}
            </span>
            
            <span className="text-xs md:text-sm text-zinc-400 text-right hidden md:block">
              {formatPlayCount(track.play_count)}
            </span>
            
            <span className="text-xs md:text-sm text-zinc-500 text-right">
              {formatTime(track.duration)}
            </span>
            
            <div className="hidden md:block opacity-0 group-hover:opacity-100 transition-opacity">
              <PlaylistSelector 
                playlists={playlists}
                trackId={track.id}
                onAddToPlaylist={onAddToPlaylist}
              />
            </div>
          </motion.div>
        ))}
      </div>

      {sorted.length === 0 && (
        <div className="text-center py-12">
          <Music className="w-16 h-16 mx-auto mb-4 text-zinc-600" />
          <p className="text-zinc-400">No tracks yet</p>
        </div>
      )}
    </motion.div>
  );
}