import {useCurrentFrame} from "remotion";
import {BrowserFrame, Pill, Scene, reveal} from "../components";
import {COLORS} from "../constants";

export const RecallScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const left = reveal(frame, 48, 30);
  const right = reveal(frame, 92, 30);
  const receipt = reveal(frame, 332, 24);

  return (
    <Scene duration={duration} index={4} label="RECALL WITH RECEIPTS">
      <div style={{position: "absolute", left: 92, right: 92, top: 120}}>
        <div style={{display: "flex", alignItems: "flex-end", justifyContent: "space-between"}}>
          <h1
            style={{
              margin: 0,
              maxWidth: 1060,
              fontFamily: "Space Grotesk",
              fontSize: 64,
              lineHeight: 1,
              fontWeight: 700,
              letterSpacing: "-0.055em",
            }}
          >
            Ranked answers. <span style={{color: COLORS.cobalt}}>Auditable reasons.</span>
          </h1>
          <Pill>Trust × relevance</Pill>
        </div>
      </div>

      <BrowserFrame
        src="screens/dashboard-recall.png"
        style={{
          position: "absolute",
          left: 84,
          top: 274,
          width: 842,
          height: 652,
          opacity: left,
          transform: `translateX(${(1 - left) * -70}px)`,
        }}
        label="SCOPED RECALL"
      />
      <BrowserFrame
        src="screens/dashboard-trust-evidence.png"
        style={{
          position: "absolute",
          right: 84,
          top: 274,
          width: 842,
          height: 652,
          opacity: right,
          transform: `translateX(${(1 - right) * 70}px)`,
        }}
        label="TRUST EXPLANATION + TRACE"
      />

      <div
        style={{
          position: "absolute",
          left: 928,
          top: 548,
          width: 2,
          height: 240,
          background: COLORS.cobalt,
          opacity: reveal(frame, 250, 20),
          zIndex: 12,
        }}
      />
      <div
        style={{
          position: "absolute",
          right: 118,
          bottom: 76,
          zIndex: 15,
          opacity: receipt,
          transform: `translateY(${(1 - receipt) * 18}px)`,
        }}
      >
        <Pill tone="green">HydraDB algo.SSpaths · bounded trace</Pill>
      </div>
    </Scene>
  );
};
