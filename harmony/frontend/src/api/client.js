import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = String(error.config?.url || '');
    const isAuthAttempt = url.includes('/auth/login') || url.includes('/auth/sso');
    if (error.response?.status === 401 && !isAuthAttempt) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      localStorage.removeItem('harmony_from_nous');
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

// Rating API functions
export const ratingApi = {
  /**
   * Rate a track (like/dislike)
   * @param trackId - Track ID  
   * @param rating - -1 (dislike) or 1 (like)
   */
  rateTrack: async (trackId, rating) => {
    // FIX: Change 'rating' to 'vote' to match backend parameter name
    const res = await api.post(`/ratings/${trackId}?vote=${rating}`);
    return res.data;
  },

  /**
   * Get all ratings by current user
   */
  getMyRatings: async () => {
    const res = await api.get('/ratings/my-ratings');
    return res.data;
  }
};

export default api;
