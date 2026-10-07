-- Brownstone Scan: read-only auction house scan (STORY-023).
--
-- A scan starts only from the "Brownstone Scan" button or "/bscan start" while
-- the auction house window is open. The addon only reads listings. It never
-- bids, buys, posts or cancels, and never scans on a timer or on its own.
--
-- Output: BrownstoneScanDB (SavedVariables), written by the game on /reload or
-- logout. See addon/README.md for the format and the measurement checklist.

local ADDON = "BrownstoneScan"
local SCHEMA_VERSION = 4
local ADDON_VERSION = "0.4.0"
-- Each listing is saved as one short string in this field order (schemas 3/4), with names stored
-- once per scan, together with sellers, level types, links and item references. Brownstone does all pricing; the addon only records what the client reports.
local LISTING_FORMAT = "item_id:quantity:buyout:min_bid:bid:flags:name_index:seller_index:time_left:quality:level:level_type_index:link_index"
local FLAG_COMPLETE_INFO, FLAG_COMMODITY = 1, 2

local CHUNK = 2000            -- listings read per frame, to avoid freezing the client
local ITEM_WAIT_LIMIT = 20    -- total pass seconds, including spreading requests across frames
local ITEM_REQUESTS_PER_FRAME = 200
local missingEvents = {}
local itemPass  -- transient queue/pending IDs; observations live only in the saved scan

local START_TIMEOUT = 30      -- seconds to wait for the server to answer the request

