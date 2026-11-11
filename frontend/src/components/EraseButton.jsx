// Erasing someone's personal details: one press asks, the second does it. No browser dialog.
import { Confirm } from "@/components/ui/confirm";

/** `onErase(close)` erases; `close()` puts the button back. */
export default function EraseButton({ name, onErase, pending }) {
  return (
    <Confirm size="sm" label="Erase" ariaLabel={`Erase ${name}`} question="Erase for good?" yes={pending ? "Erasing…" : `Yes, erase ${name}`}
      pending={pending} onConfirm={onErase} className="justify-end" />
  );
}
