"""
Ark service API
See here: https://developers.editshare.com/?urls.primaryName=EditShare%20Ark
"""

import json
import logging
from FlowAPI.core import Connection, create_gateway_instance_inner, create_instance


try:
    # Newer core modules expose the Ark port directly
    from .core import ARK_PORT
except ImportError:  # pragma: no cover - fallback for older core modules
    ARK_PORT = 8000


class Ark(Connection):
    """Wraps the Ark service api"""

    # pylint: disable=too-many-public-methods

    #: Valid Ark backup sources / storage types
    SOURCE_DISK = "disk"
    SOURCE_TAPE = "tape"

    #: Valid search modes for search_backups()
    SEARCH_EXACT = "exact"
    SEARCH_CONTAINS = "contains"
    SEARCH_WILDCARD = "wildcard"
    SEARCH_FLOW_HASH = "flow_hash"

    def __init__(self):
        super().__init__()
        self._service_name = "ark"

    @staticmethod
    def create_instance(ip_addr, username, password):
        """Create and connect directly to service server"""

        return create_instance(Ark, ip_addr, username, password)

    @staticmethod
    def create_gateway_instance(username, password, ip_addr=None):
        """Create and connect to service via the local gateway"""

        return create_gateway_instance_inner(Ark, username, password, ip_addr)

    def connect(self, ip_addr, username, password):
        """Connect to service server"""

        return Connection.connect2(self, ip_addr, ARK_PORT, username, password)

    # ------------------------------------------------------------------
    # restore
    # ------------------------------------------------------------------

    def getBackups(self):
        """Retrieve a list of backups stored in Ark"""

        return self.get_backups()

    def get_backups(self):
        """Retrieve a list of backups stored in Ark

        Returns
        -------
        list
            A list of backups (Ark disk and Ark tape) available for
            restoration.  Each entry contains at least `backup_id`,
            `backup_type`, `date`, `media_space_name`, `media_space_uuid`
            and `destination_name`.
        """

        return self.getThatReturnsObj("/restore/backups")

    def find_backups_by_space_name(self, space_name):
        """Helper to find all backups of a media space by its name"""

        backups = self.get_backups()
        if not backups:
            return []

        return [
            backup
            for backup in backups
            if backup.get("media_space_name") == space_name
        ]

    def find_backups_by_space_uuid(self, space_uuid):
        """Helper to find all backups of a media space by its uuid"""

        backups = self.get_backups()
        if not backups:
            return []

        return [
            backup
            for backup in backups
            if backup.get("media_space_uuid") == str(space_uuid)
        ]

    def find_backup(self, backup_id):
        """Helper to find a single backup by its id"""

        backups = self.get_backups()
        if not backups:
            return {}

        for backup in backups:
            if backup.get("backup_id") == backup_id:
                return backup

        return {}

    def restoreBackups(self, data):
        """Restore backups from Ark to a storage location"""

        return self.restore_backups(data)

    def restore_backups(self, data):
        """Restore backups from Ark to a storage location

        Parameters
        ----------
        data : dict
            The restore command.  Requires `backups` and `target_data`,
            optionally `storage_goals` and `restoreTime`, e.g.::

                {
                    "backups": [{"backup_id": "ark.tapeserver_f541..."}],
                    "target_data": {
                        "ms_target": "esa_IBN1e---es-master---/efs/efs_1"
                    },
                }

        Returns
        -------
        str
            The id of the new restore job, e.g. 'restorejob_sovh0C'.
            False if the request failed.
        """

        reply = self.post("/restore/restoreBackups", json.dumps(data))
        if self.lastReturnCode() != 200:
            return False

        try:
            return json.loads(reply)
        except (TypeError, ValueError):
            return reply

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
        # pylint: disable=too-many-arguments
        """Helper to restore a single backup

        Parameters
        ----------
        backup_id : str
            The id of the backup to restore.  See get_backups()
        target : str
            The restore target.  For media spaces this is made up of three
            parts separated by three hyphens; ESA group, server group
            member and the path to the bit bucket, e.g.
            'esa_IBN1e---es-master---/efs/efs_1'.  For all other space
            types the ESA group is enough, e.g. 'esa_HiNbl'
        space_type : str
            One of 'ms', 'ps', 'priv', 'fe', 'es' or 'flow'
        rename : str
            Optional new name for the restored space
        cumulative : bool
            Restore every file of the incremental backup chain up to
            `backup_id`.  Ark Tape only
        storage_goal : str
            Optional EFS storage goal used for restored media spaces
        restore_date : str
            Optional schedule date, e.g. '10/21/2015'
        restore_time : str
            Optional schedule time, e.g. '03:00am'

        Returns
        -------
        str
            The id of the new restore job
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

    def restoreHashes(self, data):
        """Restore individual files by FLOW hash"""

        return self.restore_hashes(data)

    def restore_hashes(self, data):
        """Restore individual files by FLOW hash

        Parameters
        ----------
        data : dict
            The restore command.  Requires `files` and `destination`,
            optionally `source`, e.g.::

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
            The session guid of the new restore job.  False if the
            request failed.  Note that all supplied hashes have to be
            restorable, otherwise Ark replies with a 404
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
        """Helper to restore a list of FLOW hashes into a media space

        Parameters
        ----------
        hashes : list
            A list of FLOW hashes (version 2, i.e. '2:<md5>') or a list
            of dicts as expected by restore_hashes()
        mediaspace : str
            Name of the destination media space
        restore_path : str
            Path inside the media space, '/' for its root.  Created if
            it does not exist
        space_uuid : str
            Optional uuid of the destination media space
        ark_sources : list
            Optional list of sources to search, e.g. ['disk', 'tape']
        prefer_source : str
            Optional preferred source if a file exists in both, 'disk'
            or 'tape'

        Returns
        -------
        str
            The session guid of the new restore job
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

    # ------------------------------------------------------------------
    # file status
    # ------------------------------------------------------------------

    def getFileHashDatabaseStatus(self):
        """Report the status of the file hash database"""

        return self.get_file_hash_database_status()

    def get_file_hash_database_status(self):
        """Report the status of the file hash database

        Returns
        -------
        dict
            `status` ('importing', 'complete' or 'error'),
            `progress_complete` and `progress_estimated`
        """

        return self.getThatReturnsObj("/filestatus/database")

    def getFileStatus(self, flow_hash):
        """Lookup Ark backup status for a file based on a hash"""

        return self.get_file_status(flow_hash)

    def get_file_status(self, flow_hash):
        """Lookup Ark backup status for a file based on a hash

        Parameters
        ----------
        flow_hash : str
            A FLOW hash.  Version 0 ('<md5>'), version 1 ('1:<md5>')
            and version 2 ('2:<md5>') hashes are supported.
            See cli command: flow-hash

        Returns
        -------
        list
            A list of matches.  Each entry contains `hash`,
            `storage_type`, `job_id`, `job_time`, `file_id`, `pathname`,
            `filename`, `space_uuid`, `space_name` and `tapes`.
            An empty list if Ark has no copy of the file
        """

        url = "/filestatus/" + self.safe_url_string(str(flow_hash))
        reply = self.getThatReturnsObj(url)
        if not reply:
            # 404 simply means Ark has no matches for this hash
            return []
        return reply

    def getFileStatuses(self, hash_list):
        """Lookup Ark backup status for files based on a list of hashes"""

        return self.get_file_statuses(hash_list)

    def get_file_statuses(self, hash_list):
        """Lookup Ark backup status for files based on a list of hashes

        Parameters
        ----------
        hash_list : list
            A list of FLOW hashes

        Returns
        -------
        list
            A list of matches, see get_file_status()
        """

        # Note: the trailing slash is required by the service
        reply = self.postThatReturnsObj("/filestatus/", list(hash_list))
        if not reply:
            return []
        return reply

    def is_archived(self, flow_hash, storage_type=None):
        """Helper to check whether Ark holds a copy of a file

        Parameters
        ----------
        flow_hash : str
            A FLOW hash
        storage_type : str
            Optionally only accept a copy on 'ark_disk' or 'ark_tape'

        Returns
        -------
        bool
            True if Ark has at least one matching copy
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
        """Helper to collect the tape barcodes of a file status entry"""

        tapes = []
        for tape in file_status.get("tapes", []) or []:
            if isinstance(tape, dict):
                barcode = tape.get("barcode") or tape.get("name")
                if barcode:
                    tapes.append(barcode)
            else:
                tapes.append(tape)
        return tapes

    # ------------------------------------------------------------------
    # backup search
    # ------------------------------------------------------------------

    def getDiskSearchStatus(self):
        """Get disk backup indexing status"""

        return self.get_disk_search_status()

    def get_disk_search_status(self):
        """Get disk backup indexing status

        Returns
        -------
        dict
            `total`, `indexed`, `indexing`, `not_indexed`,
            `needs_indexing` and `total_files`
        """

        return self.getThatReturnsObj("/backup/disk/search/status")

    def searchBackups(self, data):
        """Search for files across indexed backups"""

        return self.postThatReturnsObj("/backup/search", data)

    def search_backups(
        self,
        search_pattern,
        search_mode="contains",
        *,
        backup_type=None,
        limit=100,
        offset=0,
    ):
        # pylint: disable=too-many-arguments
        """Search for files across indexed backups

        Parameters
        ----------
        search_pattern : str
            The filename or pattern to look for.  When `search_mode` is
            'flow_hash' this is a version 2 FLOW hash
        search_mode : str
            'exact', 'contains', 'wildcard' or 'flow_hash'
        backup_type : str
            'disk', 'tape' or None for both
        limit : int
            Maximum number of results, 1 - 10000
        offset : int
            Number of results to skip

        Returns
        -------
        dict
            `total_matches`, `limit`, `offset` and `results`.
            Note that disk backups have to be indexed before they show
            up here.  See get_disk_search_status()
        """

        data = {
            "search_pattern": search_pattern,
            "search_mode": search_mode,
            "limit": limit,
            "offset": offset,
        }

        if backup_type:
            data["backup_type"] = backup_type

        return self.searchBackups(data)

    def search_all_backups(
        self,
        search_pattern,
        search_mode="contains",
        *,
        backup_type=None,
        page_size=1000,
        max_results=0,
    ):
        # pylint: disable=too-many-arguments
        """Helper which pages through all search results

        Parameters
        ----------
        page_size : int
            Number of results fetched per request, 1 - 10000
        max_results : int
            Stop after this many results.  0 fetches everything

        Returns
        -------
        list
            All matching results
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
        """Helper to search the backup index for a FLOW hash"""

        if not str(flow_hash).startswith("2:"):
            logging.warning(
                "search_by_flow_hash: '%s' is not a version 2 hash", flow_hash
            )

        return self.search_backups(
            flow_hash,
            self.SEARCH_FLOW_HASH,
            backup_type=backup_type,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # tape library
    # ------------------------------------------------------------------

    def getTapes(self):
        """Get comprehensive tape library status"""

        return self.get_tapes()

    def get_tapes(self):
        """Get comprehensive tape library status

        Returns
        -------
        list
            A list of all tape volumes known to the system, not just
            those currently loaded.  Each entry contains at least
            `barcode` and `in_changer`
        """

        reply = self.get_tape_library_status()
        if not reply:
            return []
        return reply.get("tapes", [])

    def get_tape_library_status(self):
        """Get the raw tape library status including its timestamp"""

        return self.getThatReturnsObj("/api/tape/library/tapes")

    def find_tape(self, barcode):
        """Helper to find a tape volume by its barcode"""

        for tape in self.get_tapes():
            if tape.get("barcode") == barcode:
                return tape

        return {}
