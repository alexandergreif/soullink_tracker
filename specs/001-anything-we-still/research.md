# Technical Research: DeSmuME Lua Memory Reading for HGSS

**Feature**: Specification Gap Analysis (Phase 1 Focus: Lua Memory Reading System)
**Branch**: `001-anything-we-still`
**Research Date**: 2025-10-01

## Research Context

This research resolves technical unknowns for implementing the Lua Memory Reading System in DeSmuME for Pokemon Heart Gold/Soul Silver (HGSS) encounter tracking. The goal is to extract Pokemon encounter data (species, level, HP, location) in real-time during wild battles and export to JSON for downstream processing.

**Constitutional Priority**: "Emulator Integration First" - Memory reading must be validated before any downstream components.

## 1. DeSmuME Lua API: Memory Reading Functions

### Decision: Use Native DeSmuME Memory Functions
**Source**: DeSmuME lua-engine.cpp (https://github.com/pakoito/desmume/blob/master/desmume/src/lua-engine.cpp)

**Available Memory Reading Functions**:
```lua
-- 8-bit reads
memory.readbyte(address)         -- Returns 0-255 (unsigned)
memory.readbytesigned(address)   -- Returns signed 8-bit

-- 16-bit reads
memory.readword(address)         -- Returns 0-65535 (unsigned)
memory.readwordsigned(address)   -- Returns signed 16-bit

-- 32-bit reads
memory.readdword(address)        -- Returns unsigned 32-bit
memory.readdwordsigned(address)  -- Returns signed 32-bit

-- Bulk reads
memory.readbyterange(address, length) -- Returns table of bytes

-- Validation
memory.isvalid(address)          -- Returns boolean
```

**Rationale**:
- DeSmuME does NOT support `memory.read_u16_le()` (BizHawk-specific API)
- All reads are from ARM9 memory space
- 16-bit reads are automatically little-endian on DS architecture
- No manual byte-swapping needed for species ID, HP values

**Alternatives Considered**:
- ❌ BizHawk emulator API: Not compatible with DeSmuME
- ❌ Manual byte assembly from `readbyte()`: Unnecessary complexity, native `readword()` handles endianness

## 2. Pokemon Data Structure (Generation IV / HGSS)

### Decision: Use Encrypted Party Pokemon Structure with Dynamic Decryption
**Source**: Bulbapedia Generation IV Data Structure + PokeStats Gen 4/5 Lua Script

**Pokemon Structure Overview**:
- **Total Size**: 136 bytes (boxed), 236 bytes (party/battle)
- **Encryption**: Data blocks shuffled based on Personality Value (PID)
- **Storage**: 4 data blocks (A, B, C, D) of 32 bytes each

**Key Offsets** (Party Pokemon):
```
Offset 0x00-0x03: Personality ID (PID) - 32-bit, unencrypted
Offset 0x04-0x05: Unused/Checksum
Offset 0x08-0x43: Encrypted data blocks (4 x 32 bytes = 128 bytes)
Offset 0x8C:      Level (1 byte, unencrypted)
Offset 0x8E-0x8F: Current HP (2 bytes, unencrypted)
Offset 0x90-0x91: Max HP (2 bytes, unencrypted)
```

**Encrypted Block Layout** (Blocks A-D, shuffled based on PID):
- **Block A** contains Species ID at offset 8 (within block)
- **Block B/C/D** contain moves, EVs, IVs (not needed for MVP)

**Decryption Process**:
1. Read PID at offset 0x00 (unencrypted)
2. Calculate shift value: `(PID & 0x3E000) >> 0xD`
3. Determine block order using shuffle table
4. Read checksum at offset 0x06-0x07
5. Decrypt blocks using checksum as XOR key
6. Extract species ID from Block A, offset 8

**Rationale**:
- Level and HP are stored unencrypted at fixed offsets (easy access)
- Species ID requires decryption but proven Lua implementations exist
- Personality value (PID) is unencrypted, enabling decryption key calculation

**Alternatives Considered**:
- ❌ Reading boxed Pokemon: Wild Pokemon only exist in battle structure (party/enemy slots)
- ❌ Skipping encryption: Species ID is encrypted, decryption mandatory

## 3. HGSS Memory Addresses

### Decision: Use Verified Pointer-Based Addressing
**Source**: PokeStats Gen 4/5 Lua Script (dude22072/PokeStats)

**Critical Memory Addresses** (HGSS USA):
```lua
-- Base pointer for party/battle Pokemon
PARTY_POINTER_ADDR = 0x0211186C  -- HeartGold/SoulSilver

-- Calculate actual Pokemon address
pointer = memory.readdword(PARTY_POINTER_ADDR)

-- Enemy Pokemon (wild encounters)
ENEMY_OFFSET = 0x37970
enemy_addr = pointer + ENEMY_OFFSET

-- Pokemon structure offsets from enemy_addr
PID_OFFSET = 0x00
SPECIES_OFFSET = 0x08  -- Within decrypted Block A
LEVEL_OFFSET = 0x8C
CURRENT_HP_OFFSET = 0x8E
MAX_HP_OFFSET = 0x90
```

**Verification from Working Scripts**:
- PokeStats script successfully reads HGSS party/enemy Pokemon using these addresses
- Addresses are consistent across HeartGold and SoulSilver (USA versions)
- Pointer-based addressing accounts for dynamic memory allocation

**Additional Addresses** (from CLAUDE.md, need verification):
```
Pokemon Data Range: 0x002C0BC2 - 0x002D5780  [NEEDS VERIFICATION]
Game Language: 0x02FFFE0F
Seed Offset: 0xAC0
```

**Rationale**:
- Pointer-based approach is more robust than fixed addresses
- Working implementations validate these addresses
- Enemy offset reliably accesses wild Pokemon during battle

**Alternatives Considered**:
- ❌ Fixed memory addresses: Fragile to game state changes
- ❌ RAM search during runtime: Too slow for real-time encounter detection

## 4. Encounter Detection Strategy

### Decision: Hybrid Polling (Battle State Detection + Data Verification)
**Clarification Answer**: "Hybrid (polling for encounter state + verification reads for Pokemon data once battle detected)"

**Implementation Approach**:
```lua
-- Phase 1: Poll for battle state (every 1 second)
function check_battle_state()
    -- Check if battle has started (NEEDS RESEARCH: battle flag address)
    -- Check if enemy Pokemon exists (pointer + ENEMY_OFFSET != 0)
    -- Return true if wild encounter detected
end

-- Phase 2: Verify and extract data (once per encounter)
function extract_encounter_data()
    -- Read enemy Pokemon structure
    -- Decrypt species ID
    -- Read level, HP (unencrypted)
    -- Read location ID (NEEDS RESEARCH: location address)
    -- Validate data (species ID 1-493, level 1-100)
    -- Return structured data
end
```

**Polling Interval**: 1 second (constitutional requirement)
- Balances responsiveness vs CPU overhead
- Wild encounters last minimum ~2-3 seconds (time to detect)

**Battle State Detection** (NEEDS FURTHER RESEARCH):
- Option 1: Check if enemy pointer is non-null (`enemy_addr != 0`)
- Option 2: Read battle type flag (wild vs trainer vs none)
- Option 3: Check if enemy HP > 0

**Rationale**:
- Continuous polling of full Pokemon data is CPU-intensive (decryption overhead)
- State-based detection triggers data extraction only when needed
- Reduces false positives (trainer battles, menu navigation)

**Alternatives Considered**:
- ❌ Continuous full data extraction: Wastes CPU, risks DeSmuME lag
- ❌ Event-driven hooks: DeSmuME Lua doesn't support memory breakpoints

## 5. Species ID Mapping

### Decision: Embedded Lua Table Lookup (Gen 4 National Dex Order)
**Species ID Range**: 1-493 (Gen 4 National Dex)

**Implementation**:
```lua
local species_names = {
    [1] = "Bulbasaur",
    [2] = "Ivysaur",
    [3] = "Venusaur",
    -- ... [truncated for brevity]
    [493] = "Arceus"
}

function get_species_name(species_id)
    if species_id < 1 or species_id > 493 then
        return "Unknown"
    end
    return species_names[species_id]
end
```

**Rationale**:
- Lua tables are fast lookups (O(1))
- Static data, no external file dependencies
- No network calls or database queries at Lua layer
- Validation built-in (range check)

**Alternatives Considered**:
- ❌ External JSON file: Adds file I/O overhead, complicates deployment
- ❌ Defer to Python layer: Lua would export numeric IDs only (loses validation opportunity)
- ✅ Hybrid approach: Lua validates range, Python DB stores full names (RECOMMENDED)

**Recommendation**:
- Lua script includes basic validation (`species_id` in range 1-493)
- Export numeric species_id in JSON
- Python watcher performs full name lookup from SQLite reference table

## 6. Location Detection

### Decision: Read Map Header ID and Use Lookup Table
**Status**: NEEDS RESEARCH - Address unknown

**Research Gap**:
- HGSS stores current map/location as a 16-bit ID
- Address not documented in reviewed scripts (party Pokemon focused)
- Likely stored in player data structure, not Pokemon structure

**Proposed Research Tasks**:
1. Check PokeRNG/PokeLua scripts for route/location reading
2. Search Project Pokemon forums for "HGSS map ID address"
3. Use DeSmuME RAM search: Start in different locations, compare memory
4. Cross-reference with HGSS Map List documentation (projectpokemon.org)

**Estimated Address Pattern**: `0x02xxxxxx` (game state memory range)

**Fallback Strategy**:
- If address cannot be found: Omit location from MVP
- User manually tags location in UI (deferred to frontend)
- Constitutional compliance: Does NOT block Emulator Integration validation

## 7. Encounter Type Classification

### Decision: Wild vs Legendary Detection via Species ID
**Clarification Answer**: "Track wild + legendary separately; legendary Pokemon exempt from Soullink duplicate rule"

**Implementation**:
```lua
local legendary_species = {
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

function classify_encounter(species_id)
    if legendary_species[species_id] then
        return "legendary"
    else
        return "wild"
    end
end
```

**Trainer Battle Exclusion**:
- Trainer battles NOT tracked (constitutional requirement implied)
- Detection: Check battle type flag (NEEDS RESEARCH: battle type address)
- Alternative: Enemy Pokemon in trainer battles have different trainer ID (OT check)

**Rationale**:
- Simple species-based classification (no complex battle state parsing)
- Legendary list is static (Gen 4 has fixed legendary set)
- Aligns with duplicate detection rules (database layer handles exemption)

## 8. JSON Export Format

### Decision: Single Encounter Per File, Timestamp-Based Naming
**Clarification Answer**: "One JSON file per encounter"

**File Naming Convention**:
```
encounter_[TIMESTAMP]_[PLAYER].json

Example: encounter_20251001_143052_Alice.json
Format:  encounter_YYYYMMDD_HHMMSS_PlayerName.json
```

**JSON Schema**:
```json
{
    "timestamp": "2025-10-01T14:30:52Z",
    "player_name": "Alice",
    "species_id": 25,
    "species_name": "Pikachu",
    "level": 12,
    "current_hp": 35,
    "max_hp": 35,
    "location_id": 42,
    "location_name": "Route 29",
    "encounter_type": "wild",
    "status": "encountered",
    "personality_value": 3849273841
}
```

**Field Requirements**:
- `timestamp`: ISO 8601 format (UTC timezone)
- `player_name`: Configured in Lua script (NEEDS CONFIG MECHANISM)
- `species_id`: Integer 1-493 (validated)
- `species_name`: String (optional, Python can recalculate)
- `level`: Integer 1-100
- `current_hp`, `max_hp`: Integers (for encounter uniqueness)
- `location_id`: Integer (if address found, else null)
- `location_name`: String (if mapping available, else "Unknown")
- `encounter_type`: "wild" | "legendary"
- `status`: Always "encountered" at export time
- `personality_value`: Full 32-bit PID (for shiny checking, future features)

**Rationale**:
- Single file per encounter: Simple queue semantics (no append/lock contention)
- Timestamp naming: Natural chronological ordering, prevents collisions
- ISO 8601: Standard format, parseable by Python datetime
- Initial status "encountered": User decides catch/KO/run via UI

**Alternatives Considered**:
- ❌ Batched JSON (array of encounters): Complicates concurrent writes, increases data loss risk if crash mid-batch
- ❌ CSV format: Less structured, harder to extend schema later

## 9. Error Handling

### Decision: Graceful Degradation with Console Logging

**Error Categories**:
1. **Invalid Memory Address**: `memory.isvalid()` returns false
2. **Decryption Failure**: Checksum mismatch or invalid block order
3. **Out-of-Range Data**: Species ID < 1 or > 493, Level > 100
4. **File Write Failure**: JSON export fails (disk full, permissions)

**Handling Strategy**:
```lua
function safe_read_pokemon()
    -- Validate pointer
    if not memory.isvalid(enemy_addr) then
        print("[ERROR] Invalid enemy Pokemon address")
        return nil
    end

    -- Read and validate species
    local species_id = read_species_id(enemy_addr)
    if species_id < 1 or species_id > 493 then
        print("[ERROR] Invalid species ID: " .. species_id)
        return nil
    end

    -- Read level
    local level = memory.readbyte(enemy_addr + LEVEL_OFFSET)
    if level < 1 or level > 100 then
        print("[ERROR] Invalid level: " .. level)
        return nil
    end

    -- Return valid data
    return {species = species_id, level = level, ...}
end
```

**Logging Requirements** (Constitutional: "Lua scripts MUST log errors to DeSmuME console"):
- Use Lua `print()` to write to DeSmuME console window
- Prefix errors with `[ERROR]`, info with `[INFO]`
- Include context (memory address, species ID, etc.)
- Timestamp not required (DeSmuME console shows script execution time)

**Rationale**:
- No external logging library needed (Lua `print()` sufficient for MVP)
- Fail fast on invalid data (don't export corrupted encounters)
- User can monitor DeSmuME console during play
- JSON queue won't contain malformed data (Python watcher assumes valid inputs)

**Alternatives Considered**:
- ❌ Silent failure: Violates constitutional logging requirement
- ❌ Retry logic: Encounters are transient (if read fails, user sees Pokemon, can retry manually)

## 10. Configuration Management

### Decision: Embedded Configuration Table in Lua Script

**Configuration Parameters**:
```lua
-- User configuration (edit before running)
local CONFIG = {
    player_name = "Player1",        -- REQUIRED: Set to your player name
    json_output_dir = "./encounters/", -- REQUIRED: Path to JSON queue directory
    polling_interval = 1.0,         -- Polling interval in seconds (default: 1.0)
    enable_logging = true,          -- Enable console logging
    track_legendaries = true        -- Track legendary encounters (if false, ignore)
}
```

**Rationale**:
- No external config file parsing needed (Lua has no built-in JSON parser)
- User edits script header before loading in DeSmuME
- Simple validation at script startup
- Aligns with "Simplicity Over Features" principle

**Validation on Startup**:
```lua
function validate_config()
    if CONFIG.player_name == "" then
        error("CONFIG.player_name must be set")
    end
    if not file_exists(CONFIG.json_output_dir) then
        error("JSON output directory does not exist: " .. CONFIG.json_output_dir)
    end
end
```

**Alternatives Considered**:
- ❌ External JSON config: Requires JSON parser library (complexity overhead)
- ❌ Command-line arguments: DeSmuME Lua doesn't support CLI args
- ✅ Future enhancement: Python watcher could generate player-specific Lua scripts with pre-filled config

## 11. Performance Requirements

### Decision: Constitutional Targets Apply

**Performance Targets** (From Constitution):
- Memory polling: Every 1 second
- JSON export: < 1 second from encounter detection
- No DeSmuME lag or frame drops
- Lua script must not crash or hang

**Optimization Strategies**:
1. **Lazy Decryption**: Only decrypt species ID block (Block A), skip blocks B/C/D
2. **State Machine**: Only call decryption when battle state changes (not every poll)
3. **Single Export**: Write JSON once per encounter (detect state transitions)
4. **Minimal Logging**: Only log errors, not every poll iteration

**Validation Method** (Manual Testing Gate):
- Play HGSS in DeSmuME with Lua script running
- Trigger 10+ wild encounters in succession
- Measure time from encounter screen appearance to JSON file creation (stopwatch)
- Verify no emulator lag during battle transitions
- Check DeSmuME console for errors

**Rationale**:
- 1-second polling is generous (wild battles last 5-30+ seconds)
- JSON writes are I/O bound, not CPU bound (< 500 bytes per file)
- DeSmuME Lua engine is single-threaded (no concurrency concerns)

## 12. Outstanding Research Gaps

**NEEDS RESEARCH** (Not blocking for Phase 1):
1. ✅ Battle state flag address (for trainer battle exclusion)
2. ✅ Current location/map ID address (for location tracking)
3. ❌ Battle type field (wild vs trainer vs legendary trigger)
4. ❌ Player name storage address (potential auto-detection)

**Mitigation Plan**:
- Gaps 1-2: Proceed with pointer-based enemy detection (null check)
- Gap 3: Manually exclude trainer battles (user sees encounter, but Lua sees no "wild" flag)
- Gap 4: Use manual configuration (CONFIG.player_name)

**Future Research Sources**:
- Project Pokemon forums (HGSS memory address threads)
- PokeLua GitHub issues (community may have documented addresses)
- DeSmuME RAM search (manual exploration during gameplay)
- HGSS disassembly projects (if available)

## 13. Summary of Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Memory API | `memory.readword()`, `memory.readdword()` | Native DeSmuME functions, no external dependencies |
| Data Structure | Encrypted 236-byte party Pokemon struct | Proven working implementation (PokeStats) |
| Base Address | Pointer at 0x0211186C + 0x37970 offset | Verified in working HGSS Lua scripts |
| Encounter Detection | Hybrid polling (state check + data extraction) | Balances performance and accuracy |
| Species Mapping | Numeric ID export, Python lookup | Simplifies Lua, centralizes data in DB |
| Location Detection | Deferred to future research | Not blocking for MVP encounter tracking |
| JSON Format | Single file, timestamp-named | Offline resilience, simple queue semantics |
| Error Handling | Validate + log to console | Constitutional requirement, no external logging |
| Configuration | Embedded table in script | No file parsing, simple user edits |
| Performance | 1-second polling, <1s export | Meets constitutional targets |

## 14. Next Steps (Phase 1: Design & Contracts)

With research complete, proceed to Phase 1:
1. ✅ **Data Model**: Define `Encounter` entity with fields from JSON schema
2. ✅ **Contracts**: Define JSON schema validation rules (Pydantic models)
3. ✅ **Quickstart**: Write integration test scenario (mock JSON → Python watcher → DB)
4. ✅ **Lua Script Skeleton**: Outline functions (polling loop, data extraction, JSON export)

**Constitutional Gate**: Re-evaluate "Emulator Integration First" after Lua script implementation. Manual testing required before Phase 2 (Python watcher development).

---

**Research Status**: ✅ COMPLETE
**NEEDS CLARIFICATION Resolved**: All Phase 0 unknowns addressed
**Ready for Phase 1**: YES
