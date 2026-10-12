"""
Offizielle Endpunkte der Ark API, je eine Methode pro Operation.

Spezifikation:
https://developers.editshare.com/?urls.primaryName=EditShare%20Ark
"""

# --------- IMPORTS ---------

from ._core import ArkCore


# --------- CLASS ---------
class OfficialMixin(ArkCore):
    """Die Operationen der Spezifikation, je eine Methode pro Endpunkt"""

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

    # --------- TAPE POOLS ---------

    def get_tape_pools(self):
        """Alle Tape-Pools aller Ark-Tape-Server holen

        GET /tape/pools

        Returns
        -------
        ArkResult
            data ist ein dict je server_id, darin je pool_id ein dict mit
            name und tapes (Barcodes). Sonst ein leeres dict

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            All tape pools, grouped by the Ark Tape server that owns them
        """

        return self._request(
            "GET",
            "/tape/pools",
            codes={
                200: "All tape pools, grouped by the Ark Tape server that "
                "owns them"
            },
            default={},
        )

    def get_tape_pool(self, pool_id):
        """Einen Tape-Pool ueber seine ID holen

        GET /tape/pool/{pool_id}

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht), z. B. "poolid-1-1700000000"

        Returns
        -------
        ArkResult
            data enthaelt bei 200 pool_id und pool_name, sonst ein leeres
            dict

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Identity of a single tape pool
        404
            No pool matches the given pool_id. error ist POOL_NOT_FOUND
        """

        return self._request(
            "GET",
            self._path("tape", "pool", pool_id),
            codes={
                200: "Identity of a single tape pool",
                404: "No pool matches the given pool_id",
            },
            default={},
        )

    def create_tape_pool(self, name, server):
        """Einen leeren Tape-Pool auf einem Ark-Tape-Server anlegen

        PUT /tape/pool

        Parameters
        ----------
        name : str
            Name des Pools (Pflicht), eindeutig ueber alle Tape-Ziele
        server : str
            ID des Ark-Tape-Servers (Pflicht), z. B.
            "ark.tapeserver_d8ce43f0-..."

        Returns
        -------
        ArkResult
            data ist bei 200 die ID des neuen Pools als str, z. B.
            "poolid-1-1700000000", sonst ""

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Identifier of the newly created pool
        400
            A pool with the requested name already exists. error ist
            POOL_EXISTS
        """

        return self._request(
            "PUT",
            "/tape/pool",
            {"name": name, "server": server},
            codes={
                200: "Identifier of the newly created pool",
                400: "A pool with the requested name already exists",
            },
            default="",
        )

    def rename_tape_pool(self, pool_id, name):
        """Einen Tape-Pool umbenennen

        PATCH /tape/pool/{pool_id}

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        name : str
            Neuer Name (Pflicht), eindeutig ueber alle Tape-Ziele

        Returns
        -------
        ArkResult
            data ist immer None, die Auskunft steckt im Code

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Pool renamed successfully
        400
            A pool with the requested name already exists. error ist
            POOL_EXISTS
        404
            No pool matches the given pool_id. error ist POOL_NOT_FOUND
        """

        return self._request(
            "PATCH",
            self._path("tape", "pool", pool_id),
            {"name": name},
            codes={
                200: "Pool renamed successfully",
                400: "A pool with the requested name already exists",
                404: "No pool matches the given pool_id",
            },
        )

    def delete_tape_pool(self, pool_id):
        """Einen Tape-Pool loeschen

        DELETE /tape/pool/{pool_id}

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)

        Returns
        -------
        ArkResult
            data ist immer None, die Auskunft steckt im Code

        Notes
        -----
        Dokumentierte Statuscodes:

        200
            Pool deleted
        404
            No pool matches the given pool_id. error ist POOL_NOT_FOUND
        """

        return self._request(
            "DELETE",
            self._path("tape", "pool", pool_id),
            codes={
                200: "Pool deleted",
                404: "No pool matches the given pool_id",
            },
        )
