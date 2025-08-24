-- Test script to find correct memory addresses for encounter detection
-- Run this while in a battle to see which addresses have non-zero values

print("=== Memory Address Scanner for Pokemon HGSS ===")
print("Instructions:")
print("1. Start a wild Pokemon encounter")
print("2. Run this script while in battle")
print("3. Check which addresses show non-zero values")
print("===============================================")

-- Common battle state addresses to test
local addresses_to_test = {
    -- US version addresses
    {name = "US Battle State 1", addr = 0x02226E18},
    {name = "US Battle State 2", addr = 0x02226E1C},
    {name = "US Wild Pokemon", addr = 0x0223AB00},
    
    -- EU version addresses
    {name = "EU Battle State 1", addr = 0x02226E20},
    {name = "EU Battle State 2", addr = 0x02226E24},
    {name = "EU Wild Pokemon", addr = 0x0223AB08},
    
    -- Alternative addresses from other sources
    {name = "Alt Battle Flag 1", addr = 0x02228870},
    {name = "Alt Battle Flag 2", addr = 0x02228874},
    {name = "Alt Battle Type", addr = 0x021BF6B0},
    {name = "Alt Wild Data", addr = 0x0223AAF0},
    
    -- Battle-related flags
    {name = "Battle Mode", addr = 0x02226E10},
    {name = "Battle Status", addr = 0x02226E14},
    {name = "Battle Turn", addr = 0x02226E28},
    
    -- Pokemon data areas
    {name = "Enemy Pokemon 1", addr = 0x0223AB00},
    {name = "Enemy Pokemon 2", addr = 0x0223AC00},
    {name = "Wild Pokemon Alt", addr = 0x0223AD00},
}

-- Function to read different data sizes
local function read_value(addr, size)
    if size == 1 then
        return memory.readbyte(addr)
    elseif size == 2 then
        return memory.readword(addr)
    elseif size == 4 then
        return memory.readdword(addr)
    end
    return 0
end

-- Main scanning function
local scan_count = 0

local function scan_memory()
    scan_count = scan_count + 1
    print("\n=== Scan #" .. scan_count .. " at " .. os.date("%H:%M:%S") .. " ===")
    
    local found_values = false
    
    for _, test in ipairs(addresses_to_test) do
        local val_u8 = read_value(test.addr, 1)
        local val_u16 = read_value(test.addr, 2)
        
        -- Only show non-zero values
        if val_u8 > 0 or val_u16 > 0 then
            print(string.format("%s (0x%08X): u8=%d, u16=%d", 
                test.name, test.addr, val_u8, val_u16))
            found_values = true
        end
    end
    
    if not found_values then
        print("No non-zero values found. Make sure you're in a battle!")
    end
    
    -- Also check for Pokemon species in the wild pokemon area
    local wild_species = memory.readword(0x0223AB00)
    local wild_level = memory.readbyte(0x0223AB00 + 0x54)
    
    if wild_species > 0 and wild_species < 1000 then
        print(string.format("\nDetected Wild Pokemon: Species=%d, Level=%d", wild_species, wild_level))
    end
end

-- Frame counter
local frame_count = 0

local function on_frame()
    frame_count = frame_count + 1
    
    -- Scan every 60 frames (1 second)
    if frame_count >= 60 then
        frame_count = 0
        scan_memory()
    end
end

-- Initial scan
scan_memory()

-- Register frame callback
gui.register(on_frame)