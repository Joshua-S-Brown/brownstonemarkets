-- Brownstone Scan: read-only auction house scan (STORY-023).
--
-- A scan starts only from the "Brownstone Scan" button or "/bscan start" while
-- the auction house window is open. The addon only reads listings. It never
-- bids, buys, posts or cancels, and never scans on a timer or on its own.
--
-- Output: BrownstoneScanDB (SavedVariables), written by the game on /reload or
-- logout. See addon/README.md for the format and the measurement checklist.

local ADDON = "BrownstoneScan"
local SCHEMA_VERSION = 3
local ADDON_VERSION = "0.3.0"
-- Each listing is saved as one short string in this field order (schema 3), with names stored
-- once per scan, together with sellers, level types, links and item references. Brownstone does all pricing; the addon only records what the client reports.
local LISTING_FORMAT = "item_id:quantity:buyout:min_bid:bid:flags:name_index:seller_index:time_left:quality:level:level_type_index:link_index"
local FLAG_COMPLETE_INFO, FLAG_COMMODITY = 1, 2

local CHUNK = 2000            -- listings read per frame, to avoid freezing the client
local START_TIMEOUT = 30      -- seconds to wait for the server to answer the request

local frame = CreateFrame("Frame")
local button
local ensureButton
local scan  -- the scan in progress, or nil
-- Scans finished since login or the last /reload. They are only in memory until the game writes the
-- file on /reload or logout, so /bscan clear refuses to delete them (Brownstone hasn't seen them yet).
local unsavedScans = 0

local function say(msg)
    print("|cff66ccffBrownstoneScan:|r " .. msg)
end

local function utc(t)
    return date("!%Y-%m-%dT%H:%M:%SZ", t)
end

---------------------------------------------------------------------------
-- Which auction API does this client have?
---------------------------------------------------------------------------

-- Returns "modern", "legacy" or nil. Modern is C_AuctionHouse.ReplicateItems
-- (full snapshot, including Retail-style commodities). Legacy is the Classic
-- QueryAuctionItems "getAll" scan.
local function detectApi()
    if C_AuctionHouse and C_AuctionHouse.ReplicateItems
        and C_AuctionHouse.GetNumReplicateItems
        and C_AuctionHouse.GetReplicateItemInfo then
        return "modern"
    end
    if QueryAuctionItems and GetNumAuctionItems and GetAuctionItemInfo then
        return "legacy"
    end
    return nil
end

local function ahIsOpen()
    if AuctionHouseFrame and AuctionHouseFrame:IsShown() then return true end
    if AuctionFrame and AuctionFrame:IsShown() then return true end
    return false
end

---------------------------------------------------------------------------
-- Metadata about the client and the auction house
---------------------------------------------------------------------------

local function safe(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b = pcall(fn, ...)
    if ok then return a, b end
    return nil
end

local function collectContext()
    local version, build, buildDate, interface = GetBuildInfo()
    local regionId = safe(GetCurrentRegion)
    local regionName = safe(GetCurrentRegionName)
    local playerFaction, playerFactionLocal = UnitFactionGroup("player")

    -- Neutral detection. Nothing documented is guaranteed on Forever, so try
    -- the modern call if present and record how the answer was obtained.
    local houseFaction, neutral, neutralSource
    if C_AuctionHouse and C_AuctionHouse.GetAuctionHouseFaction then
        houseFaction = safe(C_AuctionHouse.GetAuctionHouseFaction)
        if houseFaction ~= nil then
            neutral = (tostring(houseFaction):lower() == "neutral")
            neutralSource = "C_AuctionHouse.GetAuctionHouseFaction"
        end
    end
    if neutral == nil then
        -- Not exposed by any call we know of. Leave it undetermined rather
        -- than guessing; the NPC name and zone below identify the house.
        neutralSource = "undetermined"
    end

    return {
        client = {
            version = version,
            build = build,
            build_date = buildDate,
            interface = interface,
            locale = GetLocale(),
            project_id = WOW_PROJECT_ID,
        },
        region = { id = regionId, name = regionName },
        realm = {
            name = GetRealmName(),
            normalized = safe(GetNormalizedRealmName),
        },
        faction = {
            player = playerFaction,
            house = houseFaction,
            neutral = neutral,
            neutral_source = neutralSource,
        },
        house = {
            npc_name = UnitName("npc"),
            npc_guid = UnitGUID("npc"),
            zone = GetZoneText(),
            subzone = GetSubZoneText(),
        },
    }
end

---------------------------------------------------------------------------
-- Reading one listing
---------------------------------------------------------------------------

-- Commodity status per item ID for the scan in progress, so the client is asked once per item, not
-- once per listing. Enum.ItemCommodityStatus: 0 unknown, 1 item, 2 commodity. The Forever beta reports none.
local commodityCache = {}

local function isCommodity(itemID)
    if not C_AuctionHouse.GetItemCommodityStatus then return false end
    local cached = commodityCache[itemID]
    if cached == nil then
        cached = safe(C_AuctionHouse.GetItemCommodityStatus, itemID) == 2
        commodityCache[itemID] = cached
    end
    return cached
end

-- Both auction APIs expose the same 18-value tuple. Keep the level type: level can mean
-- required level or something else. Empty seller/link values remain missing, never guessed.
local function listingInfo(name, texture, count, quality, usable, level, levelType,
    minBid, minIncrement, buyout, bidAmount, highBidder, bidderFullName, owner, ownerFullName,
    saleStatus, itemID, hasAllInfo)
    if not itemID then return nil end
    return { name = name, item_id = itemID, quantity = count, quality = quality,
        level = level, level_type = levelType, min_bid = minBid, buyout = buyout, bid = bidAmount,
        seller = (ownerFullName and ownerFullName ~= "") and ownerFullName or owner,
        complete_info = hasAllInfo }
end

-- Modern indexes are 0-based; legacy indexes are 1-based. Optional readers are guarded.
local function readModern(index)
    local r = listingInfo(C_AuctionHouse.GetReplicateItemInfo(index))
    if not r then return nil end
    r.commodity = isCommodity(r.item_id)
    r.time_left = safe(C_AuctionHouse.GetReplicateItemTimeLeft, index)
    r.item_link = safe(C_AuctionHouse.GetReplicateItemLink, index)
    return r
end

local function readLegacy(index)
    local r = listingInfo(GetAuctionItemInfo("list", index))
    if not r then return nil end
    r.time_left = safe(GetAuctionItemTimeLeft, "list", index)
    r.item_link = safe(GetAuctionItemLink, "list", index)
    return r
end

-- Indexed text is stored exactly as returned (including full links), once per scan.
local function textIndex(s, tableName, value)
    if not value or value == "" then return 0 end
    local indexes = s.textIndexes[tableName]
    local index = indexes[value]
    if not index then
        index = #s[tableName] + 1
        s[tableName][index] = value
        indexes[value] = index
    end
    return index
end

-- One item-reference observation/lookup attempt per ID per scan. No retries, waits or
-- requests for uncached data: missing values are saved as missing in this observation.
local function recordItem(s, itemID)
    if s.itemSeen[itemID] then return end
    s.itemSeen[itemID] = true
    local r = { item_id = itemID }
    local instant = (C_Item and C_Item.GetItemInfoInstant) or GetItemInfoInstant
    if type(instant) == "function" then
        local ok, id, itemType, subtype, equip, icon, classID, subclassID = pcall(instant, itemID)
        if ok and id then r.class_id, r.subclass_id = classID, subclassID end
    end
    local info = (C_Item and C_Item.GetItemInfo) or GetItemInfo
    if type(info) == "function" then
        local ok, name, link, quality, itemLevel, required, itemType, subtype, stack, equip, icon, sell =
            pcall(info, itemID)
        if ok and name then
            r.item_level, r.max_stack_size, r.vendor_sell_copper = itemLevel, stack, sell
        end
    end
    s.items[#s.items + 1] = r
end

local function optionalNumber(value)
    return value ~= nil and tostring(value) or ""
end

local function addListing(s, r)
    local flags = (r.complete_info and FLAG_COMPLETE_INFO or 0) + (r.commodity and FLAG_COMMODITY or 0)
    s.listings[#s.listings + 1] = table.concat({
        tostring(r.item_id), tostring(r.quantity or 0), tostring(r.buyout or 0),
        tostring(r.min_bid or 0), tostring(r.bid or 0), tostring(flags),
        tostring(textIndex(s, "names", r.name)), tostring(textIndex(s, "sellers", r.seller)),
        optionalNumber(r.time_left), optionalNumber(r.quality), optionalNumber(r.level),
        tostring(textIndex(s, "level_types", r.level_type)), tostring(textIndex(s, "links", r.item_link)),
    }, ":")
    recordItem(s, r.item_id)
end

---------------------------------------------------------------------------
-- Scan life cycle
---------------------------------------------------------------------------

local function finish(status, reason)
    local s = scan
    if not s then return end
    scan = nil
    frame:SetScript("OnUpdate", nil)
    s.finished_at = time()
    s.finished_at_utc = utc(s.finished_at)
    s.duration_seconds = GetTime() - s.clock_start
    s.clock_start = nil
    s.phase, s.waited, s.cursor, s.total, s.skipped, s.textIndexes, s.itemSeen = nil, nil, nil, nil, nil, nil, nil
    commodityCache = {}
    s.status = status
    s.stop_reason = reason
    s.listing_count = #s.listings
    if button then button:SetText("Brownstone Scan") button:Enable() end
    if s.listing_count == 0 then
        -- Throttled, not ready, closed too early: nothing to import, so don't
        -- leave an empty scan in the file. The reason is printed instead.
        say(("%s, nothing saved%s."):format(status, reason and (" (" .. reason .. ")") or ""))
        return
    end
    BrownstoneScanDB.scans[#BrownstoneScanDB.scans + 1] = s
    unsavedScans = unsavedScans + 1
    say(("%s: %d of %d listings in %.1fs%s. Type /reload to write the file."):format(
        status, s.listing_count, s.reported_count or 0, s.duration_seconds, reason and (" (" .. reason .. ")") or ""))
end

local function readChunks()
    local s = scan
    if not s then return end
    local read, limit = 0, CHUNK
    while s.cursor < s.total and read < limit do
        local index = s.cursor
        local r
        if s.api == "modern" then
            r = readModern(index)
        else
            r = readLegacy(index + 1)
        end
        if r then
            addListing(s, r)
        else
            s.skipped = (s.skipped or 0) + 1
        end
        s.cursor = s.cursor + 1
        read = read + 1
    end
    if button then button:SetText(("Scanning %d/%d"):format(s.cursor, s.total)) end
    if s.cursor >= s.total then
        if (s.skipped or 0) > 0 then
            s.errors[#s.errors + 1] = ("%d listings had no item ID and were skipped"):format(s.skipped)
        end
        finish("completed")
    end
end

local function beginReading()
    local s = scan
    if not s or s.phase == "reading" then return end
    s.phase = "reading"
    s.cursor = 0
    s.listings = {}
    s.names = {}
    s.sellers, s.level_types, s.links, s.items = {}, {}, {}, {}
    s.textIndexes = { names = {}, sellers = {}, level_types = {}, links = {} }
    s.itemSeen = {}
    commodityCache = {}
    if s.api == "modern" then
        s.total = C_AuctionHouse.GetNumReplicateItems() or 0
    else
        local shown, total = GetNumAuctionItems("list")
        s.total = shown or 0
        s.total_on_server = total
    end
    s.reported_count = s.total
    if s.total == 0 then
        finish("stopped", "server reported zero listings")
        return
    end
    frame:SetScript("OnUpdate", readChunks)
end

local function onTimeout(_, elapsed)
    local s = scan
    if not s or s.phase ~= "waiting" then return end
    s.waited = s.waited + elapsed
    if s.waited >= START_TIMEOUT then
        frame:SetScript("OnUpdate", nil)
        local why = s.api == "modern"
            and "no reply from the auction house; ReplicateItems is throttled to once per 15 minutes per account, so wait and try again"
            or "no reply from the auction house; a full legacy scan is limited to once per 15 minutes"
        s.errors[#s.errors + 1] = why
        finish("stopped", "timeout")
        say(why)
    end
end

local function startScan()
    if scan then say("A scan is already running.") return end
    if not ahIsOpen() then say("Open the auction house window first.") return end
    ensureButton()
    local api = detectApi()
    if not api then
        say("No auction API found (neither C_AuctionHouse.ReplicateItems nor QueryAuctionItems). Run /dump C_AuctionHouse and send me the output.")
        return
    end

    local ctx = collectContext()
    local now = time()
    scan = {
        schema_version = SCHEMA_VERSION,
        scan_id = ("%s-%06x"):format(date("!%Y%m%dT%H%M%SZ", now), math.random(0, 0xFFFFFF)),
        started_at = now,
        started_at_utc = utc(now),
        clock_start = GetTime(),
        api = api,
        label = BrownstoneScanDB.label,
        client = ctx.client,
        region = ctx.region,
        realm = ctx.realm,
        faction = ctx.faction,
        house = ctx.house,
        listing_format = LISTING_FORMAT,
        names = {},
        listings = {},
        errors = {},
        phase = "waiting",
        waited = 0,
    }

    if api == "modern" then
        if C_AuctionHouse.IsThrottledMessageSystemReady and not C_AuctionHouse.IsThrottledMessageSystemReady() then
            scan.errors[#scan.errors + 1] = "auction house message system not ready"
            finish("stopped", "not ready")
            say("The auction house is still busy with another request. Wait a moment and try again.")
            return
        end
        local ok, err = pcall(C_AuctionHouse.ReplicateItems)
        if not ok then
            scan.errors[#scan.errors + 1] = "ReplicateItems failed: " .. tostring(err)
            finish("stopped", "error")
            say("ReplicateItems failed: " .. tostring(err))
            return
        end
    else
        local canQuery, canGetAll = CanSendAuctionQuery()
        if not (canQuery and canGetAll) then
            scan.errors[#scan.errors + 1] = "client reports a full scan is not allowed right now"
            finish("stopped", "throttled")
            say("The client says a full scan is not allowed yet (limited to once per 15 minutes). Try later.")
            return
        end
        local ok, err = pcall(QueryAuctionItems, "", nil, nil, 0, false, 0, true, false, nil)
        if not ok then
            scan.errors[#scan.errors + 1] = "QueryAuctionItems failed: " .. tostring(err)
            finish("stopped", "error")
            say("QueryAuctionItems failed: " .. tostring(err))
            return
        end
    end

    if button then button:Disable() button:SetText("Waiting...") end
    frame:SetScript("OnUpdate", onTimeout)
    say(("Scan started using the %s auction API."):format(api))
end

local function stopScan(status, reason)
    if not scan then return false end
    scan.errors[#scan.errors + 1] = reason
    finish(status or "stopped", reason)
    return true
end

---------------------------------------------------------------------------
-- Events
---------------------------------------------------------------------------

-- RegisterEvent throws on an event this client doesn't know (the legacy
-- AUCTION_ITEM_LIST_UPDATE is missing on Forever), so register one at a time
-- and record which ones the client rejected.
local missingEvents = {}
for _, event in ipairs({
    "ADDON_LOADED",
    "AUCTION_HOUSE_SHOW",
    "AUCTION_HOUSE_CLOSED",
    "REPLICATE_ITEM_LIST_UPDATE",
    "AUCTION_ITEM_LIST_UPDATE",
}) do
    if not pcall(frame.RegisterEvent, frame, event) then
        missingEvents[#missingEvents + 1] = event
    end
end

function ensureButton()
    if button then return end
    local parent = AuctionHouseFrame or AuctionFrame
    if not parent then return end
    button = CreateFrame("Button", "BrownstoneScanButton", parent, "UIPanelButtonTemplate")
    button:SetSize(130, 22)
    button:SetText("Brownstone Scan")
    button:SetPoint("BOTTOMRIGHT", parent, "TOPRIGHT", -40, 2)  -- above the window, clear of its own buttons
    button:SetScript("OnClick", startScan)
end

frame:SetScript("OnEvent", function(_, event, arg1)
    if event == "ADDON_LOADED" then
        if arg1 ~= ADDON then return end
        BrownstoneScanDB = BrownstoneScanDB or {}
        BrownstoneScanDB.schema_version = SCHEMA_VERSION
        BrownstoneScanDB.addon_version = ADDON_VERSION
        BrownstoneScanDB.scans = BrownstoneScanDB.scans or {}
    elseif event == "AUCTION_HOUSE_SHOW" then
        ensureButton()
    elseif event == "AUCTION_HOUSE_CLOSED" then
        stopScan("stopped", "auction house window closed")
    elseif event == "REPLICATE_ITEM_LIST_UPDATE" then
        if scan and scan.api == "modern" and scan.phase == "waiting" then
            beginReading()
        end
    elseif event == "AUCTION_ITEM_LIST_UPDATE" then
        if scan and scan.api == "legacy" and scan.phase == "waiting" then
            beginReading()
        end
    end
end)

---------------------------------------------------------------------------
-- Slash command
---------------------------------------------------------------------------

SLASH_BROWNSTONESCAN1 = "/bscan"
SlashCmdList["BROWNSTONESCAN"] = function(msg)
    local cmd, rest = (msg or ""):match("^%s*(%S*)%s*(.-)%s*$")
    cmd = cmd:lower()
    if cmd == "start" then
        startScan()
    elseif cmd == "stop" then
        if not stopScan("stopped", "stopped by user") then say("No scan is running.") end
    elseif cmd == "label" then
        BrownstoneScanDB.label = (rest ~= "") and rest or nil
        say("Label for future scans: " .. tostring(BrownstoneScanDB.label))
    elseif cmd == "status" then
        local n = #BrownstoneScanDB.scans
        local last = BrownstoneScanDB.scans[n]
        say(("Events the client rejected: %s."):format(#missingEvents > 0 and table.concat(missingEvents, ", ") or "none"))
        say(("%d saved scan(s). API: %s. Last: %s."):format(n, tostring(detectApi()),
            last and (last.scan_id .. " " .. last.status .. ", " .. (last.listing_count or 0) .. " listings") or "none"))
    elseif cmd == "clear" then
        if unsavedScans > 0 and rest:lower() ~= "all" then
            say(("%d scan(s) from this session aren't in the file yet, so nothing was cleared. Type /reload, "
                .. "import into Brownstone, then /bscan clear. (/bscan clear all deletes them anyway.)"):format(unsavedScans))
            return
        end
        BrownstoneScanDB.scans = {}
        unsavedScans = 0
        say("Saved scans cleared (written at the next /reload).")
    else
        say("/bscan start | stop | status | label <text> | clear [all]")
    end
end
