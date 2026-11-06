import { PageHeader, useSlottedHeader } from "../layout/AppPage";
import { useEffect, useId, useRef } from "react";

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
// The legacy root's full-screen height and ground, undone so only its button styles apply.
const HEADER_ACTIONS = { minHeight: 0, background: "transparent" };

// In the party console the title and its actions move into the frosted page header.
export function PageTitle({ title, sub, action }) {
  const header = useSlottedHeader(<PageHeader title={title} sub={sub} actions={action && <div className="legacy" style={HEADER_ACTIONS}>{action}</div>} />);
  if (header.slotted) return header.rendered;
  return <div className="flex flex-wrap items-end justify-between gap-3 page-head"><div><div className="page-title">{title}</div>{sub && <div className="page-sub">{sub}</div>}</div>{action}</div>;
}

const FOCUSABLE = "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

// Tab from the last control goes to the first, and Shift+Tab from the first to the last.
function keepFocusInside(box, e) {
  const controls = [...box.querySelectorAll(FOCUSABLE)];
  if (!controls.length) return;
  const first = controls[0];
  const last = controls[controls.length - 1];
  const at = document.activeElement;
  if (e.shiftKey && (at === first || at === box)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && at === last) {
    e.preventDefault();
    first.focus();
  }
}

// Takes focus when it opens and gives it back when it closes; Escape closes it unless `locked`.
export function Modal({ title, sub, onClose, locked, children }) {
  const box = useRef(null);
  const titleId = useId();
  useEffect(() => {
    const before = document.activeElement;
    box.current?.focus();
    return () => before?.focus?.();
  }, []);
  const onKeyDown = (e) => {
    if (e.key === "Escape" && !locked) {
      e.stopPropagation();
      onClose();
    }
    if (e.key === "Tab") keepFocusInside(box.current, e);
  };
  return (
    <div onClick={locked ? undefined : onClose} className="modal-backdrop">
      <div
        ref={box}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        onClick={(e) => e.stopPropagation()}
        className="modal"
      >
        <div className="flex items-start justify-between modal-head">
          <div><div id={titleId} className="modal-title">{title}</div>{sub && <div className="modal-sub">{sub}</div>}</div>
          <button type="button" aria-label="Close" onClick={onClose} className="modal-close">×</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

// A password shown once; a click on the backdrop leaves it open.
// What happened to a new login's emailed invite, or a reset link: "email" or "none".
export const linkNote = (sent, username) =>
  sent === "email"
    ? `We emailed ${username} a link to choose their password.`
    : `${username} has no email, so no link could be sent. Add an email to their login, then send a reset link from the console.`;

// Shown after a login is made: the invite went out by email, or could not.
export const InviteModal = ({ title, invite, username, onClose, children }) => (
  <Modal title={title} sub={linkNote(invite, username)} onClose={onClose}>
    {children && <div className="modal-text">{children}</div>}
    <div className="flex justify-end gap-2 form-actions"><Button primary onClick={onClose}>Done</Button></div>
  </Modal>
);
