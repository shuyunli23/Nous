import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { captureConversation, deleteConversation, listConversations } from '../api/conversations';
import type {
  ConversationCaptureResult,
  ConversationStatus,
  ConversationSummary,
  ExtractionStatus,
} from '../api/types';
import OverflowTitle from '../components/OverflowTitle';
import { useI18n, type MessageKey } from '../i18n';

const PAGE_SIZE = 15;

const EXTRACTION_KEY: Record<ExtractionStatus, MessageKey> = {
  pending: 'extraction.pending',
  running: 'extraction.running',
  done: 'extraction.done',
  skipped: 'extraction.skipped',
  failed: 'extraction.failed',
};

type SettleKind = 'skill' | 'knowledge' | 'persona' | 'none';

function settleKind(modeKey?: string | null): SettleKind {
  if (!modeKey || modeKey === 'workbench') return 'skill';
  if (modeKey === 'tutor') return 'knowledge';
  if (modeKey === 'companion') return 'persona';
  return 'none';
}

function extractionBadgeClass(status: ExtractionStatus): string {
  if (status === 'done') return 'badge badge--active';
  if (status === 'failed') return 'badge badge--failed';
  if (status === 'running' || status === 'pending') return 'badge badge--draft';
  return 'badge badge--disabled';
}

function conversationStatusKey(status: ConversationStatus): MessageKey {
  if (status === 'active') return 'status.conversationActive';
  if (status === 'closed') return 'status.conversationClosed';
  return 'status.conversationArchived';
}

