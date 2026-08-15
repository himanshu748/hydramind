import {interpolate, useCurrentFrame} from "remotion";
import {BrowserFrame, Pill, Scene, reveal} from "../components";
import {COLORS} from "../constants";

const TrustBadge: React.FC<{
  from: string;
  to: string;
  label: string;
  tone: "red" | "amber";
  opacity: number;
}> = ({from, to, label, tone, opacity}) => (
  <div
    style={{
      borderRadius: 16,
      border: `1px solid ${tone === "red" ? "rgba(194,65,58,.28)" : "rgba(215,137,39,.3)"}`,
      background: "rgba(255,253,247,.96)",
      padding: "15px 18px",
      opacity,
      minWidth: 195,
    }}
  >
    <div style={{fontFamily: "IBM Plex Mono", fontSize: 14, color: COLORS.muted}}>{label}</div>
    <div
      style={{
        marginTop: 7,
        fontFamily: "Space Grotesk",
        fontWeight: 700,
        fontSize: 30,
        color: tone === "red" ? COLORS.red : COLORS.amber,
      }}
    >
      {from} → {to}
    </div>
  </div>
);

export const ContradictionScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const screenIn = reveal(frame, 12, 26);
  const zoom = interpolate(frame, [0, 240, duration], [1.05, 1.05, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const edge = reveal(frame, 114, 25);

  return (
    <Scene duration={duration} index={3} label="CONTRADICTION → TRUST DECAY">
      <div style={{position: "absolute", left: 92, top: 126, right: 92, zIndex: 8}}>
        <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
          <h1
            style={{
              margin: 0,
              fontFamily: "Space Grotesk",
              fontWeight: 700,
              fontSize: 67,
              letterSpacing: "-0.055em",
            }}
          >
            Contradiction becomes <span style={{color: COLORS.red}}>evidence.</span>
          </h1>
          <Pill tone="red">History is preserved</Pill>
        </div>
      </div>

      <BrowserFrame
        src="screens/dashboard-graph.png"
        style={{
          position: "absolute",
          left: 88,
          top: 238,
          width: 1744,
          height: 777,
          opacity: screenIn,
          transform: `translateY(${(1 - screenIn) * 34}px) scale(${zoom})`,
        }}
        label="LIVE SCOPE / PRODUCTION"
      />

      <svg
        width="900"
        height="450"
        viewBox="0 0 900 450"
        style={{position: "absolute", left: 505, top: 355, zIndex: 11, pointerEvents: "none"}}
      >
        <path
          d="M140 100 C280 48 410 82 528 190"
          fill="none"
          stroke={COLORS.red}
          strokeWidth="6"
          strokeLinecap="round"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={1 - edge}
        />
        <circle cx="140" cy="100" r="11" fill={COLORS.red} opacity={edge} />
        <circle cx="528" cy="190" r="11" fill={COLORS.red} opacity={edge} />
      </svg>

      <div
        style={{
          position: "absolute",
          right: 116,
          bottom: 92,
          zIndex: 14,
          display: "flex",
          gap: 10,
        }}
      >
        <TrustBadge from="1.00" to="0.60" label="CONTRADICTED SOURCE" tone="red" opacity={reveal(frame, 148, 22)} />
        <TrustBadge from="1.00" to="0.85" label="ONE HOP" tone="amber" opacity={reveal(frame, 260, 22)} />
        <TrustBadge from="1.00" to="0.70" label="TWO HOPS" tone="amber" opacity={reveal(frame, 355, 22)} />
      </div>
    </Scene>
  );
};
