import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import { getUsageSummary } from '../api/usage';
import type { UsagePeriod, UsageSummary } from '../api/types';
import { useI18n, type MessageKey } from '../i18n';

const PURPOSE_KEY: Record<string, MessageKey> = {
  chat: 'usage.purposeChat',
  skill: 'usage.purposeSkill',
  memory: 'usage.purposeMemory',
  notes: 'usage.purposeNotes',
  knowledge: 'usage.purposeKnowledge',
  probe: 'usage.purposeProbe',
  other: 'usage.purposeOther',
};

function formatTokens(n: number): string {
  return n.toLocaleString();
}

function PeriodCard({
  title,
  period,
}: {
  title: string;
  period: UsagePeriod;
}) {
  const { t } = useI18n();
  return (
    <article className="card memory-card">
      <h3 className="mode-card__name">{title}</h3>
      <p className="usage-card__total">
        {formatTokens(period.total_tokens)}
        <span className="usage-card__unit"> tokens</span>
      </p>
      <p className="memory-group__desc">
        {t('usage.split', {
          prompt: formatTokens(period.prompt_tokens),
          completion: formatTokens(period.completion_tokens),
          calls: period.calls,
        })}
      </p>
      {period.by_purpose.length > 0 ? (
        <ul className="memory-group__list usage-card__list">
          {period.by_purpose.map((row) => (
            <li key={row.purpose}>
              <span className="memory-group__label">
                {t(PURPOSE_KEY[row.purpose] ?? 'usage.purposeOther')}
              </span>
              ：{formatTokens(row.total_tokens)}
              <span className="faint"> · {row.calls}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="memory-group__desc">{t('usage.emptyPeriod')}</p>
      )}
    </article>
  );
}

export default function UsageSection() {
  const { t } = useI18n();
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await getUsageSummary());
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('usage.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const models = summary?.month.by_model ?? [];

  return (
    <section id="usage" className="modes-section">
      <div className="page__header" style={{ marginBottom: 12 }}>
        <div>
          <h2 className="section__title" style={{ margin: 0 }}>
            {t('usage.title')}
          </h2>
          <p className="page__subtitle">{t('usage.subtitle')}</p>
        </div>
      </div>

      {error && <div className="alert alert--error">{error}</div>}

      {loading || !summary ? (
        <div className="empty row" style={{ justifyContent: 'center' }}>
          <span className="spinner" aria-hidden="true" />
          <span>{t('common.loading')}</span>
        </div>
      ) : (
        <>
          <div className="memory__grid">
            <PeriodCard title={t('usage.today')} period={summary.today} />
            <PeriodCard title={t('usage.month')} period={summary.month} />
            <PeriodCard title={t('usage.all')} period={summary.all} />
          </div>
          {models.length > 0 ? (
            <div className="usage-models">
              <h4 className="memory-group__title">{t('usage.byModel')}</h4>
              <ul className="memory-group__list">
                {models.map((row) => (
                  <li key={`${row.provider_label}:${row.model}`}>
                    <span className="memory-group__label">
                      {row.provider_label
                        ? `${row.provider_label} / ${row.model}`
                        : row.model}
                    </span>
                    ：{formatTokens(row.total_tokens)}
                    <span className="faint"> · {row.calls}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