export default function ConversationsPage() {
  const { t, formatDateTime } = useI18n();
  const navigate = useNavigate();
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<ConversationStatus | ''>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await listConversations({
        limit: PAGE_SIZE,
        offset,
        status: statusFilter || undefined,
        search: search || undefined,
      });
      setItems(page.items);
      setTotal(page.total);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.message : t('conversations.loadFailed'),
      );
    } finally {
      setLoading(false);
    }
  }, [offset, search, statusFilter, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function noticeForCapture(result: ConversationCaptureResult): string {
    if (result.kind === 'skill') {
      if (result.skill_id) return t('conversations.extractedNew');
      if (result.merged_into) {
        return t('conversations.extractedMerged', {
          reason: result.reason ?? '',
        });
      }
      return t('conversations.extractedNone', {
        reason: result.reason ?? t('conversations.noReuse'),
      });
    }
    if (result.kind === 'knowledge') {
      if (result.notes_skipped && result.reason === 'already_extracted') {
        return result.memory_updated
          ? t('conversations.knowledgeAlreadyRemembered', {
              n: result.notes.length,
            })
          : t('conversations.knowledgeAlready', { n: result.notes.length });
      }
      if (result.notes_skipped && !result.memory_updated) {
        return t('conversations.knowledgeNone', {
          reason: result.reason ?? t('conversations.noReuse'),
        });
      }
      return result.memory_updated
        ? t('conversations.knowledgeSavedRemembered', {
            n: result.notes.length,
          })
        : t('conversations.knowledgeSaved', { n: result.notes.length });
    }
    return result.memory_updated
      ? t('conversations.personaSaved')
      : t('conversations.personaNone');
  }

  async function handleDelete(id: string) {
    if (!window.confirm(t('conversations.confirmDelete'))) return;
    setBusyId(id);
    setError(null);
    try {
      await deleteConversation(id);
      setNotice(t('conversations.deleted'));
      await load();
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.message : t('conversations.deleteFailed'),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function handleCapture(id: string) {
    setBusyId(id);
    setError(null);
    setNotice(null);
    try {
      setNotice(noticeForCapture(await captureConversation(id)));
      await load();
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.code === 'llm_error'
            ? `${err.message}${t('conversations.extractNeedKey')}`
            : err.message
          : t('conversations.extractFailed'),
      );
    } finally {
      setBusyId(null);
    }
  }

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = offset + items.length;

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1 className="page__title">{t('conversations.title')}</h1>
          <p className="page__subtitle">
            {t('conversations.subtitle', { total })}
          </p>
        </div>
      </div>

      {error && <div className="alert alert--error">{error}</div>}
      {notice && <div className="alert alert--info">{notice}</div>}

      <div className="filters">
        <input
          type="search"
          value={search}
          placeholder={t('conversations.searchPlaceholder')}
          aria-label={t('conversations.searchAria')}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
        <select
          value={statusFilter}
          aria-label={t('conversations.filterAria')}
          onChange={(e) => {
            setStatusFilter(e.target.value as ConversationStatus | '');
            setOffset(0);
          }}
        >
          <option value="">{t('conversations.allStatuses')}</option>
          <option value="active">{t('status.conversationActive')}</option>
          <option value="closed">{t('status.conversationClosed')}</option>
          <option value="archived">{t('status.conversationArchived')}</option>
        </select>
      </div>

      {loading ? (
        <div className="empty row" style={{ justifyContent: 'center' }}>
          <span className="spinner" aria-hidden="true" />
          <span>{t('common.loading')}</span>
        </div>
      ) : items.length === 0 ? (
        <div className="empty">{t('conversations.empty')}</div>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('conversations.colTitle')}</th>
                  <th>{t('conversations.colMode')}</th>
                  <th>{t('conversations.colStatus')}</th>
                  <th>{t('conversations.colExtraction')}</th>
                  <th>{t('conversations.colMessages')}</th>
                  <th>{t('conversations.colTokens')}</th>
                  <th>{t('conversations.colUpdated')}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const kind = settleKind(item.mode_key);
                  return (
                    <tr key={item.id}>
                      <td>
                        <button
                          type="button"
                          className="conv-title-btn"
                          onClick={() => navigate(`/chat/${item.id}`)}
                        >
                          <OverflowTitle
                            className="conv-title"
                            text={item.title}
                          />
                        </button>
                      </td>
                      <td>
                        <span className="badge badge--closed">
                          {item.mode_name || t('nav.workbench')}
                        </span>
                      </td>
                      <td>
                        <span
                          className={
                            item.status === 'active'
                              ? 'badge badge--active'
                              : item.status === 'closed'
                                ? 'badge badge--closed'
                                : 'badge badge--disabled'
                          }
                        >
                          {t(conversationStatusKey(item.status))}
                        </span>
                      </td>
                      <td>
                        {kind === 'skill' ? (
                          <span
                            className={extractionBadgeClass(
                              item.extraction_status,
                            )}
                          >
                            {t(EXTRACTION_KEY[item.extraction_status])}
                          </span>
                        ) : (
                          <span className="badge badge--closed">
                            {kind === 'knowledge'
                              ? t('conversations.settleKnowledge')
                              : kind === 'persona'
                                ? t('conversations.settlePersona')
                                : t('conversations.settleNone')}
                          </span>
                        )}
                      </td>
                      <td className="mono">{item.message_count}</td>
                      <td className="mono faint">
                        {item.token_total
                          ? item.token_total.toLocaleString()
                          : '—'}
                      </td>
                      <td className="faint mono">
                        {formatDateTime(item.updated_time)}
                      </td>
                      <td>
                        <div className="table__actions">
                          {kind !== 'none' && (
                            <button
                              type="button"
                              className="btn btn--sm"
                              disabled={busyId === item.id}
                              onClick={() => void handleCapture(item.id)}
                              title={
                                kind === 'skill'
                                  ? t('conversations.extractTitle')
                                  : kind === 'knowledge'
                                    ? t('conversations.knowledgeTitle')
                                    : t('conversations.personaTitle')
                              }
                            >
                              {busyId === item.id
                                ? t('common.processing')
                                : kind === 'skill'
                                  ? t('conversations.extractAction')
                                  : kind === 'knowledge'
                                    ? t('conversations.knowledgeAction')
                                    : t('conversations.personaAction')}
                            </button>
                          )}
                          <button
                            type="button"
                            className="btn btn--sm btn--danger"
                            disabled={busyId === item.id}
                            onClick={() => void handleDelete(item.id)}
                          >
                            {t('common.delete')}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <span>
              {pageStart}–{pageEnd} / {total}
            </span>
            <div className="row">
              <button
                type="button"
                className="btn btn--sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                {t('common.previous')}
              </button>
              <button
                type="button"
                className="btn btn--sm"
                disabled={pageEnd >= total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
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
