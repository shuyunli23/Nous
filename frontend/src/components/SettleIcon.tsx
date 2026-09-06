export default function SettleIcon({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.15"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M9 5.2h7.4c1.6 0 2.9 1.3 2.9 2.9v7.4" />
      <rect x="3.8" y="8.6" width="12.6" height="12.6" rx="2.7" />
      <path d="M6.8 13.8h6.4" />
      <path d="M6.8 17h3.8" />
    </svg>
  );
}
