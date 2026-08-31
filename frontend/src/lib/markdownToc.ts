import GithubSlugger from 'github-slugger';

export interface TocEntry {
  id: string;
  text: string;
  level: number;
}

const FENCE = /^ {0,3}(`{3,}|~{3,})/;
const ATX = /^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$/;
const SETEXT = /^(=+|-+)[ \t]*$/;

function visibleHeadingText(raw: string): string {
  return raw
    .replace(/\\([\\`*_{}[\]()#+.!-])/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/[*_~`]+/g, '')
    .replace(/\{#[\w.-]+\}/g, '')
    .trim();
}

/** Headings + github-slugger ids, matching `rehype-slug` on the rendered article. */
export function extractMarkdownToc(markdown: string): TocEntry[] {
  const slugger = new GithubSlugger();
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const entries: TocEntry[] = [];
  let fence: string | null = null;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] ?? '';
    const fenceOpen = FENCE.exec(line);
    if (fenceOpen) {
      const mark = fenceOpen[1]?.[0];
      if (!mark) continue;
      if (!fence) {
        fence = mark;
      } else if (mark === fence) {
        fence = null;
      }
      continue;
    }
    if (fence) continue;

    const atx = ATX.exec(line);
    if (atx) {
      const marks = atx[1];
      const raw = atx[2];
      if (!marks || !raw) continue;
      const text = visibleHeadingText(raw);
      if (!text) continue;
      const id = slugger.slug(text);
      if (!id) continue;
      entries.push({
        level: marks.length,
        text,
        id,
      });
      continue;
    }

    const next = lines[i + 1] ?? '';
    if (SETEXT.test(next) && line.trim() && !line.startsWith(' ')) {
      const text = visibleHeadingText(line);
      if (text) {
        const id = slugger.slug(text);
        if (id) {
          entries.push({
            level: next.trim().startsWith('=') ? 1 : 2,
            text,
            id,
          });
        }
      }
      i += 1;
    }
  }

  return entries;
}
