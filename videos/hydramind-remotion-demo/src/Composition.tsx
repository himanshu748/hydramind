import {Audio} from "@remotion/media";
import {AbsoluteFill, Sequence, staticFile} from "remotion";
import {SCENES, SCENE_STARTS} from "./constants";
import {ContradictionScene} from "./scenes/ContradictionScene";
import {GraphNativeScene} from "./scenes/GraphNativeScene";
import {MeetScene} from "./scenes/MeetScene";
import {ProblemScene} from "./scenes/ProblemScene";
import {ProofScene} from "./scenes/ProofScene";
import {RecallScene} from "./scenes/RecallScene";
import {TimelineScene} from "./scenes/TimelineScene";

const sceneComponents = [
  ProblemScene,
  MeetScene,
  ContradictionScene,
  RecallScene,
  TimelineScene,
  GraphNativeScene,
  ProofScene,
] as const;

export const HydraMindLaunch: React.FC = () => (
  <AbsoluteFill style={{background: "#fffdf7"}}>
    {SCENES.map((scene, index) => {
      const Component = sceneComponents[index];
      return (
        <Sequence
          key={scene.id}
          from={SCENE_STARTS[index]}
          durationInFrames={scene.frames}
          premountFor={30}
        >
          <Component duration={scene.frames} />
          <Audio src={staticFile(`audio/${scene.audio}`)} volume={1} />
        </Sequence>
      );
    })}
  </AbsoluteFill>
);
