import React, { useEffect, useMemo, useRef, useState } from 'react';
import { FileText, Loader2, Upload } from 'lucide-react';
import api from '../api/client';
import { activeLineIndex, looksLikeLrc, parseLrc, shiftLrc } from '../utils/lrc';

const OFFSET_STEP = 0.5;

function roundOffset(value) {
  return Math.round(value * 10) / 10;
}

function formatOffset(value) {
  if (value === 0) return '0.0s';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}s`;
}

function OffsetButtons({ value, onMinus, onPlus, minusDisabled, plusDisabled, disabled, display }) {
  return (
    <div className="inline-flex items-center gap-0.5 text-[11px] text-zinc-500">
      <button
        type="button"
        className="px-1.5 py-0.5 rounded hover:bg-white/10 hover:text-zinc-200 disabled:opacity-40"
        disabled={disabled || minusDisabled}
        onClick={onMinus}
        title="Lyrics earlier (−0.5s)"
      >
        −
      </button>
      <span className="min-w-[3.2rem] text-center tabular-nums text-zinc-400">
        {display ?? formatOffset(value)}
      </span>
      <button
        type="button"
        className="px-1.5 py-0.5 rounded hover:bg-white/10 hover:text-zinc-200 disabled:opacity-40"
        disabled={disabled || plusDisabled}
        onClick={onPlus}
        title="Lyrics later (+0.5s)"
      >
        +
      </button>
    </div>
  );
}

function FilePicker({ fileRef, uploading, label, className, onFile }) {
  return (
    <label className={className}>
      <Upload className="w-3 h-3" />
      {uploading ? 'Uploading…' : label}
      <input
        ref={fileRef}
        type="file"
        accept=".lrc,.txt,text/plain"
        className="sr-only"
        disabled={uploading}
        onChange={(event) => onFile(event.target.files?.[0])}
      />
    </label>
  );
}

function ReplaceBar({
  replacing,
  uploading,
  importOffset,
  fileRef,
  closedLabel = 'Replace',
  closedClassName = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] text-zinc-400 hover:text-zinc-100 hover:bg-white/10',
  onReplace,
  onCancel,
  onMinus,
  onPlus,
  onFile,
}) {
  return (
    <div className="relative z-50 mt-2 shrink-0 flex flex-col items-center gap-1.5 pointer-events-auto">
      {replacing ? (
        <>
          <OffsetButtons
            value={importOffset}
            disabled={uploading}
            minusDisabled={importOffset <= -10}
            plusDisabled={importOffset >= 10}
            onMinus={onMinus}
            onPlus={onPlus}
          />
          <p className="text-[10px] text-zinc-600">Timing offset applied on import</p>
          <div className="flex items-center gap-3">
            <FilePicker
              fileRef={fileRef}
              uploading={uploading}
              label="Choose file"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 hover:bg-white/15 text-[11px] text-zinc-200 cursor-pointer"
              onFile={onFile}
            />
            <button
              type="button"
              className="text-[11px] text-zinc-500 hover:text-zinc-300"
              onClick={onCancel}
            >
              Cancel
            </button>
          </div>
        </>
      ) : (
        <button type="button" className={closedClassName} onClick={onReplace}>
          <Upload className="w-3 h-3" />
          {closedLabel}
        </button>
      )}
    </div>
  );
}

export default function LyricsPanel({
  trackId,
  currentTime,
  onSeek,
  fontFamily,
  lineScale = 1,
  viewportHeight,
  side = false,
}) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [importOffset, setImportOffset] = useState(0);
  const [replacing, setReplacing] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    if (!trackId) return undefined;
    let cancelled = false;
    setLoading(true);
    setError('');
    setImportOffset(0);
    setReplacing(false);

    api.get(`/music/${trackId}/lyrics`)
      .then(({ data }) => {
        if (!cancelled) setPayload(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.response?.data?.detail || 'Failed to load lyrics');
        setPayload(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [trackId]);

  const timed = useMemo(() => {
    const text = payload?.text || '';
    const format = payload?.format || (looksLikeLrc(text) ? 'lrc' : 'plain');
    if (format !== 'lrc') return [];
    return parseLrc(text);
  }, [payload]);

  const active = timed.length ? activeLineIndex(timed, currentTime) : -1;

  async function uploadFile(file) {
    if (!file || !trackId) return;
    setUploading(true);
    setError('');
    try {
      let body = await file.text();
      if (importOffset && looksLikeLrc(body)) {
        body = shiftLrc(body, importOffset);
      }
      const data = new FormData();
      data.append('text', body);
      const res = await api.post(`/music/${trackId}/lyrics`, data, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPayload(res.data);
      setImportOffset(0);
      setReplacing(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to import lyrics');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  const canReplace = payload?.source === 'upload';
  const importBar = (
    <ReplaceBar
      replacing={replacing}
      uploading={uploading}
      importOffset={importOffset}
      fileRef={fileRef}
      closedLabel={canReplace ? 'Replace' : 'Import lyrics'}
      closedClassName={
        canReplace
          ? 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] text-zinc-400 hover:text-zinc-100 hover:bg-white/10'
          : 'inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 hover:bg-white/15 text-sm text-zinc-200'
      }
      onReplace={() => setReplacing(true)}
      onCancel={() => {
        setReplacing(false);
        setImportOffset(0);
      }}
      onMinus={() => setImportOffset((v) => roundOffset(v - OFFSET_STEP))}
      onPlus={() => setImportOffset((v) => roundOffset(v + OFFSET_STEP))}
      onFile={(file) => void uploadFile(file)}
    />
  );
  const replaceBar = canReplace ? importBar : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-zinc-500">
        <Loader2 className="w-5 h-5 animate-spin" />
      </div>
    );
  }

  if (!payload?.has_lyrics) {
    return (
      <div className="w-full max-w-lg mx-auto text-center px-4 py-4">
        <FileText className="w-8 h-8 mx-auto mb-2 text-zinc-600" />
        <p className="text-sm text-zinc-400">No lyrics for this track</p>
        <p className="text-xs text-zinc-600 mt-1">
          Import a .lrc (timed) or .txt file, or put one next to the audio file
        </p>
        {error ? <p className="text-xs text-red-400 mt-2">{error}</p> : null}
        <div className="mt-1">{importBar}</div>
      </div>
    );
  }

  if (timed.length) {
    const lineHeight = Math.round(Math.min(44, Math.max(38, 40 * Math.min(lineScale, 1.08))));
    const chrome = replaceBar ? 44 : 8;
    const rawView = (viewportHeight ?? 200) - chrome;
    const viewH = Math.min(300, Math.max(lineHeight * 3, rawView));
    const offset = viewH / 2 - (Math.max(active, 0) + 0.5) * lineHeight;

    function handleViewportClick(event) {
      const rect = event.currentTarget.getBoundingClientRect();
      const index = Math.floor((event.clientY - rect.top - offset) / lineHeight);
      if (index >= 0 && index < timed.length) {
        onSeek?.(timed[index].time);
      }
    }

    const fade = viewH < lineHeight * 5 ? 8 : 18;

    return (
      <div className={`w-full mx-auto min-h-0 flex flex-col ${side ? 'max-w-xl' : 'max-w-lg'}`} style={{ fontFamily }}>
        <div
          className="relative overflow-hidden"
          onClick={handleViewportClick}
          style={{
            height: viewH,
            clipPath: 'inset(0)',
            maskImage: `linear-gradient(to bottom, transparent 0%, #000 ${fade}%, #000 ${100 - fade}%, transparent 100%)`,
            WebkitMaskImage: `linear-gradient(to bottom, transparent 0%, #000 ${fade}%, #000 ${100 - fade}%, transparent 100%)`,
          }}
        >
          <div
            className="px-2 pointer-events-none"
            style={{
              transform: `translate3d(0, ${offset}px, 0)`,
              transition: 'transform 0.55s cubic-bezier(0.22, 1, 0.36, 1)',
              willChange: 'transform',
            }}
          >
            {timed.map((line, index) => {
              const distance = Math.abs(index - Math.max(active, 0));
              const isActive = index === active;
              return (
                <div
                  key={`${line.time}-${index}`}
                  className="block w-full text-center px-3 rounded-lg"
                  style={{
                    height: lineHeight,
                    lineHeight: `${lineHeight}px`,
                    fontSize: isActive ? 17 : 14.5,
                    fontWeight: isActive ? 650 : 400,
                    color: isActive
                      ? '#fff'
                      : distance === 1
                        ? 'rgba(255,255,255,0.42)'
                        : 'rgba(255,255,255,0.22)',
                    transform: `scale(${isActive ? 1.04 : 1})`,
                    transition: 'color 0.35s ease, font-size 0.35s ease, font-weight 0.35s ease, transform 0.45s cubic-bezier(0.22, 1, 0.36, 1)',
                  }}
                >
                  <span className="block truncate">{line.text}</span>
                </div>
              );
            })}
          </div>
        </div>
        {replaceBar}
        {error ? <p className="text-[10px] text-center text-red-400 mt-1">{error}</p> : null}
      </div>
    );
  }

  return (
    <div className="w-full max-w-lg mx-auto min-h-0 flex flex-col" style={{ fontFamily }}>
      <pre
        className="whitespace-pre-wrap text-center text-sm leading-7 text-zinc-300 overflow-y-auto px-3 max-h-56 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {payload.text}
      </pre>
      {replaceBar}
    </div>
  );
}
