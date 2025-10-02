-- =============================================================================
-- HGSS ENCOUNTER TRACKER - SOULLINK EDITION
-- =============================================================================
-- DeSmuME Lua script for real-time Pokemon encounter detection
-- Pokemon Heart Gold / Soul Silver (USA)
--
-- This script polls emulator memory every 1 second to detect wild Pokemon
-- encounters, decrypts Pokemon data structures, and exports encounter info
-- to JSON files for downstream processing by the Soullink Tracker system.
--
-- USAGE:
-- 1. Copy and customize config_template.lua with your player name and output path
-- 2. Load this script in DeSmuME: Tools > Lua Scripting > New Lua Script Window
-- 3. Run your HGSS ROM and trigger wild encounters
-- 4. JSON files will be created in your configured output directory
-- =============================================================================

-- =============================================================================
-- CONFIGURATION
-- =============================================================================
-- Load configuration from external file
-- Copy config_template.lua and edit with your settings
dofile("config_template.lua")

-- =============================================================================
-- MEMORY ADDRESSES (HGSS USA)
-- =============================================================================
local PARTY_POINTER_ADDR = 0x0211186C  -- Base pointer for party/battle Pokemon
local ENEMY_OFFSET = 0x37970           -- Offset to enemy Pokemon from base

-- Pokemon structure offsets (from pokemon_addr)
local PID_OFFSET = 0x00              -- Personality ID (32-bit, unencrypted)
local CHECKSUM_OFFSET = 0x06         -- Checksum for XOR decryption (16-bit)
local ENCRYPTED_DATA_START = 0x08    -- Start of encrypted blocks
local LEVEL_OFFSET = 0x8C            -- Level (1 byte, unencrypted)
local CURRENT_HP_OFFSET = 0x8E       -- Current HP (16-bit, unencrypted)
local MAX_HP_OFFSET = 0x90           -- Max HP (16-bit, unencrypted)

-- Block shuffle lookup table (indexed by shift value)
local BLOCK_SHUFFLE_TABLE = {
    [0]  = {0, 1, 2, 3},  -- ABCD
    [1]  = {0, 1, 3, 2},  -- ABDC
    [2]  = {0, 2, 1, 3},  -- ACBD
    [3]  = {0, 3, 1, 2},  -- ADBC
    [4]  = {0, 2, 3, 1},  -- ACDB
    [5]  = {0, 3, 2, 1},  -- ADCB
    [6]  = {1, 0, 2, 3},  -- BACD
    [7]  = {1, 0, 3, 2},  -- BADC
    [8]  = {2, 0, 1, 3},  -- CABD
    [9]  = {3, 0, 1, 2},  -- DABC
    [10] = {2, 0, 3, 1},  -- CADB
    [11] = {3, 0, 2, 1},  -- DACB
    [12] = {1, 2, 0, 3},  -- BCAD
    [13] = {1, 3, 0, 2},  -- BDAC
    [14] = {2, 1, 0, 3},  -- CBAD
    [15] = {3, 1, 0, 2},  -- DBAC
    [16] = {2, 3, 0, 1},  -- CDAB
    [17] = {3, 2, 0, 1},  -- DCAB
    [18] = {1, 2, 3, 0},  -- BCDA
    [19] = {1, 3, 2, 0},  -- BDCA
    [20] = {2, 1, 3, 0},  -- CBDA
    [21] = {3, 1, 2, 0},  -- DBCA
    [22] = {2, 3, 1, 0},  -- CDBA
    [23] = {3, 2, 1, 0}   -- DCBA
}

-- =============================================================================
-- LEGENDARY POKEMON LIST (Species IDs)
-- =============================================================================
-- Legendary Pokemon are exempt from Soullink duplicate rule
local LEGENDARY_SPECIES = {
    [144] = true, -- Articuno
    [145] = true, -- Zapdos
    [146] = true, -- Moltres
    [150] = true, -- Mewtwo
    [243] = true, -- Raikou
    [244] = true, -- Entei
    [245] = true, -- Suicune
    [249] = true, -- Lugia
    [250] = true, -- Ho-Oh
    [380] = true, -- Latias
    [381] = true, -- Latios
    [382] = true, -- Kyogre
    [383] = true, -- Groudon
    [384] = true, -- Rayquaza
    [483] = true, -- Dialga
    [484] = true, -- Palkia
    [487] = true, -- Giratina
    [493] = true  -- Arceus
}

