# Brownstone Markets requirements

Accepted product behavior and decisions. This is the single home for rules; other documents link here instead of restating them. Planned work lives in `backlog.md`, architecture in `design.md`, current state in `status.md`.

## Product direction

- **Purpose:** a local WoW market research tool that traces materials through intermediate crafts to finished goods and explains which crafts are worth investigating.
- **Target game:** WoW Forever (beta since 17 September 2026; last full beta testing day 21 October; launches 4 November 2026). It has no public price feed, so the baseline source is our own read-only scanning addon, imported as described under *Addon scans* below.
  - **Official dates** (checked 2026-10-04): [Blizzard beta announcement](https://worldofwarcraft.blizzard.com/en-us/news/24304160/) gives 21 October as the last full testing day; [Blizzard Forever page](https://worldofwarcraft.blizzard.com/en-us/forever) lists launch on 4 November 2026.
- **Known Forever market facts** (checked 2026-10-04, mostly third-party; re-verify at launch):
  - Forever has no realms. Each region (US, EU and so on) has one auction house per server type (Normal, PvP, RP, later Hardcore) and faction, plus a neutral house with a 15% cut instead of 5%.
  - Blizzard's API publishes no Forever auction data, and TSM has no Forever data.
  - Existing Forever price sites are fed by players' addon scans. Forever addons reportedly use the modern `C_AuctionHouse` API, which has Retail-style commodities.
  - Forever reuses Classic item IDs: 2,323 of the 2,927 items priced in the 2026-10-04 beta scan are also priced on Classic Era Mankrik under the same IDs. Prices differ (see STORY-012), so this allows explicit comparison, never joining (DATA-03).
  - **Unconfirmed claims** (from outside design notes, 2026-10-06; not evidence, never built on until checked in game, checklist under *Now* in `backlog.md`): a Black Market vendor sells a fixed list of scarce materials at fixed prices (claimed 50g each, Pyrite 5g); a sold auction's gold arrives by mail about 2 minutes after the sale; auction scans are throttled beyond `ReplicateItems`' 15 minutes; the event names for purchases, crafts, posts and mail match Retail's.
  - **Measured, contradicting those notes:** the notes assumed Retail-style commodities (per-unit price tiers) and a seller on every listing. The beta reports neither (ADDON-02, ADDON-07).
  - Sources: [Wikipedia](https://en.wikipedia.org/wiki/World_of_Warcraft:_Forever), [AHledger](https://ahledger.com/wow-forever/auction-house), [WowGuide realms](https://wowguide.net/en/guides/wow-forever-realms-rulesets), [Blizzard API forum: Classic Era auction 404s](https://us.forums.blizzard.com/en/blizzard/t/404-for-all-classic-era-namespace-auction-house-endpoints/54307), [WOW4E_AH_Trader](https://github.com/1nd1v1d/WOW4E_AH_Trader).
- **Development stand-in:** Mankrik Alliance, Classic Era (TSM public realm CSV). Classic is used to build and prove the product, not as the end market. Switching to Forever must be a configuration and catalog change: add a source whose market fields describe the Forever house and whose `rules_version` matches a Forever catalog. It must not require code changes.
- **Retail:** not a product requirement (decided 2026-10-04). Retail sources remain configured only as an ingestion regression check, because they exercise regional scope and upstream timestamps that Classic lacks. No feature work targets Retail. They may be removed when they stop earning their keep.
- **Launch market (decided 2026-10-04):** Forever, US region, Roleplaying server type, Alliance faction. The neutral auction house is a separate, secondary market. The user has beta access, so SPIKE-008 targets the Forever beta directly.
- **Dependable data (decided 2026-10-04):** nothing in the architecture may require a source the user doesn't control.
  - **Baseline source:** the user's own addon scans. Every feature must work with only this.
  - **Optional sources:** other players' aggregated scans (third-party sites, TSM). They may only enrich or cross-check, never be required.
  - **Access rules:** a third-party source is used only through an official export or API whose terms allow it, never by scraping.
  - **Removability:** if an optional source disappears, Brownstone keeps working on the baseline.
- **Addon (decided 2026-10-04, SPIKE-008): build it.** A read-only addon, `addon/BrownstoneScan/`, scans only after a click or slash command at the auction house and never buys, posts, cancels or scans unattended.
  - **Your own character's data (decided 2026-10-06, product owner):** the addon may also *read* your own characters' gold, bags, bank, mailbox (including auction invoices and returns), your own auctions, crafts and vendor purchases and sales, and record them locally for Brownstone (STORY-032, STORY-033). It still never acts: every buy, post, craft, mail and cancel stays a manual click by you. Recording happens on game events you trigger by playing (opening the bank or mailbox, logging out), never on a timer. Why: profit, sell-through and cost basis can't be measured from listings alone; only your own sales and holdings show them. **Observing your own actions (decided 2026-10-07, product owner):** the addon may log all of your economy activity silently in the background, on game events and by observing the game functions you call (secure post-hooks that record arguments). It never acts on your behalf (no sending mail, posting, buying, cancelling, crafting, looting or taking mail), because automated actions break the game's terms. Logging prints nothing to chat in normal use; only problems (a rejected event, a full journal) are reported.
  - **Deferred (2026-10-06):** an in-game plan or to-do list written by Brownstone into the addon folder (`PlanData.lua`). Reading Today on a second screen covers it for now, and it would make Brownstone write into the game folder.
  - **Evidence:** on the Forever beta (client 1.60.1, build 70205), one scan of the Alliance Normal-server house in Stormwind used `C_AuctionHouse.ReplicateItems` and saved 101,485 listings in about 10.6 s, in a 24 MB SavedVariables file. A second scan three minutes later got no reply, as the documented 15-minute account-wide throttle predicts. The client has no legacy auction event.
  - **Not measured:** the Roleplaying house (not yet available in the beta), a neutral house (out of reach for now), and whether a slash command alone is accepted without the button click. The button worked.
  - **Scan format STORY-010 ingests:** `BrownstoneScanDB` with a list of scans, each with its own `schema_version`; fields are documented in `addon/README.md`, with a sample at `tests/fixtures/brownstone_scan_sample.lua`. Schema 1 (addon 0.1.0) writes one keyed table per listing. Schema 2 (addon 0.2.0, decided 2026-10-04 to keep the addon light and the file small) writes one `item_id:quantity:buyout:min_bid:bid:flags:name_index` string per listing and each scan's distinct names once; it drops `link` and `unit_buyout`, which Brownstone never used. Both import to identical listings and prices. Format 3 (addon 0.3.0) adds indexed sellers, level types and full links, richer listings and one item-reference observation per ID per scan (ADDON-09). A file may hold all three formats. Each scan has a `scan_id`, UTC start and finish, `status` (`completed` or `stopped`), `listing_count` against `reported_count`, client build, region, realm, player faction, auctioneer and zone, and a free-text `label`. Import treats these as evidence of which house it is, never as a market (ADDON-01).
  - **Listing semantics:** Forever's `buyout` is the price of the whole stack (Classic-style), with `quantity` the stack size, and no commodity status is reported. The addon does no pricing: import divides `buyout` by `quantity` itself (ADDON-02). Schema 1's `unit_buyout` was meant to hold that division but was missing on all 28,105 stacked listings of the 2026-10-04 scan; it is only a cross-check, and schema 2 doesn't write it. A listing the client flags as a commodity (per-unit price) rejects the scan, since only stack prices are modeled. A missing `buyout` means no buyout, never free. Listings the client hadn't fully loaded (4,690 in that scan) have an empty `name` and no `link`, but valid item ID, quantity and buyout.
  - **Known costs:** schema 1 takes about 240 bytes per listing (24.8 MB for the 101,485-listing scan); schema 2 about 28 (2.8 MB, parsed in 0.1 s). The addon keeps every scan until `/bscan clear`, which refuses scans not yet written to the file (they exist only in game memory until `/reload` or logout). Brownstone suggests clearing only after an import saved something new and every scan in the reviewed file is saved; a subset with remaining scans forbids clearing, scans from another auction house get a warning that clearing deletes them, and an import with nothing new warns to `/reload` instead (decided 2026-10-04, after a scan was lost by clearing before it was written). Region and realm are generic on the beta and do not identify the house.
- **Recipe data (decided 2026-10-04, STORY-004):** catalogs are generated from Wowhead profession pages that the user saves in a web browser, one page per game version and profession (for example `https://www.wowhead.com/forever/spells/professions/tailoring`; Wowhead lists Cooking and First Aid under `.../spells/secondary-skills/` instead). Brownstone never downloads from Wowhead.
  - **Terms:** Wowhead's terms (`wowhead.com/tos` → ZAM Network EULA, last updated 14 May 2025, checked 2026-10-04) grant a personal, non-commercial licence to use the websites "solely for your own internal use". They forbid downloading content with "spiders, robots, crawlers, data mining tools or the like" other than ordinary web browsers, and they allow ZAM's APIs only as documented (the tooltip API is documented for embedding tooltips on web pages). So scripted fetching, including of `nether.wowhead.com` tooltips, is not allowed. Pages saved by hand in a browser are.
  - **Why one page:** a saved profession list page holds every recipe of the profession: reagents, quantities, created item and count, and the skill level it's learned at. It also holds every item it mentions, with name, sell price and buy price. Forever pages also mark each spell as new, updated or unchanged relative to Classic, but Runecloth Bag is marked unchanged despite its new dyes, so the marker isn't trusted for reagents.
  - **Alternatives considered:** reading the in-game Tailoring and trainer windows with the addon would confirm output counts but covers only recipes the character knows. wago.tools has no Forever build. Both stay options for confirmation, not the catalog source.
- **Out of scope:** automated buying, selling or posting, unattended in-game scanning, cloud deployment and AI-generated recommendations without explainable features.

## Rules

### Data integrity
- **DATA-01 Raw preservation:** every download is saved byte-for-byte before validation. Each has a manifest with source, SHA-256, UTC collection time and status, including failures. Raw files are never overwritten. An addon scan file whose bytes (SHA-256) are already in that source's bronze folder is not copied again; the new manifest names the existing file in `bronze_file` (decided 2026-10-04, because scan files are about 24 MB). New addon copies are stored gzip-compressed (`.lua.gz`, decided 2026-10-04 to save disk): the manifest's SHA-256 is of the original bytes, and the copy is checked to decompress to them before it is kept, so preservation stays exact. Earlier `.lua` copies stay as they are. Preview and rejected reviewed imports are read-only exceptions: they create no archive or failure manifest. An explicit CLI import still preserves successfully read bytes before validation; a successful reviewed import archives exactly the reviewed bytes.
- **DATA-02 Validation:** required columns, integer copper prices, unique positive item IDs and timestamps that are either all present or all absent. Zero means unavailable or no listing.
  - **Item names (decided 2026-10-05, STORY-022):** retain each observation's loaded name. NULL, blank/whitespace and `Item <digits>` placeholders are missing names. At read time, missing names use a derived lookup keyed only by `game_version + item_id`; this shares labels across sources, houses, regions and beta/live within that version. Labels never join prices or supply, cross game versions, or imply categories (DATA-03/DATA-08).
  - **Fallback precedence:** observed game-client/TSM names beat catalog (Wowhead) names. Among observations, use the newest loaded name by scan finish time or TSM update time, falling back to collection time when absent. A newer observation without a loaded name never erases one. Equal timestamps choose the alphabetically first name; catalog-only conflicts also choose the alphabetically first name. Identical names/times choose the alphabetically first evidence reference, so import order and migration replay cannot change the result. Legacy observations without either time use the Unix epoch for ordering.
  - **Preservation and display:** fill the lookup from any imported listing (including partial scans), price row and validated local catalog; backfill existing observations on migration. Bronze, silver, listings and stored price names stay unchanged. Browse/search, Opportunities and Scan changes use resolved labels; crafting and board depth retain their catalog labels. `Item <ID>` remains only when no observation or catalog in that game version has ever named the item. Local catalogs seed on upgrade, import (including duplicates) and app startup; labels do not require catalog rules compatibility.
- **DATA-03 Market identity:** a market is one auction house: `game_version + region + scope + realm + server_type + faction + environment`. Item IDs never join across any of these.
  - **Fields:**
    - `environment` is `live` or `beta` (decided 2026-10-05, STORY-017). Forever sources must configure it explicitly; Classic and Retail are always `live` (the default; `beta` is refused, decided 2026-10-05). It comes only from source configuration, never scan contents or client-version inference. A beta and live scan of the same house have identical house evidence; verify the configuration during cutover (STORY-020b).
    - `scope` is `house` (one auction house) or `region` (a region-wide commodity pool).
    - `realm` names the house where realms exist; `server_type` (normal/pvp/roleplaying/hardcore) names it in realmless Forever. A market uses one or the other, never both.
    - `faction` is alliance, horde, neutral, or blank for cross-faction houses.
  - **`market_id` is derived, never configured** (for example `classic-us-mankrik-alliance`, `forever-us-roleplaying-alliance`), so two sources for one house and environment always agree. Beta IDs append `-beta` (for example `forever-us-normal-alliance-beta`); live IDs stay unchanged.
  - **Auction cut:** set per source. Neutral houses default to 15%.
- **DATA-08 Source independence:** a market's identity says *which auction house*. A source's identity (`source_id`, `provider`) says *who observed it*: your addon, TSM or a third-party site. The same market can have several sources. Every manifest and price observation records its source, deduplication is per source, and each source keeps its own data folder. Combining sources follows an explicit, versioned policy, never silent mixing. Until that policy exists (STORY-011b), each view reads one selected source.
- **DATA-04 Deduplication:** identical market, scan time and content hash reuse one analytical snapshot. Every raw collection is still recorded with its own manifest. Addon scans deduplicate by `scan_id` per source instead (ADDON-04).
- **DATA-05 Freshness:** age comes from upstream scan time when the source provides it (for addon scans, the scan's finish time). Otherwise it comes from collection time, explicitly labeled as "price age unknown". Stale means older than `max_age_hours` (default 24) or more than 15 minutes in the future. A source may opt out of upstream time only when the entire column is blank (`allow_missing_updated_at`).

### Addon scans (decided 2026-10-04, STORY-010)
- **ADDON-01 House identity:** the configured source defines the market; nothing is derived from a scan. Each scan's player faction must match the market's alliance or horde faction, and must not be from a neutral house. A neutral market needs the client's `neutral = true` or a configured auctioneer. Optional `scan_evidence` (`faction`, `auctioneer`, `zone`, `realm`, `label`) must match exactly. Any mismatch in any selected scan fails the whole import, naming the scan, field, observed and configured values, before anything reaches DuckDB. Beta region and realm are generic and aren't evidence by default.
- **ADDON-02 Stack pricing:** a listing's unit price is `buyout / quantity` in integer copper. When that isn't exact, `unit_buyout` stays empty and `unit_buyout_ceil` rounds up, so a unit's cost is never understated; derived prices use `unit_buyout_ceil`. On the sale side this can overstate a unit by under 1c; the manifest counts such stacks (`nonexact_stacks`). A reported `unit_buyout` (schema 1) that disagrees with the division rejects the scan. A missing or zero `buyout` has no unit price and is never free.
- **ADDON-03 Item prices:** each complete scan writes one `market_snapshots` row per item identity, including variant and resolution state (ADDON-08):
  - `min_buyout` and `market_value`: projections of ADDON-10's lowest unit buyout and quantity-weighted 25th percentile, using the shared calculator.
  - `recent_value` and `historical_value`: 0 (unavailable), so the discount screen explains it can't run.
  - Items listed only without a buyout get 0/0, so Browse still finds them.
  - Cautious and listed bases (CRAFT-04) use these unchanged.
- **ADDON-04 Deduplication and partial scans:** a scan is identified by `scan_id` per source. Re-importing it is a no-op; the same `scan_id` with different content fails. A scan is partial when `status` isn't `completed` or `listing_count` differs from `reported_count`. Partial scans are stored and labeled, listings included, but never feed prices, because they can miss the cheapest listing. A file with no complete scan leaves prices unchanged. The newest complete scan in a file becomes its snapshot, and the views use the newest observation across imports, so an older file can't replace newer prices.
- **ADDON-05 Time:** a scan's finish time is its observation time. Old scans import, and the board labels them stale. A scan finished more than 15 minutes in the future is rejected as a clock error.
- **ADDON-06 Import is read-only and on demand:** an explicit **Preview addon scans** click reads the selected source's configured `scan_path`, validates every scan's header, times and listings using the shared CLI rules and displays ID, UTC start/finish, status, listing count, import state and partial status. A scan whose house evidence doesn't match the source's market (ADDON-01; the SavedVariables file is account-wide, so other characters' scans share it) is listed as from another house with the reasons and can't be selected, instead of failing the preview. New partial scans and imported partial scans are distinguishable. Preview writes nothing: no data directory, database creation/migration, bronze, manifest, silver or source-file edits. Existing databases are queried read-only; a missing database has no imported scans.
  - Select any subset of new scan IDs (the same selection semantics as CLI `--scan`), then explicitly click **Import addon scan**. Empty selections offer no import. A duplicates-only file explains that nothing is new, reminds the user to `/reload` and offers no import. Partial and empty scans remain importable for preservation under ADDON-04.
  - Before writing, import recomputes the preview. Changed bytes, source/configuration (including input and data paths, market, rules and house evidence), or duplicate records for scans in the file invalidate it and require another Preview click. Import uses the validated bytes held in memory, never a subsequent unreviewed reread. The database writer transaction rechecks duplicate state before archiving or loading. A known scan ID with a different per-scan content hash is a conflict, not a duplicate.
  - Reads are bounded to 256 MiB plus one overflow byte and compare descriptor/path identity, size and nanosecond modification/change times before/after reading. This is best-effort change detection, not an atomic read guarantee. Missing, unreadable, truncated, malformed, oversized or detected-changing files fail with a retryable message. These read failures happen before there are bytes to preserve, so they write no manifest (DATA-01 applies from the first complete read). The game's file is never written, watched or polled.
  - CLI imports remain available from configured `scan_path` or `--input`, with selected-scan validation and failure preservation under DATA-01. Shared app/CLI guidance recommends `/bscan clear` only when something new was saved and no scans in the file remain unimported; subset imports protect the remaining scans. Scans from another auction house don't count as remaining, since this source can never import them; guidance warns that clearing deletes them. Scans an import didn't select are not validated, and an unusable one counts as remaining instead of failing the import. Nothing-new guidance reminds users to `/reload` before retrying.
- **ADDON-07 Seller names (decided 2026-10-05, STORY-023):** addon 0.3.0 records each listing's seller name. These are other players' character names, kept only on the user's own machines: never exported, published, shared or sent to any external service (including AI narration, unless that decision says otherwise). The explicitly approved private Google Drive drop transport under OPS-03 is the exception for raw addon copies between the user's machines; it does not authorize publishing or other external processing. A seller the client hasn't loaded is missing (null), never guessed. **Beta finding 2026-10-06 (build 70235):** the bulk scan API returned no owner for any listing (0 of 88,119), so format-3 beta scans carry no sellers. Any other way of capturing them needs a new decision (*Seller capture* under Later in `backlog.md`).
- **ADDON-08 Item variants (decided 2026-10-05, STORY-023):** a variant that changes an item's stats, such as a random suffix (*of the Monkey* versus *of the Bear*), is a separate priced item. Its listings, prices, metrics and depth never pool with other variants or the base item ID, because demand and price differ. Variant identity is part of the item key alongside DATA-03's market identity; items without variants keep a null variant. Scans from formats 1 and 2 carry no variant evidence, so their gear listings stay unresolved, never assigned to a variant. **Identity approved 2026-10-05:** source + full DATA-03 market identity + scan/snapshot + `item_id, variant_id, variant_state`; crafting retains the `rules_version` check. `variant_state` is `base`, `variant` or `unresolved` in format 3. Older observations keep null new fields (shown as `legacy`); their historical aggregates are preserved without reassignment. **Comparison amended 2026-10-05:** a legacy row matches another legacy row of the same item, and matches a format-3 `base` row only when that format-3 scan has nothing but base listings for the item ID; otherwise (variant or unresolved rows present, or the item absent) it stays a separate `legacy` row, since it may pool suffixes. Item-name evidence comes only from base or legacy rows, never a variant's or unresolved row's name. Historical catalog reads still work on their original scans, but format-3 unresolved rows never enter a base-item craft/depth calculation. Explicit variant/depth reads match the requested identity exactly; legacy null-state rows never answer an explicit `base`, `variant` or `unresolved` read.
  - Count item-link payload positions from `itemID = 1`: include enchant (2), four gems (3–6), traditional suffix ID (7), and the bonus list (count at 13; IDs from 14). Canonical key: `v1:e<enchant>:g<four comma-separated gems>:s<suffix>:b<sorted comma-separated bonuses>`. Empty and zero stat fields are equivalent. A supported link without modifications has null `variant_id` and state `base`; missing/unsupported links have null ID and state `unresolved`.
  - Viewer level (9), specialization (10), unique ID (8), display name and color are not price identity. The observed contexts (12: empty/0 or 1) and modifier type 28 carry provenance and are ignored for identity. Nonzero modifier mask (11), other contexts/modifier types, nonzero unknown tails, malformed/count-truncated links, item-ID mismatches and negative suffixes with a nonzero unique seed/factor remain unresolved. All original link bytes remain available, so an expanded parser can be implemented later with evidence. These rules conservatively isolate unsupported observations; they do not infer suffixes from names.
  - **Actual Forever evidence:** archived scan `20261004T164730Z-c651bd` (build 70205, 2026-10-04) has Willow Robe (6538) Monkey/Bear/Eagle bonus IDs 12721/12722/12718 and Primal Wraps (15010) Whale/Bear IDs 12719/12722. All have an empty traditional suffix field. Full representative links are pinned in offline tests; tooltip equivalence, including context/modifier-28 variants of the same bonus, must be checked in game (checklist in `addon/README.md`).


- **ADDON-09 Capture contract (approved 2026-10-05, STORY-023):** addon 0.4.0 writes scan format 4 (format 3 listing fields unchanged). Existing client/house/times/counts/status evidence and the read-only manual lifecycle stay intact. The canonical capture list and API sources are below. Optional APIs are guarded; item references get one initial lookup per ID, then the scan-owned bounded pass below. Missing new fields in formats 1 and 2 stay null, never taken from newer scans or catalogs. Format 1's old link stays preserved in bronze, but is not retroactively variant evidence.

  | Per listing | API source (modern; legacy fallback) |
  | --- | --- |
  | `item_id`, `name`, `quantity`, `min_bid`, `buyout`, `bid`, `complete_info` | `C_AuctionHouse.GetReplicateItemInfo(index)`; `GetAuctionItemInfo("list", index)`, existing return positions 17, 1, 3, 8, 10, 11, 18 |
  | `seller` | Same tuple, nonblank `ownerFullName` (15), falling back to `owner` (14); missing stays null, ADDON-07 |
  | `quality`, `level`, `level_type` | Same tuple, returns 4, 6, 7. Quality/level zero is a reported value, not a missing sentinel |
  | `required_level` (import-derived) | `level` only when `level_type` is `REQ_LEVEL` (modern) or `REQ_LEVEL_ABBR` (Classic auction UI header); other/unknown types stay null. The Forever beta reports `REQ_LEVEL_ABBR` (also `SLOT_ABBR`, `SKILL_ABBR`; 2026-10-06) |
  | `time_left` | `C_AuctionHouse.GetReplicateItemTimeLeft(index)`; `GetAuctionItemTimeLeft("list", index)`. Raw bucket 1–4, no invented expiry timestamp or duration mapping. A time left outside 1–4, quality outside 0–8 or negative level is stored as missing and counted (`listing_out_of_range`), never rejecting the scan; the raw value stays in bronze |
  | `item_link` | `C_AuctionHouse.GetReplicateItemLink(index)`; `GetAuctionItemLink("list", index)`. Full original link for every available listing, indexed once per distinct link |
  | Commodity flag | Existing `C_AuctionHouse.GetItemCommodityStatus(itemID)` evidence; legacy never asserts commodity status; per-unit scans still rejected under ADDON-02 |

  | Per item ID, once per scan | API source |
  | --- | --- |
  | `item_id` | Observed listing ID |
  | `class_id`, `subclass_id` | `C_Item.GetItemInfoInstant(itemID)` or global `GetItemInfoInstant`, returns 6 and 7; official numeric class IDs, never name-derived categories |
  | `item_level`, `max_stack_size`, `vendor_sell_copper` | `C_Item.GetItemInfo(itemID)` or global `GetItemInfo`, returns 4, 8 and 11. Base-item observations, not variant tooltip stats; vendor price is per item in integer copper, including a reported zero |

  - **Amendment approved 2026-10-06 (STORY-031):** the beta loaded vendor price, item level and stack size for only 1,192 of 3,066 items. Addon 0.4.0 saves the scan and counts it as unsaved immediately after listing reading, before its item pass. When the pass reaches an item missing any of these three fields, it first re-reads it with the guarded item-info reader: if every missing field is now present (the item loaded during listing reads, before the pass listened), the values are recorded without a request. Otherwise the item gets at most one guarded `C_Item.RequestLoadItemDataByID(itemID)` request. `ITEM_WAIT_LIMIT = 20` seconds bounds the whole pass, including request dispatch; `ITEM_REQUESTS_PER_FRAME = 200` bounds dispatch per frame. Guarded registration of `GET_ITEM_INFO_RECEIVED(itemID, success)` records rejection; a missing request API or rejected event skips the pass with a reason. Successful answers use the same guarded item-info reader (returns 4, 8, 11); failed answers or request exceptions are counted, never retried. Answers at/after the deadline or after termination are ignored. Completion clears the frame callback; no later timer, repeat or automated scan is permitted.
  - **Preservation and effective references:** `items` and all listings/links remain first-pass evidence, never re-read or changed. Separate `item_pass.items` records only IDs gaining a reference field, with missing fields omitted. Import resolves each field from first-pass evidence when present, otherwise from this scan's pass; a reported zero wins. Raw pass fields and per-item effective-field provenance remain stored separately; older observations retain null provenance. References keep source + full MARKET_KEYS + scan/snapshot scope. This improves item references only: the 6,060 missing listing links in the baseline remain missing and variant identity is unchanged.
  - **Lifecycle/UI:** closing the house after listings finish does not stop the pass; closing during listing reading keeps a stopped scan and its bounded reference pass. The scan button shows `Item info answered/total`; Reload and Clear stay disabled, and all clear paths refuse during the pass (the unsaved-session guard still applies afterward). One pass-end chat summary reports requested, received, failed and timed-out counts. `/bscan stop` ends the pass without changing scan completion/partial/pricing status. Manual `/reload` or logout mid-pass preserves gathered data with pass status `running`, never resumes the pass on login, and does not discard or deprice a completed scan. The format and counter definitions are in `addon/README.md`.
  - **Availability:** format-4 availability includes first-pass, pass-added and effective field counts, plus pass total/requested/received/failed/timed_out counts in the per-scan manifest and database. Availability never changes listing counts, scan status, partial state or pricing eligibility. Beta acceptance of 0.4.0 is pending availability, added duration, bytes-per-listing and reload-lag measurements against 0.3.1; the checklist is in `addon/README.md`.

  API contracts: [Blizzard generated auction definitions](https://github.com/Gethe/wow-ui-source/blob/live/Interface/AddOns/Blizzard_APIDocumentationGenerated/AuctionHouseDocumentation.lua), [Classic item definitions](https://github.com/Gethe/wow-ui-source/blob/classic/Interface/AddOns/Blizzard_APIDocumentationGenerated/ItemDocumentation.lua). Forever availability is still subject to beta measurement.
  - **Measurement limits:** one full format-3 beta scan (addon 0.3.0 or later; record the exact version) must be imported by 21 October. Compare single-scan 0.2.0 and 0.3.0 files from the same house with similar listing counts: duration at most **2×** baseline, uncompressed bytes per listing at most **4×** baseline. Record actual values, lag/reload time, and availability counts/denominators for every new listing/item field; there is no invented availability threshold. Availability affects evidence, not completion status. Import records these counts (including resolved/base/unresolved links and out-of-range optional values) and duration locally in the per-scan manifest and database. File byte counts are the original uncompressed input, not gzip bronze size. A failed limit leaves beta acceptance pending; remeasure after any change.


### ADDON-10 Market metrics (metrics_version 1, approved 2026-10-06, STORY-024)

The market metrics layer describes observed listed supply, not executed sales, demand, liquidity,
realizable profit or a seller's complete activity. These facts support subsequent buying/crafting,
market timing and competitor models without inventing evidence. Rules below define version 1;
a changed definition requires a new metrics version and an explicit rebuild policy.

- **Eligibility:** store metrics only for `status='completed'`, `partial=false`, `priced=true` addon
  scans. `priced` is the existing complete/nonempty flag, not a guarantee of a buyout for every item.
  Complete scans containing only no-buyout listings still have supply metrics with null prices.
  Partial/unpriced scans retain their existing observations, but metrics are unavailable. An empty
  scan has no metric rows. Missing prices are always null in this layer, never zero.
- **Identity:** `metrics_version + source_id + every MARKET_KEYS field + scan_id + snapshot_id +
  item_id + variant_id + variant_state`. This includes derived `market_id` and all seven DATA-03
  fields. Never pool variants, base or unresolved identities. Formats 1/2 retain null variant state
  (displayed as legacy), including historical scans whose format metadata is null. No retrospective
  link interpretation or seller backfill. ADDON-08's legacy/base cross-scan comparison policy stays
  a read-time matching policy; it does not merge facts. Every listing must match its stored parent
  on source, full market identity, scan and snapshot.
- **Prices:** use positive `unit_buyout_ceil` from ADDON-02, in integer copper. Lowest unit buyout is
  the minimum. Median, 10th and 25th percentile are quantity-weighted nearest rank: sort prices,
  let N be buyout-priced units, and choose the first price whose cumulative quantity reaches
  `ceil(p*N/100)` for p=50,10,25. Count each unit once, without interpolation. The even-count median
  is the lower middle unit. The 25th percentile agrees exactly with ADDON-03's market value.
  No-buyout quantities never enter N. All four prices are null when N=0; priced units is then zero.
- **Supply:** units listed sums all quantities; listing count counts listing rows, including rows
  without buyouts. Largest-stack share is `max(quantity) / units listed`, for one listing (ties do
  not combine). Shares are exact numerator/denominator integer pairs, not rounded stored floats.
- **Supply below a price:** calculate at read time from stored listings, under identical eligibility
  and exact identity predicates. Sum quantities with positive `unit_buyout_ceil` strictly less than
  the caller's positive integer-copper threshold; equality and no-buyout listings do not count.
  Reject nonpositive/noninteger thresholds. This reuses listings instead of duplicating a threshold
  distribution. It describes units at quoted unit prices, not an executable whole-stack purchase
  cost. An absent exact identity in an eligible scan returns zero; an ineligible scan is unavailable.
  Null variant/state arguments select legacy exactly, unlike catalog depth's compatibility default.
- **Sellers:** format-3 seller count is distinct observed nonblank strings compared exactly as
  stored, without guessed character equivalence or case normalization. Sum each observed seller's
  units, including no-buyout listings. Top seller share is the largest such sum divided by all
  seller-known units. With incomplete coverage, label it *top observed seller's share of seller-known
  units*. Always report seller-known listing/total listing and seller-known unit/total unit coverage
  alongside seller measures. Missing sellers are never an invented seller. Format 3 with no known
  sellers has null seller count/top share and zero known counts over total supply. Formats 1/2 and
  historical null-format scans have null seller measures and coverage, not zero. ADDON-07 applies:
  no seller strings or top-seller identity in metric storage, returned aggregates, logs, reports,
  exports or external services. Existing local listing evidence remains local.
- **Storage/rebuild:** migration 7 creates `scan_metrics` using frozen schema DDL only. Version-aware
  derived initialization, outside migrations, backfills eligible stored listings before analytical
  reads and records completion only after success. Missing completion at schema 7 retries on startup
  or explicit import. One transactional rebuild path recalculates version 1 from stored listings;
  repeated runs give identical rows, including after reordered input. Imports compute new facts in
  the existing scan transaction. Preserve archives, silver and historical observation rows.
- **Shared calculations:** addon item prices project this calculator's minimum and 25th percentile
  into `market_snapshots`. Its existing ADDON-03 zero sentinel remains for compatibility only;
  metric outputs use null. Historical price rows are not rewritten. TSM's price contract stays
  unchanged. Board depth reads stored units/listings; Scan changes reads stored minimum, percentile,
  units and listings, retaining ADDON-08 matching and DATA-02 naming. Name-only listing aggregation
  remains for labels; threshold supply reads listings because its price is caller-selected.


### ADDON-11 Character snapshots (STORY-032)

- Introduced in addon **0.5.0** with account-wide `BrownstoneScanDB` format **5** (`SavedVariables`); ADDON-12 extends the current file to format 6;
  scan records retain format 4 and formats 1–4 remain importable. `snapshots` records bags/gold on
  guarded `PLAYER_LOGOUT` (including `/reload`), and bank on guarded `BANKFRAME_OPENED` and
  `BANKFRAME_CLOSED`. These events and container API behavior remain pending Forever beta checks.
  Only container/money/identity/level/skill reads are added: no requests, timers, buying, posting, moving,
  sorting or mail. Bank readers run only between bank-open and bank-close events.
- Snapshot evidence is character name, realm, faction, Unix seconds + UTC text, addon version,
  kind (`bags`/`bank`), triggering event, login time, container API, rejected events and fired-event
  counts. Gold is nullable integer copper; reported zero is valid. Occupied slots retain container ID,
  positive slot, nullable item ID/count and exact item-link text. Empty slots are omitted; missing
  values never become zero. Container IDs follow the client's own bank offset: bags are the keyring
  and 0 to `NUM_TOTAL_EQUIPPED_BAG_SLOTS` (a modern reagent bag included; `NUM_BAG_SLOTS` where that
  isn't defined), and the bank is the main bank, the reagent bank and the `NUM_BANKBAGSLOTS` bags after
  them. `Enum.BagIndex` is not used for IDs, because a reagent-bag name can share the first bank bag's
  number on Classic-style clients; each snapshot records the layout values it used (`container_layout`)
  for the beta check. Container sizes remain nullable when
  unreadable; failed slot reads mark `slots_readable = false`; a zero-sized main bank is treated as
  inaccessible. Incomplete container coverage is labeled and latest item/slot totals stay unknown rather than asserting an empty inventory.
- **Level and skills (STORY-041, addon 0.8.0):** every bags snapshot also reads nullable
  `UnitLevel("player")` and both available guarded skill surfaces: `GetNumSkillLines`/
  `GetSkillLineInfo` and `GetProfessions`/`GetProfessionInfo`. Keep API provenance, counted raw
  tuples (including nil positions), row indexes, names, header state, rank/max and reported IDs.
  Missing APIs/returns stay absent; an older snapshot or unreadable skills remains *skills unknown*.
  A collapsed or unreadable legacy skill header hides lines, so `skills.legacy.possibly_incomplete`
  is set and the import page shows *possibly incomplete*; the addon never expands it.
  The addon import page alone displays latest bags level and skill ranks/max per character;
  it never infers a profession or catalog match from a name. Beta must confirm skill API shapes,
  IDs, gathering/secondary coverage and logout/reload readability.
- **Unreadable logout reads (addon 0.10.0, decided 2026-10-08):** the first real Forever logout
  snapshot (Windows, 08 Oct) read 0 slots in every bag, 0 copper and level 1 while the same
  login's journal showed items and 52 copper. The client no longer answers at logout. The addon
  therefore also reads bags/gold/level/skills in memory after login, settled bag changes, money
  changes, `PLAYER_LEVEL_UP` (using its level argument) and `SKILL_LINES_CHANGED`, keeping only a
  read whose backpack (container 0) has a positive size. At `PLAYER_LOGOUT` a fresh read is still
  tried first. If its backpack isn't readable and this character has such a read, that read is saved
  instead with its own `captured_at` and `read_event`, `event = PLAYER_LOGOUT`, and the logout's
  gold/level/containers kept under `unreadable_read`. Without one, the logout read is saved as read.
  Brownstone treats any bags snapshot whose backpack reports 0 slots as unreadable: never complete,
  never the latest bags/gold/level/skills (*unknown* instead), excluded from beta reconciliation and a
  `bags readable` failure in the beta report. Its raw record is preserved and imported unchanged.
- **Clear/session rule:** initial `PLAYER_ENTERING_WORLD(true, false)` records this character's
  login marker in `sessions`; `(false, true)` retains it across reload. Only the first world entry
  after the addon loads sets or keeps the marker; later loading screens leave it alone, flags or not.
  Unknown first signals retain all snapshots, and `/bscan clear` says so instead of claiming a prune. Both `/bscan clear` and
  `clear all` remove only snapshot records with `captured_at < current login_at` (account-wide),
  keeping current-session records, including bank records and other characters' records at/after
  that time. Missing timestamps are retained. Scans keep their existing behavior: written scans
  clear, unwritten scans refuse unless `clear all`, and active scans/item passes block either clear.
  The confirmed button uses the same rule. A removed bank record becomes *bank unknown* in game;
  clearing never deletes Brownstone's latest imported bank evidence or changes its time.
- IDs contain length-prefixed character/realm, kind, Unix time and a persistent account sequence
  to distinguish same-second events. Deduplication is per source + snapshot ID; identical canonical
  content is a no-op, changed content conflicts. Stored parents carry every MARKET_KEYS field,
  character realm/faction and machine from the configured local input or drop filename (OPS-03),
  never from SavedVariables. Scope changes refuse ID reuse. Characters are never pooled.
- Snapshot realm matches configured `scan_evidence.realm`, otherwise a realm-based market's
  lowercase, hyphenated realm slug; faction matches `scan_evidence.faction`, otherwise the market faction. Auctioneer/zone/label
  evidence applies to scans only: a character need not stand at an auctioneer to snapshot bags.
  Forever's generic realm cannot establish server type; verify the source selection manually.
  **Scope (decided 2026-10-07, product owner):** the addon runs only on characters of the market's
  own realm and faction, so other-house snapshots are not expected in normal use; if one appears it
  blocks Fully imported until cleared, like a scan. Neutral-house sources are out of scope for
  snapshots for now (a character is never neutral, so every snapshot would count as other house).
- Snapshots use the same bounded read, read-only preview, stale-review checks, per-file transaction,
  exact-byte bronze collection and drop inventory as scans (ADDON-06, DATA-01, OPS-03). Snapshots-only
  files are valid; a completely empty file still gets reload guidance. Import guidance counts new
  snapshots as well as new scans: an import with neither still says *Nothing new*, /reload first. Preview lists each snapshot's
  character/kind/time/machine and new/duplicate/other-house state. Every matching snapshot in a selected
  file imports, including with CLI `--scan` (which limits scans only). Other-house snapshots remain
  unimported. Fully imported requires **every scan and snapshot** to match stored content and house;
  other-house records or file errors block cleanup. Snapshot evidence never enters auction prices.
- The addon import page alone shows latest imported bags time/gold and independent latest bank
  time (or *bank unknown*), distinct item/occupied-slot counts and machine for each character,
  realm and faction. Missing bank never means empty; unknown slot item IDs keep the distinct-item
  total missing rather than zero. No holdings use in Today yet.


### ADDON-12 Event journal (STORY-033)

- Addon **0.8.0** writes account-wide file format **6** (STORY-040/041 extend 0.6.0 without a format bump): the existing scans, snapshots, sessions
  and `snapshot_sequence`, plus `journal`, `journal_diagnostics` and problem counters `journal_errors`. Formats 1–5 stay importable;
  scan records still use format 4. Capture follows Product direction → *Observing your own actions*.
  Only events and `hooksecurefunc` post-hooks record evidence; no economy actions, requests or timers.
  Normal journal capture is silent. Unavailable identity and the cap are problems reported in chat.
  Rejected events and missing/rejected hooks are reported as **one summary line per load** with their
  counts (the candidate list spans old and new clients, so some are always missing); `/bscan status`
  lists the names. Explicit status/clear commands retain their manual messages.
- Each raw entry records `entry_id`, event/hook name, family, positional arguments with explicit
  `n` (nil holes/trailing nil remain absent), character, realm, faction, Unix seconds + UTC text,
  nullable `GetTime()` session seconds, addon version, login time, and observed window states.
  Missing/unsupported values stay missing; an explicitly reported zero remains evidence, never a
  substitute for an unknown value. Table arguments are copied to depth 8; non-serializable values
  are omitted while retaining positions/count. No arguments are interpreted as transaction results.
  ID is length-prefixed character/realm + `:journal:` + Unix seconds + the **same persistent account
  sequence snapshots increment**. Each observation has its own ID, even within one second.
- At login/reload, money and carried-bag counts establish transient baselines. `PLAYER_MONEY`
  records nullable before/after integer copper. `BAG_UPDATE_DELAYED` records signed per-item carried
  count differences after settling, with bank/mailbox/merchant/auction house/trade skill/loot context;
  no unchanged-bag entry. Incomplete reads invalidate the baseline and record `baseline_missing`,
  never guessed zeros/deltas. A later complete read reestablishes it before differences resume.
  Window booleans are based on observed open/close events; absent means not observed, not closed.
- Mail open/inbox changes read `GetInboxNumItems`, every header and invoice, and available attachment
  info/links (an attachment is kept when any of its values is reported, so an item the client
  hasn't loaded yet keeps its ID and count without a name). Header/invoice tuples retain their full positional return values and counts. Capture
  never opens a message or takes anything. Equal inbox states are suppressed within the loaded
  session; reload resets this transient comparison. `MAIL_SEND_INFO_UPDATE` reads draft money/COD
  and attachments. The `SendMail` post-hook records recipient/subject/body arguments plus the
  **last observed draft**, explicitly marked as such: post-hook APIs may already have cleared it.
  It is evidence for later reconciliation, not a claim of successful delivery or complete attachments.
- **Vendor services (addon 0.10.0, decided 2026-10-08):** the merchant's sell-junk button and
  class trainers are family `vendor`: post-hooks `C_MerchantFrame.SellAllJunkItems` and
  `BuyTrainerService`, and events `TRAINER_SHOW`/`TRAINER_CLOSED` (window `trainer`). Before this,
  junk sales and trainer spending appeared only as bag and money changes. File format stays **6**.
- **Active owned auctions (STORY-040):** guarded `OWNED_AUCTIONS_UPDATED` reads
  `C_AuctionHouse.GetNumOwnedAuctions` and every 1-based `GetOwnedAuctionInfo` table;
  guarded `AUCTION_OWNED_LIST_UPDATE` reads `GetNumAuctionItems("owner")` and every 1-based
  `GetAuctionItemInfo("owner", index)` tuple, link and time-left value. Neither reader requests
  a list; `QueryOwnedAuctions`, `GetOwnerAuctionItems` and refresh/action APIs are never called.
  Each changed list adds one family `auction` entry with `owned_auctions`: API, counted raw count
  returns and indexed auctions with raw info. Modern tables retain all returned fields (including
  itemKey, ID, link, quantity, status, bid/buyout copper, bidder and time left); legacy tuples
  retain every position and `n`, plus separate link/time-left. No absent value becomes zero.
  Modern optional `HasFullOwnedAuctionResults` and `Enum.AuctionStatus.Sold` are saved as reported.
  Equal states are suppressed against the last successfully recorded list this loaded session;
  reload resets comparison. Shared ID/sequence/cap/clear rules apply unchanged.
  An observed zero-count list is evidence of empty; never observed means *active auctions unknown*.
  The import page alone shows each known character's latest observation UTC, reported count and
  count marked sold (modern saved enum; Classic legacy saleStatus position 16 equals 1).
  Legacy display uses the reported total when present, otherwise the reported batch count;
  every available batch row is read, with both count returns preserved. A partial batch cannot
  establish an empty full list. Missing statuses/read failures, a batch/total mismatch or explicitly
  incomplete modern results keep sold count unknown. Passive capture cannot fetch uncached pages.
  Characters are known from scoped imported snapshots/journal entries. Same-second lists use
  shared sequence to select the latest. This is raw client status, never an inferred sale or expiry.
  File format stays **6**, storage stays schema **11**, and shared non-scan import counts these
  entries under `auction`. Event/API support, completeness and arrival without opening the Auctions
  tab remain beta checks by 13 October; preserve recordings before 21 October.
- **Known recipes (STORY-041):** guarded `TRADE_SKILL_SHOW`/`TRADE_SKILL_UPDATE` and
  `CRAFT_SHOW`/`CRAFT_UPDATE` read the corresponding available `GetTradeSkill*`/`GetCraft*`
  window APIs. Each changed profession list adds one family `craft` journal entry with
  `known_recipes`; comparison is per character/profession against its last successfully recorded
  state this loaded session. It resets on reload and uses the shared identity/sequence/cap/clear.
  The comparison ignores craftable counts (the row field and its raw `info` position), which change
  with every craft or bag change; saved lists still carry them (decided 2026-10-07 at review, to keep
  one craft session from saving a full list per craft). An update is read only while that window
  (trade skill or craft, tracked separately) has been shown and not closed: a closed window reports
  a placeholder name (Classic: `UNKNOWN`). Opening a window whose list is unchanged still journals a
  plain window-open entry, as before 0.8.0.
  Preserve window profession name/rank/max, reported row count, every indexed header/recipe's raw
  info, name/type/difficulty, craftable count, expansion state, recipe/output links and reported
  link IDs, min/max made and every reagent's raw info/link/ID/count. Unavailable values stay missing.
  Preserve reported subclass/inventory filter states (including index 0, All) and makeable/skill-up
  filters and available text/level filters. Mark `possibly_incomplete` for active restrictions,
  collapsed/unknown header expansion,
  missing row type or unreadable row count. Never open windows, expand headers, change filters,
  train, learn or craft. Missing filter APIs cannot prove completeness; the flag describes observed
  restrictions, not a guarantee of a complete learned catalog. Capture is silent in normal play.
  A window never observed remains *known recipes unknown*. The import page alone shows the latest
  list UTC and listed non-header recipe count per profession, with the incompleteness flag;
  unreadable counts/rows remain unknown. Matching/learned-recipe interpretation is STORY-043.
  Journal was chosen instead of a new snapshot kind to reuse change-only lists and the bounded
  existing non-scan lifecycle. Addon is **0.8.0**; format remains **6**, schema remains **11**:
  existing raw JSON stores the added payloads without a migration. Forever event/API support,
  default hidden recipes, ID meaning and UI completeness remain beta checks by 13 October.
- **Spellcasts are crafting evidence only (decided 2026-10-07, product owner):** only
  `UNIT_SPELLCAST_SUCCEEDED` for unit `player` while a trade skill or craft window is observed open is
  recorded. Start, failed and interrupted casts, other units' casts and every spell cast without a
  crafting window open (combat, gathering, travel) are not registered or not recorded: they are not
  economy evidence and would fill the cap. Gathering shows up through loot events and bag changes.
  A craft that finishes after its window was closed is not recorded as a spellcast; its hook call and
  bag change still are. `CHAT_MSG_LOOT` requires argument 12 equal to the
  player's readable GUID; ambiguous/missing sender identity is omitted. Loot-window events are
  the player's own window.
- **Ordinary refresh events are counted, not journalled:** `MERCHANT_UPDATE` and
  `AUCTION_ITEM_LIST_UPDATE` carry no arguments and fire often (the last also
  during the addon's own scan), so they only add to `journal_diagnostics.fired_events`.
  Profession refresh events are also counted
  and now record changed lists under STORY-041; they do not append unchanged generic refresh entries.
  Container-use hooks log only while the merchant is observed open (possible selling), without
  asserting a sale. Other hooks log arguments regardless of success; events/deltas supply context.
- Every event registration is guarded independently. Hooks install only for existing functions,
  with guarded `hooksecurefunc`; missing/rejected names and installed names are saved in diagnostics,
  together with rejected events and fired counts. Unexpected observation errors are guarded,
  reported in chat and counted by name in `journal_errors`, without interrupting the game call. Later `ADDON_LOADED` retries unavailable hooks
  for lazily loaded UI modules, without rehooking installed functions. Candidate event/hook lists
  are discovery evidence, **not a promise of beta support**:
  - Events: `PLAYER_MONEY`, `BAG_UPDATE_DELAYED`, `MAIL_SHOW`, `MAIL_CLOSED`, `MAIL_INBOX_UPDATE`, `MAIL_SEND_INFO_UPDATE`, `MAIL_SEND_SUCCESS`, `MAIL_FAILED`, `AUCTION_HOUSE_SHOW`, `AUCTION_HOUSE_CLOSED`, `AUCTION_HOUSE_PURCHASE_COMPLETED`, `AUCTION_HOUSE_AUCTION_CREATED`, `AUCTION_HOUSE_AUCTION_CANCELED`, `AUCTION_HOUSE_SHOW_ERROR`, `OWNED_AUCTIONS_UPDATED`, `AUCTION_OWNED_LIST_UPDATE`, `AUCTION_ITEM_LIST_UPDATE`, `AUCTION_MULTISELL_START`, `AUCTION_MULTISELL_UPDATE`, `AUCTION_MULTISELL_FAILURE`, `MERCHANT_SHOW`, `MERCHANT_CLOSED`, `MERCHANT_UPDATE`, `TRADE_SKILL_SHOW`, `TRADE_SKILL_CLOSE`, `TRADE_SKILL_UPDATE`, `CRAFT_SHOW`, `CRAFT_CLOSE`, `CRAFT_UPDATE`, `UNIT_SPELLCAST_SUCCEEDED`, `CHAT_MSG_LOOT`, `LOOT_OPENED`, `LOOT_CLOSED`, `LOOT_SLOT_CLEARED`, `BANKFRAME_OPENED`, `BANKFRAME_CLOSED`.
  - Global hooks: `TakeInboxMoney`, `TakeInboxItem`, `AutoLootMailItem`, `SendMail`, `ReturnInboxItem`, `DeleteInboxItem`, `SetSendMailMoney`, `SetSendMailCOD`, `StartAuction`, `PostAuction`, `PlaceAuctionBid`, `CancelAuction`, `BuyMerchantItem`, `SellCursorItem`, `UseContainerItem`, `RepairAllItems`, `DoTradeSkill`, `DoCraft`.
  - Namespace hooks: `C_AuctionHouse.PostItem`, `C_AuctionHouse.PostCommodity`, `C_AuctionHouse.PlaceBid`, `C_AuctionHouse.CancelAuction`, `C_AuctionHouse.ConfirmCommoditiesPurchase`, `C_Container.UseContainerItem`, `C_TradeSkillUI.CraftRecipe`.
- **Size cap: 10,000 ordinary journal entries account-wide plus one overflow marker.** Further
  attempts add to `skipped` and report the cap once per loaded session when first reached. Existing
  entries are never silently evicted. Updating the single `JOURNAL_OVERFLOW` marker gives it a fresh
  shared sequence/ID; previously imported markers remain immutable historical evidence and cannot
  conflict with a later drop. Skipped counts in successive marker versions are cumulative, not additive.
  This is an entry-count bound, not a byte bound (mailboxes and argument strings vary in size).
  Normal-session bytes, counts, reload time and observed overflow behavior remain a beta measurement.
- **Clear:** reuse ADDON-11's account-wide login marker and prune: both clear commands/button keep
  entries at/after the current login and entries with missing timestamps; unknown login keeps all.
  Old overflow markers follow the same rule. Removing old entries makes space; current-session
  entries/overflow survive a clear and confirmed reload. Scan clear protections remain unchanged.
  OPS-03 latest-drop Fully imported is still required before cleanup.
- Snapshots and entries share one non-scan lifecycle: validation adapters, preview summaries, known
  hashes, house checks, stale-review checks, conflicts, transactional load, expected batch commits,
  Fully imported and guidance. Deduplication is source + record type + ID; same ID/different canonical
  content or market conflicts. Character realm/faction checks reuse ADDON-11; machine comes from
  configuration/drop name only. Bronze preserves exact original bytes beside scans. Entries never
  supply prices or holdings interpretations. CLI `--scan` still limits scans only.
- Per-file CLI/page preview groups journal counts by character/realm/faction and event family into
  new/duplicate/other-house counts. The import page alone shows scoped imported counts and latest
  entry time by character/family. Every record must match house/content for Fully imported; any
  file error or other-house record blocks cleanup. If no scans, snapshots or entries were newly
  saved, guidance remains **Nothing new: /reload first**, before any clear suggestion.


### ADDON-13 Brownstone panel (STORY-044)

Addon **0.9.0** adds a minimap button and `/bscan panel` toggle for a movable,
Escape-closeable convenience view of status and the manual play → Reload → import →
Clear → Reload routine. It captures nothing new. Reload, confirmed Clear, Start scan
and chat Status reuse the existing functions; maintenance/scan disabled states share
`setMaintenanceEnabled` and auction-house visibility. All existing guards and
ADDON-11/12 capture, cap and clear rules remain authoritative and unchanged.
The auction-house row and existing slash commands remain available.

Only `BrownstoneScanDB.ui` is new saved state: numeric `minimap_angle`, restored on
load. File format **6**, scan format **4** and record fields stay unchanged. Brownstone
preview, import and beta-report ignore UI state as evidence while preserving the
whole original file's bytes/provenance. No third-party Lua library or automatic action
is added. Panel usage and the pending play check are in `addon/README.md` → Panel.

### Money
- **MONEY-01:** store and calculate integer copper only. 1g = 100s = 10,000c.
- **MONEY-02:** display gold. Tables show decimal gold with four places, so one copper is exact and columns sort numerically. Headline figures and prose use `4g 50s 97c`.

### Crafting
- **CRAFT-01 Versioned catalogs:** each catalog declares `game_version`, `rules_version` (the game build's rules, distinct from Forever server types), `catalog_version`, status, and provenance URLs for every item and recipe. Classic and Forever catalogs never share rules implicitly. A catalog used for decisions records verification evidence for every recipe quantity and vendor price. Changing a verified value requires new evidence and a `catalog_version` bump.
- **CRAFT-02 Expansion:** intermediates expand without cycles or double counting. Unsupported cases (cycles, fractional units) are rejected, not approximated.
- **CRAFT-03 Routes:** each input uses its cheapest valid route: buy, craft or vendor. Missing or zero prices are never free. Equal costs resolve deterministically.
- **CRAFT-04 Price bases:**
  - **Cautious** is the default for ranking and labels. It buys inputs at the higher, and sells output at the lower, of minimum buyout and market value. When only one value is positive, that value is used.
  - **Listed** uses minimum buyout only.
  - Every board row shows profit under both bases.
- **CRAFT-05 Action Board:** ranks finished outputs of every catalog compatible with the selected source (same game version and `rules_version`) on one board. Each recipe is costed within its own catalog; routes never cross catalogs.
  - Profession is shown and can be filtered without renumbering the combined ranks. Catalog identity plus recipe ID selects a row and its own recipe details; catalogs making the same item retain separate rows.
  - Shows craft cost, sale price, net revenue after the auction cut, profit and margin, where margin = profit / net revenue.
  - Labels, in precedence order:
    1. **unsupported recipe:** calculation error; the message is shown.
    2. **missing prices**
    3. **stale data**
    4. **potential craft:** profit > 0.
    5. **negative margin:** profit ≤ 0.
  - Sorts by profit or by margin, descending, then the other metric, then recipe ID, then catalog identity for duplicate-ID ties. Incomplete rows sort last.
  - Policy version is shown.
- **CRAFT-06 Explanation:** for a selected recipe, show:
  - direct inputs with route, unit and total cost, observed prices and source
  - the shopping list for the chosen routes
  - the all-craft materials
  - break-even sale price
  - assumptions, provenance and freshness
- **CRAFT-07 Rounding:** net revenue rounds down to the copper; break-even rounds up. Quantities are per recipe execution.
- **CRAFT-08 Generated catalogs (STORY-004):** a catalog is generated by `python -m brownstone recipes`, or the app's **Recipe catalogs** page through the same code, from one saved page plus a tracked selection file (`config/recipe-selections/<catalog>.toml`), never edited by hand.
  - **One per game version and profession:** named `<prefix>-<profession>`, with prefix `classic-era` or `forever` (for example `forever-leatherworking`). A catalog exists when its selection file does; nothing finds catalogs by file name pattern.
  - **Same version only:** the page's game version and profession must match the selection's. Values never come from another version's page.
  - **No seasonal spells:** Wowhead's Classic pages also list seasonal realms' spells (`seasonId`, 2 = Season of Discovery): 57 of 287 Tailoring and 48 of 204 Enchanting on the 2026-10-04 pages. They are never offered, never added as intermediates, and a selection naming one is refused.
  - **Selection:** lists finished recipes. A reagent made by exactly one usable recipe on the page is added as an intermediate.
  - **One rule for every profession:** a recipe is usable only if it makes a fixed, known quantity (Wowhead lists some transmutes and oils as making 0, meaning unknown) and isn't seasonal. An item that several usable recipes make is always bought, never crafted, and those recipes can't be selected. So a catalog never chooses between recipes, and the app never asks. It changes nothing on the saved Tailoring and Enchanting pages; it exists for Alchemy's transmutes.
  - **Evidence:** every recipe records its Wowhead spell URL, the page URL, the date the page was saved and the page's SHA-256. The saved page is archived byte-for-byte under `data/recipe-sources/` with a manifest.
  - **Vendor materials need evidence:** Wowhead gives a buy price to items no vendor sells (Felcloth, elemental essences, raid gear), so a buy price never makes an item a vendor material. The selection marks vendor items, with evidence or `vendor_verified = false`. The page's buy price is the vendor price; it replaces the sell price × 4 estimate (they differ for Coarse Thread: 10c, not 8c).
  - **Unconfirmed values are marked:** `output_quantity_verified = false` and `vendor_verified = false` stay until confirmed in game, and the recipe view shows them. Forever output counts are unconfirmed until counted in game. Wowhead's list data says 1 for every Tailoring recipe; the "(2)" in its spell tooltips is the effect number (effect 1 consumes the reagents, effect 2 creates the item), not a quantity (checked 2026-10-06), so nothing suggests a yield above 1. A Forever catalog added in the app still marks every yield unconfirmed, and any vendor item marked there gets `vendor_verified = false`.
  - **Availability:** a recipe or item may be marked `availability = "post-launch"` with a note. It is display-only; the board still prices it.
  - **Staying current:** after a game update, re-save the page and regenerate. The command lists recipe and vendor price changes for review; a changed value bumps `catalog_version`. In the app, **Save catalog** bumps the minor part of the selection's `catalog_version` (0.1 → 0.2) whenever the catalog file would change, unless the selection's version was already changed by hand (then it keeps that version), and does nothing when the page reproduces it exactly.
  - **Refresh due:** the app flags a catalog when an enabled market of the same game version uses another `rules_version`, or when its page is older than the selection's `refresh_after_days` (default 30).
  - **Edited, never re-dumped:** the app edits an existing selection file line by line, keeping its comments, and refuses any edit that doesn't read back as chosen. Removing recipes drops notes on items nothing uses any more; the preview lists each one.
  - **Must load:** a catalog the board's loader would reject (for example two recipes making one item) is refused before anything is written.
- **CRAFT-09 Market depth (STORY-019):** the board shows auction listing and unit counts for each output and direct input; the recipe input table shows the same counts. Counts include listings without a buyout and describe the exact complete, priced scan used for the prices, scoped by source and full market identity. An absent item is labeled **Not listed** with zero observed listings and units. TSM or a snapshot without a matching priced addon scan shows **Unavailable**, with no counts. Depth is display-only: it changes no cost, action label, ranking or policy version, and is not vendor stock or a claim about demand.

### Today (today_version 1, STORY-025, implemented pending review 2026-10-06)

- **Opening and settings:** every source opens on Today; subsequent navigation is remembered per
  source during the session. Each source has its own ignored preferences file,
  `data_dir/today-settings.<source_id>.local.json`, because the data directory is shared and each
  source's funds are its own. It is written atomically (through a `.tmp` sibling, also ignored) only on
  Save; the pattern is also ignored for custom data directories. Invalid or unreadable settings show a
  warning and defaults, never silently replace the file. A rejected or failed Save shows an error and the
  tables stay visible, still sized by the last saved settings. Gold starts at **0c**, because funds cannot be inferred. Explicit integer `g/s/c`
  text is required (case-insensitive, optional spaces, each unit at most once; properly grouped thousands
  commas accepted). Bare numbers get a units hint. The parser round-trips signed money display; settings
  reject negative amounts. Minimum mode starts **scaled**, **1%** (**100 basis points**) with a **10s**
  floor. Fixed mode uses only the fixed minimum. Scaled mode is `max(fixed, ceil(gold * basis_points / 10000))`.
  Percentage is adjustable from **0 to 100%** in hundredths; most crafts per item starts at **5**, adjustable
  from **1 to 1,000** (bounded to keep interactive calculations predictable). All amounts are integer copper.
- **Routes and batch costs:** reuse compatible Action Board catalog-local routes under the cautious
  basis (CRAFT-03/04/05); no cross-profession routing. Routes are selected once from aggregate evidence,
  then held fixed while sizing. Today changes auction purchase costs to the exact listing ladder, ordered
  by positive unit-buyout-ceiling, then quantity and buyout for deterministic ties. **Whole listings** are
  bought: include the entire buyout when the final stack exceeds required units. Show required and purchased
  units; surplus has **no revenue credit**, and is not reused by another batch in v1. Vendor routes use
  their catalog purchase prices without a supply limit. Unsupported expansion remains isolated and hidden
  with its reason. Cautious output revenue and auction-cut rounding remain per CRAFT-07, per execution.
- **One funded plan:** first rank the board and prepare prefix ladders, then quote batches by binary search,
  without walking listings for each recipe or expanding stacks. For each candidate, batch sizes are
  bounded by priced input supply, remaining gold and the per-item craft cap; within that bound the size with
  the greatest batch profit is chosen (the smaller on ties), because deeper listings can make extra crafts
  lose money. Profit can only peak at the bound or just before an input needs another listing, so only
  those sizes are quoted. Select the greatest **total batch profit**, reserve its complete input listings and cost, then re-size/rank remaining candidates.
  Repeat up to **10 craft rows**. Select each output only once, choosing the catalog/recipe with
  the greatest feasible batch profit; hide other routes as **output already planned**, so the per-item
  cap cannot be multiplied by duplicate catalogs. Display the selected rows by descending batch
  profit, then recipe ID, then catalog identity; there is no score. This greedy plan makes the combined shopping list payable and
  avoids double-use of cheap listings; it does not claim globally optimal portfolio profit. The limiting factor is
  **more crafts lower profit** when a smaller size beats the bound; otherwise ties prefer cap, then input
  supply, then gold. Profit per craft displays `floor(batch_profit / batch_size)`;
  exact batch profit remains authoritative. Each row identifies its recipe/catalog, rules and provenance,
  quantities, costs, revenue, competition, limits, availability and unconfirmed yield/vendor evidence.
- **Hidden and capped:** hide invalid recipes (unsupported recipe before missing prices), no batch with
  priced supply (**insufficient listed materials**), batches where one craft exceeds remaining funds
  (**one craft exceeds funds**), and nonpositive profit or profit strictly below the minimum (**below
  minimum gain**). Reasons are mutually exclusive in that order and describe the remaining plan budget.
  Count remaining feasible outputs (each output once, whatever its routes) outside the 10-row selection
  separately from hidden rows. Every list
  caps at **10 rows**, with a count of the rest; shopping totals include materials beyond its display cap.
- **Buy:** merge the selected batches' purchases by base item and buy/vendor route, summing required units,
  purchased units and full buyouts, and taking the highest paid unit-buyout-ceiling. Sort by cost descending,
  item ID, route. *Cheap now* is informational only: for auction purchases, full cost divided by purchased
  units is **strictly below** that exact scan identity's quantity-weighted **25th percentile** (ADDON-10).
  Vendor routes and missing percentile evidence never receive the flag.
- **Below vendor price:** a separate, independent aside, not an addition to the craft budget. Only base
  or legacy identities supported by the v1 catalog evidence reads are considered; variants/unresolved
  identities are excluded rather than pooled. Use the selected scan's positive **vendor sell** reference,
  never a catalog vendor purchase price. Include complete listings with unit-buyout-ceiling **strictly
  below** that reference. Gain is vendor price × purchased units minus actual buyouts, positive and **at
  least the minimum gain**. Sort gain descending then item ID. Nothing implies a completed sale.
- **Sell:** one row per selected output, with its chosen catalog/recipe identity.
  Show lowest positive competing unit price, all listings/units (including no-buyout listings), largest
  stack, and **1c** below the lowest as undercut price. A lowest price of **1c** has no valid positive
  undercut and no undercut-profit estimate. Profit at undercut uses the selected batch costs and auction
  cut; it can be negative. **Thin** means **fewer than 3 listings**, or the largest stack holds **at least
  half** of listed units. No claim about demand, sales speed, deposits, or actual sales is made.
- **Evidence and honesty:** source, market, snapshot/scan, evidence time and time basis appear once
  on the page rather than on every row. A single rules/provenance caption names Today version, cautious
  output price, auction cut and that evidence; the page context and DATA-05 freshness captions remain.
  Every table keeps a visible State column, including **stale — inspect only** for stale/future evidence.
  DATA-05's configured freshness limit applies unchanged: stale/future rows
  remain inspectable but are **never actionable**, and the page shows a banner. No missing/zero price
  becomes a recommendation. TSM has **not available for this source** for individual listings, thin,
  undercuts, cheap-now and below-vendor evidence; so does an addon snapshot without eligible scan
  metrics (STORY-030 keeps this notice tied to missing listing evidence, not to the provider). TSM batches use cautious aggregate purchase estimates,
  gold and cap only. Base/null-legacy compatibility follows ADDON-08; all storage reads retain full
  source/market/snapshot identity and catalog compatibility retains `rules_version`.


### Interface
- **UI-01:** browsing saved data never triggers a download or import. Only **Refresh from TSM** (TSM sources) or **Import addon scan** after the read-only preview (addon sources; ADDON-06) collects, and only for the selected source. Disabled sources (`enabled = false`) are hidden. The sidebar lists experiences WoW Forever first, then Classic Era, then Retail, whatever order `market.toml` uses, so Forever opens by default. The shared sidebar experience choice resolves its source and market together when there is one enabled source for that experience. If there are several, an explicit sidebar source choice is required; sources are never merged. Every view follows the selection, including Recipe catalogs. Each page names the selected experience, source and market under its title. The sidebar contains navigation and collection actions; source ID, label, market ID, feed type and the `market.toml` hint stay in a collapsed **Source details** expander (STORY-030).
  - **Today layout (STORY-030):** one visible settings summary (gold available, minimum batch gain,
    most crafts per item) and the existing Save-only form in a **Today settings** expander, automatically
    expanded when gold is 0c or the settings file is unreadable. An expander keeps the existing form in
    ordinary page flow with fewer controls than a popover. **Craft**, **Buy**, **Sell** and **Below vendor**
    are tabs, each keeping its remaining-row count; Craft keeps hidden reasons and Buy the whole-list
    total. Decision columns come first, followed by the always-visible State. A default-off **Show evidence
    columns** toggle per tab reveals the remaining columns in the same table, avoiding duplicate tables.
    Shared provenance stays on the page; missing values stay blank and freshness warnings stay visible.
  - **Crafting layout (STORY-030):** compatible catalog captions stay in collapsed **Catalogs on this
    board (N)**; coverage, depth meaning, margin and label explanations in collapsed **How to read this
    board**. Unsupported rows keep their board labels and collect into one collapsed **N recipes could
    not be evaluated** table (output, profession, catalog, reason). One board provenance caption remains
    visible, as do DATA-05 freshness captions and warnings. Recipe details retain their existing behavior.
- **UI-02:** Browse market finds items regardless of price or discount. Categories are not inferred from names or commodity status.
- **UI-03:** the discount screen (Opportunities) explains when a source cannot support it, for example Classic historical values being zero. Its spread is integer copper: the reference price after the auction cut rounds down, as in CRAFT-07. Search filters the ranked list without renumbering it.
- **UI-04:** Crafting has no catalog selector. Incompatible catalogs for the selected game version remain inspectable without pricing; their catalog and source `rules_version` mismatch is explained. If none is compatible, the view explains this and offers navigation to Recipe catalogs. Recipe catalogs shows the sidebar experience's catalogs and has no game-version switch of its own (decided 2026-10-04); an experience without catalogs (Retail) says so.
- **UI-06 Scan changes:** compare two distinct complete, non-partial, priced addon scans within the sidebar's selected source and full market identity (DATA-03/DATA-08). Choices come from scan IDs, never import manifests, newest finish first; the newest two are the default. Display both finish times in UTC, their gap and freshness (DATA-05); only the later scan carries the stale warning, since the earlier one is deliberately historical. Show per-unit minimum buyout and market value, listing counts and units for each scan, and later-minus-earlier changes. An item is listed if any listing exists, including one without a buyout. Absent items show **not listed**, with blank changes; listed items without usable prices show **no buyout** or **no market value**, never free. New and vanished items have separate lists. Shared items are changed if any price or supply metric differs. The catalog filter uses only item IDs from catalogs compatible with the selected source (UI-04). A non-addon source or fewer than two eligible scans explains why no comparison is available.
- **UI-05:** the launcher reuses a running server only if its code is current. It restarts its own outdated server and never stops a server it did not start.

### Operations
- **OPS-01:** tests are offline and run in CI on macOS and Windows from the lock file, including the UI test, alongside Ruff and mypy. No market data is stored in Git.
- **OPS-02:** database schema changes go through numbered, idempotent migrations.
  - A database newer than the code is refused, never modified.
  - Before migrating, the existing file is copied to `data/brownstone.v<N>.backup.duckdb`.
  - The app upgrades at startup and the pipeline before writing, so read-only views never see an outdated schema.
  - Manifests written before a change are read through an upgrade adapter; they are never edited.
- **OPS-03 One home machine** (decided 2026-10-05): Brownstone and its `data/` folder run on the Mac. The Windows desktop didn't scan at first, to keep one scan file and one writer; Windows scans were accepted on 2026-10-07 (below). Windows stays a supported, CI-tested platform (OPS-01).
  - **Revisited 2026-10-06 (product owner):** with character data (STORY-032/033), characters played on Windows produce their own logs. Direction: Brownstone and `data/` stay on the Mac as the only database writer; each machine's addon file is a separate input, tagged by machine, copied write-once into a drop folder the Mac imports from. The contract is STORY-037; the Mac imports its own file and immutable Windows drops through the same source and full market scope.
  - **Drop folder decided 2026-10-06 (product owner):** Google Drive, through Google Drive for desktop on both machines (free tier; the account already exists). It holds only copies of addon files, never `data/`. Brownstone reads it as an ordinary local folder; files can be cleaned out after import because bronze keeps the exact bytes (DATA-01).
  - **Windows scans accepted (product owner, 2026-10-07):** auction scans taken on the Windows PC are imported like the Mac's, into the same source and market when the house evidence matches, tagged with their machine. Scan IDs and per-scan hashes still deduplicate (ADDON-04). The Windows PC has the repository cloned, so its drop script lives in the repository and is updated with `git pull`. Brownstone and `data/` stay on the Mac.
  - **Second-machine input rules (STORY-037):** each addon source requires a configured `machine` for its local `scan_path`; labels contain only lowercase ASCII letters, digits and hyphens. Machine is provenance only, never a market key, and is never inferred from file contents. Historical scans retain missing machine values. Optional `drop_folder` belongs only in untracked `config/market.local.toml`; it must not contain `data_dir`. Without it, the single-file import/review flow is unchanged.
  - **Drops:** final names are `<machine>-<UTC YYYYMMDDTHHMMSSZ>-BrownstoneScan.lua`, for example `windows-pc-20261007T004900Z-BrownstoneScan.lua`. The shared naming contract and examples live in `brownstone/drop_contract.json`. Partial, conflict and unrelated names are ignored with reasons; unreadable, truncated and conflicting inputs are reported independently. Brownstone only reads this folder, never writes, renames or deletes there. Each imported file has its own collection manifest with exact archived bytes, machine and original name; identical byte blobs may be reused. House checks, scan-ID/hash conflicts, partial pricing and stale reviews remain per file.
  - **Windows routine:** the manually run PowerShell script and `.cmd` wrapper use an ignored local settings file, refuse while WoW runs or the source is missing, copy through a temporary name, verify SHA-256 and publish without overwriting. Identical bytes to that machine's latest final drop produce “Nothing new”. The SavedVariables file is only read. No installation, scheduler or collection automation is introduced.
  - **Cleanup:** every file reports whether all its scans and character snapshots are imported; another-house record or an unreadable/conflicting file prevents that claim. Each machine's latest final drop is shown even if unreadable. The user deletes drops by hand after full import. `/bscan clear` on Windows next session is safe only when that machine's latest drop is fully imported and the user has not played there since it was made. Importing an older drop cannot authorize clearing a later session.
  - Local storage is enough: about 5 MB per beta scan all-in (up to about 10 MB expected for a busier live house), so roughly 5–35 GB a year at 3–10 scans a day. Cloud storage and a home server aren't needed. `data/` must not sit in a live-synced folder such as iCloud Drive, because DuckDB has a single writer.
  - Backups are deferred (product owner, 2026-10-06): STORY-016 is no longer due by 21 October and has no date. Until it is done, migrations still copy the database first (OPS-02), but nothing else protects the raw archive.


## Not modeled (do not imply otherwise)

Demand, sale likelihood, deposits, vendor stock, reputation discounts, recipe quality/rank, reagent alternatives and multi-yield recipes. Today v1 models listing costs and bounded batches under its rules above; the Action Board's depth remains display-only under CRAFT-09. The importer rejects variable yields, and an intermediate yielding more than 1 can fail with "Fractional unit costs". Every current catalog recipe yields 1.

## Open decisions

- Classic regional demand integration (Classic demand context, under Later in `backlog.md`).
- Which third-party Forever aggregates, if any, offer a usable export or API (STORY-011a).
- Where backups go and how often (STORY-016; the timing is decided under OPS-03), historical retention and scheduling.
- The movement ledger's contract: which recorded events become which movements, and how lots and cost basis are assigned (STORY-034).
- Whether to model the Black Market vendor and its prices, once confirmed in game (STORY-036).
- Whether to add AI narration, which model runs it and what data may leave this machine (*AI narration*, Later in `backlog.md`).
- Whether to remove the Retail regression sources. SPIKE-008 found Forever listings are per-stack, not Retail-style per-unit commodities, so the Retail commodity feed is not a close test of Forever's model.

None is approved by default.
