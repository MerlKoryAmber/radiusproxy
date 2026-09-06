import { useState } from "react";
import { api, setToken } from "../api.js";

export default function Login({ onLoggedIn }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r = await api.auth.login(username, password);
      setToken(r.token);
      onLoggedIn?.();
    } catch {
      setErr("Invalid username or password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <form className="login-box" onSubmit={submit}>
        <div className="login-brand">
          <span className="brand-mark">
            <img src="/logo.png" alt="" />
          </span>
          <div>
            <b>RADIUS Proxy</b>
            <span>3.2</span>
          </div>
        </div>
        <div className="field">
          <label>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
          />
        </div>
        {err && <div className="err" style={{ marginBottom: 10 }}>{err}</div>}
        <button className="btn primary" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
