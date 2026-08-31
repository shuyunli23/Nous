import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ThumbsUp, ThumbsDown, Loader2, Check } from 'lucide-react';
import { useRating } from '../contexts/RatingContext';

/**
 * Like/Dislike buttons for tracks with visual feedback
 */
export default function LikeDislikeButton({ 
  trackId, 
  onRatingChange,
  compact = false,
  showTooltip = true 
}) {
  const { getTrackRating, rateTrack, canRateTrack } = useRating();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showError, setShowError] = useState(false);
  const [justVoted, setJustVoted] = useState(null); // 'like' or 'dislike'

  const ratingInfo = getTrackRating(trackId);
  const canRate = canRateTrack(trackId);

  const handleRate = useCallback(async (voteValue) => {
    if (isLoading) return;

    setIsLoading(true);
    setError(null);

    const result = await rateTrack(trackId, voteValue);

    if (result.success) {
      // Show success animation
      setJustVoted(voteValue === 1 ? 'like' : 'dislike');
      setTimeout(() => setJustVoted(null), 800);

      if (onRatingChange) {
        onRatingChange(trackId, null, result.trackPopularity);
      }

      if (result.remaining === 0) {
        setError("Reached 10 votes limit for this song");
        setShowError(true);
        setTimeout(() => setShowError(false), 3000);
      }
    } else {
      setError(result.error);
      setShowError(true);
      setTimeout(() => setShowError(false), 3000);
    }
    
    setIsLoading(false);
  }, [trackId, isLoading, rateTrack, onRatingChange]);

  const buttonSize = compact ? 'w-7 h-7' : 'w-8 h-8';
  const iconSize = compact ? 'w-3.5 h-3.5' : 'w-4 h-4';

  return (
    <div className="relative flex items-center gap-1">
      {/* Like button */}
      <motion.button
        onClick={(e) => {
          e.stopPropagation();
          handleRate(1);
        }}
        disabled={isLoading || !canRate}
        className={`
          ${buttonSize} rounded-full flex items-center justify-center transition-all duration-200 relative overflow-hidden
          ${ratingInfo.rating > 0
            ? 'bg-emerald-500/30 text-emerald-400 border border-emerald-500/50'
            : 'bg-white/5 text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10 border border-transparent'
          }
          disabled:opacity-50 disabled:cursor-not-allowed
        `}
        whileHover={{ scale: canRate ? 1.1 : 1 }}
        whileTap={{ scale: canRate ? 0.95 : 1 }}
        title={`Vote Up (${ratingInfo.remaining_today} left)`}
      >
        {/* Success ripple effect */}
        <AnimatePresence>
          {justVoted === 'like' && (
            <motion.div
              initial={{ scale: 0, opacity: 1 }}
              animate={{ scale: 2, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.6 }}
              className="absolute inset-0 bg-emerald-400 rounded-full"
            />
          )}
        </AnimatePresence>

        {isLoading ? (
          <Loader2 className={`${iconSize} animate-spin`} />
        ) : justVoted === 'like' ? (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 500, damping: 15 }}
          >
            <Check className={`${iconSize} text-emerald-400`} />
          </motion.div>
        ) : (
          <ThumbsUp className={`${iconSize} ${ratingInfo.rating > 0 ? 'fill-current' : ''}`} />
        )}
      </motion.button>

      {/* Dislike button */}
      <motion.button
        onClick={(e) => {
          e.stopPropagation();
          handleRate(-1);
        }}
        disabled={isLoading || !canRate}
        className={`
          ${buttonSize} rounded-full flex items-center justify-center transition-all duration-200 relative overflow-hidden
          ${ratingInfo.rating < 0
            ? 'bg-red-500/30 text-red-400 border border-red-500/50'
            : 'bg-white/5 text-zinc-400 hover:text-red-400 hover:bg-red-500/10 border border-transparent'
          }
          disabled:opacity-50 disabled:cursor-not-allowed
        `}
        whileHover={{ scale: canRate ? 1.1 : 1 }}
        whileTap={{ scale: canRate ? 0.95 : 1 }}
        title={`Vote Down (${ratingInfo.remaining_today} left)`}
      >
        {/* Success ripple effect */}
        <AnimatePresence>
          {justVoted === 'dislike' && (
            <motion.div
              initial={{ scale: 0, opacity: 1 }}
              animate={{ scale: 2, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.6 }}
              className="absolute inset-0 bg-red-400 rounded-full"
            />
          )}
        </AnimatePresence>

        {isLoading ? (
          <Loader2 className={`${iconSize} animate-spin`} />
        ) : justVoted === 'dislike' ? (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 500, damping: 15 }}
          >
            <Check className={`${iconSize} text-red-400`} />
          </motion.div>
        ) : (
          <ThumbsDown className={`${iconSize} ${ratingInfo.rating < 0 ? 'fill-current' : ''}`} />
        )}
      </motion.button>

      {/* Rating score indicator (optional) */}
      {!compact && ratingInfo.rating !== 0 && (
        <motion.span 
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className={`text-xs font-medium ${ratingInfo.rating > 0 ? 'text-emerald-400' : 'text-red-400'}`}
        >
          {ratingInfo.rating > 0 ? '+' : ''}{ratingInfo.rating}
        </motion.span>
      )}

      {/* Tooltip */}
      {showTooltip && (
        <AnimatePresence>
          {showError && (
            <motion.div
              initial={{ opacity: 0, y: 5, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 5, scale: 0.95 }}
              className={`
                absolute -top-8 left-1/2 -translate-x-1/2 
                px-2 py-1 rounded-md text-xs whitespace-nowrap z-50
                ${error ? 'bg-red-500/90 text-white' : 'bg-zinc-800 text-zinc-300'}
              `}
            >
              {error}
              <div className={`absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 rotate-45 ${error ? 'bg-red-500/90' : 'bg-zinc-800'}`} />
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}

/**
 * Compact inline version for MiniPlayer
 */
export function LikeDislikeInline({ trackId, onRatingChange }) {
  const { getTrackRating, rateTrack, canRateTrack } = useRating();
  const [isLoading, setIsLoading] = useState(false);
  const [justVoted, setJustVoted] = useState(null);

  const ratingInfo = getTrackRating(trackId);
  const canRate = canRateTrack(trackId);

  const handleRate = async (voteValue) => {
    if (isLoading) return;

    setIsLoading(true);
    const result = await rateTrack(trackId, voteValue);
    setIsLoading(false);

    if (result.success) {
      setJustVoted(voteValue === 1 ? 'like' : 'dislike');
      setTimeout(() => setJustVoted(null), 600);
      
      if (onRatingChange) {
        onRatingChange(trackId, null, result.trackPopularity);
      }
    }
  };

  return (
    <div className="flex items-center gap-0.5">
      <motion.button
        onClick={(e) => { e.stopPropagation(); handleRate(1); }}
        disabled={isLoading || !canRate}
        className={`
          p-1.5 rounded-full transition-all relative overflow-hidden
          ${ratingInfo.rating > 0 ? 'text-emerald-400 bg-emerald-500/20' : 'text-zinc-500 hover:text-emerald-400'}
          disabled:opacity-40
        `}
        whileTap={{ scale: 0.9 }}
        title={`${ratingInfo.remaining_today} votes left`}
      >
        <AnimatePresence>
          {justVoted === 'like' && (
            <motion.div
              initial={{ scale: 0, opacity: 0.8 }}
              animate={{ scale: 2, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.5 }}
              className="absolute inset-0 bg-emerald-400 rounded-full"
            />
          )}
        </AnimatePresence>
        <ThumbsUp className={`w-4 h-4 relative z-10 ${ratingInfo.rating > 0 ? 'fill-current' : ''}`} />
      </motion.button>
      
      <motion.button
        onClick={(e) => { e.stopPropagation(); handleRate(-1); }}
        disabled={isLoading || !canRate}
        className={`
          p-1.5 rounded-full transition-all relative overflow-hidden
          ${ratingInfo.rating < 0 ? 'text-red-400 bg-red-500/20' : 'text-zinc-500 hover:text-red-400'}
          disabled:opacity-40
        `}
        whileTap={{ scale: 0.9 }}
        title={`${ratingInfo.remaining_today} votes left`}
      >
        <AnimatePresence>
          {justVoted === 'dislike' && (
            <motion.div
              initial={{ scale: 0, opacity: 0.8 }}
              animate={{ scale: 2, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.5 }}
              className="absolute inset-0 bg-red-400 rounded-full"
            />
          )}
        </AnimatePresence>
        <ThumbsDown className={`w-4 h-4 relative z-10 ${ratingInfo.rating < 0 ? 'fill-current' : ''}`} />
      </motion.button>

      {/* Show score if not zero */}
      {ratingInfo.rating !== 0 && (
        <motion.span 
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className={`text-xs font-medium ml-1 ${ratingInfo.rating > 0 ? 'text-emerald-400' : 'text-red-400'}`}
        >
          {ratingInfo.rating > 0 ? '+' : ''}{ratingInfo.rating}
        </motion.span>
      )}
    </div>
  );
}