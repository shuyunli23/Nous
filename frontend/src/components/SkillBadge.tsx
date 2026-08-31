import { useState } from 'react';
import { Link } from 'react-router-dom';

import { sendSkillFeedback } from '../api/skills';
import type { SkillUsedInfo } from '../api/types';
import { useI18n } from '../i18n';

interface SkillBadgeProps {
  skill: SkillUsedInfo;
  messageId?: string;
}

export default function SkillBadge({ skill, messageId }: SkillBadgeProps) {
  const { t } = useI18n();
  const [voted, setVoted] = useState<'positive' | 'negative' | null>(null);
  const [busy, setBusy] = useState(false);

  async function vote(value: 'positive' | 'negative') {
    if (voted || busy) return;
    setBusy(true);
    try {
      await sendSkillFeedback(skill.id, value, messageId);
      setVoted(value);
    } catch {
      /* non-critical */
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="skill-badge">
      <span aria-hidden="true">🧠</span>
      <Link
        to={`/skills/${skill.id}`}
        title={t('skillBadge.view', { name: skill.name })}
      >
        {skill.name}
      </Link>
      {typeof skill.similarity === 'number' && (
        <span className="skill-badge__score">
          {skill.similarity.toFixed(2)}
        </span>
      )}
      {voted ? (
        <span
          className="skill-badge__vote skill-badge__vote--done"
          title={
            voted === 'positive'
              ? t('skillBadge.votedHelpful')
              : t('skillBadge.votedUnhelpful')
          }
        >
          {voted === 'positive' ? '✓' : '✕'}
        </span>
      ) : (
        <>
          <button
            type="button"
            className="skill-badge__vote"
            onClick={() => vote('positive')}
            disabled={busy}
            title={t('skillBadge.helpful')}
            aria-label={t('skillBadge.markHelpful', { name: skill.name })}
          >
            👍
          </button>
          <button
            type="button"
            className="skill-badge__vote"
            onClick={() => vote('negative')}
            disabled={busy}
            title={t('skillBadge.unhelpful')}
            aria-label={t('skillBadge.markUnhelpful', { name: skill.name })}
          >
            👎
          </button>
        </>
      )}
    </span>
  );
}
