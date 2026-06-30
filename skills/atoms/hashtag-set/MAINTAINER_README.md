---
file: skills/atoms/hashtag-set/MAINTAINER_README.md
purpose: keep hashtag-set tiered (broad/niche/micro), honest about count instability, and within platform norms.
---

# hashtag-set: Maintainer README

## Purpose
Return a three-tier hashtag set ready to paste. Never assert follower counts or reach figures as facts.

## Non-negotiable invariants
- Output includes a note directing Alex to verify counts in-app before use.
- Tier structure: 3 to 5 broad, 5 to 8 niche, 3 to 5 micro.
- Tags are relevant to moody/vintage home decor and DIY; never generic lifestyle tags unrelated to the niche.

## Known failure modes
- Stating a hashtag has "500K followers" as fact when it changes daily.
- Using generic tags (#home, #decor) as the entire broad tier with no niche specificity.
- Fewer than 3 micro/hyper-niche tags.

## Regression cases to preserve
1. TikTok platform: output skews toward shorter, discovery-oriented tags; Pinterest: skews keyword-descriptive.
2. Holiday pillar: seasonal tags (e.g., #falldecor) present in niche tier.

## Update checklist
- Run python3 tools/sync_check.py.
