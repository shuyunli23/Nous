import { useEffect, useState } from 'react';

import type {
  SkillCreatePayload,
  SkillDetail,
  WorkflowStep,
} from '../api/types';
import { useI18n } from '../i18n';

interface SkillEditorProps {
  skill: SkillDetail | null;
  open: boolean;
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSave: (payload: SkillCreatePayload) => void;
}

function workflowToText(workflow: WorkflowStep[]): string {
  return workflow
    .map((step) => {
      const action = step.action ?? '';
      return step.command ? `${action} | ${step.command}` : action;
    })
    .filter(Boolean)
    .join('\n');
}

function textToWorkflow(text: string): WorkflowStep[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [action, command] = line.split('|').map((part) => part.trim());
      const step: WorkflowStep = { step: index + 1, action: action ?? line };
      if (command) step.command = command;
      return step;
    });
}

export default function SkillEditor({
  skill,
  open,
  saving,
  error,
  onClose,
  onSave,
}: SkillEditorProps) {
  const { t } = useI18n();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [instruction, setInstruction] = useState('');
  const [keywords, setKeywords] = useState('');
  const [intent, setIntent] = useState('');
  const [workflowText, setWorkflowText] = useState('');

  useEffect(() => {
    if (!open) return;
    setName(skill?.name ?? '');
    setDescription(skill?.description ?? '');
    setInstruction(skill?.instruction ?? '');
    setKeywords((skill?.trigger_keywords ?? []).join(', '));
    setIntent(skill?.trigger_intent ?? '');
    setWorkflowText(workflowToText(skill?.workflow ?? []));
  }, [open, skill]);

  if (!open) return null;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    onSave({
      name: name.trim(),
      description: description.trim(),
      instruction: instruction.trim(),
      trigger_keywords: keywords
        .split(',')
        .map((k) => k.trim())
        .filter(Boolean),
      trigger_intent: intent.trim() || null,
      workflow: textToWorkflow(workflowText),
    });
  }

  return (
    <div
      className="modal__backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="skill-editor-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <form className="modal" onSubmit={handleSubmit}>
        <div className="modal__header">
          <h2 className="modal__title" id="skill-editor-title">
            {skill
              ? t('skillEditor.editTitle', { version: skill.version })
              : t('skillEditor.createTitle')}
          </h2>
          <button
            type="button"
            className="close-btn"
            onClick={onClose}
            aria-label={t('common.close')}
          >
            ×
          </button>
        </div>

        <div className="modal__body stack">
          {error && <div className="alert alert--error">{error}</div>}

          <div className="field">
            <label htmlFor="skill-name">{t('skillEditor.name')}</label>
            <input
              id="skill-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('skillEditor.namePlaceholder')}
              required
              maxLength={200}
            />
          </div>

          <div className="field">
            <label htmlFor="skill-desc">{t('skillEditor.description')}</label>
            <textarea
              id="skill-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder={t('skillEditor.descriptionPlaceholder')}
            />
          </div>

          <div className="field">
            <label htmlFor="skill-keywords">{t('skillEditor.keywords')}</label>
            <input
              id="skill-keywords"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="ssh timeout, gitlab ssh, port 22"
            />
            <p className="field__hint">{t('skillEditor.keywordsHint')}</p>
          </div>

          <div className="field">
            <label htmlFor="skill-intent">{t('skillEditor.intent')}</label>
            <input
              id="skill-intent"
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder={t('skillEditor.intentPlaceholder')}
            />
          </div>

          <div className="field">
            <label htmlFor="skill-workflow">{t('skillEditor.workflow')}</label>
            <textarea
              id="skill-workflow"
              value={workflowText}
              onChange={(e) => setWorkflowText(e.target.value)}
              rows={6}
              placeholder={t('skillEditor.workflowPlaceholder')}
              style={{ fontFamily: 'var(--mono)', fontSize: 12.5 }}
            />
            <p className="field__hint">{t('skillEditor.workflowHint')}</p>
          </div>

          <div className="field">
            <label htmlFor="skill-instruction">
              {t('skillEditor.instruction')}
            </label>
            <textarea
              id="skill-instruction"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              rows={3}
              placeholder={t('skillEditor.instructionPlaceholder')}
            />
          </div>
        </div>

        <div className="modal__footer">
          <button type="button" className="btn" onClick={onClose}>
            {t('common.cancel')}
          </button>
          <button
            type="submit"
            className="btn btn--primary"
            disabled={saving || !name.trim()}
          >
            {saving
              ? t('common.saving')
              : skill
                ? t('skillEditor.saveBump')
                : t('common.create')}
          </button>
        </div>
      </form>
    </div>
  );
}
