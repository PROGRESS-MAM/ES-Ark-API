"""
Prueft die Ark-Endpunkte an einem echten Restore.

Ablauf: lesende Endpunkte abfragen, Clip ueber den Searcher finden,
Restore pruefen, nach Rueckfrage starten und den Job bis zum Ende
beobachten. Jede Antwort landet als JSON in ark_probe/<Zeitstempel>/.

    python ark_probe.py
"""

# --------- IMPORTS ---------
import json
import time
from datetime import datetime
from itertools import count
from pathlib import Path

import searcher
from toolbox import tb_link_api

# --------- CONFIG ---------
app_name = "ARK-PROBE"
app_version = "0.2"

base_path = Path(__file__).parent
cred_path = base_path / "cred.env"
out_root = base_path / "ark_probe"

clip_id = "412505"
mediaspace = "Transfer"
restore_path = "tmp Martin/"

poll_seconds = 10
watch_minutes = 60
stop_test = False    # True: stop the restore as soon as it runs

# --------- STATIC ---------
read_calls = (
    "get_backups", "get_tape_library_status", "get_tape_pools",
    "get_disk_search_status", "get_file_hash_database_status",
    "get_notifications_init", "get_notifications", "get_license_status",
    "get_destinations", "get_job_queue", "get_active_jobs",
    "get_completed_jobs", "get_inactive_jobs", "get_disk_license",
    "get_disk_backups", "get_tape_license", "get_tape_servers",
    "get_tape_server_list", "get_tape_backups", "get_tape_alerts",
    "get_media_spaces", "get_media_space_types", "get_project_spaces",
    "get_private_spaces", "get_exchange_spaces", "get_flow_sources",
    "get_ark_tape_db",
)
job_lists = ("get_job_queue", "get_active_jobs", "get_completed_jobs", "get_inactive_jobs")
run_states = ("active", "queued")


# --------- FUNC OUTPUT ---------
def shape(value, depth: int = 0) -> str:
    """Kurze Strukturbeschreibung fuer die Konsole"""
    if isinstance(value, list):
        return f"list[{len(value)}]" + (f" of {shape(value[0], depth + 1)}" if value and depth < 1 else "")
    if isinstance(value, dict):
        keys = list(value)
        return "{" + ", ".join(map(str, keys[:8])) + (", ..." if len(keys) > 8 else "") + "}"
    if isinstance(value, str):
        return f"str[{len(value)}]"
    return type(value).__name__


