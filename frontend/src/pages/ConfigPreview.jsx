import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Spinner } from "../components.jsx";

// Minimal, safe syntax highlighting: escape first, then wrap comments and the
// block keywords. Never inject raw content into innerHTML unescaped.
function highlight(conf) {
  const esc = conf
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return esc
    .split("\n")
    .map((line) => {
      if (line.trimStart().startsWith("#"))
        return `<span class="cmt">${line}</span>`;
      return line.replace(
        /^(home_server_pool|home_server|realm)\b/,
        '<span class="kw">$1</span>'
      );
    })
    .join("\n");
}

export default function ConfigPreview({ notify }) {
  const [conf, setConf] = useState(null);
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const load = async () => {
    setConf((await api.config.preview()).content);
  };
  useEffect(() => {
    load();
  }, []);

  const apply = async () => {
    if (!confirm("Write proxy.conf and reload FreeRADIUS?")) return;
    setApplying(true);
    setResult(null);
    setError(null);
    try {
      const r = await api.config.apply();
      setResult(r);
      notify("Config applied");
    } catch (e) {
      // Backend returns {message, output} on validation failure.
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
    navigator.clipboard?.writeText(conf || "");
    notify("Copied to clipboard");
  };

  if (conf === null) return <Spinner />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Config & apply</h1>
          <p>
            Live preview of the generated{" "}
            <span className="mono">proxy.conf</span>. Applying validates it with{" "}
            <span className="mono">freeradius -XC</span> before touching the
            running server.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn ghost" onClick={load}>
            Refresh
          </button>
          <button className="btn primary" disabled={applying} onClick={apply}>
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
            Written to <span className="mono">{result.written_path}</span> ·
            validated: {String(result.validated)} · reloaded:{" "}
            {String(result.reloaded)}
          </div>
          {result.validation_output && result.validated && (
            <pre>{result.validation_output.trim().slice(-600)}</pre>
          )}
        </div>
      )}

      <div className="config-pane">
        <header>
          <span className="path">proxy.conf</span>
          <button className="btn sm ghost" onClick={copy}>
            Copy
          </button>
        </header>
        <pre
          className="conf"
          dangerouslySetInnerHTML={{ __html: highlight(conf) }}
        />
      </div>
    </>
  );
}
