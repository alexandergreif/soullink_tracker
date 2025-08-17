--[[
DeSmuME Lua API Test Script
Tests basic functionality and compatibility with your DeSmuME version
Run this first to diagnose any issues before using the main tracker
]]

local function log(message)
    print("[TEST] " .. message)
end

local function test_memory_api()
    log("=== Testing Memory API ===")
    
    -- Test different memory read functions
    local functions_to_test = {
        {"memory.read_u8", memory and memory.read_u8},
        {"memory.readbyte", memory and memory.readbyte}, 
        {"memory.read_u16_le", memory and memory.read_u16_le},
        {"memory.read_u16", memory and memory.read_u16},
        {"memory.read_u32_le", memory and memory.read_u32_le},
        {"memory.read_u32", memory and memory.read_u32}
    }
    
    for _, func_test in ipairs(functions_to_test) do
        local name, func = func_test[1], func_test[2]
        if func then
            log("✅ " .. name .. " - Available")
            
            -- Test reading a safe address (usually 0x00000000 works)
            local success, result = pcall(func, 0x02000000)
            if success then
                log("   Test read successful: " .. tostring(result))
            else
                log("   Test read failed: " .. tostring(result))
            end
        else
            log("❌ " .. name .. " - Not available")
        end
    end
end

local function test_emu_api()
    log("=== Testing Emulator API ===")
    
    local emu_functions = {
        {"emu.frameadvance", emu and emu.frameadvance},
        {"emu.pause", emu and emu.pause},
        {"emu.unpause", emu and emu.unpause},
        {"FCEU.frameadvance", FCEU and FCEU.frameadvance}
    }
    
    for _, func_test in ipairs(emu_functions) do
        local name, func = func_test[1], func_test[2]
        if func then
            log("✅ " .. name .. " - Available")
        else
            log("❌ " .. name .. " - Not available")
        end
    end
end

local function test_gui_api()
    log("=== Testing GUI API ===")
    
    local gui_functions = {
        {"gui.register", gui and gui.register},
        {"gui.text", gui and gui.text},
        {"gui.pixel", gui and gui.pixel}
    }
    
    for _, func_test in ipairs(gui_functions) do
        local name, func = func_test[1], func_test[2]
        if func then
            log("✅ " .. name .. " - Available")
        else
            log("❌ " .. name .. " - Not available")
        end
    end
end

local function test_file_io()
    log("=== Testing File I/O ===")
    
    local test_dir = "C:/temp/soullink_test/"
    local test_file = test_dir .. "test.txt"
    
    -- Create directory
    local mkdir_success = os.execute('if not exist "' .. test_dir .. '" mkdir "' .. test_dir .. '"')
    log("Directory creation: " .. (mkdir_success and "Success" or "Failed"))
    
    -- Test file writing
    local file = io.open(test_file, "w")
    if file then
        file:write("Test file content\n")
        file:close()
        log("✅ File writing - Success")
        
        -- Test file reading
        local read_file = io.open(test_file, "r")
        if read_file then
            local content = read_file:read("*all")
            read_file:close()
            log("✅ File reading - Success: " .. string.sub(content, 1, 20) .. "...")
        else
            log("❌ File reading - Failed")
        end
        
        -- Cleanup
        os.remove(test_file)
    else
        log("❌ File writing - Failed")
    end
end

local function test_basic_lua()
    log("=== Testing Basic Lua ===")
    
    -- Test basic Lua functions
    log("Lua version: " .. ((_VERSION or "unknown")))
    log("OS time: " .. os.time())
    log("Math random: " .. math.random(1, 100))
    log("String format: " .. string.format("Test %d", 123))
    
    -- Test JSON-like string creation
    local json_test = string.format([[{
    "type": "test",
    "time": "%s",
    "value": %d
}]], os.date("!%Y-%m-%dT%H:%M:%SZ"), 42)
    
    log("JSON creation test:")
    log(json_test)
end

local function main()
    log("=== DeSmuME Lua Compatibility Test ===")
    log("Time: " .. os.date("%Y-%m-%d %H:%M:%S"))
    log("")
    
    test_basic_lua()
    log("")
    
    test_memory_api()
    log("")
    
    test_emu_api() 
    log("")
    
    test_gui_api()
    log("")
    
    test_file_io()
    log("")
    
    log("=== Test Complete ===")
    log("If you see this message, basic Lua functionality is working!")
    log("Check above for any ❌ marks indicating missing features.")
    log("")
    
    -- Test a short monitoring loop
    log("Testing 5-second monitoring loop...")
    local start_time = os.time()
    local frame_count = 0
    
    while os.time() - start_time < 5 do
        frame_count = frame_count + 1
        
        if emu and emu.frameadvance then
            emu.frameadvance()
        else
            -- Fallback delay
            os.execute("ping 127.0.0.1 -n 1 > nul 2>&1")
        end
        
        if frame_count % 60 == 0 then
            log("Loop running... frame " .. frame_count)
        end
    end
    
    log("Loop test complete! Processed " .. frame_count .. " frames")
    log("Script finished successfully")
end

-- Run the test
main()