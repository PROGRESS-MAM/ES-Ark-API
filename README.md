# ARK

Wrapper für die EditShare Ark API.

## Installation

Als Abhängigkeit direkt aus GitHub:

```powershell
pip install "ArkAPI @ git+https://github.com/PROGRESS-MAM/ES-Ark-API.git@main"
```

Die Anführungszeichen sind Pflicht, sobald Leerzeichen um das `@` stehen — sonst zerlegt die Shell den Ausdruck in zwei Argumente. Ohne Leerzeichen geht es auch ohne:

```powershell
pip install ArkAPI@git+https://github.com/PROGRESS-MAM/ES-Ark-API.git@main
```

Das letzte `@main` wählt den Branch. Ein Tag oder Commit funktioniert genauso, z. B. `@v0.1.1`.

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

`-e` steht für editable. Statt die Dateien nach `site-packages` zu kopieren, legt pip dort nur einen Verweis auf dieses Verzeichnis ab. Änderungen an `ArkAPI/ark.py` sind damit beim nächsten Start des Python-Prozesses wirksam, ohne erneutes Installieren. Ein `pip install .` ohne `-e` kopiert dagegen und friert den Stand ein — dann arbeitet man weiter an einer Datei, die niemand mehr importiert. Für Projekte, die ArkAPI nur benutzen, ist die Variante aus GitHub die richtige.

## Inhalt

