"""
Liest alle lesenden Ark-Endpunkte einmal ab und speichert die Antworten.

Nur lesende Aufrufe: es wird nichts gestartet, gestoppt, angelegt,
geaendert oder geloescht.

    python ark_probe.py --env .env
    python ark_probe.py --env .env --job-id restorejob_80XIRz
    python ark_probe.py --env .env --server-id ark.tapeserver_... --tape-job-id 123
    python ark_probe.py --env .env --backup-id ark.tapeserver_... --pool-id poolid-1-...
    python ark_probe.py --env .env --events
"""

# --------- IMPORTS ---------
import argparse
import json
from datetime import datetime
from pathlib import Path

from toolbox import tb_link_api

# --------- CONFIG ---------
app_name = "ARK-PROBE"
app_version = "0.1"
default_out_dir = Path(__file__).parent / "ark_probe"

# --------- FUNC ---------
always = (
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", type=Path, required=True, help=".env mit ARK_USER, ARK_PASSWORD, ARK_HOST")
    parser.add_argument("--out", type=Path, default=default_out_dir, help="Zielordner fuer die Antworten")
    parser.add_argument("--job-id", help="Restore-Job, z. B. restorejob_80XIRz")
    parser.add_argument("--job-type", help="Job-Typ fuer /job/details, Standard: Teil der ID vor dem ersten _")
    parser.add_argument("--backup-id", help="Backup fuer /backup/...")
    parser.add_argument("--server-id", help="Tape-Server fuer /tape/jobs und /tape/alerts")
    parser.add_argument("--tape-job-id", help="Tape-Job fuer /tape/log, braucht --server-id")
    parser.add_argument("--pool-id", help="Tape-Pool fuer /tape/pool/...")
    parser.add_argument("--events", action="store_true", help="/events/0 abfragen, wartet bis zu 50 s")
    args = parser.parse_args()
    if not args.env.is_file():
        parser.error(f"--env: Datei nicht gefunden: {args.env}")
    if args.tape_job_id and not args.server_id:
        parser.error("--tape-job-id braucht --server-id")
    return args


def planned_calls(ark, args: argparse.Namespace) -> list[tuple[str, tuple]]:
    """Alle lesenden Aufrufe als (Methode, Argumente)"""
    calls = [(name, ()) for name in always]
    if args.job_id:
        status = ark.get_restore_job_status(args.job_id)
        run_id = status.data.get("job", {}).get("id") if isinstance(status.data, dict) else None
        job_ids = list(dict.fromkeys(filter(None, (args.job_id, run_id))))
        calls += [("get_restore_job_status", (args.job_id,))]
        for job_id in job_ids:
            job_type = args.job_type or str(job_id).split("_", 1)[0]
            calls += [("get_job", (job_id,)), ("get_job_actions", (job_id,)), ("get_job_details", (job_type, job_id))]
        calls += [("get_restore_job_errors", (args.job_id, args.job_type))]
    if args.backup_id:
        calls += [
            ("get_backup_contents", (args.backup_id,)),
            ("get_backup_contents", (args.backup_id, 1)),
            ("get_json_backup_contents", (args.backup_id,)),
            ("get_session_files", (args.backup_id, 1)),
        ]
    if args.server_id:
        calls += [("get_tape_jobs", (args.server_id,)), ("get_tape_alerts", (args.server_id,))]
    if args.tape_job_id:
        calls += [("get_tape_job_log", (args.server_id, args.tape_job_id))]
    if args.pool_id:
        calls += [
            ("get_tape_pool", (args.pool_id,)),
            ("get_pool_tapes", (args.pool_id,)),
            ("get_assigned_tapes", (args.pool_id,)),
            ("get_unassigned_tapes", (args.pool_id,)),
            ("get_pool_contents", (args.pool_id, 1)),
        ]
    if args.events:
        calls += [("wait_for_events", (0,))]
    return calls


def shape(value, depth: int = 0) -> str:
    """Kurze Strukturbeschreibung fuer die Konsole"""
    if isinstance(value, list):
        return f"list[{len(value)}]" + (f" of {shape(value[0], depth + 1)}" if value and depth < 1 else "")
    if isinstance(value, dict):
        keys = list(value)
        return "{" + ", ".join(keys[:8]) + (", ..." if len(keys) > 8 else "") + "}"
    if isinstance(value, str):
        return f"str[{len(value)}]"
    return type(value).__name__


def run_call(ark, name: str, call_args: tuple) -> dict:
    try:
        result = getattr(ark, name)(*call_args)
    except Exception as exc:  # keep probing the other endpoints
        return {"call": name, "args": call_args, "code": None, "message": f"Exception: {exc}"}
    return {
        "call": name, "args": call_args, "code": result.code, "error": result.error,
        "message": result.message, "data": result.data, "raw": ark.last_response()[:20000],
    }


def save(out_dir: Path, index: int, record: dict) -> Path:
    path = out_dir / f"{index:02d}_{record['call']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


# --------- MAIN ---------
def main():
    args = parse_args()
    ark = tb_link_api(args.env, "ark")
    if ark is None:
        raise SystemExit("Keine Ark-Verbindung, .env pruefen")

    out_dir = args.out / datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{app_name} {app_version}: Antworten nach {out_dir}")

    summary = []
    for index, (name, call_args) in enumerate(planned_calls(ark, args), 1):
        record = run_call(ark, name, call_args)
        save(out_dir, index, record)
        line = f"{record['code']!s:>4}  {name}{call_args if call_args else ''}  {shape(record.get('data'))}"
        print(line if record["code"] and 200 <= record["code"] < 300 else f"{line}  {record['message'][:120]}")
        summary.append({key: record.get(key) for key in ("call", "args", "code", "error", "message")})

    (out_dir / "00_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


# --------- EXEC ---------
if __name__ == "__main__":
    main()
