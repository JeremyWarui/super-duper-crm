
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
