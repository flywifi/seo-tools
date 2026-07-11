# The ChatGPT profile-import prompt

Paste the prompt below into ChatGPT to export what it knows about you in a form Creator OS can
ingest. Run it ONCE PER CONTEXT, because ChatGPT's knowledge is scattered: once in a default
chat (it sees your memory and custom instructions), once inside EACH Project you use for creator
work (it sees that Project's files and chats), and once inside each custom GPT you built. Save
each JSON reply to a file named after the context (for example `profile-export-default-chat.json`)
and bring them home; the profile-import atom merges them into ONE proposed profile with per-field
provenance, and you save the final file yourself.

Privacy note: this prompt asks ChatGPT to REPORT what it already knows; it sends nothing new
anywhere. Review each reply before bringing it home.

---

Copy everything between the lines into ChatGPT:

```
You are exporting my creator profile for an external system. Follow these rules exactly.

RULES
1. Report ONLY what you actually know about me from this context (this chat's memory, my custom
   instructions, and, if we are inside a Project or custom GPT, its files and instructions).
   Never guess, infer beyond evidence, or fill a field to be helpful. Omit unknown fields
   entirely.
2. For every field you report, state WHERE it came from and quote the evidence.
3. Output a single JSON code block and nothing else, in exactly this shape:

{
  "context": "default_chat | project:<project name> | custom_gpt:<gpt name>",
  "exported_on": "<today's date, YYYY-MM-DD>",
  "fields": {
    "<field_key>": {
      "value": "<the value>",
      "source": "memory | custom_instructions | stated_in_this_chat | project_files | gpt_instructions",
      "confidence": "explicit | high | medium | low",
      "verbatim_quote": "<the exact sentence or note this came from>"
    }
  }
}

4. Field keys to look for (omit any you do not actually know):
   creator_name, creator_display_name, channel_name, channel_url, location_city, location_state,
   location_country, timezone, contact_email, content_niche, content_pillars, audience_summary,
   posting_cadence, brand_voice_notes, past_brand_partners, typical_deliverables,
   negotiation_preferences, legal_name, business_address, governing_law_state.
5. confidence means: explicit = I told you this in so many words; high = directly supported by a
   quote; medium = summarized from several notes; low = a weak signal you are unsure about.
6. Do not include anything about other people, private third parties, or payment credentials.
```
