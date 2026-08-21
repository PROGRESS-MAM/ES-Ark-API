# ark

Wrapper für die EditShare Ark API. Setzt auf `FlowAPI.core` auf, gleicher Stil wie `FlowAPI.metadata`. Eine Datei: `ark/ark.py`.

## Installation

```powershell
pip install -e .
```

Als Abhängigkeit in einem anderen Projekt:

```toml
dependencies = [
    "ark @ git+https://github.com/PROGRESS-MAM/ES-Ark-API.git@main",
]
```

## Rückgabe-Prinzip

Jede Methode gibt ein `ArkResult` zurück. Der Statuscode wird unverändert durchgereicht, ausgewertet wird im Caller.

```python
result = ark.get_file_status("2:d41d8cd98f00b204e9800998ecf8427e")

result.code        # 200, 400 oder 404
result.data        # Nutzdaten, bei Fehlern der Leerwert der Methode
result.message     # Klartext: details der API, sonst Text aus der Spezifikation
result.error       # maschinenlesbar, z. B. "INVALID_HASH", sonst ""
result.from_ark    # True, wenn code einer der vier dokumentierten Codes ist
result.raw         # unveränderter Response-Body
result.verb        # "GET", "POST" oder "HEAD"
result.endpoint    # angefragter Pfad

print(result)      # "200 A list of statuses for files managed by Ark"
```

Die API kennt genau vier Codes: **200, 204, 400, 404**. Kommt etwas anderes an, ist `from_ark` `False` — dann hat nicht Ark geantwortet, sondern Gateway, Auth oder ein abgebrochener Socket. `code == 0` heißt: keine verwertbare Antwort.

```python
if not result.from_ark:
    raise RuntimeError(result.message)

if result.code == 200:
    ...
elif result.code == 404:
    ...
elif result.code == 400:
    print(result.error, result.message)
```

Konstanten dafür: `ARK_OK`, `ARK_NO_CONTENT`, `ARK_BAD_REQUEST`, `ARK_NOT_FOUND`, `ARK_CODES`, `ARK_SUCCESS_CODES`, `ERROR_INVALID_HASH`, `ERROR_INVALID_DESTINATION`, `ERROR_INVALID_SOURCE`, `ERROR_MISSING_REQUIRED_FIELD`.

## Verbinden

| Methode | Pflicht | Optional |
|---|---|---|
| `Ark.create_instance(ip_addr, username, password)` | `ip_addr`, `username`, `password` | – |
| `Ark.create_gateway_instance(username, password)` | `username`, `password` | `ip_addr` (Standard: `EDITSHARE_DOCKER_GATEWAY`, sonst `127.0.0.1`) |
| `ark.connect(ip_addr, username, password)` | `ip_addr`, `username`, `password` | – |

```python
from ark import Ark

# direkt zum Ark-Server, Port 8000
ark = Ark.create_instance("10.0.0.5", "user", "pass")

# oder über das lokale Gateway, Port 8006
ark = Ark.create_gateway_instance("user", "pass")
```

`connect()` wird von `create_instance()` aufgerufen und ist selten direkt nötig. Über das Gateway kann ein Reverse Proxy antworten, bevor Ark den Request sieht — solche Antworten haben `from_ark == False`.

---

# Die zehn Endpunkt-Funktionen

## get_backups()

`GET /restore/backups` — alle in Ark gespeicherten Backups.

Keine Argumente.

```python
result = ark.get_backups()
for backup in result.data:
    print(backup["backup_id"], backup["media_space_name"], backup["date"])
```

| Code | Bedeutung | `data` |
|---|---|---|
| 200 | A list of backups managed by Ark available for restoration. | `list`, ggf. leer |

## restore_backups(data)

`POST /restore/restoreBackups` — Backups auf ein Storage-Ziel zurückspielen.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `data` | ja | Restore-Kommando. Pflichtfelder `backups` und `target_data`, optional `storage_goals` und `restoreTime` |

