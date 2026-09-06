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
