import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Music, Play, TrendingUp, Flame, RefreshCw, Sparkles, ThumbsUp, ThumbsDown } from 'lucide-react';
import { formatPlayCount } from '../utils/helpers';
import { PlaylistSelector } from '../components';
import LikeDislikeButton from '../components/LikeDislikeButton';

// Album cover component with fallback
const AlbumCover = ({ track, size = "default" }) => {
  const [imageError, setImageError] = React.useState(false);
  const token = localStorage.getItem('token');
  
  const sizeClasses = {
    small: "w-10 h-10",
    default: "w-full aspect-square",
    large: "w-full aspect-square"
  };
  
  if (track.cover_path && !imageError) {
    return (
      <img 
        src={`/api/music/${track.id}/cover?token=${encodeURIComponent(token)}`}
        alt={track.title}
        className={`${sizeClasses[size]} rounded-lg object-cover`}
        onError={() => setImageError(true)}
      />
    );
  }
  
  return (
    <div 
      className={`${sizeClasses[size]} rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-900 flex items-center justify-center`}
    >
      <Music className={size === "small" ? "w-4 h-4" : "w-8 h-8"} style={{ color: 'rgb(82 82 91)' }} />
    </div>
  );
};

// Crown SVG component
const CrownIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/>
  </svg>
);

// Flame SVG component
const FireIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M12 23c-3.9 0-7-3.1-7-7 0-2.1.9-4.5 2.6-7.1.4-.6.8-1.1 1.2-1.6l.5-.5c.3-.3.8-.3 1.1 0l.5.5c.2.2.4.5.6.8.4-.8.6-1.5.6-1.9 0-.4.3-.8.7-.9.4-.1.8.1 1 .4 1.5 2.1 3.2 5.2 3.2 8.3 0 3.9-3.1 7-7 7z"/>
  </svg>
);

// Star SVG component
const StarIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
  </svg>
);

// Ranking configuration - only for top 5
const rankConfig = {
  1: {
    badgeSize: 'w-11 h-11',
    glowSize: 'w-16 h-16',
    iconSize: 'w-5 h-5',
    fontSize: 'text-base',
    colors: {
      glow: 'bg-yellow-400',
      glowOpacity: 'opacity-50',
      badge: 'from-yellow-300 via-amber-400 to-orange-500',
      border: 'border-yellow-300/60',
      shadow: 'shadow-amber-400/50',
      iconColor: 'text-yellow-900',
      textColor: 'text-yellow-900',
    },
    card: {
      bg: 'from-yellow-500/15 via-amber-500/10 to-orange-500/15',
      border: 'border-yellow-400/40 hover:border-yellow-300/60',
      shadow: 'hover:shadow-xl hover:shadow-yellow-500/25',
    },
    Icon: CrownIcon,
    animate: true,
  },
  2: {
    badgeSize: 'w-11 h-11',
    glowSize: 'w-14 h-14',
    iconSize: 'w-4 h-4',
    fontSize: 'text-sm',
    colors: {
      glow: 'bg-slate-300',
      glowOpacity: 'opacity-40',
      badge: 'from-slate-200 via-gray-300 to-slate-400',
      border: 'border-slate-200/60',
      shadow: 'shadow-slate-300/40',
      iconColor: 'text-slate-600',
      textColor: 'text-slate-700',
    },
    card: {
      bg: 'from-slate-400/10 via-gray-300/5 to-slate-400/10',
      border: 'border-slate-300/30 hover:border-slate-200/50',
      shadow: 'hover:shadow-xl hover:shadow-slate-400/20',
    },
    Icon: CrownIcon,
    animate: false,
  },
  3: {
    badgeSize: 'w-10 h-10',
    glowSize: 'w-13 h-13',
    iconSize: 'w-3.5 h-3.5',
    fontSize: 'text-sm',
    colors: {
      glow: 'bg-amber-500',
      glowOpacity: 'opacity-35',
      badge: 'from-amber-400 via-orange-500 to-amber-600',
      border: 'border-amber-300/50',
      shadow: 'shadow-amber-500/40',
      iconColor: 'text-amber-100',
      textColor: 'text-amber-100',
    },
    card: {
      bg: 'from-amber-500/10 via-orange-500/5 to-amber-600/10',
      border: 'border-amber-400/30 hover:border-amber-300/50',
      shadow: 'hover:shadow-xl hover:shadow-amber-500/20',
    },
    Icon: CrownIcon,
    animate: false,
  },
  4: {
    badgeSize: 'w-9 h-9',
    glowSize: 'w-12 h-12',
    iconSize: 'w-3 h-3',
    fontSize: 'text-sm',
    colors: {
      glow: 'bg-rose-500',
      glowOpacity: 'opacity-25',
      badge: 'from-rose-400 via-pink-500 to-rose-600',
      border: 'border-rose-300/40',
      shadow: 'shadow-rose-400/30',
      iconColor: 'text-rose-100',
      textColor: 'text-rose-100',
    },
    card: {
      bg: 'from-rose-500/8 via-pink-500/5 to-rose-600/8',
      border: 'border-rose-400/25 hover:border-rose-300/40',
      shadow: 'hover:shadow-lg hover:shadow-rose-500/15',
    },
    Icon: FireIcon,
    animate: false,
  },
  5: {
    badgeSize: 'w-9 h-9',
    glowSize: 'w-11 h-11',
    iconSize: 'w-3 h-3',
    fontSize: 'text-xs',
    colors: {
      glow: 'bg-violet-500',
      glowOpacity: 'opacity-25',
      badge: 'from-violet-400 via-purple-500 to-violet-600',
      border: 'border-violet-300/40',
      shadow: 'shadow-violet-400/30',
      iconColor: 'text-violet-100',
      textColor: 'text-violet-100',
    },
    card: {
      bg: 'from-violet-500/8 via-purple-500/5 to-violet-600/8',
      border: 'border-violet-400/25 hover:border-violet-300/40',
      shadow: 'hover:shadow-lg hover:shadow-violet-500/15',
    },
    Icon: StarIcon,
    animate: false,
  },
};

