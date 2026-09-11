import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Spinner, ConfirmDialog } from "../components.jsx";

// Minimal, safe syntax highlighting: escape first, then wrap comments and the
// block keywords. Never inject raw content into innerHTML unescaped.
function highlight(conf) {
  const esc = (conf || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return esc
    .split("\n")
    .map((line) => {
      if (line.trimStart().startsWith("#"))
        return `<span class="cmt">${line}</span>`;
      return line.replace(
        /^(\s*)(home_server_pool|home_server|realm|client|policy)\b/,
        '$1<span class="kw">$2</span>'
      );
    })
    .join("\n");
}

// The files the panel writes on apply (ldap module/CA are shown in Settings → AD/LDAP).
const FILES = [
  { id: "proxy", label: "proxy.conf" },
  { id: "clients", label: "clients.conf" },
  { id: "policy", label: "policy.d/radiuspanel" },
];

export default function ConfigPreview({ notify }) {
  const [files, setFiles] = useState(null); // { proxy, clients, policy }
  const [tab, setTab] = useState("proxy");
  const [applying, setApplying] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const load = async () => {
    const [proxy, clients, policy] = await Promise.all([
      api.config.preview().then((r) => r.content),
      api.config.clientsPreview(),
      api.config.policyPreview(),
    ]);
    setFiles({ proxy, clients, policy });
  };
  useEffect(() => {
    load().catch((e) => notify(e.message, "err"));
  }, []);

  const doApply = async () => {
    setConfirmOpen(false);
    setApplying(true);
    setResult(null);
    setError(null);
    try {
      const r = await api.config.apply();
      setResult(r);
      notify("Config applied");
    } catch (e) {
      let parsed;
      try {
        parsed = JSON.parse(e.message);
      } catch {
        parsed = { message: e.message };
      }
      setError(parsed);
      notify("Apply failed", "err");
    } finally {
      setApplying(false);
    }
  };

  const copy = () => {
    navigator.clipboard?.writeText(files?.[tab] || "");
    notify("Copied to clipboard");
  };

  if (files === null) return <Spinner />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Config & apply</h1>
          <p>
            Live preview of every file the panel generates. Applying writes them
            all, validates with <span className="mono">freeradius -XC</span>, and
            rolls back on failure before reloading.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn ghost" onClick={() => load().catch((e) => notify(e.message, "err"))}>
            Refresh
          </button>
          <button className="btn primary" disabled={applying} onClick={() => setConfirmOpen(true)}>
            {applying ? "Applying…" : "Apply & reload"}
          </button>
        </div>
      </div>

      {error && (
        <div className="result err">
          <h3 style={{ color: "var(--danger)" }}>
            Validation failed — live config untouched
          </h3>
          <div className="muted">{error.message}</div>
          {error.output && <pre>{error.output}</pre>}
        </div>
      )}

      {result && (
        <div className="result ok">
          <h3 style={{ color: "var(--ok)" }}>Applied</h3>
          <div className="muted">
            Written:{" "}
            <span className="mono">{(result.written_paths || []).join(", ")}</span>{" "}
            · validated: {String(result.validated)} · reloaded:{" "}
            {String(result.reloaded)}
          </div>
          {result.validation_output && result.validated && (
            <pre>{result.validation_output.trim().slice(-600)}</pre>
          )}
        </div>
      )}

      <div className="subtabs">
        {FILES.map((f) => (
          <button
            key={f.id}
            className={`subtab ${tab === f.id ? "active" : ""}`}
            onClick={() => setTab(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="config-pane">
        <header>
          <span className="path">{FILES.find((f) => f.id === tab)?.label}</span>
          <button className="btn sm ghost" onClick={copy}>Copy</button>
        </header>
        <pre className="conf" dangerouslySetInnerHTML={{ __html: highlight(files[tab]) }} />
      </div>

      {confirmOpen && (
        <ConfirmDialog
          title="Apply configuration"
          message="Write proxy.conf, clients.conf and policy.d/radiuspanel, validate with freeradius -XC, and reload FreeRADIUS? A failed validation rolls back automatically."
          confirmLabel="Apply & reload"
          onConfirm={doApply}
          onClose={() => setConfirmOpen(false)}
        />
      )}
    </>
  );
}
