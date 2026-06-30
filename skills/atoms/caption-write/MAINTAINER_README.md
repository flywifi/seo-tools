---
file: skills/atoms/caption-write/MAINTAINER_README.md
purpose: keep caption-write in published-to-audience voice, within platform character limits, and with FTC disclosure flags when content is sponsored, gifted, or affiliate.
---

# caption-write: Maintainer README

## Purpose
Write one platform-appropriate caption in the published-to-audience voice. FTC disclosure is flagged in the output, never omitted.

## Non-negotiable invariants
- Voice is always published-to-audience, never planning-to-Alex.
- If sponsored/gifted/affiliate is true, the output must include ftc_disclosure_line.
- Character counts stay within platform limits: Instagram 2200, TikTok 2200, Pinterest 500, Shorts 100 visible.

## Known failure modes
- Writing in the planning voice ("you should post this...") instead of the audience voice.
- Omitting the FTC disclosure line when sponsored=true.
- Exceeding the Pinterest 500-char limit.

## Regression cases to preserve
1. Sponsored post: ftc_disclosure_line is present, never null.
2. Pinterest caption: stays under 500 chars; keyword appears in the first sentence.

## Update checklist
- Run python3 tools/sync_check.py.
