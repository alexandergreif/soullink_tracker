# PRD – SoulLink HG/SS Tracker

**Owner:** Alex  
**Datum:** 2025-08-01 (UTC)  
**Platform:** Windows (Server & Clients)  
**Games:** Pokémon HeartGold / SoulSilver (EU-Region)  
**Emulator:** DeSmuME (Lua-Scripting, RAM Watch/Search)  
**Stack:** FastAPI + Uvicorn, SQLite (WAL), Cloudflare *Quick Tunnel*, WebSockets

---

## 1) Zweck & Ziele

**Problem**  
In einem 3-Spieler-Soul-Link-Run (randomized) müssen „First Encounters“ (inkl. globaler Dupes/Species-Clause), Fänge/Fehlschläge, verlinkte Trios und KOs zuverlässig, live und regelkonform verfolgt werden. Manuelles Tracking ist fehleranfällig und stört den Spielflow.

**Lösung (High-Level)**  
- Client-seitig liest ein **Lua-Skript in DeSmuME** Live-RAM (Map/Route-ID, Wild-Pokémon Species/Level, Party-HP; inkl. Fishing-Erkennung) und schreibt **append-only Events** (NDJSON). DeSmuME stellt **Lua-Scripting** und **RAM Watch/Search** bereit.  
- Ein **Watcher** sendet Events an eine **FastAPI** mit **Bearer-Token pro Spieler**. Der Server persistiert in **SQLite (WAL-Modus)** und pusht **WebSocket**-Events an die Web-UI. *(FastAPI unterstützt WebSockets nativ.)* citeturn0search0

**Ziele (messbar)**  
- ≥ 95 % korrekte automatische Erkennung von Encounters/Catches/Faints.  
- < 1 s Ende-zu-Ende-Latenz bis UI-Anzeige.  
- Setup pro Spieler < 15 Min (Lua + Watcher + Token).  
- Stabilität über 2 h-Session ohne Event-Verlust (Idempotenz + Retries).

---

## 2) Regeln

1. **Globaler First-Encounter mit Dupes-Clause (über alle Spieler):**  
   Für *(Spieler × Route)* wird der First-Encounter **erst final**, wenn die angetroffene **Evolutionsfamilie** **weder** global bereits als First-Encounter markiert **noch** global gefangen ist. Dupe-Begegnungen zählen **nicht**; der Spieler darf weiterbegegnen, bis eine **neue** Familie erscheint.

2. **Fishing (Phase 1)**  
   Fishing als eigene Methode mit **Old/Good/Super Rod**. Wir erfassen `encounter_method="fish"` und `rod_kind ∈ {old, good, super}`. *(HG/SS definieren für Fishing eigene Tabellen/Quoten; Safari-Zone hat beim Angeln 100 % Encounter-Rate – Validierungssignal.)*

3. **Seelenbindung (Soul Link):**  
   Pokémon, die auf derselben In-Game-Route von den drei Spielern gefangen werden, sind verlinkt. Faint (HP → 0) eines Mitglieds markiert alle verlinkten als „tot“.

4. **Einmal pro Evolutionsfamilie (global):**  
   Jede Familie darf im gesamten Run nur **einmal** gefangen werden.

---

## 3) Scope

**Im MVP**  
- Live-Erkennung: `encounter`, `catch_result`, `faint` (inkl. Fishing).  
- Server-Regeln: globale Dupes-Clause, Einmal-pro-Familie, Soul-Link-Propagation bei „Faint“.  
- Web-UI: Route-Matrix (pro Spieler), Live-Feed, Blocklist (verbrauchte Familien), Link-Details.  
- Admin: Run/Spieler anlegen, **Token generieren/rotieren**.

**Out of scope (MVP)**  
- Headbutt / Rock Smash (Phase 2).  
- Andere Emulatoren.  
- Offline-Save-Parsing.

---

## 4) Systemarchitektur

