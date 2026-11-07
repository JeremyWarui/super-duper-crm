import { Button } from "./ui";

/** The page a private link opens: a note and one button that acts on the link, then the server's reply. `action` is the mutation. */
export default function LinkAction({ action, heading, note, label, busyLabel, style }) {
  return (
    <div className="join-shell" style={style}>
      <div className="join-card">
        <div className="join-heading">{heading}</div>
        {action.isSuccess ? (
          <div className="join-message-success">{action.data.message}</div>
        ) : (
          <>
            <div className="join-note">{note}</div>
            {action.error && <div className="join-error">{action.error.message}</div>}
            <Button tone="danger" disabled={action.isPending} onClick={() => action.mutate()} className="join-submit">
              {action.isPending ? busyLabel : label}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
