---
file: skills/atoms/search-intent/SKILL.md
name: search-intent
description: "classifies search intent (informational/commercial/transactional/navigational) and best-fit content format for a home decor or DIY keyword; feeds title-generate and hook-write but does NOT write those outputs itself."
load:
  - shared/platform-engine.md
  - shared/brand-engine.md
  - protocols/no-fabrication.md
---

# search-intent

Classify the underlying searcher intent and format fit for a home decor or DIY keyword so that downstream atoms can tailor their output to what the searcher actually wants. This atom resolves four intent types (informational, commercial, transactional, navigational) against five format types (tutorial/how-to, inspiration/listicle, product-review/haul, transformation/before-after, trend/explainer) and returns a structured classification that title-generate, hook-write, and other downstream atoms consume to stay on-model for the query.

## Purpose

This atom exists because the same keyword can serve radically different searcher goals, and writing a hook or title without knowing intent produces generic output that fails to satisfy the underlying query. It accepts a keyword and an optional platform signal, reasons over the word-level and contextual signals in the keyword itself, and returns a structured intent label plus the most fitting content format. It does NOT write any creative copy, generate titles, or make live search calls.

## Inputs

```json
{
  "keyword": {
    "type": "string",
    "required": true,
    "description": "The search keyword or phrase to classify, e.g. 'moody living room ideas' or 'how to style a thrift store lamp'."
  },
  "platform": {
    "type": "string",
    "required": false,
    "enum": ["youtube", "pinterest", "tiktok"],
    "description": "Target platform. Informs format-fit scoring because format conventions differ across platforms. Omit to return a platform-agnostic classification."
  }
}
```

## Output

```json
{
  "tool": "search-intent",
  "keyword": "the input keyword, echoed back",
  "intent": {
    "label": "informational | commercial | transactional | navigational",
    "definition": "informational = searcher wants to learn or get ideas; commercial = searcher is evaluating products or approaches before buying; transactional = searcher is ready to act, buy, or download; navigational = searcher wants a specific creator, brand, or page"
  },
  "content_format_fit": {
    "primary": "tutorial/how-to | inspiration/listicle | product-review/haul | transformation/before-after | trend/explainer",
    "secondary": "optional second-best format if the keyword is ambiguous",
    "rationale": "one to two sentences explaining which signals in the keyword drove the format choice"
  },
  "confidence": {
    "value": "high | medium | low",
    "note": "high = unambiguous keyword signals; medium = one competing interpretation exists; low = keyword is too short or generic to classify reliably"
  },
  "rationale": "two to four sentences explaining the intent classification, referencing the specific word-level signals (modifier words, question framing, brand mentions, action verbs) that drove the decision",
  "notes": "any caveats, alternate reads, or flags for the downstream atom to consider; null if none"
}
```

## Do NOT use for

- Writing video titles or thumbnail text (use title-generate).
- Writing hooks or opening lines (use hook-write).
- Building keyword clusters or expanding a seed keyword into a list (use keyword-cluster).
- Scoring SEO difficulty, search volume, or ranking probability.
- Publishing any output directly to a platform or CRM record.

## Pipeline note

This atom classifies from keyword signals alone. It reads `shared/platform-engine.md` for platform-specific format conventions and `shared/brand-engine.md` to confirm format fit against the creator's content model, but it does NOT make live search calls or pull live SERP data. If fresh SERP context has already been retrieved by `web-intel-engine.md` and is present in the current context window, this atom may reference it; it will not initiate a new fetch. All classifications obey `protocols/no-fabrication.md`: if confidence is low, the atom returns `"confidence": "low"` and flags the ambiguity in `notes` rather than forcing a label.

## Cross-modality
Inherits its calling spoke's class (Class B); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
