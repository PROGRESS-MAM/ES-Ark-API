"""
ArkAPI - Wrapper fuer die EditShare Ark API
"""

# --------- IMPORTS ---------

# Explizite Re-Exports statt "from .ark import *": nur so sieht ein Type
# Checker, dass Ark und ArkResult zum oeffentlichen Namensraum von
# ArkAPI gehoeren. Damit funktionieren Autovervollstaendigung,
# Go-to-Definition und Docstring-Anzeige beim Aufrufer.
from .ark import ARK_VERSION, Ark, ArkResult

# --------- STATIC ---------

__version__ = ARK_VERSION

__all__ = [
    "ARK_VERSION",
    "Ark",
    "ArkResult",
]
