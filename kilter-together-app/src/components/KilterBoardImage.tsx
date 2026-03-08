import type { HighlightedHold } from "@/types";

interface BoardLayer {
  key: string;
  src: string;
  alt: string;
}

interface KilterBoardImageProps {
  layers: BoardLayer[];
  highlightedHolds?: HighlightedHold[];
  onLayerError?: (key: string) => void;
  maxHeightClassName?: string;
}

const roleRadius: Record<string, number> = {
  start: 1.9,
  middle: 1.65,
  finish: 2,
  foot: 1.45,
};

export default function KilterBoardImage({
  layers,
  highlightedHolds = [],
  onLayerError,
  maxHeightClassName = "max-h-[70vh]",
}: KilterBoardImageProps) {
  return (
    <div className="relative inline-block max-w-full">
      {layers.map((layer, index) => (
        <img
          key={layer.key}
          src={layer.src}
          alt={layer.alt}
          className={`max-w-full object-contain ${
            index === 0 ? "relative" : "absolute left-0 top-0"
          } ${maxHeightClassName}`}
          style={{
            mixBlendMode: index > 0 ? "multiply" : "normal",
          }}
          onError={() => onLayerError?.(layer.key)}
        />
      ))}

      {highlightedHolds.length > 0 ? (
        <svg
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {highlightedHolds.map((hold) => {
            const color = normalizeColor(hold.color);
            const glow = hexToRgba(color, 0.28);
            const ring = roleRadius[hold.role] ?? 1.7;
            const outer = ring + 0.95;

            return (
              <g
                key={`${hold.position}-${hold.role}`}
                transform={`translate(${hold.x} ${hold.y})`}
                style={{
                  filter: `drop-shadow(0 0 10px ${glow})`,
                }}
              >
                <circle fill={glow} r={outer} />
                <circle
                  fill="none"
                  r={ring}
                  stroke={color}
                  strokeDasharray={
                    hold.role === "foot" ? "1.25 0.85" : undefined
                  }
                  strokeWidth={0.6}
                />
                <circle fill="#FFFFFF" opacity={0.95} r={0.45} />
                <circle fill={color} r={0.75} />
              </g>
            );
          })}
        </svg>
      ) : null}
    </div>
  );
}

function normalizeColor(color: string): string {
  if (color.startsWith("#")) {
    return color.toUpperCase();
  }
  return `#${color.toUpperCase()}`;
}

function hexToRgba(color: string, alpha: number): string {
  const normalized = normalizeColor(color).replace("#", "");
  const parsed = normalized.match(/.{1,2}/g);
  if (!parsed || parsed.length !== 3) {
    return `rgba(0, 221, 0, ${alpha})`;
  }

  const [red, green, blue] = parsed.map((value) => Number.parseInt(value, 16));
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}
