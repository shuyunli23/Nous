import { useEffect, useRef, useState } from 'react';

import { ApiError } from '../api/client';
import {
  applySettleTrace,
  proposeSettle,
  runSettleStream,
} from '../api/conversations';
import type {
  ExecutionStep,
  SettleKind,
  SettleProposal,
  SettleRunResult,
} from '../api/types';
import { useI18n, type MessageKey, type Vars } from '../i18n';
import ExecutionTrace from './ExecutionTrace';

const KIND_LABEL: Record<SettleKind, MessageKey> = {
  skill: 'settle.kindSkill',
  knowledge: 'settle.kindKnowledge',
  persona: 'settle.kindPersona',
  pack: 'settle.kindPack',
};

const KIND_HINT: Record<SettleKind, MessageKey> = {
  skill: 'settle.hintSkill',
  knowledge: 'settle.hintKnowledge',
  persona: 'settle.hintPersona',
  pack: 'settle.hintPack',
};

function emptySelection(): Record<SettleKind, boolean> {
  return { skill: false, knowledge: false, persona: false, pack: false };
}

function resultTone(row: SettleRunResult['results'][number]): 'ok' | 'skip' | 'err' {
  if (row.error || (!row.ok && !row.skipped)) return 'err';
  if (row.skipped) return 'skip';
  return 'ok';
}

export function settleResultNotice(
  result: SettleRunResult,
  t: (key: MessageKey, vars?: Vars) => string,
): string {
  const parts = result.results.map((row) => {
    const name = t(KIND_LABEL[row.kind]);
    const tone = resultTone(row);
    const headline =
      tone === 'ok'
        ? t('settle.resultWritten', { name })
        : tone === 'skip'
          ? t('settle.resultSkipped', { name })
          : t('settle.resultFailed', { name });
    const detail = row.error || row.detail || row.reason || '';
    return detail ? `${headline}：${detail}` : headline;
  });
  return parts.join(' ') || t('settle.finished');
}

