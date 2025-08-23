--[[
SoulLink Tracker Configuration
Copy this file to 'config.lua' and fill in your specific values
]]

local config = {
    -- API Configuration
    api_base_url = "http://127.0.0.1:8000",
    
    -- Run and Player IDs (get these from the admin panel)
    run_id = "REPLACE_WITH_YOUR_RUN_ID",        -- UUID from admin panel
    player_id = "REPLACE_WITH_YOUR_PLAYER_ID",  -- UUID from admin panel
    
    -- Event Output Configuration
    output_dir = "C:/temp/soullink_events/",
    
    -- Script Behavior
    poll_interval = 60,    -- Frames between checks (60 = 1 second at 60fps)
    debug = true,          -- Enable debug logging
    max_runtime = 3600,    -- Maximum runtime in seconds
    
    -- Memory Profile (US/EU)
    memory_profile = "US"  -- Change to "EU" if needed
}

return config