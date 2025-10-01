# Data Model: Encounter Tracking System

**Feature**: Specification Gap Analysis (Phase 1: Lua Memory Reading System)
**Branch**: `001-anything-we-still`
**Created**: 2025-10-01

## Entity Overview

This data model defines the core entities for tracking Pokemon encounters across the Soullink Tracker pipeline (Lua → JSON → Python → SQLite → API → UI).

## 1. Encounter Entity

**Purpose**: Represents a single wild Pokemon encounter event detected by the Lua script.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `timestamp` | ISO 8601 string | Required, UTC | When encounter occurred (from DeSmuME clock) |
| `player_name` | String | Required, 1-50 chars | Player identifier (configured in Lua script) |
| `species_id` | Integer | Required, 1-493 | National Dex number (Gen 4) |
| `species_name` | String | Optional | Pokemon species name (lookup from species_id) |
| `level` | Integer | Required, 1-100 | Pokemon level |
| `current_hp` | Integer | Required, ≥0 | HP when encountered |
| `max_hp` | Integer | Required, >0 | Maximum HP stat |
| `location_id` | Integer | Optional | HGSS map/route ID (if address found) |
| `location_name` | String | Optional | Human-readable location (e.g., "Route 29") |
| `encounter_type` | Enum | Required | "wild" or "legendary" |
| `status` | Enum | Required | "encountered", "caught", "ko", "run" |
| `personality_value` | Integer (32-bit) | Required | Pokemon PID (for shiny detection, uniqueness) |

**Validation Rules**:
- `species_id` must be in range [1, 493] (Gen 4 National Dex)
- `level` must be in range [1, 100]
- `current_hp` ≤ `max_hp`
- `max_hp` > 0
- `encounter_type` = "wild" OR "legendary"
- `status` initial value: "encountered" (set by Lua)
- `status` transitions: "encountered" → ("caught" | "ko" | "run") (set by user via UI)
- `timestamp` must be valid ISO 8601 with timezone (prefer UTC)

**State Transitions**:
```
[Lua Export] → status: "encountered"
                    ↓
           [User Action in UI]
                    ↓
    ┌───────────────┼───────────────┐
    ↓               ↓               ↓
status: "caught"  status: "ko"   status: "run"
```

**Relationships**:
- Many Encounters → One SoulinkRule (via species_id, when status = "caught")
- Many Encounters → One Player (via player_name)

**Indexes** (SQLite):
- Primary key: `(timestamp, player_name, personality_value)` (composite uniqueness)
- Index on `species_id` (for duplicate lookups)
- Index on `player_name` (for player-specific queries)
- Index on `status` (for filtering caught/ko/run)

## 2. SoulinkRule Entity

**Purpose**: Enforces the core Soullink rule - once a species is caught by any player, no other player can catch it (except legendaries).

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `species_id` | Integer | Primary Key, UNIQUE | National Dex number (1-493) |
| `caught_by_player` | String | Required | Player who caught this species first |
| `caught_at` | ISO 8601 string | Required, UTC | Timestamp of first catch |

**Validation Rules**:
- `species_id` UNIQUE constraint (one species can only be caught once across all players)
- Exception: Legendary species exempt from uniqueness (see Legendary exemption logic)
- INSERT fails if `species_id` already exists (IntegrityError)

**Relationships**:
- One SoulinkRule ← Many Encounters (via species_id)

**Exemption Logic** (Legendary Pokemon):
- Legendary species (see research.md § 7 for full list) are NOT inserted into `soullink_rules` table
- All players can catch the same legendary species
- Database constraint does not apply to legendary encounters

**Indexes** (SQLite):
- Primary key on `species_id` (enforces uniqueness)

## 3. SpeciesReference Entity (Optional/Future)

**Purpose**: Static lookup table mapping species_id to species_name and legendary status.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `species_id` | Integer | Primary Key, 1-493 | National Dex number |
| `species_name` | String | Required, unique | Pokemon name (e.g., "Pikachu") |
| `is_legendary` | Boolean | Required | True if legendary, false otherwise |

**Data Population**:
- Seed data from Gen 4 National Dex (493 entries)
- Legendary flags based on constitutional clarification (18 legendary species in HGSS)