```python
result = ark.restore_backups({
    "backups": [{"backup_id": "ark.tapeserver_f541..."}],
    "target_data": {"ms_target": "esa_IBN1e---es-master---/efs/efs_1"},
})
print(result.data)   # "restorejob_sovh0C"
```

| Code | Bedeutung | `data` |
|---|---|---|
| 200 | Restoration job queued. | Job-ID als `str` |

Der Service antwortet mit einem reinen JSON-String, nicht mit einem Objekt. Bequemer geht es mit `restore_backup()`.

## restore_hashes(data)

`POST /restore/hashes` — einzelne Dateien anhand ihrer FLOW-Hashes zurückspielen.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `data` | ja | Restore-Kommando. Pflichtfelder `files` und `destination`, optional `source` |

```python
result = ark.restore_hashes({
    "files": [{
        "flow_hash": "2:d41d8cd98f00b204e9800998ecf8427e",
        "restore_path": "restored_files/",
    }],
    "destination": {"mediaspace": "MyMediaSpace"},
})
```

| Code | Bedeutung | `data` |
|---|---|---|
| 200 | Hash-based restore job created successfully. | `dict` mit `session_guid` |
| 400 | Bad Request - Invalid hash format, invalid destination, or malformed request. `error` nennt die Ursache | `{}` |
| 404 | Not Found - One or more hashes cannot be restored. Kein Backup vorhanden oder Tape offline, `details` nennt die Hashes | `{}` |

Es gilt alles oder nichts: ein einziger nicht restaurierbarer Hash lässt den ganzen Auftrag scheitern. Bequemer geht es mit `restore_files_by_hash()`.

## get_file_hash_database_status()

`GET /filestatus/database` — Status des Hash-Imports in die Ark-Datenbank.

Keine Argumente.

```python
result = ark.get_file_hash_database_status()
print(result.data["status"])              # importing, complete oder error
print(result.data["progress_complete"], "von", result.data["progress_estimated"])
```

| Code | Bedeutung | `data` |
|---|---|---|
| 200 | Status of the file hash database | `dict` |

## get_file_status(flow_hash)

`GET /filestatus/{FileHash}` — Ark Backup-Status einer Datei.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `flow_hash` | ja | FLOW-Hash, Version 0 (`<md5>`), 1 (`1:<md5>`) oder 2 (`2:<md5>`). Erzeugen mit dem CLI-Kommando `flow-hash` |

```python
result = ark.get_file_status("2:d41d8cd98f00b204e9800998ecf8427e")
for match in result.data:
    print(match["storage_type"], match["pathname"], match["filename"])
    print(Ark.tapes_from_file_status(match))
```

| Code | Bedeutung | `data` |
|---|---|---|
| 200 | A list of statuses for files managed by Ark — Ark hält mindestens eine Kopie | `list` |
| 400 | Hash is invalid — passt nicht auf `(1:\|2:\|)[A-Fa-f0-9]{32}` | `[]` |
| 404 | No matches found — Ark hält keine Kopie | `[]` |

404 ist eine Fachauskunft, kein Transportfehler. Wer daran eine Löschentscheidung hängt, muss 400 und 404 unterscheiden — beide liefern eine leere `data`.

## has_file_status(flow_hash)

`HEAD /filestatus/{FileHash}` — nur prüfen, ob Ark eine Kopie hat. Die günstige Variante von `get_file_status()`: kein Body, nur der Statuscode. Für Schleifen über viele Dateien deutlich sparsamer.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `flow_hash` | ja | FLOW-Hash, Version 0, 1 oder 2 |

```python
result = ark.has_file_status("2:d41d8cd98f00b204e9800998ecf8427e")

if not result.from_ark:
    raise RuntimeError(result.message)      # nicht loeschen, Antwort unklar

if result.code == 204:
    os.remove(original)                     # Ark hat eine Kopie
elif result.code == 404:
    print("keine Kopie in Ark")
elif result.code == 400:
    print("Hash ungueltig:", result.message)
```

