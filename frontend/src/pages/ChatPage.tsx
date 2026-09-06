import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';

import { applyLiveTrace, sendMessageStream } from '../api/chat';
import { listChatModes, updateChatMode } from '../api/chatModes';
import { ApiError } from '../api/client';
import {
  closeConversation,
  getConversation,
  listConversations,
} from '../api/conversations';
import { getLLMConfig } from '../api/llmConfig';
import type {
  ChatMode,
  ConversationDetail,
  ExecutionStep,
  Message,
  ProviderView,
  SkillUsedInfo,
} from '../api/types';
import { isChatProviderKind } from '../api/types';
import MessageInput from '../components/MessageInput';
import MessageList, { type ChatHeroCopy } from '../components/MessageList';
import NewChatDialog from '../components/NewChatDialog';
import OverflowTitle from '../components/OverflowTitle';
import SettleDialog, { settleResultNotice } from '../components/SettleDialog';
import SettleIcon from '../components/SettleIcon';
import { useI18n, type MessageKey } from '../i18n';

const MODE_STORAGE = 'nous.selectedModeId';
const PROVIDER_STORAGE = 'nous.chatProviderId';

type NewChatNav = {
  confirmedNew?: boolean;
  modeId?: string | null;
};

function optimisticContent(text: string, files?: File[]) {
  if (!files?.length) return text;
  const names = files.map((file) => file.name).join('、');
  return text ? `${text}\n\n📎 ${names}` : `📎 ${names}`;
}

function freezeLiveSteps(steps: ExecutionStep[]): ExecutionStep[] {
  return steps.map((step) =>
    step.status === 'running' ? { ...step, status: 'error' } : step,
  );
}

function failedAssistantMessage(
  text: string,
  steps: ExecutionStep[],
): Message {
  return {
    id: `temp-err-${Date.now()}`,
    seq: 0,
    role: 'assistant',
    content: text,
    execution_trace: steps.length ? steps : null,
    created_at: new Date().toISOString(),
  };
}

function conversationIdFromUnknown(err: unknown): string | null {
  if (!(err instanceof ApiError)) return null;
  const raw = err.details?.conversation_id;
  return typeof raw === 'string' && raw.trim() ? raw : null;
}

function readStoredModeId(): string | null {
  try {
    return localStorage.getItem(MODE_STORAGE);
  } catch {
    return null;
  }
}

function persistModeId(id: string) {
  try {
    localStorage.setItem(MODE_STORAGE, id);
  } catch {
    /* private mode */
  }
}

function readStoredProviderId(): string {
  try {
    return localStorage.getItem(PROVIDER_STORAGE) ?? '';
  } catch {
    return '';
  }
}

function persistProviderId(id: string) {
  try {
    if (id) localStorage.setItem(PROVIDER_STORAGE, id);
    else localStorage.removeItem(PROVIDER_STORAGE);
  } catch {
    /* private mode */
  }
}

function CloseMark() {
  return (
    <svg
      className="chat-btn__mark"
      width="11"
      height="11"
      viewBox="0 0 12 12"
      aria-hidden="true"
    >
      <path
        fill="currentColor"
        d="M2.22 1.28 6 5.05l3.78-3.77a.67.67 0 1 1 .94.94L6.95 6l3.77 3.78a.67.67 0 1 1-.94.94L6 6.95l-3.78 3.77a.67.67 0 1 1-.94-.94L5.05 6 1.28 2.22a.67.67 0 0 1 .94-.94Z"
      />
    </svg>
  );
}

function PlusMark() {
  return (
    <svg
      className="chat-btn__mark"
      width="11"
      height="11"
      viewBox="0 0 12 12"
      aria-hidden="true"
    >
      <path
        fill="currentColor"
        d="M6.72 2.05a.72.72 0 0 0-1.44 0v3.23H2.05a.72.72 0 0 0 0 1.44h3.23v3.23a.72.72 0 0 0 1.44 0V6.72h3.23a.72.72 0 0 0 0-1.44H6.72V2.05Z"
      />
    </svg>
  );
}

function pickDefaultModeId(modes: ChatMode[], preferred: string | null): string | null {
  if (preferred && modes.some((mode) => mode.id === preferred)) return preferred;
  return modes.find((mode) => mode.key === 'workbench')?.id ?? modes[0]?.id ?? null;
}

