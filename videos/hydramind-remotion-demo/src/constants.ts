export const FPS = 30;

export const COLORS = {
  cream: "#fffdf7",
  ink: "#191c20",
  cobalt: "#164bdc",
  green: "#347745",
  red: "#c2413a",
  amber: "#d78927",
  muted: "#687078",
  paleBlue: "#edf2ff",
  border: "rgba(22, 75, 220, 0.18)",
} as const;

export const SCENES = [
  {id: "problem", frames: 265, audio: "01.wav"},
  {id: "meet", frames: 392, audio: "02.wav"},
  {id: "contradiction", frames: 545, audio: "03.wav"},
  {id: "recall", frames: 583, audio: "04.wav"},
  {id: "timeline", frames: 462, audio: "05.wav"},
  {id: "graph-native", frames: 614, audio: "06.wav"},
  {id: "proof", frames: 813, audio: "07.wav"},
] as const;

export const SCENE_STARTS = SCENES.map((_, index) =>
  SCENES.slice(0, index).reduce((total, scene) => total + scene.frames, 0),
);

export const TOTAL_FRAMES = SCENES.reduce(
  (total, scene) => total + scene.frames,
  0,
);

export const REPO_URL = "github.com/himanshu748/hydramind";
