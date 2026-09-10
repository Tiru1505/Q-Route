/**
 * Central mock data store.
 *
 * Every number in this file is DEMO DATA. Nothing here comes from a real
 * benchmark run. When the FastAPI backend is ready, src/services/api.js swaps
 * these objects for real responses — the components never change, because they
 * only ever consume the shapes defined here.
 *
 * Coordinates are genuine Hyderabad locations, so the map is geographically
 * correct even while the routing numbers are illustrative.
 */

export const DEMO_DATA_NOTICE =
  'Demo data — not a validated benchmark run. Replace via src/services/api.js.'

export const HYDERABAD_CENTER = [17.4065, 78.4772]

/* ------------------------------------------------------------------ places */
// Routing landmarks, mirroring config/places.yaml.
//
// GENERATED — regenerate with `python scripts/build_places.py`, which
// rewrites both files from the same geocoded source. Hand-editing one of
// them is how the two drift apart, and a coordinate that disagrees between
// frontend and engine routes to a different place than the label claims.
export const LOCATIONS = [
  { id: 'hyderabad_hitec_city', name: 'Hitec City', city: 'hyderabad', coords: [17.449005, 78.383138] },
  { id: 'hyderabad_gachibowli', name: 'Gachibowli', city: 'hyderabad', coords: [17.443622, 78.351964] },
  { id: 'hyderabad_madhapur', name: 'Madhapur', city: 'hyderabad', coords: [17.440892, 78.39163] },
  { id: 'hyderabad_kondapur', name: 'Kondapur', city: 'hyderabad', coords: [17.458791, 78.373056] },
  { id: 'hyderabad_jubilee_hills', name: 'Jubilee Hills', city: 'hyderabad', coords: [17.430836, 78.410288] },
  { id: 'hyderabad_banjara_hills', name: 'Banjara Hills', city: 'hyderabad', coords: [17.417746, 78.439901] },
  { id: 'hyderabad_panjagutta', name: 'Panjagutta', city: 'hyderabad', coords: [17.425424, 78.451752] },
  { id: 'hyderabad_ameerpet', name: 'Ameerpet', city: 'hyderabad', coords: [17.437501, 78.448251] },
  { id: 'hyderabad_begumpet', name: 'Begumpet', city: 'hyderabad', coords: [17.446195, 78.463016] },
  { id: 'hyderabad_secunderabad', name: 'Secunderabad', city: 'hyderabad', coords: [17.433725, 78.500683] },
  { id: 'hyderabad_mehdipatnam', name: 'Mehdipatnam', city: 'hyderabad', coords: [17.394263, 78.434251] },
  { id: 'hyderabad_charminar', name: 'Charminar', city: 'hyderabad', coords: [17.361602, 78.474642] },
  { id: 'hyderabad_dilsukhnagar', name: 'Dilsukhnagar', city: 'hyderabad', coords: [17.368443, 78.52286] },
  { id: 'hyderabad_uppal', name: 'Uppal', city: 'hyderabad', coords: [17.402509, 78.561256] },
  { id: 'hyderabad_kukatpally', name: 'Kukatpally', city: 'hyderabad', coords: [17.493084, 78.405441] },
  { id: 'hyderabad_miyapur', name: 'Miyapur', city: 'hyderabad', coords: [17.498161, 78.356763] },
  { id: 'hyderabad_lb_nagar', name: 'LB Nagar', city: 'hyderabad', coords: [17.350162, 78.551094] },
  { id: 'hyderabad_shamshabad', name: 'Shamshabad', city: 'hyderabad', coords: [17.257207, 78.345104] },
  { id: 'hyderabad_attapur', name: 'Attapur', city: 'hyderabad', coords: [17.367224, 78.430728] },
  { id: 'hyderabad_alwal', name: 'Alwal', city: 'hyderabad', coords: [17.502229, 78.508858] },
  { id: 'bengaluru_koramangala', name: 'Koramangala', city: 'bengaluru', coords: [12.935737, 77.624081] },
  { id: 'bengaluru_indiranagar', name: 'Indiranagar', city: 'bengaluru', coords: [12.973291, 77.640467] },
  { id: 'bengaluru_whitefield', name: 'Whitefield', city: 'bengaluru', coords: [12.995743, 77.757949] },
  { id: 'bengaluru_electronic_city', name: 'Electronic City', city: 'bengaluru', coords: [12.84876, 77.648253] },
  { id: 'bengaluru_jayanagar', name: 'Jayanagar', city: 'bengaluru', coords: [12.929273, 77.582423] },
  { id: 'bengaluru_malleshwaram', name: 'Malleshwaram', city: 'bengaluru', coords: [13.002735, 77.570325] },
  { id: 'bengaluru_hebbal', name: 'Hebbal', city: 'bengaluru', coords: [13.038218, 77.5919] },
  { id: 'bengaluru_marathahalli', name: 'Marathahalli', city: 'bengaluru', coords: [12.955257, 77.698416] },
  { id: 'bengaluru_btm_layout', name: 'BTM Layout', city: 'bengaluru', coords: [12.914001, 77.610282] },
  { id: 'bengaluru_rajajinagar', name: 'Rajajinagar', city: 'bengaluru', coords: [13.000523, 77.549617] },
  { id: 'bengaluru_banashankari', name: 'Banashankari', city: 'bengaluru', coords: [12.92782, 77.556621] },
  { id: 'bengaluru_yeshwanthpur', name: 'Yeshwanthpur', city: 'bengaluru', coords: [13.017694, 77.555501] },
  { id: 'bengaluru_kr_puram', name: 'KR Puram', city: 'bengaluru', coords: [13.007516, 77.695935] },
  { id: 'bengaluru_bellandur', name: 'Bellandur', city: 'bengaluru', coords: [12.932049, 77.684292] },
  { id: 'bengaluru_hsr_layout', name: 'HSR Layout', city: 'bengaluru', coords: [12.911623, 77.638862] },
  { id: 'bengaluru_basavanagudi', name: 'Basavanagudi', city: 'bengaluru', coords: [12.941726, 77.575502] },
  { id: 'bengaluru_yelahanka', name: 'Yelahanka', city: 'bengaluru', coords: [13.100698, 77.596345] },
  { id: 'bengaluru_majestic_bangalore', name: 'Majestic Bangalore', city: 'bengaluru', coords: [13.023739, 77.548179] },
  { id: 'bengaluru_mg_road_bangalore', name: 'MG Road Bangalore', city: 'bengaluru', coords: [12.974321, 77.615002] },
  { id: 'bengaluru_kengeri', name: 'Kengeri', city: 'bengaluru', coords: [12.917657, 77.483757] },
  { id: 'delhi_connaught_place', name: 'Connaught Place', city: 'delhi', coords: [28.63177, 77.21938] },
  { id: 'delhi_karol_bagh', name: 'Karol Bagh', city: 'delhi', coords: [28.652998, 77.189023] },
  { id: 'delhi_dwarka', name: 'Dwarka', city: 'delhi', coords: [28.615887, 77.022434] },
  { id: 'delhi_rohini', name: 'Rohini', city: 'delhi', coords: [28.706308, 77.108789] },
  { id: 'delhi_saket', name: 'Saket', city: 'delhi', coords: [28.521168, 77.202224] },
  { id: 'delhi_hauz_khas', name: 'Hauz Khas', city: 'delhi', coords: [28.549809, 77.207764] },
  { id: 'delhi_lajpat_nagar', name: 'Lajpat Nagar', city: 'delhi', coords: [28.566092, 77.243285] },
  { id: 'delhi_janakpuri', name: 'Janakpuri', city: 'delhi', coords: [28.621927, 77.087476] },
  { id: 'delhi_pitampura', name: 'Pitampura', city: 'delhi', coords: [28.703268, 77.13225] },
  { id: 'delhi_vasant_kunj', name: 'Vasant Kunj', city: 'delhi', coords: [28.529249, 77.154134] },
  { id: 'delhi_chandni_chowk', name: 'Chandni Chowk', city: 'delhi', coords: [28.655983, 77.232194] },
  { id: 'delhi_nehru_place', name: 'Nehru Place', city: 'delhi', coords: [28.549257, 77.252953] },
  { id: 'delhi_mayur_vihar', name: 'Mayur Vihar', city: 'delhi', coords: [28.609855, 77.292632] },
  { id: 'delhi_shahdara', name: 'Shahdara', city: 'delhi', coords: [28.67343, 77.289886] },
  { id: 'delhi_okhla', name: 'Okhla', city: 'delhi', coords: [28.563662, 77.289055] },
  { id: 'delhi_munirka', name: 'Munirka', city: 'delhi', coords: [28.554886, 77.171084] },
  { id: 'delhi_model_town_delhi', name: 'Model Town Delhi', city: 'delhi', coords: [28.707334, 77.188523] },
  { id: 'delhi_paschim_vihar', name: 'Paschim Vihar', city: 'delhi', coords: [28.669578, 77.095956] },
  { id: 'delhi_kalkaji', name: 'Kalkaji', city: 'delhi', coords: [28.546948, 77.258801] },
  { id: 'delhi_narela', name: 'Narela', city: 'delhi', coords: [28.846477, 77.085663] },
  { id: 'chennai_t_nagar', name: 'T Nagar', city: 'chennai', coords: [13.037829, 80.231836] },
  { id: 'chennai_adyar', name: 'Adyar', city: 'chennai', coords: [13.00645, 80.257779] },
  { id: 'chennai_velachery', name: 'Velachery', city: 'chennai', coords: [12.980166, 80.222851] },
  { id: 'chennai_anna_nagar', name: 'Anna Nagar', city: 'chennai', coords: [13.088249, 80.20734] },
  { id: 'chennai_guindy', name: 'Guindy', city: 'chennai', coords: [13.008669, 80.212606] },
  { id: 'chennai_mylapore', name: 'Mylapore', city: 'chennai', coords: [13.031647, 80.270017] },
  { id: 'chennai_tambaram', name: 'Tambaram', city: 'chennai', coords: [12.94543, 80.11866] },
  { id: 'chennai_porur', name: 'Porur', city: 'chennai', coords: [13.032013, 80.158304] },
  { id: 'chennai_perungudi', name: 'Perungudi', city: 'chennai', coords: [12.971024, 80.241805] },
  { id: 'chennai_egmore', name: 'Egmore', city: 'chennai', coords: [13.072832, 80.257691] },
  { id: 'chennai_nungambakkam', name: 'Nungambakkam', city: 'chennai', coords: [13.062063, 80.240487] },
  { id: 'chennai_ambattur', name: 'Ambattur', city: 'chennai', coords: [13.105565, 80.163959] },
  { id: 'chennai_chromepet', name: 'Chromepet', city: 'chennai', coords: [12.957501, 80.143507] },
  { id: 'chennai_sholinganallur', name: 'Sholinganallur', city: 'chennai', coords: [12.917443, 80.21649] },
  { id: 'chennai_thiruvanmiyur', name: 'Thiruvanmiyur', city: 'chennai', coords: [12.985895, 80.264421] },
  { id: 'chennai_vadapalani', name: 'Vadapalani', city: 'chennai', coords: [13.050384, 80.21177] },
  { id: 'chennai_kodambakkam', name: 'Kodambakkam', city: 'chennai', coords: [13.049207, 80.224283] },
  { id: 'chennai_royapettah', name: 'Royapettah', city: 'chennai', coords: [13.055472, 80.263971] },
  { id: 'chennai_avadi', name: 'Avadi', city: 'chennai', coords: [13.099422, 80.211897] },
  { id: 'chennai_pallavaram', name: 'Pallavaram', city: 'chennai', coords: [12.967574, 80.15205] },
  { id: 'mumbai_bandra', name: 'Bandra', city: 'mumbai', coords: [19.054979, 72.84022] },
  { id: 'mumbai_andheri', name: 'Andheri', city: 'mumbai', coords: [19.119698, 72.84642] },
  { id: 'mumbai_colaba', name: 'Colaba', city: 'mumbai', coords: [18.915091, 72.825969] },
  { id: 'mumbai_dadar', name: 'Dadar', city: 'mumbai', coords: [19.019227, 72.842848] },
  { id: 'mumbai_powai', name: 'Powai', city: 'mumbai', coords: [19.11872, 72.907348] },
  { id: 'mumbai_borivali', name: 'Borivali', city: 'mumbai', coords: [19.229068, 72.857363] },
  { id: 'mumbai_goregaon', name: 'Goregaon', city: 'mumbai', coords: [19.164869, 72.849549] },
  { id: 'mumbai_malad', name: 'Malad', city: 'mumbai', coords: [19.186719, 72.848588] },
  { id: 'mumbai_chembur', name: 'Chembur', city: 'mumbai', coords: [19.054818, 72.897971] },
  { id: 'mumbai_ghatkopar', name: 'Ghatkopar', city: 'mumbai', coords: [19.085693, 72.908367] },
  { id: 'mumbai_worli', name: 'Worli', city: 'mumbai', coords: [19.011739, 72.817871] },
  { id: 'mumbai_juhu', name: 'Juhu', city: 'mumbai', coords: [19.107021, 72.827528] },
  { id: 'mumbai_kurla', name: 'Kurla', city: 'mumbai', coords: [19.06528, 72.87938] },
  { id: 'mumbai_vikhroli', name: 'Vikhroli', city: 'mumbai', coords: [19.11148, 72.928021] },
  { id: 'mumbai_mulund', name: 'Mulund', city: 'mumbai', coords: [19.172137, 72.956697] },
  { id: 'mumbai_santacruz', name: 'Santacruz', city: 'mumbai', coords: [19.079611, 72.847057] },
  { id: 'mumbai_wadala', name: 'Wadala', city: 'mumbai', coords: [19.026919, 72.875934] },
  { id: 'mumbai_marine_lines', name: 'Marine Lines', city: 'mumbai', coords: [18.945764, 72.823719] },
  { id: 'mumbai_bhandup', name: 'Bhandup', city: 'mumbai', coords: [19.142757, 72.937654] },
  { id: 'mumbai_kandivali', name: 'Kandivali', city: 'mumbai', coords: [19.204114, 72.851738] },
  { id: 'pune_koregaon_park', name: 'Koregaon Park', city: 'pune', coords: [18.536623, 73.893274] },
  { id: 'pune_hinjewadi', name: 'Hinjewadi', city: 'pune', coords: [18.592068, 73.757639] },
  { id: 'pune_kothrud', name: 'Kothrud', city: 'pune', coords: [18.507262, 73.805668] },
  { id: 'pune_viman_nagar', name: 'Viman Nagar', city: 'pune', coords: [18.570388, 73.913334] },
  { id: 'pune_baner', name: 'Baner', city: 'pune', coords: [18.558994, 73.784523] },
  { id: 'pune_hadapsar', name: 'Hadapsar', city: 'pune', coords: [18.500774, 73.937915] },
  { id: 'pune_aundh', name: 'Aundh', city: 'pune', coords: [18.561883, 73.810196] },
  { id: 'pune_wakad', name: 'Wakad', city: 'pune', coords: [18.602249, 73.764445] },
  { id: 'pune_kharadi', name: 'Kharadi', city: 'pune', coords: [18.551276, 73.941658] },
  { id: 'pune_shivajinagar_pune', name: 'Shivajinagar Pune', city: 'pune', coords: [18.523643, 73.848188] },
  { id: 'pune_camp_pune', name: 'Camp Pune', city: 'pune', coords: [18.521624, 73.871753] },
  { id: 'pune_warje', name: 'Warje', city: 'pune', coords: [18.482044, 73.80017] },
  { id: 'pune_pimpri', name: 'Pimpri', city: 'pune', coords: [18.623185, 73.801993] },
  { id: 'pune_chinchwad', name: 'Chinchwad', city: 'pune', coords: [18.640355, 73.791713] },
  { id: 'pune_katraj', name: 'Katraj', city: 'pune', coords: [18.453679, 73.85632] },
  { id: 'pune_magarpatta', name: 'Magarpatta', city: 'pune', coords: [18.511154, 73.927382] },
  { id: 'pune_bavdhan', name: 'Bavdhan', city: 'pune', coords: [18.520954, 73.778087] },
  { id: 'pune_yerwada', name: 'Yerwada', city: 'pune', coords: [18.545317, 73.886688] },
  { id: 'pune_dhankawadi', name: 'Dhankawadi', city: 'pune', coords: [18.46542, 73.850152] },
  { id: 'pune_nigdi', name: 'Nigdi', city: 'pune', coords: [18.659813, 73.777282] },
]