-- =============================================================================
-- SPECIES NAME LOOKUP (Gen 4 National Dex 1-493)
-- =============================================================================
-- Abbreviated table - full implementation would include all 493 species
-- For MVP, we'll include the most common HGSS encounters + legendaries
local SPECIES_NAMES = {
    [1] = "Bulbasaur", [2] = "Ivysaur", [3] = "Venusaur",
    [4] = "Charmander", [5] = "Charmeleon", [6] = "Charizard",
    [7] = "Squirtle", [8] = "Wartortle", [9] = "Blastoise",
    [10] = "Caterpie", [11] = "Metapod", [12] = "Butterfree",
    [13] = "Weedle", [14] = "Kakuna", [15] = "Beedrill",
    [16] = "Pidgey", [17] = "Pidgeotto", [18] = "Pidgeot",
    [19] = "Rattata", [20] = "Raticate",
    [21] = "Spearow", [22] = "Fearow",
    [23] = "Ekans", [24] = "Arbok",
    [25] = "Pikachu", [26] = "Raichu",
    [27] = "Sandshrew", [28] = "Sandslash",
    [29] = "Nidoran♀", [30] = "Nidorina", [31] = "Nidoqueen",
    [32] = "Nidoran♂", [33] = "Nidorino", [34] = "Nidoking",
    [35] = "Clefairy", [36] = "Clefable",
    [37] = "Vulpix", [38] = "Ninetales",
    [39] = "Jigglypuff", [40] = "Wigglytuff",
    [41] = "Zubat", [42] = "Golbat",
    [43] = "Oddish", [44] = "Gloom", [45] = "Vileplume",
    [46] = "Paras", [47] = "Parasect",
    [48] = "Venonat", [49] = "Venomoth",
    [50] = "Diglett", [51] = "Dugtrio",
    [52] = "Meowth", [53] = "Persian",
    [54] = "Psyduck", [55] = "Golduck",
    [56] = "Mankey", [57] = "Primeape",
    [58] = "Growlithe", [59] = "Arcanine",
    [60] = "Poliwag", [61] = "Poliwhirl", [62] = "Poliwrath",
    [63] = "Abra", [64] = "Kadabra", [65] = "Alakazam",
    [66] = "Machop", [67] = "Machoke", [68] = "Machamp",
    [69] = "Bellsprout", [70] = "Weepinbell", [71] = "Victreebel",
    [72] = "Tentacool", [73] = "Tentacruel",
    [74] = "Geodude", [75] = "Graveler", [76] = "Golem",
    [77] = "Ponyta", [78] = "Rapidash",
    [79] = "Slowpoke", [80] = "Slowbro",
    [81] = "Magnemite", [82] = "Magneton",
    [83] = "Farfetch'd",
    [84] = "Doduo", [85] = "Dodrio",
    [86] = "Seel", [87] = "Dewgong",
    [88] = "Grimer", [89] = "Muk",
    [90] = "Shellder", [91] = "Cloyster",
    [92] = "Gastly", [93] = "Haunter", [94] = "Gengar",
    [95] = "Onix",
    [96] = "Drowzee", [97] = "Hypno",
    [98] = "Krabby", [99] = "Kingler",
    [100] = "Voltorb", [101] = "Electrode",
    [102] = "Exeggcute", [103] = "Exeggutor",
    [104] = "Cubone", [105] = "Marowak",
    [129] = "Magikarp", [130] = "Gyarados",
    [133] = "Eevee", [134] = "Vaporeon", [135] = "Jolteon", [136] = "Flareon",
    [143] = "Snorlax",
    [144] = "Articuno", [145] = "Zapdos", [146] = "Moltres",
    [147] = "Dratini", [148] = "Dragonair", [149] = "Dragonite",
    [150] = "Mewtwo", [151] = "Mew",
    -- Gen 2 Pokemon
    [152] = "Chikorita", [153] = "Bayleef", [154] = "Meganium",
    [155] = "Cyndaquil", [156] = "Quilava", [157] = "Typhlosion",
    [158] = "Totodile", [159] = "Croconaw", [160] = "Feraligatr",
    [161] = "Sentret", [162] = "Furret",
    [163] = "Hoothoot", [164] = "Noctowl",
    [165] = "Ledyba", [166] = "Ledian",
    [167] = "Spinarak", [168] = "Ariados",
    [169] = "Crobat",
    [170] = "Chinchou", [171] = "Lanturn",
    [172] = "Pichu",
    [173] = "Cleffa",
    [174] = "Igglybuff",
    [175] = "Togepi", [176] = "Togetic",
    [177] = "Natu", [178] = "Xatu",
    [179] = "Mareep", [180] = "Flaaffy", [181] = "Ampharos",
    [182] = "Bellossom",
    [183] = "Marill", [184] = "Azumarill",
    [185] = "Sudowoodo",
    [186] = "Politoed",
    [187] = "Hoppip", [188] = "Skiploom", [189] = "Jumpluff",
    [190] = "Aipom",
    [191] = "Sunkern", [192] = "Sunflora",
    [193] = "Yanma",
    [194] = "Wooper", [195] = "Quagsire",
    [196] = "Espeon", [197] = "Umbreon",
    [198] = "Murkrow",
    [199] = "Slowking",
    [200] = "Misdreavus",
    [201] = "Unown",
    [202] = "Wobbuffet",
    [203] = "Girafarig",
    [204] = "Pineco", [205] = "Forretress",
    [206] = "Dunsparce",
    [207] = "Gligar",
    [208] = "Steelix",
    [209] = "Snubbull", [210] = "Granbull",
    [211] = "Qwilfish",
    [212] = "Scizor",
    [213] = "Shuckle",
    [214] = "Heracross",
    [215] = "Sneasel",
    [216] = "Teddiursa", [217] = "Ursaring",
    [218] = "Slugma", [219] = "Magcargo",
    [220] = "Swinub", [221] = "Piloswine",
    [222] = "Corsola",
    [223] = "Remoraid", [224] = "Octillery",
    [225] = "Delibird",
    [226] = "Mantine",
    [227] = "Skarmory",
    [228] = "Houndour", [229] = "Houndoom",
    [230] = "Kingdra",
    [231] = "Phanpy", [232] = "Donphan",
    [233] = "Porygon2",
    [234] = "Stantler",
    [235] = "Smeargle",
    [236] = "Tyrogue", [237] = "Hitmontop",
    [238] = "Smoochum",
    [239] = "Elekid",
    [240] = "Magby",
    [241] = "Miltank",
    [242] = "Blissey",
    [243] = "Raikou", [244] = "Entei", [245] = "Suicune",
    [246] = "Larvitar", [247] = "Pupitar", [248] = "Tyranitar",
    [249] = "Lugia", [250] = "Ho-Oh",
    [251] = "Celebi",
    -- Gen 3 Pokemon (Hoenn Dex)
    [252] = "Treecko", [253] = "Grovyle", [254] = "Sceptile",
    [255] = "Torchic", [256] = "Combusken", [257] = "Blaziken",
    [258] = "Mudkip", [259] = "Marshtomp", [260] = "Swampert",
    [261] = "Poochyena", [262] = "Mightyena",
    [263] = "Zigzagoon", [264] = "Linoone",
    [276] = "Taillow", [277] = "Swellow",
    [278] = "Wingull", [279] = "Pelipper",
    [280] = "Ralts", [281] = "Kirlia", [282] = "Gardevoir",
    [293] = "Whismur", [294] = "Loudred", [295] = "Exploud",
    [304] = "Aron", [305] = "Lairon", [306] = "Aggron",
    [315] = "Roselia",
    [318] = "Carvanha", [319] = "Sharpedo",
    [333] = "Swablu", [334] = "Altaria",
    [339] = "Barboach", [340] = "Whiscash",
    [371] = "Bagon", [372] = "Shelgon", [373] = "Salamence",
    [374] = "Beldum", [375] = "Metang", [376] = "Metagross",
    [380] = "Latias", [381] = "Latios",
    [382] = "Kyogre", [383] = "Groudon", [384] = "Rayquaza",
    -- Gen 4 Pokemon (Sinnoh Dex)
    [387] = "Turtwig", [388] = "Grotle", [389] = "Torterra",
    [390] = "Chimchar", [391] = "Monferno", [392] = "Infernape",
    [393] = "Piplup", [394] = "Prinplup", [395] = "Empoleon",
    [396] = "Starly", [397] = "Staravia", [398] = "Staraptor",
    [399] = "Bidoof", [400] = "Bibarel",
    [401] = "Kricketot", [402] = "Kricketune",
    [403] = "Shinx", [404] = "Luxio", [405] = "Luxray",
    [406] = "Budew", [407] = "Roserade",
    [418] = "Buizel", [419] = "Floatzel",
    [420] = "Cherubi", [421] = "Cherrim",
    [422] = "Shellos", [423] = "Gastrodon",
    [443] = "Gible", [444] = "Gabite", [445] = "Garchomp",
    [447] = "Riolu", [448] = "Lucario",
    [459] = "Snover", [460] = "Abomasnow",
    [461] = "Weavile",
    [462] = "Magnezone",
    [463] = "Lickilicky",
    [464] = "Rhyperior",
    [465] = "Tangrowth",
    [466] = "Electivire",
    [467] = "Magmortar",
    [468] = "Togekiss",
    [469] = "Yanmega",
    [470] = "Leafeon",
    [471] = "Glaceon",
    [472] = "Gliscor",
    [473] = "Mamoswine",
    [474] = "Porygon-Z",
    [475] = "Gallade",
    [476] = "Probopass",
    [477] = "Dusknoir",
    [478] = "Froslass",
    [479] = "Rotom",
    [480] = "Uxie", [481] = "Mesprit", [482] = "Azelf",
    [483] = "Dialga", [484] = "Palkia",
    [485] = "Heatran",
    [486] = "Regigigas",
    [487] = "Giratina",
    [488] = "Cresselia",
    [489] = "Phione",
    [490] = "Manaphy",
    [491] = "Darkrai",
    [492] = "Shaymin",
    [493] = "Arceus"
}

