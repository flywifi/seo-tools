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

## Per-engine command/trust posture (research in progress)

> **STATUS: this section's external vendor-doc citations are pending** a research pass that was
> interrupted by a session-usage limit. The architecture and OWASP framing above are firsthand and
> stable; the per-engine specifics below are seeded from known behavior and MUST be completed with
> dated, cited vendor-doc URLs (and, once cited in a fenced `sources` block, seeded into
> `canonical-sources/source-registry.json` via `tools/source_sync.py reconcile` so invariant 52
> passes). Do not add the fenced `sources` block until the URLs are verified — no fabricated dates.

- **Anthropic / Claude** — wrap untrusted content in delimiters/XML tags; treat quoted content as
  data, not instructions; system-prompt and tool-result trust boundaries; agentic / computer-use
  injection defenses. [cite docs.anthropic.com prompt-injection + tool-use guidance, dated]
- **OpenAI / ChatGPT** — the Model Spec **instruction hierarchy** (platform/root > system/developer
  > user > guideline), with `untrusted_text` blocks that carry no authority; a Custom GPT or Action
  must treat Action-returned content as untrusted (below the user). [cite the Model Spec
  chain-of-command + `untrusted_text`, dated]
- **Google / Gemini** — `system_instruction` vs user-content separation; Google's published layered
  prompt-injection defense / classifier approach for Gemini apps. [cite Vertex AI / AI Studio
  prompt-injection guidance, dated]
- **Cross-cutting** — OWASP LLM01 Prompt Injection (defense in depth; a model judging injected
  content is itself injectable). [cite OWASP LLM Top 10 LLM01, dated]

## Where the code lives

- Offline tier + `render_prior`: `tools/injection_scan.py`.
- The prior + `pass2_pending` on drop-folder records: `tools/handoff/inbox.py::scan`.
- The reconciliation record + fail-safe: `tools/handoff/inbox.py::approve` (+ the scan-record
  schema under `shared/schemas/`).
- The session-side second pass contract: `skills/atoms/ingest-route/SKILL.md` and
  `skills/atoms/inbox-routing/SKILL.md`.
- The envelope + reconciliation model: `shared/injection-guard-engine.md` "Two-pass handoff".
