// Erasing someone's personal details: one press asks, the second does it. No browser dialog.
import { useState } from "react";
import { Button } from "@/components/ui/button";

export default function EraseButton({ name, onErase, pending }) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return <Button size="sm" shape="rounded" variant="danger" aria-label={`Erase ${name}`} onClick={() => setAsking(true)}>Erase</Button>;
  }
  return (
    <span className="inline-flex flex-wrap items-center justify-end gap-2">
      <span className="text-small text-muted-foreground">Erase for good?</span>
      <Button size="sm" shape="rounded" variant="danger" disabled={pending} onClick={() => onErase(() => setAsking(false))}>
        {pending ? "Erasing…" : `Yes, erase ${name}`}
      </Button>
      <Button size="sm" shape="rounded" variant="ghost" onClick={() => setAsking(false)}>Cancel</Button>
    </span>
  );
}