-- =============================================================================
-- STATE TRACKING
-- =============================================================================
local last_exported_pid = nil  -- Track last exported personality ID to prevent duplicates

-- =============================================================================
-- T012: MEMORY READING FUNCTIONS
-- =============================================================================

-- Read 32-bit Personality ID (PID) from Pokemon data
-- @param pokemon_addr: Base address of Pokemon structure
-- @return: 32-bit PID (unsigned) or nil if invalid
function read_personality_value(pokemon_addr)
    if not memory.isvalid(pokemon_addr + PID_OFFSET) then
        print("[ERROR] Invalid address for PID read: " .. string.format("0x%X", pokemon_addr))
        return nil
    end

    local pid = memory.readdword(pokemon_addr + PID_OFFSET)

    if CONFIG.enable_logging then
        print("[INFO] Read PID: " .. pid .. " from address " .. string.format("0x%X", pokemon_addr))
    end

    return pid
end

-- Calculate block shuffle order from PID
-- @param pid: 32-bit Personality ID
-- @return: Table of block indices {A, B, C, D} in shuffled order
function calculate_block_shuffle(pid)
    -- Extract shift value from PID
    -- Formula: (PID & 0x3E000) >> 0xD
    local shift_value = math.floor((pid % 0x40000) / 0x2000)  -- Equivalent to (pid & 0x3E000) >> 13

    local shuffle_order = BLOCK_SHUFFLE_TABLE[shift_value]

    if shuffle_order == nil then
        print("[ERROR] Invalid shift value: " .. shift_value .. " from PID: " .. pid)
        return {0, 1, 2, 3}  -- Default to ABCD
    end

    if CONFIG.enable_logging then
        print("[INFO] Block shuffle order for PID " .. pid .. ": " .. table.concat(shuffle_order, ", "))
    end

    return shuffle_order
