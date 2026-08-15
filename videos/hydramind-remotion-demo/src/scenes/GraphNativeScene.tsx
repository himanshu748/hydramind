import {interpolate, useCurrentFrame} from "remotion";
import {BrandLockup, Node, Pill, Scene, reveal} from "../components";
import {COLORS} from "../constants";

const Terminal: React.FC<{frame: number}> = ({frame}) => {
  const lines = [
    "$ codex mcp add hydramind -- hydramind",
    "✓ connected · MCP 2026-07-28 · sessionless",
    "> remember(\"Production deploys must not use direct routing\")",
    "✓ memory written · CONTRADICTS persisted · trust 1.00 → 0.60",
    "> trace_memory(memory_id, scope, max_hops=2)",
    "✓ engine: HydraDB algo.SSpaths · bounded evidence returned",
  ];

  return (
    <div
      style={{
        position: "absolute",
        right: 86,
        top: 232,
        width: 790,
        height: 590,
        borderRadius: 20,
        border: "1px solid rgba(255,253,247,.15)",
        background: "#101316",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          height: 46,
          display: "flex",
          alignItems: "center",
          borderBottom: "1px solid rgba(255,253,247,.12)",
          padding: "0 18px",
          color: "rgba(255,253,247,.5)",
          fontFamily: "IBM Plex Mono",
          fontSize: 13,
          letterSpacing: "0.08em",
        }}
      >
        MCP STDIO INTERACTION · TRANSPORT-TESTED
      </div>
      <div style={{padding: "28px 30px"}}>
        {lines.map((line, index) => {
          const progress = reveal(frame, 46 + index * 55, 18);
          const success = line.startsWith("✓");
          return (
            <div
              key={line}
              style={{
                minHeight: 70,
                opacity: progress,
                transform: `translateY(${(1 - progress) * 11}px)`,
                color: success ? "#81d49a" : index % 2 === 0 ? "#a9c1ff" : COLORS.cream,
                fontFamily: "IBM Plex Mono",
                fontSize: success ? 16 : 17,
                lineHeight: 1.45,
                letterSpacing: "-0.01em",
              }}
            >
              {line}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const GraphNativeScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const hub = reveal(frame, 20, 28);
  const links = reveal(frame, 112, 40);
  const scale = interpolate(frame, [0, duration], [0.97, 1.02]);

  return (
    <Scene duration={duration} dark index={6} label="GRAPH-NATIVE BY DESIGN">
      <div style={{position: "absolute", left: 88, top: 123}}>
        <h1
          style={{
            margin: 0,
            fontFamily: "Space Grotesk",
            fontSize: 67,
            lineHeight: 1,
            fontWeight: 700,
            letterSpacing: "-0.055em",
          }}
        >
          Not graph-shaped. <span style={{color: COLORS.green}}>Graph-native.</span>
        </h1>
      </div>

      <div
        style={{
          position: "absolute",
          left: 50,
          top: 225,
          width: 930,
          height: 660,
          transform: `scale(${scale})`,
          transformOrigin: "center",
          opacity: hub,
        }}
      >
        <svg width="930" height="660" viewBox="0 0 930 660" style={{position: "absolute", inset: 0}}>
          {[
            [455, 110],
            [186, 250],
            [734, 250],
            [210, 525],
            [700, 525],
          ].map(([x, y]) => (
            <path
              key={`${x}-${y}`}
              d={`M455 330 C455 330 ${x} ${y} ${x} ${y}`}
              fill="none"
              stroke="rgba(255,253,247,.25)"
              strokeWidth="2"
              pathLength="1"
              strokeDasharray="1"
              strokeDashoffset={1 - links}
            />
          ))}
        </svg>
        <div
          style={{
            position: "absolute",
            left: 455,
            top: 330,
            transform: "translate(-50%, -50%)",
            width: 220,
            height: 220,
            borderRadius: 999,
            border: `2px solid ${COLORS.green}`,
            background: "rgba(52,119,69,.13)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <BrandLockup light />
        </div>
        <Node x={455} y={110} label="HYDRADB" tone="green" scale={reveal(frame, 60, 18)} />
        <Node x={186} y={250} label="BOLT" tone="blue" scale={reveal(frame, 90, 18)} />
        <Node x={734} y={250} label="OPENCYPHER" tone="blue" scale={reveal(frame, 120, 18)} />
        <Node x={210} y={525} label="BOUNDED PATHS" tone="amber" scale={reveal(frame, 180, 18)} />
        <Node x={700} y={525} label="SCOPED IDS" tone="red" scale={reveal(frame, 220, 18)} />
      </div>

      <Terminal frame={frame} />
      <div style={{position: "absolute", right: 90, bottom: 100, opacity: reveal(frame, 400, 22)}}>
        <Pill tone="ink">State belongs in HydraDB—not the MCP session</Pill>
      </div>
    </Scene>
  );
};
