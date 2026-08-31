import { useI18n } from '../i18n';
import { unwrapMarkdownImages } from '../lib/chatAttachments';
import {
  isExportImage,
  isExportSvg,
  normalizeExportHref,
} from '../lib/exportLinks';

const FILE_URL_PATTERN =
  /(https?:\/\/(?:127\.0\.0\.1|localhost)(?::\d+)?\/api\/v1\/files\/(?:exports|uploads)\/[^\s<>"']+|https?:\/\/[^\s<>"']+|\/api\/v1\/files\/(?:exports|uploads)\/[^\s<>"']+)/g;

export function renderPlainContent(
  text: string,
  downloadFile: string,
  viewOriginal: string,
) {
  const pattern = FILE_URL_PATTERN;
  const parts = unwrapMarkdownImages(text).split(pattern);
  const shown = new Set<string>();
  return parts.map((part, index) => {
    if (!part) return null;
    const normalized = normalizeExportHref(part) || part;
    const isPath =
      normalized.startsWith('/api/v1/files/exports/') ||
      normalized.startsWith('/api/v1/files/uploads/');
    const isUrl = /^https?:\/\//.test(normalized);
    if (!isPath && !isUrl) return <span key={index}>{part}</span>;
    if (isExportImage(normalized) || isExportSvg(normalized)) {
      if (shown.has(normalized)) return null;
      shown.add(normalized);
      return (
        <span key={index} className="msg__media">
          <a
            href={normalized}
            target="_blank"
            rel="noreferrer"
            className="msg__link"
          >
            {viewOriginal}
          </a>
          <img src={normalized} alt="" className="msg__image" />
        </span>
      );
    }
    return (
      <a
        key={index}
        href={normalized}
        target="_blank"
        rel="noreferrer"
        className="msg__link"
      >
        {isPath ? downloadFile : part}
      </a>
    );
  });
}

export function UserAttachmentDump({ dump }: { dump: string }) {
  const { t } = useI18n();
  return (
    <details className="msg__attach">
      <summary>{t('chat.parsedAttachments')}</summary>
      <pre className="msg__attach-dump">{dump}</pre>
    </details>
  );
}