**Client je Spieler**  
- **DeSmuME + Lua**: liest RAM-Signale (Map/Route, Wild-Species/Level, Party-HP; Fishing-Heuristik) und schreibt NDJSON-Events lokal.  
- **Watcher**: tailt Datei, sendet **HTTP POST** (Idempotenz-Key, Retries/Backoff) an FastAPI.

**Server (auf Alex’ PC)**  
- **FastAPI + Uvicorn** (ASGI) – HTTP-API + **WebSocket**-Broadcasts an UI. *(WebSockets sind in FastAPI/Starlette nativ.)* citeturn0search5  
- **SQLite (WAL-Modus)** zur Persistenz; Migrationen via Alembic. *(WAL verbessert Read-Concurrency.)* citeturn0search2  
- **Cloudflare Quick Tunnel** exponiert die API nach außen **ohne Port-Forwarding** und erzeugt eine **zufällige `*.trycloudflare.com`-URL**. WebSockets werden proxied. citeturn0search1turn0search11turn0search6

**Web-UI**  
- Browser-App (kann lokal vom selben Host oder via Quick Tunnel ausgeliefert werden).  
- Daten via REST + Live über **WebSocket**.

---

## 5) Datenmodell (vereinfacht)

**Tabellen**  
- `runs(id, name, rules_json, created_at)`  
- `players(id, run_id, name, game, region, token_hash, created_at)` *(Token pro Spieler)*  
- `species(id, name, family_id)` *(Referenzdaten)*  
- `routes(id, label, region)` *(Referenzdaten, EU)*  
- `encounters(id, run_id, player_id, route_id, species_id, family_id, level, shiny, method, rod_kind, time, status, dupes_skip, fe_finalized)`  
- `links(id, run_id, route_id)`; `link_members(link_id, player_id, encounter_id)`  
- `blocklist(run_id, family_id, origin {first_encounter|caught}, created_at)`  
- `party_status(run_id, player_id, pokemon_key, alive, last_update)`  
- `idempotency_keys(key, run_id, player_id, request_hash, response_json, created_at)`

---

## 6) Event-Formate (Client → Server)

### 6.1 `encounter`
```json
{
  "type": "encounter",
  "run_id": "uuid",
  "player_id": "uuid",
  "time": "2025-08-01T18:23:05Z",
  "route_id": 31,
  "species_id": 1,
  "family_id": 1,
  "level": 7,
  "shiny": false,
  "encounter_method": "fish",   // grass|surf|fish|static|unknown
  "rod_kind": "good"            // old|good|super (nur bei fish)
}
```

### 6.2 `catch_result`
```json
{
  "type": "catch_result",
  "run_id": "uuid",
  "player_id": "uuid",
  "time": "2025-08-01T18:24:40Z",
  "encounter_ref": { "route_id": 31, "species_id": 1 },
  "status": "caught"            // caught|fled|ko|failed
}
```

### 6.3 `faint`
```json
{
  "type": "faint",
  "run_id": "uuid",
  "player_id": "uuid",
  "time": "2025-08-01T18:59:12Z",
  "pokemon_key": "personality_or_hash",
  "party_index": 2
}
```

---

## 7) API-Design (HTTP)

**Standards & Doku**  
- Spezifikation als **OpenAPI 3.1**. citeturn0search3  
- Fehlerformat **Problem Details** (`application/problem+json`), **RFC 9457** (obsolet RFC 7807). citeturn0search4

**Security**  
- **Bearer-Token pro Spieler**. Admin erzeugt/rotiert Token beim Hinzufügen von Spielern.  
- **Watcher** sendet `Authorization: Bearer <player_token>`.

**Headers**  
- `Authorization: Bearer <player_token>`  
- `Idempotency-Key: <uuid-v4>` bei `POST /events` & `/events:batch`.

