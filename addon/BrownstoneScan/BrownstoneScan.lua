-- Brownstone Scan: read-only auction house scan (STORY-023).
--
-- A scan starts only from an auction-house/panel button or "/bscan start" while
-- the auction house window is open. The addon only reads listings. It never
-- bids, buys, posts or cancels, and never scans on a timer or on its own.
--
-- Output: BrownstoneScanDB (SavedVariables), written by the game on /reload or
-- logout. See addon/README.md for the format and the measurement checklist.

local ADDON = "BrownstoneScan"
local SCHEMA_VERSION = 6
local SCAN_VERSION = 4
local ADDON_VERSION = "0.9.0"
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
local panel = {}  -- convenience UI only; no capture or timer
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

local clearSnapshots, clearJournal

local function clearScans(force)
    if scan or itemPass then say("Wait for the scan and its item info pass to finish before clearing.") return end
    if not canClearScans(force) then return end
    BrownstoneScanDB.scans = {}
    unsavedScans = 0
    local removed = clearSnapshots()
    local entriesRemoved = clearJournal()
    if entriesRemoved then
        say(("%d journal entries from before this login cleared; current login entries kept."):format(entriesRemoved))
    else
        say("Login time unknown; every journal entry kept.")
    end
    if removed then
        say(("Saved scans cleared, and %d character snapshot(s) from before this login; this login's are kept "
            .. "(written at the next /reload)."):format(removed))
    else
        say("Saved scans cleared. This login's time is unknown, so every character snapshot was kept "
            .. "(written at the next /reload).")
    end
    if panel.refresh then panel.refresh() end
end

