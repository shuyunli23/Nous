export const ATTACH_START = '<!--nous-attachments-->';
export const ATTACH_END = '<!--/nous-attachments-->';

export const CHAT_ACCEPT =
  '.txt,.md,.csv,.json,.log,.xml,.html,.htm,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.xlsm,.png,.jpg,.jpeg,.webp,.gif,.bmp';

export const MAX_CHAT_FILES = 8;
export const MAX_CHAT_FILE_BYTES = 100 * 1024 * 1024;

export function splitUserAttachments(text: string): {
  visible: string;
  dump: string | null;
  after: string;
} {
  const start = text.indexOf(ATTACH_START);
  if (start < 0) {
    return { visible: text, dump: null, after: '' };
  }
  const visible = text.slice(0, start).trim();
  const rest = text.slice(start + ATTACH_START.length);
  const end = rest.indexOf(ATTACH_END);
  if (end < 0) {
    return { visible, dump: rest.trim(), after: '' };
  }
  return {
    visible,
    dump: rest.slice(0, end).trim(),
    after: rest.slice(end + ATTACH_END.length).trim(),
  };
}

/** Turn markdown images into bare URLs so plain-content rendering can show them. */
export function unwrapMarkdownImages(text: string): string {
  return text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '$2');
}
