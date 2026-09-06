# Seasonal aesthetic guide (canonical)

The canonical seasonal reference for the moody-vintage home decor and DIY niche. Atoms that
reason about seasonal timing or seasonal styling load this file. The machine-readable companion
is `canonical-sources/seasonal-aesthetic/seasonal.json`: its `seasonal-windows` entry carries
the same eight windows as resolved ISO dates for a stated reference year, for tools that need
date arithmetic. Upstream source for the timing table: `shared/seo-intelligence-engine.md`
("Seasonal SEO lead times"), which cites pinterest-creator-hub-seo, youtube-creator-blog, and
google-search-status in the source registry.

## Seasonal aesthetic profiles

- **Fall**: gothic undertones, rich burgundy, burnished brass, dried botanicals, layered
  textiles. Moody and collected, not orange-and-plaid farmhouse.
- **Christmas / holiday**: vintage ornaments, candlelight, dark greenery, aged metallics.
  Not red-and-green farmhouse. Pinterest interest arrives 6 to 8 weeks ahead of the holiday;
  video interest 3 to 6 weeks ahead.
- **Spring**: botanical prints, muted dusty rose, brass vessels, vintage garden elements.
- **Year shape**: January organizing, February cozy interiors, March to April outdoor and
  garden, summer retreat and backyard, fall layered coziness, November to December holiday.

## Seasonal timing windows (canonical, reconciled)

The single reconciled timing table. `skills/atoms/seasonal-map/SKILL.md` and the engine table
derive from the same rows; if these ever disagree, this file and `seasonal.json` win.

| Seasonal window | Search peak period | YouTube publish by | Pinterest pin by |
|---|---|---|---|
| Fall / Halloween (mantels, autumn decor) | September 15 to October 20 | September 1 | August 15 |
| Thanksgiving / late fall | November 1 to November 25 | October 25 | October 10 |
| Christmas / holiday (tablescapes, winter decor) | November 20 to December 15 | November 10 | October 31 |
| New Year organizing | December 26 to January 15 | December 20 | December 10 |
| Valentine / cozy February | February 1 to February 14 | January 28 | January 15 |
| Spring refresh and light interiors | March 1 to April 15 | February 20 | February 10 |
| Summer outdoor and backyard | May 1 to June 30 | April 25 | April 10 |
| Back-to-school / fall prep | August 1 to August 25 | July 25 | July 10 |

Dates are month-day pairs that recur annually. The JSON companion resolves them to full ISO
dates for its `reference_year` so offline tools (`tools/obligations.py` and the scenario
runner) can do exact date math; resolve to the planning year when building a real calendar.

## Evergreen topics

Thrift-haul walkthroughs, budget room makeovers, furniture flips, and organization systems
carry no publish-by constraint. They still benefit from keyword and entity optimization at
publish time, and they may incidentally align with a seasonal window (an organization video
lands harder in January).

## How atoms consume this file

- `seasonal-map` classifies a topic against the timing windows above and returns peak window,
  publish-by, and urgency. It never invents a window: a topic that does not map cleanly is
  evergreen (`protocols/no-fabrication.md`).
- `calendar-slot` and content-strategy planning treat the publish-by column as the anchor for
  scheduling and derive production lead time backward from it.
- Shorts do not use the advance-publish window: Shorts distribution is behavioral, not
  date-indexed. Publish Shorts on or near the peak-relevance date (see
  `shared/seo-intelligence-engine.md`, "Shorts and the seasonal calendar").
