type SendButtonProps = {
  ready: boolean;
  label: string;
  disabled?: boolean;
  type?: 'button' | 'submit';
  onClick?: () => void;
};

export function SendArrow() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 3.4 21 19.6 12 15.5 3 19.6Z"
      />
    </svg>
  );
}

export default function SendButton({
  ready,
  label,
  disabled,
  type = 'button',
  onClick,
}: SendButtonProps) {
  return (
    <button
      type={type}
      className={`composer__send${ready ? ' composer__send--ready' : ''}`}
      onClick={onClick}
      disabled={disabled || !ready}
      aria-label={label}
    >
      <SendArrow />
    </button>
  );
}
