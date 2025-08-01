--[[
Pokemon HeartGold/SoulSilver Memory Addresses
Comprehensive memory map for different game versions and regions

This file contains memory addresses for various Pokemon HGSS versions.
Use this as a reference when configuring the pokemon_tracker.lua script.
]]

-- Memory addresses by game version and region
local MEMORY_MAPS = {
    -- Pokemon HeartGold US (IPKE)
    ["HeartGold_US"] = {
        -- Party Pokemon data
        party_pokemon = 0x02234804,      -- Base address for party Pokemon (6 slots, 236 bytes each)
        party_count = 0x02234884,        -- Number of Pokemon in party (1 byte)
        
        -- Wild Pokemon encounter data
        wild_pokemon = 0x0223AB00,       -- Wild Pokemon data during battle
        battle_state = 0x02226E18,       -- Battle state flag
        battle_type = 0x02226E1C,        -- Battle type (wild, trainer, etc.)
        
        -- Player location
        current_route = 0x02256AA4,      -- Current route/map ID
        current_map = 0x02256AA6,        -- Current map bank
        player_x = 0x02256AA8,           -- Player X coordinate
        player_y = 0x02256AAA,           -- Player Y coordinate
        
        -- Game state
        in_battle = 0x02226E18,          -- Battle active flag
        menu_state = 0x021C4D94,         -- Menu/overworld state
        game_time = 0x021BAC18,          -- Game time (hours/minutes/seconds)
        
        -- RNG and random encounters
        rng_seed = 0x021BFBD4,           -- RNG seed
        encounter_table = 0x021C0000,    -- Encounter table base
        
        -- Items and inventory
        bag_items = 0x021C4C2C,          -- Bag items
        pc_items = 0x021C7024,           -- PC item storage
        
        -- Trainer data
        trainer_id = 0x021C0100,         -- Trainer ID (4 bytes)
        secret_id = 0x021C0104,          -- Secret ID (4 bytes)
        trainer_name = 0x021C0108,       -- Trainer name (Unicode)
        
        -- Save data
        save_block_1 = 0x021C0000,       -- Save block 1 start
        save_block_2 = 0x021C8000,       -- Save block 2 start
        checksum_area = 0x021BFFF0       -- Save checksum area
    },
    
    -- Pokemon SoulSilver US (IPGE) 
    ["SoulSilver_US"] = {
        -- Party Pokemon data
        party_pokemon = 0x02234C04,      -- Base address (slightly different from HG)
        party_count = 0x02234C84,        -- Number of Pokemon in party
        
        -- Wild Pokemon encounter data  
        wild_pokemon = 0x0223AF00,       -- Wild Pokemon data during battle
        battle_state = 0x02227218,       -- Battle state flag
        battle_type = 0x0222721C,        -- Battle type
        
        -- Player location
        current_route = 0x02256EA4,      -- Current route/map ID
        current_map = 0x02256EA6,        -- Current map bank
        player_x = 0x02256EA8,           -- Player X coordinate
        player_y = 0x02256EAA,           -- Player Y coordinate
        
        -- Game state
        in_battle = 0x02227218,          -- Battle active flag
        menu_state = 0x021C5194,         -- Menu/overworld state
        game_time = 0x021BB018,          -- Game time
        
        -- RNG and encounters
        rng_seed = 0x021BFFD4,           -- RNG seed
        encounter_table = 0x021C0400,    -- Encounter table base
        
        -- Items
        bag_items = 0x021C502C,          -- Bag items
        pc_items = 0x021C7424,           -- PC items
        
        -- Trainer data
        trainer_id = 0x021C0500,         -- Trainer ID
        secret_id = 0x021C0504,          -- Secret ID
        trainer_name = 0x021C0508,       -- Trainer name
        
        -- Save data
        save_block_1 = 0x021C0400,       -- Save block 1
        save_block_2 = 0x021C8400,       -- Save block 2
        checksum_area = 0x021C03F0       -- Save checksum
    },
    
    -- Pokemon HeartGold EU (IPKP)
    ["HeartGold_EU"] = {
        -- Party Pokemon data
        party_pokemon = 0x02234A04,      -- EU version has different offsets
        party_count = 0x02234A84,
        
        -- Wild Pokemon
        wild_pokemon = 0x0223AD00,
        battle_state = 0x02227018,
        battle_type = 0x0222701C,
        
        -- Location
        current_route = 0x02256CA4,
        current_map = 0x02256CA6,
        player_x = 0x02256CA8,
        player_y = 0x02256CAA,
        
        -- Game state
        in_battle = 0x02227018,
        menu_state = 0x021C4F94,
        game_time = 0x021BAE18,
        
        -- RNG
        rng_seed = 0x021BFDD4,
        encounter_table = 0x021C0200,
        
        -- Items
        bag_items = 0x021C4E2C,
        pc_items = 0x021C7224,
        
        -- Trainer
        trainer_id = 0x021C0300,
        secret_id = 0x021C0304,
        trainer_name = 0x021C0308
    },
    
    -- Pokemon SoulSilver EU (IPGP)
    ["SoulSilver_EU"] = {
        -- Party Pokemon data
        party_pokemon = 0x02234E04,
        party_count = 0x02234E84,
        
        -- Wild Pokemon
        wild_pokemon = 0x0223B100,
        battle_state = 0x02227418,
        battle_type = 0x0222741C,
        
        -- Location
        current_route = 0x022570A4,
        current_map = 0x022570A6,
        player_x = 0x022570A8,
        player_y = 0x022570AA,
        
        -- Game state
        in_battle = 0x02227418,
        menu_state = 0x021C5394,
        game_time = 0x021BB218,
        
        -- RNG
        rng_seed = 0x021C01D4,
        encounter_table = 0x021C0600,
        
        -- Items
        bag_items = 0x021C522C,
        pc_items = 0x021C7624,
        
        -- Trainer
        trainer_id = 0x021C0700,
        secret_id = 0x021C0704,
        trainer_name = 0x021C0708
    }
}