end

-- Decrypt species ID from encrypted Pokemon data
-- @param pokemon_addr: Base address of Pokemon structure
-- @param pid: Personality ID (for shuffle calculation)
-- @return: Species ID (1-493) or nil if decryption fails
function decrypt_species_id(pokemon_addr, pid)
    -- Read checksum for XOR decryption
    if not memory.isvalid(pokemon_addr + CHECKSUM_OFFSET) then
        print("[ERROR] Invalid address for checksum read")
        return nil
    end

    local checksum = memory.readword(pokemon_addr + CHECKSUM_OFFSET)

    -- Calculate block shuffle order
    local shuffle_order = calculate_block_shuffle(pid)

    -- Species ID is in Block A, offset 8 within the block
    -- Block size is 32 bytes (0x20)
    -- Need to find where Block A is located after shuffling
    local block_a_index = 0
    for i = 0, 3 do
        if shuffle_order[i + 1] == 0 then  -- Lua tables are 1-indexed
            block_a_index = i
            break
        end
    end

    -- Calculate address of Block A in shuffled data
    local block_a_addr = pokemon_addr + ENCRYPTED_DATA_START + (block_a_index * 32)
    local species_offset_in_block = 8

    -- Read encrypted species ID (16-bit)
    if not memory.isvalid(block_a_addr + species_offset_in_block) then
        print("[ERROR] Invalid address for species ID read")
        return nil
    end

    local encrypted_species = memory.readword(block_a_addr + species_offset_in_block)

    -- Decrypt using checksum XOR
    local species_id = encrypted_species
    if species_id < 1 or species_id > 493 then
        -- Try XOR decryption
        species_id = bit.bxor(encrypted_species, checksum)
    end

    -- Validate species ID range
    if species_id < 1 or species_id > 493 then
        print("[ERROR] Decrypted species ID out of range: " .. species_id)
        return nil
    end

    if CONFIG.enable_logging then
        local species_name = SPECIES_NAMES[species_id] or "Unknown"
        print("[INFO] Decrypted species ID: " .. species_id .. " (" .. species_name .. ")")
    end

    return species_id
