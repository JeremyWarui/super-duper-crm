
export function Button({
  children,
  onClick,
  disabled = false,
  primary = false,
  tone,
  type = "button",
  className = "",
  ...props
}) {
  const variant = tone === "danger" ? "danger" : primary ? "primary" : "secondary";
  return (
    <button
      {...props}
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`ui-button ui-button-${variant} ${className}`.trim()}
    >
      {children}
    </button>
  );
}

export function Panel({ children, pad = 18, className = "", style, ...props }) {
  return (
    <div
      {...props}
      className={`ui-panel ${className}`.trim()}
      style={{ padding: pad, ...style }}
    >
      {children}
    </div>
  );
}

export function FieldLabel({ children, className = "" }) {
  return (
    <span className={`ui-field-label ${className}`.trim()}>
      {children}
    </span>
  );
}

export function LoadingState({ message = "Loading…", className = "" }) {
  return <div className={`ui-loading ${className}`.trim()}>{message}</div>;
}

export function ErrorState({ error, message, className = "" }) {
  return (
    <div className={`ui-error ${className}`.trim()}>
      {message || error?.message || "Something went wrong."}
    </div>
  );
}

export function Field({ label, htmlFor, children, error, className = "" }) {
  return (
    <label className={`ui-field ${className}`.trim()} htmlFor={htmlFor}>
      <FieldLabel htmlFor={htmlFor}>{label}</FieldLabel>
      {children}
      {error && <span className="ui-field-error">{error}</span>}
    </label>
  );
}

export function SelectField({
  value,
  onChange,
  disabled = false,
  children,
  className = "",
  ...props
}) {
  return (
    <select
      {...props}
      value={value || ""}
      onChange={(event) => onChange(event.target.value, event)}
      disabled={disabled}
      className={`ui-select ${className}`.trim()}
    >
      {children}
    </select>
  );
}

export const Badge = ({ text, tone = "neutral" }) => <span className={`badge tone-${tone}`}>{text}</span>;
export const Bar = ({ pct, tone }) => <div className="bar"><div className={`bar-fill tone-${tone}`} style={{width: `${Math.min(pct, 100)}%`}} /></div>;
// A pill that toggles, for sort orders and filters.
export const Chip = ({ on, onClick, className = "", children }) => <button type="button" aria-pressed={on} onClick={onClick} className={`chip ${on ? "chip-on" : ""} ${className}`.trim()}>{children}</button>;
export const PageTitle = ({ title, sub, action }) => <div className="flex flex-wrap items-end justify-between gap-3 page-head"><div><div className="page-title">{title}</div>{sub && <div className="page-sub">{sub}</div>}</div>{action}</div>;

export const Modal = ({ title, sub, onClose, locked, children }) => (
  <div onClick={locked ? undefined : onClose} className="modal-backdrop">
    <div onClick={(e) => e.stopPropagation()} className="modal">
      <div className="flex items-start justify-between modal-head">
        <div><div className="modal-title">{title}</div>{sub && <div className="modal-sub">{sub}</div>}</div>
        <button onClick={onClose} className="modal-close">×</button>
      </div>
      <div className="modal-body">{children}</div>
    </div>
  </div>
);

// A password shown once; a click on the backdrop leaves it open.
export const PasswordModal = ({ title, password, onClose, children }) => (
  <Modal title={title} sub="Write the password down now. It is shown once." onClose={onClose} locked>
    <div className="modal-text">{children}</div>
    <div className="secret-box">
      <div className="meta">Password</div>
      <div className="secret-value">{password}</div>
    </div>
    <div className="flex justify-end gap-2 form-actions"><Button primary onClick={onClose}>Done</Button></div>
  </Modal>
);
