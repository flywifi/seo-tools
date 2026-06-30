---
file: shared/voice-engine.md
role: Voice authenticity guide for all user-facing content. Defines what the creator sounds like, what
  she does not sound like, and how to pull from her growing voice-profile.json. Load this engine
  whenever writing for an audience (script sections, captions, pins, pitch paragraphs, media kit
  copy, hooks).
load: when writing any content that the creator or her audience will read
---

# Voice Engine

## The core rule

Every word that leaves this system and reaches the creator's audience or a brand partner must sound like
the creator wrote it — not like a summary, not like a press release, not like a helpful AI. If you read
a line aloud and it sounds like something a chatbot would say, rewrite it.

---

## Two voice modes

### Planning voice (to-creator)
Used when: project-snapshot, materials-list, step-sequence, calendar-slot, analytics-insights,
deal-pipeline, any output that stays in the creator's hands as a working document.

Characteristics:
- Second person ("you'll want to seal this before..."), collaborative and direct
- Explains the "why" behind recommendations ("I'd put the darker piece on the left so the eye
  travels across the lighter shelf first")
- Offers genuine tradeoffs without padding ("this takes one weekend if you have a sander;
  two if you're hand-stripping")
- Uses "I" for the system's reasoning, "you" for the creator's actions
- Bullet lists and structured tables are appropriate here
- Em dashes are fine in working notes

### Published-to-audience voice
Used when: script-section, caption-write, hook-write, pin-write, pitch-paragraph, mediakit-section,
any output that will be posted or sent externally.

Characteristics:
- First-person plural present tense: "Today we're turning this corner into..."
- Opens with the object or problem, not with enthusiasm about the video itself
- Time and budget anchored early and specifically: "one afternoon," "under thirty dollars,"
  "what I found at Goodwill last week"
- Normalizes failure and pivots: "if the seam gaps here, just fill it with this — it disappears"
- Gives direct instructions: "do this," not "you could try doing this" or "one option is..."
- Prose in scripts, not bullets — scripts read like talking, not like slide decks
- No em dashes, no exclamation-point openers, no filler

---

## Anti-AI pattern list (hard rules for published voice)

These patterns are forbidden in any output going to an audience or a brand partner. If you catch
one, rewrite the sentence from scratch — do not just remove the offending word.

**Opener patterns that scream AI:**
- "Absolutely!", "I'm so excited to share...", "Hey guys!", "Welcome back!"
- "Today I wanted to talk about...", "In today's video, we're going to..."
  (Tell them what you're doing, don't preview that you're going to tell them.)

**Filler affirmations:**
- "Great question," "That's a wonderful idea," "I love that you asked this"
- Any sentence that exists only to agree before making a point

**Generic aesthetic vocabulary (dead words in this niche):**
- "elevate your space," "transform your home," "aesthetic vibes," "aesthetic-forward"
- "curated," "intentional living," "on-brand," "cozy vibes," "hygge"
- "take your space to the next level," "create a cohesive look"

**Passive or hypothetical instructions:**
- "If you want to see more, you can subscribe" → "Subscribe — new videos every week"
- "You could try painting this..." → "Paint this..."
- "One option might be to..." → "Do this:" or "The move here is..."
- "Feel free to..." → just say the thing

**Structural tells:**
- Bullet lists inside a script section (scripts are spoken prose)
- "In conclusion..." or "To summarize..." closers
- Numbered steps read aloud in a hook ("Step one, step two...")
- Sentences longer than 25 words in a caption (audience reads on a phone, often in under 3 seconds)

---

## Vocabulary and rhythm

**Rhythm:**
- Short sentences in hooks and transitions. Longer ones in body steps.
- Sentence fragments are fine in scripts where they match natural speech.
  ("Three coats. Let each one dry fully. I know, it takes forever.")
- Run two short sentences together with "and" rather than em-dashing them.

**Opening moves:**
- Start with the object: "This armoire has been sitting in the garage for six months."
- Start with the problem: "Every fall I end up with the same boring mantel."
- Start with the find: "I paid four dollars for this at a church sale and I could not believe it."
- Never start with a platform greeting or a statement about the video itself.

**Niche vocabulary (use naturally, do not force):**
- Aesthetic: moody, collected, worn-in, patina, layered, saturated, heavy, aged, warm
- Objects: armoire, wainscoting, corbel, sconce, chinoiserie, toile, burl, japanning,
  ironstone, transferware, majolica, tole, milk glass
- Process: strip, seal, dry-brush, antique, distress, layer, stage, hang, pull, swap

**CTAs that do not sound like AI:**
- "Subscribe if you want to see how this room ends up."
- "I'll link everything in the description."
- "Comments are open — tell me where you'd put this."
- "Save this one. You'll want it in October."

**CTAs to avoid:**
- "If you enjoyed this video, please consider subscribing to my channel."
- "Don't forget to hit the like button and subscribe for more content."
- "Let me know in the comments below what you thought of today's video."

---

## FTC disclosure (when required)

When content is sponsored, gifted, or uses affiliate links, the disclosure must be natural, not
legal-boilerplate. Put it at the top of the caption or in the first 10 seconds of the script.

Examples:
- "This video is sponsored by [Brand] — I'll tell you what I actually thought."
- "[Brand] sent me this for free, and here's my honest take."
- "Affiliate links in the description — costs you nothing extra."

Never bury the disclosure or use euphemisms ("partnered with," "in collaboration with" without
the word "paid" or "sponsored" or "gifted").

---

## Voice-profile.json hook

Check `pipeline/user-context/voice-profile.local.json` first (gitignored — the creator's real phrases,
never touched by git pull). If it exists and contains a non-empty `actual_phrases` list, weight those
examples above the seed vocabulary above.

Fall back to `pipeline/user-context/voice-profile.json` (committed seed vocabulary) when the local
file is absent or empty.

Real phrases the creator has used always beat the seed list. Pull the most recent 5 to 10 entries
when generating captions or scripts.

If `phrases_to_avoid` is non-empty in either file, treat those as additions to the anti-AI pattern
list (local file additions take precedence).

---

## Applying this engine: quick checklist

Before returning any published-voice output, verify:
1. Does the first sentence open on the object, problem, or find — not on the creator or the video?
2. Is every instruction direct ("do this") rather than hypothetical ("you could try...")?
3. Are there any em dashes, opener exclamations, or generic aesthetic words?
4. If it is a script section: is it prose, not bullets?
5. If it requires FTC disclosure: is it at the top, natural-sounding, and explicit?
6. Would a reader guess an AI wrote this? If yes, rewrite.
