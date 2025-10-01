# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Soullink Tracker** is an automated Pokemon encounter tracking system for Soullink runs that monitors real-time encounters from DeSmuME emulator (Pokemon Soul Silver/Heart Gold) and enforces Soullink rules across multiple players.

**Core Rule**: Once a Pokemon species is caught by any player, no other player can catch that species.

### Architecture

Real-time monitoring pipeline:
```
DeSmuME (Lua) → JSON Files → Python Watcher → SQLite → FastAPI/WebSocket → Web Dashboard
```

**Technology Stack**:
- Backend: FastAPI, Python watchdog, SQLite3, Pydantic
- Frontend: HTML5 + Vanilla JavaScript, Tailwind CSS (CDN), WebSocket client
- Emulator: DeSmuME Lua API for memory reading

**Target Platform**: Windows-only, Pokemon HGSS (USA version), 3 concurrent players

## Development Workflow System

This project uses a **specification-driven development workflow** with custom slash commands located in `Soullink_Tracker_planned/.claude/commands/`:

### Custom Commands

- `/constitution` - Create/update project constitution defining core principles
- `/specify` - Generate feature specification from user requirements
- `/clarify` - Interactive clarification session for ambiguous requirements
- `/plan` - Execute implementation planning workflow (Phases 0-1)
- `/tasks` - Generate task breakdown from implementation plan (Phase 2)
- `/implement` - Execute implementation plan by processing tasks.md
- `/analyze` - Analyze existing features or codebase structure

### Workflow Sequence

1. **Specification Phase**: `/specify` → creates `specs/[###-feature]/spec.md`
2. **Clarification Phase**: `/clarify` → adds clarifications to spec if needed
3. **Planning Phase**: `/plan` → generates research, data-model, contracts, quickstart
4. **Task Generation**: `/tasks` → creates tasks.md with TDD workflow
5. **Implementation Phase**: `/implement` → executes tasks sequentially/parallel

### Key Files Generated

Each feature creates a spec directory at `Soullink_Tracker_planned/specs/[###-feature]/`:
- `spec.md` - Business requirements (WHAT, not HOW)
- `plan.md` - Technical implementation plan
- `research.md` - Technical decisions and rationale
- `data-model.md` - Entities and relationships
- `contracts/` - API specifications and test requirements
- `quickstart.md` - Integration scenarios
- `tasks.md` - Sequential/parallel task breakdown

### Constitution

The project constitution at `Soullink_Tracker_planned/.specify/memory/constitution.md` defines non-negotiable development principles. All feature work must comply with constitutional requirements (verified via Constitution Check gates in plan.md).

## Critical Memory Addresses (HGSS USA)

```
Pokemon Data Range: 0x002C0BC2 - 0x002D5780
Pokemon Structure: 128 bytes (0x80 hex) per Pokemon
Species ID: Offset 0x00-0x01
Level: Offset 0x34
Current HP: Offset 0x4C-0x4D
Personality ID: Offset 0x68-0x6B
Game Language: 0x02FFFE0F
Seed Offset: 0xAC0
```

## Database Schema

### Encounters Table
- `timestamp`, `player_name`
- `species_id`, `species_name`, `level`, `location`
- `status` (encountered/caught/ko/run)
- `is_duplicate` flag

### Soullink Rules Table
- `species_id` (unique)
- `caught_by_player`
- `caught_at` timestamp

## Performance Requirements

- End-to-end latency: < 3 seconds for encounter updates
- Database queries: < 100ms response time
- Memory polling: Every 1 second
- Offline buffer: JSON files persist during connection loss

## Launch Sequence

1. Start DeSmuME emulator
2. Load Soul Silver/Heart Gold ROM
3. Load Lua script in DeSmuME
4. Start Python watcher service
5. Initialize SQLite database
6. Launch FastAPI server
7. Open web dashboard
8. Begin playing and monitoring

## Design Principles

- **KISS Principle**: Keep everything simple
- **MVP First**: Encounter detection before advanced features
- **Iterative Development**: Expand features gradually
- **Manual Fallbacks**: User can override automation
- **TDD Workflow**: Tests written → approved → fail → implement
