import { useEffect, useState } from 'react';

import { getCustomBg, isVideoMime } from './bgMedia';
import { packSrc, type WorkspacePrefs } from './workspace';
import { useAppearance } from './AppearanceProvider';

function LiveLayer({ scene }: { scene: string }) {
  return (
    <div className={`ws-live ws-live--${scene}`} aria-hidden="true">
      <span className="ws-live__a" />
      <span className="ws-live__b" />
      <span className="ws-live__c" />
      <span className="ws-live__d" />
      <span className="ws-live__e" />
    </div>
  );
}

function CustomMedia({ id }: { id: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [mime, setMime] = useState('');

  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;
    getCustomBg(id)
      .then((row) => {
        if (cancelled || !row) return;
        const next = URL.createObjectURL(row.blob);
        revoked = next;
        setMime(row.mime);
        setUrl(next);
      })
      .catch(() => {
        if (!cancelled) setUrl(null);
      });
    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [id]);

  if (!url) return null;
  if (isVideoMime(mime)) {
    return (
      <video
        className="ws-bg__media"
        src={url}
        autoPlay
        loop
        muted
        playsInline
      />
    );
  }
  return <img className="ws-bg__media" src={url} alt="" />;
}

function SceneLayers({ prefs }: { prefs: WorkspacePrefs }) {
  const pack = packSrc(prefs.scene);
  return (
    <>
      <div
        className={[
          'ws-atm',
          `ws-atm--${prefs.scene}`,
          prefs.motion ? 'ws-atm--live' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      />
      {pack ? <img className="ws-bg__media" src={pack} alt="" /> : null}
      {prefs.motion && prefs.scene !== 'plain' ? (
        <LiveLayer scene={prefs.scene} />
      ) : null}
    </>
  );
}

export default function WorkspaceBg() {
  const { prefs } = useAppearance();
  const ws = prefs.workspace;
  const veil = ws.veil;
  const customFallback = ws.source === 'custom' && !ws.customId;

  return (
    <div
      className={
        ws.source !== 'custom' && ws.scene === 'plain' ? 'ws-bg ws-bg--plain' : 'ws-bg'
      }
      style={{ ['--ws-veil' as string]: String(veil) }}
      aria-hidden="true"
    >
      {ws.source === 'custom' && ws.customId ? (
        <>
          <div className="ws-atm ws-atm--mesh" />
          <CustomMedia id={ws.customId} />
          {ws.motion ? <LiveLayer scene="dust" /> : null}
        </>
      ) : (
        <SceneLayers prefs={customFallback ? { ...ws, source: 'scene' } : ws} />
      )}
      <div className="ws-bg__grain" />
      <div className="ws-bg__veil" />
    </div>
  );
}
