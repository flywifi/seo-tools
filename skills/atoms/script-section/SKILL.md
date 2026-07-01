---
file: skills/atoms/script-section/SKILL.md
name: script-section
description: Write ONE named section of a YouTube video script for the creator in planning-to-the creator voice (speaking notes, second person). Sections are hook, intro, body-step, broll-cue, transition, cta, and outro. Use when any scripting or video-development workflow needs a single section drafted. Do NOT use to write a full script in one call; call this atom once per section and use workflow.json repeat per_section to compose the full script.
load:
  - shared/brand-engine.md
  - shared/voice-engine.md
---

# script-section

Write one named section of a YouTube video script in planning-to-the creator voice (speaking notes, second
person, "you'll say..."). Designed to be called once per section and composed into a full script via
workflow.json `repeat: per_section`.

## Purpose

Produce a single discrete script section that a spoke can assemble, in order, into a complete video
script. Each call writes exactly one section. The output is planning language addressed to the creator, not
published audience-facing copy. Tone is collaborative and practical (see "planning to the creator" mode in
`shared/brand-engine.md`).

The seven supported section types are:

- **hook** -- the opening moment (first 15 to 30 seconds on long-form; first 3 to 5 seconds on
  Shorts). States the promise or problem fast. Cuts long intros. Matches the platform opening-window
  rules in `shared/platform-engine.md`.
- **intro** -- brief context after the hook. Who you are, what the viewer will get, and why it
  matters to them. Keep it tight; retention drops in this window.
- **body-step** -- one numbered project step in conversational spoken form. Explain the action, the
  reason it matters, and any tip or watchout. Repeat this section type once per project step.
- **broll-cue** -- a production note section naming specific b-roll shots to capture at a given point
  in the script. Not spoken content; editor-facing only.
- **transition** -- a short spoken bridge (one to three sentences) that moves between two body steps
  or sections without losing momentum.
- **cta** -- the call-to-action window. Prompts subscribe, like, comment, or click. Warm and
  conversational; never pushy. Matches platform norms.
- **outro** -- closes the video. Teases the next video or playlist, thanks the viewer, signs off
  in the creator's voice.

## Inputs

```json
{
  "section_type": "hook | intro | body-step | broll-cue | transition | cta | outro (required)",
  "topic": "string (required) -- the video topic or project title, e.g. 'stylized bookshelf makeover'",
  "step_content": "string (optional, required when section_type is body-step) -- the specific step action and detail to convert into spoken script",
  "target_duration_seconds": "integer (optional) -- desired spoken length for this section in seconds",
  "platform": "youtube | shorts (optional, default youtube) -- determines opening-window timing and CTA norms"
}
```

Field notes:

- `section_type` controls the template, tone target, and timing expectation for the section.
- `topic` anchors brand voice, aesthetic, and relevance for every section type.
- `step_content` is required for `body-step`. Pass the action and detail from the step-sequence
  atom output. Omit for all other section types.
- `target_duration_seconds` is a planning target, not a guarantee. Actual delivery time varies by
  pace. If omitted, defaults apply by section type: hook 15 to 30 s (youtube) or 3 to 5 s (shorts);
  intro 30 to 60 s; body-step 60 to 120 s; broll-cue 0 s (not spoken); transition 5 to 15 s;
  cta 20 to 30 s; outro 15 to 30 s.
- `platform` shifts timing defaults and CTA language. On Shorts, hooks must work with zero prior
  context; see `shared/platform-engine.md`.

## Output

```json
{
  "section_type": "string -- mirrors the input section_type",
  "script_text": "string -- the speaking notes for the creator, written in second person planning voice (e.g. 'You'll open by holding up the before photo and saying: ...'). broll-cue sections contain editor notes, not spoken copy.",
  "duration_estimate_seconds": "integer -- rough estimate of spoken delivery time; 0 for broll-cue",
  "notes": "string or null -- timing or delivery tips for the creator (e.g. 'Pause here to let the before image land before moving on'). Null when no tips apply.",
  "broll_suggestion": "string or null -- a specific b-roll shot or sequence to capture at this point in the script. Always populated for broll-cue sections. Populated for other sections when a strong visual opportunity exists. Null otherwise."
}
```

Output rules:

- `script_text` is always in planning-to-the creator voice. Use "you" to address the creator. Write as speaking
  notes, not a verbatim teleprompter script: guide the delivery without locking every word. Example
  register: "You'll say something like: 'This corner was a disaster for two years, and I finally
  fixed it in one weekend.'"
- For `broll-cue` sections, `script_text` contains editor-facing production notes only (no spoken
  copy). `duration_estimate_seconds` is 0.
- `duration_estimate_seconds` is a rough planning range midpoint. Actual delivery time varies by pace
  and adlib. Never present it as a guaranteed runtime.
- `broll_suggestion` for non-broll-cue sections names one opportunistic shot. Keep it short and
  actionable ("overhead pour shot as you mix the stain").
- Do not fabricate product names, brand timings, measurements, or prices. If the input step_content
  references specifics, carry them through; do not invent new ones.
- Never use em dashes. Write ranges with "to" per `protocols/formatting-metadata.md`.
- Voice anchors to the home decor aesthetic and the bungalow context from `shared/brand-engine.md`.
  Warm, conversational, imperfect-is-fine energy.

## Do NOT use for

- Writing a full script in one call. Call this atom once per section; use `workflow.json`
  `repeat: per_section` in the parent spoke to compose the complete script.
- Writing audience-facing published copy such as captions, descriptions, or pin text (use
  caption-write or document-studio).
- Generating a hook for a Short without passing `platform: shorts`; the timing and no-context rules
  differ significantly from long-form.
- Writing project step sequences (use step-sequence atom to generate steps first, then pass each
  step's content here as `step_content`).
- Generating titles, thumbnails, or SEO metadata (use title-generate, thumbnail-concept, or
  seo-keywords).

## References

- `shared/brand-engine.md` -- voice modes; use "planning to the creator" mode for all output from this atom.
- `shared/platform-engine.md` -- hook opening-window lengths, Short vs long-form timing rules, and
  CTA norms per platform.
- `protocols/formatting-metadata.md` -- no em dashes; ranges use "to."
- `protocols/no-fabrication.md` -- do not invent measurements, product names, prices, or timings not
  present in the inputs.
