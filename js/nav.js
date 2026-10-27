// Small in-app navigation memory, so screens can offer "Back" and return you to the same place.
// (A home-screen app on iPhone has no browser back button.)

let depth = 0;
export const visited = () => { depth += 1; };
/** True when there is an earlier screen in this session to go back to. */
export const canGoBack = () => depth > 1;

export function goBack(fallback) {
  if (canGoBack()) history.back();
  else location.hash = fallback;
}

// Where you were on a screen (e.g. the word you tapped in the Reader), restored when you come back to it.
const places = new Map();
export const remember = (hash, info) => places.set(hash, info);
export const recall = (hash) => { const p = places.get(hash); places.delete(hash); return p; };

// A "Back to …" link shown once on the screen you jump to (e.g. a verse opened from the dictionary).
let pending = null;
export const offerReturn = (targetHash, label) => { pending = { targetHash, label }; };
export function takeReturn(hash) {
  const p = pending && pending.targetHash === hash ? pending : null;
  pending = null;
  return p;
}
