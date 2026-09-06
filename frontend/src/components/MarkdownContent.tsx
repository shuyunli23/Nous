import { Component, useEffect, useState, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import rehypeSlug from 'rehype-slug';
import type { PluggableList } from 'unified';
import 'katex/dist/katex.min.css';

import type { ExecutionStep } from '../api/types';
import { useI18n } from '../i18n';
import {
  hoistInlineSvgs,
  isCompleteSvg,
  looksLikeSvg,
  renderableSvg,
} from '../lib/sanitizeSvg';
import {
  isExportHtml,
  isExportImage,
  isExportPath,
  isExportSvg,
  markdownHasImageEmbed,
  normalizeExportHref,
} from '../lib/exportLinks';

interface MarkdownContentProps {
  content: string;
  executionTrace?: ExecutionStep[] | null;
  className?: string;
  /** Notes only: render inline HTML. SVG already renders in chat. */
  allowHtml?: boolean;
}

const SVG_TAGS = [
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
  'defs',
  'marker',
  'clipPath',
  'mask',
  'linearGradient',
  'radialGradient',
  'stop',
  'use',
  'symbol',
  'title',
  'desc',
  'pattern',
  'filter',
  'feGaussianBlur',
  'feOffset',
  'feBlend',
  'feColorMatrix',
  'feMerge',
  'feMergeNode',
  'feFlood',
  'feComposite',
  'feMorphology',
  'feDropShadow',
  'image',
  'switch',
  'style',
];

const SVG_ATTRS = [
  'viewBox',
  'xmlns',
  'width',
  'height',
  'fill',
  'stroke',
  'stroke-width',
  'stroke-linecap',
  'stroke-linejoin',
  'stroke-dasharray',
  'stroke-opacity',
  'fill-opacity',
  'fill-rule',
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
  'transform',
  'opacity',
  'id',
  'className',
  'class',
  'style',
  'href',
  'xlink:href',
  'preserveAspectRatio',
  'marker-start',
  'marker-mid',
  'marker-end',
  'markerWidth',
  'markerHeight',
  'refX',
  'refY',
  'orient',
  'offset',
  'stop-color',
  'stop-opacity',
  'gradientUnits',
  'clip-path',
  'mask',
  'filter',
  'font-size',
  'font-family',
  'text-anchor',
  'stdDeviation',
  'in',
  'result',
];

const knowledgeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), ...SVG_TAGS],
  attributes: {
    ...defaultSchema.attributes,
    '*': [...(defaultSchema.attributes?.['*'] ?? []), 'className', 'id', 'style'],
    ...Object.fromEntries(SVG_TAGS.map((tag) => [tag, SVG_ATTRS])),
  },
};

function flattenText(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(flattenText).join('');
  if (typeof node === 'object' && 'props' in node) {
    const el = node as { props?: { children?: ReactNode } };
    return flattenText(el.props?.children);
  }
  return '';
}

function PreviewSourceTabs({
  mode,
  onChange,
}: {
  mode: 'preview' | 'source';
  onChange: (mode: 'preview' | 'source') => void;
}) {
  const { t } = useI18n();
  return (
    <span className="msg__webpage-modes" role="tablist">
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'preview'}
        className={
          mode === 'preview'
            ? 'msg__webpage-mode msg__webpage-mode--on'
            : 'msg__webpage-mode'
        }
        onClick={() => onChange('preview')}
      >
        {t('chat.webpagePreviewTab')}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'source'}
        className={
          mode === 'source'
            ? 'msg__webpage-mode msg__webpage-mode--on'
            : 'msg__webpage-mode'
        }
        onClick={() => onChange('source')}
      >
        {t('chat.webpageSourceTab')}
      </button>
    </span>
  );
}

function SvgFigure({ markup }: { markup: string }) {
  return (
    <div className="md-svg" dangerouslySetInnerHTML={{ __html: markup }} />
  );
}

