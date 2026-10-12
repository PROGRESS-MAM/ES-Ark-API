"""
Wrapper fuer die EditShare Ark API.

Spezifikation:
https://developers.editshare.com/?urls.primaryName=EditShare%20Ark

"""

# --------- IMPORTS ---------

import logging
import time

from ._core import ArkResult
from ._official import OfficialMixin
from ._unofficial import UnofficialMixin

# --------- STATIC ---------

ARK_VERSION = "0.2.0"
__version__ = ARK_VERSION


# --------- CLASS ---------
class Ark(UnofficialMixin, OfficialMixin):
    """Einstiegspunkt fuer alle Ark-Methoden

    Offizielle Endpunkt-Methoden (OfficialMixin), je eine pro Operation
    der Spezifikation:

        get_backups                     GET    /restore/backups
        restore_backups                 POST   /restore/restoreBackups
        restore_hashes                  POST   /restore/hashes
        get_file_hash_database_status   GET    /filestatus/database
        get_file_status                 GET    /filestatus/{FileHash}
        has_file_status                 HEAD   /filestatus/{FileHash}
        get_file_statuses               POST   /filestatus/
        get_disk_search_status          GET    /backup/disk/search/status
        search_backups                  POST   /backup/search
        get_tape_library_status         GET    /api/tape/library/tapes
        get_tape_pools                  GET    /tape/pools
        get_tape_pool                   GET    /tape/pool/{pool_id}
        create_tape_pool                PUT    /tape/pool
        rename_tape_pool                PATCH  /tape/pool/{pool_id}
        delete_tape_pool                DELETE /tape/pool/{pool_id}

    Inoffizielle Endpunkt-Methoden der WebUI stehen in UnofficialMixin.

    Dazu Komfort-Methoden ohne eigenen Endpunkt: restore_backup,
    restore_files_by_hash, search_by_flow_hash, search_all_backups,
    find_backup, find_backups_by_space_name, find_backups_by_space_uuid,
    get_tapes, find_tape, tapes_from_file_status, sowie fuer
    Restore-Jobs check_hashes_restorable, get_restore_job_status,
    get_restore_job_errors und stop_restore_job.
    """

    # --------- CONNECTION ---------
    @staticmethod
    def create_instance(username, password, ip_addr):
        """Direkt verbundene Ark-Instanz erzeugen

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
            Verbundene Instanz, HTTPS auf Port 8000

        Examples
        --------
        >>> import ArkAPI
        >>> ark = ArkAPI.Ark.create_instance(
        ...     os.environ.get("FLOW_USER"),
        ...     os.environ.get("FLOW_PASSWORD"),
        ...     os.environ.get("FLOW_HOST"))
        """

        ark = Ark()
        ark.connect(ip_addr, username, password)
        return ark

    def connect(self, ip_addr, username, password):
        """Verbindung zum Ark-Server herstellen

        Wird von create_instance() aufgerufen und ueberschreibt
        Connection.connect() der FlowAPI mit festem Port.

        Parameters
        ----------
        ip_addr : str
            IP oder Hostname des Ark-Servers (Pflicht)
        username : str
            Benutzername fuer BasicAuth (Pflicht)
        password : str
            Passwort fuer BasicAuth (Pflicht)

        Notes
        -----
        Ark laeuft fest auf Port 8000. FlowAPI.core kennt dafuer keine
        Konstante.
        """

        return self.connect2(ip_addr, 8000, username, password)

    # --------- COMFORT ---------

    @staticmethod
    def tapes_from_file_status(file_status):
        """Barcodes der Tapes aus einem filestatus-Eintrag sammeln

        Reine Auswertung eines bereits geholten Eintrags, kein Request.

        Parameters
        ----------
        file_status : dict
            Ein Eintrag aus der data von get_file_status() oder
            get_file_statuses() (Pflicht)

        Returns
        -------
        list
            Die Barcodes. Leer bei Disk-Backups, die keine Tapes haben
        """

        tapes = []
        for tape in file_status.get("tapes", []) or []:
            if isinstance(tape, dict):
                barcode = tape.get("barcode") or tape.get("name")
                if barcode:
                    tapes.append(barcode)
            else:
                tapes.append(tape)
        return tapes

    def restore_backup(
        self,
        backup_id,
        target,
        *,
        space_type="ms",
        rename=None,
        cumulative=False,
        storage_goal=None,
        restore_date=None,
        restore_time=None,
    ):
        """Ein einzelnes Backup zurueckspielen

        Baut den Body und ruft restore_backups() auf.

        Parameters
        ----------
        backup_id : str
            ID des Backups (Pflicht), siehe get_backups()
        target : str
            Das Restore-Ziel (Pflicht). Bei Media Spaces bestehend aus
            drei durch je drei Bindestriche getrennten Teilen:
            ESA-Gruppe, Server-Group-Member und Pfad zum Bit Bucket,
            z. B. "esa_IBN1e---es-master---/efs/efs_1". Bei allen
            anderen Space-Typen genuegt die ESA-Gruppe, z. B. "esa_HiNbl"
        space_type : str
            Optional, Standard "ms". Erlaubt sind "ms", "ps", "priv",
            "fe", "es" und "flow"
        rename : str
            Optional. Neuer Name fuer den restaurierten Space
        cumulative : bool
            Optional, Standard False. Alle Dateien der
            Incremental-Kette bis backup_id zurueckspielen, nur Ark Tape
        storage_goal : str
            Optional. EFS Storage Goal fuer restaurierte Media Spaces
        restore_date : str
            Optional. Termin im Format "10/21/2015"
        restore_time : str
            Optional. Uhrzeit im Format "03:00am"

        Returns
        -------
        ArkResult
            Wie restore_backups(), data ist die Job-ID

        Notes
        -----
        Dokumentierte Statuscodes: 200, siehe restore_backups()
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
        """Eine Liste von FLOW-Hashes in einen Media Space zurueckspielen

        Baut den Body und ruft restore_hashes() auf.

        Parameters
        ----------
        hashes : list
            Liste von FLOW-Hashes (Pflicht), z. B.
            ["2:d41d8cd98f00b204e9800998ecf8427e"]. Alternativ eine
            Liste von Dicts wie sie restore_hashes() erwartet
        mediaspace : str
            Name des Ziel-Media-Space (Pflicht)
        restore_path : str
            Optional, Standard "/". Pfad innerhalb des Media Space, wird
            angelegt falls nicht vorhanden
        space_uuid : str
            Optional. UUID des Ziel-Media-Space
        ark_sources : list
            Optional. Quellen fuer die Suche, erlaubt sind "disk" und
            "tape", z. B. ["disk", "tape"]
        prefer_source : str
            Optional. Bevorzugte Quelle wenn die Datei in beiden liegt,
            "disk" oder "tape"

        Returns
        -------
        ArkResult
            Wie restore_hashes(), data enthaelt bei 200 die session_guid

        Notes
        -----
        Dokumentierte Statuscodes: 200, 400, 404, siehe restore_hashes()
        """

        files = []
        for entry in hashes:
            if isinstance(entry, dict):
                files.append(entry)
            else:
                files.append(
                    {"flow_hash": entry, "restore_path": restore_path}
                )

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

    def search_by_flow_hash(self, flow_hash, *, backup_type=None, limit=100):
        """Den Backup-Index nach einem FLOW-Hash durchsuchen

        Ruft search_backups() im Modus flow_hash auf.

        Parameters
        ----------
        flow_hash : str
            Ein FLOW-Hash der Version 2 (Pflicht), also "2:<md5>".
            Andere Versionen werden von diesem Suchmodus nicht
            unterstuetzt und nur als Warnung geloggt
        backup_type : str
            Optional. disk oder tape, ohne Angabe beide
        limit : int
            Optional, Standard 100. Maximale Trefferzahl, 1 bis 10000

        Returns
        -------
        ArkResult
            Wie search_backups()

        Notes
        -----
        Dokumentierte Statuscodes: 200, 400, siehe search_backups()
        """

        if not str(flow_hash).startswith("2:"):
            logging.warning(
                "search_by_flow_hash: '%s' ist kein Hash der Version 2",
                flow_hash,
            )

        return self.search_backups(
            flow_hash,
            "flow_hash",
            backup_type=backup_type,
            limit=limit,
        )

    def get_tapes(self):
        """Alle dem System bekannten Tapes holen

        Ruft get_tape_library_status() auf und gibt nur die Tape-Liste
        als data zurueck.

        Returns
        -------
        ArkResult
            data ist bei 200 die Liste aller Tape-Volumes, nicht nur der
            aktuell geladenen. Jeder Eintrag enthaelt mindestens barcode
            und in_changer. Sonst eine leere Liste

        Notes
        -----
        Dokumentierte Statuscodes: 200, siehe get_tape_library_status()
        """

        result = self.get_tape_library_status()
        if result.code == 200 and isinstance(result.data, dict):
            result.data = result.data.get("tapes", [])
        else:
            result.data = []
        return result

    def find_tape(self, barcode):
        """Ein Tape-Volume ueber seinen Barcode finden

        Ruft get_tapes() auf und filtert die Liste.

        Parameters
        ----------
        barcode : str
            Der Barcode des Tapes (Pflicht), z. B. "001234L5"

        Returns
        -------
        ArkResult
            data ist der passende Eintrag oder ein leeres dict, wenn
            kein Tape mit diesem Barcode bekannt ist

        Notes
        -----
        Dokumentierte Statuscodes: 200, siehe get_tape_library_status().
        Ein leeres data bei code 200 heisst: Barcode nicht gefunden
        """

        result = self.get_tapes()
        match = {}
        if result.code == 200:
            for tape in result.data or []:
                if tape.get("barcode") == barcode:
                    match = tape
                    break
        result.data = match
        return result

    def find_backups_by_space_name(self, space_name):
        """Alle Backups eines Media Space ueber den Namen finden

        Ruft get_backups() auf und filtert die Liste.

        Parameters
        ----------
        space_name : str
            Name des Media Space (Pflicht)

        Returns
        -------
        ArkResult
            data ist die Liste der passenden Backups, leer wenn keins
            passt

        Notes
        -----
        Dokumentierte Statuscodes: 200, siehe get_backups()
        """

        return self._filter_backups("media_space_name", space_name)

    def find_backups_by_space_uuid(self, space_uuid):
        """Alle Backups eines Media Space ueber die UUID finden

        Ruft get_backups() auf und filtert die Liste.

        Parameters
        ----------
        space_uuid : str
            UUID des Media Space (Pflicht)

        Returns
        -------
        ArkResult
            data ist die Liste der passenden Backups

        Notes
        -----
        Dokumentierte Statuscodes: 200, siehe get_backups()
        """

        return self._filter_backups("media_space_uuid", str(space_uuid))

    def find_backup(self, backup_id):
        """Ein einzelnes Backup ueber seine ID finden

        Ruft get_backups() auf und filtert die Liste.

        Parameters
        ----------
        backup_id : str
            Die Backup-ID (Pflicht), z. B. "ark.tapeserver_f541..."

        Returns
        -------
        ArkResult
            data ist der passende Eintrag oder ein leeres dict

        Notes
        -----
        Dokumentierte Statuscodes: 200, siehe get_backups().
        Ein leeres data bei code 200 heisst: ID nicht gefunden
        """

        result = self._filter_backups("backup_id", backup_id)
        result.data = result.data[0] if result.data else {}
        return result

    def _filter_backups(self, field, value):
        """get_backups() holen und nach einem Feld filtern

        Returns
        -------
        ArkResult
            data ist die gefilterte Liste, bei Fehlern leer
        """

        result = self.get_backups()
        if result.code != 200:
            result.data = []
            return result

        result.data = [
            backup
            for backup in result.data or []
            if backup.get(field) == value
        ]
        return result

    def search_all_backups(
        self,
        search_pattern,
        search_mode="contains",
        *,
        backup_type=None,
        page_size=1000,
        max_results=0,
    ):
        """Alle Treffer einer Suche seitenweise holen

        Ruft search_backups() so oft auf, bis total_matches erreicht ist.

        Parameters
        ----------
        search_pattern : str
            Dateiname oder Muster (Pflicht)
        search_mode : str
            Optional, Standard contains. exact, contains, wildcard oder
            flow_hash
        backup_type : str
            Optional. disk oder tape, ohne Angabe beide
        page_size : int
            Optional, Standard 1000. Treffer pro Request, 1 bis 10000
        max_results : int
            Optional, Standard 0. Abbruch nach dieser Trefferzahl,
            0 holt alles

        Returns
        -------
        ArkResult
            data ist die Liste aller Treffer. Bricht eine Seite mit
            einem anderen Code als 200 ab, kommt deren Ergebnis zurueck
            und data enthaelt nur die bis dahin gesammelten Treffer

        Notes
        -----
        Dokumentierte Statuscodes: 200, 400, siehe search_backups()
        """

        results = []
        offset = 0
        result = None

        while True:
            result = self.search_backups(
                search_pattern,
                search_mode,
                backup_type=backup_type,
                limit=page_size,
                offset=offset,
            )
            if result.code != 200:
                result.data = results
                return result

            payload = result.data if isinstance(result.data, dict) else {}
            page = payload.get("results", [])
            if not page:
                break

            results += page
            offset += len(page)

            if max_results and len(results) >= max_results:
                results = results[:max_results]
                break

            if offset >= int(payload.get("total_matches", 0)):
                break

        result.data = results
        return result

    # --------- COMFORT RESTORE JOBS ---------

    def check_hashes_restorable(self, hashes):
        """Vor einem Hash-Restore pruefen, welche Hashes restaurierbar sind

        Ruft get_file_statuses() auf und, wenn Kopien auf Tape liegen,
        get_tapes(). Hilft gegen das Alles-oder-nichts von
        restore_hashes(): ein einziger nicht restaurierbarer Hash laesst
        dort den ganzen Auftrag scheitern.

        Parameters
        ----------
        hashes : list
            Liste von FLOW-Hashes (Pflicht), Version 0, 1 oder 2

        Returns
        -------
        ArkResult
            data ist bei 200 ein dict je angefragtem Hash mit

                in_ark          bool, Ark haelt mindestens eine Kopie
                tapes           list, Barcodes aller Kopien
                offline_tapes   list, davon nicht in der Library
                restorable      bool, mindestens eine Kopie ohne Tape
                                oder mit allen Tapes in der Library

            Sonst das Ergebnis des gescheiterten Requests mit leerem dict

        Notes
        -----
        Codes wie get_file_statuses() und get_tapes()
        """

        hash_list = [str(flow_hash) for flow_hash in hashes]
        result = self.get_file_statuses(hash_list)
        if result.code != 200:
            result.data = {}
            return result

        copies_by_hash = {}
        for match in result.data or []:
            copies_by_hash.setdefault(
                str(match.get("hash", "")).casefold(), []
            ).append(self.tapes_from_file_status(match))

        online = set()
        if any(any(copies) for copies in copies_by_hash.values()):
            tapes = self.get_tapes()
            if tapes.code != 200:
                tapes.data = {}
                return tapes
            online = {
                tape.get("barcode") for tape in tapes.data if tape.get("in_changer")
            }

        report = {}
        for flow_hash in hash_list:
            copies = copies_by_hash.get(flow_hash.casefold(), [])
            needed = list(dict.fromkeys(b for copy in copies for b in copy))
            report[flow_hash] = {
                "in_ark": bool(copies),
                "tapes": needed,
                "offline_tapes": [b for b in needed if b not in online],
                "restorable": any(
                    all(b in online for b in copy) for copy in copies
                ),
            }

        result.data = report
        return result

    def get_restore_job_status(self, job_id):
        """Einen Restore-Job in den Job-Listen der WebUI finden

        Sucht nacheinander in get_active_jobs(), get_job_queue(),
        get_completed_jobs() und get_inactive_jobs(). Ein Eintrag passt,
        wenn seine id gleich job_id ist oder mit job_id plus Bindestrich
        beginnt. So findet die ID aus restore_backups() bzw. die
        session_guid aus restore_hashes(), z. B. "restorejob_80XIRz",
        auch den Lauf "restorejob_80XIRz-__restorejob__---2026-9-4-...".

        Parameters
        ----------
        job_id : str
            ID des Restore-Jobs (Pflicht)

        Returns
        -------
        ArkResult
            data ist bei 2xx {"state": ..., "job": ...} mit state
            "active", "queued", "completed" oder "inactive" und job als
            Eintrag der WebUI-Liste. Ein leeres dict heisst: nicht
            gefunden. Scheitert eine Liste, kommt deren Ergebnis mit
            leerem dict zurueck

        Notes
        -----
        inofficial. Bekannt ist nur das Format von /job/active. Jede
        Liste von dicts in der Antwort wird als Job-Liste gelesen
        """

        result = None
        for state, method in self._JOB_LISTS:
            result = getattr(self, method)()
            if not 200 <= result.code < 300:
                result.data = {}
                return result
            for entry in self._job_entries(result.data):
                entry_id = self._job_id(entry)
                if entry_id == job_id or entry_id.startswith(job_id + "-"):
                    result.data = {"state": state, "job": entry}
                    return result

        result.data = {}
        return result

    def get_restore_job_errors(self, job_id, job_type=None):
        """Fehlermeldungen eines Restore-Jobs sammeln

        Findet den Job ueber get_restore_job_status() und holt
        get_job_details(). Gesammelt werden alle Texte unter Schluesseln,
        die error, fail, warn oder alert enthalten, aus dem Listeneintrag
        und den Details.

        Parameters
        ----------
        job_id : str
            ID des Restore-Jobs (Pflicht)
        job_type : str
            Optional. Job-Typ fuer get_job_details(). Standard ist der Teil
            der gefundenen ID vor dem ersten Unterstrich, z. B. restorejob

        Returns
        -------
        ArkResult
            data ist {"state": ..., "errors": [...]}, errors ohne
            Duplikate in Fundreihenfolge. Ein leeres dict heisst: Job nicht
            gefunden. Scheitert get_job_details(), kommt dessen Ergebnis
            zurueck, errors dann nur aus dem Listeneintrag

        Notes
        -----
        inofficial. Die Auswahl der Schluessel ist eine Annahme, solange
        das Format der Details nicht bekannt ist
        """

        result = self.get_restore_job_status(job_id)
        if not 200 <= result.code < 300 or not result.data:
            return result

        state, job = result.data["state"], result.data["job"]
        entry_id = self._job_id(job)
        details = self.get_job_details(
            job_type or entry_id.split("_", 1)[0], entry_id
        )
        sources = [job]
        if 200 <= details.code < 300:
            sources.append(details.data)
        details.data = {"state": state, "errors": self._collect_messages(sources)}
        return details

    def stop_restore_job(self, job_id, *, timeout=30, poll_seconds=2):
        """Einen laufenden Restore-Job stoppen und das Ergebnis pruefen

        Findet den Lauf ueber get_restore_job_status(), ruft stop_job()
        mit dessen ID auf und fragt den Status erneut ab, bis der Job
        nicht mehr laeuft oder timeout erreicht ist.

        Parameters
        ----------
        job_id : str
            ID des Restore-Jobs (Pflicht)
        timeout : float
            Optional, Standard 30. Sekunden, die auf das Stoppen gewartet
            wird
        poll_seconds : float
            Optional, Standard 2. Abstand der Statusabfragen

        Returns
        -------
        ArkResult
            data ist {"stopped": bool, "state": str}. state ist der
            letzte gefundene Zustand, "" wenn der Job nicht mehr in den
            Listen steht. Laeuft der Job nicht, ist stopped False und
            nichts wurde gesendet. Scheitert ein Request, kommt dessen
            Ergebnis zurueck

        Notes
        -----
        inofficial
        """

        result = self.get_restore_job_status(job_id)
        if not 200 <= result.code < 300:
            return result

        state = result.data.get("state", "")
        if state != "active":
            result.data = {"stopped": False, "state": state}
            result.message = "Job laeuft nicht"
            return result

        stop = self.stop_job(self._job_id(result.data["job"]))
        if not 200 <= stop.code < 300:
            stop.data = {"stopped": False, "state": state}
            return stop

        deadline = time.monotonic() + timeout
        while True:
            result = self.get_restore_job_status(job_id)
            if not 200 <= result.code < 300:
                return result
            state = result.data.get("state", "")
            if state != "active" or time.monotonic() >= deadline:
                break
            time.sleep(poll_seconds)

        result.data = {"stopped": state != "active", "state": state}
        return result

    _JOB_LISTS = (
        ("active", "get_active_jobs"),
        ("queued", "get_job_queue"),
        ("completed", "get_completed_jobs"),
        ("inactive", "get_inactive_jobs"),
    )

    _ERROR_WORDS = ("error", "fail", "warn", "alert")

    @staticmethod
    def _job_entries(payload):
        """Job-Eintraege aus einer Antwort der WebUI ziehen

        Liest eine Liste direkt, aus einem dict jede Liste darin. Ein dict
        aus dicts gilt als Liste mit dem Schluessel als Ersatz-ID.
        """

        if isinstance(payload, list):
            return [entry for entry in payload if isinstance(entry, dict)]
        if not isinstance(payload, dict):
            return []
        entries = []
        for key, value in payload.items():
            if isinstance(value, list):
                entries += [entry for entry in value if isinstance(entry, dict)]
            elif isinstance(value, dict):
                entries.append({"id": key, **value})
        return entries

    @staticmethod
    def _job_id(entry):
        """ID eines Job-Eintrags, id oder ersatzweise job_id"""

        return str(entry.get("id") or entry.get("job_id") or "")

    @classmethod
    def _collect_messages(cls, payload, hit=False):
        """Texte unter Fehler-Schluesseln rekursiv sammeln, ohne Duplikate"""

        if isinstance(payload, str):
            return [payload.strip()] if hit and payload.strip() else []
        if isinstance(payload, dict):
            items = payload.items()
        elif isinstance(payload, list):
            items = ((None, value) for value in payload)
        else:
            return []

        messages = []
        for key, value in items:
            key_hit = hit or (
                key is not None
                and any(word in str(key).casefold() for word in cls._ERROR_WORDS)
            )
            messages += cls._collect_messages(value, key_hit)
        return list(dict.fromkeys(messages))


# --------- KEEP THIS LINE AT THE END ---------
# Explizit gepflegt, nicht ueber dir() erzeugt: ein zur Laufzeit
# gebautes __all__ kann weder ein Type Checker auswerten (Pylance sieht
# Ark dann nicht als Export von ArkAPI) noch Python vor 3.12 korrekt
# fuellen, weil Comprehensions dort einen eigenen Scope haben und dir()
# nur deren lokale Namen liefert. Neuer oeffentlicher Name: hier
# eintragen.
__all__ = [
    "ARK_VERSION",
    "Ark",
    "ArkResult",
]
