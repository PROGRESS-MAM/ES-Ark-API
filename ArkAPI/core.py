"""
Gemeinsame Basis aller Ark-Methoden: Ergebnisobjekt, Request und Helfer.
"""

# --------- IMPORTS ---------

import json
import re
import threading
import time
from collections.abc import Callable
from urllib.parse import quote

from FlowAPI.core import Connection

# --------- STATIC ---------

Progress = Callable[[str], object] | None
"""Callback fuer Fortschrittsmeldungen mit einem Text-Argument, None = stumm"""

_VERBS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")
_ERROR_CLASS = re.compile(r"'([^']+)'")
# short joins keep Ctrl+C responsive, a long join blocks it on Windows
_JOIN_SECONDS = 1


# --------- RESULT ---------
class ArkResult:
    """Ergebnis einer Ark-Funktion

    Attributes
    ----------
    code : int
        HTTP-Statuscode der Antwort, 0 wenn keine Antwort vom Server kam.
        Eigene Kennungen der API bringen eigene Codes mit, z. B. 404
        JOB_NOT_FOUND oder 408 WAIT_TIMEOUT
    data : object
        Nutzdaten. Bei Fehlern der Leerwert der Funktion
    message : str
        Klartext, immer eine Zeichenkette
    error : str
        Maschinenlesbare Kennung, sonst "". Entweder die Kennung der
        Spezifikation (z. B. INVALID_HASH), bei Fehler 500 der WebUI der
        Klassenname (z. B. InvalidArkJobError) oder eine eigene Kennung
        der API (z. B. HASHES_NOT_RESTORABLE)
    """

    def __init__(
        self, code: int, *, data: object = None, message: str = "", error: str = ""
    ):
        self.code = int(code)
        self.data = data
        self.message = message
        self.error = error

    def __str__(self):
        return "{} {}".format(self.code, self.message)

    def __repr__(self):
        return "ArkResult(code={}, error={!r}, message={!r})".format(
            self.code, self.error, self.message
        )


