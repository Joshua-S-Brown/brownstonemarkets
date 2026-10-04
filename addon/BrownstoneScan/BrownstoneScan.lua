-- Brownstone Scan: read-only auction house scan (SPIKE-008 prototype).
--
-- A scan starts only from the "Brownstone Scan" button or "/bscan start" while
-- the auction house window is open. The addon only reads listings. It never
-- bids, buys, posts or cancels, and never scans on a timer or on its own.
--
-- Output: BrownstoneScanDB (SavedVariables), written by the game on /reload or
-- logout. See addon/README.md for the format and the measurement checklist.

local ADDON = "BrownstoneScan"
local SCHEMA_VERSION = 2
local ADDON_VERSION = "0.2.0"
-- Each listing is saved as one short string in this field order (schema 2), with names stored
-- once per scan. Brownstone does all pricing; the addon only records what the client reports.
local LISTING_FORMAT = "item_id:quantity:buyout:min_bid:bid:flags:name_index"
local FLAG_COMPLETE_INFO, FLAG_COMMODITY = 1, 2

local CHUNK = 2000            -- listings read per frame, to avoid freezing the client
local START_TIMEOUT = 30      -- seconds to wait for the server to answer the request

local frame = CreateFrame("Frame")
local button
local ensureButton
local scan  -- the scan in progress, or nil

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

-- Fills one listing from the modern replicate list (index is 0-based).
local function readModern(index)
    local name, _, count, _, _, _, _, minBid, _, buyout, bidAmount, _, _, _, _, _, itemID, hasAllInfo =
        C_AuctionHouse.GetReplicateItemInfo(index)
    if not itemID then return nil end
    return name, itemID, count, minBid, buyout, bidAmount, isCommodity(itemID), hasAllInfo
end

-- Legacy list (index is 1-based).
local function readLegacy(index)
    local name, _, count, _, _, _, _, minBid, _, buyout, bidAmount, _, _, _, _, _, itemID, hasAllInfo =
        GetAuctionItemInfo("list", index)
    if not itemID then return nil end
    return name, itemID, count, minBid, buyout, bidAmount, false, hasAllInfo
end

-- Index of a name in the scan's name list, adding it the first time; 0 when the client hasn't loaded it.
local function nameIndex(s, name)
    if not name or name == "" then return 0 end
    local index = s.nameIndex[name]
    if not index then
        index = #s.names + 1
        s.names[index] = name
        s.nameIndex[name] = index
    end
    return index
end

-- One listing as "item_id:quantity:buyout:min_bid:bid:flags:name_index" (LISTING_FORMAT). Prices are
-- integer copper as the client reports them (buyout is the whole stack); 0 means none, never free.
local function addListing(s, name, itemID, count, minBid, buyout, bidAmount, commodity, hasAllInfo)
    local flags = (hasAllInfo and FLAG_COMPLETE_INFO or 0) + (commodity and FLAG_COMMODITY or 0)
    s.listings[#s.listings + 1] = ("%s:%s:%s:%s:%s:%s:%s"):format(itemID, count or 0, buyout or 0,
        minBid or 0, bidAmount or 0, flags, nameIndex(s, name))
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
    s.phase, s.waited, s.cursor, s.total, s.skipped, s.nameIndex = nil, nil, nil, nil, nil, nil
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
    say(("%s: %d of %d listings in %.1fs%s. Type /reload to write the file."):format(
        status, s.listing_count, s.reported_count or 0, s.duration_seconds, reason and (" (" .. reason .. ")") or ""))
end

local function readChunks()
    local s = scan
    if not s then return end
    local read, limit = 0, CHUNK
    while s.cursor < s.total and read < limit do
        local index = s.cursor
        local name, itemID, count, minBid, buyout, bidAmount, commodity, hasAllInfo
        if s.api == "modern" then
            name, itemID, count, minBid, buyout, bidAmount, commodity, hasAllInfo = readModern(index)
        else
            name, itemID, count, minBid, buyout, bidAmount, commodity, hasAllInfo = readLegacy(index + 1)
        end
        if itemID then
            addListing(s, name, itemID, count, minBid, buyout, bidAmount, commodity, hasAllInfo)
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
    s.nameIndex = {}
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
        BrownstoneScanDB.scans = {}
        say("Saved scans cleared (written at the next /reload).")
    else
        say("/bscan start | stop | status | label <text> | clear")
    end
end
