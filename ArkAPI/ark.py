"""
Wrapper fuer die EditShare Ark API.

Spezifikation:
https://developers.editshare.com/?urls.primaryName=EditShare%20Ark

"""

# --------- IMPORTS ---------

import json
import logging

from FlowAPI.core import Connection

# --------- STATIC ---------

ARK_VERSION = "0.1.1"
__version__ = ARK_VERSION


# --------- RESULT ---------
class ArkResult:
    """Ergebnis eines Ark-Requests

    Reicht den Statuscode unveraendert durch. Welche Codes eine Methode
    liefern kann und was sie bedeuten, steht in deren Docstring.

    Attributes
    ----------
    code : int
        Der HTTP-Statuscode der Antwort. 0 wenn keine Verbindung zustande
        kam
    data : object
        Die Nutzdaten. Bei 400 und 404 der jeweilige Leerwert der Methode
    message : str
        Lesbarer Text, immer eine Zeichenkette. Bei Fehlern das
        details-Feld der API, sonst die Beschreibung des Codes aus der
        Spezifikation. Ist details ein Objekt, steht es hier als JSON
    error : str
        Maschinenlesbare Fehlerkennung der API, 1:1 uebernommen, z. B.
        INVALID_HASH. Welche Werte ein Endpunkt liefern kann, steht in
        dessen Docstring. Die Spezifikation fuehrt sie nur als Beispiel
        und nicht als enum, die Liste kann also wachsen. Leer wenn die
        Antwort kein Fehler-Objekt war

    Mehr gibt es nicht. Welche Codes ein Endpunkt kennt, steht im
    Docstring der jeweiligen Methode und in der README.
    """

    def __init__(self, code, *, data=None, message="", error=""):
        self.code = int(code)
        self.data = data
        self.message = message
        self.error = error

    def __str__(self):
        return "{} {}".format(self.code, self.message)

    def __repr__(self):
        return "ArkResult(code={}, message={!r})".format(
            self.code, self.message
        )


