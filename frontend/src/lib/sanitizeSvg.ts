const SVG_TAGS = new Set([
  'svg',
  'g',
  'path',
  'circle',
  'ellipse',
  'rect',
  'line',
  'polyline',
  'polygon',
  'text',
  'tspan',
  'textpath',
  'defs',
  'marker',
  'clippath',
  'mask',
  'lineargradient',
  'radialgradient',
  'stop',
  'use',
  'symbol',
  'title',
  'desc',
  'pattern',
  'filter',
  'fegaussianblur',
  'feoffset',
  'feblend',
  'fecolormatrix',
  'femerge',
  'femergenode',
  'feflood',
  'fecomposite',
  'femorphology',
  'fedropshadow',
  'image',
  'switch',
  'style',
]);

const SVG_ATTR = new Set([
  'viewbox',
  'xmlns',
  'xmlns:xlink',
  'width',
  'height',
  'fill',
  'stroke',
  'stroke-width',
  'stroke-linecap',
  'stroke-linejoin',
  'stroke-dasharray',
  'stroke-dashoffset',
  'stroke-opacity',
  'stroke-miterlimit',
  'fill-opacity',
  'fill-rule',
  'opacity',
  'transform',
  'd',
  'cx',
  'cy',
  'r',
  'rx',
  'ry',
  'x',
  'y',
  'x1',
  'y1',
  'x2',
  'y2',
  'points',
  'offset',
  'stop-color',
  'stop-opacity',
  'gradientunits',
  'gradienttransform',
  'spreadmethod',
  'marker-start',
  'marker-mid',
  'marker-end',
  'markerwidth',
  'markerheight',
  'refx',
  'refy',
  'orient',
  'markerunits',
  'id',
  'class',
  'style',
  'clip-path',
  'clippathunits',
  'mask',
  'filter',
  'filterunits',
  'primitiveunits',
  'stddeviation',
  'in',
  'in2',
  'result',
  'mode',
  'type',
  'values',
  'font-size',
  'font-family',
  'font-weight',
  'text-anchor',
  'dominant-baseline',
  'alignment-baseline',
  'dx',
  'dy',
  'preserveaspectratio',
  'overflow',
  'vector-effect',
  'href',
  'xlink:href',
  'role',
  'aria-hidden',
  'focusable',
  'xmlns:svg',
  'startoffset',
  'lengthadjust',
  'textlength',
]);

function stripSvgPreamble(text: string): string {
  return text
    .replace(/^\uFEFF/, '')
    .trim()
    .replace(/^<\?xml\b[\s\S]*?\?>\s*/i, '')
    .replace(/^<!DOCTYPE\b[\s\S]*?>\s*/i, '')
    .replace(/^(?:<!--[\s\S]*?-->\s*)+/i, '')
    .trim();
}

/** Complete `<svg>…</svg>` document, ignoring XML prolog / doctype / comments. */
export function isolateSvg(input: string): string | null {
  const text = stripSvgPreamble(input);
  const start = text.search(/<svg[\s>/]/i);
  if (start < 0) return null;
  const close = /<\/svg\s*>/i.exec(text);
  if (close && close.index >= start) {
    return text.slice(start, close.index + close[0].length);
  }
  const self = text.slice(start).match(/^<svg\b[^>]*\/>/i);
  return self ? self[0] : null;
}

function isSafeUrl(value: string): boolean {
  const v = value.trim();
  if (!v || v.startsWith('#')) return true;
  return /^(https?:|data:image\/)/i.test(v);
}

function numericLength(value: string | null): number | null {
  if (!value) return null;
  const match = /^(\d+(?:\.\d+)?)(?:px)?$/i.exec(value.trim());
  if (!match) return null;
  const n = Number(match[1]);
  return n > 0 ? n : null;
}

function ensureViewBox(root: Element) {
  if (root.getAttribute('viewBox') || root.getAttribute('viewbox')) return;
  const w = numericLength(root.getAttribute('width'));
  const h = numericLength(root.getAttribute('height'));
  if (w && h) root.setAttribute('viewBox', `0 0 ${w} ${h}`);
}

function scrub(el: Element) {
  const tag = el.tagName.toLowerCase();
  if (tag.includes(':') && !tag.startsWith('fe') && tag !== 'clippath') {
    el.remove();
    return;
  }
  if (!SVG_TAGS.has(tag)) {
    el.remove();
    return;
  }
  for (const attr of [...el.attributes]) {
    const name = attr.name.toLowerCase();
    if (name.startsWith('on') || !SVG_ATTR.has(name)) {
      el.removeAttribute(attr.name);
      continue;
    }
    if ((name === 'href' || name === 'xlink:href') && !isSafeUrl(attr.value)) {
      el.removeAttribute(attr.name);
    }
    if (name === 'style' && /expression|javascript:/i.test(attr.value)) {
      el.removeAttribute(attr.name);
    }
  }
  if (tag === 'style' && /expression|javascript:/i.test(el.textContent || '')) {
    el.textContent = '';
  }
  for (const child of [...el.children]) scrub(child);
}

