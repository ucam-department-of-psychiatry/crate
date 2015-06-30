--[[ $%BEGINLICENSE%$

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

 $%ENDLICENSE%$ --]]

local client_addr = ""
local user = ""
local schema = ""

function read_handshake()
    client_addr = proxy.connection.client.src.name
end

function read_auth()
	user = proxy.connection.client.username
    set_flush()  -- good time to do this
end

function read_query(packet)
    local cmd = packet:byte()

	if cmd == proxy.COM_QUERY then
        --[[
            Better to read the default_db (schema) at this point.
            If we watch for cmd == proxy.COM_INIT_DB, and set
            schema = packet:sub(2), then we end up accepting garbage, because
            the user can do "USE nonexistent_db;".
        --]]
        set_schema("")
        audit(packet:sub(2))

    elseif cmd == proxy.COM_INIT_DB then
        --[[
            May be wrong, e.g. if user does "USE nonexistent_db;"
            However, SQL Squirrel doesn't seem to set
            proxy.connection.client.default_db, and it still works!
            We'll set this one as a guess in case we get nothing better.
        --]]
        set_schema(packet:sub(2))

    -- else
    --     log("command: " .. cmd)

	end
end

function isempty(s)
  return s == nil or s == ''
end

function set_schema(client_request)
    pref1 = proxy.connection.client.default_db
    pref2 = proxy.connection.server.default_db
    pref3 = client_request
    if not isempty(pref1) then
        schema = pref1
    elseif not isempty(pref2) then
        schema = pref2
    else
        schema = pref3
    end
end

function now()
    return os.date("%FT%T%z")  -- ISO 8601 in local timezone, with TZ
    --[[
        local now = os.date("!%Y-%m-%dT%TZ") -- ISO 8601 in UTC
        local now = os.date("%FT%T%z")  -- ISO 8601 in local timezone, with TZ

        http://www.lua.org/manual/5.2/manual.html#pdf-os.date
        http://man7.org/linux/man-pages/man3/strftime.3.html
        http://stackoverflow.com/questions/463101

        No way of doing sub-second precision yet found.
        Possible to garbage-graft the fractional time since Lua started to the
        system clock; http://help.interfaceware.com/kb/1265;
            local time_second, time_subsecond = math.modf(os.clock())
        ... but it is partly junk.
        Note that os.clock(), though fractional, is CPU time, not clock time.
    --]]
end

function set_flush()
    -- Without any extra work, stdout is NOT flushed by default, so it will
    -- lag. Good for performance. However, if we want it flushed:
    io.stdout:setvbuf("line")  -- flush stdout at end of every line
    io.stderr:setvbuf("line")  -- flush stderr at end of every line
end

function escape(x)
    --[[
        SQL queries can have newlines in. In the output, they're the last field
        of the CSV, so anything is fine except newlines. If we want the output
        to be valid and identical SQL, though, we can't (e.g.) replace newlines
        with spaces; they might have been inside a string literal.
        See also:
            http://stackoverflow.com/questions/28795538
                ... using a replacement table
            http://stackoverflow.com/questions/10156207
                ... string literals
        However, it's probably more helpful to use a space; this is an audit
        tool, not an SQL tool.
    --]]
    -- return x:gsub("\n", [[\n]])
    return x:gsub("\n", " ")
end

function audit(query)
    query = escape(query)
	print(now()
          .. "," .. client_addr
          .. "," .. user
          .. "," .. schema
          .. "," .. query)
end

function log(msg)
    io.stderr:write(now()
                    .. ": " .. client_addr
                    .. "," .. user
                    .. ": " .. msg .. "\n")
end
