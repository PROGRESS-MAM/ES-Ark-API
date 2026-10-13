"""
Wrapper fuer die EditShare Ark API.

Spezifikation:
https://developers.editshare.com/?urls.primaryName=EditShare%20Ark
"""

# --------- IMPORTS ---------

import re
import time

from .core import ArkResult, Progress
from .official import OfficialMixin
from .unofficial import UnofficialMixin

# --------- STATIC ---------

ARK_VERSION = "0.3.0"
__version__ = ARK_VERSION

_ARK_PORT = 8000
_HASH_FORMAT = re.compile(r"(1:|2:|)[A-Fa-f0-9]{32}")
_STOP_POLL_SECONDS = 2
# progress label, timeout error and timeout text of _poll_job(), by stop
_POLL_TEXTS = {
    False: ("Warte auf", "WAIT_TIMEOUT", "nicht abgeschlossen"),
    True: ("Warte auf Stopp von", "STOP_TIMEOUT", "noch aktiv"),
}


# --------- CLASS ---------
class Ark(UnofficialMixin, OfficialMixin):
    """Einstiegspunkt fuer alle Ark-Funktionen

    Offizielle Endpunkte stehen in OfficialMixin (official.py), die der
    WebUI in UnofficialMixin (unofficial.py). Hier liegen die
    zusammengesetzten Funktionen check_restore, restore_files,
    get_tape_location, find_job, wait_for_job und stop_job. Die
    Uebersicht aller Funktionen steht in der README.
    """

    # --------- CONNECTION ---------

    @staticmethod
    def create_instance(username: str, password: str, ip_addr: str) -> "Ark":
        """Verbundene Ark-Instanz erzeugen, HTTPS auf Port 8000

        Ruft die TOOLBOX ueber tb_link_api(cred_path, "ark") auf.

        Parameters
        ----------
        username : str
            Benutzername fuer BasicAuth (Pflicht)
        password : str
            Passwort fuer BasicAuth (Pflicht)
        ip_addr : str
            IP oder Hostname des Ark-Servers (Pflicht)

        Returns
        -------
        Ark
            Verbundene Instanz
        """

        ark = Ark()
        ark.connect2(ip_addr, _ARK_PORT, username, password)
        return ark

    # --------- RESTORE ---------

    def check_restore(self, hashes: str | list[str]) -> ArkResult:
        """Pruefen, ob ein Restore logisch und physisch moeglich ist

        Logisch: Ark haelt eine Kopie (get_file_status()). Physisch: alle
        Tapes einer Kopie liegen im Autochanger (get_tape_location()).
        Hashes mit ungueltigem Format werden vor der Anfrage aussortiert,
        die uebrigen trotzdem geprueft.

        Parameters
        ----------
        hashes : str | list
            Ein FLOW-Hash oder eine Liste (Pflicht), Version 0, 1 oder 2

        Returns
        -------
        ArkResult
            data ist {"restorable": bool, "files": {...}}. restorable ist
            True, wenn alle Dateien jetzt restaurierbar sind. files je Hash:

                in_ark          bool, Ark haelt mindestens eine Kopie
                copies          list, Barcodes je Kopie
                tapes_offline   list, benoetigte Tapes ausserhalb des
                                Autochangers, leer wenn restaurierbar
                restorable      bool, eine Kopie mit allen Tapes im
                                Autochanger, eine Kopie ohne Tapes zaehlt
                                ebenfalls
                reason          "", INVALID_HASH, NOT_IN_ARK oder
                                TAPES_OFFLINE

            Scheitert eine Anfrage, deren Ergebnis mit
            {"restorable": False, "files": {}}

        Notes
        -----
        Codes: 200, sonst die der gescheiterten Anfrage
        """

        wanted = self._as_list(hashes, "hashes")
        valid = [flow_hash for flow_hash in wanted if _HASH_FORMAT.fullmatch(flow_hash)]
        status = ArkResult(200, data={})
        if valid:
            status = self.get_file_status(valid)
            if status.code != 200:
                status.data = {"restorable": False, "files": {}}
                return status

        needed = list(
            dict.fromkeys(
                barcode
                for info in status.data.values()
                for copy in info["copies"]
                for barcode in copy
            )
        )
        online = set()
        if needed:
            location = self.get_tape_location(needed)
            if location.code != 200:
                location.data = {"restorable": False, "files": {}}
                return location
            online = {barcode for barcode, place in location.data.items() if place["in_changer"]}

        files = {
            flow_hash: self._restore_check(status.data.get(flow_hash), online)
            for flow_hash in wanted
        }
        count = sum(info["restorable"] for info in files.values())
        return ArkResult(
            200,
            data={"restorable": count == len(files), "files": files},
            message="{} von {} Dateien restaurierbar".format(count, len(files)),
        )

    @staticmethod
    def _restore_check(info, online):
        """Eintrag von check_restore() aus get_file_status() und Tapes im Changer

        info ist None, wenn der Hash wegen seines Formats nicht angefragt
        wurde.
        """

        if info is None:
            return {
                "in_ark": False,
                "copies": [],
                "tapes_offline": [],
                "restorable": False,
                "reason": "INVALID_HASH",
            }

        copies = info["copies"]
        restorable = any(all(barcode in online for barcode in copy) for copy in copies)
        offline = [] if restorable else list(
            dict.fromkeys(b for copy in copies for b in copy if b not in online)
        )
        reason = "" if restorable else "TAPES_OFFLINE" if info["in_ark"] else "NOT_IN_ARK"
        return {
            "in_ark": info["in_ark"],
            "copies": copies,
            "tapes_offline": offline,
            "restorable": restorable,
            "reason": reason,
        }

    def restore_files(
        self,
        hashes: str | dict | list,
        mediaspace: str,
        *,
        restore_path: str = "/",
        require_all: bool = False,
        space_uuid: str | None = None,
        ark_sources: list[str] | None = None,
        prefer_source: str | None = None,
        on_progress: Progress = print,
        progress_seconds: float = 30,
    ) -> ArkResult:
        """Dateien anhand ihrer Hashes in einen Media Space zurueckspielen

        POST /restore/hashes

        Prueft vorab mit check_restore(). Standard ist best effort: nicht
        restaurierbare Dateien werden uebersprungen, alle uebrigen kommen
        in einen Job. Mit require_all=True wird kein Job angelegt, sobald
        eine Datei nicht restaurierbar ist.

        Ark antwortet je nach Auslastung erst nach mehreren Minuten. Bis
        dahin ist der Caller blockiert und erhaelt alle progress_seconds
        "Warte auf Session-ID seit m:ss min". Bricht er in dieser Zeit ab
        (Strg+C), kann Ark den Restore trotzdem anlegen.

        Parameters
        ----------
        hashes : str | dict | list
            FLOW-Hashes oder Dicts {"flow_hash": ..., "restore_path": ...}
            fuer eigene Pfade je Datei (Pflicht)
        mediaspace : str
            Name des Ziel-Media-Space (Pflicht)
        restore_path : str
            Ordner im Media Space, wird angelegt falls nicht vorhanden,
            Standard "/"
        require_all : bool
            True: nur restaurieren, wenn alle Dateien restaurierbar sind
        space_uuid : str
            Optional. UUID des Ziel-Media-Space
        ark_sources : list
            Optional. Quellen, z. B. ["tape"]
        prefer_source : str
            Optional. Bevorzugte Quelle, z. B. "tape"
        on_progress : callable
            Meldung, solange auf die Session-ID gewartet wird, Standard
            print, None = stumm
        progress_seconds : float
            Abstand der Meldungen, Standard 30

        Returns
        -------
        ArkResult
            data ist immer, auch bei 404:

                session_id   str, lange Session-ID, None ohne Job
                restored     list, Hashes im Job
                skipped      dict, je uebersprungenem Hash reason und
                             tapes_offline, siehe check_restore()

        Notes
        -----
        Codes: 200 (Job angelegt, skipped kann Eintraege haben), 400
        INVALID_DESTINATION, INVALID_SOURCE, MISSING_REQUIRED_FIELD, 404
        HASHES_NOT_RESTORABLE (kein Job angelegt)
        """

        if not mediaspace:
            raise ValueError("mediaspace fehlt, Name des Ziel-Media-Space noetig")
        self._seconds("progress_seconds", progress_seconds)
        files = self._restore_list(hashes, restore_path)
        check = self.check_restore([entry["flow_hash"] for entry in files])
        if check.code != 200:
            check.data = self._restore_data(None, [], {})
            return check

        skipped = {
            flow_hash: {"reason": info["reason"], "tapes_offline": info["tapes_offline"]}
            for flow_hash, info in check.data["files"].items()
            if not info["restorable"]
        }
        files = [entry for entry in files if entry["flow_hash"] not in skipped]
        if not files or (require_all and skipped):
            return ArkResult(
                404,
                data=self._restore_data(None, [], skipped),
                error="HASHES_NOT_RESTORABLE",
                message="{} von {} Dateien nicht restaurierbar, kein Job angelegt".format(
                    len(skipped), len(check.data["files"])
                ),
            )

        body = {"files": files, "destination": {"mediaspace": mediaspace}}
        if space_uuid:
            body["destination"]["space_uuid"] = str(space_uuid)
        body["source"] = {
            key: value
            for key, value in (("ark_sources", ark_sources), ("prefer_source", prefer_source))
            if value
        }
        if not body["source"]:
            del body["source"]

        result = self._in_background(
            lambda: self._restore_hashes(body),
            "Warte auf Session-ID",
            on_progress,
            progress_seconds,
        )
        if result.code == 200 and isinstance(result.data, dict):
            result.data = self._restore_data(result.data.get("session_guid"), files, skipped)
        else:
            result.data = self._restore_data(None, [], skipped)
        return result

    @staticmethod
    def _restore_data(session_id, files, skipped):
        """data von restore_files(), restored ohne doppelte Hashes"""

        return {
            "session_id": session_id,
            "restored": list(dict.fromkeys(entry["flow_hash"] for entry in files)),
            "skipped": skipped,
        }

    @staticmethod
    def _restore_list(hashes, restore_path):
        """hashes als Liste von {"flow_hash", "restore_path"} fuer den Body"""

        entries = [hashes] if isinstance(hashes, (str, dict)) else list(hashes or [])
        if not entries:
            raise ValueError("hashes ist leer, mindestens ein Hash noetig")

        files = []
        for entry in entries:
            item = entry if isinstance(entry, dict) else {"flow_hash": entry}
            if not item.get("flow_hash"):
                raise ValueError("Eintrag ohne flow_hash: {!r}".format(entry))
            files.append(
                {
                    "flow_hash": str(item["flow_hash"]),
                    "restore_path": str(item.get("restore_path") or restore_path),
                }
            )
        return files

    # --------- TAPES ---------

    def get_tape_location(self, barcodes: str | list[str]) -> ArkResult:
        """Je Barcode holen, ob das Tape im Autochanger liegt

        GET /api/tape/library/tapes, ueber get_tape_library_status()

        Parameters
        ----------
        barcodes : str | list
            Ein Barcode oder eine Liste (Pflicht)

        Returns
        -------
        ArkResult
            data ist ein dict je Barcode mit known (Ark kennt das Tape),
            in_changer (liegt im Autochanger) und slot (Slot oder None),
            sonst ein leeres dict

        Notes
        -----
        Codes wie get_tape_library_status()
        """

        wanted = self._as_list(barcodes, "barcodes")
        result = self.get_tape_library_status()
        if result.code != 200:
            result.data = {}
            return result

        library = result.data.get("tapes") if isinstance(result.data, dict) else None
        tapes = {
            str(tape.get("barcode", "")).casefold(): tape
            for tape in library or []
            if isinstance(tape, dict)
        }
        result.data = {
            barcode: self._location(tapes.get(barcode.casefold())) for barcode in wanted
        }
        return result

    @staticmethod
    def _location(tape):
        """known, in_changer und slot eines Tapes aus dem Inventar"""

        in_changer = bool(tape and tape.get("in_changer"))
        return {
            "known": tape is not None,
            "in_changer": in_changer,
            "slot": tape.get("slot") if in_changer else None,
        }

    # --------- JOBS ---------

    def find_job(self, session_id: str) -> ArkResult:
        """Einen Lauf in der Queue finden

        GET /job/queue, ueber get_jobs_queue()

        Sucht in active_jobs, in den sessions der completed_jobs und in
        inactive_jobs, dort auch nach der kurzen ID vor "-__".

        Parameters
        ----------
        session_id : str
            Lange Session-ID (Pflicht), z. B.
            "restorejob_jURjob-__restorejob__---2026-10-12-14-34-2-762674"

        Returns
        -------
        ArkResult
            data ist {"list": "active" | "completed" | "inactive",
            "entry": {...}}, sonst ein leeres dict. entry bei active u. a.
            current_status, progress_txt, progress_num, current_name und
            current_speed, bei completed status, id, creation_time,
            has_filelist und name

        Notes
        -----
        Codes: 200, 404 JOB_NOT_FOUND, sonst die von get_jobs_queue()
        """

        result = self.get_jobs_queue()
        if not 200 <= result.code < 300:
            result.data = {}
            return result

        queue = result.data if isinstance(result.data, dict) else {}
        sessions = [
            session
            for job in queue.get("completed_jobs") or []
            if isinstance(job, dict)
            for session in job.get("sessions") or []
        ]
        lists = (
            ("active", queue.get("active_jobs"), (session_id,)),
            ("completed", sessions, (session_id,)),
            ("inactive", queue.get("inactive_jobs"), (session_id, self._short_id(session_id))),
        )
        for name, entries, ids in lists:
            for entry in entries or []:
                if isinstance(entry, dict) and entry.get("id") in ids:
                    return ArkResult(200, data={"list": name, "entry": entry})

        return ArkResult(
            404,
            data={},
            error="JOB_NOT_FOUND",
            message="{} ist weder aktiv noch abgeschlossen noch inaktiv".format(session_id),
        )

    def wait_for_job(
        self,
        session_id: str,
        *,
        timeout: float | None = None,
        poll_seconds: float = 10,
        on_progress: Progress = print,
        progress_seconds: float = 30,
    ) -> ArkResult:
        """Warten, bis ein Lauf abgeschlossen ist

        Fragt alle poll_seconds find_job() ab, bis der Lauf unter den
        abgeschlossenen steht. Meldet alle progress_seconds "Warte auf
        <kurze ID> seit m:ss min: <Status>".

        Parameters
        ----------
        session_id : str
            Lange Session-ID (Pflicht)
        timeout : float
            Sekunden, Standard None = unbegrenzt
        poll_seconds : float
            Abstand der Abfragen, Standard 10
        on_progress : callable
            Meldung mit aktuellem Status und Fortschritt, Standard print,
            None = stumm
        progress_seconds : float
            Abstand der Meldungen, Standard 30

        Returns
        -------
        ArkResult
            data ist das Ergebnis von find_job() fuer den abgeschlossenen
            Lauf, sonst ein leeres dict

        Notes
        -----
        Codes: 200, 404 JOB_NOT_FOUND, 408 WAIT_TIMEOUT
        """

        if timeout is not None:
            self._seconds("timeout", timeout, allow_zero=True)
        self._seconds("poll_seconds", poll_seconds)
        self._seconds("progress_seconds", progress_seconds)
        return self._poll_job(
            session_id,
            stop=False,
            timeout=timeout,
            poll_seconds=poll_seconds,
            on_progress=on_progress,
            progress_seconds=progress_seconds,
        )

    def stop_job(
        self,
        session_id: str,
        *,
        timeout: float = 60,
        on_progress: Progress = print,
        progress_seconds: float = 30,
    ) -> ArkResult:
        """Einen Lauf stoppen und bestaetigen, dass er nicht mehr aktiv ist

        POST /job/stop/{id} - inofficial

        Prueft erst mit find_job(): Ist der Lauf unbekannt oder nicht
        aktiv, wird nichts gesendet. Sonst wird gestoppt und alle 2 s
        geprueft, bis er nicht mehr aktiv ist. Getestet mit einem
        wartenden Lauf.

        Parameters
        ----------
        session_id : str
            Lange Session-ID (Pflicht)
        timeout : float
            Sekunden, Standard 60. 0 stoppt ohne zu warten und liefert den
            Stand direkt danach
        on_progress : callable
            Meldung mit aktuellem Status, Standard print, None = stumm
        progress_seconds : float
            Abstand der Meldungen, Standard 30

        Returns
        -------
        ArkResult
            data ist das Ergebnis von find_job() fuer den gestoppten Lauf,
            status in der Regel Cancelled, sonst ein leeres dict

        Notes
        -----
        Codes: 200, 404 JOB_NOT_FOUND, 408 STOP_TIMEOUT, sonst der Code
        von Ark
        """

        self._seconds("timeout", timeout, allow_zero=True)
        self._seconds("progress_seconds", progress_seconds)
        found = self.find_job(session_id)
        if found.code != 200 or found.data["list"] != "active":
            return found

        stop = self._stop_job(session_id)
        if not 200 <= stop.code < 300:
            stop.data = {}
            return stop
        if timeout == 0:
            return self.find_job(session_id)

        return self._poll_job(
            session_id,
            stop=True,
            timeout=timeout,
            poll_seconds=_STOP_POLL_SECONDS,
            on_progress=on_progress,
            progress_seconds=progress_seconds,
        )

    def _poll_job(
        self, session_id, *, stop, timeout, poll_seconds, on_progress, progress_seconds
    ):
        """find_job() abfragen, bis der Lauf abgeschlossen (stop=False) bzw.
        nicht mehr aktiv (stop=True) ist oder timeout ablaeuft"""

        label, error, timeout_text = _POLL_TEXTS[stop]
        started = time.monotonic()
        next_report = progress_seconds
        while True:
            found = self.find_job(session_id)
            if found.code != 200 or self._job_done(found.data, stop):
                return found

            elapsed = time.monotonic() - started
            if timeout is not None and elapsed >= timeout:
                return ArkResult(
                    408,
                    data={},
                    error=error,
                    message="{} nach {} s {}, zuletzt: {}".format(
                        self._short_id(session_id),
                        timeout,
                        timeout_text,
                        self._job_status(found.data),
                    ),
                )
            if elapsed >= next_report:
                self._report(
                    on_progress,
                    "{} {} seit {}: {}".format(
                        label,
                        self._short_id(session_id),
                        self._minutes(elapsed),
                        self._job_status(found.data),
                    ),
                )
                next_report += progress_seconds
            time.sleep(poll_seconds if timeout is None else min(poll_seconds, timeout - elapsed))

    @staticmethod
    def _job_done(found, stop):
        """Abgeschlossen (stop=False) bzw. nicht mehr aktiv (stop=True)"""

        return found["list"] != "active" if stop else found["list"] == "completed"

    @staticmethod
    def _job_status(found):
        """Status eines find_job()-Ergebnisses als kurzer Text"""

        entry = found.get("entry") or {}
        if found.get("list") == "inactive":
            return "inaktiv"
        if found.get("list") == "completed":
            return str(entry.get("status", ""))
        return ", ".join(
            str(entry[key]) for key in ("current_status", "progress_txt") if entry.get(key)
        )

    @staticmethod
    def _short_id(session_id):
        """Kurze ID eines Laufs, der Teil vor "-__" """

        return str(session_id).split("-__", 1)[0]


# --------- KEEP THIS LINE AT THE END ---------
# Explicitly maintained, a runtime-built __all__ is invisible to type
# checkers. New public name: add it here.
__all__ = [
    "ARK_VERSION",
    "Ark",
    "ArkResult",
]
