import { useEffect, useState } from "react";
import { api, setToken } from "../api.js";
import { Field, Spinner } from "../components.jsx";

export default function Access({ notify, onAuthChange }) {
  const [status, setStatus] = useState(null);
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => setStatus(await api.auth.status());
  useEffect(() => {
    load();
  }, []);

  const toggle = async () => {
    setBusy(true);
    try {
      const next = !status.auth_enabled;
      await api.auth.setEnabled(next);
      notify(next ? "Auth enabled — login now required" : "Auth disabled");
      await load();
      onAuthChange?.();
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const changePw = async () => {
    setBusy(true);
    try {
      await api.auth.changePassword("admin", pw);
      setPw("");
      notify("Password changed for admin");
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const logout = () => {
    setToken("");
    onAuthChange?.();
  };

  if (status === null) return <Spinner />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Access</h1>
          <p>Panel login. Off by default for development; turn on for production.</p>
        </div>
        {status.user && (
          <button className="btn ghost" onClick={logout}>
            Log out ({status.user})
          </button>
        )}
      </div>

      <div className="config-pane" style={{ padding: 20, maxWidth: 560 }}>
        <div className="check" style={{ marginBottom: 8 }}>
          <input
            id="auth-enabled"
            type="checkbox"
            checked={status.auth_enabled}
            onChange={toggle}
            disabled={busy}
          />
          <label htmlFor="auth-enabled" style={{ margin: 0 }}>
            Require login to use the panel
          </label>
        </div>
        <p className="muted" style={{ fontSize: 12, margin: "0 0 20px" }}>
          Default admin is <span className="mono">admin</span> /{" "}
          <span className="mono">admin</span> — change the password before enabling.
        </p>

        <Field label="New password for admin" hint="min 4 chars">
          <input
            type="password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
          />
        </Field>
        <button
          className="btn"
          disabled={busy || pw.length < 4}
          onClick={changePw}
        >
          Change password
        </button>
      </div>
    </>
  );
}