/**
 * Endpoints are resolved place objects, not ids into LOCATIONS — the search
 * box can return any OpenStreetMap place, which has no entry in this file.
 * LOCATIONS survives as the curated suggestion list and the offline fallback.
 */
const asPlace = (l) => ({
  id: l.id,
  name: l.name,
  address: 'Hyderabad, Telangana',
  lat: l.coords[0],
  lon: l.coords[1],
  coords: l.coords,
  source: 'preset',
})

// Ids are city-prefixed since places.yaml covers six cities. Falling back to
// the first two entries means a renamed landmark degrades to a working default
// rather than to `undefined`, which is what an unguarded find() would give.
export const DEFAULT_START =
  asPlace(LOCATIONS.find((l) => l.id === 'hyderabad_hitec_city') || LOCATIONS[0])
export const DEFAULT_END =
  asPlace(LOCATIONS.find((l) => l.id === 'hyderabad_charminar') || LOCATIONS[1])

/* ------------------------------------------------------------------ routes */
/* Three genuinely different corridors between Hitec City and Charminar. */
export const ROUTES = [
  {
    id: 'r1',
    label: 'Route 1',
    algorithm: 'QPSO',
    recommended: true,
    fastest: true,
    distanceKm: 18.9,
    etaMin: 38,
    congestion: 0.22,
    score: 91,
    timeSavedMin: 6,
    via: 'Jubilee Hills → Banjara Hills → Mehdipatnam',
    color: '#FF6B35',
    path: [
      [17.4435, 78.3772], [17.44, 78.39], [17.431, 78.402], [17.4239, 78.4138],
      [17.418, 78.429], [17.4126, 78.4482], [17.405, 78.445], [17.395, 78.436],
      [17.393, 78.448], [17.388, 78.465], [17.38, 78.47], [17.37, 78.473],
      [17.3616, 78.4747],
    ],
  },
  {
    id: 'r2',
    label: 'Route 2',
    algorithm: 'QPSO',
    recommended: false,
    fastest: false,
    distanceKm: 20.4,
    etaMin: 44,
    congestion: 0.35,
    score: 78,
    timeSavedMin: 0,
    via: 'Madhapur → Panjagutta → Khairatabad → Abids',
    color: '#E83E8C',
    path: [
      [17.4435, 78.3772], [17.4483, 78.3915], [17.44, 78.405], [17.43, 78.43],
      [17.4256, 78.45], [17.418, 78.456], [17.409, 78.465], [17.399, 78.47],
      [17.3897, 78.4747], [17.38, 78.476], [17.37, 78.475], [17.3616, 78.4747],
    ],
  },
  {
    id: 'r3',
    label: 'Route 3',
    algorithm: 'QPSO',
    recommended: false,
    fastest: false,
    distanceKm: 22.1,
    etaMin: 47,
    congestion: 0.41,
    score: 71,
    timeSavedMin: 0,
    via: 'Manikonda → Tolichowki → Attapur',
    color: '#E83E8C',
    path: [
      [17.4435, 78.3772], [17.43, 78.38], [17.415, 78.385], [17.403, 78.376],
      [17.396, 78.405], [17.39, 78.42], [17.361, 78.423], [17.355, 78.44],
      [17.356, 78.46], [17.3616, 78.4747],
    ],
  },
]