end

-- Read Pokemon level (unencrypted)
-- @param pokemon_addr: Base address of Pokemon structure
-- @return: Level (1-100) or nil if invalid
function read_level(pokemon_addr)
    if not memory.isvalid(pokemon_addr + LEVEL_OFFSET) then
        print("[ERROR] Invalid address for level read")
        return nil
    end

    local level = memory.readbyte(pokemon_addr + LEVEL_OFFSET)

    if level < 1 or level > 100 then
        print("[ERROR] Level out of range: " .. level)
        return nil
    end

    if CONFIG.enable_logging then
        print("[INFO] Read level: " .. level)
    end

    return level
end

-- Read Pokemon HP (current and max, unencrypted)
-- @param pokemon_addr: Base address of Pokemon structure
-- @return: Table {current_hp, max_hp} or nil if invalid
function read_hp(pokemon_addr)
    if not memory.isvalid(pokemon_addr + CURRENT_HP_OFFSET) or
       not memory.isvalid(pokemon_addr + MAX_HP_OFFSET) then
        print("[ERROR] Invalid address for HP read")
        return nil
    end

    local current_hp = memory.readword(pokemon_addr + CURRENT_HP_OFFSET)
    local max_hp = memory.readword(pokemon_addr + MAX_HP_OFFSET)

    if max_hp == 0 then
        print("[ERROR] Max HP is zero")
        return nil
    end

    if current_hp > max_hp then
        print("[ERROR] Current HP exceeds max HP: " .. current_hp .. " > " .. max_hp)
        return nil
    end

    if CONFIG.enable_logging then
        print("[INFO] Read HP: " .. current_hp .. "/" .. max_hp)
    end

    return {current_hp = current_hp, max_hp = max_hp}
end

