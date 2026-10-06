import { initial, levelLabel } from "../utils";
import StarRating from "./StarRating";
import VerifiedBadge from "./VerifiedBadge";

export default function UserCard({ card, onRequest, highlight }) {
  const q = (highlight || "").trim().toLowerCase();
  return (
    <article className="card user-card">
      <div className="user-card-head">
        <span className="avatar" aria-hidden="true">{initial(card.name)}</span>
        <div className="user-card-id">
          <h3>{card.name}</h3>
          <p className="user-meta">
            <StarRating value={card.rating} size="sm" />
            {card.ratingCount > 0 && <span>({card.ratingCount})</span>}
            {card.city && <span>{card.city}</span>}
            {card.matchScore != null && (
              <span className="match-score" title="Smart match score">{card.matchScore}% match</span>
            )}
          </p>
        </div>
      </div>

      {card.bio && <p className="user-bio">{card.bio}</p>}

      {card.matchReasons?.length > 0 && (
        <ul className="reasons">
          {card.matchReasons.map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}

      <div className="skill-group">
        <span className="skill-group-label">Teaches</span>
        <div className="chips">
          {card.teaches.length === 0 && <span className="muted small">Nothing listed yet</span>}
          {card.teaches.map((s) => (
            <span key={s.id} className={`chip${q && s.name.toLowerCase().includes(q) ? " chip-hit" : ""}`}>
              {s.name} <span className="chip-level">{levelLabel(s.level)}</span>
              {s.verified && <VerifiedBadge level={s.verifiedLevel} score={s.verificationScore} />}
            </span>
          ))}
        </div>
      </div>

      {card.wantsToLearn.length > 0 && (
        <div className="skill-group">
          <span className="skill-group-label">Wants to learn</span>
          <div className="chips">
            {card.wantsToLearn.map((s) => <span key={s.id} className="chip chip-soft">{s.name}</span>)}
          </div>
        </div>
      )}

      <button type="button" className="btn btn-primary btn-block" onClick={() => onRequest(card)}
        disabled={card.teaches.length === 0}>
        Request swap
      </button>
    </article>
  );
}
