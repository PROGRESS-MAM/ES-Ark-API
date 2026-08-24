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

| Funktion | Beschreibung | nutzt |
| --- | --- | --- |
| [restore_backup](#restore_backup) | Ein einzelnes Backup zurückspielen | `restore_backups()` |
| [restore_files_by_hash](#restore_files_by_hash) | Eine Liste von FLOW-Hashes in einen Media Space zurückspielen | `restore_hashes()` |
| [search_by_flow_hash](#search_by_flow_hash) | Den Backup-Index nach einem FLOW-Hash durchsuchen | `search_backups()` |
| [search_all_backups](#search_all_backups) | Alle Treffer einer Suche seitenweise holen | `search_backups()` |
| [get_tapes](#get_tapes) | Alle bekannten Tapes holen | `get_tape_library_status()` |
| [find_tape](#find_tape) | Ein Tape-Volume über seinen Barcode finden | `get_tape_library_status()` |
| [find_backup](#find_backup) | Ein einzelnes Backup über seine ID finden | `get_backups()` |
| [find_backups_by_space_name](#find_backups_by_space_name) | Alle Backups eines Media Space über den Namen finden | `get_backups()` |
| [find_backups_by_space_uuid](#find_backups_by_space_uuid) | Alle Backups eines Media Space über die UUID finden | `get_backups()` |
| [tapes_from_file_status](#tapes_from_file_status) | Barcodes der Tapes aus einem `filestatus`-Eintrag sammeln | kein Request |

**4. [API-Wrapper-Funktionen](#api-wrapper-funktionen)**

| Funktion | Endpunkt | Codes |
| --- | --- | --- |
| [get_backups](#get_backups) | `GET /restore/backups` | 200 |
| [restore_backups](#restore_backups) | `POST /restore/restoreBackups` | 200 |
| [restore_hashes](#restore_hashes) | `POST /restore/hashes` | 200, 400, 404 |
| [get_file_hash_database_status](#get_file_hash_database_status) | `GET /filestatus/database` | 200 |
| [get_file_status](#get_file_status) | `GET /filestatus/{FileHash}` | 200, 400, 404 |
| [has_file_status](#has_file_status) | `HEAD /filestatus/{FileHash}` | 204, 400, 404 |
| [get_file_statuses](#get_file_statuses) | `POST /filestatus/` | 200, 400 |
| [get_disk_search_status](#get_disk_search_status) | `GET /backup/disk/search/status` | 200 |
| [search_backups](#search_backups) | `POST /backup/search` | 200, 400 |
| [get_tape_library_status](#get_tape_library_status) | `GET /api/tape/library/tapes` | 200 |

**5. [Rückgabe-Prinzip](#rückgabe-prinzip)**

**6. [Referenz](#referenz)**

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

---

## API-Wrapper-Funktionen

Die zehn Operationen der API, je eine Methode pro Endpunkt. Die `if`/`elif`-Ketten führen genau die Codes auf, die die Spezifikation für diesen Endpunkt dokumentiert. Jeder andere Code landet im `else`.

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

`code == 0` bedeutet Verbindungsabbruch oder keine verwertbaren Daten — die Antwort kam dann nicht von Ark.

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

Ein Code sagt nicht, welche Kennung kommt: bei `restore_hashes()` kann 400 alle vier Ursachen bedeuten.

Was welcher Endpunkt liefert:

| Funktion | Code | `error` |
| --- | --- | --- |
| `restore_hashes()` | 400 | `INVALID_HASH`, `INVALID_DESTINATION`, `INVALID_SOURCE`, `MISSING_REQUIRED_FIELD` |
| `restore_hashes()` | 404 | `HASHES_NOT_RESTORABLE` |
| `get_file_status()` | 400 | `INVALID_HASH` |
| `get_file_status()` | 404 | `HASH_NOT_FOUND` |
| `get_file_statuses()` | 400 | `INVALID_HASH` |
| `search_backups()` | 400 | `INVALID_HASH` |
| `has_file_status()` | 400, 404 | — kein Body, `error` ist immer `""` |

Die Komfort-Funktionen erben die Werte der Funktion, die sie aufrufen.

[to Top](#inhalt)

## Referenz

[EditShare Ark API](https://developers.editshare.com/?urls.primaryName=EditShare%20Ark)

[to Top](#inhalt)

