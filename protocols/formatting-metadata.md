---
file: protocols/formatting-metadata.md
role: Output formatting, file-type selection, document metadata, and voice. Applied by every skill,
  especially document-studio. Feeds the Professional Quality and Accessibility gates.
load: on every output, and before producing any downloadable file
---

# Formatting and Metadata Protocol

## Punctuation (hard rules)
- Never use em dashes in any user-facing output (scripts, captions, pitch paragraphs, pin titles,
  media kit copy, any content Alex or her audience will read). Use commas, parentheses, periods, or
  rephrasing instead. Internal documentation (SKILL.md files, engine docs, protocol files,
  architecture docs) may use em dashes as standard prose punctuation.
- Never use en dashes for ranges anywhere. Write ranges with "to" (for example, "1 to 3 hours,"
  "$50 to $150," "15 to 60 seconds").
- See shared/voice-engine.md for the full anti-AI pattern list and voice guidance.

## File type
Before producing a deliverable, confirm the output file type with the user (for example, plain text,
Word, Excel, PDF, PowerPoint, image, or graphic) unless they have already specified it. Offer the
options as a checklist with an "other" box. If a format has a technical or practical limitation,
explain it and let the user choose. Use the platform's existing docx, pdf, xlsx, and pptx skills for
file mechanics.

## Document metadata
Set the document author or creator and the last-modified-by fields to the document_author value in
shared/brand-engine.md (default Alexandra Slason). Never leave an application default such as
"Python," "Claude," "Un-named," "anonymous," or a tool's name.

## Voice and accessibility
Use the correct voice mode from shared/brand-engine.md: the planning voice when talking to Alex, the
published voice when writing audience-facing copy. Keep language plain and explain any jargon or
acronym briefly on first use, since the audience skews beginner to intermediate.

## Platform formatting
Match each surface to its spec in shared/platform-engine.md (aspect ratio, length, caption limits,
safe zones), and honor the content ecosystem ratio from shared/brand-engine.md.
