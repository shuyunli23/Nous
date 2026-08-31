import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import {
  fetchHotKeywords,
  rebuildEmbeddings,
  searchKnowledge,
  type KeywordStat,
  type SearchHit,
  type SearchMode,
} from '../api/knowledge';
import { useI18n, type MessageKey } from '../i18n';

const MODE_KEYS: Record<SearchMode, MessageKey> = {
  hybrid: 'km.modeHybrid',
  keyword: 'km.modeKeyword',
  fulltext: 'km.modeFulltext',
  vector: 'km.modeVector',
};

export default function KnowledgeSearchPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [mode, setMode] = useState<SearchMode>('hybrid');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<SearchHit[]>([]);
  const [total, setTotal] = useState(0);
  const [note, setNote] = useState<string | null>(null);
  const [hot, setHot] = useState<KeywordStat[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);

  useEffect(() => {
    fetchHotKeywords()
      .then(setHot)
      .catch(() => setHot([]));
  }, []);

  const runSearch = useCallback(
    async (query: string, nextPage = 1) => {
      const trimmed = query.trim();
      if (!trimmed) return;
      setLoading(true);
      setError(null);
      setSearched(true);
      try {
        const res = await searchKnowledge({
          q: trimmed,
          mode,
          page: nextPage,
          page_size: 10,
        });
        setItems(res.items);
        setTotal(res.total);
        setNote(res.note);
        setPage(nextPage);
      } catch (err: unknown) {
        setError(err instanceof ApiError ? err.message : t('km.searchFailed'));
      } finally {
        setLoading(false);
      }
    },
    [mode, t],
  );

  async function onRebuild() {
    setRebuilding(true);
    setError(null);
    try {
      const res = await rebuildEmbeddings();
      setNote(res.message);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.rebuildFailed'));
    } finally {
      setRebuilding(false);
    }
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">{t('km.searchTitle')}</h1>
          <p className="page__subtitle">{t('km.searchLead')}</p>
        </div>
        <button
          type="button"
          className="btn"
          disabled={rebuilding}
          onClick={() => void onRebuild()}
        >
          {rebuilding ? t('common.processing') : t('km.rebuildVectors')}
        </button>
      </header>

      <form
        className="toolbar"
        onSubmit={(e) => {
          e.preventDefault();
          void runSearch(q, 1);
        }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t('km.searchPlaceholder')}
          aria-label={t('km.searchPlaceholder')}
        />
        <select
          className="toolbar__mode"
          value={mode}
          onChange={(e) => setMode(e.target.value as SearchMode)}
          aria-label={t(MODE_KEYS[mode])}
        >
          {(Object.keys(MODE_KEYS) as SearchMode[]).map((m) => (
            <option key={m} value={m}>
              {t(MODE_KEYS[m])}
            </option>
          ))}
        </select>
        <button type="submit" className="btn btn--primary" disabled={loading}>
          {t('km.searchAction')}
        </button>
      </form>

      {hot.length > 0 && (
        <div className="km-tags" style={{ marginBottom: 16 }}>
          {hot.slice(0, 16).map((k) => (
            <button
              key={k.id}
              type="button"
              className="km-tag km-tag--btn"
              onClick={() => {
                setQ(k.name);
                void runSearch(k.name, 1);
              }}
            >
              {k.name}
            </button>
          ))}
        </div>
      )}

      {error && <p className="banner banner--error">{error}</p>}
      {note && <p className="banner banner--ok">{note}</p>}

      {loading ? (
        <p className="faint">{t('common.loading')}</p>
      ) : searched && items.length === 0 ? (
        <p className="empty">{t('km.searchEmpty')}</p>
      ) : (
        <div className="km-grid">
          {items.map((item) => (
            <article
              key={item.id}
              className="km-card"
              onClick={() => navigate(`/knowledge/${item.id}`)}
            >
              <h2 className="km-card__title">{item.title}</h2>
              <p className="km-card__summary">
                {item.snippet || item.summary || t('km.noSummary')}
              </p>
              <div className="km-card__meta">
                <span className="badge badge--active">
                  {t('km.score', { n: item.score.toFixed(2) })}
                </span>
                {item.match_fields.map((f) => (
                  <span key={f} className="km-tag">
                    {f}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}

      {total > 10 && (
        <div className="pagination">
          <span>
            {(page - 1) * 10 + 1}–{Math.min(page * 10, total)} / {total}
          </span>
          <div className="row">
            <button
              type="button"
              className="btn btn--sm"
              disabled={page <= 1}
              onClick={() => void runSearch(q, page - 1)}
            >
              {t('common.previous')}
            </button>
            <button
              type="button"
              className="btn btn--sm"
              disabled={page * 10 >= total}
              onClick={() => void runSearch(q, page + 1)}
            >
              {t('common.next')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