/** Keep diagram SVGs, drop scripts and foreign content. */
export function sanitizeSvg(input: string): string | null {
  const trimmed = isolateSvg(input);
  if (!trimmed) return null;
  const xml = new DOMParser().parseFromString(trimmed, 'image/svg+xml');
  const xmlBroken = Boolean(
    xml.querySelector('parsererror') ||
      xml.getElementsByTagName('parsererror').length,
  );
  let root: Element | null = null;
  if (!xmlBroken && xml.documentElement.tagName.toLowerCase() === 'svg') {
    root = xml.documentElement;
  } else {
    root = new DOMParser()
      .parseFromString(trimmed, 'text/html')
      .querySelector('svg');
  }
  if (!root) return null;
  scrub(root);
  if (!root.getAttribute('xmlns')) {
    root.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  }
  ensureViewBox(root);
  const serialized = new XMLSerializer().serializeToString(root);
  if (!hasDrawableSvg(serialized)) {
    return lightCleanSvg(trimmed);
  }
  return serialized;
}

function hasDrawableSvg(markup: string): boolean {
  return /<(rect|path|circle|ellipse|line|polyline|polygon|text|tspan|textpath|image|use|g)\b/i.test(
    markup,
  );
}

/** Prefer a sanitized tree; if that empties the diagram, keep a script-stripped copy. */
export function renderableSvg(input: string): string | null {
  return sanitizeSvg(input) || lightCleanSvg(input);
}

export function looksLikeSvg(text: string): boolean {
  return /^<svg[\s>/]/i.test(stripSvgPreamble(text));
}

export function isCompleteSvg(text: string): boolean {
  return isolateSvg(text) != null;
}

const SVG_MARKER = '%%NOUS_SVG_';

export function lightCleanSvg(input: string): string | null {
  const trimmed = isolateSvg(input);
  if (!trimmed) return null;
  const cleaned = trimmed
    .replace(/<script\b[\s\S]*?<\/script>/gi, '')
    .replace(/<foreignObject\b[\s\S]*?<\/foreignObject\s*>/gi, '')
    .replace(/\son[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '');
  return cleaned;
}

function unescapeIfNeeded(block: string): string {
  if (!/&lt;\/?svg\b/i.test(block) && !/&lt;(rect|path|text|g|line)\b/i.test(block)) {
    return block;
  }
  return block
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'");
}

const SVG_BLOCK =
  /(?:<\?xml\b[\s\S]*?\?>\s*)?(?:<!DOCTYPE\b[\s\S]*?>\s*)?<svg\b[\s\S]*?<\/svg\s*>/gi;

function takeSvgs(chunk: string, svgs: string[]): string {
  return chunk.replace(SVG_BLOCK, (block) => {
    const index = svgs.length;
    svgs.push(unescapeIfNeeded(block));
    return `\n\n${SVG_MARKER}${index}%%\n\n`;
  });
}

function fenceHoldsSvg(lang: string, body: string): boolean {
  if (!/<svg\b/i.test(body)) return false;
  if (lang === 'svg' || lang === 'xml') return true;
  if (lang === 'html' || lang === '') return looksLikeSvg(body);
  return looksLikeSvg(body);
}

/** Pull complete SVG blocks out of markdown so CommonMark blank lines cannot split them. */
export function hoistInlineSvgs(markdown: string): { text: string; svgs: string[] } {
  const svgs: string[] = [];
  const source = markdown
    .replace(/&lt;svg\b/gi, '<svg')
    .replace(/&lt;\/svg&gt;/gi, '</svg>');
  const fence =
    /(^|\n)(```|~~~)([^\n]*)\n([\s\S]*?)\n\2[ \t]*(?=\n|$)/g;
  let last = 0;
  let out = '';
  let match: RegExpExecArray | null;
  while ((match = fence.exec(source))) {
    out += takeSvgs(source.slice(last, match.index), svgs);
    const lang = (match[3] || '').trim().split(/\s+/)[0]?.toLowerCase() ?? '';
    const body = match[4] || '';
    if (fenceHoldsSvg(lang, body)) {
      out += takeSvgs(body, svgs);
    } else {
      out += match[0];
    }
    last = match.index + match[0].length;
  }
  out += takeSvgs(source.slice(last), svgs);
  return { text: out, svgs };
}

export const SVG_CHUNK = /%%NOUS_SVG_(\d+)%%/g;
