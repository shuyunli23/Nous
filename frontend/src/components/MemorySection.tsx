import { useCallback, useEffect, useState } from 'react';

import { clearUserMemory, getUserMemory } from '../api/memory';
import { ApiError } from '../api/client';
import type { MemoryField, MemoryItem, MemoryLane, UserMemory } from '../api/types';
import { useI18n } from '../i18n';

const GENERIC_TITLES = new Set(['', 'other', '其他', 'item', 'misc', '条目', 'field']);

function itemLabel(title: string | undefined, fieldName: string, fieldKey: string): string {
  const text = (title || '').trim();
  if (!text || GENERIC_TITLES.has(text.toLowerCase()) || GENERIC_TITLES.has(text)) {
    return '';
  }
  if (text === fieldName || text === fieldKey) return '';
  return text;
}

function fallbackGroups(items: MemoryItem[] | undefined): MemoryField[] {
  const buckets = new Map<string, MemoryItem[]>();
  for (const item of items ?? []) {
    const key = item.field_key || item.category || 'other';
    const list = buckets.get(key) ?? [];
    list.push(item);
    buckets.set(key, list);
  }
  return [...buckets.entries()].map(([field_key, list]) => ({
    field_key,
    name: list[0]?.title || field_key,
    description: '',
    items: list,
  }));
}

function LaneCard({
  title,
  emptyText,
  clearLabel,
  lane,
  memory,
  busy,
  onClear,
}: {
  title: string;
  emptyText: string;
  clearLabel: string;
  lane: 'persona' | 'knowledge';
  memory: MemoryLane;
  busy: 'persona' | 'knowledge' | null;
  onClear: (lane: 'persona' | 'knowledge') => void;
}) {
  const { t } = useI18n();
  const [openKeys, setOpenKeys] = useState<Set<string>>(new Set());
  const fields =
    memory.fields && memory.fields.length > 0
      ? memory.fields
      : fallbackGroups(memory.items);
  const summary = memory.summary?.trim() ?? '';

  function toggleField(key: string) {
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <article className="card memory-card">
      <h3 className="mode-card__name">{title}</h3>
      {memory.empty ? (
        <p className="memory-card__body">{emptyText}</p>
      ) : (
        <div className="memory-card__groups">
          {summary ? (
            <div className="memory-group">
              <h4 className="memory-group__title">{t('memory.summaryLabel')}</h4>
              <p className="memory-group__desc">{summary}</p>
            </div>
          ) : null}
          {fields.length > 0 ? (
            <div className="memory-group">
              <h4 className="memory-group__title">{t('memory.fieldsLabel')}</h4>
              <div className="memory-fields">
                {fields.map((field) => {
                  const key = field.field_key;
                  const open = openKeys.has(key);
                  const count = field.items.length;
                  return (
                    <div
                      key={key}
                      className={
                        open
                          ? 'memory-field memory-field--open'
                          : 'memory-field'
                      }
                    >
                      <button
                        type="button"
                        className="memory-field__toggle"
                        aria-expanded={open}
                        onClick={() => toggleField(key)}
                      >
                        <span className="memory-field__head">
                          <span className="memory-field__name">
                            {field.name || key}
                          </span>
                          <span className="memory-field__count">
                            {t('memory.itemCount', { n: count })}
                          </span>
                        </span>
                        {field.description ? (
                          <span className="memory-field__desc">
                            {field.description}
                          </span>
                        ) : null}
                      </button>
                      {open && count > 0 ? (
                        <ul className="memory-group__list">
                          {field.items.map((item) => {
                            const label = itemLabel(item.title, field.name, field.field_key);
                            return (
                              <li key={item.item_key || item.id}>
                                {label ? (
                                  <span className="memory-group__label">{label}</span>
                                ) : null}
                                {label && item.value ? '：' : ''}
                                {item.value}
                              </li>
                            );
                          })}
                        </ul>
                      ) : null}
                      {open && count === 0 ? (
                        <p className="memory-group__desc">
                          {t('memory.noItems')}
                        </p>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>
      )}
      <button
        type="button"
        className="btn btn--sm btn--danger"
        disabled={busy !== null || memory.empty}
        onClick={() => onClear(lane)}
      >
        {busy === lane ? t('common.processing') : clearLabel}
      </button>
    </article>
  );
}

export default function MemorySection() {
  const { t } = useI18n();
  const [memory, setMemory] = useState<UserMemory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<'persona' | 'knowledge' | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMemory(await getUserMemory());
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('memory.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleClear(lane: 'persona' | 'knowledge') {
    const ok = window.confirm(
      lane === 'persona'
        ? t('memory.confirmClearPersona')
        : t('memory.confirmClearKnowledge'),
    );
    if (!ok) return;
    setBusy(lane);
    setError(null);
    try {
      setMemory(await clearUserMemory(lane));
      setNotice(t('memory.cleared'));
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('memory.clearFailed'));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section id="memory" className="modes-section">
      <div className="page__header" style={{ marginBottom: 12 }}>
        <div>
          <h2 className="section__title" style={{ margin: 0 }}>
            {t('memory.title')}
          </h2>
          <p className="page__subtitle">{t('memory.subtitle')}</p>
        </div>
      </div>

      {error && <div className="alert alert--error">{error}</div>}
      {notice && <div className="alert alert--info">{notice}</div>}

      {loading || !memory ? (
        <div className="empty row" style={{ justifyContent: 'center' }}>
          <span className="spinner" aria-hidden="true" />
          <span>{t('common.loading')}</span>
        </div>
      ) : (
        <div className="memory__grid">
          <LaneCard
            title={t('memory.personaTitle')}
            emptyText={t('memory.emptyPersona')}
            clearLabel={t('memory.clearPersona')}
            lane="persona"
            memory={memory.persona}
            busy={busy}
            onClear={(next) => void handleClear(next)}
          />
          <LaneCard
            title={t('memory.knowledgeTitle')}
            emptyText={t('memory.emptyKnowledge')}
            clearLabel={t('memory.clearKnowledge')}
            lane="knowledge"
            memory={memory.knowledge}
            busy={busy}
            onClear={(next) => void handleClear(next)}
          />
        </div>
      )}
    </section>
  );
}
