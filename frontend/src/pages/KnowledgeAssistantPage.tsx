import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { applyLiveTrace, type ChatStreamEvent } from '../api/chat';
import { ApiError } from '../api/client';
import {
  askAssistantStream,
  type Citation,
} from '../api/knowledge';
import type { ExecutionStep } from '../api/types';
import ExecutionTrace from '../components/ExecutionTrace';
import MarkdownContent from '../components/MarkdownContent';
import { UserMark } from '../components/MessageList';
import NexusMark from '../components/NexusMark';
import SendButton from '../components/SendButton';
import { useI18n } from '../i18n';

interface Turn {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  source?: string;
  model?: string | null;
  execution_trace?: ExecutionStep[];
}

export default function KnowledgeAssistantPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [input, setInput] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftReply, setDraftReply] = useState('');
  const [liveSteps, setLiveSteps] = useState<ExecutionStep[]>([]);
  const logRef = useRef<HTMLDivElement>(null);
  const canSend = Boolean(input.trim()) && !busy;

  useEffect(() => {
    const el = logRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [turns.length, busy, draftReply.length, liveSteps]);

  async function send() {
    const message = input.trim();
    if (!message || busy) return;
    setInput('');
    setError(null);
    setDraftReply('');
    setLiveSteps([]);
    const nextTurns: Turn[] = [...turns, { role: 'user', content: message }];
    setTurns(nextTurns);
    setBusy(true);
    try {
      const history = nextTurns
        .slice(0, -1)
        .map((turn) => ({ role: turn.role, content: turn.content }));
      const res = await askAssistantStream({ message, history }, (event) => {
        if (event.type === 'token' && event.text) {
          setDraftReply((prev) => prev + event.text);
        }
        setLiveSteps((prev) =>
          applyLiveTrace(prev, event as ChatStreamEvent),
        );
      });
      setTurns([
        ...nextTurns,
        {
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          source: res.source,
          model: res.model,
          execution_trace: res.execution_trace,
        },
      ]);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('km.askFailed'));
      setTurns(nextTurns);
    } finally {
      setBusy(false);
      setDraftReply('');
      setLiveSteps([]);
    }
  }

  function renderTurn(turn: Turn, i: number, streaming = false) {
    const isUser = turn.role === 'user';
    return (
      <article key={i} className={`km-turn km-turn--${turn.role}`}>
        {isUser ? null : (
          <div className="msg__avatar msg__avatar--nexus" aria-hidden="true">
            <NexusMark className="msg__avatar-mark" />
          </div>
        )}
        <div className="km-turn__body">
          {isUser ? null : (
            <div className="km-bubble__role">
              {t('km.assistantName')}
              {turn.model ? ` · ${turn.model}` : ''}
              {turn.source === 'local' ? ` · ${t('km.localAnswer')}` : ''}
            </div>
          )}
          {turn.role === 'assistant' && turn.execution_trace?.length ? (
            <ExecutionTrace
              steps={turn.execution_trace}
              defaultOpen={i === turns.length - 1}
            />
          ) : null}
          {turn.role === 'assistant' ? (
            streaming ? (
              <div className="msg__content msg__content--md msg__content--streaming">
                <MarkdownContent content={turn.content} />
                <span className="msg__stream-caret" aria-hidden="true" />
              </div>
            ) : (
              <MarkdownContent content={turn.content} />
            )
          ) : (
            <p>{turn.content}</p>
          )}
          {turn.citations && turn.citations.length > 0 && (
            <div className="km-cites">
              {turn.citations.map((c, idx) => (
                <button
                  key={c.id}
                  type="button"
                  className="km-cite"
                  onClick={() => navigate(`/knowledge/${c.id}`)}
                >
                  [{idx + 1}] {c.title}
                </button>
              ))}
            </div>
          )}
        </div>
        {isUser ? (
          <div className="msg__avatar" aria-hidden="true">
            <UserMark />
          </div>
        ) : null}
      </article>
    );
  }

  return (
    <div className="page km-assistant">
      <header className="page__header">
        <div>
          <h1 className="page__title">{t('km.assistantTitle')}</h1>
          <p className="page__subtitle">{t('km.assistantLead')}</p>
        </div>
      </header>

      {error && <p className="banner banner--error">{error}</p>}

      <div className="km-assistant__log" ref={logRef}>
        {turns.length === 0 && !busy && (
          <p className="empty">{t('km.assistantEmpty')}</p>
        )}
        {turns.map((turn, i) => renderTurn(turn, i))}
        {busy && (draftReply || liveSteps.length > 0)
          ? renderTurn(
              {
                role: 'assistant',
                content: draftReply,
                execution_trace: liveSteps,
              },
              turns.length,
              Boolean(draftReply),
            )
          : null}
        {busy && !draftReply && liveSteps.length === 0 ? (
          <p className="faint km-assistant__wait">{t('common.processing')}</p>
        ) : null}
      </div>

      <form
        className="km-assistant__composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <div className="composer__box">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('km.assistantPlaceholder')}
            disabled={busy}
            aria-label={t('km.assistantPlaceholder')}
          />
          <SendButton
            type="submit"
            ready={canSend}
            disabled={busy}
            label={t('chat.send')}
          />
        </div>
      </form>
    </div>
  );
}