// Ranking Badge Component - Only for top 5
const RankBadge = ({ rank }) => {
  const config = rankConfig[rank];
  if (!config) return null;
  
  const { Icon } = config;
  
  return (
    <div className="absolute -top-3 -left-3 z-20">
      {/* glowing background */}
      <div className={`absolute inset-0 ${config.glowSize} ${config.colors.glow} rounded-full blur-lg ${config.colors.glowOpacity} ${config.animate ? 'animate-pulse' : ''}`} />
      {/* main badge */}
      <div className={`
        relative ${config.badgeSize} rounded-full 
        bg-gradient-to-br ${config.colors.badge} 
        flex flex-col items-center justify-center 
        shadow-xl ${config.colors.shadow}
        border-2 ${config.colors.border}
        transition-transform duration-300 hover:scale-110
      `}>
        <Icon className={`${config.iconSize} ${config.colors.iconColor} -mb-0.5`} />
        <span className={`${config.colors.textColor} font-black ${config.fontSize} leading-none`}>{rank}</span>
      </div>
    </div>
  );
};

// Get card style - special styling only for top 5
const getCardStyle = (rank) => {
  const config = rankConfig[rank];
  if (!config) return 'bg-zinc-900/60 border-white/5 hover:border-white/10';
  
  return `bg-gradient-to-br ${config.card.bg} ${config.card.border} ${config.card.shadow}`;
};

// Format popularity score display
const formatPopularity = (score) => {
  if (score > 0) return `+${score}`;
  return score.toString();
};

// Popularity indicator component
const PopularityIndicator = ({ score }) => {
  const isPositive = score > 0;
  const isNegative = score < 0;
  
  return (
    <div className={`
      flex items-center gap-1 px-2 py-0.5 rounded-full text-xs
      ${isPositive ? 'bg-emerald-500/20 text-emerald-400' : ''}
      ${isNegative ? 'bg-red-500/20 text-red-400' : ''}
      ${score === 0 ? 'bg-zinc-700/50 text-zinc-400' : ''}
    `}>
      {isPositive && <ThumbsUp className="w-3 h-3" />}
      {isNegative && <ThumbsDown className="w-3 h-3" />}
      <span className="font-medium">{formatPopularity(score)}</span>
    </div>
  );
};

