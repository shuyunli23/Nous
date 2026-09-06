import { useEffect, useRef, useState } from 'react';

import type { ExecutionStep, TodoItem } from '../api/types';
import { useI18n } from '../i18n';

interface ExecutionTraceProps {
  steps: ExecutionStep[];
  defaultOpen?: boolean;
  live?: boolean;
  label?: string;
}

const STATUS_MARK: Record<string, string> = {
  ok: '✓',
  error: '!',
  info: '·',
  running: '',
};

export function formatElapsedMs(ms: number): string {
  const sec = Math.max(0, ms) / 1000;
  if (sec < 10) return `${sec.toFixed(1)}s`;
  return `${String(Math.round(sec))}s`;
}

function TodoList({ items }: { items: TodoItem[] }) {
  return (
    <ul className="exec__todos">
      {items.map((item, index) => {
        const status = item.status || 'pending';
        const mark =
          status === 'completed' ? '✓' : status === 'in_progress' ? '›' : '·';
        return (
          <li
            key={`${status}-${item.content}-${index}`}
            className={`exec__todo exec__todo--${status}`}
          >
            <span className="exec__todo-mark" aria-hidden="true">
              {mark}
            </span>
            <span>{item.content}</span>
          </li>
        );
      })}
    </ul>
  );
}

function previewLine(text: string): string {
  const line = text.replace(/\s+/g, ' ').trim();
  if (line.length <= 72) return line;
  return `${line.slice(0, 71)}…`;
}

function CotBody({
  text,
  streaming,
}: {
  text: string;
  streaming: boolean;
}) {
  const { t } = useI18n();
  const scroller = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(streaming);

  useEffect(() => {
    if (streaming) setOpen(true);
  }, [streaming]);

  useEffect(() => {
    const el = scroller.current;
    if (!el || !streaming || !open) return;
    el.scrollTop = el.scrollHeight;
  }, [text, streaming, open]);

  if (!text && !streaming) return null;

  const chars = text.replace(/\s/g, '').length;
  const meta = streaming
    ? t('exec.summaryRunning')
    : chars > 0
      ? t('exec.outputChars', { n: chars })
      : t('exec.outputPreview');

  return (
    <div className="exec__fold">
      <button
        type="button"
        className="exec__fold-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="exec__chevron" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
        <span className="exec__fold-label">{t('exec.output')}</span>
        <span className="exec__fold-meta faint">{meta}</span>
      </button>
      {open ? (
        <div
          ref={scroller}
          className={`exec__cot${streaming ? ' exec__cot--live' : ''}`}
        >
          {text}
          {streaming ? (
            <span className="msg__stream-caret" aria-hidden="true" />
          ) : null}
        </div>
      ) : text ? (
        <p className="exec__fold-preview">{previewLine(text)}</p>
      ) : null}
    </div>
  );
}

export default function ExecutionTrace({
  steps,
  defaultOpen = true,
  live = false,
  label,
}: ExecutionTraceProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(defaultOpen);
  const [now, setNow] = useState(() => Date.now());
  const hasRunning = steps.some((step) => step.status === 'running');

  useEffect(() => {
    if (!hasRunning) return;
    const id = window.setInterval(() => setNow(Date.now()), 200);
    return () => window.clearInterval(id);
  }, [hasRunning]);

  if (!steps.length) return null;

  function kindLabel(step: ExecutionStep): string {
    if (step.kind === 'skill_retrieve' || step.kind === 'retrieve') {
      return t('exec.retrieve');
    }
    if (step.kind === 'plan') return t('exec.plan');
    if (step.kind === 'guard') return t('exec.guard');
    if (step.kind === 'think') return t('exec.think');
    if (step.kind === 'tool') return t('exec.tool');
    if (step.kind === 'verify') return t('exec.verify');
    if (step.kind === 'answer') return t('exec.answer');
    return step.kind || t('exec.step');
  }

  function elapsedLabel(step: ExecutionStep): string | null {
    if (step.status === 'running') {
      const started = step.started_at ?? now;
      return formatElapsedMs(now - started);
    }
    if (typeof step.elapsed_ms === 'number') {
      return formatElapsedMs(step.elapsed_ms);
    }
    return null;
  }

  const toolCount = steps.filter((s) => s.kind === 'tool').length;
  const summary = hasRunning
    ? t('exec.summaryRunning')
    : toolCount > 0
      ? t('exec.summaryTools', { steps: steps.length, tools: toolCount })
      : t('exec.summarySteps', { steps: steps.length });

  return (
    <div className={`exec${live ? ' exec--live' : ''}`}>
      <button
        type="button"
        className="exec__toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="exec__chevron" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
        <span className="exec__toggle-label">{label || t('exec.toggle')}</span>
        <span className="exec__toggle-meta faint">{summary}</span>
      </button>

      {open && (
        <ol className="exec__list">
          {steps.map((step, index) => {
            const status = step.status || 'ok';
            const elapsed = elapsedLabel(step);
            const streaming =
              live && status === 'running' && step.kind === 'think';
            const hasModelOutput = step.kind === 'think' && Boolean(step.detail || streaming);
            return (
              <li
                key={`${step.kind}-${step.tool || step.title}-${index}`}
                className={`exec__step exec__step--${status}`}
              >
                <div className="exec__rail" aria-hidden="true">
                  <span className="exec__dot">{STATUS_MARK[status] ?? '·'}</span>
                </div>
                <div className="exec__body">
                  <div className="exec__row">
                    <span className="exec__kind">{kindLabel(step)}</span>
                    <span className="exec__title mono">{step.title}</span>
                    {elapsed ? (
                      <span className="exec__elapsed mono">{elapsed}</span>
                    ) : null}
                  </div>
                  {hasModelOutput ? (
                    <CotBody text={step.detail || ''} streaming={streaming} />
                  ) : step.todos && step.todos.length > 0 ? (
                    <TodoList items={step.todos} />
                  ) : step.detail ? (
                    <div className="exec__detail">{step.detail}</div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
