type HydraMarkProps = {
  className?: string;
};

function HydraMark({ className = "brand-mark" }: HydraMarkProps) {
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true">
      <path className="hydra-mark-frame" d="M24 3.5 42 14v20L24 44.5 6 34V14Z" />
      <path className="hydra-mark-branch" d="M24 38V25M24 25c0-6-9-4-10-11M24 25V9M24 25c0-6 9-4 10-11" />
      <circle className="hydra-mark-head head-left" cx="14" cy="11" r="3.6" />
      <circle className="hydra-mark-head head-center" cx="24" cy="7" r="3.6" />
      <circle className="hydra-mark-head head-right" cx="34" cy="11" r="3.6" />
      <circle className="hydra-mark-core" cx="24" cy="38" r="3.8" />
    </svg>
  );
}

export default HydraMark;