local frame = CreateFrame("Frame")
local button, reloadButton, clearButton
local ensureButton
local scan  -- the scan in progress, or nil
-- Scans finished since login or the last /reload. They are only in memory until the game writes the
-- file on /reload or logout, so /bscan clear refuses to delete them (Brownstone hasn't seen them yet).
local unsavedScans = 0

local function say(msg)
    print("|cff66ccffBrownstoneScan:|r " .. msg)
end

-- Shared by the slash command and the confirmed button; only the slash command
-- can explicitly request the existing "all" override.
local function canClearScans(force)
    if unsavedScans > 0 and not force then
        say(("%d scan(s) from this session aren't in the file yet, so nothing was cleared. Type /reload, "
            .. "import into Brownstone, then /bscan clear. (/bscan clear all deletes them anyway.)"):format(unsavedScans))
        return false
    end
    return true
end

local function clearScans(force)
    if scan or itemPass then say("Wait for the scan and its item info pass to finish before clearing.") return end
    if not canClearScans(force) then return end
    BrownstoneScanDB.scans = {}
    unsavedScans = 0
    say("Saved scans cleared (written at the next /reload).")
end

local CLEAR_POPUP = "BROWNSTONESCAN_CLEAR_SAVED"
StaticPopupDialogs[CLEAR_POPUP] = {
    text = "Delete %d saved Brownstone scan(s)? Import them into Brownstone first. Reload afterward to write the change.",
    button1 = "Clear saved scans",
    button2 = CANCEL,
    timeout = 0,
    whileDead = true,
    hideOnEscape = true,
    preferredIndex = 3,  -- keep clear of the popup slots Blizzard's protected dialogs use
    OnAccept = function(self)
        if scan or itemPass then return end
        if not canClearScans(false) then return end
        if #BrownstoneScanDB.scans ~= self.data then
            say("Saved scans changed; click Clear saved scans again to review the count.")
            return
        end
        clearScans(false)
    end,
}

local function confirmClearScans()
    if scan or itemPass or not canClearScans(false) then return end
    local count = #BrownstoneScanDB.scans
    StaticPopup_Show(CLEAR_POPUP, count, nil, count)
end

local function reloadUI()
    if not scan and not itemPass then ReloadUI() end
end

local function setMaintenanceEnabled(enabled)
    for _, control in ipairs({ reloadButton, clearButton }) do
        if enabled then control:Enable() else control:Disable() end
    end
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

-- Both passes use the same guarded reader and tuple positions. The initial observation stays intact.
local function readItemValues(itemID, r)
    r = r or { item_id = itemID }
    local info = (C_Item and C_Item.GetItemInfo) or GetItemInfo
    if type(info) == "function" then
        local ok, name, link, quality, itemLevel, required, itemType, subtype, stack, equip, icon, sell =
            pcall(info, itemID)
        if ok and name then
            r.item_level, r.max_stack_size, r.vendor_sell_copper = itemLevel, stack, sell
        end
    end
    return r
end

-- One initial observation per ID, with no explicit load request during listing reads.
local function recordItem(s, itemID)
    if s.itemSeen[itemID] then return end
    s.itemSeen[itemID] = true
    local r = { item_id = itemID }
    local instant = (C_Item and C_Item.GetItemInfoInstant) or GetItemInfoInstant
    if type(instant) == "function" then
        local ok, id, itemType, subtype, equip, icon, classID, subclassID = pcall(instant, itemID)
        if ok and id then r.class_id, r.subclass_id = classID, subclassID end
    end
    readItemValues(itemID, r)
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

local function endItemPass(status, reason)
    local p = itemPass
    if not p then return end
    local result = p.result
    result.status, result.reason = status, reason
    result.duration_seconds = GetTime() - p.started
    result.timed_out = result.requested - result.received - result.failed
    itemPass = nil
    frame:SetScript("OnUpdate", nil)
    setMaintenanceEnabled(true)
    if button then button:SetText("Brownstone Scan") button:Enable() end
    say(("Item info: %d already loaded, %d requested, %d received, %d failed, %d timed out. Type /reload to write the file.")
        :format(result.cached, result.requested, result.received, result.failed, result.timed_out))
end

-- Fields this read gains over the first pass (nil when none), and whether none are still missing.
local function passValues(p, itemID)
    local r, first, complete = readItemValues(itemID), p.first[itemID], true
    local gained = false
    for _, key in ipairs({ "item_level", "max_stack_size", "vendor_sell_copper" }) do
        if first[key] == nil and r[key] ~= nil then
            gained = true
        else
            complete = complete and first[key] ~= nil
            r[key] = nil
        end
    end
    return gained and r or nil, complete
end

local function itemAnswer(itemID, success)
    local p = itemPass
    if not p or not p.pending[itemID] then return end
    if GetTime() - p.started >= ITEM_WAIT_LIMIT then return end
    p.pending[itemID] = nil
    if success ~= true then
        p.result.failed = p.result.failed + 1
        return
    end
    p.result.received = p.result.received + 1
    local r = passValues(p, itemID)
    if r then p.result.items[#p.result.items + 1] = r end
end

local function updateItemPass()
    local p = itemPass
    if not p then return end
    local result = p.result
    result.duration_seconds = GetTime() - p.started
    if result.duration_seconds >= ITEM_WAIT_LIMIT then endItemPass("timeout") return end
    for _ = 1, ITEM_REQUESTS_PER_FRAME do
        local itemID = p.queue[p.cursor]
        if not itemID then break end
        if GetTime() - p.started >= ITEM_WAIT_LIMIT then endItemPass("timeout") return end
        p.cursor = p.cursor + 1
        -- Items that loaded during listing reads may never answer a request, so read them first.
        local r, complete = passValues(p, itemID)
        if complete then
            result.cached = result.cached + 1
            result.items[#result.items + 1] = r
        else
            -- Mark before calling: clients may deliver an answer synchronously.
            p.pending[itemID] = true
            result.requested = result.requested + 1
            local ok = pcall(C_Item.RequestLoadItemDataByID, itemID)
            if not ok and p.pending[itemID] then
                p.pending[itemID] = nil
                result.failed = result.failed + 1
            end
        end
    end
    if button then button:SetText(("Item info %d/%d"):format(result.received + result.failed + result.cached, result.total)) end
    if p.cursor > #p.queue and result.received + result.failed == result.requested then
        endItemPass("completed")
    end
end

local function beginItemPass(s)
    local queue, first = {}, {}
    for _, r in ipairs(s.items or {}) do
        first[r.item_id] = r
        if r.item_level == nil or r.max_stack_size == nil or r.vendor_sell_copper == nil then
            queue[#queue + 1] = r.item_id
        end
    end
    local result = { total = #queue, requested = 0, received = 0, failed = 0, timed_out = 0, cached = 0,
        wait_limit_seconds = ITEM_WAIT_LIMIT, duration_seconds = 0, status = "running",
        api = "C_Item.RequestLoadItemDataByID", items = {} }
    s.item_pass = result
    itemPass = { result = result, queue = queue, first = first, pending = {}, cursor = 1, started = GetTime() }
    if #queue == 0 then endItemPass("completed") return end
    if not C_Item or type(C_Item.RequestLoadItemDataByID) ~= "function" then
        endItemPass("skipped", "request API missing") return
    end
    for _, event in ipairs(missingEvents) do
        if event == "GET_ITEM_INFO_RECEIVED" then
            endItemPass("skipped", "GET_ITEM_INFO_RECEIVED registration rejected") return
        end
    end
    setMaintenanceEnabled(false)
    if button then button:Disable() button:SetText(("Item info 0/%d"):format(#queue)) end
    frame:SetScript("OnUpdate", updateItemPass)
end

local function finish(status, reason)
    local s = scan
    if not s then return end
    scan = nil
    setMaintenanceEnabled(true)
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
    say(("%s: %d of %d listings in %.1fs%s. Item info pass follows."):format(
        status, s.listing_count, s.reported_count or 0, s.duration_seconds, reason and (" (" .. reason .. ")") or ""))
    beginItemPass(s)
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
    if scan or itemPass then say("A scan is already running.") return end
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

    StaticPopup_Hide(CLEAR_POPUP)
    setMaintenanceEnabled(false)

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
    if itemPass then endItemPass("stopped", reason) return true end
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
for _, event in ipairs({
    "ADDON_LOADED",
    "AUCTION_HOUSE_SHOW",
    "AUCTION_HOUSE_CLOSED",
    "REPLICATE_ITEM_LIST_UPDATE",
    "AUCTION_ITEM_LIST_UPDATE",
    "GET_ITEM_INFO_RECEIVED",
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
    reloadButton = CreateFrame("Button", "BrownstoneScanReloadButton", parent, "UIPanelButtonTemplate")
    reloadButton:SetSize(70, 22)
    reloadButton:SetText("Reload")
    reloadButton:SetPoint("RIGHT", button, "LEFT", -4, 0)
    reloadButton:SetScript("OnClick", reloadUI)
    clearButton = CreateFrame("Button", "BrownstoneScanClearButton", parent, "UIPanelButtonTemplate")
    clearButton:SetSize(140, 22)
    clearButton:SetText("Clear saved scans")
    clearButton:SetPoint("RIGHT", reloadButton, "LEFT", -4, 0)
    clearButton:SetScript("OnClick", confirmClearScans)
    setMaintenanceEnabled(not scan and not itemPass)
end

frame:SetScript("OnEvent", function(_, event, arg1, arg2)
    if event == "ADDON_LOADED" then
        if arg1 ~= ADDON then return end
        BrownstoneScanDB = BrownstoneScanDB or {}
        BrownstoneScanDB.schema_version = SCHEMA_VERSION
        BrownstoneScanDB.addon_version = ADDON_VERSION
        BrownstoneScanDB.scans = BrownstoneScanDB.scans or {}
    elseif event == "AUCTION_HOUSE_SHOW" then
        ensureButton()
    elseif event == "AUCTION_HOUSE_CLOSED" then
        StaticPopup_Hide(CLEAR_POPUP)
        if scan then stopScan("stopped", "auction house window closed") end
    elseif event == "GET_ITEM_INFO_RECEIVED" then
        itemAnswer(arg1, arg2)
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
        clearScans(rest:lower() == "all")
    else
        say("/bscan start | stop | status | label <text> | clear [all]")
    end
end