**Limits**  
- **Einzelevent ≤ 16 KB**, **Batch ≤ 100 Events oder 64 KB** → sonst `413`.  
- **Rate-Limit pro Spieler-Token:** **10 req/s burst**, **60 req/min** sustained → sonst `429` + `Retry-After` (Client wiederholt später).

**Routen (MVP)**  
- `POST /v1/runs` *(admin)* → Run anlegen.  
- `POST /v1/runs/{run_id}/players` *(admin)* → Spieler anlegen + **Token generieren** (einmalige Anzeige).  
- `POST /v1/players/{player_id}/rotate-token` *(admin)* → Token-Rotation.  
- `POST /v1/events` → Einzel-Event (Antwort: `202 Accepted`).  
- `POST /v1/events:batch` → Batch-Ingestion (ebenfalls `202`).  
- `GET /v1/runs/{run_id}/routes/status` → Route-Matrix.  
- `GET /v1/runs/{run_id}/encounters` → Query (Filter).  
- `GET /v1/runs/{run_id}/blocklist` → globale Familien-Sperren.  
- `GET /v1/runs/{run_id}/links` → Soul-Link-Trios.

---

## 8) Idempotenz & Retries

**Muster:** Client sendet **`Idempotency-Key` (UUIDv4)** mit jedem POST. Server persistiert `(key, request_hash, response)` und liefert bei Retries **das gleiche Ergebnis** zurück. *(Bewährtes Stripe-Pattern; generische Best Practice.)*

**Server-Tabelle:** `idempotency_keys` (Key, Run, Player, Request-Hash, Response, CreatedAt).  
**TTL-Cleanup:** periodisch (z. B. 24–72 h).  
**429-Handling:** Client beachtet `Retry-After`.

---

## 9) Realtime (WebSocket)

- **Endpoint:** `GET /v1/ws?run_id=...` (Header `Authorization: Bearer <token>`).  
- **Events (Server → Client):** `encounter`, `catch_result`, `faint`, `admin_override`.  
- **Hinweis:** WebSocket-Routen erscheinen nicht in OpenAPI; optional später **AsyncAPI** für formale WS-Schemas. citeturn0search10

---

## 10) CORS

- Für lokale UI auf demselben Origin **nicht nötig**.  
- Wenn UI eine andere Origin (z. B. eigener Quick-Tunnel) nutzt: **FastAPI `CORSMiddleware`** mit `allow_origins=[…]` aktivieren.

---

## 11) Deployment (Windows) & Netzwerk

**Schnellstart ohne eigene Domain – Cloudflare *Quick Tunnel***  
1. `cloudflared.exe` installieren.  
2. Starten: `cloudflared tunnel --url http://127.0.0.1:9000`  
3. Du erhältst eine **zufällige `https://<random>.trycloudflare.com`-URL**, die Anfragen (inkl. **WebSockets**) an deinen lokalen FastAPI-Port proxyt. citeturn0search1turn0search11turn0search6

**FastAPI/Uvicorn Start:** `uvicorn app:app --host 127.0.0.1 --port 9000`  
**SQLite WAL:** beim DB-Init `PRAGMA journal_mode=WAL;` setzen. citeturn0search2

---

## 12) Emulator-Integration (EU-ROM)

- **DeSmuME (Windows):** Lua-Scripting aktivieren (`Tools → Lua Scripting`), RAM Watch/Search nutzen, um Adressen zu kalibrieren (Route-ID, Enemy Species/Level, Fishing-Flag/Rod-Kind).  
- **Fishing-Erkennung (MVP):** Heuristik „Angeln aktiv/Bite“-Flag vor Kampfstart + Wasser-Kachel; **Rod-Typ** aus Key-Item-State.  
- **Species/Level/HP** aus den bekannten Gen‑4 Pokémon‑Strukturen im RAM lesen (128‑Byte‑Blöcke im Kampf/Party-Kontext sind gängige Referenzen).

---

## 13) Sicherheit

