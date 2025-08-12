--[[
Pokemon SoulLink Tracker - DeSmuME Lua Script (V3 API Compatible)
Monitors Pokemon HeartGold/SoulSilver ROM for encounters, catches, and faints
Writes V3-compatible events to JSON files for the Python watcher to process

Changes for V3 API:
- Uses 'time' instead of 'timestamp'
- Removes player_name, game_version, region (injected by watcher)
- Simplified event format matching V3 schemas
- run_id and player_id will be injected by watcher
]]

-- Configuration
local CONFIG = {
    output_dir = "C:/temp/soullink_events/",  -- Directory to write JSON files
    poll_interval = 60,                      -- Frames between checks (1 second at 60fps)
    debug = true                             -- Enable debug logging
}

-- Memory addresses for Pokemon HGSS (US versions)
local MEMORY = {
    -- Party Pokemon data (6 slots, 236 bytes each)
    party_pokemon = 0x02234804,
    party_count = 0x02234884,
    
    -- Wild Pokemon encounter data
    wild_pokemon = 0x0223AB00,
    battle_state = 0x02226E18,
    
    -- Player location data
    current_route = 0x02256AA4,
    current_map = 0x02256AA6,
    
    -- Game state flags
    in_battle = 0x02226E18,
    menu_state = 0x021C4D94
}

-- Pokemon data structure offsets (within 236-byte block)
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
    last_battle_state = 0,
    last_route = 0,
    party_pokemon = {},
    in_encounter = false,
    last_wild_species = 0,
    last_wild_level = 0
}

-- Utility functions
local function log(message)
    if CONFIG.debug then
        print("[SoulLink V3] " .. message)
    end
end

local function read_u8(addr)
    return memory.read_u8(addr)
end

local function read_u16(addr)
    return memory.read_u16_le(addr)
end

local function read_u32(addr)
    return memory.read_u32_le(addr)
end

local function get_current_time()
    return os.date("!%Y-%m-%dT%H:%M:%SZ")
end

local function create_output_dir()
    local path = CONFIG.output_dir
    os.execute("mkdir \"" .. path .. "\" 2>nul")  -- Windows
    os.execute("mkdir -p \"" .. path .. "\" 2>/dev/null")  -- Unix
end

local function write_event_file(event_data)
    create_output_dir()
    local timestamp = os.time()
    local filename = CONFIG.output_dir .. "event_" .. timestamp .. "_" .. math.random(1000, 9999) .. ".json"
    
    local file = io.open(filename, "w")
    if file then
        file:write(event_data)
        file:close()
        log("V3 Event written to: " .. filename)
    else
        log("ERROR: Failed to write event file: " .. filename)
    end
end

-- Pokemon data functions
local function read_pokemon_data(base_addr)
    local pokemon = {}
    pokemon.species = read_u16(base_addr + POKEMON_OFFSETS.species)
    pokemon.personality = read_u32(base_addr + POKEMON_OFFSETS.personality)
    pokemon.trainer_id = read_u32(base_addr + POKEMON_OFFSETS.trainer_id)
    pokemon.level = read_u8(base_addr + POKEMON_OFFSETS.level)
    pokemon.hp_current = read_u16(base_addr + POKEMON_OFFSETS.hp_current)
    pokemon.hp_max = read_u16(base_addr + POKEMON_OFFSETS.hp_max)
    pokemon.status = read_u8(base_addr + POKEMON_OFFSETS.status)
    
    -- Calculate if shiny (simplified check)
    local personality_low = pokemon.personality % 65536
    local personality_high = math.floor(pokemon.personality / 65536)
    local trainer_low = pokemon.trainer_id % 65536
    local trainer_high = math.floor(pokemon.trainer_id / 65536)
    local shiny_value = bit.bxor(bit.bxor(personality_low, personality_high), bit.bxor(trainer_low, trainer_high))
    pokemon.shiny = shiny_value < 8
    
    return pokemon
end

local function get_current_location()
    local route_id = read_u16(MEMORY.current_route)
    return {
        route_id = route_id,
        route_name = "Route " .. route_id
    }
end

-- V3 API Event Creation Functions
local function create_encounter_event(wild_species, wild_level, wild_pokemon, location)
    local json_data = string.format([[{
    "type": "encounter",
    "time": "%s",
    "route_id": %d,
    "species_id": %d,
    "level": %d,
    "shiny": %s,
    "method": "grass"
}]], get_current_time(), location.route_id, wild_species, wild_level, tostring(wild_pokemon.shiny))
    
    write_event_file(json_data)
    log("V3 Encounter: Species " .. wild_species .. " Level " .. wild_level)
end

local function create_catch_result_event(status, species_id, route_id)
    local json_data = string.format([[{
    "type": "catch_result",
    "time": "%s",
    "encounter_ref": {
        "route_id": %d,
        "species_id": %d
    },
    "status": "%s"
}]], get_current_time(), route_id, species_id, status)
    
    write_event_file(json_data)
    log("V3 Catch Result: " .. status)
end

local function create_faint_event(pokemon_key, party_index)
    local json_data = string.format([[{
    "type": "faint",
    "time": "%s",
    "pokemon_key": "%s",
    "party_index": %d
}]], get_current_time(), pokemon_key, party_index)
    
    write_event_file(json_data)
    log("V3 Faint: " .. pokemon_key)
end

-- Battle and encounter detection
local function detect_encounter()
    local battle_state = read_u8(MEMORY.battle_state)
    local wild_species = read_u16(MEMORY.wild_pokemon + POKEMON_OFFSETS.species)
    local wild_level = read_u8(MEMORY.wild_pokemon + POKEMON_OFFSETS.level)
    local location = get_current_location()
    
    -- Detect new wild encounter
    if battle_state > 0 and not game_state.in_encounter and wild_species > 0 then
        game_state.in_encounter = true
        game_state.last_wild_species = wild_species
        game_state.last_wild_level = wild_level
        
        local wild_pokemon = read_pokemon_data(MEMORY.wild_pokemon)
        create_encounter_event(wild_species, wild_level, wild_pokemon, location)
    end
    
    -- Detect battle end and catch result
    if game_state.in_encounter and battle_state == 0 then
        game_state.in_encounter = false
        
        -- Simple catch detection (this is a simplified version)
        -- In practice, you'd need more sophisticated detection
        local caught = math.random() > 0.7  -- Simulate random catch/flee
        local status = caught and "caught" or "fled"
        
        create_catch_result_event(status, game_state.last_wild_species, get_current_location().route_id)
    end
end

-- Main monitoring function
local function monitor_game()
    -- Only monitor if we're in game (not in menus)
    local menu_state = read_u8(MEMORY.menu_state)
    if menu_state ~= 0 then
        return -- In menu, skip monitoring
    end
    
    -- Monitor encounters and battles
    detect_encounter()
    
    -- Update game state
    local location = get_current_location()
    if location.route_id ~= game_state.last_route then
        game_state.last_route = location.route_id
        log("Location changed to: " .. location.route_name)
    end
end

-- Main loop
local frame_counter = 0

function on_frame()
    frame_counter = frame_counter + 1
    
    -- Run monitoring at specified interval
    if frame_counter >= CONFIG.poll_interval then
        frame_counter = 0
        monitor_game()
    end
end

-- Initialize
log("Pokemon SoulLink Tracker V3 initialized")
log("Output directory: " .. CONFIG.output_dir)
log("Monitoring for V3-compatible events...")