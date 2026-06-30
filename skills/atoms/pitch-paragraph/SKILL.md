---
file: skills/atoms/pitch-paragraph/SKILL.md
name: pitch-paragraph
description: >
  Write the personalized pitch paragraph for a brand partnership outreach email or media kit.
  Anchors to a specific brand, connects Alex's moody-vintage aesthetic and audience to the brand's
  product category, and proposes a concrete content format. Outputs the pitch paragraph, three
  subject line options, and personalization notes for the sender to verify before use. Do NOT use
  to send emails, post to any external system, or produce final outreach copy without human review.
load: on_demand
---

# pitch-paragraph

Write Alex Slason's personalized pitch paragraph for a brand partnership inquiry.

## Purpose

Produce one ready-to-refine pitch paragraph (150 to 250 words) that a spoke or human writer can
drop into an outreach email or media kit. The paragraph must feel specific to the target brand, not
templated. It names the brand, connects its product category to Alex's content aesthetic and audience
in concrete terms, and proposes a single content format with enough detail that the brand contact
understands what a collaboration would look like.

Voice follows the professional outreach mode of `shared/brand-engine.md`: warm, direct, and
specific. Generic flattery ("I love your brand!") is not used. Every claim about audience fit,
aesthetic alignment, or past performance must be grounded in what the inputs provide; if a claim
cannot be grounded, the atom surfaces it as a `personalization_note` for the sender to fill rather
than inventing a supporting fact. No fabricated metrics, audience data, or past brand results under
any circumstance; see `protocols/no-fabrication.md`.

FTC disclosure requirements apply to any sponsored content. The atom flags this in
`personalization_notes` per `protocols/safety.md`; the sender must include a disclosure statement
in the final email or content piece.

## Inputs

```json
{
  "brand_name": "string -- exact brand name as it should appear in the pitch",
  "brand_product_category": "string -- the product category or product line being pitched (e.g., vintage-style cabinet hardware, linen throw blankets)",
  "proposed_format": "integration | dedicated | short-form -- the content format to propose",
  "brand_fit_notes": "string or null -- optional: why this brand fits Alex's niche; provide any specific product detail, shared aesthetic, or audience overlap the writer knows",
  "alex_pillar": "string or null -- optional: which of Alex's five content pillars this partnership fits (DIY and room makeovers | thrifting antiques and markets | home organization and systems | seasonal and holiday decor | backyard and outdoor living)"
}
```

- `brand_name` and `brand_product_category` are required. The atom cannot write a grounded pitch
  without them.
- `proposed_format` is required. Choose one: `integration` (brand mention woven into a longer
  video), `dedicated` (full video built around the product), `short-form` (Shorts or Reels feature).
- `brand_fit_notes` and `alex_pillar` are optional but improve specificity. When omitted, the atom
  draws fit language from `shared/brand-engine.md` and flags gaps in `personalization_notes`.

## Output

```json
{
  "tool": "pitch-paragraph",
  "brand_name": "echo of input",
  "proposed_format": "echo of input",
  "pitch_paragraph": "string -- 150 to 250 words; professional, warm, specific; ready to paste into an outreach email draft",
  "subject_line_options": [
    "Subject line variant 1 -- direct value proposition angle",
    "Subject line variant 2 -- aesthetic or niche angle",
    "Subject line variant 3 -- question or curiosity angle"
  ],
  "personalization_notes": [
    "List of items the sender must verify or customize before sending -- e.g., confirm current follower count, check brand's active campaign focus, add FTC disclosure statement to final email, verify product name spelling"
  ],
  "fabrication_check": "PASS if no metrics, outcomes, or claims were invented; FLAG:<reason> if any detail was omitted or nulled to avoid fabrication"
}
```

### pitch_paragraph guidance

The paragraph should:
1. Open with a one-sentence connection that names the brand and its product category alongside a
   specific element of Alex's aesthetic or audience (not a generic compliment).
2. Describe in one to two sentences how the partnership serves Alex's audience -- what problem the
   product solves or what mood it supports for the moody-vintage home decor viewer.
3. Propose the specific content format with a concrete framing (for example: "a dedicated video
   walking through a dark-and-moody bedroom refresh anchored by [Brand]'s hardware line").
4. Close with a clear, low-friction call to action (offer to send the media kit, suggest a brief
   call, or ask for the right contact).

Word count target: 150 to 250 words. Do not pad with pleasantries to hit the floor; do not compress
past the floor to keep it short.

### subject_line_options guidance

Three variants that bracket different angles the sender can test:
- Variant 1: states the value proposition directly (audience, format, niche).
- Variant 2: leads with aesthetic or niche identity to catch a brand manager scanning by fit.
- Variant 3: opens with a question or curiosity frame to invite a read.

No subject line should be longer than 60 characters. No clickbait. Each must accurately reflect the
pitch paragraph content.

### personalization_notes guidance

Always include at minimum:
- A reminder to add an FTC disclosure statement to the final email or content piece (required for
  any sponsored content per `protocols/safety.md`).
- A reminder to verify the brand contact's name and title before sending.
- Any field from `brand_fit_notes` or `alex_pillar` that was absent and would strengthen the pitch
  if supplied.

Add additional notes for any metric, claim, or product detail the sender should confirm before use.

## Do NOT use for

- Sending emails or posting content to any external platform or system. This atom writes text only.
- Writing a complete outreach email (opening, pitch paragraph, media kit summary, close, signature).
  Use a spoke that sequences this atom with other writing atoms.
- Producing final ready-to-send copy without human review. `personalization_notes` must be resolved
  by the sender before the email goes out.
- Generating pitch paragraphs for product categories unrelated to moody-vintage home decor, DIY,
  thrifting, seasonal decor, or outdoor living. Out-of-niche pitches misrepresent Alex's audience
  and brand.
- Inventing past campaign results, engagement metrics, subscriber counts, or brand endorsements.
  If real figures are not supplied, the atom omits them and flags the gap.

## References

- `shared/brand-engine.md` -- channel identity, aesthetic, content pillars, voice (professional
  outreach mode)
- `protocols/safety.md` -- FTC disclosure requirement: sponsored content must be disclosed; flag
  in personalization_notes on every output
- `protocols/no-fabrication.md` -- hard rule; no invented metrics, brand outcomes, or audience
  claims under any circumstance
