import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import VerifiedBadge from "../components/VerifiedBadge";
import { levelLabel } from "../utils";

export default function AIPicks() {
  const navigate = useNavigate();
  const [picks, setPicks] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/recommendations").then((r) => setPicks(r.data))
      .catch((err) => setError(errorMessage(err, "Recommendations couldn't be loaded.")));
  }, []);

  const source = picks?.[0]?.source;

  return (
    <main className="page">
      <h1 className="page-title">AI picks</h1>
      <p className="page-sub">Skills to learn next, based on what you teach and what you want to learn.</p>

      {error && <p className="alert alert-error" role="alert">{error}</p>}
      {!picks && !error && <p className="muted">Finding skills for you…</p>}

      {picks && picks.length === 0 && (
        <div className="empty">
          <p>Add a few skills first so the model has something to go on.</p>
          <Link className="btn btn-primary" to="/skills">Add skills</Link>
        </div>
      )}

      {picks && picks.length > 0 && (
        <>
          <p className="muted small section-note">
            {source === "ML model"
              ? "Suggested by the recommendation model, trained on which skills learners tend to combine."
              : source === "Popular among learners"
                ? "The model doesn't know your skills yet, so these are the skills learners pick most often."
                : "The model couldn't make suggestions yet, so these are the most taught skills on SkillSwap."}
          </p>
          <div className="card-grid">
            {picks.map((p) => (
              <article key={p.skill} className="card pick-card">
                <div className="pick-head">
                  <h3>{p.skill}</h3>
                  <span className="muted small">{p.score}% fit</span>
                </div>
                <div className="meter" aria-hidden="true"><span style={{ width: `${Math.max(6, p.score)}%` }} /></div>
                {p.teachers.length === 0 ? (
                  <p className="muted small">No one teaches this on SkillSwap yet.</p>
                ) : (
                  <ul className="teacher-list">
                    {p.teachers.map((t) => (
                      <li key={t.userId}>
                        <span>{t.name}</span>
                        <span className="muted small">{levelLabel(t.level)}</span>
                        {t.verified && <VerifiedBadge level={t.level} />}
                      </li>
                    ))}
                  </ul>
                )}
                <button className="btn btn-outline btn-block" onClick={() => navigate(`/explore?skill=${encodeURIComponent(p.skill)}`)}
                  disabled={p.teachers.length === 0}>
                  Find teachers
                </button>
              </article>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
