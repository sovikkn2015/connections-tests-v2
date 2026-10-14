/**
 * Workflow 360 brand mark — inline SVG, 18px default.
 * Sourced from the uploaded UIUX design zip.
 */

export interface W360LogoProps {
  size?: number;
  color?: string;
}

export function W360Logo({ size = 18, color = '#1B96FF' }: W360LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="12" r="10" stroke={color} strokeWidth="1.6" />
      <path
        d="M12 2v20M2 12h20"
        stroke={color}
        strokeWidth="1"
        opacity="0.4"
      />
      <circle cx="12" cy="12" r="3.5" fill={color} />
    </svg>
  );
}