/* Route the system switches to during the rerouting demo. */
export const REROUTED_ROUTE = {
  id: 'r1b',
  label: 'New QPSO Route',
  algorithm: 'QPSO',
  recommended: true,
  fastest: true,
  distanceKm: 19.8,
  etaMin: 31,
  congestion: 0.19,
  score: 94,
  timeSavedMin: 7,
  via: 'Madhapur → Panjagutta → Masab Tank → Nampally',
  color: '#FF6B35',
  path: [
    [17.4435, 78.3772], [17.4483, 78.3915], [17.442, 78.408], [17.4374, 78.4487],
    [17.4256, 78.45], [17.415, 78.452], [17.4026, 78.4535], [17.3935, 78.4485],
    [17.3888, 78.4655], [17.379, 78.4705], [17.369, 78.4735], [17.3616, 78.4747],
  ],
}

/* ---------------------------------------------------------------- traffic */
/* Coloured overlay segments — the "live" congestion picture. */
export const TRAFFIC_SEGMENTS = [
  { id: 't1', name: 'Jubilee Hills Road No. 36', level: 'low', congestion: 0.14,
    path: [[17.4239, 78.4138], [17.418, 78.429]] },
  { id: 't2', name: 'Banjara Hills Road No. 1', level: 'moderate', congestion: 0.42,
    path: [[17.4126, 78.4482], [17.405, 78.445], [17.395, 78.436]] },
  { id: 't3', name: 'Mehdipatnam – Masab Tank', level: 'severe', congestion: 0.88,
    path: [[17.395, 78.436], [17.393, 78.448]] },
  { id: 't4', name: 'Nampally – Charminar', level: 'heavy', congestion: 0.67,
    path: [[17.388, 78.465], [17.38, 78.47], [17.37, 78.473], [17.3616, 78.4747]] },
  { id: 't5', name: 'Madhapur Main Road', level: 'moderate', congestion: 0.38,
    path: [[17.4435, 78.3772], [17.4483, 78.3915]] },
  { id: 't6', name: 'Panjagutta Flyover', level: 'heavy', congestion: 0.71,
    path: [[17.4256, 78.45], [17.418, 78.456]] },
  { id: 't7', name: 'Ameerpet – Begumpet', level: 'moderate', congestion: 0.49,
    path: [[17.4374, 78.4487], [17.4443, 78.4649]] },
  { id: 't8', name: 'Tank Bund Road', level: 'low', congestion: 0.21,
    path: [[17.4239, 78.4738], [17.4344, 78.5013]] },
  { id: 't9', name: 'Gachibowli – Kondapur', level: 'low', congestion: 0.18,
    path: [[17.4401, 78.3489], [17.464, 78.364]] },
  { id: 't10', name: 'Dilsukhnagar – LB Nagar', level: 'severe', congestion: 0.83,
    path: [[17.3687, 78.5247], [17.3457, 78.5522]] },
  { id: 't11', name: 'Uppal Ring Road', level: 'heavy', congestion: 0.62,
    path: [[17.402, 78.559], [17.425, 78.558]] },
  { id: 't12', name: 'PVNR Expressway', level: 'low', congestion: 0.12,
    path: [[17.361, 78.423], [17.33, 78.42], [17.2403, 78.4294]] },
]

