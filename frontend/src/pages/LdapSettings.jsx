import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Field, Spinner } from "../components.jsx";

export default function LdapSettings({ notify }) {
  const [form, setForm] = useState(null);
  const [hasPassword, setHasPassword] = useState(false);
  const [password, setPassword] = useState("");
  const [hasCa, setHasCa] = useState(false);
  const [caCert, setCaCert] = useState("");
  const [caFileName, setCaFileName] = useState("");
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState("");

  const loadPreview = async () => {
    const res = await fetch(api.ldap.previewUrl);
    setPreview(await res.text());
  };

  const load = async () => {
    const s = await api.ldap.get();
    setHasPassword(s.has_password);
    setHasCa(s.has_ca_cert);
    setForm(s);
    await loadPreview();
  };
  useEffect(() => {
    load();
  }, []);

  const set = (k) => (e) => {
    const v =
      e.target.type === "checkbox"
        ? e.target.checked
        : e.target.type === "number"
        ? Number(e.target.value)
        : e.target.value;
    setForm((f) => ({ ...f, [k]: v }));
  };

  const onCaFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCaFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => setCaCert(String(reader.result || ""));
    reader.readAsText(file);
  };

  const save = async () => {
    setSaving(true);
    try {
      // Empty password/ca fields keep stored values.
      await api.ldap.update({ ...form, bind_password: password, ca_cert: caCert });
      setPassword("");
      setCaCert("");
      setCaFileName("");
      notify("AD / LDAP settings saved");
      await load();
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setSaving(false);
    }
  };

  if (form === null) return <Spinner />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>AD / LDAP</h1>
          <p>
            Active Directory connection for the per-realm group gate. Rendered
            into a FreeRADIUS <span className="mono">mods-enabled/ldap</span>{" "}
            module. The bind password is write-only and never shown.
          </p>
        </div>
        <button className="btn primary" disabled={saving} onClick={save}>
          {saving ? "Saving…" : "Save settings"}
        </button>
      </div>

      <div className="config-grid">
        <div style={{ maxWidth: 720 }}>
          <div className="check" style={{ marginBottom: 16 }}>
            <input
              id="ldap-enabled"
              type="checkbox"
              checked={form.enabled}
              onChange={set("enabled")}
            />
            <label htmlFor="ldap-enabled" style={{ margin: 0 }}>
              Enable AD group checking
            </label>
          </div>

          <div className="grid-2">
            <Field label="Server host / IP">
              <input
                value={form.server}
                onChange={set("server")}
                placeholder="dc1.corp.example.com"
              />
            </Field>
            <Field label="Port">
              <input type="number" value={form.port} onChange={set("port")} />
            </Field>
          </div>

          <div className="grid-2">
            <div className="check">
              <input
                id="ldaps"
                type="checkbox"
                checked={form.use_ldaps}
                onChange={set("use_ldaps")}
              />
              <label htmlFor="ldaps" style={{ margin: 0 }}>
                LDAPS (ldaps://, port 636)
              </label>
            </div>
            <div className="check">
              <input
                id="starttls"
                type="checkbox"
                checked={form.start_tls}
                onChange={set("start_tls")}
              />
              <label htmlFor="starttls" style={{ margin: 0 }}>
                StartTLS (plain port)
              </label>
            </div>
          </div>

          <Field label="Bind DN" hint="service account used to search AD">
            <input
              value={form.bind_dn}
              onChange={set("bind_dn")}
              placeholder="CN=svc-radius,OU=Service,DC=corp,DC=example,DC=com"
            />
          </Field>
          <Field
            label="Bind password"
            hint={
              hasPassword
                ? "a password is stored — leave blank to keep it"
                : "no password stored yet"
            }
          >
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={hasPassword ? "•••••••• (unchanged)" : ""}
            />
          </Field>

          <Field label="Base DN">
            <input
              value={form.base_dn}
              onChange={set("base_dn")}
              placeholder="DC=corp,DC=example,DC=com"
            />
          </Field>

          <div className="grid-2">
            <Field label="Group base DN" hint="blank → same as Base DN">
              <input
                value={form.group_base_dn}
                onChange={set("group_base_dn")}
              />
            </Field>
            <Field label="Group filter">
              <input
                value={form.group_filter}
                onChange={set("group_filter")}
              />
            </Field>
          </div>

          <div className="grid-2">
            <Field label="Membership attribute">
              <input
                value={form.group_membership_attribute}
                onChange={set("group_membership_attribute")}
              />
            </Field>
            <Field label="Membership cache TTL (s)">
              <input
                type="number"
                value={form.cache_ttl}
                onChange={set("cache_ttl")}
              />
            </Field>
          </div>

          <Field label="Network timeout (s)">
            <input
              type="number"
              value={form.net_timeout}
              onChange={set("net_timeout")}
            />
          </Field>

          <div className="section-heading" style={{ margin: "18px 0 8px", fontWeight: 600 }}>
            TLS (LDAPS / StartTLS)
          </div>
          <div className="grid-2">
            <Field
              label="Validate DC certificate"
              hint="demand = strict (needs CA); never = skip (insecure, diagnostics)"
            >
              <select
                value={form.tls_require_cert}
                onChange={set("tls_require_cert")}
              >
                <option value="never">never</option>
                <option value="allow">allow</option>
                <option value="try">try</option>
                <option value="demand">demand</option>
                <option value="hard">hard</option>
              </select>
            </Field>
            <Field label="Min TLS version">
              <select
                value={form.tls_min_version}
                onChange={set("tls_min_version")}
              >
                <option value="1.2">1.2</option>
                <option value="1.3">1.3</option>
                <option value="1.1">1.1</option>
                <option value="1.0">1.0</option>
              </select>
            </Field>
          </div>
          <Field
            label="Root CA certificate (PEM)"
            hint={
              hasCa
                ? "a CA is stored — upload/paste to replace, or type - to clear"
                : "upload the CA that signed the DC cert (LDAPS needs it)"
            }
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 8,
              }}
            >
              <label className="btn ghost sm" style={{ margin: 0 }}>
                Choose file…
                <input
                  type="file"
                  accept=".pem,.crt,.cer,.txt"
                  onChange={onCaFile}
                  hidden
                />
              </label>
              <span className="muted" style={{ fontSize: 12 }}>
                {caFileName || "no file selected"}
              </span>
            </div>
            <textarea
              value={caCert}
              onChange={(e) => setCaCert(e.target.value)}
              placeholder={
                hasCa
                  ? "-----BEGIN CERTIFICATE----- (stored — leave blank to keep)"
                  : "-----BEGIN CERTIFICATE-----"
              }
              style={{ minHeight: 96 }}
            />
          </Field>
        </div>

        <div className="config-pane">
          <header>
            <span>Rendered module (preview)</span>
            <span className="path">mods-enabled/ldap</span>
          </header>
          <pre className="conf">{preview}</pre>
        </div>
      </div>
    </>
  );
}
