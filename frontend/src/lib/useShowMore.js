import { useState } from "react";

/** The first `step` rows of a list already in hand, and `more()` to show `step` more; `reset()` goes back to the first rows. */
export function useShowMore(rows, step = 20) {
  const [count, setCount] = useState(step);
  const all = rows || [];
  return {
    visible: all.slice(0, count),
    shown: Math.min(count, all.length),
    total: all.length,
    hasMore: count < all.length,
    more: () => setCount((n) => n + step),
    reset: () => setCount(step),
  };
}
