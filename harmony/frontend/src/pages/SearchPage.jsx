import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Search, Music, Play, Download, Loader2 } from 'lucide-react';
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

// Download button component
const DownloadButton = ({ track }) => {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async (e) => {
    e.stopPropagation();
    if (downloading) return;

    setDownloading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/music/${track.id}/stream?token=${encodeURIComponent(token)}`);
      
      if (!response.ok) throw new Error('Download failed');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      
      // Get file extension from file_path
      const ext = track.file_path?.split('.').pop() || 'mp3';
      const filename = `${track.title} - ${track.artist}.${ext}`;
      
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Download failed. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <button
      onClick={handleDownload}
      disabled={downloading}
      className="p-2 text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/20 rounded-lg transition-colors disabled:opacity-50"
      title="Download"
    >
      {downloading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : (
        <Download className="w-4 h-4" />
      )}
    </button>
  );
};

export default function SearchPage({ tracks, playlists, onPlay, onAddToPlaylist }) {
  const [query, setQuery] = useState('');
  
  const results = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return tracks.filter(t => 
      t.title.toLowerCase().includes(q) || 
      t.artist.toLowerCase().includes(q) || 
      (t.album && t.album.toLowerCase().includes(q))
    );
  }, [query, tracks]);

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0 }} 
      className="p-4 md:p-8"
    >
      {/* Search Header */}
      <div className="mb-6 md:mb-8">
        <h1 className="text-2xl md:text-3xl font-bold mb-4 md:mb-6">Search</h1>
        <div className="relative max-w-xl">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
          <input 
            type="text" 
            placeholder="What do you want to listen to?" 
            value={query} 
            onChange={(e) => setQuery(e.target.value)} 
            className="w-full h-12 pl-12 pr-4 bg-zinc-800/50 border border-zinc-700/50 rounded-full text-base focus:outline-none focus:border-emerald-500/50 transition-colors" 
            autoFocus 
          />
        </div>
      </div>
      
      {/* Results */}
      {query && (
        <div className="mb-4">
          <p className="text-sm text-zinc-400">
            {results.length} result{results.length !== 1 ? 's' : ''} for "{query}"
          </p>
        </div>
      )}
      
      {/* Track list */}
      <div className="space-y-1">
        {results.map((track, i) => (
          <motion.div 
            key={track.id} 
            initial={{ opacity: 0, y: 10 }} 
            animate={{ opacity: 1, y: 0 }} 
            transition={{ delay: i * 0.03 }} 
            className="flex items-center gap-3 md:gap-4 p-2 md:p-3 rounded-lg hover:bg-white/5 transition-colors group"
          >
            {/* Play button / Cover */}
            <div 
              className="relative cursor-pointer"
              onClick={() => onPlay(track, results)}
            >
              <TrackCover track={track} />
              <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity rounded flex items-center justify-center">
                <Play className="w-5 h-5 text-white" />
              </div>
            </div>
            
            {/* Track info */}
            <div 
              className="flex-1 min-w-0 cursor-pointer"
              onClick={() => onPlay(track, results)}
            >
              <p className="font-medium truncate text-sm md:text-base">{track.title}</p>
              <p className="text-xs md:text-sm text-zinc-400 truncate">
                {track.artist}
                {track.album && ` • ${track.album}`}
              </p>
            </div>
            
            {/* Duration */}
            <span className="text-xs md:text-sm text-zinc-500 hidden sm:block">
              {formatTime(track.duration)}
            </span>
            
            {/* Actions */}
            <div className="flex items-center gap-1">
              <DownloadButton track={track} />
              <div className="hidden md:block opacity-0 group-hover:opacity-100 transition-opacity">
                <PlaylistSelector 
                  playlists={playlists}
                  trackId={track.id}
                  onAddToPlaylist={onAddToPlaylist}
                />
              </div>
            </div>
          </motion.div>
        ))}
      </div>
      
      {/* Empty state */}
      {query && results.length === 0 && (
        <div className="text-center py-12">
          <Search className="w-16 h-16 mx-auto mb-4 text-zinc-600" />
          <p className="text-zinc-400">No results found for "{query}"</p>
          <p className="text-zinc-500 text-sm mt-2">Try different keywords</p>
        </div>
      )}
      
      {/* Initial state */}
      {!query && (
        <div className="text-center py-12">
          <Music className="w-16 h-16 mx-auto mb-4 text-zinc-600" />
          <p className="text-zinc-400">Search for songs, artists, or albums</p>
        </div>
      )}
    </motion.div>
  );
}