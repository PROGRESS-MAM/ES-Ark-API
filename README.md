# ARK

Wrapper für die EditShare Ark API.

## Installation

```powershell
pip install -e .
```

Als Abhängigkeit in einem anderen Projekt:

```toml
dependencies = [
    "ArkAPI @ git+https://github.com/PROGRESS-MAM/ES-Ark-API.git@main",
]
```

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

### Schlanker Aufruf

Für die Endpunkte, die laut Spezifikation nur 200 kennen, reicht der Stil aus `FlowAPI.metadata` — `last_return_code()` ist von `Connection` geerbt und funktioniert:

```python
backups = ark.get_backups().data
if ark.last_return_code() != 200:
    ...
```

Vorsicht bei den Komfort-Funktionen: `search_all_backups()` schickt pro Seite einen Request, `find_backup()` einen internen `get_backups()`. `last_return_code()` zeigt danach nur den **letzten** Request, `result.code` dagegen den Code, auf den die Funktion gelaufen ist. Bei mehreren Aufrufen hintereinander überschreibt jeder neue Request den Wert — `result.code` bleibt erhalten.

### Ausführlicher Aufruf

Die API kennt genau vier Codes: **200, 204, 400, 404**. Welche davon eine Funktion liefern kann, steht bei jeder Funktion in diesem Dokument und in ihrem Docstring. Codes werden als Zahl verglichen, es gibt keine Code-Konstanten.

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

Kommt ein Code, den die Funktion nicht aufführt, hat nicht Ark geantwortet, sondern ein Proxy, die Authentifizierung oder ein abgebrochener Socket. `message` sagt das dann ausdrücklich:

```
Statuscode 502 ist fuer diesen Endpunkt nicht dokumentiert: <html>...
```