export const TRAFFIC_COLORS = {
  low: '#A3E635',
  moderate: '#FFB020',
  heavy: '#FF6B35',
  severe: '#FF4D5A',
}


export const TRAFFIC_LABELS = {
  low: 'Low',
  moderate: 'Moderate',
  heavy: 'Heavy',
  severe: 'Severe',
}

export const INCIDENTS = [
  { id: 'i1', type: 'accident', name: 'Multi-vehicle collision',
    location: 'Mehdipatnam Junction', coords: [17.395, 78.436],
    severity: 'severe', reportedAt: '5 min ago',
    description: 'Two lanes blocked. Traffic police on site.' },
  { id: 'i2', type: 'closure', name: 'Road closure — metro works',
    location: 'Nampally Station Road', coords: [17.388, 78.465],
    severity: 'heavy', reportedAt: '32 min ago',
    description: 'Carriageway closed until 18:00. Diversion via Abids.' },
  { id: 'i3', type: 'congestion', name: 'Heavy congestion',
    location: 'Panjagutta Flyover', coords: [17.4256, 78.45],
    severity: 'heavy', reportedAt: '12 min ago',
    description: 'Peak-hour build-up. Average speed 11 km/h.' },
  { id: 'i4', type: 'waterlogging', name: 'Waterlogging reported',
    location: 'Dilsukhnagar', coords: [17.3687, 78.5247],
    severity: 'moderate', reportedAt: '48 min ago',
    description: 'Slow-moving traffic in the right lane.' },
]

