import { useMemo, useRef } from 'react';

interface MarkdownSourceEditorProps {
  value: string;
  onChange: (next: string) => void;
  label: string;
}

export default function MarkdownSourceEditor({
  value,
  onChange,
  label,
}: MarkdownSourceEditorProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const gutterRef = useRef<HTMLPreElement>(null);
  const lines = useMemo(
    () => Math.max(1, value.split('\n').length),
    [value],
  );
  const gutter = useMemo(
    () => Array.from({ length: lines }, (_, i) => String(i + 1)).join('\n'),
    [lines],
  );

  function syncScroll() {
    const input = inputRef.current;
    const gutterEl = gutterRef.current;
    if (!input || !gutterEl) return;
    gutterEl.scrollTop = input.scrollTop;
  }

  return (
    <div className="km-source">
      <pre
        ref={gutterRef}
        className="km-source__gutter"
        aria-hidden="true"
      >
        {gutter}
      </pre>
      <textarea
        ref={inputRef}
        className="km-source__input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onScroll={syncScroll}
        spellCheck={false}
        wrap="off"
        aria-label={label}
      />
    </div>
  );
}
