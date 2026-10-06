import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import Modal from "../components/Modal";
import UserCard from "../components/UserCard";
import { levelLabel } from "../utils";

export default function Explore() {
  const [params, setParams] = useSearchParams();
  const initialQuery = params.get("skill") || "";
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState([]);
  const [mode, setMode] = useState(initialQuery ? "search" : "matches");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mySkills, setMySkills] = useState([]);
  const [target, setTarget] = useState(null);
  const [notice, setNotice] = useState("");

  const run = async (q) => {
    setLoading(true);
    setError("");
    try {
      if (q.trim()) {
        const r = await api.get("/api/users/search", { params: { skill: q.trim() } });
        setResults(r.data);
        setMode("search");
      } else {
        const r = await api.get("/api/matches");
        if (r.data.length > 0) {
          setResults(r.data);
          setMode("matches");
        } else {
          const all = await api.get("/api/users/search", { params: { skill: "" } });
          setResults(all.data);
          setMode("all");
        }
      }
    } catch (err) {
      setError(errorMessage(err, "Results couldn't be loaded."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    run(initialQuery);
    api.get("/api/skills/me").then((r) => setMySkills(r.data)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = (e) => {
    e.preventDefault();
    setParams(query.trim() ? { skill: query.trim() } : {});
    run(query);
  };

  const heading = mode === "search" ? `People who teach "${query.trim()}"`
    : mode === "matches" ? "Best matches for you" : "Everyone on SkillSwap";

  return (
    <main className="page">
      <h1 className="page-title">Explore users</h1>
      <p className="page-sub">Find people with skills you want to learn.</p>

      <form className="search-bar" onSubmit={submit} role="search">
        <input aria-label="Search by skill" placeholder="Search by skill (e.g. Python, Design…)"
          value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="submit" className="btn btn-primary">Search</button>
      </form>

      {notice && <p className="alert alert-success" role="status">{notice}</p>}
      {error && <p className="alert alert-error" role="alert">{error}</p>}

      <h2 className="section-title">{heading}</h2>
      {mode === "matches" && (
        <p className="muted small section-note">
          Ranked by the smart matching algorithm: skills you can exchange, level, verification, rating and city.
        </p>
      )}

      {loading ? <p className="muted">Loading…</p> : results.length === 0 ? (
        <div className="empty">
          <p>No one teaches that yet.</p>
          <p className="muted small">Try a broader name, like "Design" instead of "Logo design".</p>
        </div>
      ) : (
        <div className="card-grid">
          {results.map((card) => (
            <UserCard key={card.id} card={card} highlight={mode === "search" ? query : ""} onRequest={setTarget} />
          ))}
        </div>
      )}

      {target && (
        <RequestModal target={target} mySkills={mySkills} preferred={mode === "search" ? query : ""}
          onClose={() => setTarget(null)}
          onSent={(name) => { setTarget(null); setNotice(`Swap request sent to ${name}.`); }} />
      )}
    </main>
  );
}

function RequestModal({ target, mySkills, preferred, onClose, onSent }) {
  const navigate = useNavigate();
  const myTeaching = mySkills.filter((s) => s.type === "OFFERED");
  const pre = target.teaches.find((s) => preferred && s.name.toLowerCase().includes(preferred.trim().toLowerCase()));
  const [skillName, setSkillName] = useState((pre || target.teaches[0])?.name || "");
  const wantsFromMe = myTeaching.find((s) => target.wantsToLearn.some((w) => w.name.toLowerCase() === s.name.toLowerCase()));
  const [offered, setOffered] = useState(wantsFromMe?.name || "");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/api/swap-requests", {
        toUserId: target.id, skillName, offeredSkillName: offered || null, message,
      });
      onSent(target.name);
    } catch (err) {
      setError(errorMessage(err, "The request couldn't be sent."));
      setBusy(false);
    }
  };

  return (
    <Modal title={`Request a swap with ${target.name}`} onClose={onClose}>
      <form onSubmit={send} className="form">
        <label className="field">
          <span>I want to learn</span>
          <select value={skillName} onChange={(e) => setSkillName(e.target.value)}>
            {target.teaches.map((s) => <option key={s.id} value={s.name}>{s.name} ({levelLabel(s.level)})</option>)}
          </select>
        </label>
        <label className="field">
          <span>I can teach in return</span>
          <select value={offered} onChange={(e) => setOffered(e.target.value)}>
            <option value="">Nothing for now</option>
            {myTeaching.map((s) => <option key={s.id} value={s.name}>{s.name}</option>)}
          </select>
          {myTeaching.length === 0 && (
            <small className="muted">
              You haven't listed skills you teach.{" "}
              <button type="button" className="link-btn" onClick={() => navigate("/skills")}>Add one</button>
            </small>
          )}
        </label>
        <label className="field">
          <span>Message (optional)</span>
          <textarea rows={3} maxLength={500} value={message} onChange={(e) => setMessage(e.target.value)}
            placeholder="Say hi and mention when you're usually free." />
        </label>
        {error && <p className="alert alert-error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy || !skillName}>
            {busy ? "Sending…" : "Send request"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
