import {interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {COLORS} from "../constants";
import {Pill, Scene, reveal} from "../components";

export const ProblemScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const titleIn = spring({frame, fps, config: {damping: 18, mass: 0.85}});
  const truthIn = reveal(frame, 76, 26);
  const wrongIn = reveal(frame, 128, 22);
  const chainIn = reveal(frame, 164, 30);
  const drift = interpolate(frame, [0, duration], [0, -34]);

  return (
    <Scene duration={duration} dark index={1} label="THE PROBLEM">
      <div
        style={{
          position: "absolute",
          left: 92,
          top: 156,
          width: 1160,
          transform: `translateY(${(1 - titleIn) * 42}px)`,
          opacity: titleIn,
        }}
      >
        <Pill tone="ink">Persistent memory is not enough</Pill>
        <div
          style={{
            marginTop: 26,
            fontFamily: "Space Grotesk",
            fontSize: 108,
            lineHeight: 0.96,
            fontWeight: 700,
            letterSpacing: "-0.065em",
          }}
        >
          Yesterday&apos;s fact.
          <br />
          <span style={{color: COLORS.green}}>Still true?</span>
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          right: 70,
          top: 138 + drift,
          width: 585,
          height: 790,
        }}
      >
        <svg width="585" height="790" viewBox="0 0 585 790">
          <path d="M287 96 C268 190 278 262 300 348" stroke="rgba(255,253,247,.18)" strokeWidth="2" fill="none" />
          <path d="M300 348 C206 430 168 508 145 642" stroke="rgba(215,137,39,.75)" strokeWidth="3" fill="none" strokeDasharray="8 10" opacity={chainIn} />
          <path d="M300 348 C382 438 420 532 448 665" stroke="rgba(215,137,39,.75)" strokeWidth="3" fill="none" strokeDasharray="8 10" opacity={chainIn} />
          <circle cx="287" cy="96" r="70" fill="rgba(22,75,220,.18)" stroke={COLORS.cobalt} strokeWidth="3" />
          <circle cx="300" cy="348" r="86" fill="rgba(194,65,58,.18)" stroke={COLORS.red} strokeWidth="3" opacity={wrongIn} />
          <circle cx="145" cy="642" r="58" fill="rgba(215,137,39,.15)" stroke={COLORS.amber} strokeWidth="2" opacity={chainIn} />
          <circle cx="448" cy="665" r="58" fill="rgba(215,137,39,.15)" stroke={COLORS.amber} strokeWidth="2" opacity={chainIn} />
          <text x="287" y="92" fill={COLORS.cream} fontFamily="IBM Plex Mono" fontSize="18" textAnchor="middle">FACT</text>
          <text x="287" y="118" fill="rgba(255,253,247,.58)" fontFamily="IBM Plex Mono" fontSize="15" textAnchor="middle">trust 1.00</text>
          <text x="300" y="342" fill={COLORS.cream} fontFamily="IBM Plex Mono" fontSize="17" textAnchor="middle" opacity={wrongIn}>CONTRADICTED</text>
          <text x="300" y="371" fill="#ff9a94" fontFamily="IBM Plex Mono" fontSize="18" textAnchor="middle" opacity={wrongIn}>trust 0.60</text>
          <text x="145" y="647" fill={COLORS.cream} fontFamily="IBM Plex Mono" fontSize="15" textAnchor="middle" opacity={chainIn}>0.85</text>
          <text x="448" y="670" fill={COLORS.cream} fontFamily="IBM Plex Mono" fontSize="15" textAnchor="middle" opacity={chainIn}>0.70</text>
        </svg>
      </div>

      <div
        style={{
          position: "absolute",
          left: 96,
          bottom: 86,
          display: "flex",
          alignItems: "center",
          gap: 16,
          opacity: truthIn,
        }}
      >
        <span style={{width: 58, height: 3, background: COLORS.cobalt}} />
        <span
          style={{
            fontFamily: "IBM Plex Mono",
            fontSize: 20,
            color: "rgba(255,253,247,.72)",
            letterSpacing: "0.04em",
          }}
        >
          What changed—and what depended on it?
        </span>
      </div>
    </Scene>
  );
};
