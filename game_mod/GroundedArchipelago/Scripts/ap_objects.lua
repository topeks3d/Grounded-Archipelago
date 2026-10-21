-- ap_objects.lua
--
-- Cached FindFirstOf / FindAllOf. Both walk the whole object array (a
-- once-a-second hitch with ~10 lookups per tick); the objects looked up live
-- for a session, so each is reused while IsValid(). Misses are remembered
-- for MISS_RETRY_SECONDS, since a miss is the most expensive scan.

local M = {}

local MISS_RETRY_SECONDS = 2

local cache = {}      -- class name -> object
local last_miss = {}  -- class name -> os.time() of the last failed scan

local function is_valid(obj)
    if not obj then
        return false
    end
    local ok, valid = pcall(function() return obj:IsValid() end)
    return ok and valid == true
end
M.is_valid = is_valid

local function recently_missed(key)
    local t = last_miss[key]
    return t ~= nil and os.difftime(os.time(), t) < MISS_RETRY_SECONDS
end

-- Drop-in for FindFirstOf(class_name): returns the object or nil.
function M.find_first(class_name)
    local cached = cache[class_name]
    if is_valid(cached) then
        return cached
    end
    cache[class_name] = nil
    if recently_missed(class_name) then
        return nil
    end
    local ok, obj = pcall(FindFirstOf, class_name)
    if ok and is_valid(obj) then
        cache[class_name] = obj
        last_miss[class_name] = nil
        return obj
    end
    last_miss[class_name] = os.time()
    return nil
end

-- Returns the first valid object of `class_name` for which pred(obj) is
-- true (FindAllOf + filter), cached the same way under `key`.
function M.find_matching(key, class_name, pred)
    local cached = cache[key]
    if is_valid(cached) then
        return cached
    end
    cache[key] = nil
    if recently_missed(key) then
        return nil
    end
    local ok, objects = pcall(FindAllOf, class_name)
    if ok and objects then
        for _, obj in ipairs(objects) do
            if is_valid(obj) then
                local pred_ok, matched = pcall(pred, obj)
                if pred_ok and matched then
                    cache[key] = obj
                    last_miss[key] = nil
                    return obj
                end
            end
        end
    end
    last_miss[key] = os.time()
    return nil
end

return M
