interface OptionToggleProps {
  checked: boolean;
  disabled?: boolean;
  title: string;
  hint?: string;
  onChange: (on: boolean) => void;
}

export default function OptionToggle({
  checked,
  disabled,
  title,
  hint,
  onChange,
}: OptionToggleProps) {
  return (
    <label
      className={[
        'opt-toggle',
        checked ? 'opt-toggle--on' : '',
        disabled ? 'opt-toggle--disabled' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <span className="opt-toggle__copy">
        <span className="opt-toggle__title">{title}</span>
        {hint ? <span className="opt-toggle__hint">{hint}</span> : null}
      </span>
      <span className="opt-toggle__control">
        <input
          className="opt-toggle__input"
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span className="opt-toggle__track" aria-hidden="true">
          <span className="opt-toggle__thumb" />
        </span>
      </span>
    </label>
  );
}
