"""
Inoffizielle Endpunkte der Ark WebUI.

Nicht in der Spezifikation. Pfade und Verben stammen aus der WebUI,
Bodies und Antworten sind nicht dokumentiert und werden unveraendert
durchgereicht.
"""

# --------- IMPORTS ---------

import json
from urllib.parse import urlencode

from .core import ArkCore, ArkResult


# --------- CLASS ---------
class UnofficialMixin(ArkCore):
    """Inoffizielle Endpunkte der WebUI

    Alle Methoden liefern ein ArkResult. Bei 2xx ist data der als JSON
    geparste Body, ist er kein JSON, der Text. Ohne Body und bei allen
    anderen Codes ist data None. Kein Code ist dokumentiert, Erfolg ist
    200 <= code < 300.
    """

    def _call(self, verb, endpoint, data=None):
        """Inoffiziellen Endpunkt aufrufen, JSON wenn moeglich, sonst Text"""

        result = self._request(verb, endpoint, data, codes={}, raw=True)
        if isinstance(result.data, str) and result.data.strip():
            try:
                result.data = json.loads(result.data)
            except ValueError:
                pass
        elif isinstance(result.data, str):
            result.data = None
        return result

    # --------- JOBS ---------

    def get_jobs_queue(self) -> ArkResult:
        """Aktive, abgeschlossene und inaktive Jobs in einer Antwort holen

        GET /job/queue - inofficial

        Returns
        -------
        ArkResult
            data enthaelt active_jobs, completed_jobs (Laeufe unter
            sessions) und inactive_jobs
        """

        return self._call("GET", "/job/queue")

    def get_jobs_active(self) -> ArkResult:
        """Laufende und wartende Laeufe mit Fortschritt holen

        GET /job/active - inofficial

        Returns
        -------
        ArkResult
            data ist {"active_jobs": [...]}, je Lauf u. a. id,
            current_status, progress_txt, progress_num, current_name und
            current_speed
        """

        return self._call("GET", "/job/active")

    def get_jobs_completed(self) -> ArkResult:
        """Abgeschlossene Jobs holen, ihre Laeufe unter sessions

        GET /job/completed - inofficial

        Returns
        -------
        ArkResult
            data ist {"completed_jobs": [...]}, je Lauf unter sessions
            u. a. id, status, creation_time, has_filelist und name
        """

        return self._call("GET", "/job/completed")

    def get_jobs_inactive(self) -> ArkResult:
        """Geplante Backup-Jobs mit naechstem Termin holen

        GET /job/inactive - inofficial
        """

        return self._call("GET", "/job/inactive")

    def get_session_files(self, session_id: str, page_num: int = 0) -> ArkResult:
        """Dateiliste und Fehlertext eines Laufs holen, seitenweise

        POST /backup/sessionFiles - inofficial

        Parameters
        ----------
        session_id : str
            Lange Session-ID (Pflicht), die kurze liefert 500
        page_num : int
            Seite, Standard 0

        Returns
        -------
        ArkResult
            data ist {"files": [...], "explanation": "...",
            "num_pages": 0, "id": "..."}. explanation nennt den Grund,
            wenn nicht alles restauriert wurde
        """

        return self._call(
            "POST", "/backup/sessionFiles", {"id": session_id, "page_num": page_num}
        )

    def get_job(self, job_id: str) -> ArkResult:
        """Eine Job-Definition holen, vermutlich mit Zeitplan

        GET /job/{id} - inofficial, ungetestet

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        """

        return self._call("GET", self._path("job", job_id))

    def get_job_actions(self, job_id: str) -> ArkResult:
        """Die Aktionen einer Job-Definition holen

        GET /job/actions/{id} - inofficial, ungetestet

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        """

        return self._call("GET", self._path("job", "actions", job_id))

    def get_job_details(
        self, session_id: str, job_list: str = "completed_jobs"
    ) -> ArkResult:
        """Die Details eines Laufs holen

        GET /job/details/{job_list}/{id} - inofficial, ungetestet

        Parameters
        ----------
        session_id : str
            Lange Session-ID (Pflicht)
        job_list : str
            Liste, in der der Lauf steht, Standard "completed_jobs"
        """

        return self._call("GET", self._path("job", "details", job_list, session_id))

    def create_job(self, data: dict, *, confirm: bool = False) -> ArkResult:
        """Einen Job anlegen

        PUT /job - inofficial, ungetestet

        Parameters
        ----------
        data : dict
            Body wie in der WebUI (Pflicht)
        confirm : bool
            Muss True sein, sonst ValueError ohne Anfrage
        """

        self._confirm(confirm, "create_job")
        return self._call("PUT", "/job", data)

    def modify_job(self, job_id: str, data: dict, *, confirm: bool = False) -> ArkResult:
        """Einen Job aendern

        PUT /job/modify/{id} - inofficial, ungetestet

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        data : dict
            Body wie in der WebUI (Pflicht)
        confirm : bool
            Muss True sein, sonst ValueError ohne Anfrage
        """

        self._confirm(confirm, "modify_job")
        return self._call("PUT", self._path("job", "modify", job_id), data)

    def delete_job(self, job_id: str, *, confirm: bool = False) -> ArkResult:
        """Einen Job loeschen

        DELETE /job/{id} - inofficial, ungetestet

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        confirm : bool
            Muss True sein, sonst ValueError ohne Anfrage
        """

        self._confirm(confirm, "delete_job")
        return self._call("DELETE", self._path("job", job_id))

    def run_job(self, job_id: str) -> ArkResult:
        """Einen Job starten

        POST /job/run/{id} - inofficial, ungetestet

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        """

        return self._call("POST", self._path("job", "run", job_id))

    def _stop_job(self, session_id):
        """POST /job/stop/{id}, siehe stop_job()"""

        return self._call("POST", self._path("job", "stop", session_id))

    def wait_for_events(self, last_event: int = 0) -> ArkResult:
        """Auf neue Ereignisse seit einer Ereignisnummer warten

        GET /events/{last_event} - inofficial, ungetestet

        Long-Poll: der Server antwortet bei einem neuen Ereignis oder nach
        etwa 50 Sekunden.

        Parameters
        ----------
        last_event : int
            Nummer des zuletzt gesehenen Ereignisses, Standard 0
        """

        return self._call("GET", self._path("events", last_event))

    # --------- RESTORE AND BACKUP ---------

    def get_restore_targets(self, data: object) -> ArkResult:
        """Moegliche Ziele fuer ausgewaehlte Backups holen

        POST /restore/restoreTargets - inofficial, ungetestet

        Parameters
        ----------
        data : object
            Auswahl der Backups wie in der WebUI (Pflicht)
        """

        return self._call("POST", "/restore/restoreTargets", data)

    def get_restore_names(self, data: object) -> ArkResult:
        """Namen fuer ausgewaehlte Backups vorschlagen lassen

        POST /restore/getRestoreNames - inofficial, ungetestet

        Parameters
        ----------
        data : object
            Auswahl der Backups wie in der WebUI (Pflicht)
        """

        return self._call("POST", "/restore/getRestoreNames", data)

    def get_backup_contents(self, backup_id: str, page: int | None = None) -> ArkResult:
        """Den Inhalt eines Backups holen

        GET /backup/contents/{id}[/{page}] - inofficial, ungetestet

        Parameters
        ----------
        backup_id : str
            ID des Backups (Pflicht)
        page : int
            Optional. Seite, ohne Angabe die erste Antwort des Servers
        """

        parts = ("backup", "contents", backup_id) + (() if page is None else (page,))
        return self._call("GET", self._path(*parts))

    # --------- POOLS ---------

    def get_pools_targets(self) -> ArkResult:
        """Die Pools holen, die als Backup-Ziel nutzbar sind

        GET /destinations - inofficial
        """

        return self._call("GET", "/destinations")

    def get_pool_tapes(self, pool_id: str) -> ArkResult:
        """Die Tapes eines Pools holen

        GET /tape/pool/{pool}/tapes - inofficial, ungetestet

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        """

        return self._call("GET", self._path("tape", "pool", pool_id, "tapes"))

    def set_pool_tapes(self, pool_id: str, data: object, *, confirm: bool = False) -> ArkResult:
        """Festlegen, welche Tapes zu einem Pool gehoeren

        PUT /tape/pool/{pool}/tapes - inofficial, ungetestet

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        data : object
            Body wie in der WebUI (Pflicht)
        confirm : bool
            Muss True sein, sonst ValueError ohne Anfrage
        """

        self._confirm(confirm, "set_pool_tapes")
        return self._call("PUT", self._path("tape", "pool", pool_id, "tapes"), data)

    def get_pool_tapes_assigned(self, pool_id: str) -> ArkResult:
        """Die einem Pool zugewiesenen Tapes holen

        GET /tape/getAssignedTapes/{pool} - inofficial, ungetestet

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        """

        return self._call("GET", self._path("tape", "getAssignedTapes", pool_id))

    def get_pool_tapes_unassigned(self, pool_id: str) -> ArkResult:
        """Die freien Tapes fuer einen Pool holen

        GET /tape/getUnassignedTapes/{pool} - inofficial, ungetestet

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        """

        return self._call("GET", self._path("tape", "getUnassignedTapes", pool_id))

    def get_pool_contents(self, pool_id: str, page_num: int) -> ArkResult:
        """Den Inhalt eines Pools holen, seitenweise

        POST /tape/getPoolContents - inofficial, ungetestet

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        page_num : int
            Seite (Pflicht)
        """

        return self._call(
            "POST", "/tape/getPoolContents", {"id": pool_id, "page_num": page_num}
        )

    # --------- TAPES ---------

    def get_tape_servers(self) -> ArkResult:
        """Die Tape-Server mit Adresse holen

        GET /tape/servers - inofficial
        """

        return self._call("GET", "/tape/servers")

    def get_tape_server_list(self) -> ArkResult:
        """Die Tape-Server fuer die Auswahlliste holen

        GET /tape/getTapeServers - inofficial
        """

        return self._call("GET", "/tape/getTapeServers")

    def get_tape_backups(self) -> ArkResult:
        """Die Tape-Backups nach Pool und Space holen

        GET /tape/getTapeBackups - inofficial
        """

        return self._call("GET", "/tape/getTapeBackups")

    def get_tape_license(self) -> ArkResult:
        """Die Ark-Tape-Lizenzen holen

        GET /tape/license - inofficial
        """

        return self._call("GET", "/tape/license")

    def get_tape_jobs(
        self, server_id: str, *, offset: int = 0, limit: int = 100, ascending: bool = False
    ) -> ArkResult:
        """Die Jobs eines Tape-Servers holen, seitenweise

        GET /tape/jobs/{server}?offset=&limit=&ascending= - inofficial,
        ungetestet

        Parameters
        ----------
        server_id : str
            ID des Tape-Servers (Pflicht), siehe get_tape_servers()
        offset : int
            Zu ueberspringende Jobs, Standard 0
        limit : int
            Jobs pro Seite, Standard 100
        ascending : bool
            Aelteste zuerst, Standard False
        """

        query = urlencode(
            {"offset": offset, "limit": limit, "ascending": str(bool(ascending)).lower()}
        )
        return self._call("GET", self._path("tape", "jobs", server_id) + "?" + query)

    def get_tape_job_log(self, server_id: str, job_id: str) -> ArkResult:
        """Das Log eines Tape-Jobs holen

        GET /tape/log/{server}/{job} - inofficial, ungetestet

        Parameters
        ----------
        server_id : str
            ID des Tape-Servers (Pflicht)
        job_id : str
            ID des Tape-Jobs (Pflicht), siehe get_tape_jobs()
        """

        return self._call("GET", self._path("tape", "log", server_id, job_id))

    def get_tape_alerts(self, server_id: str | None = None) -> ArkResult:
        """Tape-Alarme mit Tape, Laufwerk und Tape-Job holen

        GET /tape/alerts[/{server}] - inofficial

        Parameters
        ----------
        server_id : str
            Optional. Nur die Alarme dieses Tape-Servers

        Returns
        -------
        ArkResult
            data ist {"count": ..., "start": ..., "data": [...]}
        """

        parts = ("tape", "alerts") + (() if server_id is None else (server_id,))
        return self._call("GET", self._path(*parts))

    def acknowledge_tape_alert(
        self, server_id: str, alert_id: str, *, confirm: bool = False
    ) -> ArkResult:
        """Einen Tape-Alarm bestaetigen

        PUT /tape/alerts/acknowledge/{server}/{id} - inofficial, ungetestet

        Parameters
        ----------
        server_id : str
            ID des Tape-Servers (Pflicht)
        alert_id : str
            ID des Alarms (Pflicht), siehe get_tape_alerts()
        confirm : bool
            Muss True sein, sonst ValueError ohne Anfrage
        """

        self._confirm(confirm, "acknowledge_tape_alert")
        return self._call(
            "PUT", self._path("tape", "alerts", "acknowledge", server_id, alert_id)
        )

    def scan_tapes(self) -> ArkResult:
        """Die Tapes in der Library neu einlesen

        POST /tape/scanTapes - inofficial, ungetestet
        """

        return self._call("POST", "/tape/scanTapes")

    # --------- SOURCES AND SYSTEM ---------

    def get_mediaspaces(self) -> ArkResult:
        """Die Media Spaces holen

        GET /sources/mediaSpaces - inofficial
        """

        return self._call("GET", "/sources/mediaSpaces")

    def get_mediaspaces_types(self) -> ArkResult:
        """Die Media-Space-Typen holen

        GET /sources/mediaSpaceTypes - inofficial
        """

        return self._call("GET", "/sources/mediaSpaceTypes")

    def get_mediaspaces_project(self) -> ArkResult:
        """Die Project Spaces holen

        GET /sources/projectSpaces - inofficial
        """

        return self._call("GET", "/sources/projectSpaces")

    def get_mediaspaces_private(self) -> ArkResult:
        """Die Private Spaces holen

        GET /sources/privateSpaces - inofficial
        """

        return self._call("GET", "/sources/privateSpaces")

    def get_mediaspaces_exchange(self) -> ArkResult:
        """Die Exchange Spaces holen

        GET /sources/exchangeSpaces - inofficial
        """

        return self._call("GET", "/sources/exchangeSpaces")

    def get_sources_flow(self) -> ArkResult:
        """Die FLOW-Quellen (Proxies, Datenbank) holen

        GET /sources/flow - inofficial
        """

        return self._call("GET", "/sources/flow")

    def get_sources_tape_db(self) -> ArkResult:
        """Die Ark-Tape-Datenbank als Quelle holen

        GET /sources/arkTapeDB - inofficial
        """

        return self._call("GET", "/sources/arkTapeDB")

    def get_notifications(self) -> ArkResult:
        """Die letzten Benachrichtigungen holen, etwa 290 Eintraege

        GET /notifications - inofficial
        """

        return self._call("GET", "/notifications")

    def get_license_status(self) -> ArkResult:
        """Den Lizenzstatus holen

        GET /license/status - inofficial
        """

        return self._call("GET", "/license/status")