| Code | Bedeutung | `data` |
|---|---|---|
| 204 | One or more matches found | `None` |
| 400 | Invalid hash | `None` |
| 404 | No matches found | `None` |

Diese Operation liefert **kein 200**. Ein Vergleich auf 200 geht hier immer schief — auf 204 prüfen. `data` ist immer `None`, HEAD hat per HTTP keinen Body.

## get_file_statuses(hash_list)

`POST /filestatus/` — Massenabfrage für viele Hashes.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `hash_list` | ja | Liste von FLOW-Hashes, Version 0, 1 oder 2 |

```python
angefragt = ["2:d41d8cd9...", "2:1b54a3f2..."]
result = ark.get_file_statuses(angefragt)

gefunden = {match["hash"] for match in result.data}
fehlt = [h for h in angefragt if h not in gefunden]
```

| Code | Bedeutung | `data` |
|---|---|---|
| 200 | A list of statuses for files managed by Ark | `list`, ggf. leer |
| 400 | Hash is invalid — mindestens ein Hash der Liste ist ungültig | `[]` |

Diese Operation kennt **kein 404**. Hashes ohne Kopie fehlen einfach im Ergebnis, ein Abgleich mit `hash_list` zeigt also, welche Dateien nicht in Ark liegen.

## get_disk_search_status()

`GET /backup/disk/search/status` — Indexierungsstatus der Disk-Backups.

Keine Argumente.

```python
result = ark.get_disk_search_status()
print(result.data["indexed"], "von", result.data["total"], "Backups indexiert")
```

| Code | Bedeutung | `data` |
|---|---|---|
| 200 | Disk backup indexing status | `dict` mit `total`, `indexed`, `indexing`, `not_indexed`, `needs_indexing`, `total_files` |

Nur indexierte Disk-Backups sind über `search_backups()` auffindbar, daher vor einer Suche prüfen.

## search_backups(search_pattern, search_mode="contains", \*, backup_type=None, limit=100, offset=0)

`POST /backup/search` — Dateien in den indexierten Backups suchen.

| Argument | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| `search_pattern` | ja | – | Dateiname oder Muster. Bei `search_mode="flow_hash"` ein Hash der Version 2 |
| `search_mode` | nein | `"contains"` | `exact`, `contains`, `wildcard` oder `flow_hash` — siehe `SEARCH_*` |
| `backup_type` | nein | beide | `disk` oder `tape` — siehe `SOURCE_DISK`, `SOURCE_TAPE` |
| `limit` | nein | `100` | maximale Trefferzahl, 1 bis 10000 |
| `offset` | nein | `0` | Anzahl zu überspringender Treffer |

`backup_type`, `limit` und `offset` sind keyword-only.

```python
result = ark.search_backups("*.mov", "wildcard", backup_type="disk", limit=500)
print(result.data["total_matches"], "Treffer")
for hit in result.data["results"]:
    print(hit["filename"])
```

| Code | Bedeutung | `data` |
|---|---|---|
| 200 | Search results with pagination information | `dict` mit `total_matches`, `limit`, `offset`, `results` |
| 400 | Hash is invalid — bei `search_mode="flow_hash"` mit ungültigem Hash | `{}` |

## get_tape_library_status()

`GET /api/tape/library/tapes` — Status der Tape Library inklusive Inventar.

Keine Argumente.

```python
result = ark.get_tape_library_status()
print(result.data["timestamp"], len(result.data["tapes"]), "Tapes")
```

| Code | Bedeutung | `data` |
|---|---|---|
| 200 | Tape library status with complete inventory | `dict` mit `tapes` und `timestamp` |

---

# Komfort-Funktionen

Setzen auf den zehn Endpunkt-Funktionen auf und kennen keinen eigenen Endpunkt. Ihre Statuscodes sind daher die der jeweils aufgerufenen Funktion.

## restore_backup(backup_id, target, \*, ...)

