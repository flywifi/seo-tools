---
tool: deal-pipeline
spoke: deal-pipeline
lane: pipeline
fabrication_flags:
  - "Brand name, deal value, and contact details are placeholders. Never populate these fields from memory or inference. Fill them from actual communications."
retrieval_gaps: []
safety_flags:
  - "FTC disclosure required: any sponsored content featuring this brand must include clear disclosure at the start of the video and in the description."
quality_review:
  composite: 4.3
  integrity: 5
  accuracy: 4
  brand_alignment: 4
  audience_fit: 4
  governance: 5
  user_intent: 5
  accessibility: 4
  professional_quality: 4
  safety: 5
  release_approved: true
---

# Deal Pipeline: Home Decor Brand Partnership

## Deal record

**Brand name:** [brand_name: null -- fill from actual outreach]
**Contact name:** [contact_name: null -- fill from actual communications]
**Contact email:** [contact_email: null -- fill from actual communications]
**Deal type:** Sponsored integration (brand pays for inclusion in existing content)
**Product category:** Home decor accessories or paint/finish products
**Current stage:** in-discussion
**Stage entered:** [date: null -- fill when stage transition occurred]

---

## Stage history

| Stage | Entered | Evidence | Notes |
|---|---|---|---|
| outreach-sent | [null] | [email sent or DM sent] | First contact from creator side |
| in-discussion | [null] | [brand replied with interest] | Awaiting brief and rate discussion |

---

## Stage advance: in-discussion to contract-negotiating

To advance this deal to **contract-negotiating**, the following evidence must be on record:

- [ ] Brand has confirmed interest in a specific content format (integration, dedicated video, or Shorts series)
- [ ] Brand has provided a campaign brief or creative direction
- [ ] Preliminary rate discussion has occurred (brand stated budget range OR creator sent rate card)
- [ ] Exclusivity window (if any) has been raised and acknowledged by both parties
- [ ] Usage rights scope has been raised (organic only vs. paid amplification vs. whitelisting)

**Do not advance the stage until all five items are confirmed.** The deal-stage-advance atom
requires documented evidence for each gate before updating the pipeline record.

---

## Usage rights check

**Current status:** [usage_rights: null -- not yet discussed]

Usage rights must be explicitly agreed before contract stage. Standard options to discuss:

| Rights type | Typical duration | Typical rate premium |
|---|---|---|
| Organic only (creator's channels) | Perpetual (content stays up) | Base rate |
| Paid amplification (brand boosts the post) | 30 to 90 days | 20 to 40 percent above base rate [estimated] |
| Whitelisting (brand runs ads from creator's handle) | 30 to 60 days | 30 to 50 percent above base rate [estimated] |
| Full buyout (brand owns the content) | Perpetual | 2x to 3x base rate [estimated] |

Rate premiums above are [estimated] from industry benchmark ranges. Verify with actual
rate-card-fill output grounded in channel-context.json when channel stats are available.

---

## Exclusivity check

**Current status:** [exclusivity: null -- not yet discussed]

Exclusivity categories to clarify:

- **Category exclusivity:** Does the brand want the creator to avoid featuring any competitor brand
  in the same content category (e.g., no other paint brands) for a window?
- **Platform exclusivity:** Is the content restricted to one platform only (YouTube only vs. cross-post to TikTok and Pinterest)?
- **Duration:** Standard exclusivity windows in home decor partnerships run 30 to 60 days. Longer
  windows require rate compensation.

Flag for negotiation if exclusivity is requested without corresponding rate adjustment.

---

## FTC disclosure requirements

This deal will require FTC-compliant disclosure in all deliverables. Required placements:

- **In-video:** Verbal disclosure at the start of the integration ("This portion of the video is
  sponsored by [brand]"). Must appear before the sponsored segment, not at the end.
- **Video description:** Written disclosure in the first 3 lines of the description, visible without
  expanding. Standard language: "This video is sponsored by [brand]. I was gifted/compensated for
  including their product."
- **Shorts:** On-screen text disclosure within the first 3 seconds if the Short is fully sponsored.
- **Pinterest pins:** Disclosure in the pin description if the pin is part of a paid campaign.

The safety protocol flags any output that omits disclosure on sponsored content as a hard fail.

---

## Pitch paragraph (knowledge-only draft)

The following is a placeholder pitch for the in-discussion stage. Replace all bracketed
fields with actual information before sending.

---

"[Creator name] creates moody, vintage-inspired home decor content for an audience of
home owners and renters who want a collected, layered aesthetic without a designer budget.
Her channel launches January 2026 with a content library covering furniture makeovers,
thrift finds, and seasonal styling -- all filmed in an authentic [creator's home].

[Brand]'s [product line] aligns directly with her DIY makeover pillar. A natural integration
would feature [product] in a furniture flip or seasonal decor project, reaching an audience
that actively searches for specific product names and techniques -- not just inspiration.

[Creator name]'s rate card covers integrations, dedicated videos, and Shorts series.
She is available for [season/timeframe] content. Full media kit available on request."

---

**Note:** Subscriber count, average views, and engagement rates are null in this record.
They will be populated from channel-context.json once Alex provides her actual channel
statistics. Rate recommendations from rate-card-fill are currently based on industry
benchmark ranges and are labeled [estimated] until grounded in real channel data.
