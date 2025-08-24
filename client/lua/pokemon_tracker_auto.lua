--[[
Pokemon SoulLink Tracker - Auto-Configuration Version
Automatically detects OS and sets appropriate paths
]]

-- Auto-detect temp directory
local function get_output_directory()
    local temp = os.getenv("TEMP") or os.getenv("TMP") or os.getenv("TMPDIR")
    
    if temp then
        temp = string.gsub(temp, "\\", "/")
        if not string.match(temp, "/$") then
            temp = temp .. "/"
        end
        return temp .. "soullink_events/"
    end
    
    -- Fallback based on OS
    local separator = package.config:sub(1,1)
    if separator == "\\" then
        local username = os.getenv("USERNAME") or "User"
        return "C:/Users/" .. username .. "/AppData/Local/Temp/soullink_events/"
    else
        return "/tmp/soullink_events/"
    end
end

-- Load configuration with auto-detection
local function load_config()
    -- First try to load manual config
    local config_files = {"config.lua", "./config.lua", "client/lua/config.lua"}
    
    for _, path in ipairs(config_files) do
        local success, config = pcall(dofile, path)
        if success and type(config) == "table" then
            print("[Config] Loaded from: " .. path)
            
            -- Override output_dir with auto-detected path if not set
            if not config.output_dir or config.output_dir == "/tmp/soullink_events/" then
                config.output_dir = get_output_directory()
                print("[Config] Auto-detected output dir: " .. config.output_dir)
            end
            
            return config
        end
    end
    
    -- No config found, use defaults with auto-detection
    print("[Config] No config.lua found, using auto-configuration")
    return {
        api_base_url = "http://127.0.0.1:8000",
        run_id = "MISSING_RUN_ID",
        player_id = "MISSING_PLAYER_ID",
        output_dir = get_output_directory(),
        poll_interval = 60,
        debug = true,
        max_runtime = 3600
    }
end

local CONFIG = load_config()

print("=== Pokemon SoulLink Tracker (Auto-Config) ===")
print("Output Directory: " .. CONFIG.output_dir)
print("Run ID: " .. CONFIG.run_id)
print("Player ID: " .. CONFIG.player_id)
print("===============================================")

-- Test directory access
local function test_directory()
    local test_file = CONFIG.output_dir .. "startup_test_" .. os.time() .. ".json"
    local file = io.open(test_file, "w")
    
    if file then
        file:write('{"type":"test","message":"Directory writable"}')
        file:close()
        print("[OK] Output directory is writable: " .. CONFIG.output_dir)
        return true
    else
        print("[ERROR] Cannot write to: " .. CONFIG.output_dir)
        print("[ERROR] Please create this directory or check permissions")
        return false
    end
end

if not test_directory() then
    print("Script will continue but events won't be saved!")
end

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

-- Pokemon data offsets
local POKEMON_OFFSETS = {
    species = 0x00,
    personality = 0x08,
    level = 0x54,
    hp_current = 0x56,
    hp_max = 0x58,
    trainer_id = 0x04
}

-- Game state
local game_state = {
    in_encounter = false,
    last_wild_species = 0,
    last_wild_level = 0,
    last_route = 0,
    frame_count = 0,
    last_battle_state = 0
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

local function safe_read_u32(addr)
    if addr and addr > 0 then
        return memory.readdword(addr)
    end
    return 0
end

-- Get current timestamp
local function get_current_time()
    return os.date("!%Y-%m-%dT%H:%M:%SZ")
end

-- Write event to file
local function write_event(event_data)
    local timestamp = os.time()
    local random = math.random(1000, 9999)
    local filename = CONFIG.output_dir .. "event_" .. timestamp .. "_" .. random .. ".json"
    
    local file = io.open(filename, "w")
    if file then
        file:write(event_data)
        file:close()
        print("[Event] Written: " .. filename)
        return true
    else
        print("[Error] Cannot write: " .. filename)
        return false
    end
end

-- Create encounter event
local function create_encounter_event(species, level, route)
    if CONFIG.run_id == "MISSING_RUN_ID" then
        print("[Warning] Missing run_id/player_id - get from admin panel!")
    end
    
    local event = string.format([[{
    "type": "encounter",
    "run_id": "%s",
    "player_id": "%s",
    "time": "%s",
    "route_id": %d,
    "species_id": %d,
    "level": %d,
    "shiny": false,
    "method": "grass",
    "event_version": "auto"
}]], CONFIG.run_id, CONFIG.player_id, get_current_time(), route, species, level)
    
    write_event(event)
    print(string.format("[Encounter] Species %d Level %d on Route %d", species, level, route))
end

-- Detect encounters
local function detect_encounter()
    local battle_state = safe_read_u8(MEMORY.battle_state)
    
    -- Check for battle state change
    if battle_state ~= game_state.last_battle_state then
        game_state.last_battle_state = battle_state
        
        if battle_state > 0 then
            -- Battle started, check for wild Pokemon
            local wild_species = safe_read_u16(MEMORY.wild_pokemon + POKEMON_OFFSETS.species)
            local wild_level = safe_read_u8(MEMORY.wild_pokemon + POKEMON_OFFSETS.level)
            local current_route = safe_read_u16(MEMORY.current_route)
            
            if wild_species > 0 and wild_species < 1000 and not game_state.in_encounter then
                game_state.in_encounter = true
                game_state.last_wild_species = wild_species
                game_state.last_wild_level = wild_level
                
                create_encounter_event(wild_species, wild_level, current_route)
            end
        else
            -- Battle ended
            if game_state.in_encounter then
                game_state.in_encounter = false
                print("[Battle] Ended")
            end
        end
    end
end

-- Main monitoring function
local function monitor_game()
    game_state.frame_count = game_state.frame_count + 1
    
    -- Check every N frames
    if game_state.frame_count >= CONFIG.poll_interval then
        game_state.frame_count = 0
        
        -- Skip if in menu
        local menu_state = safe_read_u8(MEMORY.menu_state)
        if menu_state == 0 then
            detect_encounter()
        end
    end
end

-- Register frame callback
gui.register(monitor_game)

print("Script running! Enter a wild Pokemon battle to test.")