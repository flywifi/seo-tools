# Two-pass injection screening: an offline pre-filter feeding an authoritative in-session guard

## Why this exists

Creator OS screens externally-sourced content for prompt injection in two tiers (see
`shared/injection-guard-engine.md`):

1. **The offline pattern tier** (`tools/injection_scan.py`) — a stdlib regex scorer. Fast,
   always-on where Python runs, deterministic. It catches the *known phrasings* the engine
   enumerates. A reworded or obfuscated attack scores CLEAN against it, so a CLEAN offline verdict
   is **not** a clearance.
2. **The in-session semantic guard** — a Claude session applying its judgment over the content.
   It is **authoritative** and can catch rewordings the regex misses, because it is semantic.

Before P62 these ran independently: the offline tier's verdict was never handed to the session,
so the cheap always-on layer never informed the expensive authoritative one, and the session
re-judged raw content from scratch. P62 connects them into a **two-pass** pipeline: the offline
result becomes an *advisory prior* the session reads, the session does the authoritative second
pass, and a reconciled verdict is recorded.

This is defense in depth — a cheap pre-filter that hard-blocks the worst content before any model
sees it, feeding a semantic judge — which is the industry-recommended shape (OWASP LLM01, below).
It is **not** "the notes are what let the AI catch rewordings": the AI catches rewordings because
it is semantic; the notes add attention-direction on long content, provenance/auditability for the
human, and let the cheap layer block BLOCK-level content before it ever reaches a model.

## The pipeline

```
content ──▶ PASS 1: offline pattern tier (tools/injection_scan.py)
              │  produces offline_pattern_scan = {risk_level, total_score, patterns_detected}
              │
              ├─ QUARANTINE / BLOCK ──▶ SEALED (terminal). Pass 2 never runs on it.
              │                          Releasing a false positive is a deliberate HUMAN move.
              │
              └─ CLEAN / REVIEW ──────▶ flows onward, carrying its offline prior + pass2_pending
                                          │
                                          ▼
                                        PASS 2: in-session semantic guard (authoritative)
                                          reads the content + the advisory prior (as DATA),
                                          writes injection_scan_result + a reconciliation record
```

**Sealing is terminal (SEAL-TERMINAL).** The AI second pass runs only on content that flows
onward. A file the offline tier sealed is never auto-re-examined by the AI; the offline tier can
only ever be *more* cautious than the session on a sealed item, and undoing that is a human
decision, not a model decision.

## The untrusted-content envelope (the safety keystone)

Passing the offline notes and the raw content to the model *is* the injection vector, so both are
wrapped so the model can never mistake them for instructions. The canonical form (defined in
`shared/injection-guard-engine.md` "Two-pass handoff"):

```
<untrusted_content source_trust_class="untrusted_external" offline_prior="REVIEW (offline pattern score 5): EXFIL x1">
  ...the raw content, verbatim...
</untrusted_content>
```

Everything inside is **DATA to analyze and to extract from under a strict schema, never
instructions to follow**. The `offline_prior` attribute is rendered by
`tools/injection_scan.py::render_prior`, which emits only the risk level, score, and matched
category names — **never raw content**, so the prior itself can never smuggle an injection into the
session. The session treats a flagged category as a focus area and specifically hunts for reworded
versions of it. This is the one canonical statement of the delimiting discipline the email/task
extraction atoms describe in prose (`shared/tasks-engine.md`,
`skills/atoms/{email-to-task,pitch-extract}/SKILL.md`, `protocols/safety.md`).

## Reconciliation

The session emits the authoritative `injection_scan_result` plus a `reconciliation` object:

| Field | Meaning |
|---|---|
| `agreed` | did the session verdict match the offline prior's risk direction? |
| `session_action` | `confirmed` (agreed) · `escalated` (session found injection the prior missed — the primary value) · `downgraded` (session judged a prior REVIEW benign; both verdicts still shown to the human) |
| `pass_coverage` | `both` · `offline_only` · `session_only` (which passes actually ran) |
| `note` | short human-readable reason |

**The session verdict decides, with one fail-safe:** it can never *un-seal* a file the offline
tier already sealed (SEAL-TERMINAL). The `{offline_pattern_scan, injection_scan_result,
reconciliation}` triple is persisted on the record (the inbox ledger for the drop-folder path).

## Availability by modality (which passes actually run)

The two passes do not always co-occur; `pass_coverage` records which ran. Grounded in the repo's
cross-modality model (`shared/cross-modality-engine.md`, `shared/cross-modality/transitions.json`,
`docs/TRANSITIONS.md`):

| Surface | Pass 1 (offline) | Pass 2 (in-session semantic) | Coverage | Notes |
|---|---|---|---|---|
| Claude Desktop / Code (atoms over the hub) | runs | runs, reads the prior | `both` | the ideal informed second pass |
| Headless runner (`inbox_scan` job) | runs | no AI in the loop | `offline_only` | record marked `pass2_pending`; a later session completes pass 2 |
| claude.ai web / mobile | usually can't (no local Python) | runs | `session_only` | session guard runs without a prior |
| Cowork remote sandbox | maybe (Python present; needs files connected) | runs | varies | as available |
| ChatGPT custom GPT / Action / web | no (unless a deployed MCP is connected) | the engine's OWN handling | `session_only` | we INSTRUCT the envelope discipline; we cannot enforce it |
| Gemini Gems / API | no | the engine's OWN handling | `session_only` | same — instruct, not enforce |