- [Installation](#installation)
- [Verbinden](#verbinden)
- [Komfort-Funktionen](#komfort-funktionen)
  - [restore_backup](#restore_backup)
  - [restore_files_by_hash](#restore_files_by_hash)
  - [search_by_flow_hash](#search_by_flow_hash)
  - [search_all_backups](#search_all_backups)
  - [get_tapes](#get_tapes)
  - [find_tape](#find_tape)
  - [find_backup](#find_backup)
  - [find_backups_by_space_name](#find_backups_by_space_name)
  - [find_backups_by_space_uuid](#find_backups_by_space_uuid)
  - [tapes_from_file_status](#tapes_from_file_status)
- [API-Wrapper-Funktionen](#api-wrapper-funktionen)
  - [get_backups](#get_backups)
  - [restore_backups](#restore_backups)
  - [restore_hashes](#restore_hashes)
  - [get_file_hash_database_status](#get_file_hash_database_status)
  - [get_file_status](#get_file_status)
  - [has_file_status](#has_file_status)
  - [get_file_statuses](#get_file_statuses)
  - [get_disk_search_status](#get_disk_search_status)
  - [search_backups](#search_backups)
  - [get_tape_library_status](#get_tape_library_status)
- [Rückgabe-Prinzip](#rückgabe-prinzip)
  - [Das Muster in den Snippets](#das-muster-in-den-snippets)
  - [Schlanker Aufruf](#schlanker-aufruf)
  - [Fehlerkennungen](#fehlerkennungen)
  - [message ist immer ein String](#message-ist-immer-ein-string)
- [Bekannte Fallstricke](#bekannte-fallstricke)
- [Interne Funktionen](#interne-funktionen)
- [Exportliste](#exportliste)
- [Referenz](#referenz)

## Verbinden

```python
import ArkAPI

ark = ArkAPI.Ark.create_instance(
    os.environ.get("FLOW_USER"),
    os.environ.get("FLOW_PASSWORD"),
    os.environ.get("FLOW_HOST"),
)
```

Alle drei Werte sind Pflicht, die Reihenfolge ist **Benutzer, Passwort, Host**. Ark antwortet per HTTPS auf Port 8000.

Eine statische Fabrik an der Klasse, wie bei `FlowAPI.Metadata`. Auf Modulebene gibt es keine Funktionen — `ArkAPI.create_instance(...)` ohne `Ark.` dazwischen existiert nicht.

Die Umgebungsvariablen liest das aufrufende Projekt, nicht `ArkAPI`, genauso wie in der Toolbox. Das Paket kennt keine Variablennamen. Liegen die Werte in einer `.env`, braucht es `load_dotenv()` davor; `os.environ` liest solche Dateien nicht von allein. Fehlt eine Variable, gibt `os.environ.get()` ein `None` zurück, das bis in `http.client` durchläuft und dort als schwer lesbarer `TypeError` auffällt.

Ark ist über den FLOW-Gateway auf Port 8006 **nicht** erreichbar. Am laufenden System geprüft: der direkte Weg auf Port 8000 antwortet, der Gateway nicht. Die Spezifikation nennt als Server ausschliesslich `https://{server}:8000/` ohne Basispfad. Deshalb gibt es hier bewusst kein `create_gateway_instance()`, anders als bei `FlowAPI.Metadata`.

Sitzt ein Reverse Proxy vor dem Server, kann der antworten, bevor Ark den Request sieht. Solche Antworten tragen einen Code, den die jeweilige Funktion nicht aufführt, und landen im `else`-Zweig.

---

## Komfort-Funktionen

Setzen auf den [API-Wrapper-Funktionen](#api-wrapper-funktionen) auf und kennen keinen eigenen Endpunkt. Ihre Statuscodes sind die der jeweils aufgerufenen Funktion. Das Muster hinter den `if`/`elif`-Ketten steht unter [Rückgabe-Prinzip](#rückgabe-prinzip).

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
    print("Job:", result.data)                  # restorejob_sovh0C
else:
    raise RuntimeError(result.message)
```

`target` besteht bei Media Spaces aus drei durch je drei Bindestriche getrennten Teilen: ESA-Gruppe, Server-Group-Member und Pfad zum Bit Bucket. Bei allen anderen Space-Typen genügt die ESA-Gruppe, z. B. `esa_HiNbl`.

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
    # INVALID_HASH, INVALID_DESTINATION, INVALID_SOURCE,
    # MISSING_REQUIRED_FIELD
    print(result.error, result.message)
else:
    raise RuntimeError(result.message)
```

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
    print(result.error, result.message)         # INVALID_HASH
else:
    raise RuntimeError(result.message)
```

Andere Hash-Versionen unterstützt dieser Suchmodus nicht, sie werden als Warnung geloggt.

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

### find_backups_by_space_uuid

Dasselbe über die UUID.

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

### tapes_from_file_status

Barcodes der Tapes aus einem `filestatus`-Eintrag sammeln. Reine Auswertung, kein Request — daher `@staticmethod`, **ohne** `ArkResult` und ohne Statuscode.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `file_status` | ja | ein Eintrag aus der `data` von `get_file_status()` oder `get_file_statuses()` |

```python
for match in ark.get_file_status(flow_hash).data:
    print(ArkAPI.Ark.tapes_from_file_status(match))     # ["001234L5"]
```

Gibt eine `list` zurück, leer bei Disk-Backups.

---

## API-Wrapper-Funktionen

Die zehn Operationen der Spezifikation, je eine Methode pro Endpunkt. Die `if`/`elif`-Ketten führen genau die Codes auf, die die Spezifikation für diesen Endpunkt dokumentiert. Jeder andere Code landet im `else` — siehe [Das Muster in den Snippets](#das-muster-in-den-snippets).

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
    print("Job:", result.data)                  # restorejob_sovh0C
else:
    raise RuntimeError(result.message)
```

Der Service antwortet mit einem reinen JSON-String, nicht mit einem Objekt. `data` ist deshalb ein `str`. Bequemer geht es mit [restore_backup](#restore_backup).

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
    # INVALID_HASH, INVALID_DESTINATION, INVALID_SOURCE,
    # MISSING_REQUIRED_FIELD
    print(result.error, result.message)
else:
    raise RuntimeError(result.message)
```

Es gilt alles oder nichts: ein einziger nicht restaurierbarer Hash lässt den ganzen Auftrag scheitern. Bei 400 und 404 ist `data` ein leeres `dict`. Bequemer geht es mit [restore_files_by_hash](#restore_files_by_hash).

### get_file_hash_database_status

`GET /filestatus/database` — Status des Hash-Imports in die Ark-Datenbank.

Keine Argumente.

```python
result = ark.get_file_hash_database_status()

if result.code == 200:
    print(result.data["status"])            # importing, complete oder error
    print(result.data["progress_complete"],
          "von", result.data["progress_estimated"])
else:
    raise RuntimeError(result.message)
```

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
    print("keine Kopie in Ark")                 # HASH_NOT_FOUND
elif result.code == 400:
    print(result.error, result.message)         # INVALID_HASH
else:
    raise RuntimeError(result.message)
```

404 ist eine Fachauskunft, kein Transportfehler. Wer daran eine Löschentscheidung hängt, muss 400 und 404 unterscheiden — beide liefern eine leere `data`.

### has_file_status

`HEAD /filestatus/{FileHash}` — nur prüfen, ob Ark eine Kopie hat. Die günstige Variante von [get_file_status](#get_file_status): kein Body, nur der Statuscode. Für Schleifen über viele Dateien deutlich sparsamer.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `flow_hash` | ja | FLOW-Hash, Version 0, 1 oder 2 |

```python
result = ark.has_file_status("2:d41d8cd98f00b204e9800998ecf8427e")

if result.code == 204:
    os.remove(original)                         # Ark hat eine Kopie
elif result.code == 404:
    print("keine Kopie in Ark")
elif result.code == 400:
    print("Hash ungueltig:", result.message)
else:
    raise RuntimeError(result.message)          # nicht loeschen, Antwort unklar
```

Diese Operation liefert **kein 200** — ein Vergleich auf 200 geht hier immer schief. Keiner der drei Codes hat einen Body, `data` ist immer `None` und `error` immer `""`. Die Auskunft steckt allein im Code.

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
    print(result.error, result.message)   # INVALID_HASH, mindestens einer
else:
    raise RuntimeError(result.message)
```

Diese Operation kennt **kein 404**. Hashes ohne Kopie fehlen einfach im Ergebnis, ein Abgleich mit `hash_list` zeigt also, welche Dateien nicht in Ark liegen.

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
    print(result.error, result.message)         # INVALID_HASH
else:
    raise RuntimeError(result.message)
```

`data` enthält bei 200 `total_matches`, `limit`, `offset` und `results`, sonst ein leeres `dict`. Für alle Seiten auf einmal siehe [search_all_backups](#search_all_backups).

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

### Das Muster in den Snippets

Die API kennt genau vier Codes: **200, 204, 400, 404**. Welche davon eine Funktion liefern kann, steht in ihrem Snippet und in ihrem Docstring. Codes werden als Zahl verglichen, es gibt keine Code-Konstanten.

```python
if result.code == 200:
    ...
elif result.code == 404:
    ...
elif result.code == 400:
    print(result.error, result.message)
else:
    raise RuntimeError(result.message)
```

Der `else`-Zweig ist kein Schmuck. Kommt ein Code, den die Funktion nicht aufführt, hat nicht Ark geantwortet, sondern ein Proxy, die Authentifizierung oder ein abgebrochener Socket. `message` sagt das dann ausdrücklich:

```
Statuscode 502 ist fuer diesen Endpunkt nicht dokumentiert: <html>...
```

`code == 0` heißt: keine verwertbare Antwort, siehe [Bekannte Fallstricke](#bekannte-fallstricke).

### Schlanker Aufruf

Für die Endpunkte, die laut Spezifikation nur 200 kennen, reicht der Stil aus `FlowAPI.metadata` — `last_return_code()` ist von `Connection` geerbt und funktioniert:

```python
backups = ark.get_backups().data
if ark.last_return_code() != 200:
    ...
```

Vorsicht bei den Komfort-Funktionen: `search_all_backups()` schickt pro Seite einen Request, `find_backup()` einen internen `get_backups()`. `last_return_code()` zeigt danach nur den **letzten** Request, `result.code` dagegen den Code, auf den die Funktion gelaufen ist. Bei mehreren Aufrufen hintereinander überschreibt jeder neue Request den Wert — `result.code` bleibt erhalten.

### Fehlerkennungen

`result.error` ist die maschinenlesbare Kennung aus dem Fehlerobjekt der API, 1:1 übernommen. Der Wrapper vergleicht sie nirgends und definiert keine Konstanten dafür — verglichen wird im Caller gegen die Zeichenkette:

```python
if result.code == 400:
    if result.error == "INVALID_HASH":
        ...             # Hash in der CSV korrigieren
    elif result.error == "INVALID_DESTINATION":
        ...             # Restore-Ziel falsch konfiguriert
```

Ein Code sagt nicht, welche Kennung kommt: bei `restore_hashes()` kann 400 alle vier Ursachen bedeuten. Was welcher Endpunkt liefert:

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

**Die Liste ist nicht abschließend.** Die Spezifikation führt diese Werte nur als Beispiel, nicht als `enum`. Ein `else`-Zweig, der einen unbekannten Wert protokolliert, ist deshalb Pflicht.

### message ist immer ein String

`message` ist bei Fehlern das `details`-Feld der API. Bei `restore_hashes()` und 404 ist `details` allerdings ein Objekt und keine Zeichenkette — es listet jeden gescheiterten Hash mit eigener Begründung:

```json
{
  "code": 404,
  "error": "HASHES_NOT_RESTORABLE",
  "details": {
    "files": [
      {"flow_hash": "2:0000...", "error": "Hash not found in any source"}
    ]
  }
}
```

Das ist eine Inkonsistenz der Spezifikation: dasselbe Schema deklariert `details` als `type: string` mit der Beschreibung „A string which can be presented to human users“. Nur das Beispiel zeigt ein Objekt.

Kommt ein Objekt, wird es als JSON serialisiert. `message` ist damit in jedem Fall eine Zeichenkette, `result.message.strip()` läuft nicht ins Leere, und fürs Protokoll reicht `message` allein:

```python
if result.code == 404:
    logging.error("Restore gescheitert: %s", result.message)
    # -> {"files": [{"flow_hash": "2:0000...", "error": "Hash not ..."}]}
```

Wer die Einträge einzeln braucht, liest den Rohbody — der ist zeichengleich zur Serverantwort:

```python
if result.code == 404:
    roh = json.loads(ark.last_response())
    for eintrag in roh["details"]["files"]:
        print(eintrag["flow_hash"], eintrag["error"])
```

Das Objekt landet **nicht** in `data`. `data` behält bei jedem Fehler den Leerwert der Funktion — und der ist je Endpunkt eine Liste, ein Dict, ein String oder `None`. Ein Objekt dort würde den Typ von `data` je Statuscode wechseln lassen.

`error` wird umgekehrt behandelt: ist es keine Zeichenkette, bleibt es leer. Das Feld wird mit `==` gegen Kennungen verglichen, ein JSON-Text darin wäre irreführend.

---

## Bekannte Fallstricke

`code == 0` mit einer Meldung über ungültiges JSON fängt einen Bug der FlowAPI ab: bricht die Verbindung nach einem erfolgreichen Request weg, lässt `core.do_request()` den alten Statuscode stehen und legt eine Klartextmeldung in den Body. `getThatReturnsObj()` schickt die durch `json.loads()` und wirft einen `JSONDecodeError`. Der Wrapper nutzt `getThatReturnsObj()` deshalb nicht.

`POST /filestatus/` braucht den abschließenden Slash. `HEAD /filestatus/{FileHash}` liefert 204, nie 200 — und 204 bedeutet dort **Treffer gefunden**, nicht „nichts da“.

`POST /filestatus/` dokumentiert kein 404. Kommt trotzdem eins, meldet `message` den Code als für diesen Endpunkt undokumentiert.

Bei `restore_hashes()` und 404 ist das `details`-Feld der API ein Objekt, obwohl das Schema eine Zeichenkette vorschreibt. `message` trägt es dann als JSON — siehe [message ist immer ein String](#message-ist-immer-ein-string).

Der Ark-Port 8000 steht als Zahl in `connect()`. `FlowAPI.core` kennt dafür keine Konstante.

## Interne Funktionen

Alles mit `_` am Anfang ist intern und kann sich ohne Vorwarnung ändern: `_read_error()`, `_request()`, `_filter_backups()`.

## Exportliste

`ArkAPI/ark.py` erzeugt sein `__all__` in der letzten Zeile selbst.

```python
# --------- KEEP THIS LINE AT THE END ---------
__all__ = [
    name
    for name in dir()
    if name.startswith(("Ark", "ARK_", "create_"))
]
```

Das sind drei Namen: `Ark`, `ArkResult` und `ARK_VERSION`. Aus `FlowAPI.core` kommt nur `Connection`, und weil dieser Name keinen der Prefixe trägt, braucht es dafür keinen Alias. Der Prefix `create_` greift derzeit nichts, weil `create_instance` an der Klasse hängt und nicht am Modul — er bleibt als Konvention für den Fall stehen, dass doch einmal eine Modulfunktion dazukommt. Das Paket kennt keine Konstanten: Statuscodes sind Zahlen, Fehlerkennungen und Aufzählungswerte sind Zeichenketten.

**Neue öffentliche Namen müssen einen dieser Prefixe tragen**, sonst tauchen sie im Paket nicht auf.

## Referenz

[EditShare Ark API](https://developers.editshare.com/?urls.primaryName=EditShare%20Ark)
