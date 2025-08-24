-- Simple Battle Detection Test for Pokemon HGSS
-- This script tests if we can detect when you're in battle

print("=== Simple Battle Detector ===")
print("This will show when you enter/exit battles")
print("If this doesn't work, the memory addresses are wrong")
print("================================")

-- Try multiple battle state addresses
local ADDRESSES = {
    -- Primary US addresses
    {name = "US Primary", addr = 0x02226E18},
    {name = "US Alt", addr = 0x02226E1C},
    
    -- EU addresses
    {name = "EU Primary", addr = 0x02226E20},
    {name = "EU Alt", addr = 0x02226E24},
    
    -- Other common addresses
    {name = "Battle Flag 1", addr = 0x02228870},
    {name = "Battle Flag 2", addr = 0x021BF6B0},
    {name = "Battle Mode", addr = 0x02226E10},
}

-- Track last values
local last_values = {}
for i, addr_info in ipairs(ADDRESSES) do
    last_values[i] = 0
end

-- Check for battle every frame
local frame_count = 0

local function check_battle()
    frame_count = frame_count + 1
    
    -- Only check every 30 frames (0.5 seconds)
    if frame_count < 30 then
        return
    end
    frame_count = 0
    
    local changes_detected = false
    
    for i, addr_info in ipairs(ADDRESSES) do
        local current_value = memory.readbyte(addr_info.addr)
        
        -- Check if value changed
        if current_value ~= last_values[i] then
            print(string.format("[%s] Changed: %d -> %d %s",
                os.date("%H:%M:%S"),
                last_values[i],
                current_value,
                addr_info.name))
            
            -- Specifically note battle start/end
            if last_values[i] == 0 and current_value > 0 then
                print("  ^^^ BATTLE STARTED at " .. addr_info.name .. " ^^^")
                changes_detected = true
            elseif last_values[i] > 0 and current_value == 0 then
                print("  vvv BATTLE ENDED at " .. addr_info.name .. " vvv")
                changes_detected = true
            end
            
            last_values[i] = current_value
        end
    end
    
    -- If we detected changes, also check for wild Pokemon
    if changes_detected then
        local wild_species = memory.readword(0x0223AB00)  -- Species ID at wild Pokemon address
        local wild_level = memory.readbyte(0x0223AB00 + 0x54)  -- Level offset
        
        if wild_species > 0 and wild_species < 1000 then
            print(string.format("  Wild Pokemon detected: Species=%d, Level=%d", wild_species, wild_level))
        end
    end
end

-- Also create a test file to verify file writing works
local function test_file_write()
    local test_dir = "/tmp/soullink_events/"
    local test_file = test_dir .. "battle_test_" .. os.time() .. ".txt"
    
    local file = io.open(test_file, "w")
    if file then
        file:write("Battle detection test at " .. os.date("%Y-%m-%d %H:%M:%S"))
        file:close()
        print("Test file written successfully: " .. test_file)
    else
        print("ERROR: Cannot write to " .. test_dir)
        print("Please check directory permissions or create the directory")
    end
end

-- Test file writing on startup
test_file_write()

-- Register frame callback
gui.register(check_battle)

print("Script running. Enter a wild Pokemon battle to test detection.")