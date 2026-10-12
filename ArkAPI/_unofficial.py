"""
Inoffizielle Endpunkte der Ark WebUI.

Nicht in der Spezifikation. Pfade und Verben stammen aus der WebUI,
Bodies und Antworten sind nicht dokumentiert und werden unveraendert
durchgereicht.
"""

# --------- IMPORTS ---------

import json
from urllib.parse import urlencode

from ._core import ArkCore


# --------- CLASS ---------
class UnofficialMixin(ArkCore):
    """Inoffizielle Endpunkte, je eine Methode pro Endpunkt

    Alle Methoden liefern ein ArkResult. Bei 2xx ist data der als JSON
    geparste Body, ist er kein JSON, der Text. Ohne Body und bei allen
    anderen Codes ist data None. Kein Code ist dokumentiert, message
    nennt daher bei Fehlern den undokumentierten Code.
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

    # --------- SYSTEM ---------

    def get_notifications_init(self):
        """Benachrichtigungen beim Laden der WebUI holen

        GET /notifications/init - inofficial
        """

        return self._call("GET", "/notifications/init")

    def get_notifications(self):
        """Aktuelle Benachrichtigungen holen

        GET /notifications - inofficial
        """

        return self._call("GET", "/notifications")

    def get_license_status(self):
        """Lizenzstatus holen

        GET /license/status - inofficial
        """

        return self._call("GET", "/license/status")

    def get_destinations(self):
        """Alle Backup-Ziele holen

        GET /destinations - inofficial
        """

        return self._call("GET", "/destinations")

    def get_schedule_string(self, schedule):
        """Zeitplan als lesbaren Text formatieren lassen

        POST /schedule/scheduleString - inofficial

        Parameters
        ----------
        schedule : object
            Zeitplan wie in der WebUI (Pflicht)
        """

        return self._call("POST", "/schedule/scheduleString", schedule)

    def send_email(self, data):
        """E-Mail ueber Ark versenden

        POST /email/send - inofficial

        Parameters
        ----------
        data : dict
            Body wie in der WebUI (Pflicht)
        """

        return self._call("POST", "/email/send", data)

    # --------- JOBS ---------

    def get_job_queue(self):
        """Wartende Jobs holen

        GET /job/queue - inofficial
        """

        return self._call("GET", "/job/queue")

    def get_active_jobs(self):
        """Laufende Jobs holen

        GET /job/active - inofficial

        Bekanntes Format: {"active_jobs": [{"id", "name", "current_status",
        "current_name", "progress_num", "progress_txt", ...}]}
        """

        return self._call("GET", "/job/active")

    def get_completed_jobs(self):
        """Abgeschlossene Jobs holen

        GET /job/completed - inofficial
        """

        return self._call("GET", "/job/completed")

    def get_inactive_jobs(self):
        """Inaktive Jobs holen

        GET /job/inactive - inofficial
        """

        return self._call("GET", "/job/inactive")

    def get_job(self, job_id):
        """Einen Job holen

        GET /job/<id> - inofficial

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        """

        return self._call("GET", self._path("job", job_id))

    def get_job_actions(self, job_id):
        """Aktionen eines Jobs holen

        GET /job/actions/<id> - inofficial

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        """

        return self._call("GET", self._path("job", "actions", job_id))

    def get_job_details(self, job_type, job_id):
        """Details eines Jobs holen

        GET /job/details/<job_type>/<id> - inofficial

        Parameters
        ----------
        job_type : str
            Job-Typ wie in der WebUI (Pflicht)
        job_id : str
            ID des Jobs (Pflicht)
        """

        return self._call(
            "GET", self._path("job", "details", job_type, job_id)
        )

    def create_job(self, data):
        """Job anlegen

        PUT /job - inofficial

        Parameters
        ----------
        data : dict
            Body wie in der WebUI (Pflicht)
        """

        return self._call("PUT", "/job", data)

    def modify_job(self, job_id, data):
        """Job aendern

        PUT /job/modify/<id> - inofficial

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        data : dict
            Body wie in der WebUI (Pflicht)
        """

        return self._call("PUT", self._path("job", "modify", job_id), data)

    def run_job(self, job_id):
        """Job starten

        POST /job/run/<id> - inofficial

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        """

        return self._call("POST", self._path("job", "run", job_id))

    def stop_job(self, job_id):
        """Job stoppen

        POST /job/stop/<id> - inofficial

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        """

        return self._call("POST", self._path("job", "stop", job_id))

    def delete_job(self, job_id):
        """Job loeschen

        DELETE /job/<id> - inofficial

        Parameters
        ----------
        job_id : str
            ID des Jobs (Pflicht)
        """

        return self._call("DELETE", self._path("job", job_id))

    def wait_for_events(self, last_event=0):
        """Auf neue Ereignisse warten

        GET /events/<last_event> - inofficial

        Long-Poll: der Server antwortet bei einem neuen Ereignis oder
        nach etwa 50 Sekunden.

        Parameters
        ----------
        last_event : int
            Optional, Standard 0. Kennung des zuletzt gesehenen Ereignisses
        """

        return self._call("GET", self._path("events", last_event))

    # --------- RESTORE ---------

    def get_restore_targets(self, data):
        """Moegliche Restore-Ziele fuer ausgewaehlte Backups holen

        POST /restore/restoreTargets - inofficial

        Parameters
        ----------
        data : object
            Auswahl der Backups wie in der WebUI (Pflicht)
        """

        return self._call("POST", "/restore/restoreTargets", data)

    def get_restore_names(self, data):
        """Namen fuer ausgewaehlte Backups beim Restore holen

        POST /restore/getRestoreNames - inofficial

        Parameters
        ----------
        data : object
            Auswahl der Backups wie in der WebUI (Pflicht)
        """

        return self._call("POST", "/restore/getRestoreNames", data)

    # --------- BACKUP ---------

    def get_backup_contents(self, backup_id, page=None):
        """Inhalt eines Backups holen

        GET /backup/contents/<backup_id>[/<page>] - inofficial

        Parameters
        ----------
        backup_id : str
            ID des Backups (Pflicht)
        page : int
            Optional. Seite, ohne Angabe die erste Antwort des Servers
        """

        parts = ("backup", "contents", backup_id)
        if page is not None:
            parts += (page,)
        return self._call("GET", self._path(*parts))

    def get_json_backup_contents(self, backup_id):
        """Inhalt eines Backups als JSON holen

        POST /backup/getJSONBackupContents - inofficial

        Parameters
        ----------
        backup_id : str
            ID des Backups (Pflicht)
        """

        return self._call(
            "POST", "/backup/getJSONBackupContents", {"id": backup_id}
        )

    def get_session_files(self, backup_id, page_num):
        """Dateien einer Backup-Session seitenweise holen

        POST /backup/sessionFiles - inofficial

        Parameters
        ----------
        backup_id : str
            ID des Backups (Pflicht)
        page_num : int
            Seite (Pflicht)
        """

        return self._call(
            "POST",
            "/backup/sessionFiles",
            {"id": backup_id, "page_num": page_num},
        )

    def prepare_disk_search(self):
        """Indexierung der Disk-Backups anstossen

        POST /backup/disk/search/prepare - inofficial
        """

        return self._call("POST", "/backup/disk/search/prepare")

    def remove_backups(self, data):
        """Disk-Backups loeschen

        DELETE /backup/removeBackups - inofficial

        Parameters
        ----------
        data : object
            Auswahl der Backups wie in der WebUI (Pflicht)
        """

        return self._call("DELETE", "/backup/removeBackups", data)

    # --------- DISK ---------

    def get_disk_license(self):
        """Lizenzen fuer Ark Disk holen

        GET /disk/license - inofficial
        """

        return self._call("GET", "/disk/license")

    def get_disk_backups(self):
        """Alle Disk-Backups holen

        GET /disk/getDiskBackups - inofficial
        """

        return self._call("GET", "/disk/getDiskBackups")

    # --------- TAPE ---------

    def get_tape_license(self):
        """Lizenzen fuer Ark Tape holen

        GET /tape/license - inofficial
        """

        return self._call("GET", "/tape/license")

    def get_tape_servers(self):
        """Tape-Server holen

        GET /tape/servers - inofficial
        """

        return self._call("GET", "/tape/servers")

    def get_tape_server_list(self):
        """Tape-Server fuer die Auswahlliste holen

        GET /tape/getTapeServers - inofficial
        """

        return self._call("GET", "/tape/getTapeServers")

    def get_tape_backups(self):
        """Alle Tape-Backups holen

        GET /tape/getTapeBackups - inofficial
        """

        return self._call("GET", "/tape/getTapeBackups")

    def get_tape_jobs(self, server_id):
        """Jobs eines Tape-Servers holen

        GET /tape/jobs/<server_id> - inofficial

        Parameters
        ----------
        server_id : str
            ID des Tape-Servers (Pflicht)
        """

        return self._call("GET", self._path("tape", "jobs", server_id))

    def get_tape_job_log(self, server_id, job_id):
        """Log eines Tape-Jobs holen

        GET /tape/log/<server_id>/<job_id> - inofficial

        Parameters
        ----------
        server_id : str
            ID des Tape-Servers (Pflicht)
        job_id : str
            ID des Tape-Jobs (Pflicht), siehe get_tape_jobs()
        """

        return self._call(
            "GET", self._path("tape", "log", server_id, job_id)
        )

    def get_tape_alerts(self, server_id=None):
        """Tape-Alarme holen

        GET /tape/alerts bzw. /tape/alerts/<server_id> - inofficial

        Parameters
        ----------
        server_id : str
            Optional. Nur die Alarme dieses Tape-Servers
        """

        if server_id is None:
            return self._call("GET", "/tape/alerts")
        return self._call("GET", self._path("tape", "alerts", server_id))

    def acknowledge_tape_alert(self, server_id, alert_id):
        """Einen Tape-Alarm bestaetigen

        PUT /tape/alerts/acknowledge/<server_id>/<alert_id> - inofficial

        Parameters
        ----------
        server_id : str
            ID des Tape-Servers (Pflicht)
        alert_id : str
            ID des Alarms (Pflicht)
        """

        return self._call(
            "PUT",
            self._path("tape", "alerts", "acknowledge", server_id, alert_id),
        )

    def get_pool_contents(self, pool_id, page_num):
        """Inhalt eines Tape-Pools seitenweise holen

        POST /tape/getPoolContents - inofficial

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        page_num : int
            Seite (Pflicht)
        """

        return self._call(
            "POST",
            "/tape/getPoolContents",
            {"id": pool_id, "page_num": page_num},
        )

    def scan_tapes(self):
        """Tapes in der Library neu einlesen

        POST /tape/scanTapes - inofficial
        """

        return self._call("POST", "/tape/scanTapes")

    def get_pool_tapes(self, pool_id):
        """Tapes eines Pools holen

        GET /tape/pool/<pool>/tapes - inofficial

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        """

        return self._call("GET", self._path("tape", "pool", pool_id, "tapes"))

    def set_pool_tapes(self, pool_id, data):
        """Tapes eines Pools setzen

        PUT /tape/pool/<pool>/tapes - inofficial

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        data : object
            Body wie in der WebUI (Pflicht)
        """

        return self._call(
            "PUT", self._path("tape", "pool", pool_id, "tapes"), data
        )

    def get_assigned_tapes(self, pool_id):
        """Einem Pool zugewiesene Tapes holen

        GET /tape/getAssignedTapes/<pool> - inofficial

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        """

        return self._call(
            "GET", self._path("tape", "getAssignedTapes", pool_id)
        )

    def get_unassigned_tapes(self, pool_id):
        """Nicht zugewiesene Tapes fuer einen Pool holen

        GET /tape/getUnassignedTapes/<pool> - inofficial

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        """

        return self._call(
            "GET", self._path("tape", "getUnassignedTapes", pool_id)
        )

    # --------- SOURCES ---------

    def get_media_spaces(self):
        """Media Spaces als Backup-Quelle holen

        GET /sources/mediaSpaces - inofficial
        """

        return self._call("GET", "/sources/mediaSpaces")

    def get_media_space_types(self):
        """Media-Space-Typen holen

        GET /sources/mediaSpaceTypes - inofficial
        """

        return self._call("GET", "/sources/mediaSpaceTypes")

    def get_project_spaces(self):
        """Project Spaces als Backup-Quelle holen

        GET /sources/projectSpaces - inofficial
        """

        return self._call("GET", "/sources/projectSpaces")

    def get_private_spaces(self):
        """Private Spaces als Backup-Quelle holen

        GET /sources/privateSpaces - inofficial
        """

        return self._call("GET", "/sources/privateSpaces")

    def get_exchange_spaces(self):
        """Exchange Spaces als Backup-Quelle holen

        GET /sources/exchangeSpaces - inofficial
        """

        return self._call("GET", "/sources/exchangeSpaces")

    def get_flow_sources(self):
        """FLOW als Backup-Quelle holen

        GET /sources/flow - inofficial
        """

        return self._call("GET", "/sources/flow")

    def get_ark_tape_db(self):
        """Ark-Tape-Datenbank als Backup-Quelle holen

        GET /sources/arkTapeDB - inofficial
        """

        return self._call("GET", "/sources/arkTapeDB")

    # --------- DOWNLOAD ---------

    def download_csv(self, params=None):
        """CSV-Export holen

        GET /download/csv?<params> - inofficial

        Parameters
        ----------
        params : dict
            Optional. Query-Parameter wie in der WebUI

        Returns
        -------
        ArkResult
            data ist der CSV-Text
        """

        return self._download("/download/csv", params)

    def download_search_csv(self, params=None):
        """CSV-Export einer Suche holen

        GET /download/search_csv?<params> - inofficial

        Parameters
        ----------
        params : dict
            Optional. Query-Parameter wie in der WebUI

        Returns
        -------
        ArkResult
            data ist der CSV-Text
        """

        return self._download("/download/search_csv", params)

    def _download(self, endpoint, params):
        """Text-Download ohne JSON-Auswertung"""

        query = "?" + urlencode(params) if params else ""
        return self._request(
            "GET", endpoint + query, codes={}, default="", raw=True
        )
