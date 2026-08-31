// harmony-music/frontend/src/components/MiniPlayer.jsx
// Updated: Added Like/Dislike buttons

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Play, Pause, SkipBack, SkipForward, Volume2, VolumeX, 
  Repeat, Repeat1, Shuffle, ListMusic, Maximize2, Music,
  Check, ListPlus, Download, Loader2, MoreHorizontal, X,
  ThumbsUp, ThumbsDown
} from 'lucide-react';
import AudioVisualizer from './AudioVisualizer';
import { LikeDislikeInline } from './LikeDislikeButton';
import { formatTime } from '../utils/helpers';

const PlayModeIcon = ({ mode, className }) => {
  switch (mode) {
    case 'repeat-all':
      return <Repeat className={className} />;
    case 'repeat-one':
      return <Repeat1 className={className} />;
    case 'shuffle':
      return <Shuffle className={className} />;
    default: // sequential
      return <Repeat className={`${className} opacity-40`} />;
  }
};

const TrackCover = ({ track, className }) => {
  const [imageError, setImageError] = React.useState(false);
  const token = localStorage.getItem('token');
  
  if (track.cover_path && !imageError) {
    return (
      <img 
        src={`/api/music/${track.id}/cover?token=${encodeURIComponent(token)}`}
        alt={track.title}
        className={`${className} object-cover`}
        onError={() => setImageError(true)}
      />
    );
  }
  
  return (
    <div className={`${className} bg-zinc-700 flex items-center justify-center`}>
      <Music className="w-5 h-5 md:w-6 md:h-6 text-zinc-500" />
    </div>
  );
};

/**
 * Download Button Component
 */
const DownloadButton = ({ track, compact = false }) => {
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
    } finally {
      setDownloading(false);
    }
  };

  return (
    <motion.button
      onClick={handleDownload}
      disabled={downloading}
      className={`${compact ? 'p-1.5' : 'p-1.5 md:p-2'} rounded-full text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10 transition-all disabled:opacity-50`}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.95 }}
      title="Download"
    >
      {downloading ? (
        <Loader2 className={`${compact ? 'w-4 h-4' : 'w-4 h-4 md:w-5 md:h-5'} animate-spin`} />
      ) : (
        <Download className={`${compact ? 'w-4 h-4' : 'w-4 h-4 md:w-5 md:h-5'}`} />
      )}
    </motion.button>
  );
};

/**
 * Beautiful Add to Playlist Button with dropdown
 */