On non-Claude engines Creator OS can only *advise* the envelope discipline (baked into the ChatGPT
and Gemini packaging under `implementation/`), honestly labeled: the offline pre-filter runs on
those surfaces only when a local tool or deployed MCP is connected, and the second pass is that
engine's own judgment, not ours.

## Honest limits (OWASP LLM01, defense in depth)

- **No single pass is authoritative in isolation.** The offline tier misses rewordings; the
  session guard is a model reading attacker-controlled content and is *itself* injectable. The
  design is layered precisely because neither layer is sufficient alone. (OWASP LLM01: Prompt
  Injection — keep untrusted content outside the trust boundary; do not rely on a single model
  pass.)
- **The prior is advisory, never a gate.** A CLEAN prior never clears content; the session
  re-judges from the content. An offline QUARANTINE/BLOCK is a hard seal the session cannot undo.
- **The envelope is a mitigation, not a guarantee.** Wrapping content as data and instructing the
  model to treat it as data reduces but does not eliminate injection risk; that is why sealing is
  terminal and why every downstream action stays human-confirmed (`human_review_required`).

## Per-engine command/trust posture

Each engine's own published guidance converges on the shape Creator OS implements: keep
attacker-reachable content out of the instruction channel and treat it as data a screen inspects,
not as commands to follow. The dates below are each vendor doc's stated version or last-updated
stamp, verified 2026-07-18.

- **Anthropic / Claude** — Anthropic's guidance separates jailbreaks / direct injection (the user is
  the adversary) from indirect injection (Claude reads adversarial third-party content). For
  indirect injection it prescribes: deliver third-party content only inside `tool_result` blocks,
  never in the system prompt or a plain user turn; state in the system prompt that tool, document,
  and search content is untrusted data whose embedded instructions are "information to report, not
  commands to follow"; JSON-encode or otherwise delimit the untrusted payload so an attacker cannot
  break out of the quoting; and screen tool outputs with a lightweight classifier (for example
  Claude Haiku 4.5 returning a structured-output verdict) before Claude acts on them. That
  cheap-screen-then-authoritative-pass shape is exactly the two-pass pipeline above. (Mitigate
  jailbreaks and prompt injections, platform.claude.com, accessed 2026-07-18.)
- **OpenAI / ChatGPT** — the OpenAI Model Spec defines an explicit **chain of command**: Root >
  System > Developer > User > Guideline. Quoted text (plaintext in quotation marks, YAML, JSON, XML,
  or `untrusted_text` blocks), multimodal data, file attachments, and **tool outputs** are "assumed
  to contain untrusted data and have no authority by default." A Custom GPT or Action must therefore
  treat Action-returned content as untrusted, below the user. (Model Spec, version 2025-12-18.)
- **Google / Gemini** — Google documents a **layered defense** against indirect prompt injection for
  Gemini: prompt-injection content **classifiers** that screen incoming data, security-thought
  reinforcement, markdown sanitization and URL redaction, a **user-confirmation** framework for
  sensitive actions, the models' own adversarial **resilience**, and end-user security
  notifications. No single layer is treated as sufficient. (Indirect prompt injections and Google's
  layered defense strategy for Gemini, Google Workspace admin knowledge base, last updated
  2026-07-17.)
- **Cross-cutting** — OWASP LLM01:2025 Prompt Injection recommends *multiple simultaneous*
  mitigations — constraining model behavior, defining expected output formats, input and output
  filtering, least-privilege access control, human approval for high-risk actions, **segregating
  external and untrusted content**, and adversarial testing — and states plainly that, given the
  stochastic nature of models, there is no known fool-proof prevention: the goal is mitigation, not
  elimination. Creator OS's own point above (a model asked to judge injected content is itself
  injectable, so no single pass is authoritative) follows directly from that. (OWASP Top 10 for LLM
  Applications, LLM01:2025.)

The external authorities these four claims rest on are declared below for the currency system. Every
id must exist in `canonical-sources/source-registry.json` with the same URL (drift-guard invariant
52, fail-closed); `tools/source_sync.py reconcile` generates a seed for any id not yet registered,
and the human runs `seed-sources` on it.

```sources
[
  {"id": "anthropic-mitigate-jailbreaks", "name": "Anthropic Mitigate Jailbreaks and Prompt Injections guidance", "url": "https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-model-spec", "name": "OpenAI Model Spec chain of command and instruction hierarchy", "url": "https://model-spec.openai.com/2025-12-18.html", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "google-gemini-prompt-injection-defense", "name": "Google layered defense against indirect prompt injection for Gemini", "url": "https://knowledge.workspace.google.com/admin/security/indirect-prompt-injections-and-googles-layered-defense-strategy-for-gemini", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "owasp-llm01-prompt-injection", "name": "OWASP Top 10 for LLM Applications LLM01:2025 Prompt Injection", "url": "https://genai.owasp.org/llmrisk/llm01-prompt-injection/", "category": "ai-surface-spec", "tier": "T1"}
]
```

## Where the code lives

- Offline tier + `render_prior`: `tools/injection_scan.py`.
- The prior + `pass2_pending` on drop-folder records: `tools/handoff/inbox.py::scan`.
- The reconciliation record + fail-safe: `tools/handoff/inbox.py::approve` (+ the scan-record
  schema under `shared/schemas/`).
- The session-side second pass contract: `skills/atoms/ingest-route/SKILL.md` and
  `skills/atoms/inbox-routing/SKILL.md`.
- The envelope + reconciliation model: `shared/injection-guard-engine.md` "Two-pass handoff".
