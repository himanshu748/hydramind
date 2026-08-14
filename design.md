# Generated-app design system

Every app the swarm ships follows these rules. The frontend agent receives this file verbatim in its system prompt; the critic may flag high-severity violations of the non-negotiables.

## Non-negotiables

1. Responsive from 360px to 1440px. The head contains exactly `<meta name="viewport" content="width=device-width, initial-scale=1">`. Layout uses flex/grid with sensible wrapping; no horizontal page scroll at any width; touch targets at least 40px.
2. Real interactivity with real states: hover, focus-visible, disabled, loading, empty and error states all designed, not defaulted. An empty screen tells the user what to do next.
3. Accessible floor: semantic elements (button, form, label), contrast at least 4.5:1 for body text, visible keyboard focus, `prefers-reduced-motion` respected.
4. No lorem ipsum, no placeholder images, no dead buttons. If a control exists, it works.

## Look and feel

- Color comes from the subject's world, never from habit. Ask: what would this thing's physical or cultural materials look like? A recipe journal earns warm paper and tomato red, a finance tool earns banknote green or ledger ink blue, a sleep app earns deep night blues, a climbing log earns chalk and granite. Commit to the palette the plan's design_direction names.
- Banned defaults: do not reach for emerald/mint green, teal or violet-on-near-black unless the subject specifically earns them (a forest app earns green; a generic tracker does not). These are the palettes every AI tool produces; producing them means the design failed.
- Dark or light is also a subject decision: night-adjacent and focus subjects go dark; domestic, editorial, health and daytime subjects usually deserve a light or warm theme. Do not default to dark. Same discipline either way: deep neutral surfaces, one saturated accent, neutrals for everything else.
- Type: choose real typefaces on purpose and load them from Google Fonts with a preconnect. Pair a display face that carries the subject's character with a clean text face, and add a mono only where numbers or labels earn it. Editorial and domestic subjects usually want a serif display (Fraunces, Instrument Serif, Newsreader, Lora); technical and utility subjects want a confident sans (Geist, Inter Tight, Space Grotesk). Falling back to the system stack is a failure of nerve, not restraint: it is the single clearest tell of a generated page.
- Then still win on hierarchy: one display size for the page title, a clear label/body/caption scale, and tabular numerals for any stat or timer.
- Space: generous padding (16 to 24px in cards), consistent radius (8 to 12px), 1px borders from a neutral tone rather than heavy shadows.
- Motion, and this applies to every archetype including tools and dashboards: 150 to 250ms ease-out transitions on state changes, scroll-triggered reveals via IntersectionObserver (fade plus a 12 to 24px rise, staggered children, once only), one entrance sequence for the header or hero on load, and hover lift on cards using transform only. Plus at most one slow ambient loop where it depicts something true about the subject (steam off a mug, a plant leaning to light, a record turning, a timer breathing). Gate everything behind prefers-reduced-motion. An app that only animates on click feels like a form; ambient motion that depicts nothing is what to cut, not motion as such.
- Depth is allowed everywhere too: a subtle radial glow, a faint grid or noise layer, gradient text on the one headline that earns it. At most two such devices per screen, chosen for the subject.
- Draw the subject, do not only typeset it. Render its characteristic object as inline SVG and use it structurally: books become spines on a shelf, plants become pots in a row, records become sleeves, workouts become a load curve. Hand-built SVG at this scale beats an icon font or an emoji, and it is usually the difference between a designed app and a styled form.
- Personality comes from the subject: a habit tracker can celebrate a streak, a pomodoro timer can breathe. One signature moment per app, everything else quiet.

## Marketing sites (the Framer bar)

When the plan's archetype is "site" (landing page, portfolio, product site), the output must feel like a designed site, not a form with a header. All of the above still applies, plus:

- Structure: sticky translucent nav (backdrop blur), full-viewport hero with one strong composition, alternating content sections, a proper footer. Use the plan's sections list as the outline.
- Motion and depth: the shared rules above already cover reveals, the entrance sequence, hover lift and the two depth devices. A site may spend its full allowance on the hero rather than spreading it thin.
- Typography: hero headline at clamp(2.5rem, 7vw, 5rem) with tight leading and letter-spacing, an eyebrow label above it, balanced text wrapping. Scale drops deliberately through the page.
- Bento or feature grids beat bullet lists. Cards carry one idea each with a visual anchor (number, icon drawn as inline SVG, or stat).
- Real copy: specific headlines about the subject, not "Welcome to our website". Social proof, pricing or FAQ sections get realistic, subject-appropriate content.
- Forms wired for real: waitlist/contact forms POST to the contract endpoint, show inline success and error states, never dead-end.

## Copy

- Sentence case, plain verbs, buttons say what they do ("Add task", not "Submit").
- Empty states invite action ("Create your first habit"), errors say what failed and what to do.
- No exclamation marks, no hype.
- Never use em dashes or en dashes anywhere in copy, code comments or generated text. Use a comma, a period, a colon or parentheses instead.
- Invent an original app name; never use an existing product's name (no "Splitwise", "Todoist", "Notion" clones by name).

## Craft principles (how the good ones think)

- The hero is a thesis. Open with the most characteristic thing in the subject's world, not a generic welcome. A big number with a small label plus a gradient accent is the template answer; only use it when it is truly the best option.
- Typography carries personality. Set a deliberate scale (one display size, clear label/body/caption steps) and let weight and spacing do the work. Tabular numerals for any stat, timer or price.
- Structure is information. Use numbered markers, eyebrows or dividers only when they encode something true about the content (a real sequence, a real hierarchy), never as decoration.
- One signature element per page: the single thing the page will be remembered by (a waveform under the headline, a recipe card texture, a breathing timer ring). Build it, usually as inline SVG, and spend the boldness there while everything around it stays quiet. A page with no signature element has failed this checklist even if every other rule passes.
- Remove one accessory before shipping: if a glow, gradient or animation does not serve the subject, cut it. This is a rule about accessories, never about the signature element or the subject's own illustration; do not economise your way to a page of plain boxes.
- Fill the fields the contract gives you. If an entity carries a description, tags, a count or a colour token, the card that renders it shows them. Empty space inside a card where real data exists is a bug, not restraint.
- Copy is design material. Name things by what the user controls ("Add recipe", not "Submit entry"), keep one name per action through the whole flow, and let empty states invite the first action.
