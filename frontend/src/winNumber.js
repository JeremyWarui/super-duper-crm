// Half the projected votes plus one, as the server computes it; turnoutPct is a whole number.
export function winNumber(registered, turnoutPct) {
  if (!registered || !turnoutPct) return null;
  return Math.floor((registered * turnoutPct) / 200) + 1;
}
