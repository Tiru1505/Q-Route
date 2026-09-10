import { useEffect, useState } from 'react'
import { Bike, Bus, Car, CarTaxiFront, Info, Truck } from 'lucide-react'
import { getVehicles } from '../services/api'
import { useApp } from '../store/AppContext'

/**
 * How is the user travelling?
 *
 * The choice changes the route, not just the label. It reaches the cost model
 * every algorithm prices roads through, where it does two things: roads the
 * vehicle may not use cost infinity, and time on each road uses the slower of
 * the road's speed and the vehicle's top speed.
 *
 * The options, what each avoids and how fast it can go all come from
 * GET /api/vehicles — the same table the router applies — so this panel cannot
 * describe a rule that is not being used. Most of those rules are assumptions
 * rather than local law, and the panel says so for every vehicle it applies to.
 */

// lucide has no motorcycle, only a bicycle, so the two-wheeler is drawn here
// in the same stroke style.
function Motorbike({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true">
      <circle cx="5" cy="17" r="3" />
      <circle cx="19" cy="17" r="3" />
      <path d="M5 17 9 11h5l2 3 3 3" />
      <path d="m16 14 1-6h2" />
      <path d="M8 11h5" />
    </svg>
  )
}

const ICONS = {
  car: Car,
  two_wheeler: Motorbike,
  auto_rickshaw: CarTaxiFront,
  bus: Bus,
  truck: Truck,
  bicycle: Bike,
}

// OSM road classes, in words a traveller would use.
const ROAD_WORDS = {
  motorway: 'expressways',
  motorway_link: 'expressways',
  trunk: 'national highways',
  trunk_link: 'national highways',
  residential: 'residential streets',
  living_street: 'residential streets',
}

function ruleText(v) {
  const avoid = [...new Set((v.avoids || []).map((c) => ROAD_WORDS[c] || c))]
  const parts = []
  if (avoid.length) parts.push(`Avoids ${avoid.join(' and ')}`)
  if (v.maxSpeedKph) parts.push(`top speed ${v.maxSpeedKph} km/h`)
  return parts.length ? parts.join(' · ') : 'No restrictions — the road speeds are car speeds'
}

export default function VehicleSelector() {
  const { vehicle, setVehicle } = useApp()
  const [profiles, setProfiles] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    getVehicles()
      .then((res) => { if (alive) setProfiles(res) })
      .catch((err) => { if (alive) setError(err.message || 'Vehicle profiles unavailable') })
    return () => { alive = false }
  }, [])

  // A remembered choice the backend no longer offers falls back to its
  // default, rather than sending an id the router would reject.
  useEffect(() => {
    if (!profiles) return
    if (!profiles.vehicles.some((v) => v.id === vehicle)) setVehicle(profiles.default)
  }, [profiles, vehicle, setVehicle])

  if (error) {
    return (
      <div className="field route-field">
        <label>Your vehicle</label>
        <p className="vehicle-rule">Vehicle profiles are unavailable, so routes are computed for a car.</p>
      </div>
    )
  }

  const list = profiles?.vehicles || []
  const active = list.find((v) => v.id === vehicle)

  return (
    <div className="field route-field">
      <label>Your vehicle</label>

      <div className="segmented vehicle-grid" role="radiogroup" aria-label="Your vehicle">
        {list.map((v) => {
          const Icon = ICONS[v.id] || Car
          const on = v.id === vehicle
          return (
            <button
              key={v.id}
              type="button"
              role="radio"
              aria-checked={on}
              data-active={on}
              className="vehicle-opt"
              onClick={() => setVehicle(v.id)}
              title={v.basis}
            >
              <Icon size={16} />
              <span>{v.label}</span>
            </button>
          )
        })}
        {!profiles && <span className="vehicle-loading">Loading vehicles…</span>}
      </div>

      {active && (
        <p className="vehicle-rule">
          <Info size={11} />
          <span>
            {ruleText(active)}
            {active.assumption && <em className="vehicle-assumed"> · assumed rule</em>}
          </span>
        </p>
      )}
    </div>
  )
}
