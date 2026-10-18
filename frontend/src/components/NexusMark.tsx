type NexusMarkProps = {
  className?: string;
};

export default function NexusMark({ className }: NexusMarkProps) {
  return (
    <img
      className={className}
      src="/nexus-mark.svg"
      alt=""
      aria-hidden="true"
      draggable={false}
    />
  );
}
