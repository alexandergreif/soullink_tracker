--[[
Pokemon SoulLink Tracker - DeSmuME Lua Script
Monitors Pokemon HeartGold/SoulSilver ROM for encounters, catches, and faints
Writes events to JSON files for the Python watcher to process

Compatible with:
- Pokemon HeartGold (IPKE/IPKJ)  
- Pokemon SoulSilver (IPGE/IPGJ)

Memory addresses are for the US versions of the games.
]]

-- Configuration
local CONFIG = {
    output_dir = "C:/temp/soullink_events/",  -- Directory to write JSON files
    player_name = "Player1",                  -- Configure per player
    game_version = "HeartGold",              -- "HeartGold" or "SoulSilver"
    region = "EU",                           -- Game region
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
    
    -- RNG and encounter data
    encounter_rng = 0x021BFBD4,
    last_encounter = 0x0223AB00,
    
    -- Game state flags
    in_battle = 0x02226E18,
    menu_state = 0x021C4D94
}

-- Pokemon data structure offsets (within 236-byte block)
local POKEMON_OFFSETS = {
    species = 0x00,      -- 2 bytes
    item = 0x02,         -- 2 bytes
    trainer_id = 0x04,   -- 4 bytes
    personality = 0x08,  -- 4 bytes (unique identifier)
    checksum = 0x0C,     -- 2 bytes
    level = 0x54,        -- 1 byte
    hp_current = 0x56,   -- 2 bytes
    hp_max = 0x58,       -- 2 bytes
    status = 0x5A,       -- 1 byte (0=healthy, 1=asleep, 2=poisoned, etc.)
    shiny_flag = 0x40    -- Calculated from personality/trainer_id
}

-- Game state tracking
local game_state = {
    last_battle_state = 0,
    last_route = 0,
    last_party_hash = "",
    encounter_count = 0,
    last_wild_species = 0,
    last_wild_level = 0,
    party_pokemon = {},
    in_encounter = false,
    battle_result = nil
}

-- Utility functions
local function log(message)
    if CONFIG.debug then
        print("[SoulLink] " .. message)
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
        log("Event written to: " .. filename)
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

local function get_party_pokemon()
    local party = {}
    local party_count = read_u8(MEMORY.party_count)
    
    for i = 0, math.min(party_count - 1, 5) do
        local base_addr = MEMORY.party_pokemon + (i * 236)
        local pokemon = read_pokemon_data(base_addr)
        
        if pokemon.species > 0 then
            pokemon.party_index = i
            pokemon.pokemon_key = "personality_" .. pokemon.personality
            table.insert(party, pokemon)
        end
    end
    
    return party
end

local function get_party_hash(party)
    local hash_parts = {}
    for _, pokemon in ipairs(party) do
        table.insert(hash_parts, pokemon.species .. "_" .. pokemon.level .. "_" .. pokemon.hp_current)
    end
    return table.concat(hash_parts, "|")
end

-- Route and location functions
local function get_current_location()
    local route = read_u16(MEMORY.current_route)
    local map = read_u16(MEMORY.current_map)
    
    -- Map specific route IDs to human-readable names
    -- This is a simplified mapping - a full implementation would need complete route tables
    local route_names = {
        [29] = "Route 29",
        [30] = "Route 30", 
        [31] = "Route 31",
        [32] = "Route 32",
        [33] = "Route 33",
        [34] = "Route 34",
        [35] = "Route 35",
        [36] = "Route 36",
        [37] = "Route 37",
        [38] = "Route 38",
        [39] = "Route 39",
        [40] = "Route 40",
        [41] = "Route 41",
        [42] = "Route 42",
        [43] = "Route 43",
        [44] = "Route 44",
        [45] = "Route 45",
        [46] = "Route 46",
        [47] = "Route 47",
        [48] = "Route 48"
    }
    
    return {
        route_id = route,
        route_name = route_names[route] or ("Unknown Route " .. route),
        map_id = map
    }
end

