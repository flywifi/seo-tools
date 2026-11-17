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
   part), resolves the host and refuses it unless each address it resolves to is a public one
   (`public_host`; an IPv6 address that carries an IPv4 address is judged by the one it carries),
   and fetches the page with a GET. A link gets 15 seconds for the addresses it tries and the
   redirects it follows, and the read stops past 2 MB: a timer shuts a GET's connection when its
   time is up, during the TLS handshake, the headers or the body. The timer does not reach a
   connection that has no socket yet, so the TCP connect, and with a proxy the proxy's answer to
   the tunnel request, each wait up to the time that was left when the GET began. With no network
   proxy set, the connection goes to a checked address: the first in the resolver's order, then
   the next when a connection could not be made, three at most. With a proxy set, the request
   goes the environment's way and the result says the address was not pinned. `read_price` takes
   the price from the offers of a schema.org Product in a JSON-LD block (a Product listed inside
   another Product is read when it is one of its `hasVariant` entries, not otherwise), else from
   `product:price`, `og:price` or `itemprop` price meta tags. A figure in the page's wording is not read. One distinct price in USD is a
   price; no price, more than one, a range (also one with a single end given), another currency
   or no currency is a gap, and the person can state the price.
3. **The page stored is the page read.** A redirect to another address on the same host, by
   http or https and not from https down to http, is followed up to three times (`next_link`),
   and `source_ref` is the link the page came from, with the link given kept in
   `redirected_from`. A redirect to another host is reported and not followed. So one link
   costs at most four GETs per address tried. With a proxy set, a redirect the proxy would not
   carry (the environment names a proxy for http and none for https, say) is refused: that
   request would go straight to an address this computer resolved after the check. `_proxied`
   asks the environment about the host and about the host with the port the link writes, the two
   forms a `no_proxy` entry can take, and treats a bypass of either as not proxied.
4. **Screened before it is proposed.** The product's name and description and the page's titles
   go through the offline injection screen; a QUARANTINE or BLOCK verdict withholds the price
   and the title, and a REVIEW verdict is returned in `screen` with a gap. The address a
   redirect lands on goes through the same screen, unquoted up to five times, as written and as
   bare words: a flagged address, or one still encoded after five rounds, is not returned, and a
   REVIEW verdict on it adds a gap. A type that is not HTML is named back from a short list of known types, and a
   redirect's host is named back when it is letters, digits, dots and hyphens.
5. **Recording is a separate, gated write.** `tools/books.py::set_price` puts the price, its
   source, the page and the date on a product entry that is not void, through `validate_entry`'s
   provenance rule, behind `finance_management`. `set_price` also refuses a price that rounds to
   no cents and, for a brand or retailer price, a page that `check_link` does not accept. The
   entry keeps its id, status and other fields.
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
- The dashboard's POST routes still make no network request outside Confirm. The selftest that
  drives each route with each flag on reaches the new route's field checks and stops there, so a
  second case records a brand and a retailer price with the host lookup and the connection
  calls replaced by recorders, and sees neither called.
- A page that builds its price with scripts, blocks automated requests, or lists several
  variants at different prices gives a gap. In the build run, of five public product pages
  tried through a network proxy, one gave its price, one answered 403, one answered 429 after a
  same-host redirect, and two links were not product pages; a brand page the owner names was
  not run.
- With a network proxy set, the proxy resolves the host, so the address check made on this
  computer does not bind the request; when the host does not resolve on this computer, nothing
  is fetched.
- The title returned is page content. The tool's description tells a session to treat it, the
  link and the gaps as the page's words; the title is cut at 200 characters. The offline screen
  matches known patterns, so an instruction it rates CLEAN is returned.
- The selftest runs no TLS handshake: it checks that the context verifies certificates and host
  names and that a pinned connection hands the link's host name to it, with stand-ins for the
  socket and the context.
- The `price_capture` tool carries the open-world hint; `fetch` and `search` in the same server
  were not looked at here.