-- Pokemon data structure (consistent across versions)
local POKEMON_STRUCTURE = {
    -- Basic data (first 48 bytes)
    species = 0x00,          -- Species ID (2 bytes)
    held_item = 0x02,        -- Held item ID (2 bytes)
    trainer_id = 0x04,       -- Original trainer ID (4 bytes)
    personality = 0x08,      -- Personality value (4 bytes)
    checksum = 0x0C,         -- Data checksum (2 bytes)
    language = 0x0E,         -- Language flag (1 byte)
    unknown_1 = 0x0F,        -- Unknown (1 byte)
    
    -- Encrypted data blocks (32 bytes, 4 blocks of 8 bytes each)
    -- The order depends on personality value
    encrypted_data = 0x10,   -- Start of encrypted blocks
    
    -- Decrypted/calculated fields (after block decryption)
    attack_stat = 0x50,      -- Attack stat (2 bytes)
    defense_stat = 0x52,     -- Defense stat (2 bytes)
    speed_stat = 0x54,       -- Speed stat (2 bytes)
    sp_attack_stat = 0x56,   -- Special Attack (2 bytes)
    sp_defense_stat = 0x58,  -- Special Defense (2 bytes)
    level = 0x54,            -- Current level (1 byte)
    
    -- HP and status
    hp_current = 0x56,       -- Current HP (2 bytes)
    hp_max = 0x58,           -- Maximum HP (2 bytes)
    status_conditions = 0x5A, -- Status conditions (1 byte)
    
    -- Location and misc
    met_location = 0x7E,     -- Where Pokemon was met (2 bytes)
    met_level = 0x80,        -- Level when met (1 byte)
    pokeball = 0x86,         -- Pokeball type (1 byte)
    
    -- Size: 236 bytes total per Pokemon
    STRUCTURE_SIZE = 236
}

