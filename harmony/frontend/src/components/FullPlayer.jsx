import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Play, Pause, SkipBack, SkipForward, Shuffle, 
  Repeat, Repeat1, ChevronDown, Music,
  ListPlus, Check, ListMusic, Mic2
} from 'lucide-react';
import AudioVisualizer from './AudioVisualizer';
import LyricsPanel from './LyricsPanel';
import { PlayerBackground, BackgroundSelector } from './PlayerBackgrounds';
import { FontSelector, fontById } from './LyricFonts';
import { formatTime, formatPlayCount } from '../utils/helpers';

/**
 * Add to Playlist Button for FullPlayer
 */
const AddToPlaylistButton = ({ track, playlists, onAddToPlaylist }) => {
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
          className={`p-2 rounded-full transition-all duration-300
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
            <Check className="w-5 h-5 text-emerald-400" />
          ) : (
            <ListPlus className="w-5 h-5" />
          )}
        </motion.div>
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

/**
 * Progress slider with gradient fill on left side of thumb
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
      className="w-full h-1.5 cursor-pointer rounded-full appearance-none"
      style={sliderStyle}
    />
  );
};

const ART_LYRICS = 184;
const ART_ASIDE = 196;
const ART_SOLO = 216;
const LYRIC_LINE = 40;
const LYRIC_MIN = 168;
const LYRIC_MAX_STACK = 220;
const LYRIC_MAX_ASIDE = 300;

function lyricLayout({ height, width, showLyrics }) {
  const need = LYRIC_LINE * 3 + 40;
  const headerH = 72;
  const titleH = 64;
  const controlsH = 128;
  const gapH = 28;

  let artBox = showLyrics ? ART_LYRICS : ART_SOLO;
  let stackedH = height - headerH - artBox - titleH - controlsH - gapH;
  let aside = false;

  if (showLyrics && stackedH < need && width >= 768) {
    aside = true;
    artBox = ART_ASIDE;
  }

  const viewportHeight = aside
    ? Math.min(LYRIC_MAX_ASIDE, Math.max(LYRIC_MIN, height - headerH - 64))
    : Math.min(LYRIC_MAX_STACK, Math.max(LYRIC_MIN, stackedH));

  return { artBox, aside, viewportHeight };
}

const AlbumArtwork = ({ track, isPlaying, box = ART_SOLO }) => {
  const [imageError, setImageError] = React.useState(false);
  const token = localStorage.getItem('token');
  const hasCover = Boolean(track.cover_path) && !imageError;
  const coverSrc = hasCover
    ? `/api/music/${track.id}/cover?token=${encodeURIComponent(token)}`
    : null;
  const boxStyle = { width: box, height: box, maxWidth: '100%' };

  return (
    <div className="relative z-20 flex-shrink-0" style={boxStyle}>
      <AnimatePresence>
        {isPlaying ? (
          <motion.div
            key="art-bloom"
            className="absolute -inset-1.5 pointer-events-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.35 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
            style={{
              filter: 'blur(8px)',
              borderRadius: 18,
            }}
          >
            {coverSrc ? (
              <img src={coverSrc} alt="" className="w-full h-full object-cover rounded-[28px]" />
            ) : (
              <div className="w-full h-full rounded-[28px] bg-white/35" />
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="relative z-[1] w-full h-full rounded-2xl overflow-hidden">
        {coverSrc ? (
          <img
            src={coverSrc}
            alt={track.title}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="relative w-full h-full bg-gradient-to-br from-zinc-800 to-zinc-900 flex items-center justify-center overflow-hidden">
            {isPlaying ? (
              <motion.div
                className="absolute inset-0 opacity-30"
                style={{
                  background:
                    'linear-gradient(135deg, rgba(16, 185, 129, 0.3), transparent, rgba(6, 182, 212, 0.3))',
                }}
                animate={{ rotate: 360 }}
                transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
              />
            ) : null}
            <Music className="relative w-14 h-14 text-zinc-600" />
          </div>
        )}
      </div>
    </div>
  );
};

export default function FullPlayer({
  track,
  isPlaying,
  currentTime,
  duration,
  playMode,
  leftBars,
  rightBars,
  playlists,
  onTogglePlay,
  onPrev,
  onNext,
  onSeek,
  onPlayModeToggle,
  onCollapse,
  onAddToPlaylist
}) {
  const [isCompact, setIsCompact] = useState(false);
  const [viewSize, setViewSize] = useState(() => ({
    w: typeof window === 'undefined' ? 1280 : window.innerWidth,
    h: typeof window === 'undefined' ? 800 : window.innerHeight,
  }));
  const [showLyrics, setShowLyrics] = useState(() => {
    return localStorage.getItem('playerShowLyrics') !== '0';
  });
  const [backgroundId, setBackgroundId] = useState(() => {
    return localStorage.getItem('playerBackground') || 'orbs';
  });
  const [fontId, setFontId] = useState(() => {
    return localStorage.getItem('playerLyricFont') || 'sans';
  });
  const lyricFont = fontById(fontId);
  const lyricsSlotRef = useRef(null);
  const [lyricsSlotH, setLyricsSlotH] = useState(0);

  const handleLyricsToggle = () => {
    setShowLyrics((prev) => {
      const next = !prev;
      localStorage.setItem('playerShowLyrics', next ? '1' : '0');
      return next;
    });
  };

  const handleBackgroundChange = (id) => {
    setBackgroundId(id);
    localStorage.setItem('playerBackground', id);
  };

  const handleFontChange = (id) => {
    setFontId(id);
    localStorage.setItem('playerLyricFont', id);
  };

  useEffect(() => {
    const checkView = () => {
      const vh = window.innerHeight;
      const vw = window.innerWidth;
      setIsCompact(vh < 580);
      setViewSize({ w: vw, h: vh });
    };

    checkView();
    window.addEventListener('resize', checkView);
    return () => window.removeEventListener('resize', checkView);
  }, []);

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

  const { artBox, aside: lyricsAside, viewportHeight: lyricsViewport } = lyricLayout({
    height: viewSize.h,
    width: viewSize.w,
    showLyrics,
  });

  useEffect(() => {
    const el = lyricsSlotRef.current;
    if (!el || lyricsAside || !showLyrics) {
      setLyricsSlotH(0);
      return undefined;
    }
    const ro = new ResizeObserver(([entry]) => {
      setLyricsSlotH(entry.contentRect.height);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [lyricsAside, showLyrics, artBox]);

  const lyricsPanel = showLyrics ? (
    <LyricsPanel
      trackId={track.id}
      currentTime={currentTime}
      onSeek={onSeek}
      fontFamily={lyricFont.family}
      lineScale={lyricFont.lineScale || 1}
      viewportHeight={lyricsAside ? lyricsViewport : Math.min(LYRIC_MAX_STACK, lyricsSlotH || lyricsViewport)}
      side={lyricsAside}
    />
  ) : null;

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }} 
      className="fixed inset-0 z-[80] flex flex-col bg-zinc-950 text-white overflow-hidden"
    >
      <PlayerBackground backgroundId={backgroundId} isPlaying={isPlaying} />
      <div id="player-fx-front" className="absolute inset-0 z-[15] pointer-events-none overflow-hidden" />

      <div className="absolute top-0 inset-x-0 z-40 flex items-center justify-between text-white p-3 sm:p-4 pointer-events-none">
        <button 
          onClick={onCollapse} 
          className="pointer-events-auto p-2 rounded-full hover:bg-white/10 transition-colors"
        >
          <ChevronDown className="w-5 h-5 sm:w-6 sm:h-6" />
        </button>
        <p className="text-sm text-zinc-400 font-medium tracking-wide">Now Playing</p>
        <div className="pointer-events-auto flex items-center">
          <FontSelector current={fontId} onChange={handleFontChange} />
          <BackgroundSelector current={backgroundId} onChange={handleBackgroundChange} />
        </div>
      </div>
      
      <div
        className={`relative flex-1 min-h-0 text-white px-4 md:px-8 pt-14 sm:pt-16 overflow-visible ${
          lyricsAside
            ? 'flex flex-row items-center justify-center gap-8 lg:gap-14 py-2'
            : `flex flex-col items-center justify-center ${
                isCompact ? 'py-2' : 'pb-6'
              }`
        }`}
      >
        <div
          className={`relative z-10 flex flex-col items-center ${
            lyricsAside
              ? 'flex-shrink-0 w-[min(100%,22rem)] gap-4'
              : `w-full flex-1 min-h-0 ${isCompact ? 'gap-3' : 'gap-4'}`
          }`}
        >
        <div className="relative flex-shrink-0 z-20 overflow-visible">
          <AlbumArtwork track={track} isPlaying={isPlaying} box={artBox} />
        </div>
        
        <div className="relative z-20 text-center max-w-md flex-shrink-0" style={{ fontFamily: lyricFont.family }}>
          <motion.h2 
            className="text-xl sm:text-2xl font-bold mb-1 truncate px-4 text-white"
            animate={isPlaying ? { opacity: [0.9, 1, 0.9] } : { opacity: 1 }}
            transition={{ duration: 3, repeat: Infinity }}
          >
            {track.title}
          </motion.h2>
          <p className="text-sm text-zinc-400 truncate px-6">
            <span>{track.artist}</span>
            {track.album ? (
              <>
                <span className="mx-1.5 text-zinc-600">·</span>
                <span className="text-zinc-500">{track.album}</span>
              </>
            ) : null}
            <span className="mx-1.5 text-zinc-600">·</span>
            <span className="text-zinc-500">{formatPlayCount(track.play_count)} plays</span>
          </p>
        </div>
        
        {!showLyrics && (
          <div className="relative z-20 w-full max-w-lg flex-shrink-0">
            <AudioVisualizer 
              leftBars={leftBars} 
              rightBars={rightBars} 
              isPlaying={isPlaying}
              variant="full"
            />
          </div>
        )}

        {showLyrics && !lyricsAside ? (
          <div ref={lyricsSlotRef} className="relative z-30 w-full flex-1 min-h-0 flex flex-col justify-center">
            {lyricsPanel}
          </div>
        ) : null}
        
        <div className={`relative z-20 w-full max-w-md flex-shrink-0 ${lyricsAside ? 'mt-1' : ''}`}>
          <ProgressSlider 
            currentTime={currentTime}
            duration={duration}
            onSeek={onSeek}
          />
          <div className="flex justify-between text-sm mt-2 text-zinc-400">
            <span className="font-mono">{formatTime(currentTime)}</span>
            <span className="font-mono">{formatTime(duration)}</span>
          </div>
          <div className="flex items-center justify-between mt-3">
            <button 
              onClick={onPlayModeToggle} 
              className="p-2 rounded-full transition-all text-zinc-400 hover:text-white hover:bg-white/10"
              title={getModeLabel()}
            >
              <PlayModeIcon mode={playMode} className={`w-5 h-5 ${getModeColor()}`} />
            </button>
            <button 
              onClick={onPrev} 
              className="p-2 rounded-full text-white hover:text-emerald-400 hover:bg-white/10 transition-all"
            >
              <SkipBack className="w-5 h-5" />
            </button>
            <motion.button 
              onClick={onTogglePlay} 
              className="w-12 h-12 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center shadow-lg"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              style={{
                boxShadow: isPlaying 
                  ? '0 0 24px rgba(16, 185, 129, 0.35)'
                  : '0 8px 20px rgba(0, 0, 0, 0.3)'
              }}
            >
              {isPlaying ? (
                <Pause className="w-5 h-5 text-black" />
              ) : (
                <Play className="w-5 h-5 text-black ml-0.5" />
              )}
            </motion.button>
            <button 
              onClick={onNext} 
              className="p-2 rounded-full text-white hover:text-emerald-400 hover:bg-white/10 transition-all"
            >
              <SkipForward className="w-5 h-5" />
            </button>
            <button
              type="button"
              onClick={handleLyricsToggle}
              className={`p-2 rounded-full transition-colors ${
                showLyrics ? 'text-emerald-400' : 'text-zinc-400 hover:text-white'
              }`}
              title={showLyrics ? 'Hide lyrics' : 'Show lyrics'}
            >
              <Mic2 className="w-5 h-5" />
            </button>
            {playlists && onAddToPlaylist ? (
              <AddToPlaylistButton 
                track={track}
                playlists={playlists}
                onAddToPlaylist={onAddToPlaylist}
              />
            ) : (
              <span className="w-9 h-9" />
            )}
          </div>
        </div>
        </div>

        {lyricsAside ? (
          <div className="relative z-30 flex-1 min-w-0 min-h-0 max-w-xl h-full flex flex-col justify-center">
            {lyricsPanel}
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}