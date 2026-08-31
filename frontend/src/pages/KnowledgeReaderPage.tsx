import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import {
  analyzeKnowledge,
  attachmentDownloadUrl,
  confirmKnowledgeImport,
  deleteKnowledge,
  getKnowledge,
  toggleArchive,
  toggleFavorite,
  toggleImportant,
  type KnowledgeDetail,
} from '../api/knowledge';
import MarkdownContent from '../components/MarkdownContent';
import KnowledgeToc from '../components/KnowledgeToc';
import { extractMarkdownToc } from '../lib/markdownToc';
import { useI18n } from '../i18n';

export default function KnowledgeReaderPage() {
  const { t, formatDateTime } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const [item, setItem] = useState<KnowledgeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [articleEl, setArticleEl] = useState<HTMLElement | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setItem(await getKnowledge(id));
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [id, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const bindArticle = useCallback((node: HTMLElement | null) => {
    setArticleEl(node);
  }, []);

  const toc = useMemo(
    () => (item ? extractMarkdownToc(item.markdown_content) : []),
    [item],
  );

  async function onConfirmImport() {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await confirmKnowledgeImport(id);
      setItem(updated);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.importFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function onAnalyze() {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await analyzeKnowledge(id);
      await load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.analyzeFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function onFlag(kind: 'favorite' | 'important' | 'archive') {
    if (!id) return;
    setBusy(true);
    try {
      const updated =
        kind === 'favorite'
          ? await toggleFavorite(id)
          : kind === 'important'
            ? await toggleImportant(id)
            : await toggleArchive(id);
      setItem(updated);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.actionFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!item || !id) return;
    if (!window.confirm(t('km.confirmDelete', { title: item.title }))) return;
    try {
      await deleteKnowledge(id);
      navigate('/knowledge');
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.deleteFailed'));
    }
  }

  if (loading) {
    return (
      <div className="page">
        <p className="faint">{t('common.loading')}</p>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="page">
        <p className="banner banner--error">{error || t('km.missing')}</p>
        <button type="button" className="btn" onClick={() => navigate('/knowledge')}>
          {t('km.backList')}
        </button>
      </div>
    );
  }

  const isDraft = item.source_type === 'chat_draft';

  return (
    <div className="page">
      {isDraft && (
        <div className="alert alert--info">
          {t('km.pendingBanner')}
        </div>
      )}
      <header className="page__header">
        <div>
          <button
            type="button"
            className="btn btn--sm"
            onClick={() => navigate('/knowledge')}
          >
            {t('km.backList')}
          </button>
          <h1 className="page__title" style={{ marginTop: 12 }}>
            {item.title}
          </h1>
          <p className="page__subtitle">
            {item.category || t('common.emDash')} ·{' '}
            {t('km.reading', {
              words: item.word_count,
              minutes: item.reading_minutes,
            })}{' '}
            · {formatDateTime(item.updated_time)}
          </p>
        </div>
        <div className="row">
          {isDraft && (
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy}
              onClick={() => void onConfirmImport()}
            >
              {busy ? t('common.processing') : t('km.confirmImport')}
            </button>
          )}
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void onAnalyze()}
          >
            {busy ? t('common.processing') : t('km.analyze')}
          </button>
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void onFlag('favorite')}
          >
            {item.is_favorite ? t('km.unfavorite') : t('km.favorite')}
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => navigate(`/knowledge/${item.id}/edit`)}
          >
            {t('common.edit')}
          </button>
          <button
            type="button"
            className="btn btn--danger"
            onClick={() => void onDelete()}
          >
            {t('common.delete')}
          </button>
        </div>
      </header>

      {error && <p className="banner banner--error">{error}</p>}

      <div className="km-reader">
        <article className="km-reader__body" ref={bindArticle}>
          {item.summary && <p className="km-lead">{item.summary}</p>}
          {item.keywords.length > 0 && (
            <div className="km-tags">
              {item.keywords.map((k) => (
                <span key={k.id} className="km-tag">
                  {k.name}
                </span>
              ))}
            </div>
          )}
          <p className="faint">
            {t('km.analysis')}: {item.analysis_status}
            {item.analyzed_by_model ? ` · ${item.analyzed_by_model}` : ''}
            {item.analysis_error ? ` · ${item.analysis_error}` : ''}
          </p>
          <MarkdownContent
            content={item.markdown_content}
            className="md--article"
            allowHtml
          />
          {item.attachments.length > 0 && (
            <section>
              <h2 className="km-section-title">{t('km.attachments')}</h2>
              <ul className="km-attach-list">
                {item.attachments.map((a) => (
                  <li key={a.id}>
                    <a href={attachmentDownloadUrl(a.id)}>{a.filename}</a>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </article>
        {toc.length > 0 && (
          <KnowledgeToc entries={toc} article={articleEl} />
        )}
      </div>
    </div>
  );
}