-- Battle state values
local BATTLE_STATES = {
    NO_BATTLE = 0,
    BATTLE_STARTING = 1,
    IN_BATTLE = 2,
    BATTLE_ENDING = 3,
    BATTLE_ENDED = 4
}

-- Menu/game states
local GAME_STATES = {
    OVERWORLD = 0,
    IN_MENU = 1,
    IN_BATTLE = 2,
    CUTSCENE = 3,
    LOADING = 4
}

-- Encounter methods
local ENCOUNTER_METHODS = {
    GRASS = 0,
    WATER = 1,
    FISHING = 2,
    SURFING = 3,
    ROCK_SMASH = 4,
    HEADBUTT = 5,
    GIFT = 6,
    TRADE = 7,
    SPECIAL = 8
}

-- Status conditions
local STATUS_CONDITIONS = {
    HEALTHY = 0,
    ASLEEP = 1,
    POISONED = 2,
    BURNED = 3,
    FROZEN = 4,
    PARALYZED = 5,
    BADLY_POISONED = 6
}

-- Route ID mappings for HGSS
local ROUTE_MAPPINGS = {
    -- Johto routes
    [1] = "Route 29",
    [2] = "Route 30",
    [3] = "Route 31", 
    [4] = "Route 32",
    [5] = "Route 33",
    [6] = "Route 34",
    [7] = "Route 35",
    [8] = "Route 36",
    [9] = "Route 37",
    [10] = "Route 38",
    [11] = "Route 39",
    [12] = "Route 40",
    [13] = "Route 41",
    [14] = "Route 42",
    [15] = "Route 43",
    [16] = "Route 44",
    [17] = "Route 45",
    [18] = "Route 46",
    [19] = "Route 47",
    [20] = "Route 48",
    
    -- Kanto routes (post-Elite 4)
    [21] = "Route 1",
    [22] = "Route 2", 
    [23] = "Route 3",
    [24] = "Route 4",
    [25] = "Route 5",
    [26] = "Route 6",
    [27] = "Route 7",
    [28] = "Route 8",
    [29] = "Route 9",
    [30] = "Route 10",
    [31] = "Route 11",
    [32] = "Route 12",
    [33] = "Route 13",
    [34] = "Route 14",
    [35] = "Route 15",
    [36] = "Route 16",
    [37] = "Route 17",
    [38] = "Route 18",
    [39] = "Route 19",
    [40] = "Route 20",
    [41] = "Route 21",
    [42] = "Route 22",
    [43] = "Route 24",
    [44] = "Route 25",
    [45] = "Route 26",
    [46] = "Route 27",
    [47] = "Route 28",
    
    -- Special locations
    [100] = "New Bark Town",
    [101] = "Cherrygrove City",
    [102] = "Violet City",
    [103] = "Azalea Town",
    [104] = "Goldenrod City",
    [105] = "Ecruteak City",
    [106] = "Olivine City",
    [107] = "Cianwood City",
    [108] = "Mahogany Town",
    [109] = "Blackthorn City",
    [110] = "Elite Four",
    [111] = "Champion",
    
    -- Kanto cities
    [200] = "Pallet Town",
    [201] = "Viridian City",
    [202] = "Pewter City",
    [203] = "Cerulean City",
    [204] = "Vermilion City",
    [205] = "Lavender Town",
    [206] = "Celadon City",
    [207] = "Fuchsia City",
    [208] = "Saffron City",
    [209] = "Cinnabar Island",
    [210] = "Indigo Plateau"
}

-- Export the memory maps and constants
return {
    MEMORY_MAPS = MEMORY_MAPS,
    POKEMON_STRUCTURE = POKEMON_STRUCTURE,
    BATTLE_STATES = BATTLE_STATES,
    GAME_STATES = GAME_STATES,
    ENCOUNTER_METHODS = ENCOUNTER_METHODS,
    STATUS_CONDITIONS = STATUS_CONDITIONS,
    ROUTE_MAPPINGS = ROUTE_MAPPINGS
}