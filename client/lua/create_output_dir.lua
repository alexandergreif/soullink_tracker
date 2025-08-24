-- Helper script to create the output directory if it doesn't exist
-- Run this once before using the tracker

local function get_temp_directory()
    local temp = os.getenv("TEMP") or os.getenv("TMP") or os.getenv("TMPDIR")
    
    if temp then
        temp = string.gsub(temp, "\\", "/")
        if not string.match(temp, "/$") then
            temp = temp .. "/"
        end
        return temp .. "soullink_events/"
    end
    
    local separator = package.config:sub(1,1)
    if separator == "\\" then
        local username = os.getenv("USERNAME") or "User"
        return "C:/Users/" .. username .. "/AppData/Local/Temp/soullink_events/"
    else
        return "/tmp/soullink_events/"
    end
end

local output_dir = get_temp_directory()

print("=== SoulLink Directory Setup ===")
print("Detected OS: " .. (package.config:sub(1,1) == "\\" and "Windows" or "Unix-like"))
print("Output directory: " .. output_dir)

-- Try to create directory
local test_file = output_dir .. "test_" .. os.time() .. ".txt"
local file = io.open(test_file, "w")

if file then
    file:write("Directory test successful at " .. os.date("%Y-%m-%d %H:%M:%S"))
    file:close()
    print("✓ Directory exists and is writable")
    print("✓ Test file created: " .. test_file)
    
    -- Clean up test file
    os.remove(test_file)
else
    print("✗ Directory does not exist or is not writable")
    print("")
    print("Please create this directory manually:")
    print("  " .. output_dir)
    print("")
    
    if package.config:sub(1,1) == "\\" then
        -- Windows instructions
        print("Windows PowerShell command:")
        print('  New-Item -ItemType Directory -Force -Path "' .. string.gsub(output_dir, "/", "\\") .. '"')
        print("")
        print("Or Windows CMD command:")
        print('  mkdir "' .. string.gsub(output_dir, "/", "\\") .. '"')
    else
        -- Unix instructions
        print("Terminal command:")
        print('  mkdir -p "' .. output_dir .. '"')
    end
end

print("================================")