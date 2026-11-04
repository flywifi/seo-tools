# 0084. Inbound mail is sorted on this computer, senders are matched by address, and Gmail opens read-only

- Date: 2026-11-04
- Status: Accepted

## Context

The person asked for the assistant to use its own Gmail connector (Claude, ChatGPT or Gemini) to
scan the connected inbox and say which inbound messages come from brands they work with. ADR 0083
left reading mail from a connected Gmail account to a separate change.

Three facts shape it. Each vendor's Gmail connector can send mail as well as read it (Claude's
connector drafts and sends with approval; ChatGPT's Gmail app holds the `gmail.modify` scope), and
Claude's reads attachment metadata, not content. The CRM lookup `tools/accounts.py::resolve`
matches brand names, so a sender shown as "Brand Name <billing@phish.example>" resolved to that
brand's account, while the brand contact's own address matched nothing. And Claude Desktop's local
Google tool server (`workspace-mcp`) was started with every tool on, `send_gmail_message` included.

## Decision

1. `tools/accounts.py::resolve_sender` matches an email sender to an account by **address**: a
   contact email on exactly one account resolves; a domain equal to, or a subdomain (on a dot
   boundary) of, the account's website host is a candidate the person confirms, when the website
   is a homepage address (a host and an optional numeric port followed by nothing or a single
   "/": no path, query, fragment or user part) whose host is not on or under a domain in
   `FREE_MAIL_DOMAINS`. A contact's own mailbox domain is not a basis: it may be a free or ISP
   mailbox domain that the fixed list does not hold, and then every stranger there would be a
   candidate. A sender on a `FREE_MAIL_DOMAINS` domain is not matched by domain. A mail domain is
   read whole (`_domain_name`): lowercased one character at a time, one trailing dot dropped, every
   label made of ASCII letters and digits, "-", and non-ASCII characters of the Unicode categories
   L, Nd, Mn and Mc (letters, decimal digits and combining marks), and each non-ASCII label written
   as the punycode A-label of its
   NFC form with nothing mapped (the stdlib IDNA2003 codec maps ß to "ss"). A "/", "?", "#", ":"
   or space in it, or a non-ASCII letter that lowercases to an ASCII one (the Kelvin sign), makes
   the address unreadable (`no_address`) rather than cut short. The header is split into name and
   address before any decoding; only the name is decoded. An address written as an encoded word
   is flagged (`encoded_address`) and not matched; a name in a charset that cannot be decoded is
   dropped (`name_undecodable`); a header of the form `Last, First <address>` is read for its one
   address (`display_name_unquoted`). A display name read from the header that names an account
   the address does not belong to, or names one when no address could be read, is flagged
   (`display_name_names_another_account`). The display name is not used to match.
2. `tools/mail_triage.py` sorts the messages a session read through its connector (at most 50 per
   call, 65,536 characters of body each): the offline pattern tier screens the sender's name and
   From header, the subject, the body, the Message-ID, the date and the link (pass 1), and a
   QUARANTINE or BLOCK verdict puts the message in `held` with its display name, subject,
   Message-ID, date and link not echoed and no pass 2; the others get one pile, `payment_notice`, `known_brand`, `new_pitch` or
   `other`, from fixed word lists and the sender match, with a next step. A payment notice whose
   display name names another account, or whose sender address or display name could not be
   read, is told to record nothing until the person knows who sent it. It has no write path and no mail access; its selftest reads the
   module's text for imports and calls by name. The `mail_triage` MCP tool wraps it and masks the
   CRM side of each match unless the server was started on stdio, the way Claude Desktop starts
   it (`mcp_server._STDIO_BOUND`, False until the statement before the stdio `mcp.run()`): the
   account part is built field by field, names to initials, emails to a stub, and each account id
   as a per-call token, since an account id can carry a brand's name. The `mail-triage` atom is
   standalone, like `inbox-routing`; it hands a pitch to `pitch_triage`.
3. A payment notice is recorded through the Inbox, as ADR 0083 records any receipt: the person
   saves the message as an `.eml` file (Gmail: More, then Download message) into the hub Inbox and
   ticks it. The books' evidence stays a file this computer hashed.
4. The wizard starts `workspace-mcp` (2.3.0 or later) with `--permissions gmail:readonly` and every
   other service at `full`, so the Google sign-in grants Gmail's read scope alone and the server
   registers no Gmail tool that sends, drafts or changes labels. Calendar, Drive and Chat keep full access, and
   their tools can send invitations, share notices and chat messages. The Google screen's Gmail
   sending tick box sets the `gmail_write_tools` flag and switches the entries the wizard wrote
   (command `uvx` with exactly the arguments the wizard writes, or `workspace-mcp` alone as earlier
   versions wrote it) to
   `gmail:send`, or back; the screen shows the level it reads from those entries, so an entry an
   older wizard wrote (no `--permissions`, every Gmail tool on) shows as on until the person saves.
   `configure_tool` refuses that flag (`_PERSON_ONLY_FLAGS`), so an instruction in content the
   assistant reads cannot turn sending on through Creator OS's MCP tools; a session with a shell or
   file tool of its own is outside that refusal.
5. Triage results are returned to the session and not stored between runs.

## Consequences

- On Claude Desktop the person sees which inbound mail is from a brand on record, which is a new
  pitch and which is a payment notice, without Creator OS writing anything.
- A brand contact who writes from a free webmail address matches only once that address is on the
  account; an agency writing for a brand from its own domain is not matched. A colleague at the
  brand is a candidate only when the account's website is recorded as a homepage address.
- The pile words are fixed lists: a payment notice or a pitch worded another way lands in `other`.
- Text past 65,536 characters of a body is not screened or searched (`body_cut`).
- The claude.ai Gmail connector is not limited by the wizard; it asks the person before each send,
  and the atom tells the session not to send, label, archive or delete mail.
- A person who turns Gmail sending on may be asked to sign in to Google again, since the access
  requested changes.
- ChatGPT, Gemini and claude.ai on the web, which cannot call the local tool, are a separate change.

## Sources

```sources
[
  {"id": "claude-google-workspace-connectors", "name": "Claude Support - Use Google Workspace connectors", "url": "https://support.claude.com/en/articles/10166901-use-google-workspace-connectors", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-google-app-data-controls", "name": "OpenAI Help - Google app data controls FAQ (Gmail scope)", "url": "https://help.openai.com/en/articles/10408842-google-app-data-controls-faq", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gmail-download-message", "name": "Gmail Help - Download and send emails as attachments (Download message)", "url": "https://support.google.com/mail/answer/9261412", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "mcp-workspace", "name": "Google Workspace MCP (workspace-mcp)", "url": "https://github.com/taylorwilsdon/google_workspace_mcp/releases", "category": "mcp-server", "tier": "T1"}
]
```
