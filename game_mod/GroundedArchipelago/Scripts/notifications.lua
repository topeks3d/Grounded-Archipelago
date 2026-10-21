-- notifications.lua
--
-- On-screen AP messages (received / sent items, hints, DeathLinks). With
-- config.notification_style "overlay" (default) the Grounded Client draws
-- them over the game and the HUD stays quiet. Otherwise: the key-item
-- banner ("banner", show_popup), or a coloured, large-font line in the HUD's
-- notification feed (UI_NotificationLog_C:AddGenericNotification, held on
-- screen longer via TemporaryNotificationDisplayTime), falling back to
-- AGameUI:PostGenericMessage. Everything is also logged.

local M = {}

local objects = require("ap_objects")

local HOLD_SECONDS = 10

local COLORS = {
    received = {R = 255, G = 200, B = 40, A = 255},
    sent = {R = 110, G = 205, B = 255, A = 255},
    hint = {R = 200, G = 150, B = 255, A = 255},
    deathlink = {R = 255, G = 85, B = 85, A = 255},
    other = {R = 255, G = 255, B = 255, A = 255},
}

local function log(fmt, ...)
    print(string.format("[GroundedArchipelago] " .. fmt .. "\n", ...))
end

local function color_for(text)
    if text:find("^Received") or text:find("^Found your") then
        return COLORS.received
    elseif text:find("^Sent") then
        return COLORS.sent
    elseif text:find("^Hint") then
        return COLORS.hint
    elseif text:find("DeathLink") then
        return COLORS.deathlink
    end
    return COLORS.other
end

-- Several UI_NotificationLog_C exist (shopping list, photo mode, chat, and
-- the /Game/... templates); picking the first one sent every message into
-- the shopping list's hidden copy. The on-screen feed is the live HUD's
-- "...UI_HUD_C_<n>.WidgetTree.TemporaryNotificationLog" (object dump).
local function find_notification_log()
    return objects.find_matching("AP notification log", "UI_NotificationLog_C", function(widget)
        local name = widget:GetFullName()
        return name:find("/Engine/Transient", 1, true) ~= nil
            and name:find("UI_HUD_C", 1, true) ~= nil
            and name:find("TemporaryNotificationLog", 1, true) ~= nil
    end)
end

local function line_count(widget)
    local ok, n = pcall(function() return widget.LogList:GetChildrenCount() end)
    return ok and n or nil
end

-- Longer display time -----------------------------------------------------
local original_display_time = nil -- vanilla value while raised, else nil
local raised_widget = nil
local hold_until = 0

local function hold_longer(widget)
    hold_until = os.time() + HOLD_SECONDS + 1
    if original_display_time then
        return
    end
    local ok, current = pcall(function() return widget.TemporaryNotificationDisplayTime end)
    if ok and type(current) == "number" and current < HOLD_SECONDS then
        if pcall(function() widget.TemporaryNotificationDisplayTime = HOLD_SECONDS end) then
            original_display_time = current
            raised_widget = widget
        end
    end
end

-- Called every poll tick: puts the vanilla display time back once no AP
-- message has been shown for a while.
function M.tick()
    if original_display_time and os.time() >= hold_until then
        if objects.is_valid(raised_widget) then
            pcall(function() raised_widget.TemporaryNotificationDisplayTime = original_display_time end)
        end
        original_display_time = nil
        raised_widget = nil
    end
end