/* ----------------------------------------------------------------- alerts */
export const ALERTS = [
  { id: 'a1', kind: 'predictive', severity: 'severe', title: 'Predictive congestion alert',
    location: 'Mehdipatnam – Masab Tank', time: '2 min ago',
    current: 0.62, predicted: 0.91, etaMinutes: 15,
    description: 'Congestion on your current route is forecast to rise sharply.',
    action: 'Consider an alternate route via Panjagutta.' },
  { id: 'a2', kind: 'incident', severity: 'severe', title: 'Accident reported',
    location: 'Mehdipatnam Junction', time: '5 min ago',
    description: 'Multi-vehicle collision blocking two lanes.',
    action: 'Avoid the junction for the next 30 minutes.' },
  { id: 'a3', kind: 'reroute', severity: 'moderate', title: 'Better route available',
    location: 'Hitec City → Charminar', time: '8 min ago',
    description: 'An alternative route is currently 7 minutes faster.',
    action: 'Switch to the new QPSO route.' },
  { id: 'a4', kind: 'incident', severity: 'heavy', title: 'Road closure',
    location: 'Nampally Station Road', time: '32 min ago',
    description: 'Metro construction. Closed until 18:00.',
    action: 'Diversion via Abids is in effect.' },
  { id: 'a5', kind: 'predictive', severity: 'moderate', title: 'Predictive congestion alert',
    location: 'Ameerpet – Begumpet', time: '41 min ago',
    current: 0.49, predicted: 0.68, etaMinutes: 25,
    description: 'Evening peak build-up expected.',
    action: 'Depart before 17:30 to avoid delay.' },
]

