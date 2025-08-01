--[[
Configuration Template for Pokemon SoulLink Tracker
Copy this file to config.lua and customize for each player

This file should be customized for each player's setup:
- Player 1: config_player1.lua  
- Player 2: config_player2.lua
- Player 3: config_player3.lua
]]

-- Player Configuration
local PLAYER_CONFIG = {
    -- Player identification
    player_name = "Player1",           -- CHANGE THIS: "Player1", "Player2", "Player3"
    game_version = "HeartGold",        -- CHANGE THIS: "HeartGold" or "SoulSilver"
    region = "EU",                     -- CHANGE THIS: "US", "EU", "JP" based on ROM region
    
    -- API Connection
    api_base_url = "http://127.0.0.1:9000",  -- SoulLink Tracker API URL
    player_token = "your-jwt-token-here",     -- CHANGE THIS: Get from database init script
    
    -- File System Paths
    output_dir = "C:/temp/soullink_events/",  -- CHANGE THIS: Directory for event files
    log_file = "C:/temp/soullink.log",        -- CHANGE THIS: Log file path
    
    -- Performance Settings
    poll_interval = 60,                -- Frames between checks (60 = 1 second at 60fps)
    auto_save_interval = 300,          -- Frames between auto-saves (300 = 5 seconds)
    
    -- Debug and Logging
    debug_mode = true,                 -- Enable detailed logging
    log_encounters = true,             -- Log all encounters to file
    log_party_changes = true,          -- Log party status changes
    log_api_calls = true,              -- Log API communication
    
    -- Memory Configuration (auto-detected based on game_version + region)
    memory_profile = nil,              -- Leave nil for auto-detection
    
    -- Advanced Settings
    enable_shiny_detection = true,     -- Detect and flag shiny Pokemon
    enable_ability_detection = false,  -- Enable ability detection (experimental)
    enable_nature_detection = false,   -- Enable nature detection (experimental)
    
    -- Event Filtering
    skip_duplicate_encounters = false, -- Skip reporting duplicate encounters in same area
    min_level_difference = 0,          -- Only report encounters with level difference >= this
    
    -- Networking
    connection_timeout = 5000,         -- API timeout in milliseconds
    retry_attempts = 3,                -- Number of API retry attempts
    retry_delay = 1000,                -- Delay between retries in milliseconds
    
    -- Safety Features
    auto_pause_on_error = true,        -- Pause monitoring if errors occur
    max_events_per_minute = 30,        -- Rate limit for event generation
    
    -- Game-Specific Settings
    detect_fishing = true,             -- Detect fishing encounters
    detect_surfing = true,             -- Detect surfing encounters  
    detect_headbutt = true,            -- Detect headbutt encounters
    detect_rock_smash = true,          -- Detect rock smash encounters
    
    -- Soul Link Rules
    enable_dupe_clause = true,         -- Respect dupes clause
    enable_species_clause = true,      -- Respect species clause
    track_family_blocks = true,        -- Track evolution family blocking
    
    -- UI and Notifications
    show_encounter_popup = false,      -- Show popup on encounters (can be intrusive)
    play_sound_on_shiny = false,       -- Play sound when shiny encountered
    minimize_to_tray = false,          -- Minimize DeSmuME to system tray
}

-- Advanced Memory Settings (usually auto-detected)
local MEMORY_OVERRIDES = {
    -- Only change these if auto-detection fails
    -- party_pokemon = 0x02234804,    -- Uncomment and set if needed
    -- wild_pokemon = 0x0223AB00,     -- Uncomment and set if needed
    -- battle_state = 0x02226E18,     -- Uncomment and set if needed
    -- current_route = 0x02256AA4,    -- Uncomment and set if needed
}

-- Event Templates (for customizing event data)
local EVENT_TEMPLATES = {
    encounter = {
        -- Additional fields to include in encounter events
        include_location_name = true,
        include_weather = false,
        include_time_of_day = true,
        include_steps_taken = false,
    },
    
    catch_result = {
        -- Additional fields for catch events
        include_ball_used = false,
        include_critical_capture = false,
        include_catch_rate = false,
    },
    
    faint = {
        -- Additional fields for faint events
        include_cause_of_death = false,
        include_opponent_info = false,
        include_damage_taken = false,
    }
}

-- Validation function
local function validate_config()
    local errors = {}
    
    -- Required fields
    if not PLAYER_CONFIG.player_name or PLAYER_CONFIG.player_name == "Player1" then
        table.insert(errors, "player_name must be customized")
    end
    
    if not PLAYER_CONFIG.player_token or PLAYER_CONFIG.player_token == "your-jwt-token-here" then
        table.insert(errors, "player_token must be set from database initialization")
    end
    
    if not PLAYER_CONFIG.game_version or (PLAYER_CONFIG.game_version ~= "HeartGold" and PLAYER_CONFIG.game_version ~= "SoulSilver") then
        table.insert(errors, "game_version must be 'HeartGold' or 'SoulSilver'")
    end
    
    if not PLAYER_CONFIG.region or not string.match(PLAYER_CONFIG.region, "^[A-Z][A-Z]$") then
        table.insert(errors, "region must be valid 2-letter code (US, EU, JP)")
    end
    
    -- Directory validation
    if not PLAYER_CONFIG.output_dir or PLAYER_CONFIG.output_dir == "" then
        table.insert(errors, "output_dir must be specified")
    end
    
    -- URL validation
    if not PLAYER_CONFIG.api_base_url or not string.match(PLAYER_CONFIG.api_base_url, "^https?://") then
        table.insert(errors, "api_base_url must be valid HTTP/HTTPS URL")
    end
    
    return errors
end

-- Initialize directories
local function init_directories()
    -- Create output directory
    if PLAYER_CONFIG.output_dir then
        os.execute("mkdir \"" .. PLAYER_CONFIG.output_dir .. "\" 2>nul")      -- Windows
        os.execute("mkdir -p \"" .. PLAYER_CONFIG.output_dir .. "\" 2>/dev/null") -- Unix
    end
    
    -- Create log directory if needed
    if PLAYER_CONFIG.log_file then
        local log_dir = string.match(PLAYER_CONFIG.log_file, "(.+)[/\\][^/\\]+$")
        if log_dir then
            os.execute("mkdir \"" .. log_dir .. "\" 2>nul")      -- Windows  
            os.execute("mkdir -p \"" .. log_dir .. "\" 2>/dev/null") -- Unix
        end
    end
end

-- Export configuration
return {
    PLAYER_CONFIG = PLAYER_CONFIG,
    MEMORY_OVERRIDES = MEMORY_OVERRIDES,
    EVENT_TEMPLATES = EVENT_TEMPLATES,
    validate_config = validate_config,
    init_directories = init_directories
}