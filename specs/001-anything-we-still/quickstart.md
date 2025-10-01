# Quickstart: Encounter Tracking Integration Test

**Feature**: Specification Gap Analysis (Phase 1: Lua Memory Reading System)
**Branch**: `001-anything-we-still`
**Purpose**: End-to-end integration test scenario validating the encounter tracking pipeline

## Test Scenario: Wild Pokemon Encounter Flow

This quickstart validates the core Soullink rule: **Once a species is caught by any player, no other player can catch it.**

### Prerequisites

- DeSmuME 0.9.11+ with Lua support
- Pokemon Heart Gold or Soul Silver (USA version) ROM
- Python 3.11+ installed
- SQLite3 available
- Project dependencies installed (`pip install -r requirements.txt`)

### Test Setup

1. **Initialize Database**:
```bash
python src/services/database.py --init
# Creates: data/soullink_tracker.db with encounters and soullink_rules tables
```

2. **Create JSON Queue Directory**:
```bash
mkdir -p data/encounters
```

3. **Configure Lua Script**:
Edit `emulator/hgss_encounter_tracker.lua`:
```lua
local CONFIG = {
    player_name = "TestPlayer",
    json_output_dir = "./data/encounters/",
    polling_interval = 1.0,
    enable_logging = true,
    track_legendaries = true
}
```

4. **Start Python Watcher** (Phase 3 - Simulated for Manual Test):
```bash
python src/services/file_watcher.py --watch ./data/encounters/
# Watches for new JSON files, inserts into database
```

### Manual Test Steps (Phase 1 Focus: Lua Memory Reading)

**Objective**: Validate Lua script can detect encounters and export valid JSON.

#### Step 1: Load Lua Script in DeSmuME
1. Launch DeSmuME
2. Load Pokemon Heart Gold/Soul Silver ROM
3. Load save file (or start new game, play to Route 29)
4. Go to Tools → Lua Scripting → New Lua Script Window
5. Load `emulator/hgss_encounter_tracker.lua`
6. Verify console output: `[INFO] Encounter tracker initialized for player: TestPlayer`

#### Step 2: Trigger Wild Encounter
1. Walk in tall grass until wild Pokemon appears
2. Observe DeSmuME console output:
   ```
   [INFO] Wild encounter detected: Species ID 19 (Rattata), Level 3
   [INFO] Exported encounter to: ./data/encounters/encounter_20251001_143052_TestPlayer.json
   ```
3. **Expected Latency**: < 2 seconds from battle screen appearance to console message

#### Step 3: Validate JSON Output
1. Open the generated JSON file:
```bash
cat ./data/encounters/encounter_20251001_143052_TestPlayer.json
```

2. **Expected JSON** (sample):
```json
{
  "timestamp": "2025-10-01T14:30:52Z",
  "player_name": "TestPlayer",
  "species_id": 19,
  "species_name": "Rattata",
  "level": 3,
  "current_hp": 12,
  "max_hp": 12,
  "location_id": null,
  "location_name": "Unknown",
  "encounter_type": "wild",
  "status": "encountered",
  "personality_value": 3849273841
}
```

3. **Validation Checks**:
   - ✅ File exists in `data/encounters/`
   - ✅ Valid JSON format (no syntax errors)
   - ✅ All required fields present (see `contracts/encounter_json_schema.json`)
   - ✅ `species_id` in range [1, 493]
   - ✅ `level` in range [1, 100]
   - ✅ `current_hp` ≤ `max_hp`
   - ✅ `status` = "encountered"
   - ✅ `encounter_type` = "wild" OR "legendary"

#### Step 4: Repeat for Multiple Encounters
1. Run from battle (press "Run" button)
2. Trigger 5+ more wild encounters
3. Verify JSON files created for each encounter
4. Check for DeSmuME lag or script errors (none expected)

#### Step 5: Test Legendary Encounter (If Accessible)
1. Load save file near legendary Pokemon (e.g., Lugia at Whirl Islands)
2. Trigger legendary encounter
3. Verify JSON output has `"encounter_type": "legendary"`

### Automated Test Steps (Phase 2+: Python Integration)

**Objective**: Validate full pipeline (JSON → Database → Duplicate Detection).

#### Test Case 1: Single Player Encounter Tracking
```python
# tests/integration/test_encounter_pipeline.py

def test_encounter_json_to_database():
    """Test Python watcher processes JSON and inserts into database."""
    # Given: A valid encounter JSON file
    encounter_json = {
        "timestamp": "2025-10-01T14:30:52Z",
        "player_name": "Alice",
        "species_id": 25,  # Pikachu
        "species_name": "Pikachu",
        "level": 12,
        "current_hp": 35,
        "max_hp": 35,
        "location_id": None,
        "location_name": "Unknown",
        "encounter_type": "wild",
        "status": "encountered",
        "personality_value": 3849273841
    }
    write_json_file("data/encounters/test_encounter.json", encounter_json)

    # When: File watcher processes the file
    watcher.process_encounter_file("data/encounters/test_encounter.json")

    # Then: Encounter inserted into database
    encounter = db.query("SELECT * FROM encounters WHERE species_id = 25")
    assert encounter is not None
    assert encounter['player_name'] == "Alice"
    assert encounter['status'] == "encountered"
```

