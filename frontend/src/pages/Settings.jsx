import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Field, FileButton, Spinner } from "../components.jsx";
import LdapSettings from "./LdapSettings.jsx";

function AccessSettings({ notify, onAuthChange }) {
  const [status, setStatus] = useState(null);
  const [allow, setAllow] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [s, a] = await Promise.all([api.auth.status(), api.system.getAccess()]);
    setStatus(s);
    setAllow(a.ip_allowlist || "");
  };
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

  const saveAllow = async () => {
    setBusy(true);
    try {
      await api.system.setAccess(allow);
      notify("IP allowlist saved");
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  if (status === null) return <Spinner />;

  return (
    <>
      <fieldset className="settings-section" style={{ marginBottom: 16 }}>
        <legend>Login</legend>
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
          Off by default. Default admin <span className="mono">admin</span> /{" "}
          <span className="mono">admin</span> — change the password (user menu) first.
        </p>
      </fieldset>

      <fieldset className="settings-section">
        <legend>IP access restriction</legend>
        <Field
          label="Allowed IPs / CIDRs"
          hint="one per line (e.g. 10.0.0.0/24, 192.168.1.5). Empty = allow all. Your own IP must be included or the save is rejected (anti-lockout)."
        >
          <textarea
            value={allow}
            onChange={(e) => setAllow(e.target.value)}
            style={{ minHeight: 90 }}
            placeholder={"10.0.0.0/24\n192.168.1.5"}
          />
        </Field>
        <button className="btn" disabled={busy} onClick={saveAllow}>
          Save allowlist
        </button>
      </fieldset>
    </>
  );
}

function TlsSettings({ notify }) {
  const [info, setInfo] = useState(null);
  const [cert, setCert] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => setInfo(await api.system.getTls());
  useEffect(() => {
    load();
  }, []);

  const [fileKey, setFileKey] = useState(0);

  const replace = async () => {
    setBusy(true);
    try {
      await api.system.replaceTls(cert, key);
      setCert("");
      setKey("");
      setFileKey((k) => k + 1);
      notify("Certificate replaced — nginx reloads shortly");
      await load();
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const regen = async () => {
    setBusy(true);
    try {
      await api.system.regenTls();
      notify("Self-signed certificate regenerated");
      await load();
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  if (info === null) return <Spinner />;

  return (
    <fieldset className="settings-section">
      <legend>Panel HTTPS certificate</legend>
      <p className="field-hint" style={{ margin: "0 0 12px" }}>
        Current: <span className="tag accent">{info.is_self_signed ? "self-signed" : "custom"}</span>{" "}
        {info.subject && <span className="mono">{info.subject}</span>}
        {info.not_after && <> · expires {new Date(info.not_after).toLocaleDateString()}</>}
      </p>
      <Field label="Certificate (PEM file)" hint={cert ? "loaded ✓" : ".pem / .crt"}>
        <FileButton key={`c${fileKey}`} label="Choose certificate"
          accept=".pem,.crt,.cer" onFile={(t) => setCert(t)} disabled={busy} />
      </Field>
      <Field label="Private key (PEM file)" hint={key ? "loaded ✓ · stored encrypted, never shown" : ".pem / .key · stored encrypted"}>
        <FileButton key={`k${fileKey}`} label="Choose private key"
          accept=".pem,.key" onFile={(t) => setKey(t)} disabled={busy} />
      </Field>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn primary" disabled={busy || !cert || !key} onClick={replace}>
          Install certificate
        </button>
        <button className="btn ghost" disabled={busy} onClick={regen}>
          Regenerate self-signed
        </button>
      </div>
    </fieldset>
  );
}

function HostInfo() {
  const [h, setH] = useState(null);
  useEffect(() => {
    api.system.host().then(setH).catch(() => setH({ hostname: "", addresses: [] }));
  }, []);
  if (h === null) return <Spinner />;
  return (
    <fieldset className="settings-section">
      <legend>Host (read-only)</legend>
      <div className="dash-row"><span>Hostname</span><span className="mono">{h.hostname || "—"}</span></div>
      <div className="dash-row">
        <span>IP addresses</span>
        <span className="mono">{h.addresses.length ? h.addresses.join(", ") : "—"}</span>
      </div>
      <p className="field-hint" style={{ marginTop: 8 }}>
        Detected on the host at install time. Changing the host IP is done at the OS level.
      </p>
    </fieldset>
  );
}

export default function Settings({ notify, onAuthChange }) {
  const [sub, setSub] = useState("access");
  const tabs = [
    ["access", "Access"],
    ["ldap", "AD / LDAP"],
    ["tls", "TLS"],
    ["host", "Host"],
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>Panel settings. Change your password from the user menu (top right).</p>
        </div>
      </div>

      <div className="subtabs">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            className={`subtab ${sub === id ? "active" : ""}`}
            onClick={() => setSub(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {sub === "access" && <AccessSettings notify={notify} onAuthChange={onAuthChange} />}
      {sub === "ldap" && <LdapSettings notify={notify} embedded />}
      {sub === "tls" && <TlsSettings notify={notify} />}
      {sub === "host" && <HostInfo />}
    </>
  );
}
