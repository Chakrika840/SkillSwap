import { useEffect, useState } from "react";
import api, { errorMessage } from "../api/client";
import StarRating from "../components/StarRating";
import { useAuth } from "../context/AuthContext";
import { formatDate } from "../utils";

export default function Profile() {
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({ name: user.name, city: user.city || "", bio: user.bio || "" });
  const [ratings, setRatings] = useState([]);
  const [status, setStatus] = useState({ type: "", text: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/api/users/me").then((r) => {
      setUser(r.data);
      setForm({ name: r.data.name, city: r.data.city || "", bio: r.data.bio || "" });
    }).catch(() => {});
    api.get(`/api/users/${user.id}/ratings`).then((r) => setRatings(r.data)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setStatus({ type: "", text: "" });
    try {
      const r = await api.put("/api/users/me", form);
      setUser(r.data);
      setStatus({ type: "success", text: "Profile saved." });
    } catch (err) {
      setStatus({ type: "error", text: errorMessage(err, "Your profile couldn't be saved.") });
    } finally {
      setBusy(false);
    }
  };

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Your profile</h1>
      <p className="page-sub">Your city helps the matching algorithm find people near you.</p>

      <form className="card form" onSubmit={save}>
        <label className="field"><span>Name</span>
          <input value={form.name} onChange={update("name")} required maxLength={80} /></label>
        <label className="field"><span>Email</span>
          <input value={user.email} disabled /></label>
        <label className="field"><span>City</span>
          <input value={form.city} onChange={update("city")} maxLength={80} placeholder="e.g. Hyderabad" /></label>
        <label className="field"><span>About you</span>
          <textarea rows={3} value={form.bio} onChange={update("bio")} maxLength={500}
            placeholder="What you teach, what you're learning, when you're free." /></label>
        {status.text && <p className={`alert alert-${status.type}`} role="status">{status.text}</p>}
        <div><button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save profile"}</button></div>
      </form>

      <section className="card">
        <div className="card-head">
          <h2>Ratings received</h2>
          <StarRating value={user.rating || 0} />
        </div>
        {ratings.length === 0 ? <p className="muted small">No ratings yet. They appear after completed sessions.</p> : (
          <ul className="list">
            {ratings.map((r) => (
              <li key={r.id}>
                <strong>{"★".repeat(r.score)}</strong>{" "}
                <span className="muted small">from {r.fromName} for {r.skillTopic}, {formatDate(r.createdAt)}</span>
                {r.comment && <p className="quote">{r.comment}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
