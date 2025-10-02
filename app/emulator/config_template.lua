-- =============================================================================
-- CONFIGURATION TEMPLATE
-- =============================================================================
-- Copy this file and customize the CONFIG table below before running
-- the encounter tracker script.

CONFIG = {
    -- REQUIRED: Player identifier (used in JSON filenames and database)
    -- Examples: "Alice", "Player1", "Bob"
    player_name = "Player1",

    -- REQUIRED: Directory path for JSON encounter exports
    -- Must exist before running the script
    -- Examples: "./data/encounters/", "C:/soullink/encounters/"
    json_output_dir = "./data/encounters/",

    -- Polling interval in seconds (how often to check for new encounters)
    -- Default: 1.0 (constitutional requirement)
    -- Reduce for faster detection, increase to reduce CPU usage
    polling_interval = 1.0,

    -- Enable console logging to DeSmuME Lua window
    -- Set to false to reduce console spam
    enable_logging = true,

    -- Track legendary Pokemon encounters
    -- If false, legendary encounters will be ignored
    -- Default: true (legendaries exempt from Soullink duplicate rule)
    track_legendaries = true
}

-- =============================================================================
-- VALIDATION
-- =============================================================================
-- Do not edit below this line unless you know what you're doing

function validate_config()
    -- Check player name is set
    if CONFIG.player_name == nil or CONFIG.player_name == "" then
        error("CONFIG.player_name must be set to a non-empty string")
    end

    -- Check player name length
    if string.len(CONFIG.player_name) > 50 then
        error("CONFIG.player_name must be 50 characters or less")
    end

    -- Check json_output_dir is set
    if CONFIG.json_output_dir == nil or CONFIG.json_output_dir == "" then
        error("CONFIG.json_output_dir must be set to a valid directory path")
    end

    -- Ensure json_output_dir ends with separator
    local last_char = string.sub(CONFIG.json_output_dir, -1)
    if last_char ~= "/" and last_char ~= "\\" then
        CONFIG.json_output_dir = CONFIG.json_output_dir .. "/"
    end

    -- Check polling interval is positive
    if CONFIG.polling_interval <= 0 then
        error("CONFIG.polling_interval must be greater than 0")
    end

    -- Type check booleans
    if type(CONFIG.enable_logging) ~= "boolean" then
        error("CONFIG.enable_logging must be true or false")
    end

    if type(CONFIG.track_legendaries) ~= "boolean" then
        error("CONFIG.track_legendaries must be true or false")
    end

    -- Log configuration if logging enabled
    if CONFIG.enable_logging then
        print("[INFO] Configuration validated successfully")
        print("[INFO] Player: " .. CONFIG.player_name)
        print("[INFO] Output directory: " .. CONFIG.json_output_dir)
        print("[INFO] Polling interval: " .. CONFIG.polling_interval .. "s")
        print("[INFO] Track legendaries: " .. tostring(CONFIG.track_legendaries))
    end
end

-- =============================================================================
-- USAGE
-- =============================================================================
-- 1. Copy this file to a new location (e.g., my_config.lua)
-- 2. Edit the CONFIG table at the top with your settings
-- 3. Include this config file in your main Lua script:
--    dofile("path/to/my_config.lua")
--    validate_config()
-- 4. Access config values: CONFIG.player_name, CONFIG.json_output_dir, etc.
