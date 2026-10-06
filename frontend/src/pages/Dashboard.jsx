import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import VerifiedBadge from "../components/VerifiedBadge";
import { useAuth } from "../context/AuthContext";
import { formatDateTime, initial, levelLabel } from "../utils";

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/dashboard").then((r) => setData(r.data))
      .catch((err) => setError(errorMessage(err, "Your dashboard couldn't be loaded.")));
  }, []);

  return (
    <main className="page">
      <h1 className="page-title">Welcome back, {user.name.split(" ")[0]} 👋</h1>
      <p className="page-sub">Here's what's happening with your skills today.</p>

      {error && <p className="alert alert-error">{error}</p>}
      {!data && !error && <p className="muted">Loading…</p>}

      {data && (
        <>
          <div className="stats">
            <Stat value={data.skillsListed} label="Skills listed" tone="indigo" />
            <Stat value={data.pendingRequests} label="Pending requests" tone="green" />
            <Stat value={data.activeSwaps} label="Active swaps" tone="violet" />
            <Stat value={data.rating > 0 ? `★ ${data.rating.toFixed(1)}` : "★ 0.0"}
              label={data.ratingCount ? `Rating from ${data.ratingCount}` : "Rating"} tone="amber" />
          </div>

          <div className="grid-2">
            <section className="card">
              <div className="card-head">
                <h2>My skills</h2>
                <Link to="/skills" className="link-sm">Manage</Link>
              </div>
              {data.mySkills.length === 0 ? (
                <p className="muted small">No skills yet. <Link to="/skills">Add one</Link> to start matching.</p>
              ) : (
                <div className="chips">
                  {data.mySkills.map((s) => (
                    <span key={s.id} className={`chip${s.type === "WANTED" ? " chip-soft" : ""}`}>
                      {s.name} <span className="chip-level">{s.type === "WANTED" ? "learning" : levelLabel(s.level)}</span>
                      {s.verified && <VerifiedBadge level={s.verifiedLevel} />}
                    </span>
                  ))}
                </div>
              )}
            </section>

            <section className="card">
              <div className="card-head">
                <h2>Incoming requests</h2>
                <Link to="/requests" className="link-sm">View all</Link>
              </div>
              {data.incomingRequests.length === 0 ? (
                <p className="muted small">No incoming requests yet.</p>
              ) : (
                <ul className="list">
                  {data.incomingRequests.map((r) => (
                    <li key={r.id}>
                      <strong>{r.fromUser.name}</strong> wants to learn {r.skillName}
                      {r.offeredSkillName && <> and offers {r.offeredSkillName}</>}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="card">
              <div className="card-head">
                <h2>Upcoming sessions</h2>
                <Link to="/sessions" className="link-sm">All sessions</Link>
              </div>
              {data.nextSessions.length === 0 ? (
                <p className="muted small">Nothing scheduled. Accept a swap request, then schedule a session.</p>
              ) : (
                <ul className="list">
                  {data.nextSessions.map((s) => (
                    <li key={s.id}>
                      <strong>{s.skillTopic}</strong> with {s.myRole === "TEACHER" ? s.learner.name : s.teacher.name}
                      <div className="muted small">{formatDateTime(s.scheduledAt)}</div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="card">
              <div className="card-head">
                <h2>Top matches</h2>
                <Link to="/explore" className="link-sm">Explore</Link>
              </div>
              {data.topMatches.length === 0 ? (
                <p className="muted small">Add skills you teach and want to learn to see matches.</p>
              ) : (
                <ul className="list">
                  {data.topMatches.map((m) => (
                    <li key={m.id} className="match-row">
                      <span className="avatar avatar-sm" aria-hidden="true">{initial(m.name)}</span>
                      <div>
                        <strong>{m.name}</strong>
                        <div className="muted small">{m.matchReasons[0]}</div>
                      </div>
                      <span className="match-score">{m.matchScore}%</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </main>
  );
}

function Stat({ value, label, tone }) {
  return (
    <div className={`stat stat-${tone}`}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