export default function HomePage({ tracks, playlists, onPlay, onAddToPlaylist }) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  // Store stable discover tracks that don't change with tracks updates
  const [discoverTracks, setDiscoverTracks] = useState([]);
  const isInitializedRef = useRef(false);

  // Initialize Discover tracks only once on mount or when explicitly refreshed
  useEffect(() => {
    if (!isInitializedRef.current && tracks.length > 0) {
      // Initial load - generate random tracks
      const shuffled = [...tracks].sort(() => Math.random() - 0.5);
      setDiscoverTracks(shuffled.slice(0, 100));
      isInitializedRef.current = true;
    }
  }, [tracks.length]); // Only depend on tracks.length, not tracks array itself

  // Top 20 trending tracks - sorted by popularity_score first, then play_count
  const topTracks = useMemo(() => {
    return [...tracks]
      .sort((a, b) => {
        // Primary sort: popularity_score (likes - dislikes) descending
        const popularityDiff = (b.popularity_score || 0) - (a.popularity_score || 0);
        if (popularityDiff !== 0) return popularityDiff;
        // Secondary sort: play_count descending
        return b.play_count - a.play_count;
      })
      .slice(0, 20);
  }, [tracks]);

  // Split into top 5 (featured) and rest (6-20)
  const featuredTracks = topTracks.slice(0, 5);
  const otherTrendingTracks = topTracks.slice(5, 20);

  // Handle Shuffle - only way to refresh Discover section
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    setTimeout(() => {
      const shuffled = [...tracks].sort(() => Math.random() - 0.5);
      setDiscoverTracks(shuffled.slice(0, 100));
      setIsRefreshing(false);
    }, 300);
  }, [tracks]);

  // Handle track play
  const handlePlayTrack = useCallback((track, trackList) => {
    onPlay(track, trackList);
  }, [onPlay]);
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0 }} 
      className="p-4 md:p-8"
    >
      <h1 className="text-2xl md:text-4xl font-bold mb-2">Welcome Back</h1>
      <p className="text-zinc-400 mb-6 md:mb-8">Discover new music</p>
      
      {tracks.length === 0 ? (
        <div className="text-center py-12">
          <Music className="w-16 h-16 mx-auto mb-4 text-zinc-600" />
          <p className="text-zinc-400 mb-2">No music yet</p>
          <p className="text-zinc-500 text-sm">Ask your administrator to add music files</p>
        </div>
      ) : (
        <>
          {/* Trending section */}
          <div className="mb-10">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-red-500 shadow-lg shadow-orange-500/20">
                <Flame className="w-5 h-5 text-white" />
              </div>
              <h2 className="text-xl font-bold">Trending</h2>
              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-gradient-to-r from-orange-500 to-red-500 text-white uppercase tracking-wider">
                Top 20
              </span>
            </div>

            {/* Featured Top 5 - Large cards with special styling */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-5 md:gap-6 mb-6">
              {featuredTracks.map((track, i) => (
                <motion.div 
                  key={track.id} 
                  initial={{ opacity: 0, y: 30, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ 
                    delay: i * 0.1,
                    type: "spring",
                    stiffness: 100,
                    damping: 15
                  }}
                  whileHover={{ 
                    scale: 1.05, 
                    y: -8,
                    transition: { type: "spring", stiffness: 400, damping: 20 }
                  }} 
                  className={`relative backdrop-blur-sm rounded-2xl p-4 pt-5 group cursor-pointer border transition-all duration-500 ${getCardStyle(i + 1)}`}
                  onClick={() => handlePlayTrack(track, topTracks)}
                >
                  {/* Rank badge */}
                  <RankBadge rank={i + 1} />
                  
                  {/* Add to playlist button */}
                  <div className="absolute top-3 right-3 z-10 opacity-0 group-hover:opacity-100 transition-all duration-300 transform translate-y-1 group-hover:translate-y-0">
                    <div onClick={(e) => e.stopPropagation()}>
                      <PlaylistSelector 
                        playlists={playlists}
                        trackId={track.id}
                        onAddToPlaylist={onAddToPlaylist}
                      />
                    </div>
                  </div>
                  
                  {/* Album cover */}
                  <div className="relative mb-4 rounded-xl overflow-hidden shadow-lg">
                    <AlbumCover track={track} size="default" />
                    {/* Hover overlay */}
                    <motion.div 
                      className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-all duration-300 flex items-center justify-center"
                      initial={false}
                    >
                      <motion.div 
                        className="w-14 h-14 rounded-full bg-emerald-500 flex items-center justify-center shadow-2xl shadow-emerald-500/50"
                        initial={{ scale: 0.8, opacity: 0 }}
                        whileHover={{ scale: 1.1 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ type: "spring", stiffness: 400, damping: 20 }}
                      >
                        <Play className="w-6 h-6 text-black ml-1" />
                      </motion.div>
                    </motion.div>
                  </div>
                  
                  {/* Track info */}
                  <div className="space-y-1">
                    <p className="font-bold truncate text-sm group-hover:text-white transition-colors">{track.title}</p>
                    <p className="text-xs text-zinc-400 truncate group-hover:text-zinc-300 transition-colors">{track.artist}</p>
                  </div>
                  
                  {/* Stats row with popularity and play count */}
                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    <PopularityIndicator score={track.popularity_score || 0} />
                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/5 text-xs text-zinc-400">
                      <TrendingUp className="w-3 h-3" />
                      <span>{formatPlayCount(track.play_count)}</span>
                    </div>
                  </div>

                  {/* Like/Dislike buttons on hover */}
                  <div 
                    className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <LikeDislikeButton trackId={track.id} compact showTooltip={false} />
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Other Trending (6-20) - Compact list */}
            {otherTrendingTracks.length > 0 && (
              <div className="bg-zinc-900/50 rounded-xl p-4 border border-white/5">
                <p className="text-sm text-zinc-400 mb-3 font-medium">More trending tracks</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {otherTrendingTracks.map((track, i) => (
                    <motion.div 
                      key={track.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.03 }}
                      className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 cursor-pointer group"
                      onClick={() => handlePlayTrack(track, topTracks)}
                    >
                      {/* Rank number */}
                      <span className="w-6 text-center text-sm font-bold text-zinc-500">
                        {i + 6}
                      </span>
                      
                      {/* Cover */}
                      <div className="w-10 h-10 rounded-lg overflow-hidden shrink-0 relative">
                        <AlbumCover track={track} size="small" />
                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                          <Play className="w-4 h-4 text-white" />
                        </div>
                      </div>
                      
                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{track.title}</p>
                        <p className="text-xs text-zinc-500 truncate">{track.artist}</p>
                      </div>
                      
                      {/* Stats */}
                      <div className="flex items-center gap-2 shrink-0">
                        <PopularityIndicator score={track.popularity_score || 0} />
                        <span className="text-xs text-zinc-500 hidden sm:block">
                          {formatPlayCount(track.play_count)}
                        </span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          {/* Random Discovery section */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-purple-600 shadow-lg shadow-violet-500/20">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-bold">Discover</h2>
                  <p className="text-xs text-zinc-500">Random picks for you</p>
                </div>
              </div>
              <motion.button
                onClick={handleRefresh}
                disabled={isRefreshing}
                className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full text-sm font-medium transition-all disabled:opacity-50"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <motion.div
                  animate={{ rotate: isRefreshing ? 360 : 0 }}
                  transition={{ duration: 0.5, ease: "linear" }}
                >
                  <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'text-emerald-400' : ''}`} />
                </motion.div>
                <span>Shuffle</span>
              </motion.button>
            </div>

            <motion.div 
              key={discoverTracks.length}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
              className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 md:gap-4"
            >
              {discoverTracks.map((track, i) => (
                <motion.div 
                  key={track.id} 
                  initial={{ opacity: 0, y: 20 }} 
                  animate={{ opacity: 1, y: 0 }} 
                  transition={{ delay: Math.min(i * 0.02, 0.5) }} 
                  className="group bg-zinc-900/50 hover:bg-zinc-800/70 rounded-xl p-3 md:p-4 transition-all duration-300 relative cursor-pointer border border-transparent hover:border-white/5" 
                  onClick={() => handlePlayTrack(track, discoverTracks)}
                >
                  {/* Add to playlist button */}
                  <div className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div onClick={(e) => e.stopPropagation()}>
                      <PlaylistSelector 
                        playlists={playlists}
                        trackId={track.id}
                        onAddToPlaylist={onAddToPlaylist}
                      />
                    </div>
                  </div>
                  
                  {/* Album cover */}
                  <div className="relative mb-3 md:mb-4">
                    <AlbumCover track={track} size="default" />
                    <div className="absolute bottom-2 right-2 w-10 h-10 rounded-full bg-emerald-500 shadow-lg shadow-emerald-500/30 opacity-0 group-hover:opacity-100 transition-all duration-300 flex items-center justify-center transform translate-y-2 group-hover:translate-y-0">
                      <Play className="w-5 h-5 text-black ml-0.5" />
                    </div>
                  </div>
                  
                  {/* Track info */}
                  <h3 className="font-semibold truncate text-sm md:text-base">{track.title}</h3>
                  <p className="text-xs md:text-sm text-zinc-400 truncate">{track.artist}</p>
                </motion.div>
              ))}
            </motion.div>

            {/* Show count info */}
            <p className="text-center text-xs text-zinc-600 mt-6">
              Showing {discoverTracks.length} of {tracks.length} tracks
            </p>
          </div>
        </>
      )}
    </motion.div>
  );
}