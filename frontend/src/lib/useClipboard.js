import { useState } from "react";

/** `copy(text)` puts text on the clipboard; `copied` is null until tried, then whether it worked. */
export function useClipboard() {
  const [copied, setCopied] = useState(null);
  const copy = (text) =>
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => setCopied(true), () => setCopied(false));
  return { copied, copy };
}
