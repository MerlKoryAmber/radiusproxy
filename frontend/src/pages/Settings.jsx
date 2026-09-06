import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Spinner } from "../components.jsx";

export default function Settings({ notify, onAuthChange }) {
  const [status, setStatus] = useState(null);
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
      notify(next ? "Login required — sign in on next action" : "Login disabled");
      await load();
      onAuthChange?.();
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  if (status === null) return <Spinner />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>Panel settings. Change your password from the user menu (top right).</p>
        </div>
      </div>

      <fieldset className="settings-section">
        <legend>Access</legend>
        <div className="check">
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
        <p className="field-hint" style={{ marginTop: 8 }}>
          Off by default for development. Default admin is{" "}
          <span className="mono">admin</span> / <span className="mono">admin</span> —
          change the password (user menu) before enabling in production.
        </p>
      </fieldset>
    </>
  );
}
