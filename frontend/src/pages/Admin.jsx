import { useEffect, useState } from "react";
import api, { errorMessage } from "../api/client";
import { formatDate, formatDateTime } from "../utils";

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [tab, setTab] = useState("users");
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([api.get("/api/admin/stats"), api.get("/api/admin/users"), api.get("/api/admin/sessions")])
      .then(([s, u, se]) => { setStats(s.data); setUsers(u.data); setSessions(se.data); })
      .catch((err) => setError(errorMessage(err, "Admin data couldn't be loaded.")));

  useEffect(() => { load(); }, []);

  const setActive = async (u, active) => {
    if (!active && !window.confirm(`Suspend ${u.name}? They won't be able to sign in.`)) return;
    try { await api.put(`/api/admin/users/${u.id}/status`, { active }); load(); }
    catch (err) { setError(errorMessage(err, "The user couldn't be updated.")); }
  };

  const remove = async (u) => {
    if (!window.confirm(`Delete ${u.name} and all their skills, requests, sessions and ratings? This can't be undone.`)) return;
    try { await api.delete(`/api/admin/users/${u.id}`); load(); }
    catch (err) { setError(errorMessage(err, "The user couldn't be deleted.")); }
  };

  return (
    <main className="page">
      <h1 className="page-title">Admin</h1>
      <p className="page-sub">Manage users, monitor sessions, and keep the platform healthy.</p>
      {error && <p className="alert alert-error" role="alert">{error}</p>}

      {stats && (
        <div className="stats stats-wide">
          <Stat label="Users" value={stats.users} sub={`${stats.activeUsers} active`} />
          <Stat label="Skills listed" value={stats.skills} sub={`${stats.verifiedSkills} verified`} />
          <Stat label="Swap requests" value={stats.swapRequests} />
          <Stat label="Sessions" value={stats.sessions} sub={`${stats.completedSessions} completed`} />
          <Stat label="Skill tests taken" value={stats.skillTests} />
        </div>
      )}

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "users"} className={`tab${tab === "users" ? " active" : ""}`} onClick={() => setTab("users")}>Users ({users.length})</button>
        <button role="tab" aria-selected={tab === "sessions"} className={`tab${tab === "sessions" ? " active" : ""}`} onClick={() => setTab("sessions")}>Sessions ({sessions.length})</button>
      </div>

      <div className="card table-wrap">
        {tab === "users" ? (
          <table className="table">
            <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Rating</th><th>Joined</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.name}</td>
                  <td>{u.email}</td>
                  <td>{u.role.toLowerCase()}</td>
                  <td>{u.ratingCount ? `${u.rating.toFixed(1)} (${u.ratingCount})` : "–"}</td>
                  <td>{formatDate(u.createdAt)}</td>
                  <td><span className={`pill ${u.active ? "pill-accepted" : "pill-rejected"}`}>{u.active ? "active" : "suspended"}</span></td>
                  <td className="table-actions">
                    {u.role !== "ADMIN" && (
                      <>
                        <button className="btn btn-ghost btn-sm" onClick={() => setActive(u, !u.active)}>{u.active ? "Suspend" : "Reactivate"}</button>
                        <button className="btn btn-danger-soft btn-sm" onClick={() => remove(u)}>Delete</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="table">
            <thead><tr><th>Topic</th><th>Teacher</th><th>Learner</th><th>When</th><th>Length</th><th>Status</th></tr></thead>
            <tbody>
              {sessions.length === 0 && <tr><td colSpan={6} className="muted">No sessions yet.</td></tr>}
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>{s.skillTopic}</td>
                  <td>{s.teacher.name}</td>
                  <td>{s.learner.name}</td>
                  <td>{formatDateTime(s.scheduledAt)}</td>
                  <td>{s.durationMinutes} min</td>
                  <td><span className={`pill pill-${s.status.toLowerCase()}`}>{s.status.toLowerCase()}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}

function Stat({ label, value, sub }) {
  return (
    <div className="stat stat-indigo">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}{sub && <>, {sub}</>}</span>
    </div>
  );
}
