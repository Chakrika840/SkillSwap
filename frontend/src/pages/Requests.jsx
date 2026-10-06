import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import { formatDateTime, levelLabel } from "../utils";

export default function Requests() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("incoming");
  const [incoming, setIncoming] = useState([]);
  const [outgoing, setOutgoing] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([api.get("/api/swap-requests/incoming"), api.get("/api/swap-requests/outgoing")])
      .then(([i, o]) => { setIncoming(i.data); setOutgoing(o.data); })
      .catch((err) => setError(errorMessage(err, "Requests couldn't be loaded.")))
      .finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const act = async (id, action) => {
    setError("");
    try {
      await api.put(`/api/swap-requests/${id}/${action}`);
      await load();
    } catch (err) {
      setError(errorMessage(err, "That didn't work. Try again."));
    }
  };

  const list = tab === "incoming" ? incoming : outgoing;

  return (
    <main className="page">
      <h1 className="page-title">Swap requests</h1>
      <p className="page-sub">Manage your incoming and outgoing skill swap requests.</p>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "incoming"} className={`tab${tab === "incoming" ? " active" : ""}`}
          onClick={() => setTab("incoming")}>Incoming ({incoming.length})</button>
        <button role="tab" aria-selected={tab === "outgoing"} className={`tab${tab === "outgoing" ? " active" : ""}`}
          onClick={() => setTab("outgoing")}>Outgoing ({outgoing.length})</button>
      </div>

      {error && <p className="alert alert-error" role="alert">{error}</p>}
      {loading ? <p className="muted">Loading…</p> : list.length === 0 ? (
        <div className="empty">
          <p>{tab === "incoming" ? "No incoming requests yet." : "You haven't sent any requests."}</p>
          {tab === "outgoing" && (
            <button className="btn btn-primary" onClick={() => navigate("/explore")}>Find someone to learn from</button>
          )}
        </div>
      ) : (
        <div className="card-grid">
          {list.map((r) => {
            const other = tab === "incoming" ? r.fromUser : r.toUser;
            return (
              <article key={r.id} className="card request-card">
                <div className="request-head">
                  <div>
                    <h3>{other.name}</h3>
                    <p className="muted small">{other.email}</p>
                  </div>
                  <span className={`pill pill-${r.status.toLowerCase()}`}>{r.status.toLowerCase()}</span>
                </div>
                <p className="small">
                  {tab === "incoming" ? "Wants to learn" : "You want to learn"}{" "}
                  <strong>{r.skillName}</strong>{r.skillLevel && <> ({levelLabel(r.skillLevel)})</>}
                </p>
                {r.offeredSkillName && (
                  <p className="small">{tab === "incoming" ? "Offers to teach" : "You offer"} <strong>{r.offeredSkillName}</strong></p>
                )}
                {r.message && <p className="quote">{r.message}</p>}
                <p className="muted small">Sent {formatDateTime(r.createdAt)}</p>

                {r.status === "PENDING" && tab === "incoming" && (
                  <div className="btn-row">
                    <button className="btn btn-success" onClick={() => act(r.id, "accept")}>Accept</button>
                    <button className="btn btn-danger-soft" onClick={() => act(r.id, "reject")}>Reject</button>
                  </div>
                )}
                {r.status === "PENDING" && tab === "outgoing" && (
                  <button className="btn btn-ghost" onClick={() => act(r.id, "cancel")}>Cancel request</button>
                )}
                {r.status === "ACCEPTED" && (
                  <button className="btn btn-primary" onClick={() => navigate(`/sessions?swap=${r.id}`)}>
                    Schedule session
                  </button>
                )}
              </article>
            );
          })}
        </div>
      )}
    </main>
  );
}
