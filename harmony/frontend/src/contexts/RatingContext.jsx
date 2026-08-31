import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { ratingApi } from '../api/client';

const RatingContext = createContext(null);

export function RatingProvider({ children }) {
  const [trackRatings, setTrackRatings] = useState({});
  const [loading, setLoading] = useState(true);

  // Fetch all user ratings on mount
  const fetchUserRatings = useCallback(async () => {
    try {
      const data = await ratingApi.getMyRatings();
      const ratingsMap = {};
      data.ratings.forEach(r => {
        ratingsMap[r.track_id] = {
          rating: r.rating,  
          count_today: 0,    
          remaining_today: 10 
        };
      });
      setTrackRatings(ratingsMap);
    } catch (err) {
      console.error('Failed to fetch user ratings:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUserRatings();
  }, [fetchUserRatings]);

  /**
   * Rate a track
   * @param trackId - Track ID
   * @param vote - -1 (dislike) or 1 (like)
   * @returns {Promise<{success: boolean, error?: string, trackPopularity?: number}>}
   */
  const rateTrack = useCallback(async (trackId, vote) => {
    try {
      const data = await ratingApi.rateTrack(trackId, vote);
      
      setTrackRatings(prev => ({
        ...prev,
        [trackId]: {
          rating: data.your_total_contribution,
          count_today: data.count_today,
          remaining_today: data.remaining_today
        }
      }));

      return { 
        success: true, 
        trackPopularity: data.track_popularity,
        remaining: data.remaining_today 
      };
    } catch (err) {
      const errorMessage = err.response?.data?.detail || 'Failed to rate track';
      return { success: false, error: errorMessage };
    }
  }, []);

  /**
   * Get user's rating info for a track
   */
  const getTrackRating = useCallback((trackId) => {
    return trackRatings[trackId] || { rating: 0, count_today: 0, remaining_today: 10 };
  }, [trackRatings]);

  /**
   * Check if user can rate this specific track today
   */
  const canRateTrack = useCallback((trackId) => {
    const info = getTrackRating(trackId);
    return info.remaining_today > 0;
  }, [getTrackRating]);

  const value = {
    trackRatings,
    loading,
    rateTrack,
    getTrackRating,
    canRateTrack,
    refreshRatings: fetchUserRatings
  };

  return (
    <RatingContext.Provider value={value}>
      {children}
    </RatingContext.Provider>
  );
}

export const useRating = () => {
  const context = useContext(RatingContext);
  if (!context) {
    throw new Error('useRating must be used within a RatingProvider');
  }
  return context;
};