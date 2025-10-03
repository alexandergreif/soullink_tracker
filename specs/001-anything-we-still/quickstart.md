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

---

## T017: Step-by-Step Manual Testing Guide (Enhanced with Automated Capture)

**Objective**: Complete T017 constitutional gate with automated capture script for faster, more reliable testing.

### Prerequisites Checklist

- [ ] **Windows PC** with DeSmuME 0.9.11+ installed
- [ ] **Pokemon HGSS (USA) ROM** loaded in DeSmuME
- [ ] **Save file** near tall grass (Route 29, Route 30, or any early route)
- [ ] **Python 3.10+** with venv activated
- [ ] **Dependencies installed**: `pip install -r app/requirements.txt`
- [ ] **Playwright MCP configured** (optional but recommended for screenshots)

### Step 1: Environment Setup

**1.1 Activate Python Virtual Environment**
```bash
cd app
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows
```

**1.2 Verify Dependencies**
```bash
pip list | grep -E "watchdog|jsonschema|pydantic"
# Should show: watchdog, jsonschema, pydantic installed
```

**1.3 Create Debug Logs Directory**
```bash
mkdir -p tests/debug_logs/screenshots
```

### Step 2: Start Automated Capture Script

**2.1 Launch Capture Script**
```bash
cd app
python tests/capture_manual_test.py --start
```

**Expected Output**:
```
[INFO] Starting automated encounter capture...
[INFO] Monitoring directory: /path/to/app/data/encounters/
[INFO] Capture artifacts will be saved to: tests/debug_logs/
[INFO] Press CTRL+C to stop and generate report
```

**2.2 Keep Script Running**
- Leave this terminal open and running
- Open a **second terminal** for DeSmuME setup

### Step 3: Configure Lua Script

**3.1 Open Lua Script in Editor**
```bash
# In second terminal
nano app/emulator/hgss_encounter_tracker.lua
# OR open in your preferred editor
```

**3.2 Edit Configuration Header**
Find the `CONFIG` table at the top of the file and modify:
```lua
local CONFIG = {
    player_name = "TestPlayer",  -- Change to your name (e.g., "Alice")
    json_output_dir = "C:/Users/YourName/path/to/app/data/encounters/",  -- ABSOLUTE PATH on Windows
    polling_interval = 1.0,
    enable_logging = true,
    track_legendaries = true
}
```

**⚠️ CRITICAL**: Use **absolute path** for `json_output_dir` on Windows!

**3.3 Save and Close**
- Save the file
- Verify path exists: Check that `app/data/encounters/` directory exists

### Step 4: Load DeSmuME and Lua Script

**4.1 Launch DeSmuME**
- Open DeSmuME emulator
- Load Pokemon Heart Gold or Soul Silver ROM
- Load save file (or start new game, play to Route 29)

**4.2 Load Lua Script**
1. Go to **Tools** → **Lua Scripting** → **New Lua Script Window**
2. Click **Browse** and navigate to `app/emulator/hgss_encounter_tracker.lua`
3. Click **Open** to load the script

**4.3 Verify Script Loaded Successfully**
Check DeSmuME Lua console output:
```
[INFO] Encounter tracker initialized for player: TestPlayer
[INFO] Monitoring enemy Pokemon at memory address: 0x0211186C
[INFO] Polling every 1.0 seconds...
```

### Step 5: Trigger Wild Encounters

**5.1 Walk in Tall Grass**
- Move your character into tall grass (Route 29, Route 30, etc.)
- Wait for wild Pokemon battle to start

**5.2 Observe Real-Time Feedback**

**In DeSmuME Console**:
```
[INFO] Wild encounter detected: Species ID 19 (Rattata), Level 3
[INFO] Exported encounter to: C:/Users/.../encounter_20251002_143052_TestPlayer.json
```

**In Python Capture Script Terminal**:
```
[INFO] New file detected: encounter_20251002_143052_TestPlayer.json
[INFO] Schema validation: PASSED ✅
[INFO] Species: Rattata (ID: 19), Level: 3, HP: 12/12
[INFO] Latency: 1.2 seconds
```

**5.3 Complete Encounter**
- Press "Run" to flee from battle
- Trigger next encounter

**5.4 Repeat 10+ Times**
- Walk in grass to trigger 10+ wild encounters
- Capture script automatically records each one
- Monitor for any errors or validation failures

### Step 6: Manual Verification Checks

**6.1 Check In-Game vs. Captured Data**
For at least 3 encounters, manually verify:
- [ ] Species name matches what appears in game
- [ ] Level matches in-game display
- [ ] HP values match in-game stats

**6.2 Monitor DeSmuME Performance**
- [ ] No lag or frame drops during encounters
- [ ] Emulator maintains 60 FPS
- [ ] No Lua error messages in console

**6.3 Check JSON File Creation**
```bash
# In third terminal (or after testing)
ls app/data/encounters/
# Should show: encounter_YYYYMMDD_HHMMSS_TestPlayer.json files
```

### Step 7: Stop Capture and Generate Report

**7.1 Stop Capture Script**
- Return to terminal running `capture_manual_test.py`
- Press **CTRL+C**

**Expected Output**:
```
[INFO] Stopping capture...
[INFO] Generating capture report...
[INFO] Report saved to: tests/debug_logs/capture_report.json
[INFO] Total encounters captured: 12
[INFO] Valid encounters: 12
[INFO] Invalid encounters: 0
[INFO] Average latency: 1.3 seconds
```