Ein einzelnes Backup zurückspielen, baut den Body für `restore_backups()`.

| Argument | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| `backup_id` | ja | – | ID aus `get_backups()` |
| `target` | ja | – | Restore-Ziel, siehe unten |
| `space_type` | nein | `"ms"` | `ms`, `ps`, `priv`, `fe`, `es` oder `flow` — siehe `SPACE_*` |
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
print(result.code, result.data)      # 200 restorejob_sovh0C
```

`target` besteht bei Media Spaces aus drei durch je drei Bindestriche getrennten Teilen: ESA-Gruppe, Server-Group-Member und Pfad zum Bit Bucket. Bei allen anderen Space-Typen genügt die ESA-Gruppe, z. B. `esa_HiNbl`.

Codes: 200 wie `restore_backups()`.

## restore_files_by_hash(hashes, mediaspace, \*, ...)

Eine Liste von FLOW-Hashes in einen Media Space zurückspielen, baut den Body für `restore_hashes()`.

| Argument | Pflicht | Standard | Beschreibung |
|---|---|---|---|
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
else:
    print(result.code, result.error, result.message)
```

Codes: 200, 400, 404 wie `restore_hashes()`.

## search_by_flow_hash(flow_hash, \*, backup_type=None, limit=100)

Den Backup-Index nach einem FLOW-Hash durchsuchen, ruft `search_backups()` im Modus `flow_hash` auf.

| Argument | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| `flow_hash` | ja | – | Hash der **Version 2**, also `2:<md5>` |
| `backup_type` | nein | beide | `disk` oder `tape` |
| `limit` | nein | `100` | maximale Trefferzahl |

```python
result = ark.search_by_flow_hash("2:d41d8cd98f00b204e9800998ecf8427e")
```

Andere Hash-Versionen unterstützt dieser Suchmodus nicht, sie werden als Warnung geloggt.

Codes: 200, 400 wie `search_backups()`.

## search_all_backups(search_pattern, search_mode="contains", \*, ...)

Alle Treffer einer Suche seitenweise holen, ruft `search_backups()` bis `total_matches` erreicht ist.

| Argument | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| `search_pattern` | ja | – | Dateiname oder Muster |
| `search_mode` | nein | `"contains"` | `exact`, `contains`, `wildcard` oder `flow_hash` |
| `backup_type` | nein | beide | `disk` oder `tape` |
| `page_size` | nein | `1000` | Treffer pro Request, 1 bis 10000 |
| `max_results` | nein | `0` | Abbruch nach dieser Trefferzahl, `0` holt alles |

```python
result = ark.search_all_backups("Interview", "contains")
print(len(result.data), "Treffer gesammelt")
```

`data` ist die flache Liste aller Treffer. Bricht eine Seite mit einem anderen Code als 200 ab, kommt deren Ergebnis zurück und `data` enthält nur die bis dahin gesammelten Treffer.

Codes: 200, 400 wie `search_backups()`.

## get_tapes()

Alle bekannten Tapes holen, ruft `get_tape_library_status()` auf und gibt nur die Tape-Liste als `data` zurück.

Keine Argumente.

```python
for tape in ark.get_tapes().data:
    print(tape["barcode"], tape["in_changer"])
```

Enthält alle Tape-Volumes, nicht nur die aktuell geladenen.

Codes: 200 wie `get_tape_library_status()`.

## find_tape(barcode)

Ein Tape-Volume über seinen Barcode finden, filtert `get_tapes()`.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `barcode` | ja | Barcode des Tapes, z. B. `"001234L5"` |

```python
result = ark.find_tape("001234L5")
if result.code == 200 and not result.data:
    print("Barcode unbekannt")
```

`data` ist der passende Eintrag oder `{}`. Ein leeres `data` bei Code 200 heißt: nicht gefunden.

Codes: 200 wie `get_tape_library_status()`.

## find_backup(backup_id)

Ein einzelnes Backup über seine ID finden, filtert `get_backups()`.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `backup_id` | ja | die Backup-ID |