**Usage**:
- Lua script can export numeric `species_id` only
- Python watcher performs `JOIN` to add `species_name` before database insert
- Simplifies Lua script (no embedded name table)

**Status**: DEFERRED - Lua script includes embedded species name table for MVP, database table added in Phase 4 refactor if needed.

## 4. Player Entity (Optional/Future)

**Purpose**: Track registered players in multi-player mode (Phase 7).

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `player_name` | String | Primary Key | Unique player identifier |
| `registered_at` | ISO 8601 string | Required, UTC | When player joined |

**Status**: DEFERRED - MVP uses player_name strings only, no player table needed until Phase 7 (multi-player coordination).

## Data Flow Pipeline

```
[1. Lua Memory Read]
   └─> Extract Pokemon data from DeSmuME memory
       └─> Validate species_id, level, HP
           └─> Classify encounter_type (wild/legendary)

[2. JSON Export]
   └─> Write single JSON file to data/encounters/
       └─> File name: encounter_YYYYMMDD_HHMMSS_PlayerName.json
           └─> Fields: All Encounter entity fields + status="encountered"

[3. Python Watcher]
   └─> Detect new JSON file (watchdog)
       └─> Parse and validate JSON schema (Pydantic)
           └─> Insert into SQLite encounters table
               └─> If status="caught" AND NOT legendary:
                   └─> INSERT INTO soullink_rules (species_id, caught_by_player, caught_at)
                       └─> IntegrityError if duplicate → handle gracefully (log warning)

[4. Database Storage]
   └─> SQLite: encounters table (all encounters)
   └─> SQLite: soullink_rules table (caught species only, wild only)

[5. API Exposure]
   └─> FastAPI GET /encounters → query encounters table
   └─> FastAPI POST /encounters/{id}/status → update status field
   └─> WebSocket: Push encounter updates to all connected clients

[6. UI Display]
   └─> Web dashboard displays encounter feed
   └─> User clicks Catch/KO/Run button → API call → status update
   └─> Visual indicator for duplicate species (red highlight if species_id in soullink_rules)
```

## Schema Evolution

**V1 (MVP)**:
- `encounters` table with all fields listed
- `soullink_rules` table with UNIQUE constraint on species_id
- No migrations, manual schema creation

**V2 (Future)**:
- Add `species_reference` table (seed data)
- Add `players` table (multi-player coordination)
- Add `location_reference` table (map ID → location name)
- Introduce Alembic migrations for schema versioning

## Validation Examples

**Valid Encounter JSON**:
```json
{
  "timestamp": "2025-10-01T14:30:52Z",
  "player_name": "Alice",
  "species_id": 25,
  "species_name": "Pikachu",
  "level": 12,
  "current_hp": 35,
  "max_hp": 35,
  "location_id": null,
  "location_name": "Unknown",
  "encounter_type": "wild",
  "status": "encountered",
  "personality_value": 3849273841
}
```

**Invalid Encounter JSON** (species_id out of range):
```json
{
  "timestamp": "2025-10-01T14:30:52Z",
  "player_name": "Alice",
  "species_id": 999,  // ERROR: Must be 1-493
  "level": 12,
  ...
}
```

**Database Constraint Violation** (duplicate species catch):
```python
# Alice catches Pikachu (species_id = 25)
db.execute("INSERT INTO soullink_rules VALUES (25, 'Alice', '2025-10-01T14:30:52Z')")

# Bob tries to catch Pikachu (species_id = 25)
db.execute("INSERT INTO soullink_rules VALUES (25, 'Bob', '2025-10-01T15:45:10Z')")
# → IntegrityError: UNIQUE constraint failed: soullink_rules.species_id
```

## Summary

This data model supports the core Soullink rule enforcement through:
1. **Encounter tracking**: All wild Pokemon encounters recorded with full metadata
2. **Duplicate detection**: `soullink_rules` table with UNIQUE constraint on species_id
3. **Legendary exemption**: Legendary species bypass duplicate constraint
4. **Status tracking**: Encounters track full lifecycle (encountered → caught/ko/run)
5. **Offline resilience**: JSON queue persists encounters before database insert

**Next Steps**: Generate contract tests for JSON schema, create quickstart integration test scenario.