# --------- CORE ---------
class ArkCore(Connection):
    """Verbindung, Request-Logik und Helfer, Basis aller Ark-Methoden"""

    def __init__(self):
        super().__init__()
        self._service_name = "ark"
        self._content_type = "application/json"

    # --------- REQUEST ---------

    @staticmethod
    def _path(*parts):
        """Endpunkt aus Teilen bauen, jeder Teil vollstaendig escaped

        Auch ein Slash wird escaped, damit eine ID nie den Pfad verschiebt.
        """

        return "/" + "/".join(quote(str(part), safe="") for part in parts)

    def _read_error(self):
        """Fehlerobjekt aus dem letzten Body lesen

        Zwei Formate:

        - EditShareHTTPError der Spezifikation mit code, error und
          details. details ist laut Schema Text, kommt aber auch als
          Objekt vor und wird dann als JSON uebernommen
        - Fehler 500 der WebUI mit error_class und error_msg, z. B.
          "<class 'editshare_common.InvalidArkJobError'>". error ist dann
          der Klassenname ohne Modul

        Returns
        -------
        tuple
            (error, details), beide str. Leer, wenn der Body keins der
            beiden Formate ist
        """

        try:
            payload = json.loads(self.lastResponse() or "")
        except (ValueError, TypeError):
            return "", ""
        if not isinstance(payload, dict):
            return "", ""

        if "error_class" in payload:
            match = _ERROR_CLASS.search(str(payload["error_class"]))
            name = match.group(1) if match else str(payload["error_class"])
            return name.rsplit(".", 1)[-1], self._text(payload.get("error_msg"))

        error = payload.get("error", "")
        return (error if isinstance(error, str) else ""), self._text(
            payload.get("details")
        )

    @staticmethod
    def _text(value):
        """Wert als Text: str unveraendert, Leeres als "", sonst JSON"""

        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False) if value else ""

    def _request(
        self, verb, endpoint, data=None, *, codes, default=None, raw=False
    ):
        """Request ausfuehren und den Statuscode unveraendert durchreichen

        Parameters
        ----------
        verb : str
            GET, POST, PUT, PATCH, DELETE oder HEAD
        endpoint : str
            Pfad ohne Host
        data : object
            Optionaler Body, dict und list werden JSON
        codes : dict
            Dokumentierte Codes des Endpunkts und ihre Bedeutung
        default : object
            Nutzdaten, wenn kein verwertbarer Body vorliegt
        raw : bool
            Body bei Erfolg als Text in data legen, ohne json.loads()

        Returns
        -------
        ArkResult
            Bei 2xx steht der geparste Body in data, sonst default. code
            ist 0, wenn keine Antwort kam oder ein 2xx-Body kein JSON ist
        """

        verb = verb.upper()
        if verb not in _VERBS:
            raise ValueError("nicht unterstuetztes Verb: {}".format(verb))

        # core leaves the previous status code untouched when the
        # connection fails, so reset it to detect that case reliably
        self._last_return_code = 0
        body = "" if verb in ("GET", "HEAD") else self._encode(data)
        reply = self.do_request(verb, endpoint, body)
        code = self.lastReturnCode()
        excerpt = str(reply or "").strip()[:160]

        if code == 0:
            return ArkResult(
                0, data=default, message="Keine Antwort vom Ark-Server: " + excerpt
            )

        if not 200 <= code < 300:
            error, details = self._read_error()
            return ArkResult(
                code,
                data=default,
                error=error,
                message=details
                or codes.get(code, "")
                or "Statuscode {} ist fuer diesen Endpunkt nicht dokumentiert: "
                "{}".format(code, excerpt),
            )

        payload = default
        if raw:
            payload = reply if reply else default
        elif reply and str(reply).strip():
            try:
                payload = json.loads(reply)
            except (ValueError, TypeError):
                return ArkResult(
                    0,
                    data=default,
                    message="Antwort ist kein gueltiges JSON, Statuscode {}: "
                    "{}".format(code, excerpt),
                )

        return ArkResult(code, data=payload, message=codes.get(code, ""))

    @staticmethod
    def _encode(data):
        """Body fuer do_request() aufbereiten

        dict und list werden JSON, Text bleibt unveraendert. json.dumps
        bleibt bei ensure_ascii, weil core Content-length aus der
        Zeichenzahl statt aus der Bytezahl bildet.
        """

        if data is None:
            return ""
        if isinstance(data, (dict, list)):
            return json.dumps(data)
        return data

    # --------- CHECKS ---------

    @staticmethod
    def _as_list(value, name):
        """Einen Text oder eine Liste als Liste von Texten ohne Duplikate

        Raises
        ------
        ValueError
            Wenn die Liste leer ist
        """

        items = [value] if isinstance(value, str) else list(value or [])
        items = list(dict.fromkeys(str(item) for item in items))
        if not items:
            raise ValueError("{} ist leer, mindestens ein Wert noetig".format(name))
        return items

    @staticmethod
    def _confirm(confirm, action):
        """ValueError, wenn eine aendernde Funktion ohne confirm=True kommt"""

        if confirm is not True:
            raise ValueError(
                "{} aendert Ark und braucht confirm=True, es wurde nichts "
                "gesendet".format(action)
            )

    @staticmethod
    def _seconds(name, value, *, allow_zero=False):
        """ValueError, wenn eine Sekundenangabe keine Zahl > 0 (bzw. >= 0) ist"""

        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        if not valid or value < 0 or (value == 0 and not allow_zero):
            raise ValueError(
                "{} muss eine Zahl {} 0 sein, ist {!r}".format(
                    name, ">=" if allow_zero else ">", value
                )
            )

    # --------- PROGRESS ---------

    @staticmethod
    def _minutes(seconds):
        """Dauer als "m:ss min" """

        return "{}:{:02d} min".format(int(seconds) // 60, int(seconds) % 60)

    @staticmethod
    def _report(on_progress, text):
        """Fortschritt melden, wenn ein Callback gesetzt ist"""

        if on_progress is not None:
            on_progress(text)

    def _in_background(self, func, text, on_progress, progress_seconds):
        """func() in einem Hintergrund-Thread ausfuehren und darauf warten

        Meldet alle progress_seconds "<text> seit m:ss min". Eine
        Ausnahme in func() wird hier erneut ausgeloest. Der Thread ist ein
        Daemon, Strg+C beendet also das Warten, nicht aber einen bereits
        gesendeten Request.
        """

        outcome = {}

        def run():
            try:
                outcome["result"] = func()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                outcome["error"] = exc  # re-raised in the calling thread

        worker = threading.Thread(target=run, daemon=True)
        started = time.monotonic()
        next_report = progress_seconds
        worker.start()
        while worker.is_alive():
            worker.join(min(_JOIN_SECONDS, progress_seconds))
            elapsed = time.monotonic() - started
            if worker.is_alive() and elapsed >= next_report:
                self._report(on_progress, "{} seit {}".format(text, self._minutes(elapsed)))
                next_report += progress_seconds

        if "error" in outcome:
            raise outcome["error"]
        return outcome["result"]