**7.2 Copy DeSmuME Console Output**
1. In DeSmuME Lua console, select all text (CTRL+A)
2. Copy (CTRL+C)
3. Save to file:
```bash
# Paste into file
nano app/tests/debug_logs/lua_console.txt
# Paste and save
```

### Step 8: Review Generated Artifacts

**8.1 Check Capture Report**
```bash
cat app/tests/debug_logs/capture_report.json
```

**Expected Structure**:
```json
{
  "test_session": {
    "start_time": "2025-10-02T14:30:00Z",
    "end_time": "2025-10-02T14:45:00Z",
    "total_encounters": 12,
    "valid_encounters": 12,
    "invalid_encounters": 0,
    "average_latency": 1.3
  },
  "encounters": [
    {
      "timestamp": "2025-10-02T14:30:52Z",
      "species_id": 19,
      "species_name": "Rattata",
      "level": 3,
      "validation_result": "PASSED",
      "latency_seconds": 1.2,
      "errors": []
    },
    ...
  ]
}
```

**8.2 Check Screenshots (if Playwright enabled)**
```bash
ls app/tests/debug_logs/screenshots/
# Should show: encounter_001.png, encounter_002.png, etc.
```

### Step 9: Validate Success Criteria

Check all criteria are met:

- [ ] **No DeSmuME lag or frame drops** during testing
- [ ] **No Lua script errors** in `lua_console.txt`
- [ ] **All JSON files valid** per schema (check capture_report.json)
- [ ] **Species ID, level, HP match** in-game Pokemon (manual verification)
- [ ] **Average latency < 2 seconds** (check capture_report.json)
- [ ] **10+ successful encounters** with `valid=true`
- [ ] **No validation errors** in capture_report.json

### Step 10: Document Results

**10.1 Create Test Results Document**
```bash
nano app/tests/manual_testing_results.md
```

**10.2 Template**:
```markdown
# T017 Manual Testing Results

## Test Session Information
- **Date**: 2025-10-02
- **Tester**: [Your Name]
- **Platform**: Windows 10 / DeSmuME 0.9.11
- **ROM**: Pokemon Heart Gold (USA)

## Test Results Summary
- Total Encounters: 12
- Valid Encounters: 12
- Invalid Encounters: 0
- Average Latency: 1.3 seconds
- Emulator Performance: No lag, 60 FPS maintained

## Success Criteria
- [x] No DeSmuME lag or frame drops
- [x] No Lua script errors
- [x] All JSON files pass schema validation
- [x] Species ID, level, HP match in-game
- [x] Average latency < 2 seconds
- [x] 10+ encounters captured

## Issues Encountered
- None / [List any issues]

## Sample Encounters Verified
1. Rattata (ID: 19) - Level 3 - HP: 12/12 ✅
2. Pidgey (ID: 16) - Level 4 - HP: 15/15 ✅
3. Sentret (ID: 161) - Level 2 - HP: 10/10 ✅

## Conclusion
✅ T017 PASSED - Ready to proceed to T018
```

**10.3 Save and Commit**

### Step 11: AI-Assisted Debugging (If Issues Found)

**If you encounter validation errors or unexpected behavior:**

**11.1 Share Capture Report with Claude**
```bash
# Copy contents of capture_report.json
cat app/tests/debug_logs/capture_report.json
```

**11.2 Ask Claude to Analyze**
- Paste capture_report.json contents
- Ask: "Analyze this capture report for errors in T017 testing"
- Claude will identify:
  - Invalid species IDs (decryption failures)
  - HP constraint violations
  - Schema validation errors
  - Performance issues

**11.3 Implement Fixes**
- Claude suggests fixes to `hgss_encounter_tracker.lua`
- Apply fixes and re-run test

### Troubleshooting Common Issues

**Issue**: Capture script not detecting JSON files
**Solution**:
```bash
# Verify json_output_dir matches in both places:
# 1. Lua script CONFIG.json_output_dir
# 2. Capture script monitoring path
# Use absolute paths on Windows!
```

**Issue**: Schema validation failures
**Solution**:
```bash
# Check capture_report.json for specific errors
# Common issues:
# - species_id out of range [1-493]
# - current_hp > max_hp
# - Missing required fields
```

**Issue**: Latency > 2 seconds
**Solution**:
- Check CONFIG.polling_interval is set to 1.0
- Verify no other programs hogging CPU
- Close unnecessary background applications

**Issue**: Lua script crashes on encounter
**Solution**:
- Check DeSmuME console for error messages
- Verify ROM is USA version of HGSS
- Check memory addresses match ROM version

### Next Steps

After validating Phase 1 (Lua Memory Reading):
1. ✅ T017 PASSED → Proceed to T018 (Database initialization)
2. ✅ Proceed to Phase 3: Python File Watcher implementation
3. ✅ Validate database insertion and duplicate detection
4. ✅ Proceed to Phase 4: SQLite schema creation
5. ✅ Proceed to Phase 5: FastAPI backend with WebSocket
6. ✅ Proceed to Phase 6: Web dashboard frontend

**Constitutional Gate**: Do NOT proceed to Phase 2 until T017 is validated with real ROM encounters and results documented.

---

**Test Status**: ⏳ PENDING EXECUTION
**Manual Testing Required**: YES (DeSmuME + HGSS ROM on Windows)
**Automated Capture Script**: Created in T016a
**Documentation Required**: `tests/manual_testing_results.md`
