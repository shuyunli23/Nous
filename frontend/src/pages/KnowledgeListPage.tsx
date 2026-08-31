import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import {
  deleteKnowledge,
  fetchKnowledgeStats,
  importMarkdown,
  listCategories,
  listKnowledge,
  toggleFavorite,
  toggleImportant,
  type CategoryStat,
  type DashboardStats,
  type KnowledgeSummary,
} from '../api/knowledge';
import { useI18n } from '../i18n';

const PAGE_SIZE = 12;

function FilterIcon({ name }: { name: 'star' | 'mark' | 'inbox' }) {
  if (name === 'star') {
    return (
      <svg className="km-filter__icon" viewBox="0 0 16 16" aria-hidden="true">
        <path
          fill="currentColor"
          d="M8 1.6 9.7 5.3l4 .3-3.1 2.6 1 3.8L8 9.8l-3.6 2.2 1-3.8L2.3 5.6l4-.3z"
        />
      </svg>
    );
  }
  if (name === 'mark') {
    return (
      <svg className="km-filter__icon" viewBox="0 0 16 16" aria-hidden="true">
        <path
          fill="currentColor"
          d="M8 1.7 14.4 8 8 14.3 1.6 8 8 1.7zm0 3.1L4.7 8 8 11.2 11.3 8 8 4.8z"
        />
      </svg>
    );
  }
  return (
    <svg className="km-filter__icon" viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M2.2 4.2 8 7.4l5.8-3.2H2.2zm0 .9V12c0 .6.5 1 1 1h9.6c.5 0 1-.4 1-1V5.1L8 8.4 2.2 5.1z"
      />
    </svg>
  );
}

function FilterChip({
  pressed,
  label,
  icon,
  onToggle,
}: {
  pressed: boolean;
  label: string;
  icon: 'star' | 'mark' | 'inbox';
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      className={pressed ? 'km-filter km-filter--on' : 'km-filter'}
      aria-pressed={pressed}
      onClick={onToggle}
    >
      <FilterIcon name={icon} />
      {label}
    </button>
  );
}

