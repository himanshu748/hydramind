import {interpolate, useCurrentFrame} from "remotion";
import {BrowserFrame, Pill, Scene, reveal} from "../components";
import {COLORS} from "../constants";

export const TimelineScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const stage = reveal(frame, 20, 30);
  const move = interpolate(frame, [110, 310], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <Scene duration={duration} index={5} label="REVISION WITHOUT ERASURE">
      <div style={{position: "absolute", left: 92, right: 92, top: 118}}>
        <h1
          style={{
            margin: 0,
            fontFamily: "Space Grotesk",
            fontWeight: 700,
            fontSize: 70,
            letterSpacing: "-0.055em",
          }}
        >
          Current truth <span style={{color: COLORS.cobalt}}>≠</span> deleted history.
        </h1>
      </div>

      <BrowserFrame
        src="screens/dashboard-timeline.png"
        style={{
          position: "absolute",
          left: 90,
          top: 240,
          width: 1740,
          height: 690,
          opacity: stage,
          transform: `translateY(${(1 - stage) * 32}px)`,
        }}
        imageStyle={{transform: `scale(1.08) translateX(${(0.5 - move) * 45}px)`}}
        label="ENTITY TIMELINE / AGENT-RUNTIME"
      />

      <div
        style={{
          position: "absolute",
          left: 252,
          top: 532,
          zIndex: 12,
          opacity: reveal(frame, 72, 22),
        }}
      >
        <Pill tone="amber">Python 3.12 · superseded</Pill>
      </div>
      <div
        style={{
          position: "absolute",
          right: 250,
          top: 532,
          zIndex: 12,
          opacity: reveal(frame, 268, 22),
        }}
      >
        <Pill tone="green">Python 3.13 · current</Pill>
      </div>
      <div
        style={{
          position: "absolute",
          left: 568,
          right: 568,
          top: 550,
          height: 3,
          background: COLORS.amber,
          transformOrigin: "left",
          transform: `scaleX(${move})`,
          zIndex: 11,
        }}
      />
    </Scene>
  );
};
