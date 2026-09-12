# ADR 0058 — A widget is not a wall: block classification and block episodes

- Status: accepted
- Date: 2026-09-12
- Phase: P82-9 (follow-through on the ChatGPT/OpenAI audit remediation)

## Context

The escalation clock added in P82 began alerting on thirteen sources recorded as blocked since
2026-08-30. Investigating before clearing them surfaced two defects rather than a backlog.

First, the anti-bot classifier accepted two kinds of non-evidence as walls: a captcha ASSET
anywhere in a response body (genuine pages embed reCAPTCHA for their own forms; one healthy
623 KB blog page carried the marker five times), and a CDN vendor FINGERPRINT in the headers of
a healthy success response (every site fronted by that CDN carries one; one vendor's marker
table has no body entries at all, so its success-response verdicts were fingerprint-only by
construction). Nine of the thirteen "blocked" sources were serving real content with real titles
and no challenge phrases at the moment they were re-verified. The same defect had defeated the
resilient retry: its browser prong fetched the real page and the classifier re-condemned the
fetched body on the same markers, which is how the false verdicts were originally recorded.

Second, re-detecting a block re-stamped its detection date, and the escalation clock measured
days since that date -- so the clock would have been reset to zero by the very sweeps meant to
maintain currency, and the overdue alert could never fire on a maintained registry.

## Decisions

1. On a success (2xx) response, block classification requires challenge-page evidence: a
   challenge-specific body marker, or a captcha marker on a body small enough to be an
   interstitial. The size threshold is a measurement recorded beside its constant: the nine
   false-positive pages ran 85 KB to 1.1 MB while challenge interstitials run under about 16 KB,
   so 30 KB separates the populations with wide margin. Vendor fingerprints and captcha assets
   alone no longer count on a success response. Non-2xx classification is unchanged. Both
   directions are pinned by fixtures, and the conservative residual is deliberate: below the
   interstitial ceiling the classifier still errs toward "blocked", because trusting an
   interstitial as content corrupts change detection, which is the worse error.
2. A block is an EPISODE. first_block_detected is stamped when a source enters the blocked
   state, survives re-detection, and clears on recovery or on mark-checked -- the human
   verification verb, which now heals the entire block record. Both escalation clocks measure
   from the episode start; legacy rows fall back to the latest detection date, which for a
   never-reswept block is the episode start exactly, so no data migration was needed.
3. The backlog was re-swept through the fixed tools with per-source expected outcomes measured
   in advance and an authenticity spot-check on the most load-bearing recoveries before commit.
   Sources still blocked after the fix are genuinely refused for this automated context and
   were handed to the owner on a browser checklist whose items end in exact closing commands.
4. The retired TikTok creator-portal source was re-homed to its probed successor page, verified
   through the same fetch-and-classify chain the sweep uses; the recommendation-algorithm fact
   continues to rest on the separate newsroom source.
5. Deliberately NOT done: impersonating a browser in the routine fetcher. The false positives
   were cured by demanding better evidence, not by disguising the client; defeating genuine
   walls remains the opt-in resilient chain and the human handoff.

## Verification

The patched classifier passed its full pre-existing selftest and five new two-direction
fixtures, then re-classified all twelve backlog sources live: the nine false positives came
back as hashable content and the three genuine refusals kept their honest verdicts. The patched
currency module passed all thirty-seven pre-existing selftest checks plus five new ones, and the
episode logic was driven through the real detect-changes path with an injected getter: the
episode survived a simulated forty-day re-sweep, the clock read forty days, and recovery and
mark-checked both cleared the record. The successor URL was verified through the production
fetch-and-classify chain before the registry was touched.
