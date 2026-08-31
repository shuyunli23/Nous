import { useEffect } from 'react';

import type { ChatMode } from '../api/types';
import { useI18n } from '../i18n';
import OptionToggle from './OptionToggle';

interface NewChatDialogProps {
  modes: ChatMode[];
  selectedId: string | null;
  knowledgeOn: boolean;
  onSelect: (id: string) => void;
  onKnowledge: (on: boolean) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function NewChatDialog({
  modes,
  selectedId,
  knowledgeOn,
  onSelect,
  onKnowledge,
  onConfirm,
  onCancel,
}: NewChatDialogProps) {
  const { t } = useI18n();
  const selected = modes.find((mode) => mode.id === selectedId) ?? null;
  const canUseKnowledge =
    selected?.key === 'tutor' || selected?.key === 'companion';

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onCancel]);

  return (
    <div
      className="modal__backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-chat-title"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div className="modal modal--narrow">
        <div className="modal__header">
          <h2 className="modal__title" id="new-chat-title">
            {t('chat.newChatTitle')}
          </h2>
          <button
            type="button"
            className="close-btn"
            onClick={onCancel}
            aria-label={t('common.close')}
          >
            ×
          </button>
        </div>
        <div className="modal__body">
          <p className="mode-pick__lead">{t('chat.newChatLead')}</p>
          <div className="mode-pick" role="listbox" aria-label={t('chat.modePickerAria')}>
            {modes.map((mode) => {
              const active = mode.id === selectedId;
              return (
                <button
                  key={mode.id}
                  type="button"
                  role="option"
                  aria-selected={active}
                  className={
                    active
                      ? 'mode-pick__card mode-pick__card--active'
                      : 'mode-pick__card'
                  }
                  onClick={() => onSelect(mode.id)}
                >
                  <span className="mode-pick__name">{mode.name}</span>
                  {mode.description ? (
                    <span className="mode-pick__desc">{mode.description}</span>
                  ) : null}
                </button>
              );
            })}
          </div>
          {canUseKnowledge && (
            <OptionToggle
              checked={knowledgeOn}
              title={t('chat.knowledgeMemory')}
              hint={t('chat.knowledgeMemoryHint')}
              onChange={onKnowledge}
            />
          )}
        </div>
        <div className="modal__footer">
          <button type="button" className="btn" onClick={onCancel}>
            {t('common.cancel')}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!selectedId}
            onClick={onConfirm}
          >
            {t('chat.newChatConfirm')}
          </button>
        </div>
      </div>
    </div>
  );
}
