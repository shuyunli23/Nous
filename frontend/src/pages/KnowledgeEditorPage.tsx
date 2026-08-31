import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import {
  attachmentDownloadUrl,
  createKnowledge,
  deleteAttachment,
  getKnowledge,
  updateKnowledge,
  uploadAttachment,
  type Attachment,
} from '../api/knowledge';
import MarkdownContent from '../components/MarkdownContent';
import MarkdownSourceEditor from '../components/MarkdownSourceEditor';
import { useI18n } from '../i18n';

export default function KnowledgeEditorPage() {
  const { t } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const isCreate = !id;
  const fileRef = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState('');
  const [markdown, setMarkdown] = useState('# \n\n');
  const [summary, setSummary] = useState('');
  const [category, setCategory] = useState('');
  const [favorite, setFavorite] = useState(false);
  const [important, setImportant] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(!isCreate);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setTitle('');
      setMarkdown(`# ${t('km.newNote')}\n\n`);
      setSummary('');
      setCategory('');
      setFavorite(false);
      setImportant(false);
      setAttachments([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    getKnowledge(id)
      .then((detail) => {
        setTitle(detail.title);
        setMarkdown(detail.markdown_content);
        setSummary(detail.summary || '');
        setCategory(detail.category || '');
        setFavorite(detail.is_favorite);
        setImportant(detail.is_important);
        setAttachments(detail.attachments || []);
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : t('km.loadFailed'));
      })
      .finally(() => setLoading(false));
  }, [id, t]);

  async function save() {
    if (!title.trim()) {
      setError(t('km.titleRequired'));
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      title: title.trim(),
      markdown_content: markdown,
      summary: summary.trim() || null,
      category: category.trim() || null,
      is_favorite: favorite,
      is_important: important,
    };
    try {
      if (isCreate) {
        const created = await createKnowledge(payload);
        navigate(`/knowledge/${created.id}/edit`, { replace: true });
      } else if (id) {
        await updateKnowledge(id, payload);
        navigate(`/knowledge/${id}`);
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  async function onUpload(file: File | null) {
    if (!file || !id) return;
    try {
      const item = await uploadAttachment(id, file);
      setAttachments((prev) => [item, ...prev]);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.uploadFailed'));
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function onRemoveAttachment(attachmentId: string) {
    try {
      await deleteAttachment(attachmentId);
      setAttachments((prev) => prev.filter((a) => a.id !== attachmentId));
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.actionFailed'));
    }
  }

  if (loading) {
    return (
      <div className="page">
        <p className="faint">{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">
            {isCreate ? t('km.newNote') : t('km.editNote')}
          </h1>
        </div>
        <div className="row">
          <button
            type="button"
            className="btn"
            onClick={() =>
              navigate(id ? `/knowledge/${id}` : '/knowledge')
            }
          >
            {t('common.cancel')}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={saving}
            onClick={() => void save()}
          >
            {saving ? t('common.saving') : t('common.save')}
          </button>
        </div>
      </header>

      {error && <p className="banner banner--error">{error}</p>}

      <div className="km-editor-meta">
        <label>
          {t('km.fieldTitle')}
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t('km.titlePlaceholder')}
          />
        </label>
        <label>
          {t('km.category')}
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder={t('km.categoryPlaceholder')}
          />
        </label>
        <label className="km-check">
          <input
            type="checkbox"
            checked={favorite}
            onChange={(e) => setFavorite(e.target.checked)}
          />
          {t('km.favorite')}
        </label>
        <label className="km-check">
          <input
            type="checkbox"
            checked={important}
            onChange={(e) => setImportant(e.target.checked)}
          />
          {t('km.important')}
        </label>
      </div>

      <label className="km-summary">
        {t('km.summary')}
        <input
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder={t('km.summaryPlaceholder')}
        />
      </label>

      <div className="km-split">
        <MarkdownSourceEditor
          value={markdown}
          onChange={setMarkdown}
          label={t('km.markdown')}
        />
        <div className="km-preview">
          <MarkdownContent
            content={markdown}
            className="md--article"
            allowHtml
          />
        </div>
      </div>

      {!isCreate && id && (
        <section className="km-attach">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2 className="km-section-title">{t('km.attachments')}</h2>
            <div>
              <input
                ref={fileRef}
                type="file"
                hidden
                onChange={(e) => void onUpload(e.target.files?.[0] ?? null)}
              />
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => fileRef.current?.click()}
              >
                {t('km.upload')}
              </button>
            </div>
          </div>
          {attachments.length === 0 ? (
            <p className="faint">{t('km.noAttachments')}</p>
          ) : (
            <ul className="km-attach-list">
              {attachments.map((a) => (
                <li key={a.id}>
                  <a href={attachmentDownloadUrl(a.id)}>{a.filename}</a>
                  <span className="faint mono">{formatBytes(a.size_bytes)}</span>
                  <button
                    type="button"
                    className="btn btn--sm btn--danger"
                    onClick={() => void onRemoveAttachment(a.id)}
                  >
                    {t('common.delete')}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
