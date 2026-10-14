/**
 * V4 W360 brand mark — ported verbatim from the uploaded design zip
 * (UIUX Design/research.jsx → W360Logo). Same crosshair-with-dot SVG
 * the designer drew; re-used across all three personas.
 */

export interface W360LogoProps {
  size?: number;
}

export function W360Logo({ size = 18 }: W360LogoProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="#1B96FF" strokeWidth="1.6" />
      <path d="M12 2v20M2 12h20" stroke="#1B96FF" strokeWidth="1" opacity=".4" />
      <circle cx="12" cy="12" r="3.5" fill="#1B96FF" />
    </svg>
  );
}
