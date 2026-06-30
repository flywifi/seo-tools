---
file: protocols/no-fabrication.md
role: The hard rule against inventing data. Critical for the CRM lane, analytics, research, and
  pricing. Enforced everywhere and checked by the Integrity dimension of the quality gates.
load: always, and especially on any CRM record write, analytics interpretation, research claim, or price
---

# No-Fabrication Protocol

Never invent, guess, randomize, or use placeholder or "dummy" data in any output. Outputs are real,
true, and accurate to the best available knowledge. Schemas, templates, and blank structures are not
data and are allowed.

## CRM (critical)
The pipeline/ store is a record of real relationships and money. Never create sample brands, deals,
contacts, compensation figures, payment terms, dates, or deliverables. If a value is unknown, leave
it null and flag it as missing. Never backfill a field to make a record look complete. Every value
written to an account or deal record must come from the user or a real, named source.

## Analytics
Never invent audience numbers, view counts, engagement rates, or growth figures. Interpret only the
real analytics the user provides. The niche-typical defaults in shared/audience-engine.md are
planning assumptions, not the creator's measured data, and must never be presented as her actual numbers.

## Research
Cite real, locatable sources for factual claims (see protocols/research-citation.md). Never invent a
statistic, a study, a quote, or a source. If the answer cannot be found, say so.

## Pricing
Give honest ranges and say when a price depends on local sourcing, season, or supplier. Never state a
specific price as fact unless it is real and current.

## Permission gate
If a task appears to require fake, sample, or placeholder data (for example, a demo media kit with
invented brands, or a sample pipeline), stop and ask for permission first, and label any such data
clearly as illustrative if the user approves it. Default is to use only real data.
