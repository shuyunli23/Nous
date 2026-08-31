import { useCallback, useEffect, useRef, useState } from 'react';

import { useI18n } from '../i18n';
import {
  clampPlayerPos,
  coverUrl,
  defaultPlayerPos,
  loadPlayback,
  loadPlayerPos,
  nextIndex,
  nextPlayMode,
  prevIndex,
  savePlayerPos,
  streamUrl,
  fetchTrackRating,
  voteTrack,
  writePlayback,
  type PlaybackSession,
  type SlimTrack,
} from '../harmony/playback';

const MINI = 56;
const OPEN_W = 288;
const OPEN_H = 92;
const DRAG_PX = 6;
const COLLAPSE_MS = 2800;

let sharedAudio: HTMLAudioElement | null = null;

function getAudio(): HTMLAudioElement {
  if (!sharedAudio) {
    sharedAudio = new Audio();
    sharedAudio.preload = 'auto';
  }
  return sharedAudio;
}

function StrokeIcon({
  d,
  extra,
  size = 15,
}: {
  d: string;
  extra?: string;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={d} />
      {extra ? <path d={extra} /> : null}
    </svg>
  );
}

function Icon({ path, size = 16 }: { path: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

function modeIcon(mode: string): string {
  if (mode === 'shuffle') {
    return 'M10.59 9.17 5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z';
  }
  if (mode === 'repeat-one') {
    return 'M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4zm-4-2V9h-1l-2 1v1h1.5v4H13z';
  }
  if (mode === 'repeat-all') {
    return 'M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z';
  }
  return 'M4 10h12v2H4v-2zm0 4h8v2H4v-2zm0-8h16v2H4V6z';
}

function modeLabelKey(mode: string): 'playerModeSeq' | 'playerModeShuffle' | 'playerModeRepeat' | 'playerModeOne' {
  if (mode === 'shuffle') return 'playerModeShuffle';
  if (mode === 'repeat-all') return 'playerModeRepeat';
  if (mode === 'repeat-one') return 'playerModeOne';
  return 'playerModeSeq';
}

export default function FloatingHarmonyPlayer() {
  const { t } = useI18n();
  const [session, setSession] = useState<PlaybackSession | null>(() =>
    loadPlayback(),
  );
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [coverFailed, setCoverFailed] = useState(false);
  const [rating, setRating] = useState(0);
  const [voting, setVoting] = useState(false);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState(() =>
    clampPlayerPos(loadPlayerPos() ?? defaultPlayerPos(MINI, MINI), MINI, MINI),
  );
  const drag = useRef<{ dx: number; dy: number; sx: number; sy: number; moved: boolean } | null>(null);
  const loadedId = useRef<string | null>(null);
  const hover = useRef(false);
  const collapseTimer = useRef<number | null>(null);

  const visible = Boolean(session?.track && !session.dismissed);
  const track = session?.track ?? null;
  const playMode = session?.playMode || 'sequential';
  const size = open ? { w: OPEN_W, h: OPEN_H } : { w: MINI, h: MINI };

  const persist = useCallback((partial: Partial<PlaybackSession>) => {
    const next = writePlayback(partial);
    if (next) setSession(next);
  }, []);

  const bumpOpen = useCallback(() => {
    setOpen(true);
    if (collapseTimer.current) window.clearTimeout(collapseTimer.current);
    collapseTimer.current = window.setTimeout(() => {
      if (!hover.current && !drag.current) setOpen(false);
    }, COLLAPSE_MS);
  }, []);

  const loadTrack = useCallback(
    (next: SlimTrack, startAt: number, shouldPlay: boolean) => {
      const audio = getAudio();
      const same = loadedId.current === next.id && audio.src.includes(next.id);
      if (!same) {
        audio.src = streamUrl(next.id);
        loadedId.current = next.id;
        setCoverFailed(false);
      }
      const apply = () => {
        try {
          audio.currentTime = startAt;
        } catch {
          /* not seekable yet */
        }
        if (shouldPlay) {
          void audio.play().catch(() => setPlaying(false));
        } else {
          audio.pause();
        }
      };
      if (audio.readyState >= 1) apply();
      else audio.addEventListener('loadedmetadata', apply, { once: true });
    },
    [],
  );

  useEffect(() => {
    if (!track?.id) {
      setRating(0);
      return;
    }
    let cancelled = false;
    setRating(0);
    void fetchTrackRating(track.id).then((value) => {
      if (!cancelled) setRating(value);
    });
    return () => {
      cancelled = true;
    };
  }, [track?.id]);

  useEffect(() => {
    if (!visible || !track) {
      const audio = getAudio();
      if (!audio.paused) audio.pause();
      return;
    }
    loadTrack(track, session?.currentTime ?? 0, session?.isPlaying !== false);
  }, [visible, track?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const audio = getAudio();
    const onTime = () => {
      const duration = audio.duration || track?.duration || 0;
      setProgress(duration > 0 ? audio.currentTime / duration : 0);
    };
    const onPlay = () => {
      setPlaying(true);
      persist({ isPlaying: true, currentTime: audio.currentTime });
    };
    const onPause = () => {
      setPlaying(false);
      persist({ isPlaying: false, currentTime: audio.currentTime });
    };
    const onEnded = () => {
      const current = loadPlayback();
      if (!current?.track) return;
      if (current.playMode === 'repeat-one') {
        audio.currentTime = 0;
        void audio.play();
        return;
      }
      const queue = current.queue?.length ? current.queue : [current.track];
      const idx = nextIndex(queue, current.track.id, current.playMode || 'sequential');
      const next = queue[idx];
      if (!next || next.id === current.track.id) {
        persist({ isPlaying: false, currentTime: 0 });
        return;
      }
      persist({ track: next, currentTime: 0, isPlaying: true });
      setSession((s) => (s ? { ...s, track: next, currentTime: 0, isPlaying: true } : s));
      loadTrack(next, 0, true);
    };
    const flush = () => {
      persist({ currentTime: audio.currentTime, isPlaying: !audio.paused });
    };
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('ended', onEnded);
    window.addEventListener('pagehide', flush);
    return () => {
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('ended', onEnded);
      window.removeEventListener('pagehide', flush);
    };
  }, [loadTrack, persist, track?.duration]);

  useEffect(() => {
    const onResize = () => {
      setPos((p) => clampPlayerPos(p, size.w, size.h));
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [size.w, size.h]);

  useEffect(() => {
    setPos((p) => clampPlayerPos(p, size.w, size.h));
  }, [open, size.w, size.h]);

  useEffect(
    () => () => {
      if (collapseTimer.current) window.clearTimeout(collapseTimer.current);
    },
    [],
  );

  function toggle() {
    bumpOpen();
    const audio = getAudio();
    if (audio.paused) void audio.play().catch(() => undefined);
    else audio.pause();
  }

  function skip(dir: -1 | 1) {
    bumpOpen();
    const current = loadPlayback();
    if (!current?.track) return;
    const queue = current.queue?.length ? current.queue : [current.track];
    const idx =
      dir === 1
        ? nextIndex(queue, current.track.id, current.playMode || 'sequential')
        : prevIndex(queue, current.track.id);
    const next = queue[idx];
    if (!next) return;
    persist({ track: next, currentTime: 0, isPlaying: true });
    setSession((s) => (s ? { ...s, track: next, currentTime: 0, isPlaying: true } : s));
    loadTrack(next, 0, true);
  }

  function cycleMode() {
    bumpOpen();
    const next = nextPlayMode(playMode);
    persist({ playMode: next });
    localStorage.setItem('playMode', next);
    setSession((s) => (s ? { ...s, playMode: next } : s));
  }

  async function vote(value: 1 | -1) {
    if (!track || voting) return;
    bumpOpen();
    setVoting(true);
    const next = await voteTrack(track.id, value);
    if (next != null) setRating(next);
    setVoting(false);
  }

  function close() {
    getAudio().pause();
    persist({ dismissed: true, isPlaying: false, currentTime: getAudio().currentTime });
    setSession((s) => (s ? { ...s, dismissed: true, isPlaying: false } : s));
  }

  function onPointerDown(event: React.PointerEvent<HTMLElement>) {
    if ((event.target as HTMLElement).closest('button')) return;
    drag.current = {
      dx: event.clientX - pos.x,
      dy: event.clientY - pos.y,
      sx: event.clientX,
      sy: event.clientY,
      moved: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: React.PointerEvent<HTMLElement>) {
    if (!drag.current) return;
    const dist = Math.hypot(event.clientX - drag.current.sx, event.clientY - drag.current.sy);
    if (dist > DRAG_PX) drag.current.moved = true;
    if (!drag.current.moved) return;
    event.preventDefault();
    setPos(
      clampPlayerPos(
        { x: event.clientX - drag.current.dx, y: event.clientY - drag.current.dy },
        size.w,
        size.h,
      ),
    );
  }

  function onPointerUp(event: React.PointerEvent<HTMLElement>) {
    if (!drag.current) return;
    const wasDrag = drag.current.moved;
    drag.current = null;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      /* already released */
    }
    if (wasDrag) {
      setPos((p) => {
        const next = clampPlayerPos(p, size.w, size.h);
        savePlayerPos(next);
        return next;
      });
      return;
    }
    if ((event.target as HTMLElement).closest('button')) return;
    if (open) bumpOpen();
    else bumpOpen();
  }

  if (!visible || !track) return null;

  const cover = track.cover_path && !coverFailed ? (
    <img
      className="float-player__cover"
      src={coverUrl(track.id)}
      alt=""
      draggable={false}
      onError={() => setCoverFailed(true)}
    />
  ) : (
    <div className="float-player__cover float-player__cover--empty">
      <Icon size={open ? 16 : 18} path="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
    </div>
  );

  return (
    <aside
      className={open ? 'float-player float-player--open' : 'float-player float-player--mini'}
      style={{ left: pos.x, top: pos.y, width: size.w }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onPointerEnter={() => {
        hover.current = true;
        if (open) bumpOpen();
      }}
      onPointerLeave={() => {
        hover.current = false;
        if (open) bumpOpen();
      }}
      aria-label={t('harmony.playerAria')}
    >
      <div
        className="float-player__disc"
        style={{
          background: `conic-gradient(#2dd4bf ${Math.min(100, progress * 100)}%, rgba(255,255,255,0.14) 0)`,
        }}
      >
        {cover}
        {playing && !open ? <span className="float-player__eq" aria-hidden="true" /> : null}
      </div>

      {open ? (
        <div className="float-player__body">
          <div className="float-player__meta">
            <p className="float-player__title" title={track.title}>
              {track.title}
            </p>
            <p className="float-player__artist" title={track.artist}>
              {track.artist}
            </p>
          </div>
          <div className="float-player__controls">
            <button
              type="button"
              className="float-player__btn"
              aria-label={t(`harmony.${modeLabelKey(playMode)}` as 'harmony.playerModeSeq')}
              title={t(`harmony.${modeLabelKey(playMode)}` as 'harmony.playerModeSeq')}
              onClick={cycleMode}
            >
              <Icon size={15} path={modeIcon(playMode)} />
            </button>
            <button
              type="button"
              className="float-player__btn"
              aria-label={t('harmony.playerPrev')}
              onClick={() => skip(-1)}
            >
              <Icon path="M6 6h2v12H6V6zm3.5 6 8.5 6V6l-8.5 6z" />
            </button>
            <button
              type="button"
              className="float-player__btn float-player__btn--play"
              aria-label={playing ? t('harmony.playerPause') : t('harmony.playerPlay')}
              onClick={toggle}
            >
              {playing ? (
                <Icon path="M6 5h4v14H6V5zm8 0h4v14h-4V5z" />
              ) : (
                <Icon path="M8 5v14l11-7L8 5z" />
              )}
            </button>
            <button
              type="button"
              className="float-player__btn"
              aria-label={t('harmony.playerNext')}
              onClick={() => skip(1)}
            >
              <Icon path="M6 18l8.5-6L6 6v12zM16 6h2v12h-2V6z" />
            </button>
            <div className="float-player__votes">
              <button
                type="button"
                className={`float-player__btn float-player__btn--like${rating > 0 ? ' is-on' : ''}`}
                aria-label={t('harmony.playerLike')}
                title={t('harmony.playerLike')}
                disabled={voting}
                onClick={() => void vote(1)}
              >
                <StrokeIcon
                  d="M7 10v12"
                  extra="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"
                />
              </button>
              <button
                type="button"
                className={`float-player__btn float-player__btn--dislike${rating < 0 ? ' is-on' : ''}`}
                aria-label={t('harmony.playerDislike')}
                title={t('harmony.playerDislike')}
                disabled={voting}
                onClick={() => void vote(-1)}
              >
                <StrokeIcon
                  d="M17 14V2"
                  extra="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"
                />
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <button
        type="button"
        className="float-player__close"
        aria-label={t('harmony.playerClose')}
        onClick={close}
      >
        <Icon
          size={12}
          path="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"
        />
      </button>
    </aside>
  );
}
