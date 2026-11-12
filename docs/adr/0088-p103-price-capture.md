# 0088. A gifted product's price is read from the page the person names, and recorded after their yes

- Date: 2026-11-12
- Status: Accepted

## Context

The income ledger stores a product's retail price only with its source, and a brand or retailer
price only with the page it was read from and the date (ADR 0082). Recording one meant writing
the entry's JSON by hand, so gifted products stayed unpriced. Reading a price off a web page is a
network request to an address a person typed, and the Scheduling Dashboard's selftest holds its
POST routes to making no network request outside the Confirm route.

## Decision

1. **A switch, off by default.** `price_capture` in `creator-os-config.json` gates the fetch.
2. **One page, read for its stated price.** `tools/price_capture.py::capture` takes the link the
   person names, checks its form (`check_link`: http or https, a host, port 80 or 443, no sign-in
   part), resolves the host and refuses it unless each address is public (`public_host`), and
   makes one GET with a 15 second limit, reading at most 2 MB. With no network proxy set, the
   connection goes to the address that was checked; with one set, the request goes the
   environment's way and the result says the address was not pinned. `read_price` takes the price
   from a schema.org Product's offers in a JSON-LD block, else from `product:price`, `og:price`
   or `itemprop` price meta tags. A figure in the page's wording is not read. One distinct price
   in USD is a price; no price, more than one, a range, another currency or no currency is a gap,
   and the person can state the price.
3. **The page stored is the page read.** A redirect to another address on the same host, by
   http or https and not from https down to http, is followed up to three times (`next_link`),
   and `source_ref` is the link the page came from, with the link given kept in
   `redirected_from`. A redirect to another host is reported and not followed.
4. **Screened before it is proposed.** The product's name and description and the page's titles
   go through the offline injection screen; a QUARANTINE or BLOCK verdict withholds the price
   and the title.
5. **Recording is a separate, gated write.** `tools/books.py::set_price` puts the price, its
   source, the page and the date on a product entry that is not void, through `validate_entry`'s
   provenance rule, behind `finance_management`. The entry keeps its id, status and other fields.
   Three callers outside the selftests: the Books tab's price form (`POST /api/books-price`,
   `tools/dashboard/server.py::_books_price`), the `price_confirm` MCP tool (a write only with
   `write` true) and `tools/books.py --set-price`.
6. **The dashboard fetches no page.** The price form takes a price, its source, the page link
   and the date, checks the link's form with `check_link`, and calls `set_price`. Reading a page
   is done by the `price_capture` MCP tool in a chat session, or by
   `python3 tools/price_capture.py <link>`. With no link, a chat session may search for the
   item's page and let the person choose one; the price recorded is the one `capture` reads from
   that page.

## Consequences

- A creator with a chat session gives it a link, sees the price, the page and the date, says
  yes, and the entry is priced. Without a session the creator runs the command, or enters the
  price and the link on the Books tab.
- The dashboard's POST routes still make no network request outside Confirm; the selftest that
  drives each route with each flag on covers the new route.
- A page that builds its price with scripts, blocks automated requests, or lists several
  variants at different prices gives a gap. In the build run, of five public product pages
  tried through a network proxy, one gave its price, one answered 403, one answered 429 after a
  same-host redirect, and two links were not product pages; a brand page the owner names was
  not run.
- With a network proxy set, the proxy resolves the host, so the address check made on this
  computer does not bind the request; when the host does not resolve on this computer, nothing
  is fetched.
- The title returned is page content. The tool's description tells a session to treat it as
  untrusted; it is cut at 200 characters.
