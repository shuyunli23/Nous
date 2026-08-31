/** Normalize export / upload download hrefs so chat links hit the current origin. */

const LOCAL_FILE =
  /^https?:\/\/(?:127\.0\.0\.1|localhost)(?::\d+)?(\/api\/v1\/files\/(?:exports|uploads)\/[^?#\s]+)/i;

export function normalizeExportHref(href: string | undefined | null): string | undefined {
  if (!href) return undefined;
  const trimmed = href.trim();
  const local = LOCAL_FILE.exec(trimmed);
  if (local) return local[1];
  if (
    trimmed.startsWith('/api/v1/files/exports/') ||
    trimmed.startsWith('/api/v1/files/uploads/')
  ) {
    return trimmed;
  }
  return trimmed;
}

export function isExportPath(href: string | undefined | null): boolean {
  const normalized = normalizeExportHref(href);
  return Boolean(
    normalized?.startsWith('/api/v1/files/exports/') ||
      normalized?.startsWith('/api/v1/files/uploads/'),
  );
}

export function isExportImage(href: string | undefined | null): boolean {
  const normalized = normalizeExportHref(href);
  if (!normalized || !isExportPath(normalized)) return false;
  return /\.(png|jpe?g|webp|gif|bmp)(\?|$)/i.test(normalized);
}

export function isExportHtml(href: string | undefined | null): boolean {
  const normalized = normalizeExportHref(href);
  if (!normalized || !isExportPath(normalized)) return false;
  return /\.html?(\?|$)/i.test(normalized);
}

export function isExportSvg(href: string | undefined | null): boolean {
  const normalized = normalizeExportHref(href);
  if (!normalized || !isExportPath(normalized)) return false;
  return /\.svg(\?|$)/i.test(normalized);
}

/** True when the markdown already has `![...](href)` for this file. */
export function markdownHasImageEmbed(
  content: string,
  href: string | undefined | null,
): boolean {
  const normalized = normalizeExportHref(href);
  if (!normalized || !content) return false;
  const escaped = normalized.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`!\\[[^\\]]*\\]\\(${escaped}\\)`).test(content);
}