-- Large font on the line just added. Returns true if that line was found.
local function enlarge(widget, text, out)
    local candidates = {}
    if type(out) == "table" then
        candidates[#candidates + 1] = out.Notification or out[1]
    end
    pcall(function()
        local list = widget.LogList
        for i = 0, list:GetChildrenCount() - 1 do
            candidates[#candidates + 1] = list:GetChildAt(i)
        end
    end)
    for _, child in ipairs(candidates) do
        local matched = pcall(function()
            if child.Text:GetText():ToString() ~= text then
                error("different line")
            end
            child:SetLargeFont()
        end)
        if matched then
            return true
        end
    end
    return false
end

local warned_rich = false
local logged_widget = false

local function show_rich(text)
    local widget = find_notification_log()
    if not widget then
        if not warned_rich then
            warned_rich = true
            log("HUD notification feed (UI_HUD_C ... TemporaryNotificationLog) not found -- using the plain " ..
                "HUD message.")
        end
        return false
    end
    hold_longer(widget) -- before adding, in case the line's timer starts from it
    local before = line_count(widget)
    local out = {}
    local ok, err = pcall(function()
        widget:AddGenericNotification(FText(text), color_for(text), nil, out)
    end)
    if ok then
        -- Only trust the call if the line is really there: the text matched
        -- (and got the large font), or the feed grew.
        local found = select(2, pcall(enlarge, widget, text, out)) == true
        local after = line_count(widget)
        if not found and not (before and after and after > before) then
            ok, err = false, string.format("no new line appeared (%s -> %s lines)", tostring(before), tostring(after))
        end
    end
    if not ok then
        if not warned_rich then
            warned_rich = true
            log("Colored notifications unavailable (%s) -- using the plain HUD message.", tostring(err))
        end
        return false
    end
    if not logged_widget then
        logged_widget = true
        local name_ok, name = pcall(function() return widget:GetFullName() end)
        log("Notifications go to %s", name_ok and tostring(name) or "?")
    end
    return true
end

local warned_no_hud = false

local function show_plain(text)
    local hud = objects.find_first("GameUI")
    if not hud then
        return false
    end
    local ok, err = pcall(function() hud:PostGenericMessage(text, nil) end)
    if not ok and not warned_no_hud then
        warned_no_hud = true
        log("Couldn't show on-screen messages (GameUI:PostGenericMessage failed: %s) -- they'll only " ..
            "appear in this log.", tostring(err))
    end
    return ok
end

-- Banner ---------------------------------------------------------------------
-- The game's key-item banner (UI_KeyItemNotification_C) via the HUD's
-- queue (UI_KeyNotificationLog_C:CreateKeyItemNotification): headline in
-- ItemText, detail in FoundText, icon via SetData when we know the item row.
-- Off for the session after the first failure (feed lines take over).
local ok_config, config = pcall(require, "config")
config = ok_config and type(config) == "table" and config or {}
-- config.notification_style: "overlay" (default) -- the Grounded Client
-- draws the cards over the game and the HUD stays quiet (feed lines when
-- the client's overlay is off); "banner" -- the key-item banner below;
-- "feed" -- only the small feed lines.
local STYLE = config.notification_style or (config.popup_notifications == true and "banner") or "overlay"
local BANNER_SECONDS = tonumber(config.banner_seconds) or 3
local popup_failed = false
local overlay_active = false

-- Called every tick with to_game.json's overlay_notifications.
function M.set_overlay(active)
    overlay_active = active == true
end

local function find_key_log()
    return objects.find_matching("AP key notification log", "UI_KeyNotificationLog_C", function(widget)
        local name = widget:GetFullName()
        return name:find("/Engine/Transient", 1, true) ~= nil and name:find("UI_HUD_C", 1, true) ~= nil
    end)
end

local function key_item_widgets()
    local found = {}
    local ok, list = pcall(FindAllOf, "UI_KeyItemNotification_C")
    if ok and list then
        for _, widget in ipairs(list) do
            pcall(function() found[widget:GetAddress()] = widget end)
        end
    end
    return found
end

local function set_text(text_block, text)
    text_block:SetText(FText(text))
end

local function show_popup(text, detail, icon_row)
    if STYLE ~= "banner" or popup_failed then
        return false
    end
    local key_log = find_key_log()
    if not key_log then
        return false -- HUD not up yet; try again next time
    end
    local before = key_item_widgets()
    local out = {}
    local ok, err = pcall(function() key_log:CreateKeyItemNotification(out) end)
    local widget = nil
    if ok then
        pcall(function()
            if objects.is_valid(out.Widget) then
                widget = out.Widget
            end
        end)
        if not widget then
            for address, candidate in pairs(key_item_widgets()) do
                if not before[address] then
                    widget = candidate
                end
            end
        end
        if not widget then
            ok, err = false, "no popup widget appeared"
        end
    end
    if ok and icon_row then
        -- The game's own setup for an item (icon, colours); our text goes in after.
        pcall(function()
            local item_grants = require("item_grants")
            local controller = item_grants.get_local_player_controller()
            widget:SetData({DataTable = item_grants.get_item_data_table(), RowName = FName(icon_row)},
                controller.PlayerState, {})
        end)
    elseif ok then
        pcall(function() widget.ItemIcon:SetVisibility(2) end) -- Hidden: no game item to show
    end
    if ok then
        ok, err = pcall(function()
            set_text(widget.ItemText, text)
            set_text(widget.FoundText, detail ~= "" and detail or "Archipelago")
            if widget.ItemText:GetText():ToString() ~= text then
                error("the popup's text didn't change")
            end
        end)
        pcall(function() widget.PlayerNameHorizontalBox:SetVisibility(1) end) -- Collapsed
        -- Shorter than the game's own key-item banners, so a queue moves on.
        pcall(function()
            widget.TimeLeftToShow = BANNER_SECONDS
            widget.MinimumDisplayTime = math.min(1.5, BANNER_SECONDS)
        end)
    end
    if not ok then
        popup_failed = true
        log("In-game popup unavailable (%s) -- using the notification feed instead.", tostring(err))
        return false
    end
    return true
end

-- Shows `text` right now -- as a popup with `detail` under it (and the
-- icon of item row `icon_row`) when possible, else as a feed line.
-- Returns true if the HUD accepted it.
function M.show(text, detail, icon_row)
    detail = detail or ""
    if STYLE == "overlay" and overlay_active then
        log("NOTIFY (client overlay): %s%s", text, detail ~= "" and (" | " .. detail) or "")
        return true
    end
    log("NOTIFY: %s%s", text, detail ~= "" and (" | " .. detail) or "")
    if show_popup(text, detail, icon_row) then
        return true
    end
    local line = detail ~= "" and (text .. " -- " .. detail) or text
    return show_rich(line) or show_plain(line)
end

-- The mod's own messages (not AP traffic the client already shows): always
-- in the HUD feed.
function M.show_local(text)
    log("NOTIFY: %s", text)
    return show_rich(text) or show_plain(text)
end

-- Client notifications ({id, text, detail, icon_row}) newer than
-- ipc.last_notification_id; only call in the Archipelago world. A long
-- backlog is summarized.
local MAX_PER_TICK = 4

function M.show_pending(ipc, notifications)
    local pending = {}
    for _, entry in ipairs(notifications or {}) do
        if type(entry.id) == "number" and entry.id > ipc.last_notification_id then
            pending[#pending + 1] = entry
        end
    end
    if #pending == 0 then
        return
    end
    if #pending > MAX_PER_TICK then
        for i = 1, #pending - (MAX_PER_TICK - 1) do
            log("NOTIFY (summarized): %s", tostring(pending[i].text))
        end
        M.show(string.format("Archipelago: %d earlier messages (see the client)", #pending - (MAX_PER_TICK - 1)))
        pending = { table.unpack(pending, #pending - (MAX_PER_TICK - 2), #pending) }
    end
    for _, entry in ipairs(pending) do
        M.show(tostring(entry.text), type(entry.detail) == "string" and entry.detail or "",
            type(entry.icon_row) == "string" and entry.icon_row ~= "" and entry.icon_row or nil)
    end
    ipc:mark_notification_shown(notifications[#notifications].id)
end

return M
