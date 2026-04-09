import React, { useId } from 'react';

const NAVY = '#1B2A4A';
const GOLD = '#E5A820';
const BURNT_ORANGE = '#D4722C';
const BURNT_ORANGE_DARK = '#C95C26';
const GOLD_SOFT = '#F2C14E';

export interface NacariFlyLogoProps extends React.SVGProps<SVGSVGElement> {
  width?: number | string;
  height?: number | string;
  title?: string;
}

export const NacariFlyLogo: React.FC<NacariFlyLogoProps> = ({
  width = 200,
  height = 56,
  title = 'Nacari Fly',
  className,
  ...svgProps
}) => {
  const trailGradientId = useId();
  const trailHighlightGradientId = useId();

  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 760 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={title}
      className={className}
      {...svgProps}
    >
      <title>{title}</title>
      <defs>
        <linearGradient
          id={trailGradientId}
          x1="26"
          y1="154"
          x2="180"
          y2="42"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor={BURNT_ORANGE} />
          <stop offset="0.6" stopColor="#F19A18" />
          <stop offset="1" stopColor={GOLD} />
        </linearGradient>
        <linearGradient
          id={trailHighlightGradientId}
          x1="34"
          y1="162"
          x2="178"
          y2="56"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor={BURNT_ORANGE_DARK} />
          <stop offset="1" stopColor={GOLD_SOFT} />
        </linearGradient>
      </defs>

      <g transform="translate(24 10)">
        <polygon points="34 18 82 18 74 166 26 166" fill={NAVY} />
        <polygon points="76 18 118 18 130 166 88 166" fill={NAVY} />
        <polygon points="112 18 160 18 160 166 112 166" fill={NAVY} />
        <polygon points="86 42 109 42 118 132 95 132" fill="#FFFFFF" />

        <path
          d="M20 152C55 146 83 126 107 99C126 77 144 59 168 40"
          stroke={`url(#${trailGradientId})`}
          strokeWidth="14"
          strokeLinecap="round"
        />
        <path
          d="M28 160C63 152 90 132 114 106C132 85 149 68 167 54"
          stroke={`url(#${trailHighlightGradientId})`}
          strokeWidth="4.5"
          strokeLinecap="round"
        />

        <g transform="translate(120 6)">
          <g transform="scale(4.2)">
            <g transform="rotate(-32 11.5 12)">
              <path
                d="M21 16V14L13 9V3.5A1.5 1.5 0 0 0 11.5 2A1.5 1.5 0 0 0 10 3.5V9L2 14V16L10 13.5V19L8 20.5V22L11.5 21L15 22V20.5L13 19V13.5L21 16Z"
                fill={GOLD}
              />
            </g>
          </g>
        </g>
      </g>

      <text
        x="286"
        y="124"
        fill={NAVY}
        fontFamily="'Segoe UI', Arial, sans-serif"
        textAnchor="start"
      >
        <tspan fontSize="86" fontWeight="700">
          Nacari
        </tspan>
        <tspan dx="12" fontSize="76" fontWeight="400" fontStyle="italic">
          Fly
        </tspan>
      </text>
    </svg>
  );
};

export default NacariFlyLogo;