# --------- CLASS ---------
class Ark(Connection):
    """Kapselt die zehn Operationen des Ark-Service

    Oeffentliche Endpunkt-Methoden, je eine pro Operation der
    Spezifikation:

        get_backups                     GET  /restore/backups
        restore_backups                 POST /restore/restoreBackups
        restore_hashes                  POST /restore/hashes
        get_file_hash_database_status   GET  /filestatus/database
        get_file_status                 GET  /filestatus/{FileHash}
        has_file_status                 HEAD /filestatus/{FileHash}
        get_file_statuses               POST /filestatus/
        get_disk_search_status          GET  /backup/disk/search/status
        search_backups                  POST /backup/search
        get_tape_library_status         GET  /api/tape/library/tapes

    Dazu Komfort-Methoden, die auf diesen zehn aufsetzen und keinen
    eigenen Endpunkt kennen: restore_backup, restore_files_by_hash,
    search_by_flow_hash, search_all_backups, find_backup,
    find_backups_by_space_name, find_backups_by_space_uuid, get_tapes,
    find_tape und tapes_from_file_status.
    """

    def __init__(self):
        super().__init__()
        self._service_name = "ark"

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

        return Connection.connect2(self, ip_addr, 8000, username, password)

    # --------- INTERN ---------

    def _read_error(self):
        """Fehlerobjekt der API aus dem letzten Body lesen

        Die Spezifikation definiert fuer jeden Fehler dasselbe Schema
        EditShareHTTPError mit den Pflichtfeldern code, error und
        details.

        Das Schema deklariert details als Zeichenkette zur Anzeige beim
        Menschen. Das Beispiel zum 404 von POST /restore/hashes
        widerspricht dem eigenen Schema und zeigt dort ein Objekt mit
        der Liste der gescheiterten Hashes. Kommt ein solches Objekt,
        wird es als JSON serialisiert. So bleibt message immer eine
        Zeichenkette und es geht nichts verloren. Leere Werte wie null
        oder ein leeres Objekt werden dabei zu einem leeren Text, damit
        message auf die Beschreibung des Codes zurueckfallen kann.

        error dagegen wird verworfen, wenn es keine Zeichenkette ist.
        Das Feld ist die maschinenlesbare Kennung und wird mit ==
        verglichen, ein JSON-Text darin waere irrefuehrend.

        Returns
        -------
        tuple
            (error, details), beide str. error ist leer wenn der Body
            kein EditShareHTTPError war oder die Kennung kein Text ist
        """

        body = self.lastResponse()
        if not body:
            return "", ""

        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            return "", ""

        if not isinstance(payload, dict):
            return "", ""

        error = payload.get("error", "")
        details = payload.get("details", "")

        if not isinstance(error, str):
            error = ""
        if not isinstance(details, str):
            details = json.dumps(
                details, ensure_ascii=False) if details else ""

        return error, details

    def _request(self, verb, endpoint, data=None, *, codes, default=None):
        """Request ausfuehren und den Statuscode unveraendert durchreichen

        Anders als getThatReturnsObj() aus FlowAPI.core wird der Body
        nicht blind durch json.loads() geschickt. Bricht die Verbindung
        weg, laesst core den alten Statuscode stehen und legt eine
        Klartext-Meldung in den Body - das wuerde sonst als
        JSONDecodeError durchschlagen.

        Parameters
        ----------
        verb : str
            GET, POST oder HEAD
        endpoint : str
            Pfad ohne Host
        data : object
            Optionaler Request-Body
        codes : dict
            Die von diesem Endpunkt dokumentierten Codes und ihre
            Bedeutung laut Spezifikation. Ein Code, der hier fehlt, gilt
            fuer diesen Endpunkt als undokumentiert
        default : object
            Nutzdaten, wenn kein verwertbarer Body vorliegt

        Returns
        -------
        ArkResult
            Der Statuscode wird nur durchgereicht, nicht bewertet. Bei
            200 steht der geparste Body in data, sonst der Leerwert.
            Laesst sich ein Body bei 200 nicht parsen, ist code 0
        """

        if verb == "GET":
            reply = self.get(endpoint)
        elif verb == "POST":
            reply = self.post(endpoint, data)
        elif verb == "HEAD":
            # core kennt kein head(), do_request() ist aber verb-agnostisch
            reply = self.do_request("HEAD", endpoint, "")
        else:
            raise ValueError("nicht unterstuetztes Verb: {}".format(verb))

        code = self.lastReturnCode()
        error, details = self._read_error()

        if code != 200:
            return ArkResult(
                code,
                data=default,
                error=error,
                message=details
                or codes.get(code, "")
                or "Statuscode {} ist fuer diesen Endpunkt nicht "
                "dokumentiert: {}".format(
                    code, str(reply or "").strip()[:160]
                ),
            )

        payload = default
        if reply and str(reply).strip():
            try:
                payload = json.loads(reply)
            except (ValueError, TypeError):
                # Typischer Fall: die Verbindung ist weggebrochen, core
                # hat den alten Statuscode stehen gelassen und eine
                # Klartext-Meldung in den Body gelegt. Der Code luegt.
                return ArkResult(
                    0,
                    data=default,
                    error=error,
                    message="Antwort ist kein gueltiges JSON, Statuscode {} "
                    "unglaubwuerdig (Verbindungsabbruch?): {}".format(
                        code, str(reply).strip()[:160]
                    ),
                )

        return ArkResult(
            code, data=payload, error=error, message=codes.get(200, "")
        )

    # --------- RESTORE ---------

    def get_backups(self):
        """Liste aller in Ark gespeicherten Backups holen

        GET /restore/backups

        Returns
        -------
        ArkResult
            data ist die Liste der Backups auf Ark Disk und Ark Tape.
            Jeder Eintrag enthaelt u. a. backup_id, backup_type, date,
            media_space_name, media_space_uuid und destination_name

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            A list of backups managed by Ark available for restoration.
            data ist die Liste, bei keinen Backups leer
        """

        return self._request(
            "GET",
            "/restore/backups",
            codes={
                200: "A list of backups managed by Ark available for "
                "restoration."
            },
            default=[],
        )

    def restore_backups(self, data):
        """Backups aus Ark auf ein Storage-Ziel zurueckspielen

        POST /restore/restoreBackups

        Parameters
        ----------
        data : dict
            Das Restore-Kommando (Pflicht). Pflichtfelder backups und
            target_data, optional storage_goals und restoreTime, z. B.

                {
                    "backups": [{"backup_id": "ark.tapeserver_f541..."}],
                    "target_data": {
                        "ms_target": "esa_IBN1e---es-master---/efs/efs_1"
                    },
                }

        Returns
        -------
        ArkResult
            data ist die ID des neuen Restore-Jobs, z. B.
            "restorejob_sovh0C". Der Service antwortet mit einem reinen
            JSON-String, nicht mit einem Objekt

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Restoration job queued. data ist die Job-ID
        """

        return self._request(
            "POST",
            "/restore/restoreBackups",
            data,
            codes={200: "Restoration job queued."},
            default="",
        )

    def restore_hashes(self, data):
        """Einzelne Dateien anhand ihrer FLOW-Hashes zurueckspielen

        POST /restore/hashes

        Parameters
        ----------
        data : dict
            Das Restore-Kommando (Pflicht). Pflichtfelder files und
            destination, optional source, z. B.

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
        ArkResult
            data ist bei 200 das Antwortobjekt mit session_guid, sonst
            ein leeres dict

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Hash-based restore job created successfully. data enthaelt
            session_guid zum Verfolgen des Jobs
        400
            Bad Request - Invalid hash format, invalid destination, or
            malformed request. error ist INVALID_HASH,
            INVALID_DESTINATION, INVALID_SOURCE oder
            MISSING_REQUIRED_FIELD
        404
            Not Found - One or more hashes cannot be restored. error ist
            HASHES_NOT_RESTORABLE. Entweder liegt zu mindestens einem
            Hash kein Backup vor, oder das benoetigte Tape ist offline.
            Es gilt alles oder nichts: ein einziger nicht
            restaurierbarer Hash laesst den ganzen Auftrag scheitern

        Nur hier zeigt die Spezifikation fuer details ein Objekt statt
        der laut Schema vorgeschriebenen Zeichenkette: es listet unter
        files jeden gescheiterten Hash mit eigener Begruendung. message
        traegt dieses Objekt dann als JSON. Wer die Eintraege einzeln
        braucht, liest den Rohbody ueber last_response()
        """

        return self._request(
            "POST",
            "/restore/hashes",
            data,
            codes={
                200: "Hash-based restore job created successfully.",
                400: "Bad Request - Invalid hash format, invalid "
                "destination, or malformed request.",
                404: "Not Found - One or more hashes cannot be restored.",
            },
            default={},
        )

    # --------- FILESTATUS ---------

    def get_file_hash_database_status(self):
        """Status des Hash-Imports in die Ark-Datenbank abfragen

        GET /filestatus/database

        Returns
        -------
        ArkResult
            data enthaelt status (importing, complete oder error),
            progress_complete und progress_estimated

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Status of the file hash database. data ist das Statusobjekt
        """

        return self._request(
            "GET",
            "/filestatus/database",
            codes={200: "Status of the file hash database"},
            default={},
        )

    def get_file_status(self, flow_hash):
        """Ark Backup-Status einer Datei anhand ihres Hashes abfragen

        GET /filestatus/{FileHash}

        Parameters
        ----------
        flow_hash : str
            Ein FLOW-Hash (Pflicht). Version 0 ("<md5>"), Version 1
            ("1:<md5>") und Version 2 ("2:<md5>") werden unterstuetzt.
            Siehe CLI-Kommando: flow-hash

        Returns
        -------
        ArkResult
            data ist bei 200 die Liste der Treffer mit hash,
            storage_type, job_id, job_time, file_id, pathname, filename,
            space_uuid, space_name und tapes, sonst eine leere Liste

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            A list of statuses for files managed by Ark. Ark haelt
            mindestens eine Kopie
        400
            Hash is invalid. error ist INVALID_HASH, der Hash passt
            nicht auf das Muster (1:|2:|)[A-Fa-f0-9]{32}
        404
            No matches found. error ist HASH_NOT_FOUND, Ark haelt keine
            Kopie dieser Datei

        Achtung: 404 ist eine Fachauskunft, kein Transportfehler. Wer
        daran eine Loeschentscheidung haengt, muss 400 und 404
        unterscheiden - beide liefern eine leere data
        """

        url = "/filestatus/" + self.safe_url_string(str(flow_hash))
        return self._request(
            "GET",
            url,
            codes={
                200: "A list of statuses for files managed by Ark",
                400: "Hash is invalid",
                404: "No matches found",
            },
            default=[],
        )

    def has_file_status(self, flow_hash):
        """Nur pruefen ob Ark eine Kopie hat, ohne Details zu holen

        HEAD /filestatus/{FileHash}

        Die guenstige Variante von get_file_status(): der Service
        antwortet ohne Body, nur mit dem Statuscode. Fuer Schleifen ueber
        viele Dateien deutlich sparsamer.

        Parameters
        ----------
        flow_hash : str
            Ein FLOW-Hash (Pflicht), Version 0, 1 oder 2

        Returns
        -------
        ArkResult
            data ist immer None, HEAD liefert keinen Body. Die Auskunft
            steckt allein im Statuscode

        Notes
        -----
        Dokumentierte Statuscodes:

        204
            One or more matches found. Ark haelt mindestens eine Kopie
        400
            Invalid hash. Der Hash passt nicht auf das Muster
        404
            No matches found. Ark haelt keine Kopie dieser Datei

        Diese Operation liefert kein 200. Ein Vergleich auf 200 geht hier
        also immer schief - auf 204 pruefen

        Keiner der drei Codes hat einen Body, darum sind error und data
        hier immer leer. Die Auskunft steckt allein im Code
        """

        url = "/filestatus/" + self.safe_url_string(str(flow_hash))
        return self._request(
            "HEAD",
            url,
            codes={
                204: "One or more matches found",
                400: "Invalid hash",
                404: "No matches found",
            },
        )

    def get_file_statuses(self, hash_list):
        """Ark Backup-Status fuer eine Liste von Hashes abfragen

        POST /filestatus/

        Parameters
        ----------
        hash_list : list
            Liste von FLOW-Hashes (Pflicht), Version 0, 1 oder 2

        Returns
        -------
        ArkResult
            data ist bei 200 die Liste der Treffer, siehe
            get_file_status(), sonst eine leere Liste

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            A list of statuses for files managed by Ark. Die Liste kann
            leer sein, wenn zu keinem Hash eine Kopie vorliegt
        400
            Hash is invalid. error ist INVALID_HASH, mindestens ein Hash
            der Liste passt nicht auf das Muster

        Diese Operation kennt kein 404. Hashes ohne Kopie fehlen
        einfach im Ergebnis, ein Abgleich mit hash_list zeigt also,
        welche Dateien nicht in Ark liegen
        """

        # Der abschliessende Slash ist hier Pflicht, der Body ist ein
        # reines String-Array
        return self._request(
            "POST",
            "/filestatus/",
            list(hash_list),
            codes={
                200: "A list of statuses for files managed by Ark",
                400: "Hash is invalid",
            },
            default=[],
        )

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

    # --------- BACKUP SEARCH ---------

    def get_disk_search_status(self):
        """Indexierungsstatus der Disk-Backups abfragen

        GET /backup/disk/search/status

        Returns
        -------
        ArkResult
            data enthaelt total, indexed, indexing, not_indexed,
            needs_indexing und total_files

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Disk backup indexing status. data ist das Statusobjekt

        Nur indexierte Disk-Backups sind ueber search_backups()
        auffindbar, daher vor einer Suche pruefen
        """

        return self._request(
            "GET",
            "/backup/disk/search/status",
            codes={200: "Disk backup indexing status"},
            default={},
        )

    def search_backups(
        self,
        search_pattern,
        search_mode="contains",
        *,
        backup_type=None,
        limit=100,
        offset=0,
    ):
        """Dateien in den indexierten Backups suchen

        POST /backup/search

        Parameters
        ----------
        search_pattern : str
            Dateiname oder Muster (Pflicht). Bei search_mode flow_hash
            ein FLOW-Hash der Version 2
        search_mode : str
            Optional, Standard "contains". Erlaubt sind "exact",
            "contains", "wildcard" und "flow_hash"
        backup_type : str
            Optional. "disk" oder "tape", ohne Angabe werden beide
            durchsucht
        limit : int
            Optional, Standard 100. Maximale Trefferzahl, 1 bis 10000
        offset : int
            Optional, Standard 0. Anzahl zu ueberspringender Treffer

        Returns
        -------
        ArkResult
            data enthaelt bei 200 total_matches, limit, offset und
            results, sonst ein leeres dict

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Search results with pagination information. results kann
            leer sein, total_matches nennt die Gesamtzahl
        400
            Hash is invalid. error ist INVALID_HASH. Tritt bei
            search_mode flow_hash auf, wenn search_pattern kein
            gueltiger Hash ist
        """

        data = {
            "search_pattern": search_pattern,
            "search_mode": search_mode,
            "limit": limit,
            "offset": offset,
        }

        if backup_type:
            data["backup_type"] = backup_type

        return self._request(
            "POST",
            "/backup/search",
            data,
            codes={
                200: "Search results with pagination information",
                400: "Hash is invalid",
            },
            default={},
        )

    # --------- TAPE LIBRARY ---------

    def get_tape_library_status(self):
        """Status der Tape Library inklusive Inventar holen

        GET /api/tape/library/tapes

        Returns
        -------
        ArkResult
            data enthaelt tapes und timestamp

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Tape library status with complete inventory. data ist das
            Statusobjekt
        """

        return self._request(
            "GET",
            "/api/tape/library/tapes",
            codes={200: "Tape library status with complete inventory"},
            default={},
        )

    # --------- COMFORT ---------

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


# --------- KEEP THIS LINE AT THE END ---------
__all__ = [
    name
    for name in dir()
    if name.startswith(("Ark", "ARK_", "create_"))
]
