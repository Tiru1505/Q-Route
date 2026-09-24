/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  // Preflight resets margins/borders/buttons/inputs globally, which would
  // fight the hand-written base styles in src/index.css. Tailwind here is
  // purely a utility layer for motion-primitives components, not a reset.
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        brand: 'var(--brand)',
        'brand-hover': 'var(--brand-hover)',
        panel: 'var(--panel)',
        'panel-hover': 'var(--panel-hover)',
        border: 'var(--border)',
        'border-strong': 'var(--border-strong)',
        text: 'var(--text)',
        'text-dim': 'var(--text-dim)',
        'text-faint': 'var(--text-faint)',
        cyan: 'var(--cyan)',
        pink: 'var(--pink)',
        low: 'var(--low)',
        moderate: 'var(--moderate)',
        heavy: 'var(--heavy)',
        severe: 'var(--severe)',
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
        sm: 'var(--radius-sm)',
        lg: 'var(--radius-lg)',
      },
    },
  },
  plugins: [],
}
