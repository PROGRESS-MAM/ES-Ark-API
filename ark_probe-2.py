"""
Prueft Queue, Abbruch und Fehlerquellen an mehreren echten Restores.

Ablauf: Clips ueber den Searcher finden, Restores pruefen, ohne Rueckfrage
alle starten, die Queue mehrmals lesen, einen Lauf stoppen und alle
moeglichen Fehlerquellen dieses Laufs abfragen. Die uebrigen Laeufe bleiben
unberuehrt. Jede Antwort landet als JSON in ark_probe/<Zeitstempel>/.

    python ark_probe.py
"""

# --------- IMPORTS ---------
import json
import sys
import time
from datetime import datetime
from itertools import count
from pathlib import Path

import searcher
from toolbox import tb_link_api

# --------- CONFIG ---------
app_name = "ARK-PROBE"
app_version = "0.3"

base_path = Path(__file__).parent
cred_path = base_path / "cred.env"
out_root = base_path / "ark_probe"

clip_ids = ("412505", "621226", "413008", "412831")
stop_clip_id = "412831"
mediaspace = "Transfer"
restore_path = "tmp Martin/"

poll_seconds = 10
start_wait_seconds = 60
queue_reads = 3
stop_wait_minutes = 5

# --------- STATIC ---------
detail_types = ("__restorejob__", "restorejob", "completed", "active", "session")
tape_log_limit = 3


# --------- FUNC OUTPUT ---------
class Tee:
    """Konsolenausgabe zusaetzlich in eine Datei schreiben"""

    def __init__(self, stream, path: Path):
        self.stream, self.file = stream, path.open("a", encoding="utf-8")

    def write(self, text: str) -> int:
        self.file.write(text)
        self.file.flush()
        return self.stream.write(text)

    def flush(self) -> None:
        self.stream.flush()


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
                  "message": result.message, "data": result.data, "raw": ark.last_response()[:200000]}
    except Exception as exc:  # keep probing the other endpoints
        record = {"call": name, "args": args_text, "code": None, "error": "", "message": f"Exception: {exc}", "data": None}
    save(record)
    if not quiet:
        ok = record["code"] is not None and 200 <= record["code"] < 300
        line = f"{record['code']!s:>4}  {name}{args_text if args_text else ''}  {shape(record['data'])}"
        print(line if ok else f"{line}  {record['message'][:120]}")
    return record


# --------- FUNC CLIPS ---------
def find_clips(save) -> dict[str, tuple[str, list[str]]]:
    """Alle Clips in einer Suche finden, liefert je Clip-ID Clipname und Hashes"""
    searcher.link("file", cred_path, on_progress=lambda message: print(f"\r{message[:110]:<110}", end="", flush=True))
    request_fields = []
    for clip_id in clip_ids:
        request_fields += ["or", ("clip_id", "is", clip_id)]
    search = {
        "name": "Clips " + ", ".join(clip_ids),
        "request_fields": tuple(request_fields[1:]),
        "return_fields": ("clip_id", "clip_name_with_extension", "hash"),
    }
    match, progress, error = searcher.find(search)
    print()
    save({"call": "searcher_find", "args": clip_ids, "code": None, "error": error or "", "message": progress, "data": match})
    if error:
        raise RuntimeError(f"Searcher: {error}")
    clips = {}
    for found_id, clip_name, hash_text in match or ():
        hashes = list(dict.fromkeys(filter(None, (value.strip() for value in str(hash_text).split(";")))))
        clips.setdefault(str(found_id), (clip_name, hashes))
    for clip_id in clip_ids:
        if clip_id not in clips:
            print(f"      {clip_id}: nicht gefunden")
        elif not clips[clip_id][1]:
            print(f"      {clip_id}: keine Hashes")
    return {clip_id: clips[clip_id] for clip_id in clip_ids if clips.get(clip_id, (None, []))[1]}


def restorable_clips(ark, save, clips: dict) -> dict[str, tuple[str, str]]:
    """Je Clip den ersten restaurierbaren Hash waehlen, liefert Clipname und Hash"""
    usable = {}
    for clip_id, (clip_name, hashes) in clips.items():
        check = call(ark, save, "check_hashes_restorable", hashes, quiet=True)
        if check["code"] != 200:
            print(f"      {clip_id}: Pruefung fehlgeschlagen ({check['code']}) {check['message'][:100]}")
            continue
        ok_hashes = [flow_hash for flow_hash in hashes if check["data"].get(flow_hash, {}).get("restorable")]
        print(f"      {clip_id}: {clip_name}, {len(hashes)} Datei(en), {len(ok_hashes)} restaurierbar"
              + (f", verwende {ok_hashes[0]}" if ok_hashes else ""))
        if ok_hashes:
            usable[clip_id] = (clip_name, ok_hashes[0])
    return usable