def make_saver(out_dir: Path):
    """Speichert jeden Datensatz nummeriert und merkt sich die Kurzfassung"""
    numbers = count(1)
    summary = []

    def save(record: dict) -> dict:
        path = out_dir / f"{next(numbers):03d}_{record['call']}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        summary.append({key: record.get(key) for key in ("call", "args", "code", "error", "message")})
        (out_dir / "000_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return record

    return save


def call(ark, save, name: str, *args, quiet: bool = False, **kwargs) -> dict:
    """Ark-Methode aufrufen, Ergebnis speichern und kurz ausgeben"""
    args_text = args + tuple(f"{key}={value!r}" for key, value in kwargs.items())
    try:
        result = getattr(ark, name)(*args, **kwargs)
        record = {"call": name, "args": args_text, "code": result.code, "error": result.error,
                  "message": result.message, "data": result.data, "raw": ark.last_response()[:20000]}
    except Exception as exc:  # keep probing the other endpoints
        record = {"call": name, "args": args_text, "code": None, "error": "", "message": f"Exception: {exc}", "data": None}
    save(record)
    if not quiet:
        ok = record["code"] is not None and 200 <= record["code"] < 300
        line = f"{record['code']!s:>4}  {name}{args_text if args_text else ''}  {shape(record['data'])}"
        print(line if ok else f"{line}  {record['message'][:120]}")
    return record


# --------- FUNC CLIP ---------
def find_clip(save) -> tuple[str, list[str]]:
    """Clip ueber den Searcher finden, liefert Clipname und Hashes"""
    searcher.link("file", cred_path, on_progress=lambda message: print(f"\r{message[:110]:<110}", end="", flush=True))
    search = {
        "name": f"Clip {clip_id}",
        "request_fields": (("clip_id", "is", clip_id),),
        "return_fields": ("clip_id", "clip_name_with_extension", "hash"),
    }
    match, progress, error = searcher.find(search)
    print()
    save({"call": "searcher_find", "args": (clip_id,), "code": None, "error": error or "",
          "message": progress, "data": match})
    if error:
        raise RuntimeError(f"Searcher: {error}")
    if not match:
        raise RuntimeError(f"Clip {clip_id} nicht gefunden")
    if len(match) > 1:
        print(f"Achtung: {len(match)} Treffer, verwende den ersten")
    _, clip_name, hash_text = match[0]
    hashes = list(dict.fromkeys(filter(None, (value.strip() for value in hash_text.split(";")))))
    if not hashes:
        raise RuntimeError(f"Clip {clip_id} hat keine Hashes")
    return clip_name, hashes


# --------- FUNC JOB ---------
def job_snapshot(ark, save, job_id: str) -> dict:
    """Job-Listen, Status, Job, Aktionen und Details mit kurzer und langer ID speichern"""
    for name in job_lists:
        call(ark, save, name, quiet=True)
    status = call(ark, save, "get_restore_job_status", job_id)
    run_id = (status["data"] or {}).get("job", {}).get("id") if isinstance(status["data"], dict) else None
    for some_id in dict.fromkeys(filter(None, (job_id, run_id))):
        job_type = str(some_id).split("_", 1)[0]
        call(ark, save, "get_job", some_id, quiet=True)
        call(ark, save, "get_job_actions", some_id, quiet=True)
        call(ark, save, "get_job_details", job_type, some_id, quiet=True)
    return status


def watch_job(ark, save, job_id: str) -> None:
    """Job beobachten, bei jeder Aenderung einen Schnappschuss speichern

    Ende bei completed, oder wenn der Job nach dem Laufen inaktiv wird
    bzw. aus den Listen verschwindet. Strg+C beendet nur die Beobachtung.
    """
    try:
        watch_loop(ark, save, job_id)
    except KeyboardInterrupt:
        print("\n      Beobachtung abgebrochen")


def watch_loop(ark, save, job_id: str) -> None:
    deadline = time.monotonic() + watch_minutes * 60
    last_seen, was_running, stopped = None, False, False
    while time.monotonic() < deadline:
        result = ark.get_restore_job_status(job_id)
        current = json.dumps(result.data, sort_keys=True, default=str)
        if current != last_seen:
            last_seen = current
            status = job_snapshot(ark, save, job_id)
            state = (status["data"] or {}).get("state", "") if isinstance(status["data"], dict) else ""
            print(f"      Zustand: {state or 'nicht gefunden'}")
        state = result.data.get("state", "") if isinstance(result.data, dict) else ""
        was_running = was_running or state in run_states
        if stop_test and state == "active" and not stopped:
            call(ark, save, "stop_restore_job", job_id)
            stopped = True
            continue
        if state == "completed" or (was_running and state not in run_states):
            return
        time.sleep(poll_seconds)
    print(f"      Beobachtung nach {watch_minutes} min beendet")


# --------- MAIN ---------
def main():
    if not cred_path.is_file():
        raise SystemExit(f"cred.env nicht gefunden: {cred_path}")
    ark = tb_link_api(cred_path, "ark")
    if ark is None:
        raise SystemExit("Keine Ark-Verbindung, cred.env pruefen")

    out_dir = out_root / datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    save = make_saver(out_dir)
    print(f"{app_name} {app_version}: Antworten nach {out_dir}")

    print("1/4 Lesende Endpunkte")
    for name in read_calls:
        call(ark, save, name)

    print(f"2/4 Clip {clip_id} suchen")
    clip_name, hashes = find_clip(save)
    print(f"      {clip_name}: {len(hashes)} Hash(es)")

    print("3/4 Restore pruefen")
    check = call(ark, save, "check_hashes_restorable", hashes)
    if check["code"] != 200:
        return
    blocked = {flow_hash: info for flow_hash, info in check["data"].items() if not info["restorable"]}
    for flow_hash, info in blocked.items():
        reason = f"Tapes offline: {', '.join(info['offline_tapes'])}" if info["in_ark"] else "nicht in Ark"
        print(f"      nicht restaurierbar: {flow_hash} ({reason})")
    if blocked:
        return

    answer = input(f"      {len(hashes)} Datei(en) von '{clip_name}' nach '{mediaspace}/{restore_path}' "
                   f"zuruecksichern{' und danach stoppen' if stop_test else ''}? [j/N] ")
    if answer.strip().casefold() != "j":
        print("      abgebrochen, kein Restore gestartet")
        return
    restore = call(ark, save, "restore_files_by_hash", hashes, mediaspace, restore_path=restore_path)
    if restore["code"] != 200:
        return
    job_id = restore["data"].get("session_guid", "")
    print(f"4/4 Job {job_id} beobachten")
    watch_job(ark, save, job_id)
    call(ark, save, "get_restore_job_errors", job_id)


# --------- EXEC ---------
if __name__ == "__main__":
    main()
