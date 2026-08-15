# HydraMind Hack Hydra demo

This is the source for HydraMind's caption-free, 122-second product demo. It is
built entirely in Remotion and combines real dashboard captures with code-native
motion graphics, a narrated trust-decay story, and defensible verification
evidence.

## Preview

```bash
npm ci
npm run dev
```

Open the `HydraMindLaunch` composition in Remotion Studio.

## Verify and render

```bash
npm run lint
npm run build
npm run render
```

The final render is written to `renders/hydramind-hack-hydra.mp4`. Rendered media,
temporary stills, the Remotion bundle, and `node_modules` are intentionally ignored;
the composition source, narration stems, fonts, and source captures are committed
so the video can be reproduced from a clean clone.

## Story

The seven scenes cover the stale-memory problem, the HydraMind graph model,
contradiction-driven trust decay, scoped evidence recall, explicit revision
timelines, native HydraDB path tracing, and the final test/stress proof. The video
does not claim LongMemEval or semantic retrieval: HydraMind's current relevance and
conflict gates are transparent lexical heuristics.
