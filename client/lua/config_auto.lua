-- Automatic configuration with OS detection
-- This config automatically detects the operating system and sets appropriate paths

local function get_temp_directory()
    -- Try environment variables first
    local temp = os.getenv("TEMP") or os.getenv("TMP") or os.getenv("TMPDIR")
    
    if temp then
        -- Windows typically uses backslashes, but Lua handles forward slashes fine
        temp = string.gsub(temp, "\\", "/")
        if not string.match(temp, "/$") then
            temp = temp .. "/"
        end
        return temp .. "soullink_events/"
    end
    
    -- Fallback paths based on OS detection
    local separator = package.config:sub(1,1)
    if separator == "\\" then
        -- Windows
        local username = os.getenv("USERNAME") or "User"
        return "C:/Users/" .. username .. "/AppData/Local/Temp/soullink_events/"
    else
        -- Unix/Linux/macOS
        return "/tmp/soullink_events/"
    end
end

local function get_desktop_directory()
    -- Alternative: use Desktop for easier debugging
    local separator = package.config:sub(1,1)
    if separator == "\\" then
        -- Windows
        local userprofile = os.getenv("USERPROFILE")
        if userprofile then
            return string.gsub(userprofile, "\\", "/") .. "/Desktop/soullink_events/"
        end
    else
        -- Unix/Linux/macOS
        local home = os.getenv("HOME")
        if home then
            return home .. "/Desktop/soullink_events/"
        end
    end
    return get_temp_directory()  -- Fallback to temp
end

-- Auto-detected configuration
local config = {
    -- API settings (adjust these for your setup)
    api_base_url = "http://127.0.0.1:8000",
    
    -- IMPORTANT: Replace these with your actual UUIDs from the admin panel
    run_id = "f92209cf-b5a8-490c-a6d6-49488be06aaf",
    player_id = "7287b21a-40a9-40ce-ad76-54154ac6ecf1",
    
    -- Auto-detected output directory
    -- Change to get_desktop_directory() if you prefer Desktop for easier access
    output_dir = get_temp_directory(),
    
    -- Optional: Override with a custom path
    -- output_dir = "C:/soullink_events/",  -- Windows example
    -- output_dir = "/home/user/soullink_events/",  -- Linux example
    
    -- Polling and debug settings
    poll_interval = 60,  -- Check every 60 frames (1 second)
    debug = true,
    max_runtime = 3600,  -- Stop after 1 hour (0 = unlimited)
    
    -- Memory profile for your ROM version
    memory_profile = "US"  -- Options: "US" or "EU"
}

-- Print detected configuration for debugging
print("=== Auto-Configuration ===")
print("OS Detection: " .. (package.config:sub(1,1) == "\\" and "Windows" or "Unix-like"))
print("Output Directory: " .. config.output_dir)
print("Run ID: " .. config.run_id)
print("Player ID: " .. config.player_id)
print("========================")

return config