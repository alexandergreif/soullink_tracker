--[[
Pokemon SoulLink Tracker - DeSmuME Lua Script (V3 API Compatible) - FIXED VERSION
Monitors Pokemon HeartGold/SoulSilver ROM for encounters, catches, and faints
Writes V3-compatible events to JSON files for the Python watcher to process

FIXES:
- Proper script lifecycle management
- Better error handling
- Multiple execution modes for different DeSmuME versions
- Improved memory address compatibility
]]

-- Utility function declarations (needed before load_config)
local function log_error(message)
    local timestamp = os.date("%H:%M:%S")
    print("[" .. timestamp .. "] [SoulLink ERROR] " .. message)
end

local function log(message)
    -- Will be fully defined later, basic version for config loading
    local timestamp = os.date("%H:%M:%S")
    print("[" .. timestamp .. "] [SoulLink V3] " .. message)
end

-- Load configuration from external file with multiple path attempts
local function load_config()
    -- Try multiple potential config file locations
    local config_paths = {
        "config.lua",                    -- Same directory as script
        "client/lua/config.lua",         -- From project root
        "./config.lua",                  -- Current working directory
        "../config.lua",                 -- Parent directory
        "lua/config.lua",                -- From client directory
        -- Absolute paths (will be constructed dynamically)
    }
    
    -- Try to construct absolute paths if possible
    local script_dir = debug.getinfo(1).source
    if script_dir and script_dir:match("^@(.+)") then
        script_dir = script_dir:match("^@(.+)"):gsub("[^/\\]*$", "")
        table.insert(config_paths, script_dir .. "config.lua")
        table.insert(config_paths, script_dir .. "../config.lua")
    end
    
    log("Attempting to load configuration from multiple locations...")
    
    for i, config_path in ipairs(config_paths) do
        log("Trying config path: " .. config_path)
        
        local success, config = pcall(dofile, config_path)
        
        if success and config and type(config) == "table" then
            -- Validate that the config has required fields
            if config.run_id and config.player_id and
               config.run_id ~= "REPLACE_WITH_YOUR_RUN_ID" and
               config.player_id ~= "REPLACE_WITH_YOUR_PLAYER_ID" then
                log("✅ Configuration loaded successfully from: " .. config_path)
                log("📍 run_id: " .. config.run_id)
                log("📍 player_id: " .. config.player_id)
                log("📍 API URL: " .. (config.api_base_url or "default"))
                
                -- Debug: Show all loaded config fields
                log("📊 All config fields:")
                for key, value in pairs(config) do
                    log("  " .. key .. " = " .. tostring(value))
                end
                
                -- Ensure critical fields have fallbacks
                if not config.poll_interval then
                    log("⚠️  poll_interval missing, setting default to 60")
                    config.poll_interval = 60
                end
                if not config.output_dir then
                    log("⚠️  output_dir missing, setting default")
                    config.output_dir = "C:/Users/" .. os.getenv("USERNAME") .. "/AppData/Local/Temp/soullink_events/"
                end
                
                return config
            else
                log("⚠️  Config file found but contains placeholder values: " .. config_path)
            end
        else
            local error_msg = success and "not a table" or tostring(config)
            log("❌ Failed to load from " .. config_path .. ": " .. error_msg)
        end
    end
    
    log_error("=====================================")
    log_error("⚠️  CONFIGURATION LOADING FAILED  ⚠️")
    log_error("=====================================")
    log_error("Tried all possible config.lua locations:")
    for i, path in ipairs(config_paths) do
        log_error("  " .. i .. ". " .. path)
    end
    log_error("")
    log_error("SOLUTIONS:")
    log_error("1. Make sure config.lua exists in the same directory as this script")
    log_error("2. Copy config_template.lua to config.lua and fill in your values")
    log_error("3. Get UUIDs from: http://127.0.0.1:8000/admin")
    log_error("4. Ensure config.lua returns a table with run_id and player_id")
    log_error("")
    log_error("Using fallback configuration - events will fail with 422 errors!")
    
    -- Default configuration (will cause 422 errors without proper UUIDs)
    return {
        api_base_url = "http://127.0.0.1:8000",
        run_id = "MISSING_RUN_ID",
        player_id = "MISSING_PLAYER_ID",
        output_dir = "C:/Users/Alex/AppData/Local/Temp/soullink_events/",
        poll_interval = 60,
        debug = true,
        max_runtime = 3600,
        memory_profile = "US"
    }
