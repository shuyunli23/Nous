import { useEffect, useRef, useState } from 'react';

import type { ExecutionStep, Message, SkillUsedInfo } from '../api/types';
import { useI18n } from '../i18n';
import { splitUserAttachments } from '../lib/chatAttachments';
import ExecutionTrace from './ExecutionTrace';
import MarkdownContent from './MarkdownContent';
import SkillBadge from './SkillBadge';
import {
  renderPlainContent,
  UserAttachmentDump,
} from './UserMessageContent';

interface MessageListProps {
  messages: Message[];
  skillsByMessage: Record<string, SkillUsedInfo[]>;
  pending?: boolean;
  draftReply?: string;
  liveSteps?: ExecutionStep[];
  hero?: ChatHeroCopy;
  onSuggestion?: (text: string) => void;
}

export function UserMark() {
  return (
    <svg
      className="msg__avatar-mark msg__avatar-mark--user"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="8" r="3" />
      <path d="M6.5 19c.7-3.6 2.8-5.2 5.5-5.2s4.8 1.6 5.5 5.2" />
    </svg>
  );
}

export interface ChatHeroCopy {
  eyebrow: string;
  title1: string;
  title2: string;
  lead: string;
  suggestions: string[];
  placeholder: string;
  hint: string;
}

function UserBubble({ text }: { text: string }) {
  const { t } = useI18n();
  const { visible, dump, after } = splitUserAttachments(text);
  const downloadFile = t('chat.downloadFile');
  const viewOriginal = t('chat.viewOriginal');
  return (
    <>
      {visible
        ? renderPlainContent(visible, downloadFile, viewOriginal)
        : null}
      {dump ? <UserAttachmentDump dump={dump} /> : null}
      {after
        ? renderPlainContent(after, downloadFile, viewOriginal)
        : null}
    </>
  );
}

function MessageActions({ text }: { text: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="msg__actions">
      <button
        type="button"
        className="msg__action-btn"
        onClick={() => void copy()}
        title={t('chat.copyMessage')}
      >
        {copied ? t('common.copied') : t('common.copy')}
      </button>
    </div>
  );
}

function formatTime(iso: string | undefined) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export default function MessageList({
  messages,
  skillsByMessage,
  pending,
  draftReply,
  liveSteps,
  hero,
  onSuggestion,
}: MessageListProps) {
  const { t, messages: i18n } = useI18n();
  const endRef = useRef<HTMLDivElement>(null);

  const liveCount = liveSteps?.length ?? 0;
  const liveTitle = liveSteps?.[liveSteps.length - 1]?.title;
  const runningStep = liveSteps?.find((step) => step.status === 'running');
  const draft = draftReply ?? '';
  const liveThinkLen =
    liveSteps?.reduce((n, step) => n + (step.detail?.length ?? 0), 0) ?? 0;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, pending, liveCount, liveTitle, draft.length, liveThinkLen]);

  const roleLabel: Record<string, string> = {
    user: t('chat.roleUser'),
    assistant: t('chat.roleAssistant'),
    system: t('chat.roleSystem'),
    tool: t('chat.roleTool'),
  };

  const visible = messages.filter(
    (m) => m.role === 'user' || m.role === 'assistant',
  );
  const lastAssistantId = [...visible]
    .reverse()
    .find((m) => m.role === 'assistant')?.id;

  if (visible.length === 0 && !pending) {
    return (
      <div className="chat__messages">
        <div className="hero">
          <p className="hero__eyebrow">{hero?.eyebrow ?? t('chat.heroEyebrow')}</p>
          <h2 className="hero__title">
            {hero?.title1 ?? t('chat.heroTitle1')}
            <br />
            {hero?.title2 ?? t('chat.heroTitle2')}
          </h2>
          <p className="hero__lead">{hero?.lead ?? t('chat.heroLead')}</p>
          <div className="hero__chips">
            {onSuggestion
              ? (hero?.suggestions ?? i18n.chat.suggestions).map((text) => (
                  <button
                    key={text}
                    type="button"
                    className="hero__chip"
                    onClick={() => onSuggestion(text)}
                  >
                    {text}
                  </button>
                ))
              : null}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat__messages">
      {visible.map((message) => {
        const skills = skillsByMessage[message.id] ?? [];
        const isAssistant = message.role === 'assistant';
        return (
          <article
            key={message.id}
            className={`msg msg--${message.role}`}
          >
            <div className="msg__avatar" aria-hidden="true">
              {message.role === 'user' ? (
                <UserMark />
              ) : (
                <img className="msg__avatar-mark" src="/nous-mark.png" alt="" />
              )}
            </div>
            <div className="msg__body">
              <div className="msg__header">
                <span className="msg__role">
                  {roleLabel[message.role] ?? message.role}
                </span>
                {message.created_at && (
                  <span className="msg__time">
                    {formatTime(message.created_at)}
                  </span>
                )}
              </div>
              {isAssistant && message.execution_trace?.length ? (
                <ExecutionTrace
                  steps={message.execution_trace}
                  defaultOpen={message.id === lastAssistantId}
                />
              ) : null}

              <div
                className={
                  isAssistant ? 'msg__content msg__content--md' : 'msg__content'
                }
              >
                {isAssistant ? (
                  <MarkdownContent
                    content={message.content}
                    executionTrace={message.execution_trace}
                  />
                ) : (
                  <UserBubble text={message.content} />
                )}
              </div>

              {(skills.length > 0 ||
                message.token_usage?.total_tokens ||
                (isAssistant && message.created_at)) && (
                <div className="msg__meta">
                  {skills.map((skill) => (
                    <SkillBadge
                      key={skill.id}
                      skill={skill}
                      messageId={message.id}
                    />
                  ))}
                  {(isAssistant && message.created_at) ||
                  message.token_usage?.total_tokens ? (
                    <span className="faint mono">
                      {isAssistant && message.created_at
                        ? formatTime(message.created_at)
                        : null}
                      {isAssistant &&
                      message.created_at &&
                      message.token_usage?.total_tokens
                        ? ' · '
                        : null}
                      {message.token_usage?.total_tokens
                        ? `${message.token_usage.total_tokens} tokens`
                        : null}
                    </span>
                  ) : null}
                </div>
              )}

              {isAssistant && message.content.trim() ? (
                <MessageActions text={message.content} />
              ) : null}
            </div>
          </article>
        );
      })}

      {pending && (
        <article className="msg msg--assistant">
          <div className="msg__avatar" aria-hidden="true">
            <img className="msg__avatar-mark" src="/nous-mark.png" alt="" />
          </div>
          <div className="msg__body">
            <div className="msg__header">
              <span className="msg__role">{t('chat.roleAssistant')}</span>
            </div>
            {liveSteps && liveSteps.length > 0 ? (
              <ExecutionTrace steps={liveSteps} defaultOpen live />
            ) : null}
            {draft ? (
              <div
                className="msg__content msg__content--md msg__content--streaming"
                role="status"
                aria-live="polite"
              >
                <MarkdownContent content={draft} />
                <span className="msg__stream-caret" aria-hidden="true" />
              </div>
            ) : runningStep?.kind === 'think' && runningStep.detail ? null : (
              <div className="msg__typing" role="status" aria-live="polite">
                <span className="msg__typing-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <span>
                  {runningStep ? runningStep.title : t('chat.executing')}
                </span>
              </div>
            )}
          </div>
        </article>
      )}

      <div ref={endRef} />
    </div>
  );
}