export default function KnowledgeListPage() {
  const { t, formatDate } = useI18n();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const pending = searchParams.get('pending') === '1';
  const importRef = useRef<HTMLInputElement>(null);

  const [items, setItems] = useState<KnowledgeSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [category, setCategory] = useState('');
  const [onlyFavorite, setOnlyFavorite] = useState(false);
  const [onlyImportant, setOnlyImportant] = useState(false);
  const [categories, setCategories] = useState<CategoryStat[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, cats, dash] = await Promise.all([
        listKnowledge({
          page,
          page_size: PAGE_SIZE,
          q: q.trim() || undefined,
          category: category || undefined,
          is_favorite: onlyFavorite || undefined,
          is_important: onlyImportant || undefined,
          pending_import: pending || undefined,
        }),
        listCategories(),
        fetchKnowledgeStats(),
      ]);
      setItems(list.items);
      setTotal(list.total);
      setCategories(cats);
      setStats(dash);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [page, q, category, onlyFavorite, onlyImportant, pending, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onToggle(
    id: string,
    kind: 'favorite' | 'important',
  ) {
    setBusyId(id);
    try {
      const updated =
        kind === 'favorite' ? await toggleFavorite(id) : await toggleImportant(id);
      setItems((prev) =>
        prev.map((item) =>
          item.id === id
            ? {
                ...item,
                is_favorite: updated.is_favorite,
                is_important: updated.is_important,
              }
            : item,
        ),
      );
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.actionFailed'));
    } finally {
      setBusyId(null);
    }
  }

  async function onDelete(item: KnowledgeSummary) {
    if (!window.confirm(t('km.confirmDelete', { title: item.title }))) return;
    setBusyId(item.id);
    try {
      await deleteKnowledge(item.id);
      setNotice(t('km.deleted'));
      if (items.length === 1 && page > 1) setPage(page - 1);
      else void load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.deleteFailed'));
    } finally {
      setBusyId(null);
    }
  }

  async function onImport(file: File | null) {
    if (!file) return;
    const form = new FormData();
    form.append('markdown_file', file);
    setBusyId('import');
    setError(null);
    try {
      const result = await importMarkdown(form);
      const extra = result.warnings.length
        ? ` (${result.warnings.slice(0, 2).join('; ')})`
        : '';
      setNotice(t('km.imported', { title: result.knowledge.title }) + extra);
      navigate(`/knowledge/${result.knowledge.id}`);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.importFailed'));
    } finally {
      setBusyId(null);
      if (importRef.current) importRef.current.value = '';
    }
  }

  const pageStart = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const pageEnd = Math.min(page * PAGE_SIZE, total);

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">
            {pending ? t('km.pendingTitle') : t('km.title')}
          </h1>
          <p className="page__subtitle">
            {pending
              ? t('km.pendingSubtitle', { total })
              : t('km.subtitle', { total })}
          </p>
        </div>
        <div className="row">
          <input
            ref={importRef}
            type="file"
            accept=".md,text/markdown"
            hidden
            onChange={(e) => void onImport(e.target.files?.[0] ?? null)}
          />
          <button
            type="button"
            className="btn"
            disabled={busyId === 'import'}
            onClick={() => importRef.current?.click()}
          >
            {t('km.importMd')}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => navigate('/knowledge/new')}
          >
            {t('km.newNote')}
          </button>
        </div>
      </header>

      {stats && (
        <div className="km-stats">
          <span>{t('km.statNotes', { n: stats.knowledge_total })}</span>
          <span>{t('km.statKeywords', { n: stats.keyword_total })}</span>
          <span>{t('km.statFavorites', { n: stats.favorite_total })}</span>
          <span>{t('km.statFiles', { n: stats.attachment_total })}</span>
          {(stats.pending_total ?? 0) > 0 && (
            <button
              type="button"
              className="btn btn--sm"
              onClick={() => setSearchParams({ pending: '1' })}
            >
              {t('km.statPending', { n: stats.pending_total ?? 0 })}
            </button>
          )}
        </div>
      )}

      <div className="toolbar">
        <input
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          placeholder={t('km.searchPlaceholder')}
          aria-label={t('km.searchPlaceholder')}
        />
        <select
          value={category}
          onChange={(e) => {
            setPage(1);
            setCategory(e.target.value);
          }}
          aria-label={t('km.category')}
        >
          <option value="">{t('km.allCategories')}</option>
          {categories.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} ({c.count})
            </option>
          ))}
        </select>
        <div className="km-filters" role="group" aria-label={t('km.filterAria')}>
          <FilterChip
            icon="star"
            label={t('km.favorite')}
            pressed={onlyFavorite}
            onToggle={() => {
              setPage(1);
              setOnlyFavorite((on) => !on);
            }}
          />
          <FilterChip
            icon="mark"
            label={t('km.important')}
            pressed={onlyImportant}
            onToggle={() => {
              setPage(1);
              setOnlyImportant((on) => !on);
            }}
          />
          <FilterChip
            icon="inbox"
            label={t('km.pendingInbox')}
            pressed={pending}
            onToggle={() => {
              setPage(1);
              if (pending) setSearchParams({});
              else setSearchParams({ pending: '1' });
            }}
          />
        </div>
      </div>

      {error && <p className="banner banner--error">{error}</p>}
      {notice && <p className="banner banner--ok">{notice}</p>}

      {loading ? (
        <p className="faint">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <p className="empty">{pending ? t('km.pendingEmpty') : t('km.empty')}</p>
      ) : (
        <>
          <div className="km-grid">
            {items.map((item) => (
              <article
                key={item.id}
                className="km-card"
                onClick={() => navigate(`/knowledge/${item.id}`)}
              >
                <div className="km-card__top">
                  <h2 className="km-card__title">{item.title}</h2>
                  <div className="km-card__flags">
                    {item.is_favorite && <span title={t('km.favorite')}>★</span>}
                    {item.is_important && <span title={t('km.important')}>!</span>}
                  </div>
                </div>
                <p className="km-card__summary">
                  {item.summary || t('km.noSummary')}
                </p>
                <div className="km-card__meta">
                  {item.category && (
                    <span className="badge badge--draft">{item.category}</span>
                  )}
                  {item.source_type === 'chat_draft' && (
                    <span className="badge badge--closed">{t('km.pendingBadge')}</span>
                  )}
                  <span className="faint">
                    {t('km.reading', {
                      words: item.word_count,
                      minutes: item.reading_minutes,
                    })}
                  </span>
                  <span className="faint mono">{formatDate(item.updated_time)}</span>
                </div>
                {item.keywords.length > 0 && (
                  <div className="km-tags">
                    {item.keywords.slice(0, 6).map((k) => (
                      <span key={k.id} className="km-tag">
                        {k.name}
                      </span>
                    ))}
                  </div>
                )}
                <div
                  className="table__actions"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    type="button"
                    className="btn btn--sm"
                    disabled={busyId === item.id}
                    onClick={() => void onToggle(item.id, 'favorite')}
                  >
                    {item.is_favorite ? t('km.unfavorite') : t('km.favorite')}
                  </button>
                  <button
                    type="button"
                    className="btn btn--sm"
                    disabled={busyId === item.id}
                    onClick={() => void onToggle(item.id, 'important')}
                  >
                    {item.is_important ? t('km.unimportant') : t('km.important')}
                  </button>
                  <button
                    type="button"
                    className="btn btn--sm"
                    onClick={() => navigate(`/knowledge/${item.id}/edit`)}
                  >
                    {t('common.edit')}
                  </button>
                  <button
                    type="button"
                    className="btn btn--sm btn--danger"
                    disabled={busyId === item.id}
                    onClick={() => void onDelete(item)}
                  >
                    {t('common.delete')}
                  </button>
                </div>
              </article>
            ))}
          </div>
          <div className="pagination">
            <span>
              {pageStart}–{pageEnd} / {total}
            </span>
            <div className="row">
              <button
                type="button"
                className="btn btn--sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                {t('common.previous')}
              </button>
              <button
                type="button"
                className="btn btn--sm"
                disabled={pageEnd >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                {t('common.next')}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