/* -------------------------------------------------------------- analytics */
export const TRAFFIC_TREND = [
  { hour: '00:00', congestion: 12, vehicles: 420 },
  { hour: '02:00', congestion: 8, vehicles: 210 },
  { hour: '04:00', congestion: 9, vehicles: 260 },
  { hour: '06:00', congestion: 28, vehicles: 1150 },
  { hour: '08:00', congestion: 74, vehicles: 3420 },
  { hour: '10:00', congestion: 52, vehicles: 2480 },
  { hour: '12:00', congestion: 46, vehicles: 2260 },
  { hour: '14:00', congestion: 44, vehicles: 2180 },
  { hour: '16:00', congestion: 58, vehicles: 2740 },
  { hour: '18:00', congestion: 86, vehicles: 3910 },
  { hour: '20:00', congestion: 61, vehicles: 2830 },
  { hour: '22:00', congestion: 31, vehicles: 1240 },
]

export const PREDICTION_SERIES = [
  { time: 'now', actual: 62, predicted: 62 },
  { time: '+5m', actual: 68, predicted: 71 },
  { time: '+10m', actual: 79, predicted: 82 },
  { time: '+15m', actual: null, predicted: 91 },
  { time: '+20m', actual: null, predicted: 88 },
  { time: '+25m', actual: null, predicted: 74 },
  { time: '+30m', actual: null, predicted: 59 },
]

export const ROUTE_PERFORMANCE = [
  { route: 'Hitec → Charminar', distance: 18.9, time: 38 },
  { route: 'Gachibowli → Secbad', distance: 21.4, time: 44 },
  { route: 'Miyapur → LB Nagar', distance: 30.4, time: 62 },
  { route: 'Kukatpally → Uppal', distance: 24.8, time: 51 },
  { route: 'Hitec → Airport', distance: 34.1, time: 46 },
]

export const TRAFFIC_DISTRIBUTION = [
  { name: 'Low', value: 34, color: '#A3E635' },
  { name: 'Moderate', value: 29, color: '#FFB020' },
  { name: 'Heavy', value: 24, color: '#FF6B35' },
  { name: 'Severe', value: 13, color: '#FF4D5A' },
]

export const ANALYTICS_STATS = [
  { label: 'Average Traffic', value: 47, suffix: '%', trend: +4.2, tone: 'yellow' },
  { label: 'Average Delay', value: 11, suffix: ' min', trend: +1.8, tone: 'orange' },
  { label: 'Congestion Level', value: 62, suffix: '%', trend: +9.1, tone: 'red' },
  { label: 'Predicted Congestion', value: 91, suffix: '%', trend: +29, tone: 'red' },
  { label: 'Active Incidents', value: 4, suffix: '', trend: +2, tone: 'orange' },
  { label: 'Routes Optimized', value: 1284, suffix: '', trend: +12.4, tone: 'cyan' },
]

/* ------------------------------------------------------------- benchmark */
/*
 * IMPORTANT — read before presenting.
 *
 * On a single source→destination problem with additively-combined weights,
 * Dijkstra is provably optimal. The numbers below reflect that honestly:
 * Dijkstra attains the best objective value and the fastest runtime, and QPSO
 * lands close to it. Do NOT edit these to make QPSO "win" — the defensible
 * claim is that QPSO reaches near-optimal quality on a problem where the
 * optimum is known, which validates the implementation before applying it to
 * constrained problems Dijkstra cannot solve.
 */
