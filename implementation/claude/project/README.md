# Creator OS — Claude Projects Setup (Web / Mobile)

No terminal. No downloads. Works on the claude.ai web app and mobile app.

## What you get

- Full hub routing across all three lanes (Content, Document, Pipeline/CRM)
- All 22 spokes: video development, SEO keywords, project builder, competitor analysis,
  shortform repurposing, seasonal trends, audience research, analytics insights, document studio,
  account manager, deal pipeline, deal resourcing, partnership mediakit, quality review
- Voice rules enforced on all output (no em dashes, no generic AI phrasing, object-first openings)
- Protocol enforcement: no fabrication, no unverified data, FTC disclosure flags, safety checks
- Seasonal SEO lead times and SERP feature mapping from knowledge

## What requires local tooling

The system tells you when something needs a local upgrade. You never get a crash or an error
from these features in Claude Projects mode -- the system delivers the best knowledge-only output
and notes what the upgrade path is.

| Feature | Available in Projects | With Claude Desktop + MCP |
|---|---|---|
| Full hub routing and all spokes | Yes | Yes |
| SEO keyword strategy (knowledge-based) | Yes | Yes |
| Competitor analysis (knowledge-based) | Yes | Yes |
| Video scripts, hooks, captions | Yes | Yes |
| Competitor hidden video tags (ytInitialPlayerResponse) | No | Yes |
| Offline FTS5 keyword cache queries | No | Yes |
| Source staleness detection | No | Yes |
| Deterministic quality scoring | No | Yes |
| Your real YouTube / Instagram analytics | No | Yes (with API credentials) |
| Voice personalized to your actual phrases | Partial (seed vocabulary) | Yes (voice-profile.json) |

---

## Setup (5 minutes)

### Step 1: Create the Project

1. Go to [claude.ai](https://claude.ai) and sign in.
2. Click **Projects** in the left sidebar.
3. Click **New Project**.
4. Name it: **Creator OS**.

### Step 2: Add Project Instructions

1. In your new project, click **Set project instructions** (or the gear icon).
2. Open `system-prompt.md` from this folder.
3. Copy the full text and paste it into the Project Instructions field.
4. Save.

### Step 3: Upload Knowledge Files

1. In the project, click **Add content** or the upload icon.
2. Upload each file from the `knowledge/` folder in this directory:
   - `01-creator-core.md`
   - `02-brand-voice.md`
   - `03-platform-seo.md`
   - `04-protocols.md`
   - `05-content-spokes.md`
   - `06-document-spoke.md`
   - `07-pipeline-spokes.md`
   - `08-key-atoms.md`
3. Wait for all files to finish processing (the spinner stops).

### Step 4: Test

Start a new conversation inside the project and try:

> Plan a seasonal home decor project makeover video.

You should see the hub classify your request as Content lane, route to
video-development, and produce a structured output with hooks, title options,
and a script outline.

---

## Example requests

**Content lane:**
- "What keywords should I use for a thrift store armoire flip on YouTube vs Pinterest?"
- "Write a hook for a moody fall bedroom reveal reel"
- "Plan my content for fall — I want to cover the mantel, bedroom, and front porch"
- "Write a full script for a chalk paint armoire tutorial, budget under $40"

**Document lane:**
- "Create a project snapshot for my wainscoting DIY — I want to do it myself"
- "Give me a materials list for board-and-batten in a renter apartment"

**Pipeline / CRM lane:**
- "I have a new potential deal with a home decor brand, help me set it up"
- "What do I need before I can advance a deal to the contract stage?"
- "Help me write a pitch paragraph for a brass hardware brand partnership"

---

## Updating the knowledge files

If the system is updated (new atom added, engine updated, spoke changed), re-upload
the relevant knowledge file. You do not need to re-upload all 8 files for a small change:
- New atom added: re-upload `08-key-atoms.md`
- Engine updated: re-upload the file that contains that engine (02 through 03)
- New spoke added: re-upload the relevant spoke file (05, 06, or 07)
