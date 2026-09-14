function SkeletonBlock({ width = "100%", height = 16, round = false }) {
  return (
    <span
      className={round ? "skeleton skeleton--round" : "skeleton"}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

const CHIP_WIDTHS = ["5rem", "7rem", "4rem", "6rem", "8rem", "5rem", "6rem", "4.5rem"];

export function ResultsSkeleton() {
  return (
    <div className="results" role="status" aria-live="polite">
      <span className="sr-only">Loading the analysis</span>
      <SkeletonBlock width="min(24rem, 70%)" height={32} />
      <div className="results__grid">
        <div className="results__summary">
          <div className="score-row">
            <SkeletonBlock width={160} height={160} round />
            <div className="skeleton-stack">
              <SkeletonBlock width="8rem" />
              <SkeletonBlock width="6rem" />
            </div>
          </div>
          <div className="skeleton-stack">
            {[0, 1, 2, 3].map((row) => (
              <SkeletonBlock key={row} height={12} />
            ))}
          </div>
        </div>
        <div className="results__detail">
          <div className="skeleton-chips">
            {CHIP_WIDTHS.map((width, index) => (
              <SkeletonBlock key={index} width={width} height={36} />
            ))}
          </div>
          <SkeletonBlock height={320} />
        </div>
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 5 }) {
  return (
    <div className="table-skeleton" role="status" aria-live="polite">
      <span className="sr-only">Loading</span>
      {Array.from({ length: rows }, (_, index) => (
        <div className="table-skeleton__row" key={index}>
          <SkeletonBlock width="40%" />
          <SkeletonBlock width="15%" />
          <SkeletonBlock width="20%" />
        </div>
      ))}
    </div>
  );
}
