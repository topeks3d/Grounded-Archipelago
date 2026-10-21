-- ap_json.lua
--
-- Small JSON encoder/decoder (UE4SS's Lua has no guaranteed JSON library).
-- Covers the shapes used in the IPC files, not general-purpose JSON.

local json = {}

-- ---------------------------------------------------------------------
-- Encode
-- ---------------------------------------------------------------------

local function is_array(t)
    if type(t) ~= "table" then return false end
    local n = 0
    for _ in pairs(t) do n = n + 1 end
    if n == 0 then return true end -- treat empty table as empty array
    for i = 1, n do
        if t[i] == nil then return false end
    end
    return true
end

local escapes = {
    ['"'] = '\\"', ['\\'] = '\\\\', ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t',
}

local function encode_string(s)
    return '"' .. s:gsub('[%c"\\]', function(c) return escapes[c] or string.format("\\u%04x", c:byte()) end) .. '"'
end

local encode_value -- forward decl

local function encode_array(t)
    local parts = {}
    for i = 1, #t do
        parts[i] = encode_value(t[i])
    end
    return "[" .. table.concat(parts, ",") .. "]"
end

local function encode_object(t)
    local parts = {}
    for k, v in pairs(t) do
        parts[#parts + 1] = encode_string(tostring(k)) .. ":" .. encode_value(v)
    end
    return "{" .. table.concat(parts, ",") .. "}"
end

encode_value = function(v)
    local t = type(v)
    if t == "string" then
        return encode_string(v)
    elseif t == "number" then
        return tostring(v)
    elseif t == "boolean" then
        return v and "true" or "false"
    elseif t == "nil" then
        return "null"
    elseif t == "table" then
        if is_array(v) then
            return encode_array(v)
        else
            return encode_object(v)
        end
    end
    error("ap_json: cannot encode value of type " .. t)
end

function json.encode(value)
    return encode_value(value)
end

-- ---------------------------------------------------------------------
-- Decode (recursive descent)
-- ---------------------------------------------------------------------

local function skip_ws(s, i)
    local _, j = s:find("^[ \t\r\n]*", i)
    return j + 1
end

local decode_value -- forward decl

local function decode_string(s, i)
    assert(s:sub(i, i) == '"', "ap_json: expected string")
    local j = i + 1
    local out = {}
    while true do
        local c = s:sub(j, j)
        if c == "" then error("ap_json: unterminated string") end
        if c == '"' then
            return table.concat(out), j + 1
        elseif c == "\\" then
            local nc = s:sub(j + 1, j + 1)
            local map = { n = "\n", r = "\r", t = "\t", ['"'] = '"', ["\\"] = "\\", ["/"] = "/" }
            if map[nc] then
                out[#out + 1] = map[nc]
                j = j + 2
            elseif nc == "u" then
                local hex = s:sub(j + 2, j + 5)
                out[#out + 1] = string.char(tonumber(hex, 16) % 256)
                j = j + 6
            else
                out[#out + 1] = nc
                j = j + 2
            end
        else
            out[#out + 1] = c
            j = j + 1
        end
    end
end

local function decode_array(s, i)
    local t = {}
    local n = 0
    i = skip_ws(s, i + 1)
    if s:sub(i, i) == "]" then return t, i + 1 end
    while true do
        local value
        value, i = decode_value(s, i)
        n = n + 1
        t[n] = value
        i = skip_ws(s, i)
        local c = s:sub(i, i)
        if c == "," then
            i = skip_ws(s, i + 1)
        elseif c == "]" then
            return t, i + 1
        else
            error("ap_json: expected ',' or ']' in array")
        end
    end
end

local function decode_object(s, i)
    local t = {}
    i = skip_ws(s, i + 1)
    if s:sub(i, i) == "}" then return t, i + 1 end
    while true do
        local key
        key, i = decode_string(s, i)
        i = skip_ws(s, i)
        assert(s:sub(i, i) == ":", "ap_json: expected ':' in object")
        i = skip_ws(s, i + 1)
        local value
        value, i = decode_value(s, i)
        t[key] = value
        i = skip_ws(s, i)
        local c = s:sub(i, i)
        if c == "," then
            i = skip_ws(s, i + 1)
        elseif c == "}" then
            return t, i + 1
        else
            error("ap_json: expected ',' or '}' in object")
        end
    end
end

decode_value = function(s, i)
    i = skip_ws(s, i)
    local c = s:sub(i, i)
    if c == '"' then
        return decode_string(s, i)
    elseif c == "{" then
        return decode_object(s, i)
    elseif c == "[" then
        return decode_array(s, i)
    elseif c == "t" and s:sub(i, i + 3) == "true" then
        return true, i + 4
    elseif c == "f" and s:sub(i, i + 4) == "false" then
        return false, i + 5
    elseif c == "n" and s:sub(i, i + 3) == "null" then
        return nil, i + 4
    else
        local numstr = s:match("^%-?%d+%.?%d*[eE]?[%+%-]?%d*", i)
        if numstr and #numstr > 0 then
            return tonumber(numstr), i + #numstr
        end
        error("ap_json: unexpected character '" .. c .. "' at position " .. i)
    end
end

function json.decode(s)
    if not s or s == "" then return nil end
    local ok, value = pcall(function()
        local v, _ = decode_value(s, 1)
        return v
    end)
    if not ok then
        return nil, value
    end
    return value
end

return json