- **Auth:** Bearer-Token pro Spieler (Erzeugung/Rotation über Admin-Endpoints).  
- **Transport:** Quick Tunnel liefert **HTTPS/WSS**. citeturn0search6  
- **Rate-Limiting:** `429` + `Retry-After` (Client Backoff).  
- **OWASP-Orientierung:** BOLA/BOPLA, Broken Auth, Ressourcenverbrauch beachten.

---

## 14) Telemetrie & Qualität

- **Metriken:**  
  - Encounter-Detektionsrate, Catch/Fail-Übereinstimmung, Faint-Propagation  
  - `dupes_skip`-Quote, Zeit bis **fe_finalized** pro Route  
  - RPS, Latenzen, 4xx/5xx-Raten, 429-Häufigkeit
- **Logs:** JSON-Logs mit Event-IDs, Idempotency-Keys.

---

## 15) Risiken & Mitigation

- **RAM-Offsets variieren (Region/Version):** Einmalige Kalibrierung (EU), Tabelle pro ROM-Build.  
- **Fishing-Heuristik** irrt selten: Admin-Override + zusätzl. Signale (Rod-Typ).  
- **Netzwerk/Watcher-Fehler:** Idempotenz + Retries, `429`-Behandlung mit `Retry-After`.  
- **SQLite-Locks:** WAL-Modus; ggf. später Upgrade auf Postgres.

---

## 16) Meilensteine

1) **POC (1–2 Tage)**  
   - Lua-Script loggt `encounter` (inkl. Fishing), `catch_result` (Party-Delta), `faint` (HP → 0).  
   - Watcher → `POST /v1/events`.  
   - FastAPI minimal, SQLite, WebSocket-Echo.

2) **MVP (≈ 1 Woche)**  
   - Regeln (Dupes, Familie, Soul-Link), Route-Matrix UI, Live-Feed.  
   - Admin-Endpoints (Runs/Players + Token).  
   - Cloudflared Quick Tunnel im Betrieb.

3) **Beta (1–2 Wochen)**  
   - Review/Override-UI, Batch-Ingestion, Idempotenz-TTL-Cleanup, Export/CSV.  
   - Optional: Headbutt/Rock Smash.

---

## 17) API – Kurzreferenz

- **SecuritySchemes:** HTTP Bearer.  
- **`POST /v1/events`** → `202`, `429` (mit `Retry-After`), `413`, `401/403`. Fehlerobjekt: **Problem Details** (RFC 9457). citeturn0search4  
- **`POST /v1/events:batch`** (≤ 100 oder 64 KB).  
- **`POST /v1/runs`**, **`POST /v1/runs/{run_id}/players`** (Antwort enthält **einmalig** `player_token`).  
- **`GET /v1/runs/{run_id}/routes/status`**, **`/encounters`**, **`/blocklist`**, **`/links`**.  
- **WebSocket:** `GET /v1/ws?run_id=...` (Bearer im Header). *(WS nicht Teil der OpenAPI; optional AsyncAPI.)* citeturn0search10

---

## 18) Setup-Notizen (Windows)

- **FastAPI/WebSockets:** Beispiele & Referenz in der offiziellen Doku. citeturn0search0turn0search5  
- **CORS:** nur nötig, wenn UI ≠ API-Origin; per Middleware konfigurierbar.  
- **Cloudflare Quick Tunnel:** `cloudflared tunnel --url http://127.0.0.1:9000` (liefert `*.trycloudflare.com`). citeturn0search1  
- **SQLite WAL:** Vorteile & Details in der offiziellen SQLite-Doku. citeturn0search2

---

## 19) Offene Punkte

- **Referenzdaten**: Species→Family und Route-IDs (EU) als CSV importieren.  
- **Lua-Offsets** (EU) final messen & hinterlegen.  
- **UI-Design (Minimal)**: Route-Matrix + Methode-Badge (Fishing), Blocklist-Viewer.  
- **Token-Speicher**: sichere Generierung (`secrets.token_urlsafe(32)`), Speicherung als Hash.