const AddToPlaylistButton = ({ track, playlists, onAddToPlaylist, compact = false }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [adding, setAdding] = useState(null);
  const [recentlyAdded, setRecentlyAdded] = useState(false);

  const handleAdd = async (playlistId) => {
    setAdding(playlistId);
    try {
      await onAddToPlaylist(playlistId, track.id);
      setRecentlyAdded(true);
      setTimeout(() => {
        setIsOpen(false);
        setRecentlyAdded(false);
      }, 800);
    } catch (err) {
      console.error(err);
    } finally {
      setTimeout(() => setAdding(null), 800);
    }
  };

  return (
    <div className="relative">
      <motion.button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          relative ${compact ? 'p-1.5' : 'p-1.5 md:p-2'} rounded-full transition-all duration-300
          ${isOpen 
            ? 'bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 text-emerald-400' 
            : 'text-zinc-400 hover:text-white hover:bg-white/10'
          }
        `}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
        title="Add to playlist"
      >
        <motion.div
          animate={recentlyAdded ? { scale: [1, 1.3, 1] } : {}}
          transition={{ duration: 0.3 }}
        >
          {recentlyAdded ? (
            <Check className={`${compact ? 'w-4 h-4' : 'w-4 h-4 md:w-5 md:h-5'} text-emerald-400`} />
          ) : (
            <ListPlus className={`${compact ? 'w-4 h-4' : 'w-4 h-4 md:w-5 md:h-5'}`} />
          )}
        </motion.div>
        
        {/* Glow effect when open */}
        {isOpen && (
          <motion.div
            className="absolute inset-0 rounded-full bg-emerald-500/20 blur-md -z-10"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1.2 }}
            exit={{ opacity: 0, scale: 0.8 }}
          />
        )}
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div 
              className="fixed inset-0 z-40" 
              onClick={() => setIsOpen(false)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            />
            
            {/* Dropdown */}
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="absolute bottom-full mb-3 right-0 w-64 bg-zinc-900/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl z-50 overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="px-4 py-3 border-b border-white/10 bg-gradient-to-r from-emerald-500/10 to-cyan-500/10">
                <p className="text-sm font-medium text-white">Add to playlist</p>
                <p className="text-xs text-zinc-400 truncate mt-0.5">{track.title}</p>
              </div>
              
              {/* Playlist list */}
              <div className="max-h-64 overflow-y-auto py-2">
                {(!playlists || playlists.length === 0) ? (
                  <div className="px-4 py-6 text-center">
                    <ListMusic className="w-8 h-8 mx-auto mb-2 text-zinc-600" />
                    <p className="text-sm text-zinc-500">No playlists yet</p>
                    <p className="text-xs text-zinc-600 mt-1">Create one in Library</p>
                  </div>
                ) : (
                  playlists.map((playlist, index) => (
                    <motion.button
                      key={playlist.id}
                      onClick={() => handleAdd(playlist.id)}
                      disabled={adding === playlist.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.03 }}
                      className="w-full px-4 py-2.5 text-left hover:bg-white/5 transition-all flex items-center gap-3 group disabled:opacity-50"
                    >
                      {/* Playlist icon */}
                      <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center shrink-0 group-hover:from-purple-500/30 group-hover:to-pink-500/30 transition-all">
                        {adding === playlist.id ? (
                          <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ type: 'spring', damping: 15 }}
                          >
                            <Check className="w-4 h-4 text-emerald-400" />
                          </motion.div>
                        ) : (
                          <Music className="w-4 h-4 text-zinc-400 group-hover:text-white transition-colors" />
                        )}
                      </div>
                      
                      {/* Playlist info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate group-hover:text-white transition-colors">
                          {playlist.name}
                        </p>
                        <p className="text-xs text-zinc-500">
                          {playlist.track_count} track{playlist.track_count !== 1 ? 's' : ''}
                        </p>
                      </div>

                      {/* Add indicator */}
                      <motion.div
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        whileHover={{ scale: 1.1 }}
                      >
                        <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
                          <span className="text-emerald-400 text-lg leading-none">+</span>
                        </div>
                      </motion.div>
                    </motion.button>
                  ))
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
};

/**
 * Progress slider with gradient fill on left side
 */
const ProgressSlider = ({ currentTime, duration, onSeek }) => {
  const percentage = duration ? (currentTime / duration) * 100 : 0;
  
  const sliderStyle = {
    background: `linear-gradient(to right, 
      #06b6d4 0%, 
      #10b981 ${percentage}%, 
      rgba(255, 255, 255, 0.2) ${percentage}%, 
      rgba(255, 255, 255, 0.2) 100%)`
  };

  return (
    <input 
      type="range" 
      min="0" 
      max={duration || 100} 
      value={currentTime} 
      onChange={(e) => onSeek(parseFloat(e.target.value))} 
      className="flex-1 h-1 cursor-pointer rounded-full appearance-none"
      style={sliderStyle}
    />
  );
};

/**
 * Volume slider with gradient fill on left side
 */
const VolumeSlider = ({ volume, isMuted, onVolumeChange }) => {
  const currentVolume = isMuted ? 0 : volume;
  const percentage = currentVolume;
  
  const sliderStyle = {
    background: `linear-gradient(to right, 
      #10b981 0%, 
      #10b981 ${percentage}%, 
      rgba(255, 255, 255, 0.2) ${percentage}%, 
      rgba(255, 255, 255, 0.2) 100%)`
  };

  return (
    <input 
      type="range" 
      min="0" 
      max="100" 
      value={currentVolume} 
      onChange={(e) => onVolumeChange(parseInt(e.target.value))} 
      className="w-20 h-1 cursor-pointer rounded-full appearance-none"
      style={sliderStyle}
    />
  );
};

/**
 * Mobile More Actions Panel
 */
const MobileActionsPanel = ({ 
  track, 
  isOpen, 
  onClose, 
  playMode, 
  onPlayModeToggle,
  volume,
  isMuted,
  onVolumeChange,
  onMuteToggle,
  playlists,
  onAddToPlaylist,
  onQueueToggle,
  showQueue,
  onRatingChange
}) => {
  const getModeLabel = () => {
    switch (playMode) {
      case 'repeat-all': return 'Repeat All';
      case 'repeat-one': return 'Repeat One';
      case 'shuffle': return 'Shuffle';
      default: return 'Sequential';
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div 
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          
          {/* Panel */}
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed bottom-0 left-0 right-0 bg-zinc-900 border-t border-white/10 rounded-t-3xl z-50 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Handle bar */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-10 h-1 bg-zinc-600 rounded-full" />
            </div>

            {/* Track info */}
            <div className="px-4 pb-3 border-b border-white/5">
              <div className="flex items-center gap-3">
                <TrackCover track={track} className="w-12 h-12 rounded-lg" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{track.title}</p>
                  <p className="text-sm text-zinc-400 truncate">{track.artist}</p>
                </div>
                <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Actions */}
            <div className="p-4 space-y-4">
              {/* Volume control */}
              <div className="flex items-center gap-4">
                <button 
                  onClick={onMuteToggle}
                  className="p-2 text-zinc-400 hover:text-white rounded-lg hover:bg-white/5"
                >
                  {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                </button>
                <div className="flex-1">
                  <VolumeSlider 
                    volume={volume}
                    isMuted={isMuted}
                    onVolumeChange={onVolumeChange}
                  />
                </div>
                <span className="text-xs text-zinc-400 w-8">{isMuted ? 0 : volume}%</span>
              </div>

              {/* Like/Dislike - Mobile prominent display */}
              <div className="flex items-center justify-center gap-6 py-2">
                <LikeDislikeInline trackId={track.id} onRatingChange={onRatingChange} />
                <span className="text-xs text-zinc-500">Rate this track</span>
              </div>

              {/* Action buttons */}
              <div className="grid grid-cols-4 gap-2">
                {/* Play Mode */}
                <button 
                  onClick={onPlayModeToggle}
                  className="flex flex-col items-center gap-1 p-3 rounded-xl hover:bg-white/5 transition-colors"
                >
                  <PlayModeIcon mode={playMode} className={`w-5 h-5 ${playMode !== 'sequential' ? 'text-emerald-400' : 'text-zinc-400'}`} />
                  <span className="text-xs text-zinc-400">{getModeLabel()}</span>
                </button>

                {/* Queue */}
                <button 
                  onClick={() => { onQueueToggle(); onClose(); }}
                  className="flex flex-col items-center gap-1 p-3 rounded-xl hover:bg-white/5 transition-colors"
                >
                  <ListMusic className={`w-5 h-5 ${showQueue ? 'text-emerald-400' : 'text-zinc-400'}`} />
                  <span className="text-xs text-zinc-400">Queue</span>
                </button>

                {/* Download */}
                <div className="flex flex-col items-center gap-1 p-3 rounded-xl hover:bg-white/5 transition-colors">
                  <DownloadButton track={track} compact />
                  <span className="text-xs text-zinc-400">Download</span>
                </div>

                {/* Add to Playlist */}
                <div className="flex flex-col items-center gap-1 p-3 rounded-xl hover:bg-white/5 transition-colors">
                  {playlists && onAddToPlaylist ? (
                    <>
                      <AddToPlaylistButton 
                        track={track}
                        playlists={playlists}
                        onAddToPlaylist={onAddToPlaylist}
                        compact
                      />
                      <span className="text-xs text-zinc-400">Add</span>
                    </>
                  ) : (
                    <>
                      <ListPlus className="w-5 h-5 text-zinc-600" />
                      <span className="text-xs text-zinc-500">Add</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default function MiniPlayer({
  track,
  isPlaying,
  currentTime,
  duration,
  volume,
  isMuted,
  playMode,
  leftBars,
  rightBars,
  playlists,
  onTogglePlay,
  onPrev,
  onNext,
  onSeek,
  onVolumeChange,
  onMuteToggle,
  onPlayModeToggle,
  onExpand,
  onQueueToggle,
  onAddToPlaylist,
  showQueue,
  onRatingChange
}) {
  const [showMobileActions, setShowMobileActions] = useState(false);

  const getModeColor = () => {
    if (playMode === 'sequential') return 'text-zinc-400';
    return 'text-emerald-400';
  };

  const getModeLabel = () => {
    switch (playMode) {
      case 'repeat-all': return 'Repeat All';
      case 'repeat-one': return 'Repeat One';
      case 'shuffle': return 'Shuffle';
      default: return 'Sequential';
    }
  };

  return (
    <>
      <motion.div 
        initial={{ y: 100 }} 
        animate={{ y: 0 }} 
        className="bg-gradient-to-r from-zinc-900/95 via-zinc-800/95 to-zinc-900/95 backdrop-blur-xl border-t border-white/10"
      >
        {/* Progress bar on top - always visible, full width */}
        <div className="px-2 pt-2">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <span className="w-10 text-right text-[10px] shrink-0">{formatTime(currentTime)}</span>
            <ProgressSlider 
              currentTime={currentTime}
              duration={duration}
              onSeek={onSeek}
            />
            <span className="w-10 text-[10px] shrink-0">{formatTime(duration)}</span>
          </div>
        </div>

        {/* Main content - FIXED WIDTH ZONES to prevent layout shift */}
        <div className="flex items-center px-2 py-2">
          {/* LEFT ZONE: Track info - FIXED WIDTH */}
          <div 
            className="flex items-center gap-2 cursor-pointer group w-[140px] sm:w-[180px] md:w-[220px] shrink-0" 
            onClick={onExpand}
          >
            <div className="relative shrink-0">
              <TrackCover 
                track={track} 
                className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg overflow-hidden"
              />
              {isPlaying && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-lg">
                  <div className="absolute inset-0 animate-pulse bg-emerald-500/20 rounded-lg"></div>
                </div>
              )}
              <div className="absolute inset-0 rounded-lg bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <Maximize2 className="w-4 h-4" />
              </div>
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-medium truncate text-sm">{track.title}</p>
              <p className="text-xs text-zinc-400 truncate">{track.artist}</p>
            </div>
          </div>
          
          {/* MIDDLE ZONE: Flexible space with visualizer on xl screens */}
          <div className="flex-1 flex justify-center items-center">
            {/* Audio visualizer - only on xl screens */}
            <div className="hidden xl:flex justify-center max-w-xs w-full">
              <AudioVisualizer 
                leftBars={leftBars} 
                rightBars={rightBars} 
                isPlaying={isPlaying}
                variant="mini"
              />
            </div>
          </div>
          
          {/* RIGHT ZONE: Controls - FIXED WIDTH */}
          <div className="flex items-center gap-1 shrink-0">
            {/* Like/Dislike buttons - hidden on xs, shown on sm+ */}
            <div className="hidden sm:flex items-center">
              <LikeDislikeInline trackId={track.id} onRatingChange={onRatingChange} />
            </div>

            {/* Core playback controls - always visible */}
            <div className="flex items-center gap-1 sm:gap-2">
              <button onClick={onPrev} className="p-1 sm:p-1.5 text-zinc-400 hover:text-white transition-colors">
                <SkipBack className="w-4 h-4 sm:w-5 sm:h-5" />
              </button>
              <button 
                onClick={onTogglePlay} 
                className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-white flex items-center justify-center hover:scale-105 transition-transform"
              >
                {isPlaying ? (
                  <Pause className="w-4 h-4 sm:w-5 sm:h-5 text-black" />
                ) : (
                  <Play className="w-4 h-4 sm:w-5 sm:h-5 text-black ml-0.5" />
                )}
              </button>
              <button onClick={onNext} className="p-1 sm:p-1.5 text-zinc-400 hover:text-white transition-colors">
                <SkipForward className="w-4 h-4 sm:w-5 sm:h-5" />
              </button>
            </div>

            {/* Secondary controls - hidden on very small screens, shown progressively */}
            <div className="flex items-center gap-1">
              {/* Play mode - hidden on xs, shown on sm+ */}
              <button 
                onClick={onPlayModeToggle} 
                className={`p-1.5 rounded-full hidden sm:block ${getModeColor()} hover:text-white transition-colors`}
                title={getModeLabel()}
              >
                <PlayModeIcon mode={playMode} className="w-4 h-4" />
              </button>

              {/* Download - hidden on xs/sm, shown on md+ */}
              <div className="hidden md:block">
                <DownloadButton track={track} />
              </div>

              {/* Add to playlist - hidden on xs/sm, shown on md+ */}
              {playlists && onAddToPlaylist && (
                <div className="hidden md:block">
                  <AddToPlaylistButton 
                    track={track}
                    playlists={playlists}
                    onAddToPlaylist={onAddToPlaylist}
                  />
                </div>
              )}

              {/* Queue button - hidden on xs, shown on sm+ */}
              <button 
                onClick={onQueueToggle} 
                className={`p-1.5 rounded-full hidden sm:block ${showQueue ? 'text-emerald-400' : 'text-zinc-400 hover:text-white'} transition-colors`}
              >
                <ListMusic className="w-4 h-4" />
              </button>

              {/* Volume controls - only on lg+ */}
              <div className="hidden lg:flex items-center gap-2">
                <button onClick={onMuteToggle} className="p-1.5 text-zinc-400 hover:text-white transition-colors">
                  {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                </button>
                <VolumeSlider 
                  volume={volume}
                  isMuted={isMuted}
                  onVolumeChange={onVolumeChange}
                />
              </div>

              {/* Expand button - hidden on xs, shown on sm+ */}
              <button 
                onClick={onExpand} 
                className="p-1.5 text-zinc-400 hover:text-white transition-colors hidden sm:block"
              >
                <Maximize2 className="w-4 h-4" />
              </button>

              {/* More button - only shown on mobile to access hidden controls */}
              <button 
                onClick={() => setShowMobileActions(true)}
                className="p-1.5 text-zinc-400 hover:text-white transition-colors sm:hidden"
              >
                <MoreHorizontal className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Mobile actions panel */}
      <MobileActionsPanel 
        track={track}
        isOpen={showMobileActions}
        onClose={() => setShowMobileActions(false)}
        playMode={playMode}
        onPlayModeToggle={onPlayModeToggle}
        volume={volume}
        isMuted={isMuted}
        onVolumeChange={onVolumeChange}
        onMuteToggle={onMuteToggle}
        playlists={playlists}
        onAddToPlaylist={onAddToPlaylist}
        onQueueToggle={onQueueToggle}
        showQueue={showQueue}
        onRatingChange={onRatingChange}
      />
    </>
  );
}
