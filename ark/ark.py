"""
Wrapper fuer die EditShare Ark API.

Spezifikation:
https://developers.editshare.com/?urls.primaryName=EditShare%20Ark
"""

# --------- IMPORTS ---------

import logging

from FlowAPI.core import (
    Connection,
    create_gateway_instance_inner,
    create_instance,
)

# --------- KONSTANTEN ---------

ARK_VERSION = "0.1.0"

# FlowAPI.core kennt keinen Port fuer Ark, daher hier definiert.
# Siehe servers-Abschnitt der ark.yaml: https://{server}:8000/
ARK_PORT = 8000

# Ark Backup-Quellen bzw. Storage-Typen
SOURCE_DISK = "disk"
SOURCE_TAPE = "tape"

# Storage-Typen wie sie im filestatus-Response auftauchen
STORAGE_DISK = "ark_disk"
STORAGE_TAPE = "ark_tape"

# Suchmodi fuer search_backups()
SEARCH_EXACT = "exact"
SEARCH_CONTAINS = "contains"
SEARCH_WILDCARD = "wildcard"
SEARCH_FLOW_HASH = "flow_hash"

# Space-Typen fuer restore_backup()
SPACE_MEDIA = "ms"
SPACE_PROJECT = "ps"
SPACE_PRIVATE = "priv"
SPACE_FILE_EXCHANGE = "fe"
SPACE_SETTINGS = "es"
SPACE_FLOW = "flow"


# --------- KLASSE ---------