# --------- FUNC QUEUE ---------
def short_id(run_id: str) -> str:
    """Job-ID vor -__restorejob__---, mit ihr verweisen Benachrichtigungen auf den Lauf"""
    return run_id.split("-__", 1)[0]


def find_run(queue: dict, run_id: str) -> tuple[str, dict]:
    """Lauf in der Antwort von get_job_queue() finden, liefert Liste und Eintrag"""
    for entry in queue.get("active_jobs", ()):
        if entry.get("id") == run_id:
            return "active", entry
    for job in queue.get("completed_jobs", ()):
        for session in job.get("sessions", ()):
            if session.get("id") == run_id:
                return "completed", session
    for entry in queue.get("inactive_jobs", ()):
        if entry.get("id") in (run_id, short_id(run_id)):
            return "inactive", entry
    return "", {}


def read_queue(ark, save, runs: dict) -> dict:
    """Queue lesen und den Stand jedes eigenen Laufs ausgeben"""
    queue = call(ark, save, "get_job_queue", quiet=True)["data"]
    queue = queue if isinstance(queue, dict) else {}
    active = queue.get("active_jobs", ())
    states = [str(entry.get("current_status", "")).split(":", 1)[0] for entry in active]
    print(f"      active_jobs: {len(active)} ({', '.join(f'{states.count(s)}x {s}' for s in dict.fromkeys(states)) or 'leer'})")
    for clip_id, run_id in runs.items():
        list_name, entry = find_run(queue, run_id)
        text = entry.get("current_status") or entry.get("status") or ""
        print(f"      {clip_id}: {list_name or 'nicht gefunden'} {text} {entry.get('progress_txt', '')}".rstrip())
    return queue


def wait_until_listed(ark, save, run_id: str) -> str:
    """Queue lesen, bis der neue Lauf erscheint, liefert die Liste oder einen leeren Text"""
    deadline = time.monotonic() + start_wait_seconds
    while True:
        queue = call(ark, save, "get_job_queue", quiet=True)["data"]
        list_name, _ = find_run(queue if isinstance(queue, dict) else {}, run_id)
        if list_name or time.monotonic() >= deadline:
            return list_name
        time.sleep(2)


def start_jobs(ark, save, clips: dict) -> dict[str, str]:
    """Je Clip einen eigenen Job mit einer Datei starten, liefert Clip-ID und Lauf-ID

    Der naechste Job startet erst, wenn der vorige in der Queue steht, damit
    Ark die Auftraege nicht zusammenfasst.
    """
    runs = {}
    for clip_id, (_, flow_hash) in clips.items():
        restore = call(ark, save, "restore_files_by_hash", [flow_hash], mediaspace, restore_path=restore_path)
        run_id = (restore["data"] or {}).get("session_guid", "") if restore["code"] == 200 else ""
        if not run_id:
            continue
        if run_id in runs.values():
            print(f"      Achtung: {clip_id} hat dieselbe Lauf-ID wie ein vorheriger Job, Ark hat zusammengefasst")
        runs[clip_id] = run_id
        list_name = wait_until_listed(ark, save, run_id)
        print(f"      {clip_id}: {run_id} ({list_name or f'nach {start_wait_seconds} s nicht in der Queue'})")
    return runs


# --------- FUNC STOP ---------
def wait_until_stopped(ark, save, runs: dict, run_id: str) -> str:
    """Queue lesen, bis der Lauf nicht mehr aktiv ist, liefert die Liste oder active"""
    deadline = time.monotonic() + stop_wait_minutes * 60
    while time.monotonic() < deadline:
        time.sleep(poll_seconds)
        list_name, _ = find_run(read_queue(ark, save, runs), run_id)
        if list_name != "active":
            return list_name
    return "active"


def stop_run(ark, save, runs: dict, run_id: str) -> None:
    """Erst mit der langen, sonst mit der kurzen ID stoppen"""
    for some_id in (run_id, short_id(run_id)):
        code = call(ark, save, "stop_job", some_id)["code"]
        if code is None or not 200 <= code < 300:
            continue
        list_name = wait_until_stopped(ark, save, runs, run_id)
        if list_name != "active":
            print(f"      gestoppt mit {some_id}, jetzt: {list_name or 'nicht gefunden'}")
            return
        print(f"      nach {stop_wait_minutes} min noch aktiv")


