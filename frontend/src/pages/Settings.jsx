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

function RadiusSettings({ notify }) {
  const [mrt, setMrt] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.system.getRadius().then((r) => setMrt(r.max_request_time)).catch(() => setMrt(30));
  }, []);

  const save = async () => {
    setBusy(true);
    try {
      const r = await api.system.setRadius(Number(mrt));
      setMrt(r.max_request_time);
      notify("Applied — FreeRADIUS reloaded");
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  if (mrt === null) return <Spinner />;
  return (
    <fieldset className="settings-section">
      <legend>FreeRADIUS server</legend>
      <Field
        label="Max request time (s)"
        hint="Макс. время обработки запроса. Ограничивает response_window таргетов — для медленного 2FA (push/OTP-подтверждение) поднимите выше самого большого response_window. FR-дефолт 30."
      >
        <input
          type="number"
          min={5}
          max={600}
          value={mrt}
          onChange={(e) => setMrt(e.target.value)}
          style={{ width: 120 }}
        />
      </Field>
      <button className="btn primary" disabled={busy} onClick={save}>
        {busy ? "Applying…" : "Save & apply"}
      </button>
    </fieldset>
  );
}

function MailSettings({ notify }) {
  const [cfg, setCfg] = useState(null);
  const [pwd, setPwd] = useState("");
  const [hasPwd, setHasPwd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    api.system
      .getMail()
      .then((r) => {
        setCfg(r);
        setHasPwd(r.has_password);
      })
      .catch(() =>
        setCfg({
          enabled: false,
          host: "",
          port: 25,
          security: "none",
          username: "",
          from_addr: "",
          to_addrs: "",
        })
      );
  }, []);

  const set = (k) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setCfg((c) => ({ ...c, [k]: v }));
  };

  const save = async () => {
    setBusy(true);
    try {
      const body = { ...cfg, port: Number(cfg.port), password: pwd };
      const r = await api.system.setMail(body);
      setCfg(r);
      setHasPwd(r.has_password);
      setPwd("");
      notify("Настройки почты сохранены");
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      await api.system.testMail("");
      notify("Тестовое письмо отправлено");
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setTesting(false);
    }
  };

  if (cfg === null) return <Spinner />;
  return (
    <fieldset className="settings-section">
      <legend>Почтовый сервер (уведомления)</legend>
      <p className="field-hint" style={{ marginTop: 0, marginBottom: 12 }}>
        SMTP для писем-предупреждений. Сейчас используется для оповещения о
        включении аварийного обхода 2FA (когда пул недоступен — вход по одному
        паролю AD).
      </p>

      <div className="check" style={{ marginBottom: 12 }}>
        <input
          id="mail-enabled"
          type="checkbox"
          checked={cfg.enabled}
          onChange={set("enabled")}
        />
        <label htmlFor="mail-enabled" style={{ margin: 0 }}>
          Отправлять уведомления по почте
        </label>
      </div>

      <div className="grid-2">
        <Field label="SMTP-сервер (хост)" hint="напр. mail.corp.local">
          <input value={cfg.host} onChange={set("host")} placeholder="mail.corp.local" />
        </Field>
        <Field label="Порт" hint="25 без шифрования, 587 STARTTLS, 465 SSL">
          <input type="number" value={cfg.port} onChange={set("port")} />
        </Field>
      </div>

      <Field label="Шифрование" hint="как защищать соединение с SMTP-сервером">
        <select value={cfg.security} onChange={set("security")}>
          <option value="none">без шифрования</option>
          <option value="starttls">STARTTLS</option>
          <option value="ssl">SSL/TLS</option>
        </select>
      </Field>

      <div className="grid-2">
        <Field label="Логин" hint="оставьте пустым, если relay без авторизации">
          <input value={cfg.username} onChange={set("username")} autoComplete="off" />
        </Field>
        <Field
          label="Пароль"
          hint={hasPwd ? "оставьте пустым — сохранённый не меняется" : "пароль SMTP"}
        >
          <input
            type="password"
            value={pwd}
            onChange={(e) => setPwd(e.target.value)}
            placeholder={hasPwd ? "•••••••• (без изменений)" : ""}
            autoComplete="new-password"
          />
        </Field>
      </div>

      <Field label="Адрес отправителя (From)" hint="напр. radius@corp.local">
        <input value={cfg.from_addr} onChange={set("from_addr")} placeholder="radius@corp.local" />
      </Field>
      <Field
        label="Кому писать"
        hint="один или несколько адресов через запятую"
      >
        <input
          value={cfg.to_addrs}
          onChange={set("to_addrs")}
          placeholder="admin@corp.local, security@corp.local"
        />
      </Field>

      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button className="btn primary" disabled={busy} onClick={save}>
          {busy ? "Сохранение…" : "Сохранить"}
        </button>
        <button className="btn ghost" disabled={testing} onClick={test}>
          {testing ? "Отправка…" : "Отправить тест"}
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
    ["radius", "RADIUS"],
    ["mail", "Почта"],
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
      {sub === "radius" && <RadiusSettings notify={notify} />}
      {sub === "mail" && <MailSettings notify={notify} />}
      {sub === "tls" && <TlsSettings notify={notify} />}
      {sub === "host" && <HostInfo />}
    </>
  );
}