`code == 0` heißt: keine verwertbare Antwort, siehe [Bekannte Fallstricke](#bekannte-fallstricke).

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

Die Komfort-Funktionen erben die Werte der Funktion, die sie aufrufen: `restore_backup()` und `find_*()` über `get_backups()` bzw. `restore_backups()` (nur 200, also nie ein `error`), `restore_files_by_hash()` über `restore_hashes()`, `search_by_flow_hash()` und `search_all_backups()` über `search_backups()`.

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
result = ark.restore_hashes({"hashes": hashes, "destination": ziel})

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

## Verbinden

Die Argumente kommen in der Reihenfolge der Toolbox: **Benutzer, Passwort, Host**.

```python
import ArkAPI

ark = ArkAPI.create_instance(
    os.environ.get("FLOW_USER"),
    os.environ.get("FLOW_PASSWORD"),
    os.environ.get("FLOW_HOST"),
)
```

Alle drei Werte sind Pflicht. Ark antwortet per HTTPS auf Port 8000.

| Aufruf | Port |
| ---------- | ---- |
| `ArkAPI.create_instance(username, password, ip_addr)` | 8000 |
| `ark.connect(ip_addr, username, password)` | 8000 |

Die Umgebungsvariablen liest das aufrufende Projekt, nicht `ArkAPI` — genauso wie in der Toolbox. Das Paket kennt keine Variablennamen. Liegen sie in einer `.env`, braucht es `load_dotenv()` davor; `os.environ` liest solche Dateien nicht von allein.

`connect()` wird von `create_instance()` aufgerufen und ist selten direkt nötig.

### Warum die Reihenfolge von core abweicht

`FlowAPI.core` erwartet den Host zuerst:

```python
def create_instance(api, host_ip, username, password)
```

`ArkAPI.create_instance()` nimmt stattdessen `(username, password, ip_addr)` und dreht die Reihenfolge intern zurück. So sieht der Aufruf aus wie in der Toolbox.

### Kein Weg über den FLOW-Gateway

Ark ist über den Gateway auf Port 8006 nicht erreichbar. Am laufenden System geprüft: der direkte Weg auf Port 8000 antwortet, der Gateway nicht. Die Spezifikation nennt als Server ausschliesslich `https://{server}:8000/` ohne Basispfad und erwähnt keinen Gateway. Deshalb gibt es hier bewusst kein `create_gateway_instance()`, anders als bei `FlowAPI.Metadata`.

Sitzt ein Reverse Proxy vor dem Server, kann der antworten, bevor Ark den Request sieht. Solche Antworten tragen einen Code, den die jeweilige Funktion nicht aufführt — siehe [Ausführlicher Aufruf](#ausführlicher-aufruf).

---

## Die zehn Endpunkt-Funktionen

## get_backups()

`GET /restore/backups` — alle in Ark gespeicherten Backups.

Keine Argumente.

```python
result = ark.get_backups()
for backup in result.data:
    print(backup["backup_id"], backup["media_space_name"], backup["date"])
```

| Code | Bedeutung | `data` |
| ------ | ----------- | -------- |
| 200 | A list of backups managed by Ark available for restoration. | `list`, ggf. leer |

## restore_backups(data)

`POST /restore/restoreBackups` — Backups auf ein Storage-Ziel zurückspielen.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `data` | ja | Restore-Kommando. Pflichtfelder `backups` und `target_data`, optional `storage_goals` und `restoreTime` |

```python
result = ark.restore_backups({
    "backups": [{"backup_id": "ark.tapeserver_f541..."}],
    "target_data": {"ms_target": "esa_IBN1e---es-master---/efs/efs_1"},
})
print(result.data)   # "restorejob_sovh0C"
```

| Code | Bedeutung | `data` |
| --- | --- | --- |
| 200 | Restoration job queued. | Job-ID als `str` |

Der Service antwortet mit einem reinen JSON-String, nicht mit einem Objekt. Bequemer geht es mit `restore_backup()`.

## restore_hashes(data)

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
```

| Code | Bedeutung | `data` |
| --- | --- | --- |
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
| --- | --- | --- |
| 200 | Status of the file hash database | `dict` |

## get_file_status(flow_hash)

`GET /filestatus/{FileHash}` — Ark Backup-Status einer Datei.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `flow_hash` | ja | FLOW-Hash, Version 0 (`<md5>`), 1 (`1:<md5>`) oder 2 (`2:<md5>`). Erzeugen mit dem CLI-Kommando `flow-hash` |

```python
result = ark.get_file_status("2:d41d8cd98f00b204e9800998ecf8427e")
for match in result.data:
    print(match["storage_type"], match["pathname"], match["filename"])
    print(Ark.tapes_from_file_status(match))
```

| Code | Bedeutung | `data` |
| --- | --- | --- |
| 200 | A list of statuses for files managed by Ark — Ark hält mindestens eine Kopie | `list` |
| 400 | Hash is invalid — passt nicht auf `(1:\|2:\|)[A-Fa-f0-9]{32}` | `[]` |
| 404 | No matches found — Ark hält keine Kopie | `[]` |

404 ist eine Fachauskunft, kein Transportfehler. Wer daran eine Löschentscheidung hängt, muss 400 und 404 unterscheiden — beide liefern eine leere `data`.

## has_file_status(flow_hash)

`HEAD /filestatus/{FileHash}` — nur prüfen, ob Ark eine Kopie hat. Die günstige Variante von `get_file_status()`: kein Body, nur der Statuscode. Für Schleifen über viele Dateien deutlich sparsamer.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `flow_hash` | ja | FLOW-Hash, Version 0, 1 oder 2 |

```python
result = ark.has_file_status("2:d41d8cd98f00b204e9800998ecf8427e")

if result.code == 204:
    os.remove(original)                     # Ark hat eine Kopie
elif result.code == 404:
    print("keine Kopie in Ark")
elif result.code == 400:
    print("Hash ungueltig:", result.message)
else:
    raise RuntimeError(result.message)      # nicht loeschen, Antwort unklar
```

| Code | Bedeutung | `data` |
| --- | --- | --- |
| 204 | One or more matches found | `None` |
| 400 | Invalid hash | `None` |
| 404 | No matches found | `None` |

Diese Operation liefert **kein 200**. Ein Vergleich auf 200 geht hier immer schief — auf 204 prüfen. `data` ist immer `None`, HEAD hat per HTTP keinen Body.

## get_file_statuses(hash_list)

`POST /filestatus/` — Massenabfrage für viele Hashes.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `hash_list` | ja | Liste von FLOW-Hashes, Version 0, 1 oder 2 |

```python
angefragt = ["2:d41d8cd9...", "2:1b54a3f2..."]
result = ark.get_file_statuses(angefragt)

gefunden = {match["hash"] for match in result.data}
fehlt = [h for h in angefragt if h not in gefunden]
```

| Code | Bedeutung | `data` |
| --- | --- | --- |
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
| --- | --- | --- |
| 200 | Disk backup indexing status | `dict` mit `total`, `indexed`, `indexing`, `not_indexed`, `needs_indexing`, `total_files` |

Nur indexierte Disk-Backups sind über `search_backups()` auffindbar, daher vor einer Suche prüfen.

## search_backups(search_pattern, search_mode="contains", \*, backup_type=None, limit=100, offset=0)

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
print(result.data["total_matches"], "Treffer")
for hit in result.data["results"]:
    print(hit["filename"])
```

| Code | Bedeutung | `data` |
| --- | --- | --- |
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
| --- | --- | --- |
| 200 | Tape library status with complete inventory | `dict` mit `tapes` und `timestamp` |

---

## Komfort-Funktionen

Setzen auf den zehn Endpunkt-Funktionen auf und kennen keinen eigenen Endpunkt. Ihre Statuscodes sind daher die der jeweils aufgerufenen Funktion.

## restore_backup(backup_id, target, \*, ...)

Ein einzelnes Backup zurückspielen, baut den Body für `restore_backups()`.

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
print(result.code, result.data)      # 200 restorejob_sovh0C
```

`target` besteht bei Media Spaces aus drei durch je drei Bindestriche getrennten Teilen: ESA-Gruppe, Server-Group-Member und Pfad zum Bit Bucket. Bei allen anderen Space-Typen genügt die ESA-Gruppe, z. B. `esa_HiNbl`.

Codes: 200 wie `restore_backups()`.

## restore_files_by_hash(hashes, mediaspace, \*, ...)

Eine Liste von FLOW-Hashes in einen Media Space zurückspielen, baut den Body für `restore_hashes()`.

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
else:
    print(result.code, result.error, result.message)
```

Codes: 200, 400, 404 wie `restore_hashes()`.

## search_by_flow_hash(flow_hash, \*, backup_type=None, limit=100)

Den Backup-Index nach einem FLOW-Hash durchsuchen, ruft `search_backups()` im Modus `flow_hash` auf.

| Argument | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
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
| --- | --- | --- | --- |
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
| --- | --- | --- |
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
| --- | --- | --- |
| `backup_id` | ja | die Backup-ID |

```python
backup = ark.find_backup("ark.tapeserver_f541...").data
```

`data` ist der passende Eintrag oder `{}`.

Codes: 200 wie `get_backups()`.

## find_backups_by_space_name(space_name)

Alle Backups eines Media Space über den Namen finden, filtert `get_backups()`.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
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
| --- | --- | --- |
| `space_uuid` | ja | UUID des Media Space |

```python
result = ark.find_backups_by_space_uuid("6f3c1a...")
```

Codes: 200 wie `get_backups()`.

## Ark.tapes_from_file_status(file_status)

Barcodes der Tapes aus einem `filestatus`-Eintrag sammeln. Reine Auswertung, kein Request — daher `@staticmethod` und ohne `ArkResult`.

| Argument | Pflicht | Beschreibung |
| --- | --- | --- |
| `file_status` | ja | ein Eintrag aus der `data` von `get_file_status()` oder `get_file_statuses()` |

```python
for match in ark.get_file_status(flow_hash).data:
    print(Ark.tapes_from_file_status(match))     # ["001234L5"]
```

Gibt eine `list` zurück, leer bei Disk-Backups.

---

## Bekannte Fallstricke

`code == 0` mit einer Meldung über ungültiges JSON fängt einen Bug der FlowAPI ab: bricht die Verbindung nach einem erfolgreichen Request weg, lässt `core.do_request()` den alten Statuscode stehen und legt eine Klartextmeldung in den Body. `getThatReturnsObj()` schickt die durch `json.loads()` und wirft einen `JSONDecodeError`. Der Wrapper nutzt `getThatReturnsObj()` deshalb nicht.

`POST /filestatus/` braucht den abschließenden Slash. `HEAD /filestatus/{FileHash}` liefert 204, nie 200 — und 204 bedeutet dort **Treffer gefunden**, nicht "nichts da".

`POST /filestatus/` dokumentiert kein 404. Kommt trotzdem eins, meldet `message` den Code als für diesen Endpunkt undokumentiert.

Bei `restore_hashes()` und 404 ist das `details`-Feld der API ein Objekt, obwohl das Schema eine Zeichenkette vorschreibt. `message` trägt es dann als JSON — siehe [message ist immer ein String](#message-ist-immer-ein-string).

Der Ark-Port 8000 steht als Zahl in `connect()`. `FlowAPI.core` kennt dafür keine Konstante.

## Interne Funktionen

Alles mit `_` am Anfang ist intern und kann sich ohne Vorwarnung ändern: `_read_error()`, `_request()`, `_filter_backups()`.

## Exportliste

`ark/ark.py` erzeugt sein `__all__` in der letzten Zeile selbst.

```python
# --------- KEEP THIS LINE AT THE END ---------
__all__ = [
    name
    for name in dir()
    if name.startswith(("Ark", "ARK_", "create_"))
]
```

Das sind vier Namen: `Ark`, `ArkResult`, `ARK_VERSION` und `create_instance`. Der Alias mit `_` beim Import aus `core` ist Pflicht — ohne ihn fängt der Filter auf `create_` auch den core-Namen ein. Das Paket kennt keine Konstanten — Statuscodes sind Zahlen, Fehlerkennungen und Aufzählungswerte sind Zeichenketten.

**Neue öffentliche Namen müssen einen dieser Prefixe tragen**, sonst tauchen
sie im Paket nicht auf.

## Referenz

[EditShare Ark API](https://developers.editshare.com/?urls.primaryName=EditShare%20Ark)
