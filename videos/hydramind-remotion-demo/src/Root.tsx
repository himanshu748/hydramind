import "./index.css";
import {Composition} from "remotion";
import {HydraMindLaunch} from "./Composition";
import {FPS, TOTAL_FRAMES} from "./constants";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="HydraMindLaunch"
    component={HydraMindLaunch}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
