/** Shared Harmony ↔ Nous playback snapshot. Keep the key in sync with Harmony. */

export const PLAYBACK_KEY = 'harmony.playback.v1';
export const PLAYER_POS_KEY = 'harmony.player.position';

export type SlimTrack = {
  id: string;
  title: string;
  artist: string;
  album?: string;
  cover_path?: string | null;
  duration?: number;
};

export type PlaybackSession = {
  track: SlimTrack;
  queue: SlimTrack[];
  currentTime: number;
  isPlaying: boolean;
  playMode: string;
  volume?: number;
  dismissed?: boolean;
  updatedAt?: number;
};

export type PlayerPos = { x: number; y: number };

export const PLAY_MODES = ['sequential', 'shuffle', 'repeat-all', 'repeat-one'] as const;

export type PlayMode = (typeof PLAY_MODES)[number];

export function nextPlayMode(mode: string): PlayMode {
  const idx = PLAY_MODES.indexOf(mode as PlayMode);
  return PLAY_MODES[(idx + 1) % PLAY_MODES.length];
}

export function loadPlayback(): PlaybackSession | null {
  try {
    const raw = localStorage.getItem(PLAYBACK_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as PlaybackSession;
    if (!data?.track?.id) return null;
    return data;
  } catch {
    return null;
  }
}

export function writePlayback(
  partial: Partial<PlaybackSession>,
): PlaybackSession | null {
  const prev = loadPlayback() || ({} as PlaybackSession);
  const next = { ...prev, ...partial, updatedAt: Date.now() };
  try {
    localStorage.setItem(PLAYBACK_KEY, JSON.stringify(next));
  } catch {
    /* quota */
  }
  return next.track ? next : null;
}

export function streamUrl(trackId: string): string {
  const token = localStorage.getItem('token') || '';
  return `/api/music/${trackId}/stream?token=${encodeURIComponent(token)}`;
}

export function coverUrl(trackId: string): string {
  const token = localStorage.getItem('token') || '';
  return `/api/music/${trackId}/cover?token=${encodeURIComponent(token)}`;
}

function harmonyAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('token') || '';
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchTrackRating(trackId: string): Promise<number> {
  const res = await fetch(`/api/ratings/status/${trackId}`, {
    headers: harmonyAuthHeaders(),
  });
  if (!res.ok) return 0;
  const data = (await res.json()) as { user_rating?: number };
  return typeof data.user_rating === 'number' ? data.user_rating : 0;
}

export async function voteTrack(
  trackId: string,
  vote: 1 | -1,
): Promise<number | null> {
  const res = await fetch(`/api/ratings/${trackId}?vote=${vote}`, {
    method: 'POST',
    headers: harmonyAuthHeaders(),
  });
  if (!res.ok) return null;
  const data = (await res.json()) as { your_total_contribution?: number };
  return typeof data.your_total_contribution === 'number'
    ? data.your_total_contribution
    : null;
}

export function nextIndex(
  queue: SlimTrack[],
  currentId: string,
  playMode: string,
): number {
  if (!queue.length) return -1;
  const idx = queue.findIndex((t) => t.id === currentId);
  if (idx < 0) return 0;
  if (playMode === 'shuffle') return Math.floor(Math.random() * queue.length);
  if (playMode === 'repeat-all' || playMode === 'sequential') {
    return (idx + 1) % queue.length;
  }
  return idx + 1 < queue.length ? idx + 1 : idx;
}

export function prevIndex(queue: SlimTrack[], currentId: string): number {
  if (!queue.length) return -1;
  const idx = queue.findIndex((t) => t.id === currentId);
  if (idx < 0) return 0;
  return idx === 0 ? queue.length - 1 : idx - 1;
}

export function loadPlayerPos(): PlayerPos | null {
  try {
    const raw = localStorage.getItem(PLAYER_POS_KEY);
    if (!raw) return null;
    const pos = JSON.parse(raw) as PlayerPos;
    if (typeof pos.x !== 'number' || typeof pos.y !== 'number') return null;
    return pos;
  } catch {
    return null;
  }
}

export function savePlayerPos(pos: PlayerPos): void {
  localStorage.setItem(PLAYER_POS_KEY, JSON.stringify(pos));
}

export function defaultPlayerPos(width = 320, height = 112): PlayerPos {
  const pad = 24;
  return {
    x: Math.max(pad, window.innerWidth - width - pad),
    y: Math.max(pad, window.innerHeight - height - pad),
  };
}

export function clampPlayerPos(
  pos: PlayerPos,
  width: number,
  height: number,
): PlayerPos {
  const pad = 8;
  const maxX = Math.max(pad, window.innerWidth - width - pad);
  const maxY = Math.max(pad, window.innerHeight - height - pad);
  return {
    x: Math.min(maxX, Math.max(pad, pos.x)),
    y: Math.min(maxY, Math.max(pad, pos.y)),
  };
}