export const BENCHMARK = {
  isDemoData: true,
  problem: 'Hitec City → Charminar · balanced mode · 30 trials',
  rows: [
    { algorithm: 'Dijkstra', deterministic: true,
      distanceKm: 18.9, timeMin: 38.0, congestion: 0.220, runtimeMs: 512,
      fitness: 0.4120, fitnessStd: 0, fitnessBest: 0.4120, fitnessWorst: 0.4120,
      iterations: null, validity: 100 },
    { algorithm: 'QPSO', deterministic: false,
      distanceKm: 19.1, timeMin: 38.6, congestion: 0.224, runtimeMs: 1840,
      fitness: 0.4183, fitnessStd: 0.0071, fitnessBest: 0.4120, fitnessWorst: 0.4361,
      iterations: 48, validity: 100 },
    { algorithm: 'PSO', deterministic: false,
      distanceKm: 19.6, timeMin: 40.1, congestion: 0.241, runtimeMs: 1710,
      fitness: 0.4372, fitnessStd: 0.0134, fitnessBest: 0.4142, fitnessWorst: 0.4708,
      iterations: 62, validity: 97 },
    { algorithm: 'Genetic Algorithm', deterministic: false,
      distanceKm: 20.0, timeMin: 41.3, congestion: 0.253, runtimeMs: 2260,
      fitness: 0.4491, fitnessStd: 0.0186, fitnessBest: 0.4198, fitnessWorst: 0.4922,
      iterations: 80, validity: 94 },
  ],
}

/* -------------------------------------------------------- convergence */
/* Generated once at module load so the curve is stable across renders. */
function convergenceCurve(start, floor, rate, iterations, jitter, seed) {
  let s = seed
  const rand = () => {
    s = (s * 1103515245 + 12345) % 2147483648
    return s / 2147483648
  }
  const out = []
  let best = start
  for (let i = 0; i <= iterations; i++) {
    const target = floor + (start - floor) * Math.exp(-rate * i)
    const candidate = target + (rand() - 0.5) * jitter
    best = Math.min(best, candidate)
    out.push(Number(best.toFixed(4)))
  }
  return out
}

const ITER = 80
export const CONVERGENCE = {
  isDemoData: true,
  iterations: ITER,
  series: {
    QPSO: convergenceCurve(0.92, 0.412, 0.115, ITER, 0.012, 7),
    PSO: convergenceCurve(0.94, 0.436, 0.072, ITER, 0.018, 21),
    GA: convergenceCurve(0.96, 0.449, 0.055, ITER, 0.026, 43),
  },
  summary: {
    QPSO: { iterations: 48, bestFitness: 0.4183, executionMs: 1840, converged: 94 },
    PSO: { iterations: 62, bestFitness: 0.4372, executionMs: 1710, converged: 81 },
    GA: { iterations: 80, bestFitness: 0.4491, executionMs: 2260, converged: 73 },
  },
}

/** Reshaped for Recharts: [{ iteration, QPSO, PSO, GA }, ...] */
export const CONVERGENCE_CHART_DATA = Array.from({ length: ITER + 1 }, (_, i) => ({
  iteration: i,
  QPSO: CONVERGENCE.series.QPSO[i],
  PSO: CONVERGENCE.series.PSO[i],
  GA: CONVERGENCE.series.GA[i],
}))

/* ------------------------------------------------------------ scalability */
export const SCALABILITY = {
  isDemoData: true,
  rows: [
    { nodes: 100, dijkstra: 3, qpso: 118, pso: 104, ga: 142, qpsoQuality: 100.0 },
    { nodes: 500, dijkstra: 14, qpso: 356, pso: 331, ga: 448, qpsoQuality: 99.6 },
    { nodes: 1000, dijkstra: 31, qpso: 642, pso: 611, ga: 838, qpsoQuality: 99.1 },
    { nodes: 5000, dijkstra: 186, qpso: 2140, pso: 2080, ga: 2960, qpsoQuality: 98.2 },
    { nodes: 10000, dijkstra: 412, qpso: 3980, pso: 3910, ga: 5640, qpsoQuality: 97.4 },
  ],
}

