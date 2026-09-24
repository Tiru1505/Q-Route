/**
 * How a duration or a distance is written, in one place.
 *
 * The same journey was being shown as "51.6 min" on the map, "52 min" in the
 * trip card and "1h 12m" in history — three formats for one number, which
 * reads as three different measurements. A driver wants whole minutes; the
 * decimals belong in the engine, not on screen.
 *
 * Both take `t`, because the units are words: "min" is "मिनट" and "నిమి".
 */

/**
 * The *parts* forms below return the phrase key and its numbers rather than a
 * finished string, so a caller that wants to render the digits itself — the
 * driver's dashboard animates them — gets them from this same rule instead of
 * writing a fourth format. The label forms are those parts, stringified.
 */

export function durationParts(m) {
  if (m == null || Number.isNaN(m)) return null
  const total = Math.round(m)
  if (total < 60) return { tKey: 'units.min', vars: { n: total } }
  return {
    tKey: 'units.hourMin',
    vars: { h: Math.floor(total / 60), m: total % 60 },
    pad: ['m'],
  }
}

export function kmParts(km) {
  if (km == null || Number.isNaN(km)) return null
  // One decimal up to 100 km, none beyond: 8.4 km matters to a driver,
  // 128.3 km does not.
  const n = Number(km)
  return { tKey: 'units.km', vars: { n: n < 100 ? Number(n.toFixed(1)) : Math.round(n) } }
}

export function minutesLabel(t, m) {
  const parts = durationParts(m)
  if (!parts) return '—'
  const vars = parts.pad?.includes('m')
    ? { ...parts.vars, m: String(parts.vars.m).padStart(2, '0') }
    : parts.vars
  return t(parts.tKey, vars)
}

export function kmLabel(t, km) {
  const parts = kmParts(km)
  return parts ? t(parts.tKey, parts.vars) : '—'
}
