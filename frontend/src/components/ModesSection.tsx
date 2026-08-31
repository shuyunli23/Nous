import { useCallback, useEffect, useState } from 'react';

import {
  createChatMode,
  deleteChatMode,
  listChatModes,
  updateChatMode,
} from '../api/chatModes';
import { ApiError } from '../api/client';
import type { ChatMode, ChatModeCreatePayload } from '../api/types';
import { useI18n, type MessageKey } from '../i18n';
import OptionToggle from './OptionToggle';

const EMPTY_FORM = {
  name: '',
  description: '',
  system_prompt: '',
  use_long_term_memory: false,
  use_knowledge_memory: false,
};

function toolPolicyKey(policy: string): MessageKey {
  if (policy === 'full') return 'modes.toolsFull';
  if (policy === 'light') return 'modes.toolsLight';
  return 'modes.toolsNone';
}

export default function ModesSection() {
  const { t } = useI18n();
  const [modes, setModes] = useState<ChatMode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<ChatMode | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setModes(await listChatModes());
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('modes.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setEditorError(null);
    setEditorOpen(true);
  }

  function openEdit(mode: ChatMode) {
    if (mode.is_builtin) return;
    setEditing(mode);
    setForm({
      name: mode.name,
      description: mode.description,
      system_prompt: mode.system_prompt,
      use_long_term_memory: mode.use_long_term_memory,
      use_knowledge_memory: mode.use_knowledge_memory,
    });
    setEditorError(null);
    setEditorOpen(true);
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    const payload: ChatModeCreatePayload = {
      name: form.name.trim(),
      description: form.description.trim(),
      system_prompt: form.system_prompt.trim(),
      use_long_term_memory: form.use_long_term_memory,
      use_knowledge_memory: form.use_knowledge_memory,
    };
    if (!payload.name || !payload.system_prompt) return;
    setSaving(true);
    setEditorError(null);
    try {
      if (editing) {
        await updateChatMode(editing.id, payload);
        setNotice(t('modes.saved', { name: payload.name }));
      } else {
        await createChatMode(payload);
        setNotice(t('modes.created', { name: payload.name }));
      }
      setEditorOpen(false);
      await load();
    } catch (err: unknown) {
      setEditorError(
        err instanceof ApiError ? err.message : t('modes.saveFailed'),
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(mode: ChatMode) {
    if (mode.is_builtin) return;
    if (!window.confirm(t('modes.confirmDelete', { name: mode.name }))) return;
    setBusyId(mode.id);
    setError(null);
    try {
      await deleteChatMode(mode.id);
      setNotice(t('modes.deleted', { name: mode.name }));
      await load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('modes.deleteFailed'));
    } finally {
      setBusyId(null);
    }
  }

  async function handleTutorKnowledge(mode: ChatMode, on: boolean) {
    setBusyId(mode.id);
    setError(null);
    try {
      const updated = await updateChatMode(mode.id, {
        use_knowledge_memory: on,
      });
      setModes((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(on ? t('modes.kmEnabled') : t('modes.kmDisabled'));
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('modes.saveFailed'));
    } finally {
      setBusyId(null);
    }
  }

  const builtins = modes.filter((mode) => mode.is_builtin);
  const customs = modes.filter((mode) => !mode.is_builtin);

  return (
    <section id="modes" className="modes-section">
      <div className="page__header" style={{ marginBottom: 12 }}>
        <div>
          <h2 className="section__title" style={{ margin: 0 }}>
            {t('modes.title')}
          </h2>
          <p className="page__subtitle">{t('modes.subtitle')}</p>
        </div>
        <button type="button" className="btn btn--sm btn--primary" onClick={openCreate}>
          {t('modes.create')}
        </button>
      </div>

      {error && <div className="alert alert--error">{error}</div>}
      {notice && <div className="alert alert--info">{notice}</div>}

      {loading ? (
        <div className="empty row" style={{ justifyContent: 'center' }}>
          <span className="spinner" aria-hidden="true" />
          <span>{t('common.loading')}</span>
        </div>
      ) : (
        <>
          <h3 className="modes__section">{t('modes.builtin')}</h3>
          <div className="modes__grid">
            {builtins.map((mode) => (
              <article key={mode.id} className="card mode-card">
                <div className="mode-card__top">
                  <h3 className="mode-card__name">{mode.name}</h3>
                  <span className="badge badge--closed">
                    {t(toolPolicyKey(mode.tool_policy))}
                  </span>
                </div>
                <p className="mode-card__desc">{mode.description}</p>
                {mode.key === 'companion' && (
                  <p className="mode-card__chip">{t('modes.ltmOn')}</p>
                )}
                {(mode.key === 'tutor' || mode.key === 'companion') && (
                  <OptionToggle
                    checked={Boolean(mode.use_knowledge_memory)}
                    disabled={busyId === mode.id}
                    title={t('modes.kmLabel')}
                    hint={t('modes.kmHint')}
                    onChange={(on) => void handleTutorKnowledge(mode, on)}
                  />
                )}
              </article>
            ))}
          </div>

          <h3 className="modes__section">{t('modes.custom')}</h3>
          {customs.length === 0 ? (
            <div className="empty">{t('modes.empty')}</div>
          ) : (
            <div className="modes__grid">
              {customs.map((mode) => (
                <article key={mode.id} className="card mode-card">
                  <div className="mode-card__top">
                    <h3 className="mode-card__name">{mode.name}</h3>
                    <span className="badge badge--draft">
                      {t(toolPolicyKey(mode.tool_policy))}
                    </span>
                  </div>
                  <p className="mode-card__desc">
                    {mode.description || t('common.emDash')}
                  </p>
                  {(mode.use_long_term_memory || mode.use_knowledge_memory) && (
                    <p className="field__hint">
                      {[
                        mode.use_long_term_memory ? t('modes.ltmOn') : null,
                        mode.use_knowledge_memory ? t('modes.kmOn') : null,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                  )}
                  <div className="row" style={{ marginTop: 12 }}>
                    <button
                      type="button"
                      className="btn btn--sm"
                      onClick={() => openEdit(mode)}
                    >
                      {t('common.edit')}
                    </button>
                    <button
                      type="button"
                      className="btn btn--sm btn--danger"
                      disabled={busyId === mode.id}
                      onClick={() => void handleDelete(mode)}
                    >
                      {t('common.delete')}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}

      {editorOpen && (
        <div
          className="modal__backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="mode-editor-title"
          onClick={(event) => {
            if (event.target === event.currentTarget) setEditorOpen(false);
          }}
        >
          <form className="modal" onSubmit={(event) => void handleSave(event)}>
            <div className="modal__header">
              <h2 className="modal__title" id="mode-editor-title">
                {editing ? t('modes.editTitle') : t('modes.createTitle')}
              </h2>
              <button
                type="button"
                className="close-btn"
                onClick={() => setEditorOpen(false)}
                aria-label={t('common.close')}
              >
                ×
              </button>
            </div>
            <div className="modal__body stack">
              {editorError && <div className="alert alert--error">{editorError}</div>}
              <div className="field">
                <label htmlFor="mode-name">{t('modes.name')}</label>
                <input
                  id="mode-name"
                  value={form.name}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, name: event.target.value }))
                  }
                  required
                  maxLength={80}
                />
              </div>
              <div className="field">
                <label htmlFor="mode-desc">{t('modes.description')}</label>
                <input
                  id="mode-desc"
                  value={form.description}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, description: event.target.value }))
                  }
                  maxLength={400}
                />
              </div>
              <div className="field">
                <label htmlFor="mode-prompt">{t('modes.prompt')}</label>
                <textarea
                  id="mode-prompt"
                  value={form.system_prompt}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      system_prompt: event.target.value,
                    }))
                  }
                  rows={10}
                  required
                  maxLength={16000}
                  placeholder={t('modes.promptPlaceholder')}
                />
                <p className="field__hint">{t('modes.promptHint')}</p>
              </div>
              <OptionToggle
                checked={form.use_long_term_memory}
                title={t('modes.ltmLabel')}
                hint={t('modes.ltmHint')}
                onChange={(on) =>
                  setForm((prev) => ({ ...prev, use_long_term_memory: on }))
                }
              />
              <OptionToggle
                checked={form.use_knowledge_memory}
                title={t('modes.kmLabel')}
                hint={t('modes.kmHint')}
                onChange={(on) =>
                  setForm((prev) => ({ ...prev, use_knowledge_memory: on }))
                }
              />
            </div>
            <div className="modal__footer">
              <button
                type="button"
                className="btn"
                onClick={() => setEditorOpen(false)}
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                className="btn btn--primary"
                disabled={
                  saving || !form.name.trim() || !form.system_prompt.trim()
                }
              >
                {saving
                  ? t('common.saving')
                  : editing
                    ? t('common.save')
                    : t('common.create')}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