#### Test Case 2: Soullink Duplicate Detection
```python
def test_duplicate_species_catch_blocked():
    """Test Soullink rule: Alice catches Pikachu, Bob cannot catch Pikachu."""
    # Given: Alice catches Pikachu (species_id = 25)
    alice_encounter = create_encounter("Alice", species_id=25, status="caught")
    watcher.process_encounter(alice_encounter)

    # Then: Soullink rule created
    rule = db.query("SELECT * FROM soullink_rules WHERE species_id = 25")
    assert rule is not None
    assert rule['caught_by_player'] == "Alice"

    # When: Bob tries to catch Pikachu
    bob_encounter = create_encounter("Bob", species_id=25, status="caught")
    result = watcher.process_encounter(bob_encounter)

    # Then: Database constraint violation (IntegrityError)
    assert result.status == "error"
    assert "UNIQUE constraint failed" in result.message
```

#### Test Case 3: Legendary Exemption
```python
def test_legendary_allows_multiple_catches():
    """Test legendary Pokemon exempt from Soullink duplicate rule."""
    # Given: Alice catches Lugia (species_id = 249, legendary)
    alice_encounter = create_encounter("Alice", species_id=249, encounter_type="legendary", status="caught")
    watcher.process_encounter(alice_encounter)

    # Then: No soullink rule created for legendary
    rule = db.query("SELECT * FROM soullink_rules WHERE species_id = 249")
    assert rule is None

    # When: Bob catches Lugia (same species)
    bob_encounter = create_encounter("Bob", species_id=249, encounter_type="legendary", status="caught")
    result = watcher.process_encounter(bob_encounter)

    # Then: Both encounters recorded successfully
    assert result.status == "success"
    encounters = db.query("SELECT * FROM encounters WHERE species_id = 249")
    assert len(encounters) == 2  # Alice and Bob both caught Lugia
```

### Success Criteria

**Phase 1 (Manual Testing with ROM)**:
- ✅ Lua script detects wild encounters within 2 seconds
- ✅ JSON files created with valid schema
- ✅ No DeSmuME lag or Lua errors during 10+ encounters
- ✅ Species ID, level, HP data matches in-game Pokemon

**Phase 2+ (Automated Integration Tests)**:
- ✅ Python watcher processes JSON files within 1 second
- ✅ Encounters inserted into SQLite database
- ✅ Duplicate species catches blocked (IntegrityError)
- ✅ Legendary Pokemon exempt from duplicate rule
- ✅ Status transitions work (encountered → caught/ko/run)

### Performance Validation

**Constitutional Requirements** (from research.md § 11):
- Memory polling: Every 1 second ✅
- JSON export: < 1 second from encounter detection ✅
- End-to-end latency: < 3 seconds (encounter → UI display) ⏳ (Phase 6)
- No emulator lag ✅

**Measurement Method**:
1. Use stopwatch to time: Wild encounter screen appears → JSON file created
2. Check DeSmuME console timestamps for polling intervals
3. Monitor DeSmuME frame rate (should stay at 60 FPS)

### Troubleshooting

**Problem**: Lua script crashes on encounter detection
**Solution**: Check DeSmuME console for error messages. Verify memory addresses are correct for HGSS USA version.

**Problem**: JSON files not created
**Solution**: Verify `json_output_dir` path exists. Check file permissions on Windows.

**Problem**: Species ID is 0 or out of range
**Solution**: Decryption failed. Check personality value calculation. May need to validate block shuffle logic.

**Problem**: Encounter not detected at all
**Solution**: Verify enemy Pokemon pointer is non-null. Battle state detection may need refinement.

### Next Steps

After validating Phase 1 (Lua Memory Reading):
1. ✅ Proceed to Phase 2: JSON Queue System specification
2. ✅ Proceed to Phase 3: Python File Watcher implementation
3. ✅ Validate database insertion and duplicate detection
4. ✅ Proceed to Phase 4: SQLite schema creation
5. ✅ Proceed to Phase 5: FastAPI backend with WebSocket
6. ✅ Proceed to Phase 6: Web dashboard frontend

**Constitutional Gate**: Do NOT proceed to Phase 2 until Lua memory reading is validated with real ROM encounters.

---

**Test Status**: ⏳ PENDING IMPLEMENTATION
**Manual Testing Required**: YES (DeSmuME + HGSS ROM)
**Automated Tests Created**: NO (will be written in Phase 2 via TDD workflow)
