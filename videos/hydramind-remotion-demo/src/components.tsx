import type {CSSProperties, ReactNode} from "react";
import {
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {COLORS} from "./constants";

export const fade = (frame: number, duration: number, edge = 16): number =>
  interpolate(frame, [0, edge, duration - edge, duration], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

export const reveal = (frame: number, at: number, span = 24): number =>
  interpolate(frame, [at, at + span], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

export const Scene: React.FC<{
  children: ReactNode;
  duration: number;
  dark?: boolean;
  index: number;
  label: string;
}> = ({children, duration, dark = false, index, label}) => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        background: dark ? COLORS.ink : COLORS.cream,
        color: dark ? COLORS.cream : COLORS.ink,
        opacity: fade(frame, duration),
      }}
    >
      <Grid dark={dark} />
      <div
        style={{
          position: "absolute",
          left: 82,
          right: 82,
          top: 44,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          zIndex: 40,
          fontFamily: "IBM Plex Mono",
          fontSize: 17,
          letterSpacing: "0.12em",
          color: dark ? "rgba(255,253,247,0.68)" : COLORS.cobalt,
          textTransform: "uppercase",
        }}
      >
        <span>
          {String(index).padStart(2, "0")} / {label}
        </span>
        <BrandLockup light={dark} compact />
      </div>
      {children}
      <div
        style={{
          position: "absolute",
          left: 0,
          bottom: 0,
          height: 5,
          width: `${(index / 7) * 100}%`,
          background: dark ? COLORS.green : COLORS.cobalt,
          zIndex: 50,
        }}
      />
    </div>
  );
};
export const Grid: React.FC<{dark?: boolean}> = ({dark = false}) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      backgroundImage: dark
        ? "linear-gradient(rgba(255,253,247,.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,253,247,.045) 1px, transparent 1px)"
        : "linear-gradient(rgba(22,75,220,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(22,75,220,.035) 1px, transparent 1px)",
      backgroundSize: "72px 72px",
      maskImage:
        "linear-gradient(to bottom, rgba(0,0,0,.7), rgba(0,0,0,.12) 72%, transparent)",
      pointerEvents: "none",
    }}
  />
);

export const BrandLockup: React.FC<{
  light?: boolean;
  compact?: boolean;
}> = ({light = false, compact = false}) => (
  <div style={{display: "flex", alignItems: "center", gap: compact ? 10 : 18}}>
    <Img
      src={staticFile("hydramind-mark.svg")}
      style={{width: compact ? 32 : 62, height: compact ? 32 : 62}}
    />
    <span
      style={{
        fontFamily: "Space Grotesk",
        fontWeight: 700,
        fontSize: compact ? 22 : 42,
        letterSpacing: "-0.045em",
        color: light ? COLORS.cream : COLORS.ink,
      }}
    >
      HydraMind
    </span>
  </div>
);

export const BrowserFrame: React.FC<{
  src: string;
  style?: CSSProperties;
  imageStyle?: CSSProperties;
  label?: string;
}> = ({src, style, imageStyle, label = "LIVE HYDRAMIND"}) => (
  <div
    style={{
      overflow: "hidden",
      border: `1.5px solid ${COLORS.border}`,
      borderRadius: 22,
      background: "#f7f6f0",
      ...style,
    }}
  >
    <div
      style={{
        height: 42,
        display: "flex",
        alignItems: "center",
        padding: "0 17px",
        borderBottom: `1px solid ${COLORS.border}`,
        background: "rgba(255,253,247,.96)",
      }}
    >
      <span style={{width: 9, height: 9, borderRadius: 99, background: COLORS.red}} />
      <span
        style={{
          width: 9,
          height: 9,
          borderRadius: 99,
          marginLeft: 7,
          background: COLORS.amber,
        }}
      />
      <span
        style={{
          width: 9,
          height: 9,
          borderRadius: 99,
          marginLeft: 7,
          background: COLORS.green,
        }}
      />
      <span
        style={{
          marginLeft: 18,
          fontFamily: "IBM Plex Mono",
          fontSize: 13,
          letterSpacing: "0.12em",
          color: COLORS.muted,
        }}
      >
        {label}
      </span>
    </div>
    <Img
      src={staticFile(src)}
      style={{
        display: "block",
        width: "100%",
        height: "calc(100% - 42px)",
        objectFit: "cover",
        objectPosition: "center",
        ...imageStyle,
      }}
    />
  </div>
);

export const Pill: React.FC<{
  children: ReactNode;
  tone?: "blue" | "green" | "red" | "amber" | "ink";
  style?: CSSProperties;
}> = ({children, tone = "blue", style}) => {
  const toneMap = {
    blue: {color: COLORS.cobalt, bg: "rgba(22,75,220,.09)"},
    green: {color: COLORS.green, bg: "rgba(52,119,69,.10)"},
    red: {color: COLORS.red, bg: "rgba(194,65,58,.10)"},
    amber: {color: COLORS.amber, bg: "rgba(215,137,39,.11)"},
    ink: {color: COLORS.cream, bg: "rgba(255,253,247,.10)"},
  }[tone];

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        borderRadius: 999,
        padding: "11px 17px",
        background: toneMap.bg,
        color: toneMap.color,
        fontFamily: "IBM Plex Mono",
        fontSize: 16,
        fontWeight: 600,
        letterSpacing: "0.07em",
        textTransform: "uppercase",
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const AnimatedNumber: React.FC<{
  value: number;
  suffix?: string;
  at: number;
}> = ({value, suffix = "", at}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = spring({
    frame: frame - at,
    fps,
    config: {damping: 18, mass: 0.8},
  });
  return (
    <>
      {Math.round(value * progress)}
      {suffix}
    </>
  );
};

export const Node: React.FC<{
  x: number;
  y: number;
  label: string;
  tone: "blue" | "green" | "red" | "amber";
  scale?: number;
}> = ({x, y, label, tone, scale = 1}) => {
  const map = {
    blue: COLORS.cobalt,
    green: COLORS.green,
    red: COLORS.red,
    amber: COLORS.amber,
  };
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${scale})`,
        borderRadius: 999,
        padding: "14px 20px",
        border: `2px solid ${map[tone]}`,
        background: COLORS.cream,
        color: map[tone],
        fontFamily: "IBM Plex Mono",
        fontSize: 16,
        fontWeight: 600,
        letterSpacing: "0.06em",
        whiteSpace: "nowrap",
        zIndex: 4,
      }}
    >
      {label}
    </div>
  );
};
