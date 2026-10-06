import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await register(form.name, form.email, form.password);
      navigate("/skills");
    } catch (err) {
      setError(errorMessage(err, "Registration failed. Check your connection."));
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <h1 className="auth-brand">SkillSwap</h1>
        <p className="muted center">Create your account</p>

        <label className="field">
          <span>Name</span>
          <input value={form.name} onChange={update("name")} autoComplete="name" required maxLength={80} />
        </label>
        <label className="field">
          <span>Email</span>
          <input type="email" value={form.email} onChange={update("email")} autoComplete="email" required />
        </label>
        <label className="field">
          <span>Password</span>
          <input type="password" value={form.password} onChange={update("password")}
            autoComplete="new-password" minLength={6} required />
          <small className="muted">At least 6 characters</small>
        </label>

        {error && <p className="alert alert-error" role="alert">{error}</p>}

        <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="muted center small">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </main>
  );
}
