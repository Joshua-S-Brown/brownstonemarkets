-- Offline WoW API surface for executing the actual addon in Lua 5.1.
clock, requests, referenceCalls, instantCalls, messages = 0, 0, {}, {}, {}
SlashCmdList = {}
WOW_PROJECT_ID = 99
AuctionHouseFrame = { IsShown = function() return true end }
function print(text) messages[#messages + 1] = text end
function GetTime() return clock end
function time() return 1793816400 end
function date(fmt, value) return os.date(fmt, value) end
function GetBuildInfo() return "1.60.1", "70205", "beta", 16001 end
function GetLocale() return "enUS" end
function GetCurrentRegion() return 1 end
function GetCurrentRegionName() return "US" end
function GetRealmName() return "Beta" end
function UnitFactionGroup() return "Alliance", "Alliance" end
function UnitName() return "Example Auctioneer" end
function UnitGUID() return "test-npc" end
function GetZoneText() return "Stormwind City" end
function GetSubZoneText() return "Trade District" end
function CreateFrame(kind)
    local f = { scripts = {} }
    function f:RegisterEvent(event) end
    function f:SetScript(event, callback) self.scripts[event] = callback end
    function f:SetSize() end
    function f:SetText(text) self.text = text end
    function f:SetPoint() end
    function f:Enable() end
    function f:Disable() end
    if kind == "Frame" then mainFrame = f else scanButton = f end
    return f
end
local function auctionInfo(index) return unpack(listingData[index], 1, 18) end
local function itemInfo(id)
    referenceCalls[id] = (referenceCalls[id] or 0) + 1
    if id == 999 then return nil end
    return "Reference", nil, 2, 15, 10, "Armor", "Cloth", 20, "INVTYPE_ROBE", 1, 0, 4, 1
end
local function itemInstant(id)
    instantCalls[id] = (instantCalls[id] or 0) + 1
    if id == 999 then return nil end
    return id, "Armor", "Cloth", "INVTYPE_ROBE", 1, 4, 1
end
C_Item = { GetItemInfo = itemInfo, GetItemInfoInstant = itemInstant }
GetItemInfo, GetItemInfoInstant = itemInfo, itemInstant
local function forbidden() error("auction mutation is forbidden") end
C_AuctionHouse = {
    ReplicateItems = function() requests = requests + 1 end,
    GetNumReplicateItems = function() return #listingData end,
    GetReplicateItemInfo = function(i) return auctionInfo(i + 1) end,
    GetReplicateItemLink = function(i) return linkData[i + 1] end,
    GetReplicateItemTimeLeft = function(i) return timeData[i + 1] end,
    GetItemCommodityStatus = function() return 1 end,
    IsThrottledMessageSystemReady = function() return true end,
    PlaceBid = forbidden, PostItem = forbidden, CancelAuction = forbidden,
}
function GetAuctionItemInfo(which, i) assert(which == "list") return auctionInfo(i) end
function GetAuctionItemLink(which, i) assert(which == "list") return linkData[i] end
function GetAuctionItemTimeLeft(which, i) assert(which == "list") return timeData[i] end
function GetNumAuctionItems(which) assert(which == "list") return #listingData, #listingData end
function CanSendAuctionQuery() return true, true end
function QueryAuctionItems(name, low, high, page, usable, quality, getAll)
    assert(getAll == true) requests = requests + 1
end
PlaceAuctionBid, StartAuction, CancelAuction = forbidden, forbidden, forbidden