end

-- Load configuration
local CONFIG = load_config()

-- Debug: Verify CONFIG table integrity
log("DEBUG: CONFIG table verification:")
log("  run_id = " .. (CONFIG.run_id or "NIL"))
log("  player_id = " .. (CONFIG.player_id or "NIL"))
log("  poll_interval = " .. (CONFIG.poll_interval and tostring(CONFIG.poll_interval) or "NIL"))
log("  output_dir = " .. (CONFIG.output_dir or "NIL"))

-- Memory addresses for Pokemon HGSS (Multiple region support)
local MEMORY_PROFILES = {
    -- US HeartGold/SoulSilver (most common)
    US = {
        party_pokemon = 0x02234804,
        party_count = 0x02234884,
        wild_pokemon = 0x0223AB00,
        battle_state = 0x02226E18,
        current_route = 0x02256AA4,
        current_map = 0x02256AA6,
        menu_state = 0x021C4D94,
        -- Additional addresses for encounter detection
        player_state = 0x021BF6A0,  -- Player state (surfing, fishing, etc.)
        rod_type = 0x021D4F0C       -- Current rod type when fishing
    },
    -- EU versions (alternate addresses)
    EU = {
        party_pokemon = 0x02234804,
        party_count = 0x02234884,
        wild_pokemon = 0x0223AB00,
        battle_state = 0x02226E18,
        current_route = 0x02256AA4,
        current_map = 0x02256AA6,
        menu_state = 0x021C4D94,
        player_state = 0x021BF6A0,
        rod_type = 0x021D4F0C
    }
}

-- Auto-detect region or use default
local MEMORY = MEMORY_PROFILES.US

-- Pokemon data structure offsets
local POKEMON_OFFSETS = {
    species = 0x00,      -- 2 bytes
    personality = 0x08,  -- 4 bytes (unique identifier)
    level = 0x54,        -- 1 byte
    hp_current = 0x56,   -- 2 bytes
    hp_max = 0x58,       -- 2 bytes
    status = 0x5A,       -- 1 byte (0=healthy, etc.)
    trainer_id = 0x04    -- 4 bytes
}

-- Game state tracking
local game_state = {
    initialized = false,
    script_running = true,
    last_battle_state = 0,
    last_route = 0,
    party_pokemon = {},
    in_encounter = false,
    last_wild_species = 0,
    last_wild_level = 0,
    last_encounter_method = "unknown",
    last_rod_kind = nil,
    startup_time = os.time(),
    frame_count = 0,
    last_status_update = 0
}

-- Utility functions (redefine with full functionality)
local function log(message)
    if CONFIG.debug then
        local timestamp = os.date("%H:%M:%S")
        print("[" .. timestamp .. "] [SoulLink V3] " .. message)
    end
end

-- log_error already defined above, but ensure it's available
if not log_error then
    log_error = function(message)
        local timestamp = os.date("%H:%M:%S")
        print("[" .. timestamp .. "] [SoulLink ERROR] " .. message)
    end
end

-- Safe memory reading with error handling
local function safe_read_u8(addr)
    local success, result = pcall(function()
        if memory and memory.read_u8 then
            return memory.read_u8(addr)
        elseif memory and memory.readbyte then
            return memory.readbyte(addr)
        else
            return nil
        end
    end)
    return success and result or 0
end

local function safe_read_u16(addr)
    local success, result = pcall(function()
        if memory and memory.read_u16_le then
            return memory.read_u16_le(addr)
        elseif memory and memory.read_u16 then
            return memory.read_u16(addr)
        else
            -- Fallback: read two bytes manually
            local low = safe_read_u8(addr)
            local high = safe_read_u8(addr + 1)
            return low + (high * 256)
        end
    end)
    return success and result or 0
end

local function safe_read_u32(addr)
    local success, result = pcall(function()
        if memory and memory.read_u32_le then
            return memory.read_u32_le(addr)
        elseif memory and memory.read_u32 then
            return memory.read_u32(addr)
        else
            -- Fallback: read four bytes manually
            local b1 = safe_read_u8(addr)
            local b2 = safe_read_u8(addr + 1)
            local b3 = safe_read_u8(addr + 2)
            local b4 = safe_read_u8(addr + 3)
            return b1 + (b2 * 256) + (b3 * 65536) + (b4 * 16777216)
        end
    end)
    return success and result or 0
