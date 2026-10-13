"""
Offizielle Endpunkte der Ark API.

Spezifikation:
https://developers.editshare.com/?urls.primaryName=EditShare%20Ark
"""

# --------- IMPORTS ---------

from .core import ArkCore, ArkResult, Progress

# --------- STATIC ---------

_SPACE_TYPES = ("ms", "ps", "priv", "fe", "es", "flow")
_SEARCH_MODES = ("exact", "contains", "wildcard", "flow_hash")
_SEARCH_LIMIT = 10000
_SEARCH_PAGE = 1000

_RESTORE_HASHES_CODES = {
    200: "Hash-based restore job created successfully.",
    400: "Bad Request - Invalid hash format, invalid destination, or "
    "malformed request.",
    404: "Not Found - One or more hashes cannot be restored.",
}
_FILESTATUS_CODES = {
    200: "A list of statuses for files managed by Ark",
    400: "Hash is invalid",
}
_SEARCH_CODES = {
    200: "Search results with pagination information",
    400: "Hash is invalid",
}
_POOL_EXISTS = "A pool with the requested name already exists"
_POOL_NOT_FOUND = "No pool matches the given pool_id"


# --------- CLASS ---------
class OfficialMixin(ArkCore):
    """Die Operationen der Spezifikation"""

    # --------- RESTORE ---------

    def get_backups(self) -> ArkResult:
        """Alle Backups auf Ark Disk und Ark Tape holen

        GET /restore/backups

        Returns
        -------
        ArkResult
            data ist die Liste der Backups mit u. a. backup_id,
            backup_type, date, media_space_name, media_space_uuid und
            destination_name

        Notes
        -----
        Codes: 200
        """

        return self._request(
            "GET",
            "/restore/backups",
            codes={
                200: "A list of backups managed by Ark available for restoration."
            },
            default=[],
        )

    def restore_backups(
        self,
        backups: str | dict | list,
        target: str,
        *,
        space_type: str = "ms",
        storage_goals: dict | None = None,
        restore_date: str | None = None,
        restore_time: str | None = None,
        on_progress: Progress = print,
        progress_seconds: float = 30,
    ) -> ArkResult:
        """Ein oder mehrere ganze Backups zurueckspielen - ungetestet

        POST /restore/restoreBackups

        Parameters
        ----------
        backups : str | dict | list
            Backup-IDs oder Dicts {"backup_id": ..., "rename": ...,
            "cumulative": True} (Pflicht), siehe get_backups()
        target : str
            Restore-Ziel (Pflicht). Bei Media Spaces
            "<ESA-Gruppe>---<Member>---<Bit-Bucket-Pfad>", z. B.
            "esa_IBN1e---es-master---/efs/efs_1", sonst die ESA-Gruppe
        space_type : str
            "ms", "ps", "priv", "fe", "es" oder "flow", Standard "ms"
        storage_goals : dict
            Optional. Backup-ID -> EFS Storage Goal
        restore_date : str
            Optional. Termin im Format "10/21/2015"
        restore_time : str
            Optional. Uhrzeit im Format "03:00am"
        on_progress : callable
            Meldung, solange auf die Job-ID gewartet wird, Standard print,
            None = stumm
        progress_seconds : float
            Abstand der Meldungen, Standard 30

        Returns
        -------
        ArkResult
            data ist die Job-ID, z. B. "restorejob_sovh0C", sonst ""

        Notes
        -----
        Codes: 200
        """

        if space_type not in _SPACE_TYPES:
            raise ValueError(
                "space_type {!r} unbekannt, erlaubt: {}".format(
                    space_type, ", ".join(_SPACE_TYPES)
                )
            )
        self._seconds("progress_seconds", progress_seconds)
        entries = [backups] if isinstance(backups, (str, dict)) else list(backups or [])
        if not entries:
            raise ValueError("backups ist leer, mindestens ein Backup noetig")
        if any(isinstance(entry, dict) and not entry.get("backup_id") for entry in entries):
            raise ValueError("Jedes Dict in backups braucht eine backup_id")

        data = {
            "backups": [
                dict(entry) if isinstance(entry, dict) else {"backup_id": str(entry)}
                for entry in entries
            ],
            "target_data": {"{}_target".format(space_type): target},
        }
        if storage_goals:
            data["storage_goals"] = dict(storage_goals)
        restore_at = {
            key: value
            for key, value in (("date", restore_date), ("time", restore_time))
            if value
        }
        if restore_at:
            data["restoreTime"] = restore_at

        return self._in_background(
            lambda: self._request(
                "POST",
                "/restore/restoreBackups",
                data,
                codes={200: "Restoration job queued."},
                default="",
            ),
            "Warte auf Job-ID",
            on_progress,
            progress_seconds,
        )

    def _restore_hashes(self, data):
        """POST /restore/hashes mit fertigem Body, siehe restore_files()"""

        return self._request(
            "POST", "/restore/hashes", data, codes=_RESTORE_HASHES_CODES, default={}
        )

    # --------- FILESTATUS ---------

    def get_file_hash_database_status(self) -> ArkResult:
        """Stand des Hash-Imports in die Ark-Datenbank holen

        GET /filestatus/database

        Returns
        -------
        ArkResult
            data enthaelt status (importing, complete oder error),
            progress_complete und progress_estimated

        Notes
        -----
        Codes: 200
        """

        return self._request(
            "GET",
            "/filestatus/database",
            codes={200: "Status of the file hash database"},
            default={},
        )

    def get_file_status(self, hashes: str | list[str]) -> ArkResult:
        """Je Hash holen, ob und auf welchen Tapes Ark eine Kopie hat

        POST /filestatus/

        Parameters
        ----------
        hashes : str | list
            Ein FLOW-Hash oder eine Liste (Pflicht), Version 0 ("<md5>"),
            1 ("1:<md5>") oder 2 ("2:<md5>")

        Returns
        -------
        ArkResult
            data ist ein dict je angefragtem Hash mit

                in_ark    bool, Ark haelt mindestens eine Kopie
                copies    list, je Kopie die Liste ihrer Barcodes, leer
                          bei Disk-Backups
                matches   list, Rohtreffer mit space_name, pathname,
                          job_id usw., copies[i] gehoert zu matches[i]

            Sonst ein leeres dict

        Notes
        -----
        Codes: 200, 400 INVALID_HASH (mindestens ein Hash passt nicht auf
        (1:|2:|)[A-Fa-f0-9]{32})
        """

        hash_list = self._as_list(hashes, "hashes")
        # the trailing slash is required, the body is a plain string array
        result = self._request(
            "POST", "/filestatus/", hash_list, codes=_FILESTATUS_CODES, default=[]
        )
        if result.code != 200:
            result.data = {}
            return result

        found = {}
        for match in result.data if isinstance(result.data, list) else []:
            if isinstance(match, dict):
                found.setdefault(str(match.get("hash", "")).casefold(), []).append(match)

        result.data = {
            flow_hash: {
                "in_ark": bool(found.get(flow_hash.casefold())),
                "copies": [
                    self._barcodes(match) for match in found.get(flow_hash.casefold(), [])
                ],
                "matches": found.get(flow_hash.casefold(), []),
            }
            for flow_hash in hash_list
        }
        return result

    @staticmethod
    def _barcodes(match):
        """Barcodes eines filestatus-Treffers, leer bei Disk-Backups"""

        tapes = (
            (tape.get("barcode") or tape.get("name")) if isinstance(tape, dict) else tape
            for tape in match.get("tapes") or []
        )
        return [str(barcode) for barcode in tapes if barcode]

    # --------- SEARCH ---------

    def search_backups(
        self,
        pattern: str,
        mode: str = "contains",
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> ArkResult:
        """In den indexierten Backups suchen - ungetestet

        POST /backup/search

        Parameters
        ----------
        pattern : str
            Dateiname, Muster oder bei mode "flow_hash" ein FLOW-Hash der
            Version 2 (Pflicht)
        mode : str
            "exact", "contains", "wildcard" oder "flow_hash", Standard
            "contains"
        limit : int
            Treffer pro Anfrage, 1 bis 10000, Standard 100. 0 holt alle
            Seiten
        offset : int
            Zu ueberspringende Treffer, Standard 0

        Returns
        -------
        ArkResult
            data enthaelt total_matches, limit, offset und results, sonst
            ein leeres dict

        Notes
        -----
        Codes: 200, 400 INVALID_HASH (bei mode "flow_hash")
        """

        if mode not in _SEARCH_MODES:
            raise ValueError(
                "mode {!r} unbekannt, erlaubt: {}".format(mode, ", ".join(_SEARCH_MODES))
            )
        if not 0 <= limit <= _SEARCH_LIMIT:
            raise ValueError(
                "limit muss zwischen 0 und {} liegen, ist {}".format(_SEARCH_LIMIT, limit)
            )
        if limit:
            return self._search_page(pattern, mode, limit, offset)

        results = []
        while True:
            page = self._search_page(pattern, mode, _SEARCH_PAGE, offset + len(results))
            if page.code != 200:
                return page
            found = page.data.get("results") or []
            results += found
            total = int(page.data.get("total_matches") or 0)
            if not found or offset + len(results) >= total:
                page.data = {
                    "total_matches": total,
                    "limit": 0,
                    "offset": offset,
                    "results": results,
                }
                return page

    def _search_page(self, pattern, mode, limit, offset):
        """Eine Seite von search_backups(), data immer ein dict"""

        result = self._request(
            "POST",
            "/backup/search",
            {
                "search_pattern": pattern,
                "search_mode": mode,
                "limit": limit,
                "offset": offset,
            },
            codes=_SEARCH_CODES,
            default={},
        )
        if not isinstance(result.data, dict):
            result.data = {}
        return result

    # --------- TAPE LIBRARY ---------

    def get_tape_library_status(self) -> ArkResult:
        """Tape-Inventar der Library holen

        GET /api/tape/library/tapes

        Returns
        -------
        ArkResult
            data enthaelt timestamp und tapes, je Tape u. a. barcode,
            in_changer, slot, server_id, storage_name, storage_id und
            lto_generation

        Notes
        -----
        Codes: 200
        """

        return self._request(
            "GET",
            "/api/tape/library/tapes",
            codes={200: "Tape library status with complete inventory"},
            default={},
        )

    # --------- TAPE POOLS ---------

    def get_pools(self) -> ArkResult:
        """Alle Tape-Pools mit ihren Tapes holen

        GET /tape/pools

        Returns
        -------
        ArkResult
            data ist ein dict je server_id, darin je pool_id ein dict mit
            name und tapes (Barcodes)

        Notes
        -----
        Codes: 200
        """

        return self._request(
            "GET",
            "/tape/pools",
            codes={
                200: "All tape pools, grouped by the Ark Tape server that owns them"
            },
            default={},
        )

    def get_pool(self, pool_id: str) -> ArkResult:
        """Einen Tape-Pool holen - ungetestet

        GET /tape/pool/{pool_id}

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht), z. B. "poolid-1-1700000000"

        Returns
        -------
        ArkResult
            data enthaelt pool_id und pool_name, sonst ein leeres dict

        Notes
        -----
        Codes: 200, 404 POOL_NOT_FOUND
        """

        return self._request(
            "GET",
            self._path("tape", "pool", pool_id),
            codes={200: "Identity of a single tape pool", 404: _POOL_NOT_FOUND},
            default={},
        )

    def create_pool(self, name: str, server: str, *, confirm: bool = False) -> ArkResult:
        """Einen leeren Tape-Pool anlegen - ungetestet

        PUT /tape/pool

        Parameters
        ----------
        name : str
            Name des Pools (Pflicht), eindeutig ueber alle Tape-Ziele
        server : str
            ID des Ark-Tape-Servers (Pflicht), z. B.
            "ark.tapeserver_d8ce43f0-..."
        confirm : bool
            Muss True sein, sonst ValueError ohne Anfrage

        Returns
        -------
        ArkResult
            data ist die ID des neuen Pools, sonst ""

        Notes
        -----
        Codes: 200, 400 POOL_EXISTS
        """

        self._confirm(confirm, "create_pool")
        return self._request(
            "PUT",
            "/tape/pool",
            {"name": name, "server": server},
            codes={200: "Identifier of the newly created pool", 400: _POOL_EXISTS},
            default="",
        )

    def rename_pool(self, pool_id: str, name: str, *, confirm: bool = False) -> ArkResult:
        """Einen Tape-Pool umbenennen, erst ab Ark 2026.3 - ungetestet

        PATCH /tape/pool/{pool_id}

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        name : str
            Neuer Name (Pflicht), eindeutig ueber alle Tape-Ziele
        confirm : bool
            Muss True sein, sonst ValueError ohne Anfrage

        Returns
        -------
        ArkResult
            data ist None, die Auskunft steckt im Code

        Notes
        -----
        Codes: 200, 400 POOL_EXISTS, 404 POOL_NOT_FOUND
        """

        self._confirm(confirm, "rename_pool")
        return self._request(
            "PATCH",
            self._path("tape", "pool", pool_id),
            {"name": name},
            codes={
                200: "Pool renamed successfully",
                400: _POOL_EXISTS,
                404: _POOL_NOT_FOUND,
            },
        )

    def delete_pool(self, pool_id: str, *, confirm: bool = False) -> ArkResult:
        """Einen Tape-Pool loeschen - ungetestet

        DELETE /tape/pool/{pool_id}

        Parameters
        ----------
        pool_id : str
            ID des Pools (Pflicht)
        confirm : bool
            Muss True sein, sonst ValueError ohne Anfrage

        Returns
        -------
        ArkResult
            data ist None, die Auskunft steckt im Code

        Notes
        -----
        Codes: 200, 404 POOL_NOT_FOUND
        """

        self._confirm(confirm, "delete_pool")
        return self._request(
            "DELETE",
            self._path("tape", "pool", pool_id),
            codes={200: "Pool deleted", 404: _POOL_NOT_FOUND},
        )
