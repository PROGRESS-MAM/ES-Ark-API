"""
Gemeinsame Basis aller Ark-Methoden: Ergebnisobjekt und Request.
"""

# --------- IMPORTS ---------

import json
from urllib.parse import quote

from FlowAPI.core import Connection


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
        Die Nutzdaten. Bei Fehlern der jeweilige Leerwert der Methode
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


# --------- CORE ---------
class ArkCore(Connection):
    """Verbindung und Request-Logik, Basis aller Ark-Methoden"""

    def __init__(self):
        super().__init__()
        self._service_name = "ark"
        self._content_type = "application/json"

    @staticmethod
    def _path(*parts):
        """Endpunkt aus Teilen bauen, jeder Teil vollstaendig escaped

        Anders als safe_url_string() wird auch ein Slash escaped, damit
        eine ID nie den Pfad verschiebt.
        """

        return "/" + "/".join(quote(str(part), safe="") for part in parts)

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

    def _request(
        self, verb, endpoint, data=None, *, codes, default=None, raw=False
    ):
        """Request ausfuehren und den Statuscode unveraendert durchreichen

        Anders als getThatReturnsObj() aus FlowAPI.core wird der Body
        nicht blind durch json.loads() geschickt.

        Parameters
        ----------
        verb : str
            GET, POST, PUT, PATCH, DELETE oder HEAD
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
        raw : bool
            Body bei Erfolg als Text in data legen, ohne json.loads()

        Returns
        -------
        ArkResult
            Der Statuscode wird nur durchgereicht, nicht bewertet. Bei
            2xx steht der geparste Body in data, sonst der Leerwert.
            Kam keine Antwort zustande oder laesst sich ein Body bei 2xx
            nicht parsen, ist code 0
        """

        verb = verb.upper()
        if verb not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
            raise ValueError("nicht unterstuetztes Verb: {}".format(verb))

        # core leaves the previous status code untouched when the
        # connection fails, so reset it to detect that case reliably
        self._last_return_code = 0
        body = "" if verb in ("GET", "HEAD") else self._encode(data)
        reply = self.do_request(verb, endpoint, body)
        code = self.lastReturnCode()

        if code == 0:
            return ArkResult(
                0,
                data=default,
                message="Keine Antwort vom Ark-Server: {}".format(
                    str(reply or "").strip()[:160]
                ),
            )

        if not 200 <= code < 300:
            error, details = self._read_error()
            return ArkResult(
                code,
                data=default,
                error=error,
                message=details
                or codes.get(code, "")
                or "Statuscode {} ist fuer diesen Endpunkt nicht "
                "dokumentiert: {}".format(code, str(reply or "").strip()[:160]),
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
                    "{}".format(code, str(reply).strip()[:160]),
                )

        return ArkResult(code, data=payload, message=codes.get(code, ""))

    @staticmethod
    def _encode(data):
        """Body fuer do_request() aufbereiten

        dict und list werden zu JSON, Text bleibt unveraendert. json.dumps
        bleibt bei ensure_ascii, weil core Content-length aus der
        Zeichenzahl statt aus der Bytezahl bildet.
        """

        if data is None:
            return ""
        if isinstance(data, (dict, list)):
            return json.dumps(data)
        return data