class Ark(Connection):
    """Kapselt die Endpunkte des Ark-Service"""

    # pylint: disable=too-many-public-methods

    def __init__(self):
        super().__init__()
        self._service_name = "ark"

    # --------- VERBINDUNG ---------

    @staticmethod
    def create_instance(ip_addr, username, password):
        """Direkte Verbindung zum Ark-Server aufbauen"""

        return create_instance(Ark, ip_addr, username, password)

    @staticmethod
    def create_gateway_instance(username, password, ip_addr=None):
        """Verbindung ueber das lokale Gateway aufbauen"""

        return create_gateway_instance_inner(Ark, username, password, ip_addr)

    def connect(self, ip_addr, username, password):
        """Verbindung zum Service-Server herstellen"""

        return Connection.connect2(self, ip_addr, ARK_PORT, username, password)

    # --------- RESTORE ---------

    def get_backups(self):
        """Liste aller in Ark gespeicherten Backups holen

        GET /restore/backups

        Returns
        -------
        list
            Backups auf Ark Disk und Ark Tape. Jeder Eintrag enthaelt
            u. a. backup_id, backup_type, date, media_space_name,
            media_space_uuid und destination_name.
        """

        reply = self.getThatReturnsObj("/restore/backups")
        if not reply:
            return []
        return reply

    def find_backups_by_space_name(self, space_name):
        """Alle Backups eines Media Space ueber den Namen finden"""

        return [
            backup
            for backup in self.get_backups()
            if backup.get("media_space_name") == space_name
        ]

    def find_backups_by_space_uuid(self, space_uuid):
        """Alle Backups eines Media Space ueber die UUID finden"""

        return [
            backup
            for backup in self.get_backups()
            if backup.get("media_space_uuid") == str(space_uuid)
        ]

    def find_backup(self, backup_id):
        """Ein einzelnes Backup ueber seine ID finden"""

        for backup in self.get_backups():
            if backup.get("backup_id") == backup_id:
                return backup

        return {}

    def restore_backups(self, data):
        """Backups aus Ark auf ein Storage-Ziel zurueckspielen

        POST /restore/restoreBackups

        Parameters
        ----------
        data : dict
            Das Restore-Kommando. Pflicht sind backups und target_data,
            optional storage_goals und restoreTime, z. B.

                {
                    "backups": [{"backup_id": "ark.tapeserver_f541..."}],
                    "target_data": {
                        "ms_target": "esa_IBN1e---es-master---/efs/efs_1"
                    },
                }

        Returns
        -------
        str
            ID des neuen Restore-Jobs, z. B. "restorejob_sovh0C".
            False wenn der Request fehlgeschlagen ist.
        """

        # Der Service antwortet mit einem reinen JSON-String, kein Objekt
        return self.postThatReturnsObj("/restore/restoreBackups", data)

    def restore_backup(
        self,
        backup_id,
        target,
        *,
        space_type=SPACE_MEDIA,
        rename=None,
        cumulative=False,
        storage_goal=None,
        restore_date=None,
        restore_time=None,
    ):
        # pylint: disable=too-many-arguments
        """Ein einzelnes Backup zurueckspielen

        Parameters
        ----------
        backup_id : str
            ID des Backups, siehe get_backups()
        target : str
            Das Restore-Ziel. Bei Media Spaces bestehend aus drei durch
            je drei Bindestriche getrennten Teilen: ESA-Gruppe,
            Server-Group-Member und Pfad zum Bit Bucket, z. B.
            "esa_IBN1e---es-master---/efs/efs_1". Bei allen anderen
            Space-Typen genuegt die ESA-Gruppe, z. B. "esa_HiNbl"
        space_type : str
            ms, ps, priv, fe, es oder flow
        rename : str
            Optionaler neuer Name fuer den restaurierten Space
        cumulative : bool
            Alle Dateien der Incremental-Kette bis backup_id
            zurueckspielen. Nur Ark Tape
        storage_goal : str
            Optionales EFS Storage Goal fuer restaurierte Media Spaces
        restore_date : str
            Optionaler Termin, z. B. "10/21/2015"
        restore_time : str
            Optionale Uhrzeit, z. B. "03:00am"

        Returns
        -------
        str
            ID des neuen Restore-Jobs
        """

        backup = {"backup_id": backup_id}
        if cumulative:
            backup["cumulative"] = True
        if rename:
            backup["rename"] = rename

        data = {
            "backups": [backup],
            "target_data": {"{}_target".format(space_type): target},
        }

        if storage_goal:
            data["storage_goals"] = {backup_id: storage_goal}

        if restore_date or restore_time:
            data["restoreTime"] = {}
            if restore_date:
                data["restoreTime"]["date"] = restore_date
            if restore_time:
                data["restoreTime"]["time"] = restore_time

        return self.restore_backups(data)

    def restore_hashes(self, data):
        """Einzelne Dateien anhand ihrer FLOW-Hashes zurueckspielen

        POST /restore/hashes

        Parameters
        ----------
        data : dict
            Das Restore-Kommando. Pflicht sind files und destination,
            optional source, z. B.

                {
                    "files": [
                        {
                            "flow_hash": "2:d41d8cd9...",
                            "restore_path": "restored_files/",
                        }
                    ],
                    "destination": {"mediaspace": "MyMediaSpace"},
                }

        Returns
        -------
        str
            session_guid des neuen Restore-Jobs, False bei Fehler.
            Achtung: alle uebergebenen Hashes muessen restaurierbar
            sein, sonst antwortet Ark mit 404.
        """

        reply = self.postThatReturnsObj("/restore/hashes", data)
        if not reply:
            return False

        return reply.get("session_guid", False)

    def restore_files_by_hash(
        self,
        hashes,
        mediaspace,
        *,
        restore_path="/",
        space_uuid=None,
        ark_sources=None,
        prefer_source=None,
    ):
        # pylint: disable=too-many-arguments
        """Eine Liste von FLOW-Hashes in einen Media Space zurueckspielen

        Parameters
        ----------
        hashes : list
            Liste von FLOW-Hashes (Version 2, also "2:<md5>") oder eine
            Liste von Dicts wie sie restore_hashes() erwartet
        mediaspace : str
            Name des Ziel-Media-Space
        restore_path : str
            Pfad innerhalb des Media Space, "/" fuer die Wurzel. Wird
            angelegt falls nicht vorhanden
        space_uuid : str
            Optionale UUID des Ziel-Media-Space
        ark_sources : list
            Optionale Quellen fuer die Suche, z. B. ["disk", "tape"]
        prefer_source : str
            Bevorzugte Quelle wenn die Datei in beiden liegt,
            disk oder tape

        Returns
        -------
        str
            session_guid des neuen Restore-Jobs
        """

        files = []
        for entry in hashes:
            if isinstance(entry, dict):
                files.append(entry)
            else:
                files.append({"flow_hash": entry, "restore_path": restore_path})

        destination = {"mediaspace": mediaspace}
        if space_uuid:
            destination["space_uuid"] = str(space_uuid)

        data = {"files": files, "destination": destination}

        source = {}
        if ark_sources:
            source["ark_sources"] = list(ark_sources)
        if prefer_source:
            source["prefer_source"] = prefer_source
        if source:
            data["source"] = source

        return self.restore_hashes(data)

    # --------- FILESTATUS ---------

    def get_file_hash_database_status(self):
        """Status der Hash-Datenbank abfragen

        GET /filestatus/database

        Returns
        -------
        dict
            status (importing, complete oder error),
            progress_complete und progress_estimated
        """

        return self.getThatReturnsObj("/filestatus/database")

    def get_file_status(self, flow_hash):
        """Ark Backup-Status einer Datei anhand ihres Hashes abfragen

        GET /filestatus/{FileHash}

        Parameters
        ----------
        flow_hash : str
            Ein FLOW-Hash. Version 0 ("<md5>"), Version 1 ("1:<md5>")
            und Version 2 ("2:<md5>") werden unterstuetzt.
            Siehe CLI-Kommando: flow-hash

        Returns
        -------
        list
            Liste der Treffer mit hash, storage_type, job_id, job_time,
            file_id, pathname, filename, space_uuid, space_name und
            tapes. Leere Liste wenn Ark keine Kopie hat (404).
        """

        url = "/filestatus/" + self.safe_url_string(str(flow_hash))
        reply = self.getThatReturnsObj(url)
        if not reply:
            return []
        return reply

    def get_file_statuses(self, hash_list):
        """Ark Backup-Status fuer eine Liste von Hashes abfragen

        POST /filestatus/

        Parameters
        ----------
        hash_list : list
            Liste von FLOW-Hashes

        Returns
        -------
        list
            Liste der Treffer, siehe get_file_status()
        """

        # Der abschliessende Slash ist hier Pflicht, der Body ist ein
        # reines String-Array
        reply = self.postThatReturnsObj("/filestatus/", list(hash_list))
        if not reply:
            return []
        return reply

    def is_archived(self, flow_hash, storage_type=None):
        """Pruefen ob Ark eine Kopie der Datei haelt

        Parameters
        ----------
        flow_hash : str
            Ein FLOW-Hash
        storage_type : str
            Optional nur ark_disk oder ark_tape akzeptieren

        Returns
        -------
        bool
            True wenn mindestens ein Treffer vorliegt
        """

        matches = self.get_file_status(flow_hash)
        if not matches:
            return False

        if not storage_type:
            return True

        for match in matches:
            if match.get("storage_type") == storage_type:
                return True

        return False

    @staticmethod
    def tapes_from_file_status(file_status):
        """Barcodes der Tapes aus einem filestatus-Eintrag sammeln"""

        tapes = []
        for tape in file_status.get("tapes", []) or []:
            if isinstance(tape, dict):
                barcode = tape.get("barcode") or tape.get("name")
                if barcode:
                    tapes.append(barcode)
            else:
                tapes.append(tape)
        return tapes

    # --------- BACKUP SEARCH ---------

    def get_disk_search_status(self):
        """Indexierungsstatus der Disk-Backups abfragen

        GET /backup/disk/search/status

        Returns
        -------
        dict
            total, indexed, indexing, not_indexed, needs_indexing
            und total_files
        """

        return self.getThatReturnsObj("/backup/disk/search/status")

    def search_backups(
        self,
        search_pattern,
        search_mode=SEARCH_CONTAINS,
        *,
        backup_type=None,
        limit=100,
        offset=0,
    ):
        # pylint: disable=too-many-arguments
        """Dateien in den indexierten Backups suchen

        POST /backup/search

        Parameters
        ----------
        search_pattern : str
            Dateiname oder Muster. Bei search_mode flow_hash ein
            FLOW-Hash der Version 2
        search_mode : str
            exact, contains, wildcard oder flow_hash
        backup_type : str
            disk, tape oder None fuer beide
        limit : int
            Maximale Trefferzahl, 1 bis 10000
        offset : int
            Anzahl zu ueberspringender Treffer

        Returns
        -------
        dict
            total_matches, limit, offset und results. Disk-Backups
            muessen indexiert sein, siehe get_disk_search_status()
        """

        data = {
            "search_pattern": search_pattern,
            "search_mode": search_mode,
            "limit": limit,
            "offset": offset,
        }

        if backup_type:
            data["backup_type"] = backup_type

        return self.postThatReturnsObj("/backup/search", data)

    def search_all_backups(
        self,
        search_pattern,
        search_mode=SEARCH_CONTAINS,
        *,
        backup_type=None,
        page_size=1000,
        max_results=0,
    ):
        # pylint: disable=too-many-arguments
        """Alle Treffer einer Suche seitenweise holen

        Parameters
        ----------
        page_size : int
            Treffer pro Request, 1 bis 10000
        max_results : int
            Abbruch nach dieser Trefferzahl, 0 holt alles

        Returns
        -------
        list
            Alle passenden Treffer
        """

        results = []
        offset = 0

        while True:
            reply = self.search_backups(
                search_pattern,
                search_mode,
                backup_type=backup_type,
                limit=page_size,
                offset=offset,
            )
            if not reply:
                break

            page = reply.get("results", [])
            if not page:
                break

            results += page
            offset += len(page)

            if max_results and len(results) >= max_results:
                return results[:max_results]

            if offset >= int(reply.get("total_matches", 0)):
                break

        return results

    def search_by_flow_hash(self, flow_hash, *, backup_type=None, limit=100):
        """Den Backup-Index nach einem FLOW-Hash durchsuchen"""

        if not str(flow_hash).startswith("2:"):
            logging.warning(
                "search_by_flow_hash: '%s' ist kein Hash der Version 2", flow_hash
            )

        return self.search_backups(
            flow_hash,
            SEARCH_FLOW_HASH,
            backup_type=backup_type,
            limit=limit,
        )

    # --------- TAPE LIBRARY ---------

    def get_tape_library_status(self):
        """Rohen Status der Tape Library inklusive Timestamp holen

        GET /api/tape/library/tapes
        """

        return self.getThatReturnsObj("/api/tape/library/tapes")

    def get_tapes(self):
        """Alle dem System bekannten Tapes holen

        Returns
        -------
        list
            Alle Tape-Volumes, nicht nur die aktuell geladenen. Jeder
            Eintrag enthaelt mindestens barcode und in_changer
        """

        reply = self.get_tape_library_status()
        if not reply:
            return []
        return reply.get("tapes", [])

    def find_tape(self, barcode):
        """Ein Tape-Volume ueber seinen Barcode finden"""

        for tape in self.get_tapes():
            if tape.get("barcode") == barcode:
                return tape

        return {}
