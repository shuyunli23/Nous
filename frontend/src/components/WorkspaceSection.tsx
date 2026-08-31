import { useEffect, useId, useRef, useState } from 'react';

import { useAppearance } from '../appearance/AppearanceProvider';
import {
  deleteCustomBg,
  getCustomBg,
  isVideoMime,
  listCustomBgs,
  MAX_BG_BYTES,
  saveCustomBg,
  type CustomBgMeta,
} from '../appearance/bgMedia';
import {
  PACK_SCENE_IDS,
  packSrc,
  SCENE_HINT_KEY,
  SCENE_NAME_KEY,
  SOFT_SCENE_IDS,
  VEIL_MAX,
  VEIL_MIN,
  type WorkspaceSceneId,
} from '../appearance/workspace';
import { useI18n } from '../i18n';
import OptionToggle from './OptionToggle';

function SceneThumb({ id }: { id: WorkspaceSceneId }) {
  const pack = packSrc(id);
  return (
    <span className="ws-pick__swatch">
      <span className={`ws-atm ws-atm--${id}`} />
      {pack ? <img className="ws-bg__media" src={pack} alt="" /> : null}
    </span>
  );
}

function CustomThumb({ id }: { id: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [video, setVideo] = useState(false);

  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;
    getCustomBg(id)
      .then((row) => {
        if (cancelled || !row) return;
        const next = URL.createObjectURL(row.blob);
        revoked = next;
        setVideo(isVideoMime(row.mime));
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

  return (
    <span className="ws-pick__swatch">
      <span className="ws-atm ws-atm--grain" />
      {url ? (
        video ? (
          <video className="ws-bg__media" src={url} muted playsInline />
        ) : (
          <img className="ws-bg__media" src={url} alt="" />
        )
      ) : null}
    </span>
  );
}

export default function WorkspaceSection() {
  const { t } = useI18n();
  const { prefs, setPrefs } = useAppearance();
  const ws = prefs.workspace;
  const fileId = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const [customs, setCustoms] = useState<CustomBgMeta[]>([]);
  const [error, setError] = useState<string | null>(null);

  function patchWorkspace(patch: Partial<typeof ws>) {
    setPrefs({ ...prefs, workspace: { ...ws, ...patch } });
  }

  async function refreshCustoms() {
    try {
      setCustoms(await listCustomBgs());
    } catch {
      setCustoms([]);
    }
  }

  useEffect(() => {
    void refreshCustoms();
  }, []);

  async function onImport(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!file) return;
    setError(null);
    try {
      const meta = await saveCustomBg(file);
      patchWorkspace({ source: 'custom', customId: meta.id });
      await refreshCustoms();
    } catch (err) {
      const code = err instanceof Error ? err.message : '';
      setError(
        code === 'size' ? t('appearance.ws.tooLarge') : t('appearance.ws.importError'),
      );
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function onDelete(id: string) {
    await deleteCustomBg(id);
    if (ws.customId === id) {
      patchWorkspace({ source: 'scene', customId: null });
    }
    await refreshCustoms();
  }

  const selectedScene = ws.source === 'scene' ? ws.scene : null;

  return (
    <div className="card" style={{ marginTop: 12 }}>
      <h3 className="mode-card__name">{t('appearance.ws.title')}</h3>
      <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>
        {t('appearance.ws.lead')}
      </p>

      <p className="font-preview__label" style={{ marginTop: 14 }}>
        {t('appearance.ws.groupSoft')}
      </p>
      <div className="ws-picks">
        {SOFT_SCENE_IDS.map((id) => (
          <button
            key={id}
            type="button"
            className={selectedScene === id ? 'ws-pick ws-pick--on' : 'ws-pick'}
            onClick={() => patchWorkspace({ source: 'scene', scene: id })}
          >
            <SceneThumb id={id} />
            <span className="ws-pick__name">{t(SCENE_NAME_KEY[id])}</span>
            <span className="ws-pick__hint">{t(SCENE_HINT_KEY[id])}</span>
          </button>
        ))}
      </div>

      <p className="font-preview__label" style={{ marginTop: 16 }}>
        {t('appearance.ws.groupHomage')}
      </p>
      <div className="ws-picks">
        {PACK_SCENE_IDS.map((id) => (
          <button
            key={id}
            type="button"
            className={selectedScene === id ? 'ws-pick ws-pick--on' : 'ws-pick'}
            onClick={() => patchWorkspace({ source: 'scene', scene: id })}
          >
            <SceneThumb id={id} />
            <span className="ws-pick__name">{t(SCENE_NAME_KEY[id])}</span>
            <span className="ws-pick__hint">{t(SCENE_HINT_KEY[id])}</span>
          </button>
        ))}
      </div>

      <p className="font-preview__label" style={{ marginTop: 16 }}>
        {t('appearance.ws.groupCustom')}
      </p>
      <div className="ws-customs">
        <button
          type="button"
          className="ws-pick ws-pick--import"
          onClick={() => fileRef.current?.click()}
        >
          <span className="ws-pick__name">{t('appearance.ws.import')}</span>
          <span className="ws-pick__hint">
            {t('appearance.ws.importHint', { mb: Math.round(MAX_BG_BYTES / (1024 * 1024)) })}
          </span>
        </button>
        {customs.map((item) => (
          <div key={item.id} className="ws-custom">
            <button
              type="button"
              className={
                ws.source === 'custom' && ws.customId === item.id
                  ? 'ws-pick ws-pick--on'
                  : 'ws-pick'
              }
              onClick={() => patchWorkspace({ source: 'custom', customId: item.id })}
            >
              <CustomThumb id={item.id} />
              <span className="ws-pick__name">{item.name}</span>
              <span className="ws-pick__hint">{item.mime || 'image'}</span>
            </button>
            <button
              type="button"
              className="ws-custom__del"
              aria-label={t('appearance.ws.delete')}
              onClick={() => void onDelete(item.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <input
        id={fileId}
        ref={fileRef}
        className="ws-pick__file"
        type="file"
        accept="image/*,video/mp4,video/webm,.gif,.webp,.avif"
        onChange={(event) => void onImport(event.target.files)}
      />
      {error ? (
        <p className="alert alert--error" style={{ marginTop: 10 }}>
          {error}
        </p>
      ) : null}

      <div style={{ marginTop: 14 }}>
        <OptionToggle
          checked={ws.motion}
          title={t('appearance.ws.motion')}
          hint={t('appearance.ws.motionHint')}
          onChange={(on) => patchWorkspace({ motion: on })}
        />
      </div>

      <label className="ws-veil">
        <span className="font-preview__label">{t('appearance.ws.veil')}</span>
        <input
          type="range"
          min={VEIL_MIN}
          max={VEIL_MAX}
          step={0.02}
          value={ws.veil}
          onChange={(event) => patchWorkspace({ veil: Number(event.target.value) })}
        />
        <span className="muted" style={{ fontSize: 12 }}>
          {t('appearance.ws.veilHint')}
        </span>
      </label>
    </div>
  );
}
