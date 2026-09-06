import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { deleteConversation, listConversations } from '../api/conversations';
import type {
  ConversationStatus,
  ConversationSummary,
  ExtractionStatus,
} from '../api/types';
import OverflowTitle from '../components/OverflowTitle';
import SettleDialog, { settleResultNotice } from '../components/SettleDialog';
import SettleIcon from '../components/SettleIcon';
import { useI18n, type MessageKey } from '../i18n';

const PAGE_SIZE = 15;

const SETTLE_STATUS_KEY: Record<ExtractionStatus, MessageKey> = {
  pending: 'conversations.settlePending',
  running: 'extraction.running',
  done: 'extraction.done',
  skipped: 'extraction.skipped',
  failed: 'extraction.failed',
};

function modeBadgeClass(modeKey?: string | null): string {
  if (modeKey === 'tutor') return 'badge badge--mode-tutor';
  if (modeKey === 'companion') return 'badge badge--mode-companion';
  if (modeKey && modeKey !== 'workbench') return 'badge badge--mode-custom';
  return 'badge badge--mode';
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
  const [settleId, setSettleId] = useState<string | null>(null);

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

  function openSettle(id: string) {
    setError(null);
    setNotice(null);
    setSettleId(id);
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
                        <span className={modeBadgeClass(item.mode_key)}>
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
                        <span
                          className={extractionBadgeClass(
                            item.extraction_status,
                          )}
                        >
                          {t(SETTLE_STATUS_KEY[item.extraction_status])}
                        </span>
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
                          <button
                            type="button"
                            className="btn btn--icon"
                            disabled={busyId === item.id}
                            onClick={() => openSettle(item.id)}
                            aria-label={t('conversations.settleAction')}
                            title={t('settle.title')}
                          >
                            <SettleIcon />
                          </button>
                          <button
                            type="button"
                            className="btn btn--icon btn--danger"
                            disabled={busyId === item.id}
                            onClick={() => void handleDelete(item.id)}
                            aria-label={t('common.delete')}
                            title={t('common.delete')}
                          >
                            <TrashMark />
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
      <SettleDialog
        conversationId={settleId}
        open={Boolean(settleId)}
        onClose={() => setSettleId(null)}
        onDone={(result) => {
          setNotice(settleResultNotice(result, t));
          void load();
        }}
      />
    </div>
  );
}

function TrashMark() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M9.4 5.4c0-1 .8-1.8 1.8-1.8h1.6c1 0 1.8.8 1.8 1.8"
        stroke="currentColor"
        strokeWidth="2.15"
        strokeLinecap="round"
      />
      <path
        d="M5 7.4h14"
        stroke="currentColor"
        strokeWidth="2.15"
        strokeLinecap="round"
      />
      <path
        d="M7.3 7.4v10.1c0 1.2.9 2.1 2.1 2.1h5.2c1.2 0 2.1-.9 2.1-2.1V7.4"
        stroke="currentColor"
        strokeWidth="2.15"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M10 11.3v5M12 11.3v5M14 11.3v5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
