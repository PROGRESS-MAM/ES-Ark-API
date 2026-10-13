"""
ArkAPI - Wrapper fuer die EditShare Ark API
"""

# --------- IMPORTS ---------

# explicit re-exports, so type checkers see Ark and ArkResult as part of ArkAPI
from .ark import ARK_VERSION, Ark, ArkResult

# --------- STATIC ---------

__version__ = ARK_VERSION

__all__ = [
    "ARK_VERSION",
    "Ark",
    "ArkResult",
]