```python
backup = ark.find_backup("ark.tapeserver_f541...").data
```

`data` ist der passende Eintrag oder `{}`.

Codes: 200 wie `get_backups()`.

## find_backups_by_space_name(space_name)

Alle Backups eines Media Space über den Namen finden, filtert `get_backups()`.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `space_name` | ja | Name des Media Space |

```python
result = ark.find_backups_by_space_name("Projekt_2026")
job = ark.restore_backup(
    result.data[0]["backup_id"],
    "esa_IBN1e---es-master---/efs/efs_1",
)
```

Codes: 200 wie `get_backups()`.

## find_backups_by_space_uuid(space_uuid)

Dasselbe über die UUID.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `space_uuid` | ja | UUID des Media Space |

```python
result = ark.find_backups_by_space_uuid("6f3c1a...")
```

Codes: 200 wie `get_backups()`.

## Ark.tapes_from_file_status(file_status)

Barcodes der Tapes aus einem `filestatus`-Eintrag sammeln. Reine Auswertung, kein Request — daher `@staticmethod` und ohne `ArkResult`.

| Argument | Pflicht | Beschreibung |
|---|---|---|
| `file_status` | ja | ein Eintrag aus der `data` von `get_file_status()` oder `get_file_statuses()` |

```python
for match in ark.get_file_status(flow_hash).data:
    print(Ark.tapes_from_file_status(match))     # ["001234L5"]
```

Gibt eine `list` zurück, leer bei Disk-Backups.

---

## Bekannte Fallstricke

`code == 0` mit einer Meldung über ungültiges JSON fängt einen Bug der FlowAPI ab: bricht die Verbindung nach einem erfolgreichen Request weg, lässt `core.do_request()` den alten Statuscode stehen und legt eine Klartextmeldung in den Body. `getThatReturnsObj()` schickt die durch `json.loads()` und wirft einen `JSONDecodeError`. Der Wrapper nutzt `getThatReturnsObj()` deshalb nicht.

`POST /filestatus/` braucht den abschließenden Slash. `HEAD /filestatus/{FileHash}` liefert 204, nie 200.

## Interne Funktionen

Alles mit `_` am Anfang ist intern und kann sich ohne Vorwarnung ändern: `_read_error()`, `_request()`, `_filter_backups()`.

## Exportliste

`ark/ark.py` erzeugt sein `__all__` in der letzten Zeile selbst, wie `toolbox`.
Da es hier keinen Prefix wie `tb_` gibt, filtert die Zeile auf die
Namensräume des Moduls:

```python
# --------- KEEP THIS LINE AT THE END ---------
__all__ = [
    name
    for name in dir()
    if name.startswith(
        ("Ark", "ARK_", "ERROR_", "SEARCH_", "SOURCE_", "SPACE_", "STORAGE_")
    )
]
```

**Neue öffentliche Namen müssen einen dieser Prefixe tragen**, sonst tauchen
sie im Paket nicht auf. Ein `not name.startswith("_")` ginge hier nicht: das
würde `json`, `logging`, `Connection`, `create_instance` und
`create_gateway_instance_inner` mitexportieren.

`ark/__init__.py` bleibt dadurch schlank:

```python
from .ark import *
from .ark import ARK_VERSION

__version__ = ARK_VERSION
```

Nach einem `from ark import *` zeigt der Name `ark` beim Aufrufer auf das
Submodul `ark.ark`, nicht mehr auf das Paket. Praktisch ändert das nichts,
weil beide dieselben Namen tragen — `ARK_VERSION` und `__version__` sind
deshalb in beiden gesetzt. Wer es eindeutig will, nimmt
`from ark import Ark`.

## Version

`ARK_VERSION` in `ark/ark.py`, wird von `pyproject.toml` dynamisch gelesen.

## Referenz

[EditShare Ark API](https://developers.editshare.com/?urls.primaryName=EditShare%20Ark)