export default function SettleDialog({
  conversationId,
  open,
  onClose,
  onDone,
}: {
  conversationId: string | null;
  open: boolean;
  onClose: () => void;
  onDone?: (result: SettleRunResult) => void;
}) {
  const { t } = useI18n();
  const [phase, setPhase] = useState<'propose' | 'review' | 'run' | 'done'>(
    'propose',
  );
  const [proposal, setProposal] = useState<SettleProposal | null>(null);
  const [selected, setSelected] = useState(emptySelection);
  const [grantPython, setGrantPython] = useState(true);
  const [grantNetwork, setGrantNetwork] = useState(false);
  const [analyzeSteps, setAnalyzeSteps] = useState<ExecutionStep[]>([]);
  const [runSteps, setRunSteps] = useState<ExecutionStep[]>([]);
  const [runResult, setRunResult] = useState<SettleRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(true);

  useEffect(() => {
    if (!open || !conversationId) return;
    let cancelled = false;
    setPhase('propose');
    setProposal(null);
    setError(null);
    setSelected(emptySelection());
    setGrantPython(true);
    setGrantNetwork(false);
    setRunSteps([]);
    setRunResult(null);
    setAnalyzeSteps([
      {
        kind: 'analyze',
        title: t('settle.reading'),
        status: 'running',
        started_at: Date.now(),
      },
    ]);

    void proposeSettle(conversationId)
      .then((next) => {
        if (cancelled) return;
        setProposal(next);
        setSelected({
          skill: Boolean(next.items.find((item) => item.kind === 'skill')?.recommended),
          knowledge: Boolean(
            next.items.find((item) => item.kind === 'knowledge')?.recommended,
          ),
          persona: Boolean(
            next.items.find((item) => item.kind === 'persona')?.recommended,
          ),
          pack: Boolean(next.items.find((item) => item.kind === 'pack')?.recommended),
        });
        const suggested = next.items
          .filter((item) => item.recommended)
          .map((item) => t(KIND_LABEL[item.kind]));
        setAnalyzeSteps([
          {
            kind: 'analyze',
            title: t('settle.reading'),
            status: 'ok',
            detail: next.summary,
          },
          {
            kind: 'plan',
            title: t('settle.judged'),
            status: 'ok',
            detail: suggested.length ? suggested.join('、') : undefined,
          },
        ]);
        setPhase('review');
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError ? err.message : t('settle.proposeFailed'),
        );
        setAnalyzeSteps([
          {
            kind: 'analyze',
            title: t('settle.reading'),
            status: 'error',
            detail:
              err instanceof ApiError ? err.message : t('settle.proposeFailed'),
          },
        ]);
      });

    followRef.current = true;
    return () => {
      cancelled = true;
    };
  }, [open, conversationId, t]);

  useEffect(() => {
    const el = bodyRef.current;
    if (!el || !followRef.current) return;
    const pin = () => {
      const box = bodyRef.current;
      if (!box || !followRef.current) return;
      box.scrollTop = box.scrollHeight;
    };
    pin();
    const id = window.requestAnimationFrame(pin);
    return () => window.cancelAnimationFrame(id);
  }, [analyzeSteps, runSteps, runResult, phase, proposal, error]);

  if (!open || !conversationId) return null;

  const picked = (Object.keys(selected) as SettleKind[]).filter(
    (kind) => selected[kind],
  );
  const busy = phase === 'propose' || phase === 'run';
  const canPick = phase === 'review';

  async function handleRun() {
    if (!conversationId || picked.length === 0) return;
    setError(null);
    followRef.current = true;
    setPhase('run');
    setRunSteps([]);
    setRunResult(null);
    const grants = selected.pack
      ? [
          ...(grantPython ? ['script.python'] : []),
          ...(grantNetwork ? ['network'] : []),
        ]
      : undefined;
    try {
      const next = await runSettleStream(
        conversationId,
        picked,
        (event) => {
          setRunSteps((prev) => applySettleTrace(prev, event));
        },
        grants,
      );
      setRunResult(next);
      setPhase('done');
      onDone?.(next);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('settle.runFailed'));
      setPhase('review');
    }
  }

  return (
    <div
      className="modal__backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settle-dialog-title"
      onClick={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div className="modal settle-modal">
        <div className="modal__header">
          <h2 className="modal__title" id="settle-dialog-title">
            {t('settle.title')}
          </h2>
          <button
            type="button"
            className="close-btn"
            onClick={onClose}
            aria-label={t('common.close')}
            disabled={phase === 'run'}
          >
            ×
          </button>
        </div>

        <div
          className="modal__body settle-body"
          ref={bodyRef}
          onScroll={() => {
            const el = bodyRef.current;
            if (!el) return;
            const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
            followRef.current = gap < 56;
          }}
        >
          {error ? <div className="alert alert--error">{error}</div> : null}

          <ExecutionTrace
            key={phase === 'propose' || phase === 'review' ? 'analyze-open' : 'analyze-fold'}
            steps={analyzeSteps}
            label={t('settle.analyzeProcess')}
            defaultOpen={phase === 'propose' || phase === 'review'}
            live={phase === 'propose'}
          />

          {proposal ? (
            <div className="settle-pick">
              <div className="settle-pick__head">{t('settle.pickTitle')}</div>
              {canPick ? <p className="settle-lead">{t('settle.confirmLead')}</p> : null}
              <div className="settle-list" role="group" aria-label={t('settle.pickTitle')}>
                {proposal.items.map((item) => {
                  const on = selected[item.kind];
                  return (
                    <button
                      key={item.kind}
                      type="button"
                      role="checkbox"
                      aria-checked={on}
                      disabled={!canPick}
                      className={on ? 'settle-row settle-row--on' : 'settle-row'}
                      onClick={() =>
                        setSelected((prev) => ({
                          ...prev,
                          [item.kind]: !prev[item.kind],
                        }))
                      }
                    >
                      <span className="settle-row__tick" aria-hidden="true">
                        {on ? (
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                            <path
                              d="M2.4 6.1 4.7 8.4 9.6 3.4"
                              stroke="currentColor"
                              strokeWidth="1.8"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        ) : null}
                      </span>
                      <span>
                        <span className="settle-row__top">
                          <span className="settle-row__title">
                            {t(KIND_LABEL[item.kind])}
                          </span>
                          {item.recommended ? (
                            <span className="settle-row__mark">
                              {t('settle.recommended')}
                            </span>
                          ) : null}
                        </span>
                        <span className="settle-row__reason">
                          {item.reason || t(KIND_HINT[item.kind])}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
              {selected.pack ? (
                <div className="settle-grant">
                  <div className="settle-grant__head">{t('settle.packGrantTitle')}</div>
                  <p className="settle-grant__lead">{t('settle.packGrantLead')}</p>
                  <label className="settle-grant__row">
                    <input
                      type="checkbox"
                      checked={grantPython}
                      disabled={!canPick}
                      onChange={(e) => setGrantPython(e.target.checked)}
                    />
                    <span>{t('settle.packGrantPython')}</span>
                  </label>
                  <label className="settle-grant__row">
                    <input
                      type="checkbox"
                      checked={grantNetwork}
                      disabled={!canPick}
                      onChange={(e) => setGrantNetwork(e.target.checked)}
                    />
                    <span>{t('settle.packGrantNetwork')}</span>
                  </label>
                  {!grantPython ? (
                    <p className="settle-grant__warn">{t('settle.packGrantPending')}</p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}

          {phase === 'run' || phase === 'done' || runSteps.length > 0 ? (
            <ExecutionTrace
              steps={
                runSteps.length
                  ? runSteps
                  : [
                      {
                        kind: 'settle',
                        title: t('settle.running'),
                        status: 'running',
                        started_at: Date.now(),
                      },
                    ]
              }
              label={t('settle.runProcess')}
              defaultOpen
              live={phase === 'run'}
            />
          ) : null}

          {phase === 'done' && runResult?.results.length ? (
            <div className="settle-result">
              <div className="settle-result__head">{t('settle.resultHead')}</div>
              {runResult.results.map((row) => {
                const tone = resultTone(row);
                const name = t(KIND_LABEL[row.kind]);
                const headline =
                  tone === 'ok'
                    ? t('settle.resultWritten', { name })
                    : tone === 'skip'
                      ? t('settle.resultSkipped', { name })
                      : t('settle.resultFailed', { name });
                const detail = row.error || row.detail || row.reason || '';
                return (
                  <div
                    key={row.kind}
                    className={`settle-result__card settle-result__card--${tone}`}
                  >
                    <div className="settle-result__title">{headline}</div>
                    {detail ? <p className="settle-result__detail">{detail}</p> : null}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>

        <div className="modal__footer">
          <button
            type="button"
            className="btn"
            onClick={onClose}
            disabled={phase === 'run'}
          >
            {phase === 'done' ? t('common.close') : t('common.cancel')}
          </button>
          {phase === 'review' ? (
            <button
              type="button"
              className="btn btn--primary"
              disabled={picked.length === 0 || busy}
              onClick={() => void handleRun()}
            >
              {t('settle.start', { n: picked.length })}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