export default function ChatPage() {
  const { t, messages: i18n } = useI18n();
  const { id: routeId } = useParams<{ id?: string }>();
  const { state: navState } = useLocation();
  const navigate = useNavigate();
  const newChatNav = (navState as NewChatNav | null) ?? null;
  const confirmedFromNav = Boolean(newChatNav?.confirmedNew);

  const [conversationId, setConversationId] = useState<string | null>(
    routeId ?? null,
  );
  const [title, setTitle] = useState('');
  const [status, setStatus] = useState<ConversationDetail['status']>('active');
  const [messages, setMessages] = useState<Message[]>([]);
  const [skillsByMessage, setSkillsByMessage] = useState<
    Record<string, SkillUsedInfo[]>
  >({});
  const [pending, setPending] = useState(false);
  const [draftReply, setDraftReply] = useState('');
  const [liveSteps, setLiveSteps] = useState<ExecutionStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [inboxLink, setInboxLink] = useState(false);
  const [modes, setModes] = useState<ChatMode[]>([]);
  const [selectedModeId, setSelectedModeId] = useState<string | null>(null);
  const [lockedMode, setLockedMode] = useState<{
    id: string | null;
    key: string | null;
    name: string | null;
  } | null>(null);
  const [providers, setProviders] = useState<ProviderView[]>([]);
  const [providerId, setProviderId] = useState(readStoredProviderId);
  const [resuming, setResuming] = useState(() => !routeId && !confirmedFromNav);
  const [newChatConfirmed, setNewChatConfirmed] = useState(confirmedFromNav);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [settleOpen, setSettleOpen] = useState(false);
  const [draftModeId, setDraftModeId] = useState<string | null>(null);
  const [draftKnowledge, setDraftKnowledge] = useState(false);
  const autoOpenedPicker = useRef(false);

  useEffect(() => {
    let cancelled = false;
    getLLMConfig()
      .then((config) => {
        if (cancelled) return;
        const chatProviders = config.providers.filter((p) =>
          isChatProviderKind(p.kind),
        );
        setProviders(chatProviders);
        setProviderId((prev) =>
          prev && chatProviders.some((p) => p.id === prev) ? prev : '',
        );
      })
      .catch(() => {
        /* picker hidden when config cannot load */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    listChatModes()
      .then((list) => {
        if (cancelled) return;
        setModes(list);
        if (!routeId && !confirmedFromNav) {
          setSelectedModeId(pickDefaultModeId(list, readStoredModeId()));
        }
      })
      .catch(() => {
        /* picker stays empty; backend still defaults to workbench */
      });
    return () => {
      cancelled = true;
    };
  }, [routeId]);

  useEffect(() => {
    if (!routeId) {
      if (confirmedFromNav) {
        setResuming(false);
        setNewChatConfirmed(true);
        setConversationId(null);
        setMessages([]);
        setSkillsByMessage({});
        setTitle('');
        setStatus('active');
        setLockedMode(null);
        setError(null);
        setNotice(null);
        setInboxLink(false);
        if (newChatNav?.modeId) setSelectedModeId(newChatNav.modeId);
        return;
      }

      let cancelled = false;
      setResuming(true);
      listConversations({ limit: 1, status: 'active' })
        .then((page) => {
          if (cancelled) return;
          const latest = page.items[0];
          if (latest) {
            navigate(`/chat/${latest.id}`, { replace: true });
            return;
          }
          setResuming(false);
          setConversationId(null);
          setMessages([]);
          setSkillsByMessage({});
          setTitle('');
          setStatus('active');
          setLockedMode(null);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setResuming(false);
          setError(
            err instanceof ApiError ? err.message : t('chat.loadFailed'),
          );
        });
      return () => {
        cancelled = true;
      };
    }

    setResuming(false);
    setNewChatConfirmed(false);
    let cancelled = false;
    getConversation(routeId)
      .then((detail) => {
        if (cancelled) return;
        setConversationId(detail.id);
        setTitle(detail.title);
        setStatus(detail.status);
        setMessages(detail.messages);
        setLockedMode({
          id: detail.mode_id ?? null,
          key: detail.mode_key ?? 'workbench',
          name: detail.mode_name ?? t('nav.workbench'),
        });
        if (detail.mode_id) setSelectedModeId(detail.mode_id);

        const map: Record<string, SkillUsedInfo[]> = {};
        for (const message of detail.messages) {
          if (message.used_skill_ids?.length) {
            map[message.id] = message.used_skill_ids.map((skillId) => ({
              id: skillId,
              name: `Skill ${skillId.slice(0, 8)}`,
            }));
          }
        }
        setSkillsByMessage(map);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError ? err.message : t('chat.loadFailed'),
        );
      });

    return () => {
      cancelled = true;
    };
  }, [routeId, confirmedFromNav, newChatNav?.modeId, navigate, t]);

  const selectedMode =
    modes.find((mode) => mode.id === selectedModeId) ??
    modes.find((mode) => mode.id === lockedMode?.id) ??
    null;
  const modeKey = lockedMode?.key ?? selectedMode?.key ?? 'workbench';
  const modeName =
    lockedMode?.name ?? selectedMode?.name ?? t('nav.workbench');
  const canChat = Boolean(conversationId) || newChatConfirmed;

  const handleSend = useCallback(
    async (text: string, files?: File[]) => {
      if (!conversationId && !newChatConfirmed) return;
      setError(null);
      setNotice(null);
      setInboxLink(false);
      setPending(true);
      setDraftReply('');
      setLiveSteps([]);

      const tempId = `temp-${Date.now()}`;
      const optimistic: Message = {
        id: tempId,
        seq: messages.length + 1,
        role: 'user',
        content: optimisticContent(text, files),
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimistic]);

      let activeId = conversationId;
      let lastSteps: ExecutionStep[] = [];

      try {
        const response = await sendMessageStream(
          text,
          conversationId,
          files,
          (event) => {
            if (event.type === 'start' && event.conversation_id) {
              activeId = event.conversation_id;
              setConversationId(event.conversation_id);
            }
            if (event.type === 'error') {
              const fromError = event.details?.conversation_id;
              if (typeof fromError === 'string' && fromError.trim()) {
                activeId = fromError;
                setConversationId(fromError);
              }
            }
            if (event.type === 'token' && event.text) {
              setDraftReply((prev) => prev + event.text);
            }
            if (event.type === 'token_clear') {
              setDraftReply('');
            }
            lastSteps = applyLiveTrace(lastSteps, event);
            setLiveSteps(lastSteps);
          },
          conversationId ? null : selectedModeId,
          providerId || null,
        );

        setConversationId(response.conversation_id);
        if (response.title) setTitle(response.title);
        if (response.mode) {
          setLockedMode({
            id: response.mode.id,
            key: response.mode.key,
            name: response.mode.name,
          });
        }

        const detail = await getConversation(response.conversation_id);
        setMessages(detail.messages);
        setDraftReply('');
        setStatus(detail.status);
        if (detail.mode_id) {
          setLockedMode({
            id: detail.mode_id,
            key: detail.mode_key ?? response.mode?.key ?? null,
            name: detail.mode_name ?? response.mode?.name ?? null,
          });
        }

        if (response.used_skills.length > 0 && response.message_id) {
          setSkillsByMessage((prev) => ({
            ...prev,
            [response.message_id]: response.used_skills,
          }));
        }

        if (!routeId) {
          navigate(`/chat/${response.conversation_id}`, { replace: true });
        }
      } catch (err: unknown) {
        const fromError = conversationIdFromUnknown(err);
        if (fromError) activeId = fromError;
        const reason =
          err instanceof ApiError
            ? err.code === 'llm_error'
              ? `${err.message}${t('chat.llmHint')}`
              : err.message
            : t('chat.sendFailed');
        const banner = `${reason} ${t('chat.turnKept')}`;
        const failed = failedAssistantMessage(
          `${reason}\n\n${t('chat.turnKept')}`,
          freezeLiveSteps(lastSteps),
        );
        setError(banner);
        if (activeId) {
          setConversationId(activeId);
          try {
            const detail = await getConversation(activeId);
            setTitle((prev) => detail.title || prev);
            setStatus(detail.status);
            setMessages((prev) => {
              const hasQuery = detail.messages.some(
                (row) =>
                  row.role === 'user' && row.content === optimistic.content,
              );
              if (hasQuery) return detail.messages;
              const kept = prev.some((row) => row.id === tempId)
                ? prev
                : [...prev, optimistic];
              return [...kept, failed];
            });
            if (!routeId) {
              navigate(`/chat/${activeId}`, { replace: true });
            }
          } catch {
            setMessages((prev) => {
              const kept = prev.some((row) => row.id === tempId)
                ? prev
                : [...prev, optimistic];
              return [...kept, failed];
            });
          }
        } else {
          setMessages((prev) => {
            const kept = prev.some((row) => row.id === tempId)
              ? prev
              : [...prev, optimistic];
            return [...kept, failed];
          });
        }
      } finally {
        setPending(false);
        setDraftReply('');
        setLiveSteps([]);
      }
    },
    [conversationId, messages.length, navigate, newChatConfirmed, providerId, routeId, selectedModeId, t],
  );

  async function handleClose() {
    if (!conversationId) return;
    setError(null);
    try {
      const result = await closeConversation(conversationId);
      setStatus(result.status);
      setNotice(null);
      setInboxLink(Boolean(result.notes_triggered));
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('chat.closeFailed'));
    }
  }

  function openSettle() {
    if (!conversationId) return;
    setError(null);
    setNotice(null);
    setSettleOpen(true);
  }

  function openNewChatPicker() {
    const initial =
      selectedModeId ?? pickDefaultModeId(modes, readStoredModeId());
    setDraftModeId(initial);
    const mode = modes.find((item) => item.id === initial);
    setDraftKnowledge(Boolean(mode?.use_knowledge_memory));
    setPickerOpen(true);
  }

  function handleNew() {
    openNewChatPicker();
  }

  function handleCancelNewChat() {
    setPickerOpen(false);
  }

  async function handleConfirmNewChat() {
    if (!draftModeId) return;
    persistModeId(draftModeId);
    setSelectedModeId(draftModeId);
    const mode = modes.find((item) => item.id === draftModeId);
    if (
      mode &&
      (mode.key === 'tutor' || mode.key === 'companion') &&
      mode.use_knowledge_memory !== draftKnowledge
    ) {
      try {
        const updated = await updateChatMode(mode.id, {
          use_knowledge_memory: draftKnowledge,
        });
        setModes((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item)),
        );
      } catch (err: unknown) {
        setError(err instanceof ApiError ? err.message : t('modes.saveFailed'));
        return;
      }
    }
    setPickerOpen(false);
    setNewChatConfirmed(true);
    navigate('/', {
      replace: true,
      state: { confirmedNew: true, modeId: draftModeId } satisfies NewChatNav,
    });
  }

  useEffect(() => {
    if (autoOpenedPicker.current) return;
    if (resuming || conversationId || newChatConfirmed) return;
    if (modes.length === 0) return;
    autoOpenedPicker.current = true;
    openNewChatPicker();
  }, [resuming, conversationId, newChatConfirmed, modes]);

  const closed = status === 'closed';
  const hero = heroCopy(modeKey, modeName, t, i18n.chat);

  return (
    <div className="chat">
      <header className="chat__header">
        <div className="chat__heading">
          <OverflowTitle
            className="chat__title"
            text={title || t('chat.newTitle')}
          />
          <div className="chat__meta faint">
            <span className="badge badge--closed">{modeName}</span>
            {conversationId && (
              <span className="mono chat__id">
                {t('chat.messageCount', {
                  id: conversationId.slice(0, 8),
                  count: messages.length,
                })}
              </span>
            )}
          </div>
        </div>
        <div className="chat__actions">
          {closed && (
            <span className="badge badge--closed">{t('chat.closedBadge')}</span>
          )}
          {conversationId && !closed && (
            <button
              type="button"
              className="chat-btn chat-btn--ghost"
              onClick={() => openSettle()}
            >
              <SettleIcon size={14} />
              {t('conversations.settleAction')}
            </button>
          )}
          {conversationId && !closed && (
            <button
              type="button"
              className="chat-btn chat-btn--ghost"
              onClick={() => void handleClose()}
            >
              <CloseMark />
              {t('chat.close')}
            </button>
          )}
          <button
            type="button"
            className="chat-btn chat-btn--primary"
            onClick={handleNew}
          >
            <PlusMark />
            {t('chat.newChat')}
          </button>
        </div>
      </header>

      {(error || notice) && (
        <div style={{ padding: '12px 24px 0' }}>
          {error && <div className="alert alert--error">{error}</div>}
          {notice && (
            <div className="alert alert--info">
              {notice}
              {inboxLink && (
                <>
                  {' '}
                  <Link to="/knowledge?pending=1">{t('chat.openPendingInbox')}</Link>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {resuming ? (
        <div className="chat__messages">
          <p className="faint">{t('common.loading')}</p>
        </div>
      ) : (
        <div className={closed ? 'chat__main chat__main--closed' : 'chat__main'}>
          <MessageList
            messages={messages}
            skillsByMessage={skillsByMessage}
            pending={pending}
            draftReply={draftReply}
            liveSteps={liveSteps ?? []}
            hero={hero}
            onSuggestion={
              canChat && !closed ? (text) => void handleSend(text) : undefined
            }
          />
          <MessageInput
            onSend={handleSend}
            disabled={pending || !canChat || closed}
            placeholder={hero.placeholder}
            hint={hero.hint}
            providers={providers}
            providerId={providerId}
            onProviderIdChange={(id) => {
              setProviderId(id);
              persistProviderId(id);
            }}
          />
          {closed ? (
            <div className="chat__closed" role="status">
              {t('chat.closedOverlayTitle')}
            </div>
          ) : null}
        </div>
      )}
      {pickerOpen && (
        <NewChatDialog
          modes={modes}
          selectedId={draftModeId}
          knowledgeOn={draftKnowledge}
          onSelect={(id) => {
            setDraftModeId(id);
            const mode = modes.find((item) => item.id === id);
            setDraftKnowledge(Boolean(mode?.use_knowledge_memory));
          }}
          onKnowledge={setDraftKnowledge}
          onConfirm={() => void handleConfirmNewChat()}
          onCancel={handleCancelNewChat}
        />
      )}
      <SettleDialog
        conversationId={conversationId}
        open={settleOpen}
        onClose={() => setSettleOpen(false)}
        onDone={(result) => {
          setNotice(settleResultNotice(result, t));
          setInboxLink(
            result.results.some(
              (row) => row.kind === 'knowledge' && row.notes.length > 0,
            ),
          );
        }}
      />
    </div>
  );
}

function heroCopy(
  key: string,
  modeName: string,
  t: (path: MessageKey, vars?: Record<string, string>) => string,
  chat: {
    suggestions: readonly string[];
    suggestionsTutor: readonly string[];
    suggestionsCompanion: readonly string[];
    suggestionsCustom: readonly string[];
  },
): ChatHeroCopy {
  if (key === 'tutor') {
    return {
      eyebrow: t('chat.tutorHeroEyebrow'),
      title1: t('chat.tutorHeroTitle1'),
      title2: t('chat.tutorHeroTitle2'),
      lead: t('chat.tutorHeroLead'),
      suggestions: [...chat.suggestionsTutor],
      placeholder: t('chat.tutorPlaceholder'),
      hint: t('chat.tutorHint'),
    };
  }
  if (key === 'companion') {
    return {
      eyebrow: t('chat.companionHeroEyebrow'),
      title1: t('chat.companionHeroTitle1'),
      title2: t('chat.companionHeroTitle2'),
      lead: t('chat.companionHeroLead'),
      suggestions: [...chat.suggestionsCompanion],
      placeholder: t('chat.companionPlaceholder'),
      hint: t('chat.companionHint'),
    };
  }
  if (key !== 'workbench') {
    return {
      eyebrow: modeName,
      title1: t('chat.customHeroTitle1'),
      title2: t('chat.customHeroTitle2'),
      lead: t('chat.customHeroLead', { name: modeName }),
      suggestions: [...chat.suggestionsCustom],
      placeholder: t('chat.customPlaceholder'),
      hint: t('chat.customHint'),
    };
  }
  return {
    eyebrow: t('chat.heroEyebrow'),
    title1: t('chat.heroTitle1'),
    title2: t('chat.heroTitle2'),
    lead: t('chat.heroLead'),
    suggestions: [...chat.suggestions],
    placeholder: t('chat.inputPlaceholder'),
    hint: t('chat.composerHint'),
  };
}
