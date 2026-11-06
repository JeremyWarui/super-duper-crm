import { useEffect, useState } from "react";

/** Whether a CSS media query matches now; false where the browser can't tell. */
export function useMedia(query) {
  const get = () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query).matches : false);
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const list = window.matchMedia(query);
    const on = () => setMatches(list.matches);
    on();
    list.addEventListener?.("change", on);
    return () => list.removeEventListener?.("change", on);
  }, [query]);
  return matches;
}