/* --------------------------------------------------------------- history */
export const ROUTE_HISTORY = [
  { id: 'h1', date: '2026-08-27 09:14', start: 'Hitec City', end: 'Charminar',
    algorithm: 'QPSO', distanceKm: 18.9, etaMin: 38, traffic: 'moderate', status: 'completed' },
  { id: 'h2', date: '2026-08-27 08:02', start: 'Gachibowli', end: 'Secunderabad',
    algorithm: 'QPSO', distanceKm: 21.4, etaMin: 44, traffic: 'heavy', status: 'rerouted' },
  { id: 'h3', date: '2026-08-26 18:47', start: 'Miyapur', end: 'LB Nagar',
    algorithm: 'PSO', distanceKm: 30.4, etaMin: 62, traffic: 'severe', status: 'completed' },
  { id: 'h4', date: '2026-08-26 17:20', start: 'Kukatpally', end: 'Uppal',
    algorithm: 'QPSO', distanceKm: 24.8, etaMin: 51, traffic: 'heavy', status: 'completed' },
  { id: 'h5', date: '2026-08-26 11:05', start: 'Hitec City', end: 'RGIA Airport',
    algorithm: 'Dijkstra', distanceKm: 34.1, etaMin: 46, traffic: 'low', status: 'completed' },
  { id: 'h6', date: '2026-08-25 19:33', start: 'Banjara Hills', end: 'Dilsukhnagar',
    algorithm: 'QPSO', distanceKm: 14.2, etaMin: 39, traffic: 'severe', status: 'rerouted' },
  { id: 'h7', date: '2026-08-25 14:12', start: 'Ameerpet', end: 'Uppal',
    algorithm: 'GA', distanceKm: 17.6, etaMin: 42, traffic: 'moderate', status: 'cancelled' },
  { id: 'h8', date: '2026-08-25 09:58', start: 'Mehdipatnam', end: 'Madhapur',
    algorithm: 'QPSO', distanceKm: 12.3, etaMin: 29, traffic: 'moderate', status: 'completed' },
]

/* ------------------------------------------------- optimisation sequence */
/* Stage labels shown during the QPSO run animation. */
export const OPTIMIZATION_STAGES = [
  'Analyzing transportation network',
  'Initializing particle swarm',
  'Generating candidate routes',
  'Evaluating fitness',
  'Updating particle positions',
  'Searching solution space',
  'Converging on optimum',
  'Best route found',
]

export const ALGORITHMS = [
  { id: 'qpso', name: 'QPSO', full: 'Quantum Particle Swarm Optimization', quantum: true },
  { id: 'pso', name: 'PSO', full: 'Particle Swarm Optimization', quantum: false },
  { id: 'ga', name: 'GA', full: 'Genetic Algorithm', quantum: false },
  { id: 'dijkstra', name: 'Dijkstra', full: "Dijkstra's Shortest Path", quantum: false },
]

/**
 * Vehicle profiles for the backend-less demo ONLY. The live app reads them from
 * GET /api/vehicles, i.e. from graph/vehicles.py — the table the router uses.
 * tests/test_vehicles.py fails if the ids here drift from that table.
 */
export const MOCK_VEHICLES = {
  default: 'car',
  note: 'Access and speed rules are modelling assumptions, not local law.',
  vehicles: [
    { id: 'car', label: 'Car', avoids: [], maxSpeedKph: null, assumption: false,
      basis: "The baseline. The road graph's speeds are car speeds." },
    { id: 'two_wheeler', label: 'Two-wheeler', avoids: ['motorway', 'motorway_link'], maxSpeedKph: null, assumption: true,
      basis: 'Access-controlled expressways commonly prohibit two-wheelers.' },
    { id: 'auto_rickshaw', label: 'Auto-rickshaw', avoids: ['motorway', 'motorway_link'], maxSpeedKph: 50, assumption: true,
      basis: 'Commonly barred from expressways; 50 km/h is an assumed top speed.' },
    { id: 'bus', label: 'Bus', avoids: [], maxSpeedKph: 60, assumption: true,
      basis: '60 km/h is an assumed top speed for a city bus.' },
    { id: 'truck', label: 'Truck', avoids: [], maxSpeedKph: 60, assumption: true,
      basis: '60 km/h is an assumed top speed. Heavy-vehicle restrictions are not modelled.' },
    { id: 'bicycle', label: 'Bicycle', avoids: ['motorway', 'motorway_link'], maxSpeedKph: 15, assumption: true,
      basis: 'Not permitted on expressways. 15 km/h is an assumed riding speed.' },
  ],
}

export const OPTIMIZATION_MODES = [
  { id: 'balanced', name: 'Balanced', weights: { time: 0.4, distance: 0.3, congestion: 0.3 } },
  { id: 'fastest', name: 'Fastest', weights: { time: 0.7, distance: 0.2, congestion: 0.1 } },
  { id: 'shortest', name: 'Shortest', weights: { time: 0.2, distance: 0.7, congestion: 0.1 } },
  { id: 'low_congestion', name: 'Low Congestion', weights: { time: 0.2, distance: 0.1, congestion: 0.7 } },
]

export const SYSTEM_STATUS = {
  version: 'v0.1.0',
  // Reflects reality rather than a hardcoded string: the sidebar badge said
  // "MOCK" even when the app was talking to the live FastAPI backend.
  backend: import.meta.env.VITE_USE_MOCK === 'false' ? 'live' : 'mock',
  graph: 'Hyderabad · 286,603 nodes · 741,203 edges',
  lastUpdated: new Date().toISOString(),
}
