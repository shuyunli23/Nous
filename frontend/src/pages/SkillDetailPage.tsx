import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import { getSkill, setSkillStatus, updateSkill } from '../api/skills';
import type { SkillCreatePayload, SkillDetail, SkillStatus } from '../api/types';
import SkillEditor from '../components/SkillEditor';
import { useI18n, type MessageKey } from '../i18n';

const STATUS_KEY: Record<SkillStatus, MessageKey> = {
  draft: 'status.draft',
  active: 'status.active',
  disabled: 'status.disabled',
  deprecated: 'status.deprecated',
};

export default function SkillDetailPage() {
  const { t, formatDateTime } = useI18n();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [skill, setSkill] = useState<SkillDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    getSkill(id)
      .then((detail) => {
        if (!cancelled) setSkill(detail);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : t('skills.loadFailed'));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function reload() {
    if (!id) return;
    const detail = await getSkill(id);
    setSkill(detail);
  }

  async function handleToggle() {
    if (!skill) return;
    const next: SkillStatus = skill.status === 'active' ? 'disabled' : 'active';
    try {
      await setSkillStatus(skill.id, next);
      setNotice(
        t('skillDetail.toggled', {
          action:
            next === 'active' ? t('common.enable') : t('common.disable'),
        }),
      );
      await reload();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.statusFailed'));
    }
  }

  async function handleSave(payload: SkillCreatePayload) {
    if (!skill) return;
    setSaving(true);
    setEditorError(null);
    try {
      await updateSkill(skill.id, payload);
      setEditorOpen(false);
      setNotice(t('skillDetail.saved'));
      await reload();
    } catch (err: unknown) {
      setEditorError(err instanceof ApiError ? err.message : t('skills.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <div className="empty row" style={{ justifyContent: 'center' }}>
          <span className="spinner" aria-hidden="true" />
          <span>{t('common.loading')}</span>
        </div>
      </div>
    );
  }

  if (!skill) {
    return (
      <div className="page">
        <div className="alert alert--error">{error ?? t('skillDetail.missing')}</div>
        <button type="button" className="btn" onClick={() => navigate('/skills')}>
          {t('skillDetail.back')}
        </button>
      </div>
    );
  }

  const successRate =
    skill.success_rate === null || skill.success_rate === undefined
      ? '—'
      : `${Math.round(skill.success_rate * 100)}%`;

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <div className="row" style={{ marginBottom: 4 }}>
            <Link to="/skills" className="faint">
              {t('skillDetail.backManage')}
            </Link>
          </div>
          <h1 className="page__title">{skill.name}</h1>
          <p className="page__subtitle">
            {skill.description || t('skillDetail.noDescription')}
          </p>
        </div>
        <div className="row">
          <span className={`badge badge--${skill.status}`}>
            {t(STATUS_KEY[skill.status])}
          </span>
          <button type="button" className="btn btn--sm" onClick={handleToggle}>
            {skill.status === 'active'
              ? t('common.disable')
              : t('common.enable')}
          </button>
          <button
            type="button"
            className="btn btn--sm btn--primary"
            onClick={() => {
              setEditorError(null);
              setEditorOpen(true);
            }}
          >
            {t('common.edit')}
          </button>
        </div>
      </div>

      {error && <div className="alert alert--error">{error}</div>}
      {notice && <div className="alert alert--info">{notice}</div>}
      {skill.status === 'draft' && (
        <div className="alert alert--warning">
          {t('skillDetail.draftWarning')}
        </div>
      )}

      <div className="detail-grid">
        <div className="stat">
          <div className="stat__label">{t('skillDetail.version')}</div>
          <div className="stat__value">v{skill.version}</div>
        </div>
        <div className="stat">
          <div className="stat__label">{t('skillDetail.usage')}</div>
          <div className="stat__value">{skill.usage_count}</div>
        </div>
        <div className="stat">
          <div className="stat__label">{t('skillDetail.successRate')}</div>
          <div className="stat__value">{successRate}</div>
        </div>
        <div className="stat">
          <div className="stat__label">{t('skillDetail.confidence')}</div>
          <div className="stat__value">
            {Math.round(skill.confidence * 100)}%
          </div>
        </div>
        <div className="stat">
          <div className="stat__label">{t('skillDetail.feedback')}</div>
          <div className="stat__value" style={{ fontSize: 15 }}>
            <span style={{ color: 'var(--success)' }}>
              +{skill.success_count}
            </span>{' '}
            /{' '}
            <span style={{ color: 'var(--danger)' }}>
              −{skill.failure_count}
            </span>
          </div>
        </div>
      </div>

      {skill.trigger_keywords.length > 0 && (
        <section className="section">
          <h2 className="section__title">{t('skillDetail.keywords')}</h2>
          <div className="keywords">
            {skill.trigger_keywords.map((keyword) => (
              <span key={keyword} className="keyword">
                {keyword}
              </span>
            ))}
          </div>
        </section>
      )}

      {skill.trigger_intent && (
        <section className="section">
          <h2 className="section__title">{t('skillDetail.intent')}</h2>
          <p style={{ margin: 0 }}>{skill.trigger_intent}</p>
        </section>
      )}

      {skill.workflow.length > 0 && (
        <section className="section">
          <h2 className="section__title">{t('skillDetail.workflow')}</h2>
          <ol className="workflow">
            {skill.workflow.map((step, index) => (
              <li key={index}>
                <div>{step.action ?? t('skillDetail.undescribed')}</div>
                {step.command && <code>{step.command}</code>}
                {step.expect && (
                  <div className="faint" style={{ fontSize: 12, marginTop: 4 }}>
                    {t('skillDetail.expect', { expect: step.expect })}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      {skill.instruction && (
        <section className="section">
          <h2 className="section__title">{t('skillDetail.instruction')}</h2>
          <div className="card" style={{ whiteSpace: 'pre-wrap' }}>
            {skill.instruction}
          </div>
        </section>
      )}

      {skill.examples.length > 0 && (
        <section className="section">
          <h2 className="section__title">
            {t('skillDetail.examples', { count: skill.examples.length })}
          </h2>
          <div className="stack">
            {skill.examples.map((example, index) => (
              <div key={index} className="card">
                {example.question && (
                  <div style={{ marginBottom: 6 }}>
                    <strong className="faint" style={{ fontSize: 12 }}>
                      {t('skillDetail.question')}
                    </strong>
                    <div>{example.question}</div>
                  </div>
                )}
                {example.solution && (
                  <div>
                    <strong className="faint" style={{ fontSize: 12 }}>
                      {t('skillDetail.solution')}
                    </strong>
                    <div style={{ whiteSpace: 'pre-wrap' }}>
                      {example.solution}
                    </div>
                  </div>
                )}
                {example.conversation_id && (
                  <div style={{ marginTop: 8 }}>
                    <Link
                      to={`/chat/${example.conversation_id}`}
                      className="mono"
                    >
                      {t('skillDetail.viewConversation')}
                    </Link>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="section">
        <h2 className="section__title">{t('skillDetail.meta')}</h2>
        <div className="card mono faint stack" style={{ gap: 4 }}>
          <div>
            {t('skillDetail.id')}: {skill.id}
          </div>
          <div>
            {t('skillDetail.source')}:{' '}
            {skill.source === 'auto'
              ? t('source.autoExtracted')
              : t('source.manualCreated')}
          </div>
          <div>
            {t('skillDetail.created')}: {formatDateTime(skill.created_at)}
          </div>
          <div>
            {t('skillDetail.updated')}: {formatDateTime(skill.updated_at)}
          </div>
          {skill.last_used_at && (
            <div>
              {t('skillDetail.lastUsed')}: {formatDateTime(skill.last_used_at)}
            </div>
          )}
          {skill.created_from_conversation_id && (
            <div>
              {t('skillDetail.fromConversation')}:{' '}
              <Link to={`/chat/${skill.created_from_conversation_id}`}>
                {skill.created_from_conversation_id.slice(0, 8)}
              </Link>
            </div>
          )}
        </div>
      </section>

      <SkillEditor
        skill={skill}
        open={editorOpen}
        saving={saving}
        error={editorError}
        onClose={() => setEditorOpen(false)}
        onSave={handleSave}
      />
    </div>
  );
}