-- =============================================================================
-- T013: ENCOUNTER DETECTION AND CLASSIFICATION
-- =============================================================================

-- Check if enemy Pokemon exists in battle
-- @return: Enemy Pokemon address or nil
function check_enemy_pokemon_exists()
    -- Read base pointer
    if not memory.isvalid(PARTY_POINTER_ADDR) then
        print("[ERROR] Invalid party pointer address")
        return nil
    end

    local base_pointer = memory.readdword(PARTY_POINTER_ADDR)

    if base_pointer == 0 then
        return nil  -- No battle active
    end

    -- Calculate enemy Pokemon address
    local enemy_addr = base_pointer + ENEMY_OFFSET

    -- Validate enemy address
    if not memory.isvalid(enemy_addr) then
        return nil  -- Enemy slot empty
    end

    -- Check if enemy has valid data (read PID as existence check)
    local pid = memory.readdword(enemy_addr + PID_OFFSET)
    if pid == 0 then
        return nil  -- No Pokemon in enemy slot
    end

    return enemy_addr
end

-- Classify encounter type based on species ID
-- @param species_id: National Dex number
-- @return: "wild" or "legendary"
function classify_encounter_type(species_id)
    if CONFIG.track_legendaries and LEGENDARY_SPECIES[species_id] then
        return "legendary"
    else
        return "wild"
    end
end

-- Detect new encounter (state machine to avoid re-exporting same Pokemon)
-- @return: Table with Pokemon data or nil if no new encounter
function detect_new_encounter()
    local enemy_addr = check_enemy_pokemon_exists()

    if enemy_addr == nil then
        -- No battle or enemy Pokemon not present
        return nil
    end

    -- Read personality ID
    local pid = read_personality_value(enemy_addr)
    if pid == nil then
        return nil  -- Failed to read PID
    end

    -- Check if this is the same Pokemon we already exported
    if pid == last_exported_pid then
        return nil  -- Already exported this encounter
    end

    -- New encounter detected! Extract full data
    local species_id = decrypt_species_id(enemy_addr, pid)
    if species_id == nil then
        print("[ERROR] Failed to decrypt species ID")
        return nil
    end

    local level = read_level(enemy_addr)
    if level == nil then
        return nil
    end

    local hp_data = read_hp(enemy_addr)
    if hp_data == nil then
        return nil
    end

    -- Classify encounter type
    local encounter_type = classify_encounter_type(species_id)

    -- Get species name
    local species_name = SPECIES_NAMES[species_id] or "Unknown"

    if CONFIG.enable_logging then
        print("[INFO] NEW ENCOUNTER DETECTED!")
        print("[INFO] Species: " .. species_name .. " (#" .. species_id .. ")")
        print("[INFO] Level: " .. level)
        print("[INFO] HP: " .. hp_data.current_hp .. "/" .. hp_data.max_hp)
        print("[INFO] Type: " .. encounter_type)
    end

    -- Store PID to prevent re-export
    last_exported_pid = pid

    -- Return structured encounter data
    return {
        species_id = species_id,
        species_name = species_name,
        level = level,
        current_hp = hp_data.current_hp,
        max_hp = hp_data.max_hp,
        encounter_type = encounter_type,
        personality_value = pid
    }
end

-- =============================================================================
-- T014: JSON EXPORT FUNCTIONALITY
-- =============================================================================

-- Generate ISO 8601 timestamp (UTC)
-- @return: Timestamp string in format "YYYY-MM-DDTHH:MM:SSZ"
function generate_timestamp()
    -- DeSmuME Lua does not have os.date with UTC support reliably
    -- Use simple timestamp format (note: may not be true UTC without system config)
    local timestamp = os.date("!%Y-%m-%dT%H:%M:%SZ")  -- ! prefix for UTC on some systems
    return timestamp
end

-- Generate JSON filename from timestamp and player name
-- @param timestamp_raw: Raw timestamp for file naming (YYYYMMDD_HHMMSS format)
-- @param player_name: Player identifier
-- @return: Filename string
function generate_filename(timestamp_raw, player_name)
    -- Format: encounter_YYYYMMDD_HHMMSS_PlayerName.json
    local filename = "encounter_" .. timestamp_raw .. "_" .. player_name .. ".json"
    return filename
