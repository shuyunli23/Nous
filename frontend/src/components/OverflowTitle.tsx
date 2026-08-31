import { useState } from 'react';
import { createPortal } from 'react-dom';

export default function OverflowTitle({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  const [tip, setTip] = useState<{ top: number; left: number } | null>(null);
  const classes = className
    ? `overflow-title ${className}`
    : 'overflow-title';

  return (
    <>
      <span
        className={classes}
        onMouseEnter={(event) => {
          const box = event.currentTarget.getBoundingClientRect();
          setTip({ top: box.bottom + 8, left: box.left });
        }}
        onMouseLeave={() => setTip(null)}
      >
        {text}
      </span>
      {tip
        ? createPortal(
            <div
              className="overflow-title__tip"
              role="tooltip"
              style={{ top: tip.top, left: tip.left }}
            >
              {text}
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
