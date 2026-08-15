import {interpolate, useCurrentFrame} from "remotion";
import {BrowserFrame, Pill, Scene, reveal} from "../components";
import {COLORS} from "../constants";

export const MeetScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const screenIn = reveal(frame, 18, 34);
  const scale = interpolate(frame, [0, duration], [1.13, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <Scene duration={duration} index={2} label="MEET HYDRAMIND">
      <div style={{position: "absolute", left: 92, top: 132, width: 730}}>
        <Pill>Stateless MCP · durable graph</Pill>
        <h1
          style={{
            margin: "26px 0 0",
            fontFamily: "Space Grotesk",
            fontWeight: 700,
            fontSize: 78,
            letterSpacing: "-0.055em",
            lineHeight: 0.99,
          }}
        >
          Memory that keeps
          <br />
          <span style={{color: COLORS.cobalt}}>its receipts.</span>
        </h1>
        <div
          style={{
            marginTop: 34,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 14,
            width: 650,
          }}
        >
          {["BOLT + OPENCYPHER", "HYDRADB DURABILITY", "SESSIONLESS MCP", "TRUST-WEIGHTED"].map(
            (label, index) => {
              const item = reveal(frame, 94 + index * 25, 18);
              return (
                <div
                  key={label}
                  style={{
                    opacity: item,
                    transform: `translateY(${(1 - item) * 18}px)`,
                    border: `1px solid ${COLORS.border}`,
                    background: "rgba(22,75,220,.04)",
                    borderRadius: 14,
                    padding: "17px 18px",
                    fontFamily: "IBM Plex Mono",
                    fontSize: 15,
                    color: COLORS.cobalt,
                  }}
                >
                  {label}
                </div>
              );
            },
          )}
        </div>
      </div>

      <BrowserFrame
        src="screens/landing-hero.png"
        style={{
          position: "absolute",
          right: -118,
          top: 130,
          width: 1080,
          height: 770,
          opacity: screenIn,
          transform: `translateX(${(1 - screenIn) * 76}px) rotate(-1.4deg) scale(${scale})`,
          transformOrigin: "center",
        }}
        imageStyle={{objectPosition: "center"}}
        label="HYDRAMIND / LIVE PRODUCT"
      />
    </Scene>
  );
};