local CLEAR_POPUP = "BROWNSTONESCAN_CLEAR_SAVED"
StaticPopupDialogs[CLEAR_POPUP] = {
    text = "Delete %d saved Brownstone scan(s), snapshots and journal entries older than this login? Import them into Brownstone first. Reload afterward to write the change.",
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
    for _, control in pairs({ reloadButton, clearButton, panel.reload, panel.clear }) do
        if enabled then control:Enable() else control:Disable() end
    end
    if panel.syncStart then panel.syncStart(enabled) end
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
-- Character snapshots: event-driven reads only, no requests, timers or item movement.
---------------------------------------------------------------------------
local professions = { open = {}, last = {} }  -- open: trade/craft window shown and not yet closed
local bankOpen = false
local sessionKey, loginTime
local sessionSeen = false  -- the first PLAYER_ENTERING_WORLD since this addon file was loaded
local firedEvents = {}
local worldSignal = {}

local function identityKey(name, realm)
    return ("%d:%s%d:%s"):format(#name, name, #realm, realm)
end

local function characterKey()
    local name, realm = safe(UnitName, "player"), safe(GetRealmName)
    if not name or not realm then return nil end
    return identityKey(name, realm), name, realm
end

local function startSession(initial, reload)
    worldSignal = { initial_login = initial, reloading_ui = reload, observed_at = time() }
    local key = characterKey()
    if not key then return end
    sessionKey = key
    local sessions = BrownstoneScanDB.sessions
    if initial == true and reload == false then
        local now = time()
        sessions[key] = { login_at = now, login_at_utc = utc(now), initial_login = true }
    elseif initial == false and reload == true and sessions[key] then
        sessions[key].reload_seen = true
    else
        -- Unknown signal: never invent a new login that could permit deleting current evidence.
        say("Login/reload signal unknown; snapshot clear will retain all snapshots. Record /bscan status for beta.")
        loginTime = nil
        return
    end
    loginTime = sessions[key] and sessions[key].login_at
end

-- The client's own bank code places bank bags after every equipped bag (NUM_TOTAL_EQUIPPED_BAG_SLOTS
-- includes a modern reagent bag; older clients only define NUM_BAG_SLOTS). Container numbers are not
-- taken from Enum.BagIndex, whose names can include a reagent bag on clients where that number is the
-- first bank bag. Bank IDs are never read with the bank closed.
local function equippedBags()
    return NUM_TOTAL_EQUIPPED_BAG_SLOTS or NUM_BAG_SLOTS or 4
end

local function containerIDs(kind)
    local ids = {}
    local function add(id) if type(id) == "number" then ids[#ids + 1] = id end end
    local equipped = equippedBags()
    if kind == "bags" then
        add(KEYRING_CONTAINER)
        for id = 0, equipped do add(id) end
    else
        add(REAGENTBANK_CONTAINER)
        add(BANK_CONTAINER or -1)
        for id = equipped + 1, equipped + (NUM_BANKBAGSLOTS or 7) do add(id) end
    end
    table.sort(ids)
    return ids
end

local function readSlot(id, slot)
    local failed = false
    local function read(fn, ...)
        if type(fn) ~= "function" then return nil end
        local ok, value = pcall(fn, ...)
        if not ok then failed = true return nil end
        return value
    end
    local api = C_Container or {}
    local link = read(api.GetContainerItemLink or GetContainerItemLink, id, slot)
    local itemID = read(api.GetContainerItemID or GetContainerItemID, id, slot)
    local count, occupied
    if type(api.GetContainerItemInfo) == "function" then
        local info = read(api.GetContainerItemInfo, id, slot)
        if info then
            count, occupied = info.stackCount, true
            itemID, link = info.itemID or itemID, info.hyperlink or link
        end
    elseif type(GetContainerItemInfo) == "function" then
        local ok, texture, quantity = pcall(GetContainerItemInfo, id, slot)
        if ok then count, occupied = quantity, texture ~= nil else failed = true end
    end
    if not occupied and not itemID and not link then return nil, failed end
    return { container_id = id, slot = slot, item_id = itemID, count = count, item_link = link }, failed
end

local function captureCharacter(kind, event)
    if kind == "bank" and not bankOpen then return end
    local key, name, realm = characterKey()
    local faction = safe(UnitFactionGroup, "player")
    if not key or not faction then say("Character identity unavailable; snapshot not saved.") return end
    local now = time()
    local db = BrownstoneScanDB
    db.snapshot_sequence = (db.snapshot_sequence or 0) + 1
    local snapshot = { snapshot_id = key .. ":" .. kind .. ":" .. now .. ":" .. db.snapshot_sequence,
        character = name, realm = realm, faction = faction, kind = kind, sequence = db.snapshot_sequence,
        captured_at = now, captured_at_utc = utc(now), addon_version = ADDON_VERSION,
        event = event, login_at = loginTime, world_signal = worldSignal, client = collectContext().client,
        slots = {}, containers = {},
        rejected_events = {}, fired_events = {},
        container_api = C_Container and "C_Container" or "legacy",
        -- Beta check: the client's container layout behind the IDs read (see containerIDs).
        container_layout = { equipped_bags = equippedBags(), bank_bag_slots = NUM_BANKBAGSLOTS,
            reagent_bag_enum = Enum and Enum.BagIndex and Enum.BagIndex.ReagentBag } }
    for _, e in ipairs(missingEvents) do snapshot.rejected_events[#snapshot.rejected_events + 1] = e end
    for e, count in pairs(firedEvents) do snapshot.fired_events[e] = count end
    if kind == "bags" then
        snapshot.gold_copper = safe(GetMoney)
        snapshot.level = safe(UnitLevel, "player")
        snapshot.skills = professions.skills()
    end
    local api = C_Container or {}
    local canRead = api.GetContainerItemInfo or GetContainerItemInfo or api.GetContainerItemID
        or GetContainerItemID or api.GetContainerItemLink or GetContainerItemLink
    for _, id in ipairs(containerIDs(kind)) do
        local size = canRead and safe(api.GetContainerNumSlots or GetContainerNumSlots, id) or nil
        -- A closed/inaccessible main bank sometimes reports zero slots. Do not call that empty.
        if kind == "bank" and id == (BANK_CONTAINER or -1) and size == 0 then size = nil end
        local container = { container_id = id, size = size }
        snapshot.containers[#snapshot.containers + 1] = container
        if type(size) == "number" then
            for slot = 1, size do
                local item, failed = readSlot(id, slot)
                if failed then container.slots_readable = false end
                if item then snapshot.slots[#snapshot.slots + 1] = item end
            end
        end
    end
    db.snapshots[#db.snapshots + 1] = snapshot
end

-- Returns how many snapshots were removed, or nil when the login time is unknown and all are kept.
clearSnapshots = function()
    if not loginTime then return nil end
    local kept = {}
    for _, snapshot in ipairs(BrownstoneScanDB.snapshots) do
        if not snapshot.captured_at or snapshot.captured_at >= loginTime then kept[#kept + 1] = snapshot end
    end
    local removed = #BrownstoneScanDB.snapshots - #kept
    BrownstoneScanDB.snapshots = kept
    return removed
end

local function characterStatus()
    local key = characterKey()
    local bank
    for _, snapshot in ipairs(BrownstoneScanDB.snapshots) do
        if identityKey(snapshot.character, snapshot.realm) == key and snapshot.kind == "bank" then bank = snapshot.captured_at_utc end
    end
    say(("%d character snapshot(s); login: %s; bank: %s; session: %s."):format(
        #BrownstoneScanDB.snapshots, tostring(loginTime), bank or "bank unknown", tostring(sessionKey)))
    local events = {}
    for e, count in pairs(firedEvents) do events[#events + 1] = e .. "=" .. count end
    table.sort(events)
    say("Character events fired: " .. table.concat(events, ", "))
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
        schema_version = SCAN_VERSION,
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

---------------------------------------------------------------------------
-- Economy journal. Event-driven read APIs and secure post-hooks only.
---------------------------------------------------------------------------
local journal = { cap = 10000, windows = {}, hooks = {}, missing = {}, events = {}, lastInbox = nil }
local journalRejected = 0  -- events this client rejected, reported once with the missing hooks
local journalEvents = {
    PLAYER_MONEY = "money", BAG_UPDATE_DELAYED = "bags",
    MAIL_SHOW = "mail", MAIL_CLOSED = "mail", MAIL_INBOX_UPDATE = "mail",
    MAIL_SEND_INFO_UPDATE = "mail", MAIL_SEND_SUCCESS = "mail", MAIL_FAILED = "mail",
    AUCTION_HOUSE_SHOW = "auction", AUCTION_HOUSE_CLOSED = "auction",
    AUCTION_HOUSE_PURCHASE_COMPLETED = "auction", AUCTION_HOUSE_AUCTION_CREATED = "auction",
    AUCTION_HOUSE_AUCTION_CANCELED = "auction", AUCTION_HOUSE_SHOW_ERROR = "auction",
    OWNED_AUCTIONS_UPDATED = "auction", AUCTION_OWNED_LIST_UPDATE = "auction", AUCTION_ITEM_LIST_UPDATE = "auction",
    AUCTION_MULTISELL_START = "auction", AUCTION_MULTISELL_UPDATE = "auction", AUCTION_MULTISELL_FAILURE = "auction",
    MERCHANT_SHOW = "vendor", MERCHANT_CLOSED = "vendor", MERCHANT_UPDATE = "vendor",
    TRADE_SKILL_SHOW = "craft", TRADE_SKILL_CLOSE = "craft", TRADE_SKILL_UPDATE = "craft",
    CRAFT_SHOW = "craft", CRAFT_CLOSE = "craft", CRAFT_UPDATE = "craft",
    UNIT_SPELLCAST_SUCCEEDED = "craft", CHAT_MSG_LOOT = "loot", LOOT_OPENED = "loot", LOOT_CLOSED = "loot",
    LOOT_SLOT_CLEARED = "loot", BANKFRAME_OPENED = "bags", BANKFRAME_CLOSED = "bags",
}
-- Ordinary refreshes are counted; profession refreshes also save changed lists.
local journalCountOnly = { MERCHANT_UPDATE = true,
    AUCTION_ITEM_LIST_UPDATE = true }
local journalHooks = {
    { "TakeInboxMoney", "mail" }, { "TakeInboxItem", "mail" }, { "AutoLootMailItem", "mail" },
    { "SendMail", "mail" }, { "ReturnInboxItem", "mail" }, { "DeleteInboxItem", "mail" },
    { "SetSendMailMoney", "mail" }, { "SetSendMailCOD", "mail" },
    { "StartAuction", "auction" }, { "PostAuction", "auction" }, { "PlaceAuctionBid", "auction" },
    { "CancelAuction", "auction" }, { "BuyMerchantItem", "vendor" }, { "SellCursorItem", "vendor" },
    { "UseContainerItem", "vendor" }, { "RepairAllItems", "vendor" },
    { "DoTradeSkill", "craft" }, { "DoCraft", "craft" },
    { "PostItem", "auction", "C_AuctionHouse" }, { "PostCommodity", "auction", "C_AuctionHouse" },
    { "PlaceBid", "auction", "C_AuctionHouse" }, { "CancelAuction", "auction", "C_AuctionHouse" },
    { "ConfirmCommoditiesPurchase", "auction", "C_AuctionHouse" },
    { "UseContainerItem", "vendor", "C_Container" }, { "CraftRecipe", "craft", "C_TradeSkillUI" },
}

-- Explicit count preserves nil holes and trailing nils. Tables are copied, never retained by reference.
function journal.copy(value, depth)
    local kind = type(value)
    if kind == "string" or kind == "boolean" then return value end
    if kind == "number" and value == value and value ~= math.huge and value ~= -math.huge then return value end
    if kind ~= "table" or (depth or 0) >= 8 then return nil end
    local copied = {}
    for k, v in pairs(value) do
        if type(k) == "string" or (type(k) == "number" and k ~= math.huge and k ~= -math.huge) then
            copied[k] = journal.copy(v, (depth or 0) + 1)
        end
    end
    return copied
end

function journal.args(...)
    local values = { n = select("#", ...) }
    for i = 1, values.n do
        local value = select(i, ...)
        values[i] = journal.copy(value)
    end
    return values
end

function journal.entry(event, family, arguments, context)
    local db = BrownstoneScanDB
    if not db or not db.journal then return nil end
    local key, name, realm = characterKey()
    local faction = safe(UnitFactionGroup, "player")
    if not key or not faction then say("Character identity unavailable; journal event rejected: " .. event) return nil end
    db.snapshot_sequence = (db.snapshot_sequence or 0) + 1
    local now = time()
    local entry = { entry_id = key .. ":journal:" .. now .. ":" .. db.snapshot_sequence,
        sequence = db.snapshot_sequence, character = name, realm = realm, faction = faction,
        captured_at = now, captured_at_utc = utc(now), session_time = journal.copy(safe(GetTime)), login_at = loginTime,
        addon_version = ADDON_VERSION, event = event, family = family, arguments = arguments or { n = 0 },
        windows = journal.copy(journal.windows) }
    for k, v in pairs(context or {}) do entry[k] = v end
    return entry
end

function journal.findOverflow()
    journal.overflowIndex = nil
    for i, entry in ipairs(BrownstoneScanDB.journal) do
        if entry.event == "JOURNAL_OVERFLOW" then journal.overflowIndex = i end
    end
end

function journal.add(event, family, arguments, context)
    local db = BrownstoneScanDB
    if not db or not db.journal then return end
    local ordinaryCount = #db.journal - (journal.overflowIndex and 1 or 0)
    if ordinaryCount >= journal.cap then
        local previous = journal.overflowIndex and db.journal[journal.overflowIndex]
        local skipped = previous and (previous.skipped or 0) + 1 or 1
        local marker = journal.entry("JOURNAL_OVERFLOW", "system", nil, { skipped = skipped })
        if not marker then return end
        -- Fresh ID makes each previously imported marker immutable historical evidence.
        journal.overflowIndex = journal.overflowIndex or #db.journal + 1
        db.journal[journal.overflowIndex] = marker
        if not journal.capReported then
            journal.capReported = true
            say("Journal cap (10000 entries) reached; further entries counted in one overflow marker. Reload and import.")
        end
        return
    end
    local entry = journal.entry(event, family, arguments, context)
    if entry then db.journal[#db.journal + 1] = entry return true end
end

function journal.money()
    local value = safe(GetMoney)
    if type(value) == "number" and value >= 0 and value < math.huge and value % 1 == 0 then return value end
    return nil
end

function journal.bags()
    local counts = {}
    local api = C_Container or {}
    local readable = api.GetContainerItemInfo or GetContainerItemInfo or api.GetContainerItemID or GetContainerItemID
    if not readable then return nil end
    for _, id in ipairs(containerIDs("bags")) do
        local size = safe(api.GetContainerNumSlots or GetContainerNumSlots, id)
        if type(size) ~= "number" or size < 0 or size >= math.huge or size % 1 ~= 0 then return nil end
        for slot = 1, size do
            local item, failed = readSlot(id, slot)
            if failed or (item and (type(item.item_id) ~= "number" or type(item.count) ~= "number"
                or item.item_id <= 0 or item.item_id % 1 ~= 0 or item.count <= 0 or item.count % 1 ~= 0)) then return nil end
            if item then counts[item.item_id] = (counts[item.item_id] or 0) + item.count end
        end
    end
    return counts
end

function journal.bagChange(arguments)
    local current, previous = journal.bags(), journal.lastBags
    journal.lastBags = current
    if not current or not previous then
        journal.add("BAG_UPDATE_DELAYED", "bags", arguments, { baseline_missing = true })
        return
    end
    local changes = {}
    for id, count in pairs(current) do
        if count ~= (previous[id] or 0) then changes[id] = count - (previous[id] or 0) end
    end
    for id, count in pairs(previous) do if not current[id] then changes[id] = -count end end
    if next(changes) then journal.add("BAG_UPDATE_DELAYED", "bags", arguments, { item_changes = changes }) end
end

function journal.read(fn, ...)
    if type(fn) ~= "function" then return nil end
    local values = journal.args(pcall(fn, ...))
    if not values[1] then return nil end
    local result = { n = values.n - 1 }
    for i = 2, values.n do result[i - 1] = values[i] end
    return result
end

-- An uncached item has no name yet but can still report its ID and count.
function journal.present(values)
    if not values then return false end
    for i = 1, values.n do if values[i] ~= nil then return true end end
    return false
end

function journal.equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not journal.equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end

function journal.inbox(event, arguments)
    local state = { counts = journal.read(GetInboxNumItems), messages = {} }
    local count = state.counts and state.counts[1]
    if type(count) == "number" then
        for i = 1, count do
            state.messages[i] = { index = i, header = journal.read(GetInboxHeaderInfo, i),
                invoice = journal.read(GetInboxInvoiceInfo, i), items = {} }
            for slot = 1, (ATTACHMENTS_MAX_RECEIVE or 16) do
                local item = journal.read(GetInboxItem, i, slot)
                if journal.present(item) then state.messages[i].items[slot] = {
                    info = item, link = safe(GetInboxItemLink, i, slot) } end
            end
        end
    end
    if not journal.equal(state, journal.lastInbox) then
        journal.lastInbox = journal.copy(state)
        journal.add(event, "mail", arguments, { inbox = state })
    end
end

-- Read cached owned results only on the matching client event; never request a refresh.
function journal.owned(event, arguments)
    local state = { auctions = {} }
    if event == "OWNED_AUCTIONS_UPDATED" then
        local api = C_AuctionHouse or {}
        state.api = "C_AuctionHouse"
        state.counts = journal.read(api.GetNumOwnedAuctions)
        state.full_results = safe(api.HasFullOwnedAuctionResults)
        state.sold_status = Enum and Enum.AuctionStatus and Enum.AuctionStatus.Sold
        local count = state.counts and state.counts[1]
        if type(count) == "number" then
            for i = 1, count do
                state.auctions[i] = { index = i, info = journal.copy(safe(api.GetOwnedAuctionInfo, i)) }
            end
        end
    else
        state.api = "legacy"
        state.counts = journal.read(GetNumAuctionItems, "owner")
        local count = state.counts and state.counts[1]
        if type(count) == "number" then
            for i = 1, count do
                state.auctions[i] = { index = i, info = journal.read(GetAuctionItemInfo, "owner", i),
                    item_link = safe(GetAuctionItemLink, "owner", i),
                    time_left = safe(GetAuctionItemTimeLeft, "owner", i) }
            end
        end
    end
    if not journal.equal(state, journal.lastOwned) then
        if journal.add(event, "auction", arguments, { owned_auctions = state }) then
            journal.lastOwned = journal.copy(state)
        end
    end
end

-- Read both available skill surfaces; preserve raw tuples and their API provenance.
function professions.skills()
    local state = {}
    if type(GetNumSkillLines) == "function" then
        local legacy = { api = "GetSkillLineInfo", counts = journal.read(GetNumSkillLines), rows = {} }
        state.legacy = legacy
        for i = 1, (legacy.counts and legacy.counts[1] or 0) do
            local info = journal.read(GetSkillLineInfo, i)
            legacy.rows[i] = { index = i, info = info, name = info and info[1],
                is_header = info and info[2], expanded = info and info[3], rank = info and info[4],
                max_rank = info and info[7], skill_id = info and info[14] }
            -- A collapsed header hides its skills from the count; flag it, never expand it.
            local row = legacy.rows[i]
            if not info or (row.is_header and row.is_header ~= 0 and row.expanded ~= true and row.expanded ~= 1) then
                legacy.possibly_incomplete = true
            end
        end
    end
    if type(GetProfessions) == "function" then
        local modern = { api = "GetProfessionInfo", indexes = journal.read(GetProfessions), rows = {} }
        state.modern = modern
        for i = 1, (modern.indexes and modern.indexes.n or 0) do
            local index = modern.indexes[i]
            if index then
                local info = journal.read(GetProfessionInfo, index)
                modern.rows[#modern.rows + 1] = { index = index, info = info, name = info and info[1],
                    rank = info and info[3], max_rank = info and info[4], skill_id = info and info[7] }
            end
        end
    end
    return state
end

function professions.filters(prefix)
    local state, incomplete = {}, false
    for _, suffix in ipairs({ "SubClass", "InvSlot" }) do
        local count = journal.read(_G[prefix .. (suffix == "SubClass" and "SubClasses" or "InvSlots")])
        local all = safe(_G[prefix .. suffix .. "Filter"], 0)
        if count or all ~= nil then
            local selected = { all = all, names = count }
            state[suffix] = selected
            if selected.all == false or selected.all == 0 then incomplete = true end
            for i = 1, (count and count.n or 0) do
                selected[i] = { name = count[i], enabled = safe(_G[prefix .. suffix .. "Filter"], i) }
                if selected.all ~= true and selected.all ~= 1 and
                    (selected[i].enabled == false or selected[i].enabled == 0) then incomplete = true end
            end
        end
    end
    for _, suffix in ipairs({ "OnlyShowMakeable", "OnlyShowSkillUps" }) do
        local value = safe(_G[prefix .. suffix])
        state[suffix] = value
        if value == true or (type(value) == "number" and value ~= 0) then incomplete = true end
    end
    local name = safe(_G[prefix .. "ItemNameFilter"])
    state.ItemNameFilter = name
    if type(name) == "string" and name ~= "" then incomplete = true end
    state.ItemLevelFilter = journal.read(_G[prefix .. "ItemLevelFilter"])
    for i = 1, (state.ItemLevelFilter and state.ItemLevelFilter.n or 0) do
        local level = state.ItemLevelFilter[i]
        if type(level) == "number" and level > 0 then incomplete = true end
    end
    return state, incomplete
end

function professions.linkID(link, kind)
    if type(link) == "string" then return tonumber(link:match(kind .. ":(%d+)")) end
end

function professions.row(prefix, index)
    local info = journal.read(_G[prefix .. "Info"], index)
    local craft = prefix == "GetCraft"
    local kind = info and info[craft and 3 or 2]
    local link = safe(_G[prefix .. "RecipeLink"], index)
    local row = { index = index, info = info, name = info and info[1], type = kind,
        difficulty = kind, craftable = info and info[craft and 4 or 3],
        expanded = info and info[craft and 5 or 4], recipe_link = link,
        recipe_id = type(link) == "string" and tonumber(link:match("enchant:(%d+)")) or nil,
        spell_id = type(link) == "string" and tonumber(link:match("spell:(%d+)")) or nil,
        item_link = safe(_G[prefix .. "ItemLink"], index),
        made = journal.read(_G[prefix .. "NumMade"], index),
        reagent_counts = journal.read(_G[prefix .. "NumReagents"], index), reagents = {} }
    row.item_id = professions.linkID(row.item_link, "item")
    row.spell_id = row.spell_id or professions.linkID(link, "enchant") or
        professions.linkID(row.item_link, "enchant") or professions.linkID(row.item_link, "spell")
    row.min_made, row.max_made = row.made and row.made[1], row.made and row.made[2]
    for i = 1, (row.reagent_counts and row.reagent_counts[1] or 0) do
        local reagent = journal.read(_G[prefix .. "ReagentInfo"], index, i)
        local itemLink = safe(_G[prefix .. "ReagentItemLink"], index, i)
        row.reagents[i] = { index = i, info = reagent, item_link = itemLink,
            item_id = type(itemLink) == "string" and tonumber(itemLink:match("item:(%d+)")) or nil,
            count = reagent and reagent[3] }
    end
    return row
end

-- Craftable counts change with every craft or bag change; comparing without them saves a new list
-- only when recipes, ranks, headers or filters change. Saved lists still carry the counts.
function professions.structure(state)
    local copy = journal.copy(state)
    for _, row in pairs(copy.rows) do
        row.craftable = nil
        if row.info then row.info[state.api == "GetCraft" and 4 or 3] = nil end
    end
    return copy
end

-- Returns "recorded" when a changed list was saved, "unchanged" when it matched, nil when unreadable.
function professions.window(event, arguments)
    local craft = event == "CRAFT_SHOW" or event == "CRAFT_UPDATE"
    local prefix = craft and "GetCraft" or "GetTradeSkill"
    local profession = journal.read(_G[craft and "GetCraftDisplaySkillLine" or "GetTradeSkillLine"])
    if not profession or not profession[1] then return end
    local state = { api = prefix, profession = profession, name = profession[1], rank = profession[2],
        max_rank = profession[3], counts = journal.read(_G[craft and "GetNumCrafts" or "GetNumTradeSkills"]),
        rows = {} }
    state.filters, state.possibly_incomplete = professions.filters(prefix)
    if not state.counts or state.counts[1] == nil then state.possibly_incomplete = true end
    for i = 1, (state.counts and state.counts[1] or 0) do
        local row = professions.row(prefix, i)
        state.rows[i] = row
        if not row.type or (row.type == "header" and (row.expanded ~= true and row.expanded ~= 1)) then
            state.possibly_incomplete = true
        end
    end
    local identity = characterKey()
    if not identity then return end
    local key = identity .. ":" .. state.name
    local structure = professions.structure(state)
    if journal.equal(structure, professions.last[key]) then return "unchanged" end
    if journal.add(event, "craft", arguments, { known_recipes = state }) then
        professions.last[key] = structure
        return "recorded"
    end
end

function journal.draft()
    local draft = { money_copper = safe(GetSendMailMoney), cod_copper = safe(GetSendMailCOD),
        observed_at = time(), items = {} }
    for i = 1, (ATTACHMENTS_MAX_SEND or 12) do
        local item = journal.read(GetSendMailItem, i)
        if journal.present(item) then draft.items[i] = { info = item, link = safe(GetSendMailItemLink, i) } end
    end
    journal.lastDraft = draft
end

function journal.protect(fn, label, ...)
    local ok, problem = pcall(fn, ...)
    if not ok then
        local db = BrownstoneScanDB
        if db then
            db.journal_errors = db.journal_errors or {}
            db.journal_errors[label] = (db.journal_errors[label] or 0) + 1
        end
        say("Journal observation rejected: " .. label .. ": " .. tostring(problem))
    end
end

function journal.hook(name, family, label, ...)
    -- Container use is an economy action only at a merchant; elsewhere it can equip/use items.
    if name == "UseContainerItem" and not journal.windows.merchant then return end
    local context = { hook = true }
    if name == "SendMail" then
        context.draft = journal.copy(journal.lastDraft)
        context.draft_is_last_observed = true
    end
    journal.add(label, family, journal.args(...), context)
end

function journal.installHooks()
    local db = BrownstoneScanDB
    if not db then return end
    local newlyMissing = 0
    for _, spec in ipairs(journalHooks) do
        local name, family, namespace = spec[1], spec[2], spec[3]
        local target = _G
        if namespace then target = _G[namespace] end
        local label = namespace and namespace .. "." .. name or name
        if not journal.hooks[label] then
            local callback = function(...)
                journal.protect(journal.hook, label, name, family, label, ...)
            end
            local ok = type(target) == "table" and type(target[name]) == "function" and
                type(hooksecurefunc) == "function" and pcall(hooksecurefunc, target, name, callback)
            if ok then journal.hooks[label] = true
            elseif not journal.missing[label] then
                journal.missing[label] = true
                newlyMissing = newlyMissing + 1
            end
        end
    end
    db.journal_diagnostics = { rejected_events = journal.copy(missingEvents), missing_hooks = {},
        installed_hooks = journal.copy(journal.hooks), fired_events = journal.events }
    for label in pairs(journal.missing) do
        if not journal.hooks[label] then db.journal_diagnostics.missing_hooks[#db.journal_diagnostics.missing_hooks + 1] = label end
    end
    table.sort(db.journal_diagnostics.missing_hooks)
    -- Candidates span old and new clients, so some are always missing: one line, details in /bscan status.
    if newlyMissing > 0 or journalRejected > 0 then
        say(("Journal: %d event(s) and %d hook(s) unavailable on this client; /bscan status lists them.")
            :format(journalRejected, newlyMissing))
        journalRejected = 0
    end
end

function journal.observe(event, ...)
    if not BrownstoneScanDB or not BrownstoneScanDB.journal then return end
    local family = journalEvents[event]
    if not family then return end
    -- Only the player's own casts while a crafting window is open: combat and other spells are not economy evidence.
    if event == "UNIT_SPELLCAST_SUCCEEDED" and (select(1, ...) ~= "player" or not journal.windows.trade_skill) then
        return
    end
    -- CHAT_MSG_LOOT arg 12 is the sender GUID. Without positive player identity, omit it.
    if event == "CHAT_MSG_LOOT" then
        local guid = safe(UnitGUID, "player")
        if not guid or select(12, ...) ~= guid then return end
    end
    journal.events[event] = (journal.events[event] or 0) + 1
    if event == "TRADE_SKILL_SHOW" or event == "TRADE_SKILL_CLOSE" then
        professions.open.trade = event == "TRADE_SKILL_SHOW"
    elseif event == "CRAFT_SHOW" or event == "CRAFT_CLOSE" then
        professions.open.craft = event == "CRAFT_SHOW"
    elseif event == "TRADE_SKILL_UPDATE" or event == "CRAFT_UPDATE" then
        -- Closed windows report placeholder names (Classic: "UNKNOWN"); only read an open one.
        if professions.open[event == "CRAFT_UPDATE" and "craft" or "trade"] then
            professions.window(event, journal.args(...))
        end
        return
    end
    if journalCountOnly[event] then return end
    local open = { MAIL_SHOW = "mailbox", MERCHANT_SHOW = "merchant", AUCTION_HOUSE_SHOW = "auction_house",
        TRADE_SKILL_SHOW = "trade_skill", CRAFT_SHOW = "trade_skill", LOOT_OPENED = "loot", BANKFRAME_OPENED = "bank" }
    local close = { MAIL_CLOSED = "mailbox", MERCHANT_CLOSED = "merchant", AUCTION_HOUSE_CLOSED = "auction_house",
        TRADE_SKILL_CLOSE = "trade_skill", CRAFT_CLOSE = "trade_skill", LOOT_CLOSED = "loot", BANKFRAME_CLOSED = "bank" }
    if open[event] then journal.windows[open[event]] = true end
    local arguments = journal.args(...)
    if event == "TRADE_SKILL_SHOW" or event == "CRAFT_SHOW" then
        if professions.window(event, arguments) ~= "recorded" then journal.add(event, family, arguments) end
    elseif event == "BAG_UPDATE_DELAYED" then journal.bagChange(arguments)
    elseif event == "PLAYER_MONEY" then
        local current = journal.money()
        journal.add(event, family, arguments, { before_copper = journal.lastMoney, after_copper = current })
        journal.lastMoney = current
    elseif event == "MAIL_SHOW" or event == "MAIL_INBOX_UPDATE" then journal.inbox(event, arguments)
    elseif event == "OWNED_AUCTIONS_UPDATED" or event == "AUCTION_OWNED_LIST_UPDATE" then
        journal.owned(event, arguments)
    else
        if event == "MAIL_SEND_INFO_UPDATE" then journal.draft() end
        journal.add(event, family, arguments)
    end
    if close[event] then journal.windows[close[event]] = false end
end

function journal.clear()
    if not loginTime then return end
    local kept = {}
    for _, entry in ipairs(BrownstoneScanDB.journal) do
        if not entry.captured_at or entry.captured_at >= loginTime then kept[#kept + 1] = entry end
    end
    local removed = #BrownstoneScanDB.journal - #kept
    BrownstoneScanDB.journal = kept
    journal.findOverflow()
    journal.capReported = nil
    return removed
end

clearJournal = journal.clear

-- RegisterEvent throws on an event this client doesn't know (the legacy
-- AUCTION_ITEM_LIST_UPDATE is missing on Forever), so register one at a time
-- and record which ones the client rejected.
local attempted = {}
for _, event in ipairs({
    "ADDON_LOADED",
    "AUCTION_HOUSE_SHOW",
    "AUCTION_HOUSE_CLOSED",
    "REPLICATE_ITEM_LIST_UPDATE",
    "AUCTION_ITEM_LIST_UPDATE",
    "GET_ITEM_INFO_RECEIVED",
    "PLAYER_ENTERING_WORLD",
    "PLAYER_LOGOUT",
    "BANKFRAME_OPENED",
    "BANKFRAME_CLOSED",
}) do
    attempted[event] = true
    if not pcall(frame.RegisterEvent, frame, event) then
        missingEvents[#missingEvents + 1] = event
    end
end

-- Events the scan already registered are observed by the journal through the same frame.
for event in pairs(journalEvents) do
    if not attempted[event] and not pcall(frame.RegisterEvent, frame, event) then
        missingEvents[#missingEvents + 1] = event
        journalRejected = journalRejected + 1
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

-- The panel shares the existing actions and lifecycle gates. Status is refreshed on
-- open/actions (including confirmed clear), never by a polling timer.
local function printStatus()
    local n = #BrownstoneScanDB.scans
    local last = BrownstoneScanDB.scans[n]
    characterStatus()
    say(("%d journal entries; cap %d; missing hooks: %s"):format(#BrownstoneScanDB.journal, journal.cap,
        table.concat(BrownstoneScanDB.journal_diagnostics.missing_hooks, ", ")))
    say(("Events the client rejected: %s."):format(#missingEvents > 0 and table.concat(missingEvents, ", ") or "none"))
    say(("%d saved scan(s). API: %s. Last: %s."):format(n, tostring(detectApi()),
        last and (last.scan_id .. " " .. last.status .. ", " .. (last.listing_count or 0) .. " listings") or "none"))
end

function panel.syncStart(enabled)
    if not panel.start then return end
    -- Auction events can arrive before Blizzard's frame has been shown/hidden.
    local open = panel.houseOpen
    if open == nil then open = ahIsOpen() end
    if enabled and open then panel.start:Enable() else panel.start:Disable() end
end

function panel.refresh()
    if not panel.window then return end
    local db = BrownstoneScanDB
    panel.status:SetText(("Saved scans in file: %d\nSession scans not written: %d\nCharacter snapshots: %d\nLogin time: %s")
        :format(#db.scans - unsavedScans, unsavedScans, #db.snapshots,
            loginTime and "known" or "unknown (Clear keeps all journal/snapshots)"))
    local count, skipped = 0, nil
    for _, entry in ipairs(db.journal) do
        if entry.event == "JOURNAL_OVERFLOW" then skipped = entry.skipped else count = count + 1 end
    end
    panel.journal:SetText(("Journal entries: %d / 10,000%s"):format(count,
        skipped and ("; skipped: " .. skipped) or ""))
    if count >= 8000 then panel.journal:SetTextColor(1, 0.65, 0) else panel.journal:SetTextColor(1, 1, 1) end
    setMaintenanceEnabled(not scan and not itemPass)
end

local function panelText(parent, y, height)
    local text = parent:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    text:SetPoint("TOPLEFT", parent, "TOPLEFT", 16, y)
    text:SetSize(328, height)
    text:SetJustifyH("LEFT")
    text:SetJustifyV("TOP")
    return text
end

local function panelButton(name, label, x, y, action)
    local control = CreateFrame("Button", name, panel.window, "UIPanelButtonTemplate")
    control:SetSize(158, 24)
    control:SetPoint("TOPLEFT", panel.window, "TOPLEFT", x, y)
    control:SetText(label)
    control:SetScript("OnClick", function() action() panel.refresh() end)
    return control
end

local function createPanel()
    local window = CreateFrame("Frame", "BrownstoneScanPanel", UIParent, "BasicFrameTemplateWithInset")
    panel.window = window
    window:SetSize(360, 330)
    window:SetFrameStrata("HIGH")  -- below StaticPopup (DIALOG), so the Clear confirmation stays on top
    window:SetPoint("CENTER")
    window:SetMovable(true)
    window:SetClampedToScreen(true)
    window:EnableMouse(true)
    window:RegisterForDrag("LeftButton")
    window:SetScript("OnDragStart", function(self) self:StartMoving() end)
    window:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() end)
    window:SetScript("OnShow", panel.refresh)
    window.TitleText:SetText("Brownstone Scan")
    table.insert(UISpecialFrames, "BrownstoneScanPanel")
    panel.status = panelText(window, -38, 72)
    panel.journal = panelText(window, -114, 32)
    panel.reload = panelButton("BrownstonePanelReload", "Reload", 16, -150, reloadUI)
    panel.clear = panelButton("BrownstonePanelClear", "Clear saved data", 186, -150, confirmClearScans)
    panel.chat = panelButton("BrownstonePanelStatus", "Status", 16, -180, printStatus)
    panel.start = panelButton("BrownstonePanelStart", "Start scan", 186, -180, startScan)
    panel.routine = panelText(window, -218, 96)
    panel.routine:SetText("1. Play. 2. Reload (or log out) so the game writes the file. "
        .. "3. Import on the computer. 4. Clear, then Reload. Clear keeps this login's journal and snapshots; "
        .. "they import again harmlessly as duplicates.")
    window:Hide()
end

function panel.toggle()
    if not panel.window then createPanel() end
    if panel.window:IsShown() then panel.window:Hide() else panel.window:Show() end
end

function panel.positionIcon()
    local angle = math.rad(BrownstoneScanDB.ui.minimap_angle)
    panel.icon:ClearAllPoints()
    panel.icon:SetPoint("CENTER", Minimap, "CENTER", math.cos(angle) * 80, math.sin(angle) * 80)
end

function panel.dragIcon()
    local x, y = GetCursorPosition()
    local centerX, centerY = Minimap:GetCenter()
    local scale = Minimap:GetEffectiveScale()
    BrownstoneScanDB.ui.minimap_angle = math.deg(math.atan2(y / scale - centerY, x / scale - centerX)) % 360
    panel.positionIcon()
end

function panel.createIcon()
    local db = BrownstoneScanDB
    db.ui = type(db.ui) == "table" and db.ui or {}
    local angle = db.ui.minimap_angle
    if type(angle) ~= "number" or angle ~= angle or angle == math.huge or angle == -math.huge then angle = 225 end
    db.ui.minimap_angle = angle % 360
    local icon = CreateFrame("Button", "BrownstoneScanMinimapButton", Minimap)
    panel.icon = icon
    icon:SetSize(32, 32)
    icon:SetFrameStrata("MEDIUM")
    icon:RegisterForClicks("LeftButtonUp")
    icon:RegisterForDrag("LeftButton")
    icon:SetNormalTexture("Interface\\Icons\\INV_Misc_Coin_01")
    icon:GetNormalTexture():SetTexCoord(0.05, 0.95, 0.05, 0.95)
    icon:GetNormalTexture():SetPoint("TOPLEFT", icon, "TOPLEFT", 6, -6)
    icon:GetNormalTexture():SetPoint("BOTTOMRIGHT", icon, "BOTTOMRIGHT", -6, 6)
    icon:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
    local border = icon:CreateTexture(nil, "OVERLAY")
    border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
    border:SetSize(54, 54)
    border:SetPoint("TOPLEFT")
    icon:SetScript("OnClick", panel.toggle)
    icon:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_LEFT")
        GameTooltip:AddLine("Brownstone Scan")
        GameTooltip:AddLine("Click: open panel. Drag: move", 1, 1, 1)
        GameTooltip:Show()
    end)
    icon:SetScript("OnLeave", function() GameTooltip:Hide() end)
    icon:SetScript("OnDragStart", function(self)
        GameTooltip:Hide()
        -- This update exists only for the player's active drag; it never captures or runs controls.
        self:SetScript("OnUpdate", panel.dragIcon)
    end)
    icon:SetScript("OnHide", function(self)
        self:SetScript("OnUpdate", nil)
        GameTooltip:Hide()
    end)
    icon:SetScript("OnDragStop", function(self)
        panel.dragIcon()
        self:SetScript("OnUpdate", nil)
    end)
    panel.positionIcon()
end

frame:SetScript("OnEvent", function(_, event, ...)
    local arg1, arg2 = ...
    journal.protect(journal.observe, event, event, ...)
    if event == "ADDON_LOADED" then
        if arg1 ~= ADDON then journal.installHooks() return end
        BrownstoneScanDB = BrownstoneScanDB or {}
        BrownstoneScanDB.schema_version = SCHEMA_VERSION
        BrownstoneScanDB.addon_version = ADDON_VERSION
        BrownstoneScanDB.scans = BrownstoneScanDB.scans or {}
        BrownstoneScanDB.snapshots = BrownstoneScanDB.snapshots or {}
        BrownstoneScanDB.sessions = BrownstoneScanDB.sessions or {}
        BrownstoneScanDB.journal = BrownstoneScanDB.journal or {}
        journal.findOverflow()
        journal.installHooks()
        panel.createIcon()
    elseif event == "PLAYER_ENTERING_WORLD" then
        firedEvents[event] = (firedEvents[event] or 0) + 1
        -- Only the first world entry after loading (login or /reload) sets the login marker; later
        -- loading screens, including clients that pass no flags, leave it alone.
        if not sessionSeen or characterKey() ~= sessionKey then
            sessionSeen = true
            startSession(arg1, arg2)
            journal.lastMoney, journal.lastBags = journal.money(), journal.bags()
        end
    elseif event == "PLAYER_LOGOUT" then
        firedEvents[event] = (firedEvents[event] or 0) + 1
        captureCharacter("bags", event)
    elseif event == "BANKFRAME_OPENED" then
        firedEvents[event] = (firedEvents[event] or 0) + 1
        bankOpen = true
        captureCharacter("bank", event)
    elseif event == "BANKFRAME_CLOSED" then
        firedEvents[event] = (firedEvents[event] or 0) + 1
        captureCharacter("bank", event)
        bankOpen = false
    elseif event == "AUCTION_HOUSE_SHOW" then
        panel.houseOpen = true
        ensureButton()
        setMaintenanceEnabled(not scan and not itemPass)
    elseif event == "AUCTION_HOUSE_CLOSED" then
        panel.houseOpen = false
        StaticPopup_Hide(CLEAR_POPUP)
        if scan then stopScan("stopped", "auction house window closed") end
        setMaintenanceEnabled(not scan and not itemPass)
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
    elseif cmd == "panel" then
        panel.toggle()
    elseif cmd == "status" then
        printStatus()
    elseif cmd == "clear" then
        clearScans(rest:lower() == "all")
    else
        say("/bscan start | stop | status | panel | label <text> | clear [all]")
    end
end
