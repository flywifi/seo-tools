# 0086. The dashboard's Books tab reads the ledger and passes the person's Confirm or Void to it

- Date: 2026-11-12
- Status: Accepted

## Context

The income ledger (ADR 0082) proposes entries from paid invoices and approved receipts, and a
person confirms each one. Confirming or voiding an entry was a typed command
(`tools/books.py --confirm <id>`, `--void <id>`), and the payer summary, the gift register and the
form check had no screen: the wizard records a receipt on its work order (ADR 0083) and shows no
ledger. The Scheduling Dashboard already shows money owed on a read-only tab (ADR 0015), on a
server that binds 127.0.0.1, sends no CORS header, takes JSON POSTs only and refuses a POST that
carries another site's Origin.

## Decision

1. **A Books tab on the dashboard.** `GET /api/books?year=YYYY`
   (`tools/dashboard/server.py::_books_payload`) returns, for one tax year, the payer summary, the
   gift register and the form check as `tools/books.py` computes them, the ledger's entries of
   that year still proposed, and the entries of the cost-actuals file dated in that year, which
   the dashboard reads itself at the path `books.py` names, with the ledger's boundary line and
   whether recording is on. The year is four digits from 2000 to next year, else this year
   (`_books_year`), and the tab's heading shows the year answered. The selftest compares the
   files under its root before and after a read (names, bytes, inodes, modification times) and
   finds them the same.
2. **Confirm and Void are the dashboard's first finance write.** `POST /api/books-status`
   (`_books_status`) takes an entry id in the ledger's id form and the status `confirmed` or
   `void`, and calls `books.set_status`, which writes behind the `finance_management` switch under
   the ledger's lock. With the switch off the reply is 409 with the reason and the tab offers no
   buttons; an id the ledger does not hold is 404; a ledger that does not parse, or an error
   the ledger raises, is 500 and the ledger's bytes are left as they are. The dashboard checks
   two things before the call, the id's form (`BK-`, eight ASCII digits, a hyphen and eight
   lower-case hex digits; an id written by hand in another form is listed and its click answers
   400) and the status; what makes an entry valid, how
   totals are computed and how the file is written stay in `tools/books.py`. A click that
   changes an entry also sets the ledger's `last_updated` and re-serialises the file, and a
   click made with the switch on takes the ledger's lock, which leaves an empty
   `income-ledger.local.json.lock` beside it.
3. **Another site's request is refused; a program on this computer is not.** The route sits
   in `POST_ROUTES`, behind the Origin check and the JSON-only body reader `do_POST` already
   applies: a request that carries another site's Origin is refused with 403 before the route
   runs (`_origin_ok`, whose cases cover another host, another port, another scheme and the value
   `null`). A request with no Origin header, as a local script sends, is accepted, as it is on
   the scheduling routes. `books.set_status` has two callers outside the selftests, this route
   and the `books.py` command line; the books MCP tools do not call it.
4. **The selftest's ledger is a temporary one.** `tools/books.py` reads its root at each call, so
   the dashboard selftest sets `CREATOR_OS_ROOT` to a temporary folder for its run: the GET and
   POST pins, which drive every route, read and write a ledger there.

## Consequences

- A person confirms or voids an entry in the browser on their own computer; the totals on the tab
  follow at once.
- The tab does not add or edit entries, record receipts, or set a product's price. Receipts stay
  on the wizard's work order; a price is a separate change.
- A Void can be confirmed again from the command line; the tab lists entries awaiting
  confirmation and has no list of void ones.
- `do_GET` gains one route, so the selftest's pinned source for it and its route count change in
  the same commit.
