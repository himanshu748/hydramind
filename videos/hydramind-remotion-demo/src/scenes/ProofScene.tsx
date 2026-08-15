import {interpolate, useCurrentFrame} from "remotion";
import {AnimatedNumber, BrandLockup, Pill, Scene, reveal} from "../components";
import {COLORS, REPO_URL} from "../constants";

const Metric: React.FC<{
  value: React.ReactNode;
  label: string;
  detail: string;
  tone?: "blue" | "green" | "amber";
  opacity: number;
}> = ({value, label, detail, tone = "blue", opacity}) => {
  const color = {blue: COLORS.cobalt, green: COLORS.green, amber: COLORS.amber}[tone];
  return (
    <div
      style={{
        border: `1.5px solid ${COLORS.border}`,
        background: "rgba(22,75,220,.035)",
        borderRadius: 18,
        padding: "28px 28px 25px",
        opacity,
        transform: `translateY(${(1 - opacity) * 22}px)`,
      }}
    >
      <div
        style={{
          fontFamily: "Space Grotesk",
          fontSize: 58,
          fontWeight: 700,
          letterSpacing: "-0.055em",
          color,
        }}
      >
        {value}
      </div>
      <div
        style={{
          marginTop: 10,
          fontFamily: "IBM Plex Mono",
          fontSize: 16,
          fontWeight: 600,
          letterSpacing: "0.07em",
          color: COLORS.ink,
        }}
      >
        {label}
      </div>
      <div style={{marginTop: 9, fontFamily: "Inter", fontSize: 17, color: COLORS.muted}}>{detail}</div>
    </div>
  );
};
export const ProofScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const proofFade = interpolate(frame, [465, 525], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const lockup = reveal(frame, 505, 36);

  return (
    <Scene duration={duration} index={7} label="VERIFIED RELEASE">
      <div style={{position: "absolute", inset: 0, opacity: proofFade}}>
        <div style={{position: "absolute", left: 92, right: 92, top: 120}}>
          <div style={{display: "flex", alignItems: "flex-end", justifyContent: "space-between"}}>
            <h1
              style={{
                margin: 0,
                fontFamily: "Space Grotesk",
                fontSize: 75,
                fontWeight: 700,
                letterSpacing: "-0.055em",
              }}
            >
              Tested where it <span style={{color: COLORS.cobalt}}>matters.</span>
            </h1>
            <Pill tone="green">Release evidence</Pill>
          </div>
        </div>

        <div
          style={{
            position: "absolute",
            left: 92,
            right: 92,
            top: 260,
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 18,
          }}
        >
          <Metric
            value={<><AnimatedNumber value={48} at={20} /> / 48</>}
            label="FULL TEST SUITE"
            detail="18 database-independent · 30 live"
            opacity={reveal(frame, 20, 24)}
          />
          <Metric
            value={<AnimatedNumber value={30} at={80} />}
            label="LIVE HYDRADB TESTS"
            detail="Real Bolt + OpenCypher behavior"
            tone="green"
            opacity={reveal(frame, 80, 24)}
          />
          <Metric
            value={<><AnimatedNumber value={250} at={148} /> / 250</>}
            label="STRESS WRITES"
            detail="Every target verified after restart"
            tone="amber"
            opacity={reveal(frame, 148, 24)}
          />
          <Metric
            value={<AnimatedNumber value={3} at={215} />}
            label="REAL MCP TRANSPORT TESTS"
            detail="stdio · HTTP · fresh process"
            opacity={reveal(frame, 215, 24)}
          />
          <Metric
            value={<><AnimatedNumber value={6} at={276} /> / 6</>}
            label="TRACK 03 SMOKE"
            detail="Self-authored · includes abstention"
            tone="green"
            opacity={reveal(frame, 276, 24)}
          />
          <Metric
            value={<><AnimatedNumber value={91} at={338} />%</>}
            label="CORE COVERAGE"
            detail="Plus 50 / 50 exact stress recalls"
            tone="amber"
            opacity={reveal(frame, 338, 24)}
          />
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          opacity: lockup,
          transform: `scale(${0.96 + lockup * 0.04})`,
        }}
      >
        <div
          style={{
            position: "absolute",
            width: 760,
            height: 760,
            borderRadius: 999,
            border: "1px solid rgba(22,75,220,.12)",
          }}
        />
        <div
          style={{
            position: "absolute",
            width: 520,
            height: 520,
            borderRadius: 999,
            border: "1px solid rgba(22,75,220,.17)",
          }}
        />
        <BrandLockup />
        <div
          style={{
            marginTop: 38,
            fontFamily: "Space Grotesk",
            fontSize: 73,
            lineHeight: 1.02,
            fontWeight: 700,
            textAlign: "center",
            letterSpacing: "-0.06em",
          }}
        >
          Persistent memory,
          <br />
          <span style={{color: COLORS.cobalt}}>with receipts.</span>
        </div>
        <div
          style={{
            marginTop: 40,
            borderRadius: 999,
            background: COLORS.cobalt,
            color: COLORS.cream,
            padding: "17px 29px",
            fontFamily: "IBM Plex Mono",
            fontSize: 18,
            letterSpacing: "0.03em",
          }}
        >
          {REPO_URL}
        </div>
      </div>
    </Scene>
  );
};