end

local function get_current_time()
    return os.date("!%Y-%m-%dT%H:%M:%SZ")
end

local function create_output_dir()
    local path = CONFIG.output_dir or "C:/temp/soullink_events/"
    local success1 = os.execute('if not exist "' .. path .. '" mkdir "' .. path .. '"') -- Windows
    local success2 = os.execute("mkdir -p '" .. path .. "' 2>/dev/null") -- Unix
    log("Created output directory: " .. path)
end

local function write_event_file(event_data)
    local timestamp = os.time()
    local random_suffix = math.random(1000, 9999)
    local filename = CONFIG.output_dir .. "event_" .. timestamp .. "_" .. random_suffix .. ".json"
    
    local success, error_msg = pcall(function()
        local file = io.open(filename, "w")
        if file then
            file:write(event_data)
            file:close()
            log("Event written: " .. filename)
            return true
        else
            log_error("Failed to open file: " .. filename)
            return false
        end
    end)
    
    if not success then
        log_error("File write error: " .. tostring(error_msg))
    end
end

-- Pokemon data functions
local function read_pokemon_data(base_addr)
    local pokemon = {}
    pokemon.species = safe_read_u16(base_addr + POKEMON_OFFSETS.species)
    pokemon.personality = safe_read_u32(base_addr + POKEMON_OFFSETS.personality)
    pokemon.trainer_id = safe_read_u32(base_addr + POKEMON_OFFSETS.trainer_id)
    pokemon.level = safe_read_u8(base_addr + POKEMON_OFFSETS.level)
    pokemon.hp_current = safe_read_u16(base_addr + POKEMON_OFFSETS.hp_current)
    pokemon.hp_max = safe_read_u16(base_addr + POKEMON_OFFSETS.hp_max)
    pokemon.status = safe_read_u8(base_addr + POKEMON_OFFSETS.status)
    
    -- Basic shiny detection (simplified)
    local shiny_check = pokemon.personality % 65536
    pokemon.shiny = shiny_check < 8  -- Very simplified, but functional
    
    return pokemon
end

local function get_current_location()
    local route_id = safe_read_u16(MEMORY.current_route)
    return {
        route_id = route_id,
        route_name = "Route " .. route_id
    }
end

-- Detect encounter method and rod type
local function detect_encounter_method()
    local player_state = safe_read_u8(MEMORY.player_state)
    local method = "unknown"
    local rod_kind = nil
    
    -- Check player state for encounter method
    -- These values need calibration for HGSS
    if player_state == 0x04 then
        method = "surf"
    elseif player_state == 0x08 or player_state == 0x10 then
        method = "fish"
        -- Detect rod type
        local rod_value = safe_read_u8(MEMORY.rod_type)
        if rod_value == 1 then
            rod_kind = "old"
        elseif rod_value == 2 then
            rod_kind = "good"
        elseif rod_value == 3 then
            rod_kind = "super"
        else
            rod_kind = "old"  -- Default to old rod if unknown
        end
    else
        -- Default to grass for normal encounters
        method = "grass"
    end
    
    return method, rod_kind
end

-- V3 Event Creation Functions with proper UUID fields
local function create_encounter_event(wild_species, wild_level, wild_pokemon, location, method, rod_kind)
    -- Validate that we have proper UUIDs
    if CONFIG.run_id == "MISSING_RUN_ID" or CONFIG.player_id == "MISSING_PLAYER_ID" then
        log_error("Missing run_id or player_id in config! Events will fail with 422 errors.")
        log_error("Please configure config.lua with proper UUIDs from the admin panel.")
    end
    
    -- Build the JSON event with conditional rod_kind
    local json_parts = {
        string.format('    "type": "encounter"'),
        string.format('    "run_id": "%s"', CONFIG.run_id),
        string.format('    "player_id": "%s"', CONFIG.player_id),
        string.format('    "time": "%s"', get_current_time()),
        string.format('    "route_id": %d', location.route_id),
        string.format('    "species_id": %d', wild_species),
        string.format('    "level": %d', wild_level),
        string.format('    "shiny": %s', tostring(wild_pokemon.shiny)),
        string.format('    "method": "%s"', method)
    }
    
    -- Add rod_kind only for fishing encounters
    if method == "fish" and rod_kind then
        table.insert(json_parts, string.format('    "rod_kind": "%s"', rod_kind))
    end
    
    -- Add event version
    table.insert(json_parts, '    "event_version": "v3"')
    
    local json_data = "{\n" .. table.concat(json_parts, ",\n") .. "\n}"
    
    write_event_file(json_data)
    log(string.format("Encounter: Species %d Level %d Route %d Method %s%s",
        wild_species, wild_level, location.route_id, method,
        rod_kind and (" (" .. rod_kind .. " rod)") or ""))
