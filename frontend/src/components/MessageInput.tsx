import { useRef, useState, type DragEvent, type ClipboardEvent } from 'react';

import { useI18n } from '../i18n';
import SendButton from './SendButton';
import {
  CHAT_ACCEPT,
  MAX_CHAT_FILE_BYTES,
  MAX_CHAT_FILES,
} from '../lib/chatAttachments';
import type { ProviderView } from '../api/types';

interface MessageInputProps {
  onSend: (message: string, files?: File[]) => void;
  disabled?: boolean;
  placeholder?: string;
  hint?: string;
  providers?: ProviderView[];
  providerId?: string;
  onProviderIdChange?: (id: string) => void;
}

type PendingFile = {
  id: string;
  file: File;
  preview?: string;
};

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function MessageInput({
  onSend,
  disabled,
  placeholder,
  hint,
  providers,
  providerId,
  onProviderIdChange,
}: MessageInputProps) {
  const { t } = useI18n();
  const [value, setValue] = useState('');
  const [files, setFiles] = useState<PendingFile[]>([]);
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function revoke(previews: PendingFile[]) {
    for (const item of previews) {
      if (item.preview) URL.revokeObjectURL(item.preview);
    }
  }

  function addFiles(incoming: File[]) {
    setLocalError(null);
    if (!incoming.length) return;

    setFiles((prev) => {
      const next = [...prev];
      for (const file of incoming) {
        if (next.length >= MAX_CHAT_FILES) {
          setLocalError(t('chat.tooManyFiles', { max: MAX_CHAT_FILES }));
          break;
        }
        if (file.size > MAX_CHAT_FILE_BYTES) {
          setLocalError(
            t('chat.fileTooLarge', {
              name: file.name,
              max: MAX_CHAT_FILE_BYTES / (1024 * 1024),
            }),
          );
          continue;
        }
        const duplicate = next.some(
          (item) => item.file.name === file.name && item.file.size === file.size,
        );
        if (duplicate) continue;
        const preview = file.type.startsWith('image/')
          ? URL.createObjectURL(file)
          : undefined;
        next.push({
          id: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`,
          file,
          preview,
        });
      }
      return next;
    });
  }

  function removeFile(id: string) {
    setFiles((prev) => {
      const target = prev.find((item) => item.id === id);
      if (target?.preview) URL.revokeObjectURL(target.preview);
      return prev.filter((item) => item.id !== id);
    });
  }

  function submit() {
    const trimmed = value.trim();
    if (disabled) return;
    if (!trimmed && files.length === 0) return;
    onSend(
      trimmed,
      files.length ? files.map((item) => item.file) : undefined,
    );
    setValue('');
    revoke(files);
    setFiles([]);
    setLocalError(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function handleChange(event: React.ChangeEvent<HTMLTextAreaElement>) {
    setValue(event.target.value);
    const el = event.target;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    addFiles(Array.from(event.dataTransfer.files || []));
  }

  function handlePaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const pasted = Array.from(event.clipboardData?.files || []);
    if (!pasted.length) return;
    event.preventDefault();
    addFiles(pasted);
  }

  const canSend = !disabled && Boolean(value.trim() || files.length);
  const hintText = hint ?? t('chat.composerHint');

  return (
    <div
      className={`chat__composer${dragging ? ' chat__composer--drop' : ''}`}
      onDragEnter={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={(event) => {
        if (event.currentTarget.contains(event.relatedTarget as Node)) return;
        setDragging(false);
      }}
      onDrop={handleDrop}
    >
      <div className={`composer__box${dragging ? ' composer__box--drop' : ''}`}>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept={CHAT_ACCEPT}
          hidden
          disabled={disabled}
          onChange={(event) => {
            addFiles(Array.from(event.target.files || []));
            event.target.value = '';
          }}
        />
        {files.length > 0 && (
          <ul className="composer__chips" aria-label={t('chat.attachAria')}>
            {files.map((item) => (
              <li key={item.id} className="composer__chip">
                {item.preview ? (
                  <img src={item.preview} alt="" className="composer__chip-thumb" />
                ) : (
                  <span className="composer__chip-icon" aria-hidden="true">
                    📎
                  </span>
                )}
                <span className="composer__chip-meta">
                  <span className="composer__chip-name" title={item.file.name}>
                    {item.file.name}
                  </span>
                  <span className="composer__chip-size">
                    {formatSize(item.file.size)}
                  </span>
                </span>
                <button
                  type="button"
                  className="composer__chip-remove"
                  onClick={() => removeFile(item.id)}
                  aria-label={t('chat.removeFile', { name: item.file.name })}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={placeholder ?? t('chat.inputPlaceholder')}
          rows={1}
          disabled={disabled}
          aria-label={t('chat.inputAria')}
        />
        <div className="composer__bar">
          <div className="composer__tools">
            <button
              type="button"
              className="composer__icon"
              onClick={() => fileRef.current?.click()}
              disabled={disabled}
              title={t('chat.attach')}
              aria-label={t('chat.attachAria')}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
              </svg>
            </button>
            {providers && providers.length > 0 && onProviderIdChange ? (
              <select
                className="composer__model"
                value={providerId ?? ''}
                disabled={disabled}
                title={t('chat.followDefaultHint')}
                aria-label={t('chat.modelPickerAria')}
                onChange={(event) => onProviderIdChange(event.target.value)}
              >
                <option value="">{t('chat.followDefault')}</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            ) : null}
            <p className="composer__hint" title={hintText}>
              {hintText}
            </p>
          </div>
          <SendButton
            ready={canSend}
            disabled={disabled}
            label={t('chat.send')}
            onClick={submit}
          />
        </div>
      </div>
      {localError && <p className="composer__error">{localError}</p>}
    </div>
  );
}
