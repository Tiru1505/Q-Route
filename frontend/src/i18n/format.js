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

export function minutesLabel(t, m) {
  if (m == null || Number.isNaN(m)) return '—'
  const total = Math.round(m)
  if (total < 60) return t('units.min', { n: total })
  return t('units.hourMin', {
    h: Math.floor(total / 60),
    m: String(total % 60).padStart(2, '0'),
  })
}

export function kmLabel(t, km) {
  if (km == null || Number.isNaN(km)) return '—'
  // One decimal up to 100 km, none beyond: 8.4 km matters to a driver,
  // 128.3 km does not.
  const n = Number(km)
  return t('units.km', { n: n < 100 ? n.toFixed(1) : Math.round(n) })
}
