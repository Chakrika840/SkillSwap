import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import Modal from "../components/Modal";
import StarRating from "../components/StarRating";
import { useAuth } from "../context/AuthContext";
import { defaultSessionTime, formatDateTime } from "../utils";

const TABS = [
  { id: "upcoming", label: "Upcoming" },
  { id: "teaching", label: "Teaching" },
  { id: "learning", label: "Learning" },
  { id: "past", label: "Past" },
];

export default function Sessions() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [sessions, setSessions] = useState([]);
  const [accepted, setAccepted] = useState([]);
  const [tab, setTab] = useState("upcoming");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scheduleFor, setScheduleFor] = useState(null); // swap id or "" for picker
  const [rating, setRating] = useState(null);

  const load = () =>
    Promise.all([api.get("/api/sessions/me"), api.get("/api/swap-requests/accepted")])
      .then(([s, a]) => { setSessions(s.data); setAccepted(a.data); })
      .catch((err) => setError(errorMessage(err, "Sessions couldn't be loaded.")))
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
    const swap = params.get("swap");
    if (swap) setScheduleFor(swap);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const groups = useMemo(() => {
    const upcoming = sessions.filter((s) => s.status === "SCHEDULED")
      .sort((a, b) => new Date(a.scheduledAt) - new Date(b.scheduledAt));
    return {
      upcoming,
      teaching: sessions.filter((s) => s.myRole === "TEACHER"),
      learning: sessions.filter((s) => s.myRole === "LEARNER"),
      past: sessions.filter((s) => s.status !== "SCHEDULED"),
    };
  }, [sessions]);

  const act = async (id, action) => {
    if (action === "cancel" && !window.confirm("Cancel this session?")) return;
    setError("");
    try {
      await api.put(`/api/sessions/${id}/${action}`);
      await load();
    } catch (err) {
      setError(errorMessage(err, "That didn't work. Try again."));
    }
  };

  const closeSchedule = () => {
    setScheduleFor(null);
    if (params.get("swap")) setParams({});
  };

  const list = groups[tab];

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">My sessions</h1>
          <p className="page-sub">Schedule, track, and review your video sessions.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setScheduleFor("")}>New session</button>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id}
            className={`tab${tab === t.id ? " active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label} <span className="tab-count">{groups[t.id].length}</span>
          </button>
        ))}
      </div>

      {error && <p className="alert alert-error" role="alert">{error}</p>}

      {loading ? <p className="muted">Loading…</p> : list.length === 0 ? (
        <div className="empty">
          <p>No {tab === "past" ? "past" : tab} sessions yet.</p>
          {tab === "upcoming" && <button className="btn btn-primary" onClick={() => setScheduleFor("")}>Schedule one now</button>}
        </div>
      ) : (
        <div className="card-grid">
          {list.map((s) => (
            <article key={s.id} className="card session-card">
              <div className="request-head">
                <span className={`pill pill-${s.status.toLowerCase()}`}>{s.status.toLowerCase()}</span>
                <span className="muted small">{s.durationMinutes} min</span>
              </div>
              <h3>{s.skillTopic}</h3>
              <p className="small">
                {s.teacher.id === user.id ? "You" : s.teacher.name} teaching{" "}
                {s.learner.id === user.id ? "you" : s.learner.name}
              </p>
              <p className="muted small">{formatDateTime(s.scheduledAt)}</p>

              {s.status === "SCHEDULED" && (
                <div className="btn-row">
                  <a className="btn btn-primary" href={s.meetingLink} target="_blank" rel="noreferrer">Join video call</a>
                  <button className="btn btn-ghost" onClick={() => act(s.id, "complete")}>Mark complete</button>
                  <button className="btn btn-ghost" onClick={() => act(s.id, "cancel")}>Cancel</button>
                </div>
              )}
              {s.status === "COMPLETED" && !s.ratedByMe && (
                <button className="btn btn-outline" onClick={() => setRating(s)}>
                  Rate {s.myRole === "TEACHER" ? s.learner.name : s.teacher.name}
                </button>
              )}
              {s.status === "COMPLETED" && s.ratedByMe && <p className="muted small">You rated this session.</p>}
            </article>
          ))}
        </div>
      )}

      {/* Wait for the accepted swaps to load: the form fills its defaults from them when it opens. */}
      {scheduleFor !== null && !loading && (
        <ScheduleModal swaps={accepted} initialSwapId={scheduleFor} userId={user.id}
          onClose={closeSchedule} onSaved={() => { closeSchedule(); setTab("upcoming"); load(); }} />
      )}
      {rating && (
        <RateModal session={rating} onClose={() => setRating(null)} onSaved={() => { setRating(null); load(); }} />
      )}
    </main>
  );
}

function ScheduleModal({ swaps, initialSwapId, userId, onClose, onSaved }) {
  const first = swaps.find((s) => String(s.id) === String(initialSwapId)) || swaps[0];
  const [swapId, setSwapId] = useState(first ? String(first.id) : "");
  const swap = swaps.find((s) => String(s.id) === swapId);
  // The sender of a request is the one who wanted to learn.
  const iSent = swap ? swap.fromUser.id === userId : false;
  const [iAmTeacher, setIAmTeacher] = useState(!iSent);
  const [topic, setTopic] = useState(swap ? swap.skillName : "");
  const [when, setWhen] = useState(defaultSessionTime());
  const [duration, setDuration] = useState(60);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const partner = swap ? (iSent ? swap.toUser : swap.fromUser) : null;

  const pickSwap = (id) => {
    setSwapId(id);
    const s = swaps.find((x) => String(x.id) === id);
    if (s) {
      const sent = s.fromUser.id === userId;
      setIAmTeacher(!sent);
      setTopic(s.skillName);
    }
  };

  const pickRole = (teacher) => {
    setIAmTeacher(teacher);
    if (!swap) return;
    // Sender learns swap.skillName; receiver learns swap.offeredSkillName (if any).
    const learnerIsSender = iSent ? !teacher : teacher;
    setTopic(learnerIsSender || !swap.offeredSkillName ? swap.skillName : swap.offeredSkillName);
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/api/sessions", {
        swapRequestId: Number(swapId), skillTopic: topic, scheduledAt: when,
        durationMinutes: Number(duration), iAmTeacher,
      });
      onSaved();
    } catch (err) {
      setError(errorMessage(err, "The session couldn't be scheduled."));
      setBusy(false);
    }
  };

  return (
    <Modal title="Schedule video session" onClose={onClose}>
      {swaps.length === 0 ? (
        <div className="form">
          <p>You need an accepted swap request before scheduling a session.</p>
          <div className="modal-actions"><button className="btn btn-primary" onClick={onClose}>OK</button></div>
        </div>
      ) : (
        <form className="form" onSubmit={save}>
          <label className="field">
            <span>Swap partner</span>
            <select value={swapId} onChange={(e) => pickSwap(e.target.value)}>
              {swaps.map((s) => {
                const other = s.fromUser.id === userId ? s.toUser : s.fromUser;
                return <option key={s.id} value={s.id}>{other.name}, {s.skillName}{s.offeredSkillName ? ` ⇄ ${s.offeredSkillName}` : ""}</option>;
              })}
            </select>
          </label>
          <fieldset className="field">
            <legend>In this session</legend>
            <label className="radio"><input type="radio" checked={!iAmTeacher} onChange={() => pickRole(false)} />
              {partner?.name} teaches me</label>
            <label className="radio"><input type="radio" checked={iAmTeacher} onChange={() => pickRole(true)} />
              I teach {partner?.name}</label>
          </fieldset>
          <label className="field">
            <span>Skill topic</span>
            <input value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={100} required />
          </label>
          <div className="field-row">
            <label className="field">
              <span>Date and time</span>
              <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
            </label>
            <label className="field">
              <span>Duration</span>
              <select value={duration} onChange={(e) => setDuration(e.target.value)}>
                <option value={30}>30 minutes</option>
                <option value={45}>45 minutes</option>
                <option value={60}>1 hour</option>
                <option value={90}>1.5 hours</option>
                <option value={120}>2 hours</option>
              </select>
            </label>
          </div>
          <p className="muted small">A free Jitsi Meet video room is created for the session.</p>
          {error && <p className="alert alert-error" role="alert">{error}</p>}
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Scheduling…" : "Schedule session"}</button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function RateModal({ session, onClose, onSaved }) {
  const other = session.myRole === "TEACHER" ? session.learner : session.teacher;
  const [score, setScore] = useState(0);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    if (!score) { setError("Choose 1 to 5 stars."); return; }
    setBusy(true);
    setError("");
    try {
      await api.post("/api/ratings", { sessionId: session.id, score, comment });
      onSaved();
    } catch (err) {
      setError(errorMessage(err, "The rating couldn't be saved."));
      setBusy(false);
    }
  };

  return (
    <Modal title={`Rate ${other.name}`} onClose={onClose}>
      <form className="form" onSubmit={save}>
        <p className="muted small">{session.skillTopic}, {formatDateTime(session.scheduledAt)}</p>
        <StarRating value={score} onChange={setScore} />
        <label className="field">
          <span>Feedback (optional)</span>
          <textarea rows={3} maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} />
        </label>
        {error && <p className="alert alert-error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Submit rating"}</button>
        </div>
      </form>
    </Modal>
  );
}
