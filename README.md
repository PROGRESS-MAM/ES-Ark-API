# ark

Wrapper für die EditShare Ark API. Setzt auf `FlowAPI.core` auf, gleicher Stil wie `FlowAPI.metadata`.

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

## Verbinden

```python
from ark import Ark

# direkt zum Ark-Server, Port 8000
ark = Ark.create_instance("10.0.0.5", "user", "pass")

# oder über das lokale Gateway
ark = Ark.create_gateway_instance("user", "pass")
```

## Backups auflisten und zurückspielen

```python
for backup in ark.get_backups():
    print(backup["backup_id"], backup["media_space_name"], backup["date"])

backups = ark.find_backups_by_space_name("Projekt_2026")

job_id = ark.restore_backup(
    backups[0]["backup_id"],
    "esa_IBN1e---es-master---/efs/efs_1",
    rename="Projekt_2026_restored",
)
```

## Einzelne Dateien per FLOW-Hash zurückspielen

```python
session_guid = ark.restore_files_by_hash(
    ["2:d41d8cd98f00b204e9800998ecf8427e"],
    "MyMediaSpace",
    restore_path="restored/",
    prefer_source="disk",
)
```

Alle übergebenen Hashes müssen restaurierbar sein, sonst antwortet Ark mit 404 und die Methode gibt `False` zurück.

## Archivstatus prüfen

```python
if ark.is_archived("2:d41d8cd98f00b204e9800998ecf8427e"):
    print("Ark hat eine Kopie")

for match in ark.get_file_status("2:d41d8cd98f00b204e9800998ecf8427e"):
    print(match["storage_type"], match["pathname"], match["filename"])
    print(Ark.tapes_from_file_status(match))

# Massenabfrage
matches = ark.get_file_statuses(["2:d41d...", "2:1b54..."])
```

## Backups durchsuchen

```python
status = ark.get_disk_search_status()
print(status["indexed"], "von", status["total"], "Backups indexiert")

treffer = ark.search_backups("*.mov", "wildcard", backup_type="disk")
print(treffer["total_matches"])

alle = ark.search_all_backups("Interview", "contains")
```

## Tape Library

```python
for tape in ark.get_tapes():
    print(tape["barcode"], tape["in_changer"])

tape = ark.find_tape("001234L5")
```

## Version

`ARK_VERSION` in `ark/ark.py`, wird von `pyproject.toml` dynamisch gelesen.

## Referenz

[EditShare Ark API](https://developers.editshare.com/?urls.primaryName=EditShare%20Ark)