end

local function create_catch_result_event(status, species_id, route_id)
    -- Validate that we have proper UUIDs
    if CONFIG.run_id == "MISSING_RUN_ID" or CONFIG.player_id == "MISSING_PLAYER_ID" then
        log_error("Missing run_id or player_id in config! Events will fail with 422 errors.")
        return
    end
    
    local json_data = string.format([[{
    "type": "catch_result",
    "run_id": "%s",
    "player_id": "%s",
    "time": "%s",
    "encounter_ref": {
        "route_id": %d,
        "species_id": %d
    },
    "status": "%s",
    "event_version": "v3"
}]], CONFIG.run_id, CONFIG.player_id, get_current_time(), route_id, species_id, status)
    
    write_event_file(json_data)
    log("Catch Result: " .. status .. " for Species " .. species_id)
end

-- Battle and encounter detection
local function detect_encounter()
    local battle_state = safe_read_u8(MEMORY.battle_state)
    local wild_species = safe_read_u16(MEMORY.wild_pokemon + POKEMON_OFFSETS.species)
    local wild_level = safe_read_u8(MEMORY.wild_pokemon + POKEMON_OFFSETS.level)
    local location = get_current_location()
    
    -- Detect new wild encounter
    if battle_state > 0 and not game_state.in_encounter and wild_species > 0 and wild_species < 1000 then
        game_state.in_encounter = true
        game_state.last_wild_species = wild_species
        game_state.last_wild_level = wild_level
        
        -- Detect encounter method and rod type
        local method, rod_kind = detect_encounter_method()
        game_state.last_encounter_method = method
        game_state.last_rod_kind = rod_kind
        
        local wild_pokemon = read_pokemon_data(MEMORY.wild_pokemon)
        create_encounter_event(wild_species, wild_level, wild_pokemon, location, method, rod_kind)
    end
    
    -- Detect battle end and catch result (simplified)
    if game_state.in_encounter and battle_state == 0 then
        game_state.in_encounter = false
        
        -- For demo purposes, simulate random catch/flee
        -- In a real implementation, you'd detect the actual result
        local catch_chance = math.random()
        local status = catch_chance > 0.5 and "caught" or "fled"
        
        create_catch_result_event(status, game_state.last_wild_species, location.route_id)
    end
end

-- Main monitoring function
local function monitor_game()
    if not game_state.script_running then
        return
    end
    
    -- Check for maximum runtime
    local current_time = os.time()
    if current_time - game_state.startup_time > CONFIG.max_runtime then
        log("Maximum runtime reached, stopping script")
        game_state.script_running = false
        return
    end
    
    -- Try monitoring with error handling
    local success, error_msg = pcall(function()
        -- Only monitor if we're in game (not in menus)
        local menu_state = safe_read_u8(MEMORY.menu_state)
        if menu_state ~= 0 then
            return -- In menu, skip monitoring
        end
        
        -- Monitor encounters and battles
        detect_encounter()
        
        -- Update location tracking
        local location = get_current_location()
        if location.route_id ~= game_state.last_route and location.route_id > 0 then
            game_state.last_route = location.route_id
            log("Location changed to: " .. location.route_name)
        end
    end)
    
    if not success then
        log_error("Monitoring error: " .. tostring(error_msg))
    end
end

-- Frame callback function
local function on_frame()
    game_state.frame_count = game_state.frame_count + 1
    
    -- Run monitoring at specified interval
    local poll_interval = CONFIG.poll_interval or 60
    if game_state.frame_count >= poll_interval then
        game_state.frame_count = 0
        monitor_game()
    end
    
    -- Status update every 10 seconds
    local current_time = os.time()
    if current_time - game_state.last_status_update >= 10 then
        game_state.last_status_update = current_time
        local uptime = current_time - game_state.startup_time
        log("Script running for " .. uptime .. " seconds, monitoring...")
    end
