-- Offline WoW API surface for executing the actual addon in Lua 5.1.
clock, requests, referenceCalls, instantCalls, messages = 0, 0, {}, {}, {}
SlashCmdList = {}
WOW_PROJECT_ID = 99
AuctionHouseFrame = { shown = true }
function AuctionHouseFrame:IsShown() return self.shown end
StaticPopupDialogs = {}
CANCEL = "Cancel"
reloads = 0
function ReloadUI() reloads = reloads + 1 end
function StaticPopup_Show(which, arg1, arg2, data)
    local definition = StaticPopupDialogs[which]
    popup = { which = which, data = data, text = definition.text:format(arg1), shown = true }
    function popup:Accept()
        assert(self.shown)
        self.shown = false
        definition.OnAccept(self, self.data)
    end
    function popup:Cancel()
        assert(self.shown)
        self.shown = false
        if definition.OnCancel then definition.OnCancel(self, self.data) end
    end
    return popup
end
function StaticPopup_Hide(which)
    if popup and popup.which == which then popup.shown = false end
end
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
UIParent = { IsShown = function() return true end }
UISpecialFrames = {}
Minimap = { IsShown = function() return true end,
    GetCenter = function() return 100, 100 end, GetEffectiveScale = function() return 2 end }
cursorX, cursorY = 360, 200
function GetCursorPosition() return cursorX, cursorY end
local function region()
    local r = {}
    function r:SetText(text) self.text = text end
    function r:SetSize(width, height) self.width, self.height = width, height end
    function r:SetPoint(...) self.point = { ... } end
    function r:SetJustifyH(value) self.justifyH = value end
    function r:SetJustifyV(value) self.justifyV = value end
    function r:SetTextColor(...) self.color = { ... } end
    function r:SetTexture(value) self.texture = value end
    function r:SetTexCoord(...) self.texCoord = { ... } end
    return r
end
GameTooltip = region()
function GameTooltip:SetOwner(owner, anchor) self.owner, self.anchor = owner, anchor; self.lines = {} end
function GameTooltip:AddLine(text) self.lines[#self.lines + 1] = text end
function GameTooltip:Show() self.shown = true end
function GameTooltip:Hide() self.shown = false end
function CreateFrame(kind, name, parent, template)
    local f = { scripts = {}, parent = parent, template = template, enabled = true }
    function f:RegisterEvent(event) end
    function f:SetScript(event, callback) self.scripts[event] = callback end
    function f:SetSize(width, height) self.width, self.height = width, height end
    function f:SetText(text) self.text = text end
    function f:SetPoint(...) self.point = { ... } end
    function f:Enable() self.enabled = true end
    function f:Disable() self.enabled = false end
    function f:IsShown() return self.shown ~= false and (not self.parent or self.parent:IsShown()) end
    function f:Show() self.shown = true; if self.scripts.OnShow then self.scripts.OnShow(self) end end
    function f:Hide()
        self.shown = false
        if self.scripts.OnHide then self.scripts.OnHide(self) end
    end
    function f:SetMovable(value) self.movable = value end
    function f:SetClampedToScreen(value) self.clamped = value end
    function f:EnableMouse(value) self.mouse = value end
    function f:RegisterForDrag(...) self.dragButtons = { ... } end
    function f:RegisterForClicks(...) self.clickButtons = { ... } end
    function f:StartMoving() self.moving = true end
    function f:StopMovingOrSizing() self.moving = false end
    function f:SetFrameStrata(value) self.strata = value end
    function f:ClearAllPoints() self.point = nil end
    f.fontStrings = {}
    function f:CreateFontString()
        local text = region()
        self.fontStrings[#self.fontStrings + 1] = text
        return text
    end
    function f:CreateTexture() return region() end
    function f:SetNormalTexture(value) self.normal = region(); self.normal:SetTexture(value) end
    function f:GetNormalTexture() return self.normal end
    function f:SetHighlightTexture(value) self.highlight = value end
    function f:Click()
        if self.enabled and self:IsShown() then self.scripts.OnClick(self) end
    end
    if name then _G[name] = f end
    if template == "BasicFrameTemplateWithInset" then
        f.TitleText = region()
        f.CloseButton = { Click = function() f:Hide() end }
    end
    if kind == "Frame" and not name then mainFrame = f
    elseif name == "BrownstoneScanButton" then scanButton = f
    elseif name == "BrownstoneScanReloadButton" then reloadButton = f
    elseif name == "BrownstoneScanClearButton" then clearButton = f end
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
