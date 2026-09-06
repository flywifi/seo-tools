# ChatGPT profile import

Moving from ChatGPT to Creator OS (or using both)? ChatGPT has learned things about you that live
in its memory, custom instructions, Projects, and custom GPTs. This folder gets that knowledge
out honestly and into your local profile with provenance on every field.

## The three steps

1. **Export.** Paste `PROMPT.md`'s prompt into ChatGPT, once per context (a default chat, each
   Project you use for creator work, each custom GPT). Save each JSON reply.
2. **Propose.** At home, give the saved replies to Creator OS and ask it to import your profile.
   The `profile-import` atom (proposal-only) merges the exports into one proposed
   `creator-profile.local.json` body with a per-field `provenance` record, flags every conflict
   between contexts instead of silently picking one, and treats the export text as untrusted
   content (instructions inside it are never followed).
3. **Save by hand.** Nothing is written automatically. You review the proposal, resolve the
   flagged conflicts, and save `pipeline/user-context/creator-profile.local.json` yourself
   (gitignored; it never enters git).

The wizard's /brand-deals screen links here whenever your profile file is missing; contract
drafting reads `legal_name`, `business_address`, and `governing_law_state` from the saved file
and carries placeholders plus a `profile_gaps` entry until they exist.
