-- Pokemon SoulLink Tracker - Debug Version
-- This script logs detailed information to help diagnose encounter detection issues

-- Try to load configuration
local function load_config()
    local config_paths = {
        "config.lua",
        "./config.lua",
        "client/lua/config.lua",
        "../config.lua",
        "../../config.lua"
    }
    
    for _, path in ipairs(config_paths) do
        local success, result = pcall(dofile, path)
        if success and type(result) == "table" then
            print("[CONFIG] Loaded from: " .. path)
            return result
        end
    end
    
    print("[CONFIG] Using fallback configuration")
    return {
        api_base_url = "http://127.0.0.1:8000",
        run_id = "MISSING_RUN_ID",
        player_id = "MISSING_PLAYER_ID",
        output_dir = "C:/Users/Alex/AppData/Local/Temp/soullink_events/",
        poll_interval = 30,  -- Check more frequently for debugging
        debug = true
    }
end

local CONFIG = load_config()
print("[CONFIG] Output directory: " .. CONFIG.output_dir)

-- Memory addresses for Pokemon HGSS
local MEMORY = {
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

-- Alternative memory addresses to try (EU version)
local MEMORY_ALT = {
    battle_state = 0x02226E1C,  -- Sometimes off by 4 bytes
    wild_pokemon = 0x0223AB04,
}

-- Pokemon data offsets
local POKEMON_OFFSETS = {
    species = 0x00,
    level = 0x54
}

-- State tracking
local state = {
    frame_count = 0,
    last_battle_state = 0,
    last_wild_species = 0,
    debug_log_count = 0,
    in_encounter = false
}

-- Safe memory reading
local function safe_read_u8(addr)
    if addr and addr > 0 then
        return memory.readbyte(addr)
    end
    return 0
end

local function safe_read_u16(addr)
    if addr and addr > 0 then
        return memory.readword(addr)
    end
    return 0
end

-- Write debug log to file
local function write_debug_log(message)
    local timestamp = os.time()
    local filename = CONFIG.output_dir .. "debug_" .. timestamp .. "_" .. state.debug_log_count .. ".txt"
    state.debug_log_count = state.debug_log_count + 1
    
    local file = io.open(filename, "w")
    if file then
        file:write("=== Pokemon Tracker Debug Log ===\n")
        file:write("Time: " .. os.date("%Y-%m-%d %H:%M:%S") .. "\n")
        file:write("Message: " .. message .. "\n")
        file:close()
        print("[DEBUG] Log written: " .. filename)
    else
        print("[ERROR] Cannot write to: " .. filename)
        print("[ERROR] Check if directory exists: " .. CONFIG.output_dir)
    end
end

-- Main debug monitoring
local function debug_monitor()
    -- Read memory values
    local battle_state = safe_read_u8(MEMORY.battle_state)
    local battle_state_alt = safe_read_u8(MEMORY_ALT.battle_state)
    local wild_species = safe_read_u16(MEMORY.wild_pokemon + POKEMON_OFFSETS.species)
    local wild_species_alt = safe_read_u16(MEMORY_ALT.wild_pokemon + POKEMON_OFFSETS.species)
    local wild_level = safe_read_u8(MEMORY.wild_pokemon + POKEMON_OFFSETS.level)
    local menu_state = safe_read_u8(MEMORY.menu_state)
    local current_route = safe_read_u16(MEMORY.current_route)
    local party_count = safe_read_u8(MEMORY.party_count)
    
    -- Log detailed state every 60 frames (1 second)
    if state.frame_count % 60 == 0 then
        local debug_info = string.format(
            "Frame %d | Battle: %d (alt: %d) | Wild Species: %d (alt: %d) | Level: %d | Menu: %d | Route: %d | Party: %d",
            state.frame_count, battle_state, battle_state_alt, wild_species, wild_species_alt, 
            wild_level, menu_state, current_route, party_count
        )
        print(debug_info)
        
        -- Write to file every 5 seconds
        if state.frame_count % 300 == 0 then
            write_debug_log(debug_info)
        end
    end
    
    -- Detect battle state changes (primary address)
    if battle_state ~= state.last_battle_state then
        local message = string.format(
            "BATTLE STATE CHANGE: %d -> %d | Wild: Species=%d Level=%d",
            state.last_battle_state, battle_state, wild_species, wild_level
        )
        print("[IMPORTANT] " .. message)
        write_debug_log(message)
        state.last_battle_state = battle_state
        
        -- Check if this is a new encounter
        if battle_state > 0 and wild_species > 0 and wild_species < 1000 then
            print("[ENCOUNTER DETECTED] Species: " .. wild_species .. " Level: " .. wild_level)
            write_debug_log("ENCOUNTER DETECTED - Species: " .. wild_species .. " Level: " .. wild_level)
            state.in_encounter = true
        elseif battle_state == 0 and state.in_encounter then
            print("[ENCOUNTER ENDED]")
            write_debug_log("ENCOUNTER ENDED")
            state.in_encounter = false
        end
    end
    
    -- Check alternative battle state
    if battle_state_alt > 0 and battle_state_alt ~= battle_state then
        print("[ALT BATTLE] Alternative battle state active: " .. battle_state_alt)
    end
    
    -- Detect wild species changes
    if wild_species ~= state.last_wild_species and wild_species > 0 then
        local message = string.format("WILD SPECIES CHANGE: %d -> %d", state.last_wild_species, wild_species)
        print("[SPECIES] " .. message)
        write_debug_log(message)
        state.last_wild_species = wild_species
    end
end

-- Frame callback
local function on_frame()
    state.frame_count = state.frame_count + 1
    
    -- Run monitoring every frame for debugging
    debug_monitor()
end

-- Initialize
print("=== Pokemon Tracker Debug Mode ===")
print("This will log detailed memory information to help diagnose issues")
print("Output directory: " .. CONFIG.output_dir)
print("Check the debug files for memory state information")
write_debug_log("Debug script initialized")

-- Register callback
gui.register(on_frame)