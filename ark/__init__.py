"""
ark - Wrapper fuer die EditShare Ark API
"""

# --------- IMPORTS ---------

from .ark import (
    ARK_PORT,
    ARK_VERSION,
    SEARCH_CONTAINS,
    SEARCH_EXACT,
    SEARCH_FLOW_HASH,
    SEARCH_WILDCARD,
    SOURCE_DISK,
    SOURCE_TAPE,
    SPACE_FILE_EXCHANGE,
    SPACE_FLOW,
    SPACE_MEDIA,
    SPACE_PRIVATE,
    SPACE_PROJECT,
    SPACE_SETTINGS,
    STORAGE_DISK,
    STORAGE_TAPE,
    Ark,
)

# --------- METADATEN ---------

__version__ = ARK_VERSION

__all__ = [name for name in dir() if not name.startswith("_")]
