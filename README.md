# ARK

Wrapper für die EditShare Ark API, Version 0.3. Jede Funktion erledigt genau eine Ark-Aufgabe. Was das Tool daraus macht (Eingangslisten, Reports, Soll/Ist-Vergleich, Konsole), entscheidet der Caller.

## Inhalt

1. [Installation](#installation)
2. [Verbinden](#verbinden)
3. [Rückgabe](#rückgabe)
4. [Restore](#restore)
5. [Datei- und Tape-Status](#datei--und-tape-status)
6. [Jobs](#jobs)
7. [Funktionsübersicht](#funktionsübersicht)
8. [Referenz](#referenz)

## Installation

```powershell
pip install "ArkAPI @ git+https://github.com/PROGRESS-MAM/ES-Ark-API.git@main"
```

Als Abhängigkeit in einem anderen Projekt:

```toml
dependencies = [
    "ArkAPI @ git+https://github.com/PROGRESS-MAM/ES-Ark-API.git@main",
]
```

Zum Entwickeln am Paket, im Wurzelverzeichnis des Repos:

```powershell
pip install -e .
```

[to Top](#inhalt)

## Verbinden

Über die TOOLBOX, mit `ARK_HOST`, `ARK_USER` und `ARK_PASSWORD` in der `cred.env`:

```python
from toolbox import tb_link_api

ark = tb_link_api(cred_path, "ark")
if ark is None:
    raise SystemExit("Keine Ark-Verbindung, cred.env prüfen")
```

Die TOOLBOX ruft dafür `ArkAPI.Ark.create_instance(user, password, host)` auf. Direkt aufrufen muss man das nur ohne TOOLBOX.

[to Top](#inhalt)

## Rückgabe

Jede Funktion gibt ein `ArkResult` zurück:

```python
result.code        # HTTP-Statuscode, 0 = keine Antwort vom Server
result.data        # Nutzdaten, bei Fehlern der Leerwert der Funktion
result.message     # Klartext
result.error       # maschinenlesbare Kennung, sonst ""
```

- Offizielle Endpunkte liefern die Codes der Spezifikation, siehe [Funktionsübersicht](#funktionsübersicht).
- Inoffizielle Endpunkte haben keine dokumentierten Codes: Erfolg ist `200 <= result.code < 300`.
- Bei Fehler 500 der WebUI (`error_class`, `error_msg`) steht in `error` der Klassenname, z. B. `InvalidArkJobError`, in `message` der Text.

Eigene Kennungen der API:

| `error` | Code | Bedeutung |
| --- | --- | --- |
| `HASHES_NOT_RESTORABLE` | 404 | `restore_files()`: keine Datei restaurierbar, oder mit `require_all=True` mindestens eine nicht, kein Job angelegt |
| `JOB_NOT_FOUND` | 404 | Session-ID weder aktiv noch abgeschlossen noch inaktiv |
| `WAIT_TIMEOUT` | 408 | `wait_for_job()`: Lauf nach `timeout` nicht abgeschlossen |
| `STOP_TIMEOUT` | 408 | `stop_job()`: Lauf nach `timeout` noch aktiv |

**Bestätigung:** Funktionen, die in Ark etwas anlegen, ändern oder löschen, brauchen `confirm=True`. Ohne geht keine Anfrage raus, es kommt ein `ValueError`.

**Fortschritt:** Wartende Funktionen melden sich alle `progress_seconds` über `on_progress`, eine Funktion mit einem Text-Argument. Standard ist `print`, `on_progress=None` macht sie stumm.

[to Top](#inhalt)

## Restore

### Session-IDs

`restore_files()` liefert unter `data["session_id"]` die lange Session-ID eines Laufs, z. B. `restorejob_jURjob-__restorejob__---2026-10-12-14-34-2-762674`. Alle Job-Funktionen erwarten diese lange ID. Der Teil vor `-__` (`restorejob_jURjob`) taucht in Benachrichtigungen auf.

### check_restore

Kann dieser Restore gemacht werden? Prüft logisch (Kopie in Ark) und physisch (Tapes im Autochanger).

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `hashes` | ja | ein FLOW-Hash oder eine Liste, Version 0, 1 oder 2 |

`data`:

```python
{
    "restorable": True,                 # alle Dateien jetzt restaurierbar
    "files": {
        "2:53b4...": {
            "in_ark": True,             # logisch: Ark hält mindestens eine Kopie
            "copies": [["LS1916L7"]],   # Barcodes je Kopie
            "tapes_offline": [],        # physisch: benötigte Tapes außerhalb des Autochangers
            "restorable": True,         # beides: eine Kopie mit allen Tapes im Autochanger
            "reason": "",               # sonst INVALID_HASH, NOT_IN_ARK oder TAPES_OFFLINE, siehe restore_files()
        },
    },
}
```

Hashes mit ungültigem Format werden vor der Anfrage aussortiert und mit `reason` `INVALID_HASH` gemeldet, die übrigen werden trotzdem geprüft. Codes: 200.

### restore_files

Dateien anhand ihrer Hashes in einen Media Space zurückspielen. Prüft vorab mit `check_restore()`.

- **Standard (best effort):** Nicht restaurierbare Dateien werden übersprungen, alle übrigen kommen in einen Job.
- **`require_all=True`:** Ist eine Datei nicht restaurierbar, wird kein Job angelegt.

In beiden Fällen steht in `data`, was warum nicht restauriert wurde.

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `hashes` | ja | – | Liste von FLOW-Hashes oder Dicts `{"flow_hash": ..., "restore_path": ...}` für eigene Pfade je Datei |
| `mediaspace` | ja | – | Name des Ziel-Media-Space |
| `restore_path` | nein | `"/"` | Ordner im Media Space, wird angelegt falls nicht vorhanden |
| `require_all` | nein | `False` | `True`: nur restaurieren, wenn alle Dateien restaurierbar sind |
| `space_uuid` | nein | – | UUID des Ziel-Media-Space |
| `ark_sources` | nein | – | `["tape"]` |
| `prefer_source` | nein | – | `"tape"` |
| `on_progress` | nein | `print` | Meldung, solange auf die Session-ID gewartet wird |
| `progress_seconds` | nein | `30` | Abstand der Meldungen |

`data`, auch bei 404:

```python
{
    "session_id": "restorejob_jURjob-__restorejob__---2026-10-12-14-34-2-762674",   # None ohne Job
    "restored": ["2:53b4...", "2:775d..."],     # Hashes im Job
    "skipped": {                                # Hashes ohne Restore, mit Grund
        "2:8a37...": {"reason": "TAPES_OFFLINE", "tapes_offline": ["LS2048L8"]},
        "2:28dc...": {"reason": "NOT_IN_ARK", "tapes_offline": []},
        "abc": {"reason": "INVALID_HASH", "tapes_offline": []},
    },
}
```

| `reason` | Bedeutung |
| --- | --- |
| `INVALID_HASH` | Hash hat kein gültiges Format |
| `NOT_IN_ARK` | logisch: Ark hält keine Kopie |
| `TAPES_OFFLINE` | physisch: keine Kopie, deren Tapes alle im Autochanger liegen |

Ark antwortet je nach Auslastung erst nach mehreren Minuten. Bis dahin ist der Caller blockiert und erhält Meldungen wie `Warte auf Session-ID seit 2:30 min`. Bricht der Caller in dieser Zeit ab (Strg+C), kann Ark den Restore trotzdem anlegen.

```python
result = ark.restore_files(hashes, "Transfer", restore_path="tmp Martin/")

for flow_hash, info in result.data.get("skipped", {}).items():
    print("übersprungen:", flow_hash, info["reason"], info["tapes_offline"])

if result.code == 200:
    session_id = result.data["session_id"]
elif result.error != "HASHES_NOT_RESTORABLE":
    raise RuntimeError(result.message)
```

Codes: 200 (Job angelegt, `skipped` kann Einträge haben), 400 `INVALID_DESTINATION`, `INVALID_SOURCE`, `MISSING_REQUIRED_FIELD`, 404 `HASHES_NOT_RESTORABLE`.

### restore_backups

Ein oder mehrere ganze Backups zurückspielen. **Ungetestet.**

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `backups` | ja | – | Liste von Backup-IDs oder Dicts `{"backup_id": ..., "rename": ..., "cumulative": True}` |
| `target` | ja | – | Restore-Ziel, bei Media Spaces `"<ESA-Gruppe>---<Member>---<Bit-Bucket-Pfad>"`, sonst die ESA-Gruppe |
| `space_type` | nein | `"ms"` | `"ms"`, `"ps"`, `"priv"`, `"fe"`, `"es"` oder `"flow"` |
| `storage_goals` | nein | – | Dict Backup-ID → EFS Storage Goal |
| `restore_date` | nein | – | Termin, Format `"10/21/2015"` |
| `restore_time` | nein | – | Uhrzeit, Format `"03:00am"` |
| `on_progress`, `progress_seconds` | nein | `print`, `30` | wie bei `restore_files()` |

Codes: 200 (`data` = Job-ID).

[to Top](#inhalt)

## Datei- und Tape-Status

### get_file_status

Logisch: Was weiß die Ark-Datenbank über diese Dateien?

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `hashes` | ja | ein FLOW-Hash oder eine Liste |

`data` je Hash: `in_ark` (mindestens eine Kopie), `copies` (Barcodes je Kopie), `matches` (Rohtreffer mit Space, Pfad, Backup-Job). Codes: 200, 400 `INVALID_HASH`.

### get_tape_location

Physisch: Wo sind diese Tapes?

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `barcodes` | ja | ein Barcode oder eine Liste |

`data` je Barcode: `known` (Ark kennt das Tape), `in_changer` (liegt im Autochanger), `slot` (Slot oder `None`). Codes wie `get_tape_library_status()`.

[to Top](#inhalt)

## Jobs

### find_job

Einen Lauf in der Queue finden.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `session_id` | ja | lange Session-ID |

`data`: `{"list": "active" | "completed" | "inactive", "entry": {...}}`. Codes: 200, 404 `JOB_NOT_FOUND`.

`entry` bei `active`: `current_status` (`"Enqueued: (0 of 5 files)"`, `"Running: (2 of 5 files)"`), `progress_txt`, `progress_num`, `current_name`, `current_speed`.

`entry` bei `completed`: `status`, `id`, `creation_time`, `has_filelist`, `name`. Bisher gesehene Werte für `status`: `Complete`, `Partially Complete`, `Cancelled`, `Error`, `Unknown`.

### wait_for_job

Warten, bis ein Lauf abgeschlossen ist.

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `session_id` | ja | – | lange Session-ID |
| `timeout` | nein | `None` | Sekunden, `None` wartet unbegrenzt |
| `poll_seconds` | nein | `10` | Abstand der Abfragen |
| `on_progress`, `progress_seconds` | nein | `print`, `30` | Meldung mit aktuellem Status und Fortschritt |

`data` ist das Ergebnis von `find_job()` für den abgeschlossenen Lauf. Codes: 200, 404 `JOB_NOT_FOUND`, 408 `WAIT_TIMEOUT`.

### stop_job

Einen Lauf stoppen und bestätigen, dass er nicht mehr aktiv ist. Getestet mit einem wartenden Lauf.

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `session_id` | ja | – | lange Session-ID |
| `timeout` | nein | `60` | Sekunden, `0` stoppt ohne zu warten |
| `on_progress`, `progress_seconds` | nein | `print`, `30` | wie bei `wait_for_job()` |

`data` ist das Ergebnis von `find_job()` für den gestoppten Lauf, `status` in der Regel `Cancelled`. Codes: 200, 404 `JOB_NOT_FOUND`, 408 `STOP_TIMEOUT`, sonst der Code von Ark.

### get_session_files

Dateiliste und Fehlertext eines Laufs, seitenweise.

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `session_id` | ja | – | lange Session-ID, die kurze liefert 500 |
| `page_num` | nein | `0` | Seite |

`data`: `{"files": [...], "explanation": "...", "num_pages": 0, "id": "..."}`. `explanation` enthält den Grund, z. B. „Ark was unable to process all of the actions requested by this job, because the job was cancelled before it had completed.“

```python
session_id = ark.restore_files(hashes, "Transfer").data["session_id"]
done = ark.wait_for_job(session_id)

if done.code == 200 and done.data["entry"]["status"] != "Complete":
    print(ark.get_session_files(session_id).data["explanation"])
```

[to Top](#inhalt)

## Funktionsübersicht

✅ geprüft · *ungetestet* = Docstring trägt den Hinweis „ungetestet“ · 🔒 braucht `confirm=True`

### Restore und Status

| Funktion | Endpunkt | Beschreibung | |
| --- | --- | --- | --- |
| `check_restore(hashes)` | – | Prüft, ob ein Restore logisch und physisch möglich ist. | ✅ |
| `restore_files(hashes, mediaspace, ...)` | POST /restore/hashes | Prüft vorab und spielt alle restaurierbaren Dateien zurück, optional nur alle oder keine; liefert Session-ID und übersprungene Dateien mit Grund. | ✅ |
| `restore_backups(backups, target, ...)` | POST /restore/restoreBackups | Spielt ein oder mehrere ganze Backups zurück. | *ungetestet* |
| `get_file_status(hashes)` | POST /filestatus/ | Liefert je Hash, ob und auf welchen Tapes Ark eine Kopie hat. | ✅ |
| `get_tape_location(barcodes)` | GET /api/tape/library/tapes | Liefert je Barcode, ob das Tape im Autochanger liegt. | ✅ |
| `get_file_hash_database_status()` | GET /filestatus/database | Zeigt den Stand des Hash-Imports in die Ark-Datenbank. | ✅ |
| `get_backups()` | GET /restore/backups | Listet alle Backups. | ✅ |
| `search_backups(pattern, mode="contains", *, limit=100, offset=0)` | POST /backup/search | Sucht in den Backups nach Name, Muster (`exact`, `contains`, `wildcard`) oder Hash (`flow_hash`); `limit=0` holt alle Seiten. | *ungetestet* |
| `get_restore_targets(data)` | POST /restore/restoreTargets | Listet mögliche Ziele für ausgewählte Backups. | *ungetestet* |
| `get_restore_names(data)` | POST /restore/getRestoreNames | Schlägt Namen für ausgewählte Backups vor. | *ungetestet* |
| `get_backup_contents(backup_id, page=None)` | GET /backup/contents/{id}[/{page}] | Liefert den Inhalt eines Backups. | *ungetestet* |

### Jobs

| Funktion | Endpunkt | Beschreibung | |
| --- | --- | --- | --- |
| `get_jobs_queue()` | GET /job/queue | Liefert aktive, abgeschlossene und inaktive Jobs in einer Antwort. | ✅ |
| `get_jobs_active()` | GET /job/active | Listet laufende und wartende Läufe mit Fortschritt. | ✅ |
| `get_jobs_completed()` | GET /job/completed | Listet abgeschlossene Jobs, ihre Läufe unter `sessions`. | ✅ |
| `get_jobs_inactive()` | GET /job/inactive | Listet geplante Backup-Jobs mit nächstem Termin. | ✅ |
| `find_job(session_id)` | GET /job/queue | Findet einen Lauf und liefert Liste und Eintrag. | ✅ |
| `wait_for_job(session_id, ...)` | GET /job/queue | Wartet, bis ein Lauf abgeschlossen ist. | ✅ |
| `stop_job(session_id, ...)` | POST /job/stop/{id} | Stoppt einen Lauf und bestätigt den Endzustand. | ✅ |
| `get_session_files(session_id, page_num=0)` | POST /backup/sessionFiles | Liefert Dateiliste und Fehlertext eines Laufs. | ✅ |
| `get_job(job_id)` | GET /job/{id} | Liefert eine Job-Definition, vermutlich mit Zeitplan. | *ungetestet* |
| `get_job_actions(job_id)` | GET /job/actions/{id} | Liefert die Aktionen einer Job-Definition. | *ungetestet* |
| `get_job_details(session_id, job_list="completed_jobs")` | GET /job/details/{list}/{id} | Liefert die Details eines Laufs. | *ungetestet* |
| `create_job(data, *, confirm=False)` | PUT /job | Legt einen Job an. | *ungetestet* 🔒 |
| `modify_job(job_id, data, *, confirm=False)` | PUT /job/modify/{id} | Ändert einen Job. | *ungetestet* 🔒 |
| `delete_job(job_id, *, confirm=False)` | DELETE /job/{id} | Löscht einen Job. | *ungetestet* 🔒 |
| `run_job(job_id)` | POST /job/run/{id} | Startet einen Job. | *ungetestet* |
| `wait_for_events(last_event=0)` | GET /events/{last} | Wartet auf neue Ereignisse seit einer Ereignisnummer. | *ungetestet* |

### Pools und Tapes

| Funktion | Endpunkt | Beschreibung | |
| --- | --- | --- | --- |
| `get_pools()` | GET /tape/pools | Listet alle Tape-Pools mit ihren Tapes. | ✅ |
| `get_pools_targets()` | GET /destinations | Listet die Pools, die als Backup-Ziel nutzbar sind. | ✅ |
| `get_pool(pool_id)` | GET /tape/pool/{id} | Liefert einen Tape-Pool. Codes: 200, 404 `POOL_NOT_FOUND`. | *ungetestet* |
| `create_pool(name, server, *, confirm=False)` | PUT /tape/pool | Legt einen leeren Tape-Pool an. Codes: 200, 400 `POOL_EXISTS`. | *ungetestet* 🔒 |
| `rename_pool(pool_id, name, *, confirm=False)` | PATCH /tape/pool/{id} | Benennt einen Tape-Pool um, **erst ab Ark 2026.3**. Codes: 200, 400 `POOL_EXISTS`, 404 `POOL_NOT_FOUND`. | *ungetestet* 🔒 |
| `delete_pool(pool_id, *, confirm=False)` | DELETE /tape/pool/{id} | Löscht einen Tape-Pool. Codes: 200, 404 `POOL_NOT_FOUND`. | *ungetestet* 🔒 |
| `get_pool_tapes(pool_id)` | GET /tape/pool/{pool}/tapes | Listet die Tapes eines Pools. | *ungetestet* |
| `set_pool_tapes(pool_id, data, *, confirm=False)` | PUT /tape/pool/{pool}/tapes | Legt fest, welche Tapes zu einem Pool gehören. | *ungetestet* 🔒 |
| `get_pool_tapes_assigned(pool_id)` | GET /tape/getAssignedTapes/{pool} | Listet die einem Pool zugewiesenen Tapes. | *ungetestet* |
| `get_pool_tapes_unassigned(pool_id)` | GET /tape/getUnassignedTapes/{pool} | Listet die freien Tapes für einen Pool. | *ungetestet* |
| `get_pool_contents(pool_id, page_num)` | POST /tape/getPoolContents | Liefert den Inhalt eines Pools, seitenweise. | *ungetestet* |
| `get_tape_library_status()` | GET /api/tape/library/tapes | Liefert das Tape-Inventar inklusive `in_changer` und `slot`. | ✅ |
| `get_tape_servers()` | GET /tape/servers | Listet die Tape-Server mit Adresse. | ✅ |
| `get_tape_server_list()` | GET /tape/getTapeServers | Listet die Tape-Server für die Auswahlliste. | ✅ |
| `get_tape_backups()` | GET /tape/getTapeBackups | Listet die Tape-Backups nach Pool und Space. | ✅ |
| `get_tape_license()` | GET /tape/license | Zeigt die Ark-Tape-Lizenzen. | ✅ |
| `get_tape_jobs(server_id, *, offset=0, limit=100, ascending=False)` | GET /tape/jobs/{server} | Listet die Jobs eines Tape-Servers, seitenweise. | *ungetestet* |
| `get_tape_job_log(server_id, job_id)` | GET /tape/log/{server}/{job} | Liefert das Log eines Tape-Jobs. | *ungetestet* |
| `get_tape_alerts(server_id=None)` | GET /tape/alerts[/{server}] | Listet Tape-Alarme mit Tape, Laufwerk und Tape-Job. | ✅ |
| `acknowledge_tape_alert(server_id, alert_id, *, confirm=False)` | PUT /tape/alerts/acknowledge/{server}/{id} | Bestätigt einen Tape-Alarm. | *ungetestet* 🔒 |
| `scan_tapes()` | POST /tape/scanTapes | Liest die Tapes in der Library neu ein. | *ungetestet* |

### Quellen und System

| Funktion | Endpunkt | Beschreibung | |
| --- | --- | --- | --- |
| `get_mediaspaces()` | GET /sources/mediaSpaces | Listet die Media Spaces. | ✅ |
| `get_mediaspaces_types()` | GET /sources/mediaSpaceTypes | Listet die Media-Space-Typen. | ✅ |
| `get_mediaspaces_project()` | GET /sources/projectSpaces | Listet die Project Spaces. | ✅ |
| `get_mediaspaces_private()` | GET /sources/privateSpaces | Listet die Private Spaces. | ✅ |
| `get_mediaspaces_exchange()` | GET /sources/exchangeSpaces | Listet die Exchange Spaces. | ✅ |
| `get_sources_flow()` | GET /sources/flow | Listet die FLOW-Quellen (Proxies, Datenbank). | ✅ |
| `get_sources_tape_db()` | GET /sources/arkTapeDB | Liefert die Ark-Tape-Datenbank als Quelle. | ✅ |
| `get_notifications()` | GET /notifications | Liefert die letzten Benachrichtigungen, etwa 290 Einträge. | ✅ |
| `get_license_status()` | GET /license/status | Zeigt den Lizenzstatus. | ✅ |

Argumente mit `data` werden unverändert gesendet, `dict` und `list` als JSON, Aufbau wie in der WebUI.

[to Top](#inhalt)

## Referenz

[EditShare Ark API](https://developers.editshare.com/?urls.primaryName=EditShare%20Ark)

[to Top](#inhalt)