function SvgBlock({
  markup,
  source,
  preferSource = false,
}: {
  markup: string;
  source?: string;
  preferSource?: boolean;
}) {
  const { t } = useI18n();
  const srcText = source || markup;
  const [mode, setMode] = useState<'preview' | 'source'>(
    preferSource ? 'source' : 'preview',
  );
  const [copied, setCopied] = useState(false);

  async function copySource() {
    try {
      await navigator.clipboard.writeText(srcText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  }

  return (
    <span className="msg__webpage">
      <span className="msg__webpage-bar">
        <PreviewSourceTabs mode={mode} onChange={setMode} />
      </span>
      {mode === 'preview' ? (
        <div className="msg__svg-preview">
          <SvgFigure markup={markup} />
        </div>
      ) : (
        <div className="msg__html-source">
          <div className="md-code__header">
            <span className="md-code__lang">svg</span>
            <button
              type="button"
              className={`md-code__copy${copied ? ' md-code__copy--done' : ''}`}
              onClick={() => void copySource()}
            >
              {copied ? t('common.copied') : t('chat.copySource')}
            </button>
          </div>
          <pre className="msg__html-source-pre">
            <code>{srcText}</code>
          </pre>
        </div>
      )}
    </span>
  );
}

function CodeBlock({
  className,
  children,
  preferSource = false,
}: {
  className?: string;
  children: ReactNode;
  preferSource?: boolean;
}) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const match = /language-([\w-]+)/.exec(className || '');
  const lang = match?.[1] || 'text';
  const text = flattenText(children).replace(/\n$/, '');
  if (looksLikeSvg(text) && isCompleteSvg(text)) {
    const safe = renderableSvg(text);
    if (safe) {
      return (
        <SvgBlock markup={safe} source={text} preferSource={preferSource} />
      );
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="md-code">
      <div className="md-code__header">
        <span className="md-code__lang">{lang}</span>
        <button
          type="button"
          className={`md-code__copy${copied ? ' md-code__copy--done' : ''}`}
          onClick={() => void copy()}
        >
          {copied ? t('common.copied') : t('common.copy')}
        </button>
      </div>
      <pre className="md-code__pre">
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

function exportUrlsFromTrace(
  steps: ExecutionStep[] | null | undefined,
  suffix: RegExp,
): string[] {
  if (!steps?.length) return [];
  const urls: string[] = [];
  for (const step of steps) {
    if (step.kind !== 'tool' || step.status === 'error') continue;
    const detail = step.detail || '';
    const found = detail.match(/\/api\/v1\/files\/exports\/[^\s)\]"']+/gi);
    if (found) urls.push(...found.filter((url) => suffix.test(url)));
  }
  return urls;
}

async function urlExists(href: string): Promise<boolean> {
  try {
    const head = await fetch(href, { method: 'HEAD' });
    if (head.ok) return true;
    if (head.status !== 405 && head.status !== 501) return false;
    const get = await fetch(href, { method: 'GET' });
    return get.ok;
  } catch {
    return false;
  }
}

function WebpageEmbed({
  href,
  traceUrls,
  preferSource = false,
  kind = 'html',
}: {
  href: string;
  traceUrls: string[];
  preferSource?: boolean;
  kind?: 'html' | 'svg';
}) {
  const { t } = useI18n();
  const isSvg = kind === 'svg';
  const [src, setSrc] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const [mode, setMode] = useState<'preview' | 'source'>(
    preferSource ? 'source' : 'preview',
  );
  const [source, setSource] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const candidates = [href, ...traceUrls].filter(
      (url, index, all) => url && all.indexOf(url) === index,
    );
    void (async () => {
      setSrc(null);
      setMissing(false);
      setSource(null);
      setSourceError(false);
      for (const url of candidates) {
        if (await urlExists(url)) {
          if (!cancelled) setSrc(url);
          return;
        }
      }
      if (!cancelled) setMissing(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [href, traceUrls.join('|')]);

  useEffect(() => {
    const needSource = isSvg || mode === 'source';
    if (!src || !needSource || source != null || sourceError) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(src);
        if (!res.ok) throw new Error(String(res.status));
        const text = await res.text();
        if (!cancelled) setSource(text);
      } catch {
        if (!cancelled) setSourceError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [src, mode, source, sourceError, isSvg]);

  async function copySource() {
    if (!source) return;
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  }

  if (missing) {
    return (
      <p className="msg__webpage-missing">
        {isSvg ? t('chat.svgMissing') : t('chat.webpageMissing')}
      </p>
    );
  }
  if (!src) {
    return <p className="msg__webpage-missing">{t('chat.webpageChecking')}</p>;
  }
  const svgMarkup = isSvg && source ? renderableSvg(source) : null;
  return (
    <span className="msg__webpage">
      <span className="msg__webpage-bar">
        <a
          href={src}
          target="_blank"
          rel="noreferrer"
          className="msg__webpage-cta"
        >
          {isSvg ? t('chat.openSvg') : t('chat.openWebpage')}
        </a>
        <PreviewSourceTabs mode={mode} onChange={setMode} />
      </span>
      {mode === 'preview' ? (
        isSvg ? (
          sourceError ? (
            <p className="msg__webpage-missing">{t('chat.webpageSourceFailed')}</p>
          ) : source == null ? (
            <p className="msg__webpage-missing">{t('chat.webpageSourceLoading')}</p>
          ) : svgMarkup ? (
            <div className="msg__svg-preview">
              <SvgFigure markup={svgMarkup} />
            </div>
          ) : (
            <iframe
              className="msg__html-preview"
              src={src}
              title={t('chat.svgPreview')}
            />
          )
        ) : (
          <iframe
            className="msg__html-preview"
            src={src}
            title={t('chat.webpagePreview')}
          />
        )
      ) : (
        <div className="msg__html-source">
          <div className="md-code__header">
            <span className="md-code__lang">{isSvg ? 'svg' : 'html'}</span>
            <button
              type="button"
              className={`md-code__copy${copied ? ' md-code__copy--done' : ''}`}
              onClick={() => void copySource()}
              disabled={!source}
            >
              {copied ? t('common.copied') : t('chat.copySource')}
            </button>
          </div>
          {sourceError ? (
            <p className="msg__webpage-missing">{t('chat.webpageSourceFailed')}</p>
          ) : source == null ? (
            <p className="msg__webpage-missing">{t('chat.webpageSourceLoading')}</p>
          ) : (
            <pre className="msg__html-source-pre">
              <code>{source}</code>
            </pre>
          )}
        </div>
      )}
    </span>
  );
}

class MarkdownRenderGuard extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

/** Assistant / knowledge body: GFM + math + highlighted fenced code + export media. */
export default function MarkdownContent({
  content,
  executionTrace,
  className,
  allowHtml = false,
}: MarkdownContentProps) {
  const { t } = useI18n();
  const prepared = hoistInlineSvgs(content);
  const markdown = prepared.text;
  const hoistedSvgs = prepared.svgs;
  const traceHtml = exportUrlsFromTrace(executionTrace, /\.html?(\?|$)/i);
  const traceSvg = exportUrlsFromTrace(executionTrace, /\.svg(\?|$)/i);
  const preferSource = /源码|源代码|source code|html\s*代码|svg\s*代码/i.test(
    content,
  );

  function exportImageBlock(href: string, alt = '') {
    return (
      <span className="msg__media">
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="msg__link"
        >
          {t('chat.viewOriginal')}
        </a>
        <img src={href} alt={alt} className="msg__image" />
      </span>
    );
  }

  const plugins: PluggableList = allowHtml
    ? [
        rehypeRaw,
        [rehypeSanitize, knowledgeSchema],
        rehypeSlug,
        [rehypeKatex, { throwOnError: false, strict: 'ignore' }],
        rehypeHighlight,
      ]
    : [
        rehypeSlug,
        [rehypeKatex, { throwOnError: false, strict: 'ignore' }],
        rehypeHighlight,
      ];

  const components = {
          a({ href, children }: { href?: string; children?: ReactNode }) {
            const normalized = normalizeExportHref(href) ?? '';
            if (isExportImage(normalized)) {
              if (markdownHasImageEmbed(content, normalized)) {
                return (
                  <a
                    href={normalized}
                    target="_blank"
                    rel="noreferrer"
                    className="msg__link"
                  >
                    {t('chat.viewOriginal')}
                  </a>
                );
              }
              return exportImageBlock(normalized);
            }
            if (isExportSvg(normalized)) {
              return (
                <WebpageEmbed
                  href={normalized}
                  traceUrls={traceSvg}
                  preferSource={preferSource}
                  kind="svg"
                />
              );
            }
            if (isExportHtml(normalized)) {
              return (
                <WebpageEmbed
                  href={normalized}
                  traceUrls={traceHtml}
                  preferSource={preferSource}
                />
              );
            }
            const label = isExportPath(normalized)
              ? t('chat.downloadFile')
              : children;
            return (
              <a
                href={normalized || href}
                target="_blank"
                rel="noreferrer"
                className="msg__link"
              >
                {label}
              </a>
            );
          },
          img({ src, alt }: { src?: string; alt?: string }) {
            const normalized = normalizeExportHref(src) || src;
            if (!normalized) return null;
            if (isExportSvg(normalized)) {
              return (
                <WebpageEmbed
                  href={normalized}
                  traceUrls={traceSvg}
                  kind="svg"
                />
              );
            }
            if (isExportImage(normalized) && markdownHasImageEmbed(content, normalized)) {
              return (
                <span className="msg__media">
                  <img src={normalized} alt={alt || ''} className="msg__image" />
                </span>
              );
            }
            if (isExportImage(normalized)) {
              return exportImageBlock(normalized, alt || '');
            }
            return (
              <span className="msg__media">
                <img src={normalized} alt={alt || ''} className="msg__image" />
              </span>
            );
          },
          code({ className, children, ...props }: { className?: string; children?: ReactNode }) {
            const isFenced =
              Boolean(className?.includes('language-')) ||
              flattenText(children).includes('\n');
            if (isFenced) {
              return (
                <CodeBlock className={className} preferSource={preferSource}>
                  {children}
                </CodeBlock>
              );
            }
            return (
              <code className="md-inline-code" {...props}>
                {children}
              </code>
            );
          },
          pre({ children }: { children?: ReactNode }) {
            return <>{children}</>;
          },
          table({ children }: { children?: ReactNode }) {
            return (
              <div className="md-table-wrap">
                <table>{children}</table>
              </div>
            );
          },
  };

  const chunks = markdown.split(/%%NOUS_SVG_(\d+)%%/);

  return (
    <MarkdownRenderGuard
      key={content}
      fallback={<p className="banner banner--error">{t('km.markdownFailed')}</p>}
    >
      <div className={className ? `md ${className}` : 'md'}>
        {chunks.map((part, index) => {
          if (index % 2 === 1) {
            const raw = hoistedSvgs[Number(part)] || '';
            const safe = renderableSvg(raw);
            return safe ? (
              <SvgBlock
                key={`svg-${index}`}
                markup={safe}
                source={raw}
                preferSource={preferSource}
              />
            ) : null;
          }
          if (!part.trim()) return null;
          return (
            <ReactMarkdown
              key={`md-${index}`}
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={plugins}
              components={components}
            >
              {part}
            </ReactMarkdown>
          );
        })}
      </div>
    </MarkdownRenderGuard>
  );
}
