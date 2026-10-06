import { useEffect, useState } from "react";
import api, { errorMessage } from "../api/client";
import VerifySkillButton from "../components/VerifySkillButton";
import { LEVELS, levelLabel } from "../utils";

export default function Skills() {
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", level: "BEGINNER", type: "OFFERED" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () =>
    api.get("/api/skills/me").then((r) => setSkills(r.data))
      .catch((err) => setError(errorMessage(err, "Your skills couldn't be loaded.")))
      .finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api.post("/api/skills", form);
      setForm((f) => ({ ...f, name: "" }));
      await load();
    } catch (err) {
      setError(errorMessage(err, "The skill couldn't be added."));
    } finally {
      setBusy(false);
    }
  };

  const changeLevel = async (skill, level) => {
    if (skill.verified && !window.confirm("Changing the level removes this skill's verified badge. Continue?")) return;
    try {
      await api.put(`/api/skills/${skill.id}`, { name: skill.name, level, type: skill.type });
      await load();
    } catch (err) {
      setError(errorMessage(err, "The level couldn't be changed."));
    }
  };

  const remove = async (skill) => {
    if (!window.confirm(`Remove ${skill.name}?`)) return;
    try {
      await api.delete(`/api/skills/${skill.id}`);
      await load();
    } catch (err) {
      setError(errorMessage(err, "The skill couldn't be removed."));
    }
  };

  const teaching = skills.filter((s) => s.type === "OFFERED");
  const learning = skills.filter((s) => s.type === "WANTED");

  return (
    <main className="page">
      <h1 className="page-title">My skills</h1>
      <p className="page-sub">Add what you can teach and what you want to learn. Matches come from both.</p>

      <form className="card add-skill" onSubmit={add}>
        <h2>Add a skill</h2>
        <div className="add-skill-row">
          <input aria-label="Skill name" placeholder="e.g. JavaScript, Cooking, Yoga…" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={60} required />
          <select aria-label="Teach or learn" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            <option value="OFFERED">I can teach</option>
            <option value="WANTED">I want to learn</option>
          </select>
          <select aria-label="Level" value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })}>
            {LEVELS.map((l) => <option key={l} value={l}>{levelLabel(l)}</option>)}
          </select>
          <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Adding…" : "Add skill"}</button>
        </div>
        {form.type === "WANTED" && <p className="muted small">For skills you want to learn, pick your current level.</p>}
      </form>

      {error && <p className="alert alert-error" role="alert">{error}</p>}
      {loading && <p className="muted">Loading…</p>}

      {!loading && (
        <div className="grid-2">
          <SkillList title="I can teach" empty="No skills yet. Add your first one above."
            skills={teaching} onLevel={changeLevel} onRemove={remove} verifiable />
          <SkillList title="I want to learn" empty="Add skills you want to learn to get better matches."
            skills={learning} onLevel={changeLevel} onRemove={remove} />
        </div>
      )}
    </main>
  );
}

function SkillList({ title, empty, skills, onLevel, onRemove, verifiable = false }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {skills.length === 0 ? <p className="muted small">{empty}</p> : (
        <ul className="skill-rows">
          {skills.map((s) => (
            <li key={s.id} className="skill-row">
              <div className="skill-row-main">
                <span className="skill-name">{s.name}</span>
                {verifiable && <VerifySkillButton skill={s} />}
              </div>
              <div className="skill-row-actions">
                <select aria-label={`${s.name} level`} value={s.level} onChange={(e) => onLevel(s, e.target.value)}>
                  {LEVELS.map((l) => <option key={l} value={l}>{levelLabel(l)}</option>)}
                </select>
                <button type="button" className="icon-btn" onClick={() => onRemove(s)} aria-label={`Remove ${s.name}`}>×</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