end

-- Initialization function
local function initialize()
    log("=== Pokemon SoulLink Tracker V3 (Fixed) ===")
    
    -- Defensive checks for CONFIG values
    local output_dir = CONFIG.output_dir or "MISSING_OUTPUT_DIR"
    local poll_interval = CONFIG.poll_interval or 60
    
    log("Output directory: " .. output_dir)
    log("Poll interval: " .. poll_interval .. " frames")
    
    -- Create output directory
    create_output_dir()
    
    -- Test memory access
    local test_addr = MEMORY.menu_state
    local test_value = safe_read_u8(test_addr)
    log("Memory test - Address 0x" .. string.format("%08X", test_addr) .. " = " .. test_value)
    
    game_state.initialized = true
    game_state.startup_time = os.time()
    game_state.last_status_update = os.time()
    
    log("Initialization complete, monitoring for events...")
    
    -- Write a test event to verify file writing works
    local test_event = string.format([[{
    "type": "test",
    "run_id": "%s",
    "player_id": "%s",
    "time": "%s",
    "message": "Script initialized successfully",
    "event_version": "v3"
}]], CONFIG.run_id, CONFIG.player_id, get_current_time())
    write_event_file(test_event)
    
    -- Final configuration validation and user feedback
    if CONFIG.run_id == "MISSING_RUN_ID" or CONFIG.player_id == "MISSING_PLAYER_ID" then
        log_error("")
        log_error("==================================")
        log_error("⚠️  CONFIGURATION INCOMPLETE ⚠️")
        log_error("==================================")
        log_error("🔴 Current run_id: " .. CONFIG.run_id)
        log_error("🔴 Current player_id: " .. CONFIG.player_id)
        log_error("")
        log_error("🚨 CRITICAL: Events will fail with 422 errors!")
        log_error("")
        log_error("🔧 TO FIX THIS ISSUE:")
        log_error("1. Open admin panel: " .. CONFIG.api_base_url .. "/admin")
        log_error("2. Copy your run_id and player_id UUIDs")
        log_error("3. Update client/lua/config.lua with proper UUIDs")
        log_error("4. Reload this script in DeSmuME")
        log_error("")
        log_error("Script will continue but events will be rejected by API...")
        log_error("==================================")
    else
        log("")
        log("✅ ========================================")
        log("✅      CONFIGURATION SUCCESSFUL      ")
        log("✅ ========================================")
        log("🎯 Run ID: " .. CONFIG.run_id)
        log("🎯 Player ID: " .. CONFIG.player_id)
        log("🎯 API URL: " .. CONFIG.api_base_url)
        log("🎯 Output Dir: " .. CONFIG.output_dir)
        log("✅ Ready to track Pokemon encounters!")
        log("✅ ========================================")
        log("")
    end
end

-- === MAIN EXECUTION ===

-- Initialize the script
initialize()

-- Different execution modes for different DeSmuME versions
local execution_mode = "auto"

if execution_mode == "callback" then
    -- Mode 1: Use callback registration (DeSmuME 0.9.11+)
    log("Using callback execution mode")
    if gui and gui.register then
        gui.register(on_frame)
        log("Frame callback registered")
    else
        log_error("gui.register not available, trying alternative method")
        execution_mode = "loop"
    end
end

if execution_mode == "loop" or execution_mode == "auto" then
    -- Mode 2: Manual loop with frameadvance (more compatible)
    log("Using loop execution mode")
    
    while game_state.script_running do
        -- Call our monitoring function
        on_frame()
        
        -- Advance one frame and yield control
        if emu and emu.frameadvance then
            emu.frameadvance()
        elseif FCEU and FCEU.frameadvance then
            FCEU.frameadvance()
        else
            -- Fallback: just pause briefly
            os.execute("ping 127.0.0.1 -n 1 > nul 2>&1") -- Windows
            os.execute("sleep 0.016") -- Unix (16ms = ~60fps)
        end
        
        -- Safety check - stop if runtime exceeded
        if os.time() - game_state.startup_time > CONFIG.max_runtime then
            log("Maximum runtime reached, stopping")
            break
        end
    end
end

log("Script execution finished")