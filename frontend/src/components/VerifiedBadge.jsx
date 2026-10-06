import "./SkillTest.css";

const LEVEL_LABEL = { BEGINNER: "Beginner", INTERMEDIATE: "Intermediate", ADVANCED: "Advanced" };

/** Small badge for skill chips, user cards (Explore) and the dashboard. */
export default function VerifiedBadge({ level, score }) {
  if (!level) return null;
  return (
    <span className="st-badge" title={score != null ? `Skill test score: ${score}%` : undefined}>
      <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
        <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {LEVEL_LABEL[level] || level} verified
    </span>
  );
}
