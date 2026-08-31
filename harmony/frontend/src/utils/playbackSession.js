/** Shared Harmony ↔ Nous playback snapshot in localStorage. */

export const PLAYBACK_KEY = 'harmony.playback.v1';
export const PLAYER_POS_KEY = 'harmony.player.position';

export function slimTrack(track) {
  if (!track || !track.id) return null;
  return {
    id: track.id,
    title: track.title || '',
    artist: track.artist || '',
    album: track.album || '',
    cover_path: track.cover_path || null,
    duration: Number(track.duration) || 0,
    play_count: Number(track.play_count) || 0,
  };
}

export function loadPlayback() {
  try {
    const raw = localStorage.getItem(PLAYBACK_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data?.track?.id) return null;
    return data;
  } catch {
    return null;
  }
}

export function writePlayback(partial) {
  const prev = loadPlayback() || {};
  const next = { ...prev, ...partial, updatedAt: Date.now() };
  if (next.track) next.track = slimTrack(next.track);
  if (Array.isArray(next.queue)) {
    next.queue = next.queue.map(slimTrack).filter(Boolean);
  }
  try {
    localStorage.setItem(PLAYBACK_KEY, JSON.stringify(next));
  } catch {
    /* quota */
  }
  return next;
}

export function streamUrl(trackId) {
  const token = localStorage.getItem('token') || '';
  return `/api/music/${trackId}/stream?token=${encodeURIComponent(token)}`;
}

export function coverUrl(trackId) {
  const token = localStorage.getItem('token') || '';
  return `/api/music/${trackId}/cover?token=${encodeURIComponent(token)}`;
}

export function nextIndex(queue, currentId, playMode) {
  if (!queue?.length) return -1;
  const idx = queue.findIndex((t) => t.id === currentId);
  if (idx < 0) return 0;
  if (playMode === 'shuffle') return Math.floor(Math.random() * queue.length);
  if (playMode === 'repeat-all' || playMode === 'sequential') {
    return (idx + 1) % queue.length;
  }
  return idx + 1 < queue.length ? idx + 1 : idx;
}

export function prevIndex(queue, currentId) {
  if (!queue?.length) return -1;
  const idx = queue.findIndex((t) => t.id === currentId);
  if (idx < 0) return 0;
  return idx === 0 ? queue.length - 1 : idx - 1;
}
