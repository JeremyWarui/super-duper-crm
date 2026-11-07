import { Button, ErrorState, FieldLabel, LoadingState, Panel } from "../../components/ui";
import { useClipboard } from "../../lib/useClipboard";

export const Card = Panel;
export const Label = FieldLabel;
export const Btn = Button;
export const PrimaryBtn = ({ children, onClick, disabled }) => <Button primary onClick={onClick} disabled={disabled}>{children}</Button>;
export const Loading = LoadingState;
export const ErrorMsg = ErrorState;

// Copy a sign-up link, or send it on WhatsApp with a line saying what it is for.
export function ShareLink({ link, message }) {
  const { copied, copy } = useClipboard();
  const whatsapp = `https://wa.me/?text=${encodeURIComponent(`${message} ${link}`)}`;
  return (
    <div className="flex flex-wrap gap-2 share-row">
      <Btn onClick={() => copy(link)}>{copied ? "Copied" : "Copy link"}</Btn>
      <a href={whatsapp} target="_blank" rel="noreferrer" className="ui-button ui-button-outline">Share on WhatsApp</a>
      {copied === false && <span className="field-hint share-hint">This browser blocked copying; select the link above instead.</span>}
    </div>
  );
}