# --------- FUNC ERRORS ---------
def collect_ids(payload, needle: str) -> list[str]:
    """IDs aus beliebig verschachtelten Eintraegen sammeln, Treffer mit needle zuerst"""
    hits, others = [], []

    def walk(value):
        if isinstance(value, dict):
            entry_id = value.get("id") or value.get("job_id")
            if entry_id:
                (hits if needle in json.dumps(value, default=str) else others).append(str(entry_id))
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return list(dict.fromkeys(hits or others[:tape_log_limit]))


def read_errors(ark, save, run_id: str, last_notification: int) -> None:
    """Alle denkbaren Fehlerquellen des gestoppten Laufs abfragen"""
    job_id = short_id(run_id)
    notes = call(ark, save, "get_notifications")["data"]
    new_notes = [note for note in (notes or {}).get("notifications", ()) if note.get("id", 0) > last_notification]
    print(f"      {len(new_notes)} neue Benachrichtigung(en) seit dem Start")
    for note in new_notes:
        if job_id in json.dumps(note, default=str) or note.get("severity") != "__info__":
            print(f"        {note.get('severity')} {note.get('tag')}: {note.get('msg', '')[:110]}")

    for some_id in (run_id, job_id):
        for job_type in detail_types:
            call(ark, save, "get_job_details", job_type, some_id)
        for page in (0, 1):
            call(ark, save, "get_session_files", some_id, page)
        call(ark, save, "get_backup_contents", some_id)

    servers = call(ark, save, "get_tape_servers")["data"]
    for server in servers if isinstance(servers, list) else ():
        server_id = server.get("id", "")
        call(ark, save, "get_tape_alerts", server_id)
        tape_jobs = call(ark, save, "get_tape_jobs", server_id)["data"]
        for tape_job_id in collect_ids(tape_jobs, job_id):
            call(ark, save, "get_tape_job_log", server_id, tape_job_id)


def last_notification_id(ark, save) -> int:
    """Hoechste Benachrichtigungs-ID vor dem Start, um neue zu erkennen"""
    notes = call(ark, save, "get_notifications", quiet=True)["data"]
    return max((note.get("id", 0) for note in (notes or {}).get("notifications", ())), default=0)


# --------- MAIN ---------
def main():
    if not cred_path.is_file():
        raise SystemExit(f"cred.env nicht gefunden: {cred_path}")
    if stop_clip_id not in clip_ids:
        raise SystemExit(f"stop_clip_id {stop_clip_id} steht nicht in clip_ids")
    ark = tb_link_api(cred_path, "ark")
    if ark is None:
        raise SystemExit("Keine Ark-Verbindung, cred.env pruefen")

    out_dir = out_root / datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    save = make_saver(out_dir)
    sys.stdout = Tee(sys.stdout, out_dir / "console.txt")
    print(f"{app_name} {app_version}: Antworten nach {out_dir}")

    print(f"1/5 Clips {', '.join(clip_ids)} suchen")
    clips = restorable_clips(ark, save, find_clips(save))
    if stop_clip_id not in clips:
        print(f"      {stop_clip_id} ist nicht restaurierbar, Abbruchtest nicht moeglich")
        return

    print("2/5 Restores starten")
    print(f"      {len(clips)} Job(s) mit je 1 Datei nach '{mediaspace}/{restore_path}', {stop_clip_id} wird danach gestoppt")
    last_notification = last_notification_id(ark, save)
    call(ark, save, "get_job_queue", quiet=True)
    runs = start_jobs(ark, save, clips)
    if stop_clip_id not in runs:
        print(f"      {stop_clip_id} wurde nicht gestartet, Abbruchtest nicht moeglich")
        return

    print("3/5 Queue lesen")
    for number in range(queue_reads):
        if number:
            time.sleep(poll_seconds)
        read_queue(ark, save, runs)

    print(f"4/5 {stop_clip_id} stoppen")
    stop_run(ark, save, runs, runs[stop_clip_id])

    print(f"5/5 Fehlerquellen von {stop_clip_id} lesen")
    read_errors(ark, save, runs[stop_clip_id], last_notification)
    read_queue(ark, save, runs)
    print("      Laeufe, die weiterlaufen:")
    for clip_id, run_id in runs.items():
        if clip_id != stop_clip_id:
            print(f"        {clip_id}: {run_id}")


# --------- EXEC ---------
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProbe abgebrochen, gestartete Restores laufen weiter")
