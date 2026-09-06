import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

export function Modal({ title, children, onClose }) {
  return (
    <div className="overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, hint, children }) {
  return (
    <div className="field">
      {label && <label>{label}</label>}
      {children}
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export function Spinner() {
  return <div className="spinner">Loading…</div>;
}

export function Empty({ children, action }) {
  return (
    <div className="empty">
      <p>{children}</p>
      {action}
    </div>
  );
}

export function StatusDot({ on }) {
  return <span className={`dot-status ${on ? "on" : "off"}`} />;
}

export function UserMenu({ username, authEnabled, onLogout }) {
  const [open, setOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="user-menu" ref={ref}>
      <button
        className="user-menu-btn"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="who">{username}</span>
        <span className="user-menu-caret">▾</span>
      </button>
      {open && (
        <div className="user-menu-dropdown">
          <button
            className="user-menu-item"
            onClick={() => {
              setOpen(false);
              setPwOpen(true);
            }}
          >
            Change password
          </button>
          {authEnabled && (
            <button
              className="user-menu-item"
              onClick={() => {
                setOpen(false);
                onLogout?.();
              }}
            >
              Log out
            </button>
          )}
        </div>
      )}
      {pwOpen && (
        <ChangePasswordModal
          username={username}
          onClose={() => setPwOpen(false)}
        />
      )}
    </div>
  );
}

export function ChangePasswordModal({ username, onClose }) {
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setErr("");
    setOk("");
    if (pw.length < 4) return setErr("Password must be at least 4 characters");
    if (pw !== confirm) return setErr("Passwords do not match");
    setBusy(true);
    try {
      await api.auth.changePassword(username, pw);
      setOk("Password changed");
      setPw("");
      setConfirm("");
      setTimeout(onClose, 900);
    } catch (e) {
      setErr(e.message || "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`Change password — ${username}`} onClose={onClose}>
      <Field label="New password" hint="min 4 characters">
        <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoFocus />
      </Field>
      <Field label="Confirm new password">
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </Field>
      {err && <div className="err" style={{ marginBottom: 8 }}>{err}</div>}
      {ok && (
        <div style={{ color: "var(--ok)", fontSize: 13, marginBottom: 8 }}>{ok}</div>
      )}
      <div className="modal-actions">
        <button className="btn ghost" onClick={onClose}>
          Cancel
        </button>
        <button className="btn primary" disabled={busy} onClick={save}>
          {busy ? "Saving…" : "Change password"}
        </button>
      </div>
    </Modal>
  );
}