-- Battle and encounter detection
local function detect_encounter()
    local battle_state = read_u8(MEMORY.battle_state)
    local wild_species = read_u16(MEMORY.wild_pokemon)
    local wild_level = read_u8(MEMORY.wild_pokemon + POKEMON_OFFSETS.level)
    
    -- Battle state: 0=no battle, 1=battle starting, 2=in battle, 3=battle ending
    if battle_state > 0 and not game_state.in_encounter and wild_species > 0 then
        game_state.in_encounter = true
        game_state.last_wild_species = wild_species
        game_state.last_wild_level = wild_level
        
        local location = get_current_location()
        local wild_pokemon = read_pokemon_data(MEMORY.wild_pokemon)
        
        -- Create encounter event
        local encounter_event = {
            type = "encounter",
            timestamp = get_current_time(),
            player_name = CONFIG.player_name,
            game_version = CONFIG.game_version,
            region = CONFIG.region,
            route_id = location.route_id,
            species_id = wild_species,
            level = wild_level,
            shiny = wild_pokemon.shiny,
            method = "grass", -- TODO: Detect fishing, surfing, etc.
            rod_kind = nil
        }
        
        local json_data = string.format([[{
    "type": "encounter",
    "timestamp": "%s",
    "player_name": "%s", 
    "game_version": "%s",
    "region": "%s",
    "route_id": %d,
    "species_id": %d,
    "level": %d,
    "shiny": %s,
    "method": "%s"
}]], encounter_event.timestamp, encounter_event.player_name, encounter_event.game_version,
    encounter_event.region, encounter_event.route_id, encounter_event.species_id,
    encounter_event.level, tostring(encounter_event.shiny), encounter_event.method)
        
        write_event_file(json_data)
        log("Encounter detected: Species " .. wild_species .. " Level " .. wild_level)
    end
    
    -- Detect battle end and catch result
    if game_state.in_encounter and battle_state == 0 then
        game_state.in_encounter = false
        
        -- Check if Pokemon was caught (simplified - check if party size increased)
        local current_party = get_party_pokemon()
        local caught = false
        
        -- Look for new Pokemon in party with matching species
        for _, pokemon in ipairs(current_party) do
            if pokemon.species == game_state.last_wild_species then
                -- Found matching species - likely caught (this is simplified logic)
                caught = true
                break
            end
        end
        
        -- Create catch result event
        local result = caught and "caught" or "fled"
        
        local catch_event = string.format([[{
    "type": "catch_result",
    "timestamp": "%s",
    "player_name": "%s",
    "result": "%s",
    "encounter_ref": {
        "species_id": %d,
        "level": %d,
        "route_id": %d
    }
}]], get_current_time(), CONFIG.player_name, result,
    game_state.last_wild_species, game_state.last_wild_level, get_current_location().route_id)
        
        write_event_file(catch_event)
        log("Battle ended: " .. result)
        
        game_state.battle_result = result
    end
end

local function detect_faint()
    local current_party = get_party_pokemon()
    
    -- Compare with previous party state to detect faints
    for i, current_pokemon in ipairs(current_party) do
        local previous_pokemon = game_state.party_pokemon[i]
        
        if previous_pokemon and current_pokemon.pokemon_key == previous_pokemon.pokemon_key then
            -- Same Pokemon - check if it fainted
            if previous_pokemon.hp_current > 0 and current_pokemon.hp_current == 0 then
                -- Pokemon fainted!
                local faint_event = string.format([[{
    "type": "faint",
    "timestamp": "%s",
    "player_name": "%s",
    "pokemon_key": "%s",
    "party_index": %d,
    "species_id": %d,
    "level": %d
}]], get_current_time(), CONFIG.player_name, current_pokemon.pokemon_key,
    current_pokemon.party_index, current_pokemon.species, current_pokemon.level)
                
                write_event_file(faint_event)
                log("Pokemon fainted: " .. current_pokemon.pokemon_key)
            end
        end
    end
    
    -- Update stored party state
    game_state.party_pokemon = current_party
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
    
    -- Monitor party for faints
    detect_faint()
    
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
    
    if frame_counter >= CONFIG.poll_interval then
        frame_counter = 0
        monitor_game()
    end
end

-- Initialize
log("Pokemon SoulLink Tracker started")
log("Player: " .. CONFIG.player_name .. " (" .. CONFIG.game_version .. ")")
log("Output directory: " .. CONFIG.output_dir)
create_output_dir()

-- Register frame callback
emu.registerbefore(on_frame)