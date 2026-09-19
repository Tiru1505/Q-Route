import { STRINGS } from './strings'

/**
 * Names that arrive as data rather than as page text: the route objectives
 * and the vehicles the server describes.
 *
 * Translated by id when this app knows the id, and otherwise left as whatever
 * the server called it. A vehicle added to the backend tomorrow then shows up
 * in English instead of disappearing or showing a key.
 */
export function labelFor(t, kind, id, fallback) {
  const key = `${kind}.${id}`
  return STRINGS[key] ? t(key) : (fallback ?? id)
}
