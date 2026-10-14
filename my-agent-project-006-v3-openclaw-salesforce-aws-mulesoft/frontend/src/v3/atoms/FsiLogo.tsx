/**
 * FSI Workforce 360 brand mark — inline SVG, 18px default.
 *
 * Replaces v2's W360Logo. Slightly different mark so users can tell
 * v2 and v3 apart visually: three concentric arcs (three personas)
 * instead of v2's cross-in-circle.
 */

export interface FsiLogoProps {
  size?: number;
  color?: string;
}

export function FsiLogo({ size = 18, color = '#1B96FF' }: FsiLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      {/* Outer ring — 360° workforce */}
      <circle cx="12" cy="12" r="10" stroke={color} strokeWidth="1.6" fill="none" />
      {/* Three persona arcs — research (top), advisor (right), client (bottom-left) */}
      <path
        d="M12 4a8 8 0 0 1 6.928 4"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.9"
      />
      <path
        d="M18.928 16a8 8 0 0 1-6.928 4"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.7"
      />
      <path
        d="M12 20a8 8 0 0 1-6.928-12"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.5"
      />
      {/* Hub */}
      <circle cx="12" cy="12" r="2.5" fill={color} />
    </svg>
  );
}
