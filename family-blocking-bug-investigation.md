# Family Blocking Logic Bug Investigation

## Issue Summary

During v3-only migration testing on 2025-08-15, we discovered a critical bug in the Pokemon family blocking logic. The system is blocking the wrong families when Pokemon are caught, which breaks core SoulLink rules.

## Bug Description

**Expected Behavior:**
When a Pokemon is caught, its entire evolution family should be blocked globally (preventing any player from catching that family again).

**Actual Behavior:**
- Wrong families are being blocked
- Correct families that should be blocked are not being blocked
- This completely breaks the SoulLink "one family per run" rule

## Specific Test Case

### Database State (Run ID: 565db9e7-15af-427f-b2c4-4bcee601420b)

**Encounters in system:**
1. **Bulbasaur** (species_id: 1, family_id: 1) - **CAUGHT** on Route 29
2. **Charmander** (species_id: 4, family_id: 4) - **FLED** on Route 30  
3. **Squirtle** (species_id: 7, family_id: 7) - **CAUGHT** on Route 31

**Expected blocked families:**
- ✅ Family 1 (Bulbasaur line) - because Bulbasaur was caught
- ✅ Family 7 (Squirtle line) - because Squirtle was caught
- ❌ Family 4 (Charmander line) - should NOT be blocked (only encountered, fled)

**Actual blocked families (from API `/v1/runs/{run_id}/blocklist`):**
```json
{
  "blocked_families": [
    {
      "family_id": 10,
      "origin": "caught", 
      "created_at": "2025-08-15T16:45:30",
      "species_names": ["Caterpie", "Metapod", "Butterfree"]
    }
  ]
}
```

**❌ CRITICAL BUG:** Only family 10 (Caterpie) is blocked, but:
- Caterpie was never encountered or caught
- Bulbasaur and Squirtle families are missing from blocklist despite being caught

## Technical Context

### Architecture
- **V3-only event store** (post-migration from dual-write system)
- **Event sourcing** with projection engine
- **Domain-driven design** with pure functions in `domain/rules.py`

### Key Components Involved
1. **Event Processing**: `src/soullink_tracker/api/events.py::_process_event_v3()`
2. **Projection Engine**: `src/soullink_tracker/store/projections.py`
3. **Domain Rules**: `src/soullink_tracker/domain/rules.py::process_catch_result()`
4. **Family Blocking**: `FamilyBlockedEvent` and blocklist projections

### Family Blocking Flow (Expected)
1. `CatchResultEvent` with `result: "caught"` 
2. Domain rules return `CatchDecision(blocklist_add=(family_id, "caught"))`
3. Projection engine calls `_upsert_blocklist()` 
4. `Blocklist` table updated with correct family_id

## Investigation Areas

### 1. Data Isolation Issues
- Multiple test runs exist in system:
  - "Test Login Run" (565db9e7-15af-427f-b2c4-4bcee601420b) 
  - "Test manual run" (4e951621-cf63-457d-bd18-e5519eb0530d)
- Possible cross-run data pollution

### 2. Event Store Processing
- Check if `CatchResultEvent` → `FamilyBlockedEvent` conversion works correctly
- Verify projection engine applies family blocking properly
- Investigate if domain rules are returning correct `blocklist_add` values

### 3. Domain Rules Logic
File: `src/soullink_tracker/domain/rules.py`
```python
# Expected logic around line 180-185:
def process_catch_result(state: RunState, event: CatchResultEvent) -> CatchDecision:
    # Block family globally only if caught
    blocklist_add = None
    if event.result == EncounterStatus.CAUGHT:
        blocklist_add = (family_id, "caught")
    return CatchDecision(fe_finalized=fe_finalized, blocklist_add=blocklist_add)
```

### 4. Projection Engine Bug
File: `src/soullink_tracker/store/projections.py`
- `_handle_catch_result_event()` around line 250
- `_upsert_blocklist()` around line 456
- Check if `decision.blocklist_add` is being processed correctly

## Species Data Reference
```csv
id,name,family_id
1,Bulbasaur,1
4,Charmander,4  
7,Squirtle,7
10,Caterpie,10
```

## Debugging Steps Taken

1. ✅ **Verified v3-only migration successful** - Dashboard works, events processed
2. ✅ **Identified wrong blocked families** - Caterpie instead of Bulbasaur/Squirtle
3. ✅ **Confirmed encounter data integrity** - Correct Pokemon were caught/encountered
4. ✅ **Located admin panel** - Multiple test runs visible
5. 🔄 **Next: Investigate projection engine logic**

## API Endpoints for Testing

```bash
# Get encounters for run
GET /v1/runs/565db9e7-15af-427f-b2c4-4bcee601420b/encounters

# Get blocked families  
GET /v1/runs/565db9e7-15af-427f-b2c4-4bcee601420b/blocklist

# Get events (requires auth)
GET /v1/events?run_id=565db9e7-15af-427f-b2c4-4bcee601420b&since_seq=0&limit=100
```

## Impact

**High Priority Bug:**
- Breaks core SoulLink gameplay mechanic
- Players could catch multiple Pokemon from same family
- Defeats the purpose of the "one family per run" rule
- Affects competitive integrity of SoulLink runs

## Resolution Status

- ❌ **Bug confirmed and documented**
- 🔄 **Investigation in progress**  
- ⏳ **Fix pending**

## Environment Details

- **Date Found**: 2025-08-15
- **Server**: Local development (http://127.0.0.1:8000)
- **Migration Status**: V3-only (dual-write removed)
- **Database**: SQLite with WAL mode
- **Test Run**: "Test Login Run" with TestPlayer

---

## Next Investigation Steps

1. **Debug projection engine** - Add logging to `_handle_catch_result_event()`
2. **Trace domain rules** - Verify `process_catch_result()` returns correct values
3. **Check event store** - Ensure events are stored with correct family_ids
4. **Test data cleanup** - Remove old test runs to isolate issue
5. **Unit test coverage** - Add tests specifically for family blocking logic

*Investigation to be continued...*