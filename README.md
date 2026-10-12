# ARK

Wrapper für die EditShare Ark API.

## Installation

Als Abhängigkeit direkt aus GitHub:

```powershell
pip install "ArkAPI @ git+https://github.com/PROGRESS-MAM/ES-Ark-API.git@main"
```

In einem anderen Projekt als Abhängigkeit eintragen:

```toml
dependencies = [
    "ArkAPI @ git+https://github.com/PROGRESS-MAM/ES-Ark-API.git@main",
]
```

Zum Entwickeln am Paket selbst, aus dem Wurzelverzeichnis des Repos:

```powershell
pip install -e .
```

## Inhalt

**1. [Installation](#installation)**

**2. [Verbinden](#verbinden)**

**3. [Komfort-Funktionen](#komfort-funktionen)**

| | | |
| --- | --- | --- |
| [restore_backup](#restore_backup) | [restore_files_by_hash](#restore_files_by_hash) | [search_by_flow_hash](#search_by_flow_hash) |
| [search_all_backups](#search_all_backups) | [get_tapes](#get_tapes) | [find_tape](#find_tape) |
| [find_backup](#find_backup) | [find_backups_by_space_name](#find_backups_by_space_name) | [find_backups_by_space_uuid](#find_backups_by_space_uuid) |
| [tapes_from_file_status](#tapes_from_file_status) | [check_hashes_restorable](#check_hashes_restorable) |  |

**4. [API-Wrapper-Funktionen](#api-wrapper-funktionen)**

| | | |
| --- | --- | --- |
| [get_backups](#get_backups) | [restore_backups](#restore_backups) | [restore_hashes](#restore_hashes) |
| [get_file_hash_database_status](#get_file_hash_database_status) | [get_file_status](#get_file_status) | [has_file_status](#has_file_status) |
| [get_file_statuses](#get_file_statuses) | [get_disk_search_status](#get_disk_search_status) | [search_backups](#search_backups) |
| [get_tape_library_status](#get_tape_library_status) | [get_tape_pools](#get_tape_pools) | [get_tape_pool](#get_tape_pool) |
| [create_tape_pool](#create_tape_pool) | [rename_tape_pool](#rename_tape_pool) | [delete_tape_pool](#delete_tape_pool) |

**5. [Rückgabe-Prinzip](#rückgabe-prinzip)**

**6. [Referenz](#referenz)**

**7. [Inoffizielle Endpunkte](#inoffizielle-endpunkte)**

| | | |
| --- | --- | --- |
| [get_restore_job_status](#get_restore_job_status) | [get_restore_job_errors](#get_restore_job_errors) | [stop_restore_job](#stop_restore_job) |
| [System](#system) | [Jobs](#jobs) | [Restore und Backup](#restore-und-backup) |
| [Tape](#tape) | [Quellen](#quellen) | [Download](#download) |
| [Testskript](#testskript) |  |  |

## Verbinden

```python
import ArkAPI

ark = ArkAPI.Ark.create_instance(
    os.environ.get("FLOW_USER"), os.environ.get("FLOW_PASSWORD"), os.environ.get("FLOW_HOST"),
)
```

[to Top](#inhalt)

## Komfort-Funktionen

Setzen auf den [API-Wrapper-Funktionen](#api-wrapper-funktionen) auf. Das Muster hinter den `if`/`elif`-Ketten steht unter [Rückgabe-Prinzip](#rückgabe-prinzip).

[to Top](#inhalt)

### restore_backup

Ein einzelnes Backup zurückspielen, baut den Body für [restore_backups](#restore_backups).

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `backup_id` | ja | – | ID aus `get_backups()` |
| `target` | ja | – | Restore-Ziel, siehe unten |
| `space_type` | nein | `"ms"` | `"ms"`, `"ps"`, `"priv"`, `"fe"`, `"es"` oder `"flow"` |
| `rename` | nein | – | neuer Name für den restaurierten Space |
| `cumulative` | nein | `False` | ganze Incremental-Kette bis `backup_id`, nur Ark Tape |
| `storage_goal` | nein | – | EFS Storage Goal für restaurierte Media Spaces |
| `restore_date` | nein | – | Termin, Format `"10/21/2015"` |
| `restore_time` | nein | – | Uhrzeit, Format `"03:00am"` |

Alle außer `backup_id` und `target` sind keyword-only.

```python
result = ark.restore_backup(
    "ark.tapeserver_f541...",
    "esa_IBN1e---es-master---/efs/efs_1",
    rename="Projekt_2026_restored",
)

if result.code == 200:
    # restorejob_sovh0C
    print("Job:", result.data)                  
else:
    raise RuntimeError(result.message)
```

`target` besteht bei Media Spaces aus drei durch je drei Bindestriche getrennten Teilen: ESA-Gruppe, Server-Group-Member und Pfad zum Bit Bucket. Bei allen anderen Space-Typen genügt die ESA-Gruppe, z. B. `esa_HiNbl`.

[to Top](#inhalt)

### restore_files_by_hash

Eine Liste von FLOW-Hashes in einen Media Space zurückspielen, baut den Body für [restore_hashes](#restore_hashes).

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `hashes` | ja | – | Liste von Hashes, alternativ Liste von Dicts wie `restore_hashes()` sie erwartet |
| `mediaspace` | ja | – | Name des Ziel-Media-Space |
| `restore_path` | nein | `"/"` | Pfad im Media Space, wird angelegt falls nicht vorhanden |
| `space_uuid` | nein | – | UUID des Ziel-Media-Space |
| `ark_sources` | nein | beide | Quellen für die Suche, z. B. `["disk", "tape"]` |
| `prefer_source` | nein | – | bevorzugte Quelle wenn die Datei in beiden liegt |

Alle außer `hashes` und `mediaspace` sind keyword-only.

```python
result = ark.restore_files_by_hash(
    ["2:d41d8cd98f00b204e9800998ecf8427e"],
    "MyMediaSpace",
    restore_path="restored/",
    prefer_source="disk",
)

if result.code == 200:
    session_guid = result.data["session_guid"]
elif result.code == 404:
    # HASHES_NOT_RESTORABLE, message listet die Hashes als JSON
    logging.error("nicht restaurierbar: %s", result.message)
elif result.code == 400:
    # INVALID_HASH,
    # INVALID_DESTINATION,
    # INVALID_SOURCE,
    # MISSING_REQUIRED_FIELD
    print(result.error, result.message)
else:
    raise RuntimeError(result.message)
```

[to Top](#inhalt)

### search_by_flow_hash

Den Backup-Index nach einem FLOW-Hash durchsuchen, ruft [search_backups](#search_backups) im Modus `flow_hash` auf.

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `flow_hash` | ja | – | Hash der **Version 2**, also `2:<md5>` |
| `backup_type` | nein | beide | `"disk"` oder `"tape"` |
| `limit` | nein | `100` | maximale Trefferzahl |

```python
result = ark.search_by_flow_hash("2:d41d8cd98f00b204e9800998ecf8427e")

if result.code == 200:
    for hit in result.data["results"]:
        print(hit["filename"])
elif result.code == 400:
    # INVALID_HASH
    print(result.error, result.message)         
else:
    raise RuntimeError(result.message)
```

Andere Hash-Versionen unterstützt dieser Suchmodus nicht, sie werden als Warnung geloggt.

[to Top](#inhalt)

### search_all_backups

Alle Treffer einer Suche seitenweise holen, ruft [search_backups](#search_backups) auf, bis `total_matches` erreicht ist.

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `search_pattern` | ja | – | Dateiname oder Muster |
| `search_mode` | nein | `"contains"` | `"exact"`, `"contains"`, `"wildcard"` oder `"flow_hash"` |
| `backup_type` | nein | beide | `"disk"` oder `"tape"` |
| `page_size` | nein | `1000` | Treffer pro Request, 1 bis 10000 |
| `max_results` | nein | `0` | Abbruch nach dieser Trefferzahl, `0` holt alles |

```python
result = ark.search_all_backups("Interview", "contains")

if result.code == 200:
    print(len(result.data), "Treffer gesammelt")
elif result.code == 400:
    # abgebrochen, data enthaelt die bis dahin gesammelten Treffer
    print(result.error, result.message, len(result.data))
else:
    raise RuntimeError(result.message)
```

`data` ist die flache Liste aller Treffer, kein Seitenobjekt. Bricht eine Seite mit einem anderen Code als 200 ab, kommt deren Ergebnis zurück.

[to Top](#inhalt)

### get_tapes

Alle bekannten Tapes holen, ruft [get_tape_library_status](#get_tape_library_status) auf und gibt nur die Tape-Liste als `data` zurück.

Keine Argumente.

```python
result = ark.get_tapes()

if result.code == 200:
    for tape in result.data:
        print(tape["barcode"], tape["in_changer"])
else:
    raise RuntimeError(result.message)
```

Enthält alle Tape-Volumes, nicht nur die aktuell geladenen.

[to Top](#inhalt)

### find_tape

Ein Tape-Volume über seinen Barcode finden, filtert [get_tapes](#get_tapes).

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `barcode` | ja | Barcode des Tapes, z. B. `"001234L5"` |

```python
result = ark.find_tape("001234L5")

if result.code == 200 and result.data:
    print(result.data["slot"], result.data["storage_name"])
elif result.code == 200:
    print("Barcode unbekannt")
else:
    raise RuntimeError(result.message)
```

`data` ist der passende Eintrag oder `{}`. Ein leeres `data` bei Code 200 heißt: nicht gefunden.

[to Top](#inhalt)

### find_backup

Ein einzelnes Backup über seine ID finden, filtert [get_backups](#get_backups).

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `backup_id` | ja | die Backup-ID |

```python
result = ark.find_backup("ark.tapeserver_f541...")

if result.code == 200 and result.data:
    print(result.data["media_space_name"], result.data["date"])
elif result.code == 200:
    print("Backup-ID unbekannt")
else:
    raise RuntimeError(result.message)
```

[to Top](#inhalt)

### find_backups_by_space_name

Alle Backups eines Media Space über den Namen finden, filtert [get_backups](#get_backups).

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `space_name` | ja | Name des Media Space |

```python
result = ark.find_backups_by_space_name("Projekt_2026")

if result.code == 200 and result.data:
    job = ark.restore_backup(
        result.data[0]["backup_id"],
        "esa_IBN1e---es-master---/efs/efs_1",
    )
elif result.code == 200:
    print("kein Backup zu diesem Space")
else:
    raise RuntimeError(result.message)
```

`data` ist die Liste der passenden Backups, leer wenn keins passt.

[to Top](#inhalt)

### find_backups_by_space_uuid

Alle Backups eines Media Space über UUID finden, filtert [get_backups](#get_backups).

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `space_uuid` | ja | UUID des Media Space |

```python
result = ark.find_backups_by_space_uuid("6f3c1a...")

if result.code == 200:
    print(len(result.data), "Backups")
else:
    raise RuntimeError(result.message)
```

[to Top](#inhalt)

### tapes_from_file_status

Barcodes der Tapes aus einem `filestatus`-Eintrag sammeln. Reine Auswertung, kein Request.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `file_status` | ja | ein Eintrag aus der `data` von `get_file_status()` oder `get_file_statuses()` |

```python
for match in ark.get_file_status(flow_hash).data:
    # ["001234L5"]
    print(ArkAPI.Ark.tapes_from_file_status(match))     
```

Gibt eine `list` zurück, leer bei Disk-Backups.

[to Top](#inhalt)

### check_hashes_restorable

Vor einem Hash-Restore prüfen, welche Hashes restaurierbar sind, ruft [get_file_statuses](#get_file_statuses) und bei Tape-Kopien [get_tapes](#get_tapes) auf.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `hashes` | ja | Liste von FLOW-Hashes, Version 0, 1 oder 2 |

```python
result = ark.check_hashes_restorable(hashes)

if result.code == 200:
    blocked = [h for h, info in result.data.items() if not info["restorable"]]
    if blocked:
        print("nicht restaurierbar:", blocked)
    else:
        job = ark.restore_files_by_hash(hashes, "MyMediaSpace")
elif result.code == 400:
    # INVALID_HASH
    print(result.error, result.message)
else:
    raise RuntimeError(result.message)
```

`data` ist ein `dict` je angefragtem Hash:

| Schlüssel | Bedeutung |
| --- | --- |
| `in_ark` | Ark hält mindestens eine Kopie |
| `tapes` | Barcodes aller Kopien |
| `offline_tapes` | davon nicht in der Library |
| `restorable` | mindestens eine Kopie ohne Tape oder mit allen Tapes in der Library |

Bei einem Fehler kommt das Ergebnis des gescheiterten Requests mit leerem `data` zurück.

[to Top](#inhalt)

---

## API-Wrapper-Funktionen

Die fünfzehn Operationen der API, je eine Methode pro Endpunkt. Die `if`/`elif`-Ketten führen genau die Codes auf, die die Spezifikation für diesen Endpunkt dokumentiert. Jeder andere Code landet im `else`.

[to Top](#inhalt)

### get_backups

`GET /restore/backups` — alle in Ark gespeicherten Backups.

Keine Argumente.

```python
result = ark.get_backups()

if result.code == 200:
    for backup in result.data:
        print(backup["backup_id"], backup["media_space_name"], backup["date"])
else:
    raise RuntimeError(result.message)
```

`data` ist die Liste der Backups auf Ark Disk und Ark Tape, bei keinen Backups leer. Jeder Eintrag enthält unter anderem `backup_id`, `backup_type`, `date`, `media_space_name`, `media_space_uuid` und `destination_name`.

[to Top](#inhalt)

### restore_backups

`POST /restore/restoreBackups` — Backups auf ein Storage-Ziel zurückspielen.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `data` | ja | Restore-Kommando. Pflichtfelder `backups` und `target_data`, optional `storage_goals` und `restoreTime` |

```python
result = ark.restore_backups({
    "backups": [{"backup_id": "ark.tapeserver_f541..."}],
    "target_data": {"ms_target": "esa_IBN1e---es-master---/efs/efs_1"},
})

if result.code == 200:
    # restorejob_sovh0C
    print("Job:", result.data)
else:
    raise RuntimeError(result.message)
```

Der Service antwortet mit einem reinen JSON-String, nicht mit einem Objekt. `data` ist deshalb ein `str`. Bequemer geht es mit [restore_backup](#restore_backup).

[to Top](#inhalt)

### restore_hashes

`POST /restore/hashes` — einzelne Dateien anhand ihrer FLOW-Hashes zurückspielen.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `data` | ja | Restore-Kommando. Pflichtfelder `files` und `destination`, optional `source` |

```python
result = ark.restore_hashes({
    "files": [{
        "flow_hash": "2:d41d8cd98f00b204e9800998ecf8427e",
        "restore_path": "restored_files/",
    }],
    "destination": {"mediaspace": "MyMediaSpace"},
})

if result.code == 200:
    session_guid = result.data["session_guid"]
elif result.code == 404:
    # HASHES_NOT_RESTORABLE: kein Backup vorhanden oder Tape offline
    logging.error("nicht restaurierbar: %s", result.message)
elif result.code == 400:
    # INVALID_HASH,
    # INVALID_DESTINATION,
    # INVALID_SOURCE,
    # MISSING_REQUIRED_FIELD
    print(result.error, result.message)
else:
    raise RuntimeError(result.message)
```

Es gilt alles oder nichts: ein einziger nicht restaurierbarer Hash lässt den ganzen Auftrag scheitern. Bei 400 und 404 ist `data` ein leeres `dict`. Bequemer geht es mit [restore_files_by_hash](#restore_files_by_hash).

[to Top](#inhalt)

### get_file_hash_database_status

`GET /filestatus/database` — Status des Hash-Imports in die Ark-Datenbank.

Keine Argumente.

```python
result = ark.get_file_hash_database_status()

if result.code == 200:
    # importing, complete oder error
    print(result.data["status"])           
    print(result.data["progress_complete"],
          "von", result.data["progress_estimated"])
else:
    raise RuntimeError(result.message)
```

[to Top](#inhalt)

### get_file_status

`GET /filestatus/{FileHash}` — Ark Backup-Status einer Datei.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `flow_hash` | ja | FLOW-Hash, Version 0 (`<md5>`), 1 (`1:<md5>`) oder 2 (`2:<md5>`). Erzeugen mit dem CLI-Kommando `flow-hash` |

```python
result = ark.get_file_status("2:d41d8cd98f00b204e9800998ecf8427e")

if result.code == 200:
    for match in result.data:
        print(match["storage_type"], match["pathname"], match["filename"])
        print(ArkAPI.Ark.tapes_from_file_status(match))
elif result.code == 404:
    # HASH_NOT_FOUND
    print("keine Kopie in Ark")                 
elif result.code == 400:
    # INVALID_HASH
    print(result.error, result.message)         
else:
    raise RuntimeError(result.message)
```

404 ist eine Fachauskunft, kein Transportfehler. Wer daran eine Löschentscheidung hängt, muss 400 und 404 unterscheiden — beide liefern eine leere `data`.

[to Top](#inhalt)

### has_file_status

`HEAD /filestatus/{FileHash}` — nur prüfen, ob Ark eine Kopie hat. Die günstige Variante von [get_file_status](#get_file_status): kein Body, nur der Statuscode. Für Schleifen über viele Dateien deutlich sparsamer.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `flow_hash` | ja | FLOW-Hash, Version 0, 1 oder 2 |

```python
result = ark.has_file_status("2:d41d8cd98f00b204e9800998ecf8427e")

if result.code == 204:
    # Ark hat eine Kopie
    print("Kopie in Ark vorhanden")                         
elif result.code == 404:
    print("keine Kopie in Ark")
elif result.code == 400:
    print("Hash ungueltig:", result.message)
else:
    # nicht loeschen, Antwort unklar
    raise RuntimeError(result.message)          
```

Diese Operation liefert **kein 200** — ein Vergleich auf 200 geht hier immer schief. Keiner der drei Codes hat einen Body, `data` ist immer `None` und `error` immer `""`. Die Auskunft steckt allein im Code.

[to Top](#inhalt)

### get_file_statuses

`POST /filestatus/` — Massenabfrage für viele Hashes.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `hash_list` | ja | Liste von FLOW-Hashes, Version 0, 1 oder 2 |

```python
angefragt = ["2:d41d8cd9...", "2:1b54a3f2..."]
result = ark.get_file_statuses(angefragt)

if result.code == 200:
    gefunden = {match["hash"] for match in result.data}
    fehlt = [h for h in angefragt if h not in gefunden]
elif result.code == 400:
    # INVALID_HASH, mindestens einer
    print(result.error, result.message)
else:
    raise RuntimeError(result.message)
```

Diese Operation kennt **kein 404**. Hashes ohne Kopie fehlen einfach im Ergebnis, ein Abgleich mit `hash_list` zeigt also, welche Dateien nicht in Ark liegen.

[to Top](#inhalt)

### get_disk_search_status

`GET /backup/disk/search/status` — Indexierungsstatus der Disk-Backups.

Keine Argumente.

```python
result = ark.get_disk_search_status()

if result.code == 200:
    print(result.data["indexed"], "von", result.data["total"], "indexiert")
else:
    raise RuntimeError(result.message)
```

`data` enthält `total`, `indexed`, `indexing`, `not_indexed`, `needs_indexing` und `total_files`. Nur indexierte Disk-Backups sind über [search_backups](#search_backups) auffindbar, daher vor einer Suche prüfen.

[to Top](#inhalt)

### search_backups

`POST /backup/search` — Dateien in den indexierten Backups suchen.

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `search_pattern` | ja | – | Dateiname oder Muster. Bei `search_mode="flow_hash"` ein Hash der Version 2 |
| `search_mode` | nein | `"contains"` | `"exact"`, `"contains"`, `"wildcard"` oder `"flow_hash"` |
| `backup_type` | nein | beide | `"disk"` oder `"tape"` |
| `limit` | nein | `100` | maximale Trefferzahl, 1 bis 10000 |
| `offset` | nein | `0` | Anzahl zu überspringender Treffer |

`backup_type`, `limit` und `offset` sind keyword-only.

```python
result = ark.search_backups("*.mov", "wildcard", backup_type="disk", limit=500)

if result.code == 200:
    print(result.data["total_matches"], "Treffer")
    for hit in result.data["results"]:
        print(hit["filename"])
elif result.code == 400:
    # nur bei search_mode="flow_hash" mit ungueltigem Hash
    # INVALID_HASH
    print(result.error, result.message)        
else:
    raise RuntimeError(result.message)
```

`data` enthält bei 200 `total_matches`, `limit`, `offset` und `results`, sonst ein leeres `dict`. Für alle Seiten auf einmal siehe [search_all_backups](#search_all_backups).

[to Top](#inhalt)

### get_tape_library_status

`GET /api/tape/library/tapes` — Status der Tape Library inklusive Inventar.

Keine Argumente.

```python
result = ark.get_tape_library_status()

if result.code == 200:
    print(result.data["timestamp"], len(result.data["tapes"]), "Tapes")
else:
    raise RuntimeError(result.message)
```

`data` enthält `tapes` und `timestamp`. Pro Tape sind laut Spezifikation nur `barcode` und `in_changer` Pflicht; dazu kommen `slot`, `storage_name`, `lto_generation` und `server_id`. `slot` darf `null` sein, wenn das Band nicht im Wechsler steckt. Am laufenden System liefert der Endpunkt mehr Felder als die Spezifikation deklariert — `_request()` reicht den geparsten Body unverändert durch, es geht also nichts verloren. Wer nur die Liste braucht, nimmt [get_tapes](#get_tapes).

Die Spezifikation 2026.3.0 führt den Pfad als `/tape/library/tapes`; ArkAPI nutzt wie die WebUI `/api/tape/library/tapes`.

[to Top](#inhalt)

### get_tape_pools

`GET /tape/pools` — alle Tape-Pools aller Ark-Tape-Server.

Keine Argumente.

```python
result = ark.get_tape_pools()

if result.code == 200:
    for server_id, pools in result.data.items():
        for pool_id, pool in pools.items():
            print(server_id, pool_id, pool["name"], pool["tapes"])
else:
    raise RuntimeError(result.message)
```

`data` ist ein `dict` je `server_id`, darin je `pool_id` ein `dict` mit `name` und `tapes` (Barcodes).

[to Top](#inhalt)

### get_tape_pool

`GET /tape/pool/{pool_id}` — einen Tape-Pool über seine ID holen.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `pool_id` | ja | ID des Pools, z. B. `"poolid-1-1700000000"` |

```python
result = ark.get_tape_pool("poolid-1-1700000000")

if result.code == 200:
    print(result.data["pool_name"])
elif result.code == 404:
    # POOL_NOT_FOUND
    print("Pool unbekannt")
else:
    raise RuntimeError(result.message)
```

[to Top](#inhalt)

### create_tape_pool

`PUT /tape/pool` — einen leeren Tape-Pool anlegen.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `name` | ja | Name des Pools, eindeutig über alle Tape-Ziele |
| `server` | ja | ID des Ark-Tape-Servers |

```python
result = ark.create_tape_pool("Offsite Archive", "ark.tapeserver_d8ce43f0-...")

if result.code == 200:
    # poolid-1-1700000000
    print("Pool:", result.data)
elif result.code == 400:
    # POOL_EXISTS
    print(result.error, result.message)
else:
    raise RuntimeError(result.message)
```

`data` ist die ID des neuen Pools als `str`.

[to Top](#inhalt)

### rename_tape_pool

`PATCH /tape/pool/{pool_id}` — einen Tape-Pool umbenennen.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `pool_id` | ja | ID des Pools |
| `name` | ja | neuer Name, eindeutig über alle Tape-Ziele |

```python
result = ark.rename_tape_pool("poolid-1-1700000000", "Renamed Archive")

if result.code == 200:
    print("umbenannt")
elif result.code == 400:
    # POOL_EXISTS
    print(result.error, result.message)
elif result.code == 404:
    # POOL_NOT_FOUND
    print("Pool unbekannt")
else:
    raise RuntimeError(result.message)
```

`data` ist immer `None`.

[to Top](#inhalt)

### delete_tape_pool

`DELETE /tape/pool/{pool_id}` — einen Tape-Pool löschen.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `pool_id` | ja | ID des Pools |

```python
result = ark.delete_tape_pool("poolid-1-1700000000")

if result.code == 200:
    print("gelöscht")
elif result.code == 404:
    # POOL_NOT_FOUND
    print("Pool unbekannt")
else:
    raise RuntimeError(result.message)
```

`data` ist immer `None`.

[to Top](#inhalt)

---

## Rückgabe-Prinzip

Jede Methode gibt ein `ArkResult` mit vier Attributen zurück. Der Statuscode wird unverändert durchgereicht, ausgewertet wird im Caller.

```python
result = ark.get_file_status("2:d41d8cd98f00b204e9800998ecf8427e")

result.code        # 200, 400 oder 404
result.data        # Nutzdaten, bei Fehlern der Leerwert der Methode
result.message     # Klartext: details der API, sonst Text aus der Spezifikation
result.error       # maschinenlesbar, z. B. "INVALID_HASH", sonst ""

print(result)      # "200 A list of statuses for files managed by Ark"
```

[to Top](#inhalt)

### Fehlerkennungen

`result.error` ist die maschinenlesbare Kennung aus dem Fehlerobjekt der API:

```python
if result.code == 400:
    if result.error == "INVALID_HASH":
        ...             # Hash in der CSV korrigieren
    elif result.error == "INVALID_DESTINATION":
        ...             # Restore-Ziel falsch konfiguriert
```

Was welcher Endpunkt liefert:

| Funktion | Code | Error |
| --- | --- | --- |
| `alle` | 0 | `keine Antwort oder kein gültiges JSON - Klartextmeldung im message` |
| `restore_hashes()` | 400 | `INVALID_HASH`, `INVALID_DESTINATION`, `INVALID_SOURCE`, `MISSING_REQUIRED_FIELD` |
| `restore_hashes()` | 404 | `HASHES_NOT_RESTORABLE` |
| `get_file_status()` | 400 | `INVALID_HASH` |
| `get_file_status()` | 404 | `HASH_NOT_FOUND` |
| `get_file_statuses()` | 400 | `INVALID_HASH` |
| `search_backups()` | 400 | `INVALID_HASH` |
| `has_file_status()` | 400, 404 | — kein Body, `error` ist immer `""` |
| `get_tape_pool()`, `delete_tape_pool()` | 404 | `POOL_NOT_FOUND` |
| `create_tape_pool()` | 400 | `POOL_EXISTS` |
| `rename_tape_pool()` | 400 | `POOL_EXISTS` |
| `rename_tape_pool()` | 404 | `POOL_NOT_FOUND` |

Die Komfort-Funktionen erben die Werte der Funktion, die sie aufrufen.

[to Top](#inhalt)

## Referenz

[EditShare Ark API](https://developers.editshare.com/?urls.primaryName=EditShare%20Ark)

[to Top](#inhalt)

## Inoffizielle Endpunkte

Endpunkte aus der Ark WebUI, nicht in der Spezifikation (inofficial). Für alle gilt:

- Bei `2xx` ist `data` der als JSON geparste Body, ist er kein JSON, der Text. Ohne Body und bei allen anderen Codes ist `data` `None`.
- Kein Code ist dokumentiert. Erfolg daher mit `200 <= result.code < 300` prüfen, `message` nennt bei Fehlern den Code.
- Argumente mit „Body wie in der WebUI“ werden unverändert gesendet, `dict` und `list` als JSON.

```python
result = ark.get_active_jobs()

if 200 <= result.code < 300:
    for job in result.data["active_jobs"]:
        print(job["id"], job["current_status"], job["progress_txt"])
else:
    raise RuntimeError(result.message)
```

[to Top](#inhalt)

### Komfort-Funktionen für Restore-Jobs

Setzen auf den Job-Endpunkten unten auf. Bekannt ist bisher nur das Format von `/job/active`; die übrigen Job-Listen werden gleich gelesen: jede Liste von `dict`s in der Antwort gilt als Job-Liste.

[to Top](#inhalt)

#### get_restore_job_status

Einen Restore-Job finden. Sucht nacheinander in [get_active_jobs](#jobs), [get_job_queue](#jobs), [get_completed_jobs](#jobs) und [get_inactive_jobs](#jobs).

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `job_id` | ja | ID aus `restore_backups()` bzw. `session_guid` aus `restore_hashes()` |

```python
result = ark.get_restore_job_status("restorejob_80XIRz")

if 200 <= result.code < 300 and result.data:
    # active, queued, completed oder inactive
    print(result.data["state"], result.data["job"].get("current_status"))
elif 200 <= result.code < 300:
    print("Job nicht gefunden")
else:
    raise RuntimeError(result.message)
```

Ein Eintrag passt, wenn seine `id` gleich `job_id` ist oder mit `job_id` plus Bindestrich beginnt. `"restorejob_80XIRz"` findet also auch den Lauf `"restorejob_80XIRz-__restorejob__---2026-9-4-14-37-18-672061"`.

[to Top](#inhalt)

#### get_restore_job_errors

Fehlermeldungen eines Restore-Jobs sammeln, aus dem Listeneintrag und [get_job_details](#jobs).

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `job_id` | ja | – | wie bei `get_restore_job_status()` |
| `job_type` | nein | Teil der ID vor dem ersten `_`, z. B. `restorejob` | Job-Typ für `get_job_details()` |

```python
result = ark.get_restore_job_errors("restorejob_80XIRz")

if 200 <= result.code < 300 and result.data:
    for message in result.data["errors"]:
        print(result.data["state"], message)
elif 200 <= result.code < 300:
    print("Job nicht gefunden")
else:
    # Details nicht abrufbar, errors nur aus dem Listeneintrag
    print(result.message, result.data.get("errors"))
```

Gesammelt werden alle Texte unter Schlüsseln, die `error`, `fail`, `warn` oder `alert` enthalten, ohne Duplikate.

[to Top](#inhalt)

#### stop_restore_job

Einen laufenden Restore-Job stoppen und prüfen, ob er steht.

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `job_id` | ja | – | wie bei `get_restore_job_status()` |
| `timeout` | nein | `30` | Sekunden, die auf das Stoppen gewartet wird |
| `poll_seconds` | nein | `2` | Abstand der Statusabfragen |

`timeout` und `poll_seconds` sind keyword-only.

```python
result = ark.stop_restore_job("restorejob_80XIRz")

if 200 <= result.code < 300 and result.data["stopped"]:
    print("gestoppt, Zustand:", result.data["state"])
elif 200 <= result.code < 300:
    print("nicht gestoppt, Zustand:", result.data["state"])
else:
    raise RuntimeError(result.message)
```

Läuft der Job nicht, wird nichts gesendet: `stopped` ist `False`, `message` ist `"Job laeuft nicht"`. `state` ist `""`, wenn der Job nach dem Stoppen in keiner Liste mehr steht.

[to Top](#inhalt)

### System

| Methode | Endpunkt | Argumente |
| --- | --- | --- |
| `get_notifications_init()` | `GET /notifications/init` | – |
| `get_notifications()` | `GET /notifications` | – |
| `get_license_status()` | `GET /license/status` | – |
| `get_destinations()` | `GET /destinations` | – |
| `get_schedule_string(schedule)` | `POST /schedule/scheduleString` | Zeitplan wie in der WebUI |
| `send_email(data)` | `POST /email/send` | Body wie in der WebUI |

[to Top](#inhalt)

### Jobs

| Methode | Endpunkt | Argumente |
| --- | --- | --- |
| `get_job_queue()` | `GET /job/queue` | – |
| `get_active_jobs()` | `GET /job/active` | – |
| `get_completed_jobs()` | `GET /job/completed` | – |
| `get_inactive_jobs()` | `GET /job/inactive` | – |
| `get_job(job_id)` | `GET /job/<id>` | – |
| `get_job_actions(job_id)` | `GET /job/actions/<id>` | – |
| `get_job_details(job_type, job_id)` | `GET /job/details/<job_type>/<id>` | – |
| `create_job(data)` | `PUT /job` | Body wie in der WebUI |
| `modify_job(job_id, data)` | `PUT /job/modify/<id>` | Body wie in der WebUI |
| `run_job(job_id)` | `POST /job/run/<id>` | – |
| `stop_job(job_id)` | `POST /job/stop/<id>` | – |
| `delete_job(job_id)` | `DELETE /job/<id>` | – |
| `wait_for_events(last_event=0)` | `GET /events/<last_event>` | Long-Poll, Antwort spätestens nach etwa 50 s |

[to Top](#inhalt)

### Restore und Backup

| Methode | Endpunkt | Argumente |
| --- | --- | --- |
| `get_restore_targets(data)` | `POST /restore/restoreTargets` | Auswahl der Backups wie in der WebUI |
| `get_restore_names(data)` | `POST /restore/getRestoreNames` | Auswahl der Backups wie in der WebUI |
| `get_backup_contents(backup_id, page=None)` | `GET /backup/contents/<backup_id>[/<page>]` | – |
| `get_json_backup_contents(backup_id)` | `POST /backup/getJSONBackupContents` | sendet `{"id": backup_id}` |
| `get_session_files(backup_id, page_num)` | `POST /backup/sessionFiles` | sendet `{"id": backup_id, "page_num": page_num}` |
| `prepare_disk_search()` | `POST /backup/disk/search/prepare` | stößt die Indexierung an |
| `remove_backups(data)` | `DELETE /backup/removeBackups` | Auswahl der Backups wie in der WebUI |
| `get_disk_license()` | `GET /disk/license` | – |
| `get_disk_backups()` | `GET /disk/getDiskBackups` | – |

[to Top](#inhalt)

### Tape

| Methode | Endpunkt | Argumente |
| --- | --- | --- |
| `get_tape_license()` | `GET /tape/license` | – |
| `get_tape_servers()` | `GET /tape/servers` | – |
| `get_tape_server_list()` | `GET /tape/getTapeServers` | – |
| `get_tape_backups()` | `GET /tape/getTapeBackups` | – |
| `get_tape_jobs(server_id)` | `GET /tape/jobs/<server_id>` | – |
| `get_tape_job_log(server_id, job_id)` | `GET /tape/log/<server_id>/<job_id>` | `job_id` aus `get_tape_jobs()` |
| `get_tape_alerts(server_id=None)` | `GET /tape/alerts[/<server_id>]` | – |
| `acknowledge_tape_alert(server_id, alert_id)` | `PUT /tape/alerts/acknowledge/<server_id>/<alert_id>` | – |
| `get_pool_contents(pool_id, page_num)` | `POST /tape/getPoolContents` | sendet `{"id": pool_id, "page_num": page_num}` |
| `scan_tapes()` | `POST /tape/scanTapes` | liest die Library neu ein |
| `get_pool_tapes(pool_id)` | `GET /tape/pool/<pool>/tapes` | – |
| `set_pool_tapes(pool_id, data)` | `PUT /tape/pool/<pool>/tapes` | Body wie in der WebUI |
| `get_assigned_tapes(pool_id)` | `GET /tape/getAssignedTapes/<pool>` | – |
| `get_unassigned_tapes(pool_id)` | `GET /tape/getUnassignedTapes/<pool>` | – |

Anlegen, Abrufen, Umbenennen und Löschen von Pools sind offiziell, siehe [get_tape_pools](#get_tape_pools).

[to Top](#inhalt)

### Quellen

| Methode | Endpunkt |
| --- | --- |
| `get_media_spaces()` | `GET /sources/mediaSpaces` |
| `get_media_space_types()` | `GET /sources/mediaSpaceTypes` |
| `get_project_spaces()` | `GET /sources/projectSpaces` |
| `get_private_spaces()` | `GET /sources/privateSpaces` |
| `get_exchange_spaces()` | `GET /sources/exchangeSpaces` |
| `get_flow_sources()` | `GET /sources/flow` |
| `get_ark_tape_db()` | `GET /sources/arkTapeDB` |

[to Top](#inhalt)

### Download

| Methode | Endpunkt | Argumente |
| --- | --- | --- |
| `download_csv(params=None)` | `GET /download/csv?<params>` | Query-Parameter als `dict` |
| `download_search_csv(params=None)` | `GET /download/search_csv?<params>` | Query-Parameter als `dict` |

`data` ist hier immer der CSV-Text, bei Fehlern `""`.

[to Top](#inhalt)

### Testskript

`ark_probe.py` ruft alle lesenden Endpunkte einmal auf und speichert jede Antwort als JSON in `ark_probe/<Zeitstempel>/`. Es startet, stoppt, ändert und löscht nichts. Die Verbindung kommt über `tb_link_api()` aus der TOOLBOX.

```powershell
python ark_probe.py --env .env
python ark_probe.py --env .env --job-id restorejob_80XIRz
python ark_probe.py --env .env --server-id ark.tapeserver_... --tape-job-id 123
python ark_probe.py --env .env --backup-id ark.tapeserver_... --pool-id poolid-1-...
python ark_probe.py --env .env --events
```

| Option | Bedeutung |
| --- | --- |
| `--env` | `.env` mit `ARK_USER`, `ARK_PASSWORD`, `ARK_HOST` (Pflicht) |
| `--out` | Zielordner, Standard `ark_probe/` neben dem Skript |
| `--job-id` | zusätzlich Job, Aktionen, Details, Status und Fehler dieses Jobs, mit kurzer und langer ID |
| `--job-type` | Job-Typ für die Details, Standard Teil der ID vor dem ersten `_` |
| `--backup-id` | zusätzlich Inhalt und Session-Dateien dieses Backups |
| `--server-id` | zusätzlich Jobs und Alarme dieses Tape-Servers |
| `--tape-job-id` | zusätzlich das Log dieses Tape-Jobs, braucht `--server-id` |
| `--pool-id` | zusätzlich Pool, Tapes und Inhalt dieses Pools |
| `--events` | zusätzlich `/events/0`, wartet bis zu 50 s |

Die Konsole zeigt je Aufruf Code, Methode und Struktur der Antwort. `00_summary.json` fasst alle Codes zusammen.

[to Top](#inhalt)