end

-- Build JSON structure from encounter data
-- @param pokemon_data: Table with encounter fields
-- @param timestamp: ISO 8601 timestamp
-- @return: JSON string
function build_encounter_json(pokemon_data, timestamp)
    -- Note: Lua does not have native JSON library
    -- Manual JSON construction (simple but works for this schema)
    local json = "{\n"
    json = json .. '  "timestamp": "' .. timestamp .. '",\n'
    json = json .. '  "player_name": "' .. CONFIG.player_name .. '",\n'
    json = json .. '  "species_id": ' .. pokemon_data.species_id .. ',\n'
    json = json .. '  "species_name": "' .. pokemon_data.species_name .. '",\n'
    json = json .. '  "level": ' .. pokemon_data.level .. ',\n'
    json = json .. '  "current_hp": ' .. pokemon_data.current_hp .. ',\n'
    json = json .. '  "max_hp": ' .. pokemon_data.max_hp .. ',\n'
    json = json .. '  "location_id": null,\n'  -- MVP: location detection deferred
    json = json .. '  "location_name": "Unknown",\n'
    json = json .. '  "encounter_type": "' .. pokemon_data.encounter_type .. '",\n'
    json = json .. '  "status": "encountered",\n'
    json = json .. '  "personality_value": ' .. pokemon_data.personality_value .. '\n'
    json = json .. "}"

    return json
end

-- Write JSON file to disk
-- @param filepath: Full path to output file
-- @param json_content: JSON string
-- @return: true if successful, false otherwise
function write_json_file(filepath, json_content)
    local file, err = io.open(filepath, "w")

    if not file then
        print("[ERROR] Failed to open file for writing: " .. filepath)
        print("[ERROR] Error: " .. tostring(err))
        return false
    end

    file:write(json_content)
    file:close()

    if CONFIG.enable_logging then
        print("[INFO] JSON exported: " .. filepath)
    end

    return true
end

-- =============================================================================
-- T015: POLLING LOOP AND CONFIGURATION VALIDATION
-- =============================================================================

-- Main polling loop
function main_loop()
    -- Validate configuration
    validate_config()

    -- Startup message
    print("=============================================================================")
    print("HGSS ENCOUNTER TRACKER - SOULLINK EDITION")
    print("=============================================================================")
    print("[INFO] Tracker started successfully")
    print("[INFO] Player: " .. CONFIG.player_name)
    print("[INFO] Polling interval: " .. CONFIG.polling_interval .. "s")
    print("[INFO] Waiting for wild Pokemon encounters...")
    print("=============================================================================")

    -- Main loop (runs every frame in DeSmuME)
    local frame_count = 0
    local frames_per_poll = math.floor(60 * CONFIG.polling_interval)  -- Assume 60 FPS

    while true do
        frame_count = frame_count + 1

        -- Poll at configured interval
        if frame_count >= frames_per_poll then
            frame_count = 0

            -- Detect new encounter
            local encounter_data = detect_new_encounter()

            if encounter_data ~= nil then
                -- Generate timestamp
                local timestamp_iso = generate_timestamp()
                local timestamp_file = os.date("!%Y%m%d_%H%M%S")  -- For filename

                -- Build JSON
                local json_content = build_encounter_json(encounter_data, timestamp_iso)

                -- Generate filename
                local filename = generate_filename(timestamp_file, CONFIG.player_name)
                local filepath = CONFIG.json_output_dir .. filename

                -- Write to file
                local success = write_json_file(filepath, json_content)

                if success then
                    print("[INFO] ✓ Encounter exported successfully")
                else
                    print("[ERROR] ✗ Failed to export encounter")
                end
            end
        end

        -- Yield to emulator (required for DeSmuME Lua)
        emu.frameadvance()
    end
end

-- =============================================================================
-- SCRIPT ENTRY POINT
-- =============================================================================
-- Start the main loop
main_loop()
