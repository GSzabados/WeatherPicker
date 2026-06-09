"""
Weather Picker - QGIS-Plugin
============================

Auf die Karte klicken und Wetterdaten inkl. 7-Tage-Vorschau (Open-Meteo)
als Diagramm anzeigen.

Der Netzwerkabruf läuft bewusst über den QGIS-Netzwerk-Manager
(``QgsBlockingNetworkRequest``) statt über ``requests``, damit die in QGIS
hinterlegten Proxy-/Authentifizierungs-Einstellungen (z. B. NTLM/Kerberos im
Firmennetz) berücksichtigt werden.
"""

from __future__ import annotations  # Type Hints als Strings → 3.16-kompatibel

import datetime
import json
import math
import os

from qgis.core import (
    Qgis,
    QgsBlockingNetworkRequest,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeedback,
    QgsMessageLog,
    QgsProject,
)
from qgis.gui import QgsMapTool
from qgis.PyQt import QtCore, QtGui, QtWidgets
from qgis.PyQt.QtCore import QTimer, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest

# =============================================================================
# Qt5 / Qt6 Enum-Kompatibilität (QGIS 3 & QGIS 4)
# =============================================================================
if not hasattr(QtGui.QImage, "Format_ARGB32"):
    # QImage
    QtGui.QImage.Format_ARGB32        = QtGui.QImage.Format.Format_ARGB32
    # QPainter
    QtGui.QPainter.Antialiasing       = QtGui.QPainter.RenderHint.Antialiasing
    QtGui.QPainter.TextAntialiasing   = QtGui.QPainter.RenderHint.TextAntialiasing
    # QFont
    QtGui.QFont.Bold                  = QtGui.QFont.Weight.Bold
    QtGui.QFont.Normal                = QtGui.QFont.Weight.Normal
    # Qt Alignment
    QtCore.Qt.AlignLeft               = QtCore.Qt.AlignmentFlag.AlignLeft
    QtCore.Qt.AlignRight              = QtCore.Qt.AlignmentFlag.AlignRight
    QtCore.Qt.AlignCenter             = QtCore.Qt.AlignmentFlag.AlignCenter
    QtCore.Qt.AlignVCenter            = QtCore.Qt.AlignmentFlag.AlignVCenter
    QtCore.Qt.AlignHCenter            = QtCore.Qt.AlignmentFlag.AlignHCenter
    # Qt PenStyle
    QtCore.Qt.DashLine                = QtCore.Qt.PenStyle.DashLine
    QtCore.Qt.SolidLine               = QtCore.Qt.PenStyle.SolidLine
    # Qt Pen cap/join (für die geglättete Kurve)
    QtCore.Qt.RoundCap                = QtCore.Qt.PenCapStyle.RoundCap
    QtCore.Qt.RoundJoin               = QtCore.Qt.PenJoinStyle.RoundJoin
    # Qt TransformationMode
    QtCore.Qt.SmoothTransformation    = QtCore.Qt.TransformationMode.SmoothTransformation
    # Qt MouseButton
    QtCore.Qt.LeftButton              = QtCore.Qt.MouseButton.LeftButton
    # Qt CursorShape
    QtCore.Qt.WaitCursor              = QtCore.Qt.CursorShape.WaitCursor


# Einheitlicher Log-Tag → im QGIS-Log-Panel als eigener Reiter filterbar.
LOG_TAG = "Weather Picker"

# Locale-freie deutsche Wochentagskürzel (datetime.weekday(): 0 = Montag).
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _log(message: object, level: int = Qgis.Info) -> None:
    """Status-/Debug-Ausgabe ins QGIS-Log-Panel statt auf stdout."""
    QgsMessageLog.logMessage(str(message), LOG_TAG, level)


def _schoener_schritt(spanne: float, anzahl: int) -> float:
    """Liefert einen "schönen" Achsen-Schritt (1/2/5 × Zehnerpotenz) für `anzahl`
    Intervalle über die gegebene Wertespanne – für lesbare, gerundete Achsen."""
    if spanne <= 0:
        return 1.0
    roh = spanne / max(anzahl, 1)
    mag = 10 ** math.floor(math.log10(roh))
    norm = roh / mag
    if norm < 1.5:
        s = 1
    elif norm < 3:
        s = 2
    elif norm < 7:
        s = 5
    else:
        s = 10
    return s * mag


# =============================================================================
# Plugin-Klasse
# =============================================================================
class WeatherPickerPlugin:
    """Plugin-Lebenszyklus: Toolbar/Action anlegen, Map-Tool umschalten, aufräumen."""

    def __init__(self, iface) -> None:
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.toolbar = None
        self.action = None
        self.actions = []
        self.tool = None  # erst in activate_tool() belegt; hält das aktive Map-Tool

    def initGui(self) -> None:
        # --- Toolbar "geoObserverTools" suchen oder neu anlegen ---
        self.toolbar = self.iface.mainWindow().findChild(
            QtWidgets.QToolBar, "geoObserverTools"
        )

        if not self.toolbar:
            self.toolbar = self.iface.addToolBar("geoObserverTools")
            self.toolbar.setObjectName("geoObserverTools")

        # --- Icon laden (logo.png liegt im gleichen Ordner wie dieses Skript) ---
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path  = os.path.join(plugin_dir, "logo.png")

        if os.path.exists(icon_path):
            icon = QtGui.QIcon(icon_path)
        else:
            # Ausweich-Icon: Standard-QGIS-Icon, falls logo.png nicht gefunden wird
            icon = QtGui.QIcon(":/images/themes/default/mActionIdentify.svg")
            self.iface.messageBar().pushMessage(
                "Weather Picker",
                f"Icon nicht gefunden: {icon_path} – Ausweich-Icon wird verwendet.",
                level=Qgis.Warning
            )

        # --- Button / Action anlegen ---
        self.action = QtWidgets.QAction(icon, "Weather Picker", self.iface.mainWindow())
        self.action.setToolTip("Weather Picker – Auf Karte klicken für Wetterdaten")
        self.action.setCheckable(True)
        self.action.triggered.connect(self.activate_tool)

        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def activate_tool(self, checked: bool = False) -> None:
        # Umschaltbare Action: Bei erneutem Klick (checked=False) das Werkzeug
        # wieder abwählen, statt ein neues Map-Tool zu setzen.
        if not checked:
            if self.tool is not None and self.canvas.mapTool() is self.tool:
                self.canvas.unsetMapTool(self.tool)
            return

        self.tool = WeatherPickerTool(self.iface, self.canvas, self.action)
        self.canvas.setMapTool(self.tool)

        self.iface.messageBar().pushMessage(
            "Weather Picker",
            "Auf die Karte klicken – Wetterdaten & 7-Tage-Vorschau als Diagramm",
            level=Qgis.Info
        )

    def unload(self) -> None:
        # Aktives Map-Tool zurücksetzen, falls noch unseres aktiv ist –
        # sonst bleibt es als Zombie-Referenz im Canvas hängen.
        if self.tool is not None and self.canvas.mapTool() is self.tool:
            self.canvas.unsetMapTool(self.tool)
        self.tool = None

        for a in self.actions:
            if self.toolbar:
                self.toolbar.removeAction(a)

        # Toolbar entfernen, wenn sie leer ist
        if self.toolbar and len(self.toolbar.actions()) == 0:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar = None


# =============================================================================
# Map-Tool-Klasse
# =============================================================================
class WeatherPickerTool(QgsMapTool):

    def __init__(self, iface, canvas, action: QtWidgets.QAction | None = None) -> None:
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.action = action

    def deactivate(self) -> None:
        """Wird aufgerufen, wenn ein anderes Werkzeug aktiviert wird."""
        if self.action:
            self.action.setChecked(False)
        super().deactivate()

    # -------------------------------------------------------------------------
    def fetch_weather(
        self, lat: float, lon: float
    ) -> tuple[list[str], list[float], list[float], int]:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,rain"
            "&past_days=2&forecast_days=7&timezone=auto"
        )

        # Über den QGIS-Netzwerk-Manager statt über die Python-Bibliothek `requests`
        # anfragen: nur so werden die QGIS-/System-Proxy-Einstellungen inkl.
        # Authentifizierung (z. B. NTLM/Kerberos im Firmennetz) berücksichtigt.
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "QGIS-WeatherPicker")

        # QgsBlockingNetworkRequest kennt keinen Timeout-Parameter und würde sonst
        # bis zum globalen QGIS-Netzwerk-Timeout (Vorgabe 60 s) blockieren. Über ein
        # QgsFeedback + Einmal-Timer brechen wir nach 15 s selbst ab. Der Timer feuert
        # während der internen Event-Loop von get() und wird danach gestoppt, damit er
        # bei schnellem Erfolg nicht später noch ins Leere feuert.
        feedback = QgsFeedback()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(feedback.cancel)
        timer.start(15000)

        blocking = QgsBlockingNetworkRequest()

        # Hinweis: Der Aufruf blockiert den UI-Thread (bis zu 15 s). Architektonisch
        # sauber wäre ein QgsTask + Signal/Slot mit Ladeanzeige – das ist aber ein
        # größerer Umbau. Als minimale Rückmeldung wenigstens einen Warte-Cursor zeigen.
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        try:
            err = blocking.get(request, False, feedback)  # request, forceRefresh, feedback
        finally:
            timer.stop()  # nicht mehr benötigt, egal ob Erfolg/Fehler/Timeout
            QtWidgets.QApplication.restoreOverrideCursor()

        if feedback.isCanceled():
            raise RuntimeError(
                "Zeitüberschreitung (15 s) beim Abruf der Wetterdaten – "
                "Netzwerk oder Proxy nicht erreichbar?"
            )

        # HTTP-Fehler (4xx/5xx) liefert get() bereits als ServerExceptionError zurück.
        if err != QgsBlockingNetworkRequest.ErrorCode.NoError:
            raise RuntimeError(
                f"Netzwerkfehler beim Abruf der Wetterdaten: "
                f"{blocking.errorMessage()}"
            )

        content = bytes(blocking.reply().content()).decode("utf-8")

        # --- Antwort strukturiert prüfen ---------------------------------------
        # json.JSONDecodeError ist eine ValueError-Unterklasse, daher mit abgedeckt.
        try:
            data   = json.loads(content)
            hourly = data["hourly"]
            times  = hourly["time"]
            temp   = hourly["temperature_2m"]
            rain   = hourly["rain"]
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(
                "Unerwartetes Antwortformat der Open-Meteo-API."
            ) from exc

        if not isinstance(times, list) or not (len(times) == len(temp) == len(rain)):
            raise RuntimeError("Inkonsistente Wetterdaten von der API erhalten.")

        # utc_offset_seconds liefert Open-Meteo bei timezone=auto mit. Damit lässt
        # sich die lokale "Jetzt"-Zeit am Ort bestimmen, ohne auf die hourly-Indizes
        # angewiesen zu sein (die durch das null-Filtern verschoben sein könnten).
        utc_offset = data.get("utc_offset_seconds", 0)
        if not isinstance(utc_offset, (int, float)):
            utc_offset = 0

        # Open-Meteo liefert in Randlagen (Polarregion, offene See) teils null-Werte.
        # Diese herausfiltern, damit max()/min() und das Zeichnen nicht über NoneType
        # stolpern. Die drei Listen bleiben dabei index-synchron.
        cleaned = [
            (tm, tp, rn)
            for tm, tp, rn in zip(times, temp, rain)
            if tp is not None and rn is not None
        ]
        if not cleaned:
            raise RuntimeError(
                "Keine gültigen Wetterdaten für diese Position verfügbar."
            )

        times, temp, rain = (list(col) for col in zip(*cleaned))
        return times, temp, rain, utc_offset

    # -------------------------------------------------------------------------
    def create_png(
        self,
        lat: float,
        lon: float,
        times: list[str],
        temp: list[float],
        rain: list[float],
        now_local: datetime.datetime | None = None,
        scale: float = 1.0,
    ) -> QtGui.QImage:

        # --- Farbpalette (dezent-modern, aber kontraststark) ---
        C_INK       = QtGui.QColor("#222222")          # Haupttext
        C_MUTE      = QtGui.QColor("#6f6f6f")          # Sekundärtext / Datum
        C_GRID      = QtGui.QColor("#e3e3e3")          # Gitternetz
        C_AXIS      = QtGui.QColor("#bdbdbd")          # Achsenlinien
        C_NOW       = QtGui.QColor("#3a3a3a")          # "Jetzt"-Linie
        C_PAST      = QtGui.QColor(0, 0, 0, 12)        # Schattierung Vergangenheit
        C_TEMP      = QtGui.QColor("#e4572e")          # Temperatur (warmes Rot-Orange)
        C_RAIN      = QtGui.QColor(48, 127, 226, 190)  # Regenbalken (kräftiges Blau)
        C_RAIN_INK  = QtGui.QColor("#1d6fb8")          # Regen-Beschriftung

        # Logische Zeichenfläche; physisch wird mit `scale` (Geräte-Pixeldichte)
        # gerendert, damit nichts heruntergerechnet (= unscharf) werden muss.
        width, height = 1280, 620
        if scale < 1.0:
            scale = 1.0

        img = QtGui.QImage(
            max(1, int(width * scale)),
            max(1, int(height * scale)),
            QtGui.QImage.Format_ARGB32,
        )
        img.fill(QtGui.QColor("white"))

        painter = QtGui.QPainter(img)
        # try/finally: bei einer Exception während des Zeichnens muss painter.end()
        # trotzdem laufen, sonst bleibt das QImage-Backend gesperrt (Ressourcen-Leck).
        try:
            painter.scale(scale, scale)  # in logischen Koordinaten zeichnen
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

            # --- Abstände (Ränder) ---
            margin_left   = 82
            margin_right  = 82
            margin_top    = 78
            margin_bottom = 72

            plot_w      = width  - margin_left - margin_right
            plot_h      = height - margin_top  - margin_bottom
            plot_bottom = height - margin_bottom

            n = len(temp)

            # --- Temperaturachse: schön gerundete Grenzen + etwas Luft ---
            t_lo, t_hi = min(temp), max(temp)
            if t_hi - t_lo < 0.5:          # sehr flache Kurve nicht übermäßig zoomen
                mid = (t_hi + t_lo) / 2.0
                t_lo, t_hi = mid - 0.5, mid + 0.5
            step_t   = _schoener_schritt(t_hi - t_lo, 6)
            axis_min = math.floor(t_lo / step_t) * step_t
            axis_max = math.ceil(t_hi / step_t) * step_t
            n_ticks  = max(1, int(round((axis_max - axis_min) / step_t)))
            t_dec    = 0 if step_t >= 1 else 1

            # --- Regenachse: gerundete Obergrenze, aber mind. 1 mm, damit
            #     Nieselregen klein dargestellt wird (statt voller Säulenhöhe). ---
            r_peak = max(rain)
            if r_peak <= 0:
                axis_max_r = 1.0
            else:
                step_r = _schoener_schritt(r_peak, 4)
                axis_max_r = max(math.ceil(r_peak / step_r) * step_r, 1.0)
            r_dec = 1 if axis_max_r < 5 else 0

            # --- Hilfsfunktionen ---
            def x(i):
                return margin_left + i * plot_w / max(n - 1, 1)

            def yt(v):
                return plot_bottom - (v - axis_min) / (axis_max - axis_min) * plot_h

            def yr(v):
                return plot_bottom - (v / axis_max_r) * plot_h

            def set_font(size, bold=False):
                f = QtGui.QFont("Arial", size)
                f.setBold(bold)
                painter.setFont(f)

            # --- Zeitstempel parsen (für "Jetzt"-Linie und Wochentage) ---
            try:
                tdts = [datetime.datetime.fromisoformat(s) for s in times]
            except (ValueError, TypeError):
                tdts = []

            # Fraktionale X-Position des aktuellen Zeitpunkts ermitteln. Robust über
            # Zeitstempel-Vergleich – unabhängig vom hourly-Index.
            now_x = None
            if now_local is not None and tdts and tdts[0] <= now_local <= tdts[-1]:
                for k in range(len(tdts) - 1):
                    if tdts[k] <= now_local <= tdts[k + 1]:
                        span = (tdts[k + 1] - tdts[k]).total_seconds() or 1.0
                        frac = (now_local - tdts[k]).total_seconds() / span
                        now_x = x(k + frac)
                        break

            # --- Titel + Koordinaten-Untertitel ---
            set_font(17, bold=True)
            painter.setPen(QtGui.QPen(C_INK))
            painter.drawText(
                QtCore.QRect(0, 14, width, 26),
                QtCore.Qt.AlignCenter,
                "Wetterdaten & 7-Tage-Vorschau"
            )
            set_font(10)
            painter.setPen(QtGui.QPen(C_MUTE))
            painter.drawText(
                QtCore.QRect(0, 42, width, 18),
                QtCore.Qt.AlignCenter,
                f"Breite {lat:.4f}, Länge {lon:.4f}"
            )

            # --- Vergangenheit dezent schattieren (links der "Jetzt"-Linie) ---
            if now_x is not None:
                painter.fillRect(
                    int(margin_left), int(margin_top),
                    int(now_x - margin_left), int(plot_h),
                    C_PAST
                )

            # --- Horizontale Gitterlinien + Y-Achsen-Beschriftung ---
            for i in range(n_ticks + 1):
                frac  = i / n_ticks
                y_pos = int(plot_bottom - frac * plot_h)

                painter.setPen(QtGui.QPen(C_GRID, 1, QtCore.Qt.SolidLine))
                painter.drawLine(margin_left, y_pos, margin_left + plot_w, y_pos)

                # Beschriftung links (Temperatur)
                t_val = axis_min + i * step_t
                set_font(10)
                painter.setPen(QtGui.QPen(C_TEMP, 1))
                painter.drawText(
                    QtCore.QRect(0, y_pos - 9, margin_left - 8, 18),
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                    f"{t_val:.{t_dec}f}°"
                )

                # Beschriftung rechts (Regen)
                r_val = frac * axis_max_r
                painter.setPen(QtGui.QPen(C_RAIN_INK, 1))
                painter.drawText(
                    QtCore.QRect(margin_left + plot_w + 8, y_pos - 9, margin_right - 10, 18),
                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                    f"{r_val:.{r_dec}f}"
                )

            # --- Vertikale Tageslinien + Datums-Beschriftung (Wochentag, alle 24 h) ---
            set_font(10)
            step = 24
            for i in range(0, n, step):
                x_pos = int(x(i))

                # Tageslinie (sehr hell)
                painter.setPen(QtGui.QPen(C_GRID, 1, QtCore.Qt.SolidLine))
                painter.drawLine(x_pos, margin_top, x_pos, plot_bottom)

                # Strich unter der Achse
                painter.setPen(QtGui.QPen(C_AXIS, 1))
                painter.drawLine(x_pos, plot_bottom, x_pos, plot_bottom + 5)

                # Datum als "Wochentag TT.MM." – Wochentag aus geparstem Datum.
                if i < len(tdts):
                    day = tdts[i]
                    date_lbl = f"{WOCHENTAGE[day.weekday()]} {day.day:02d}.{day.month:02d}."
                else:
                    d = times[i]
                    date_lbl = f"{d[8:10]}.{d[5:7]}."

                painter.setPen(QtGui.QPen(C_MUTE, 1))
                painter.drawText(
                    QtCore.QRect(x_pos - 48, plot_bottom + 7, 96, 16),
                    QtCore.Qt.AlignCenter,
                    date_lbl
                )

            # --- Achsenlinien (links / rechts / unten), kein harter Vollrahmen ---
            painter.setPen(QtGui.QPen(C_AXIS, 1))
            painter.drawLine(margin_left, margin_top, margin_left, plot_bottom)
            painter.drawLine(margin_left + plot_w, margin_top, margin_left + plot_w, plot_bottom)
            painter.drawLine(margin_left, plot_bottom, margin_left + plot_w, plot_bottom)

            # --- Datenbereich beschneiden, damit Bézier-Überschwinger/Balken
            #     nicht über die Achsen hinausragen ---
            painter.save()
            painter.setClipRect(margin_left, margin_top, plot_w, plot_h)

            # --- Regenbalken (zuerst, damit die Temperaturlinie darüber liegt) ---
            bar_w = max(4, int(plot_w / n * 0.7))
            for i in range(n):
                if rain[i] > 0:
                    bx = int(x(i)) - bar_w // 2
                    by = int(yr(rain[i]))
                    painter.fillRect(bx, by, bar_w, plot_bottom - by, C_RAIN)

            # --- Temperatur: geglättete Kurve (Catmull-Rom → kubische Bézier) ---
            pts = [QtCore.QPointF(x(i), yt(temp[i])) for i in range(n)]

            def smooth_path(points):
                path = QtGui.QPainterPath()
                if not points:
                    return path
                path.moveTo(points[0])
                m = len(points)
                for j in range(m - 1):
                    p0 = points[j - 1] if j > 0 else points[j]
                    p1 = points[j]
                    p2 = points[j + 1]
                    p3 = points[j + 2] if j + 2 < m else points[j + 1]
                    # Catmull-Rom-Tangenten (Tension 1/6) als Bézier-Kontrollpunkte
                    c1 = QtCore.QPointF(p1.x() + (p2.x() - p0.x()) / 6.0,
                                        p1.y() + (p2.y() - p0.y()) / 6.0)
                    c2 = QtCore.QPointF(p2.x() - (p3.x() - p1.x()) / 6.0,
                                        p2.y() - (p3.y() - p1.y()) / 6.0)
                    path.cubicTo(c1, c2, p2)
                return path

            line_path = smooth_path(pts)

            # Flächenfüllung mit Verlauf (oben kräftig → unten transparent),
            # wirkt deutlich weniger "ausgewaschen" als eine flache Pastellfläche.
            fill_path = QtGui.QPainterPath()
            fill_path.moveTo(QtCore.QPointF(pts[0].x(), plot_bottom))
            fill_path.lineTo(pts[0])
            fill_path.connectPath(line_path)
            fill_path.lineTo(QtCore.QPointF(pts[-1].x(), plot_bottom))
            fill_path.closeSubpath()

            grad = QtGui.QLinearGradient(0.0, float(margin_top), 0.0, float(plot_bottom))
            grad.setColorAt(0.0, QtGui.QColor(228, 87, 46, 110))
            grad.setColorAt(1.0, QtGui.QColor(228, 87, 46, 0))
            painter.fillPath(fill_path, QtGui.QBrush(grad))

            pen_t = QtGui.QPen(C_TEMP, 2.6)
            pen_t.setCapStyle(QtCore.Qt.RoundCap)
            pen_t.setJoinStyle(QtCore.Qt.RoundJoin)
            painter.strokePath(line_path, pen_t)

            # --- "Jetzt"-Linie (gestrichelt, innerhalb des Plots) ---
            if now_x is not None:
                nx = int(now_x)
                painter.setPen(QtGui.QPen(C_NOW, 1.4, QtCore.Qt.DashLine))
                painter.drawLine(nx, margin_top, nx, plot_bottom)

            painter.restore()  # Beschneidung wieder aufheben

            # --- "Jetzt"-Beschriftung oberhalb des Plots (außerhalb der Beschneidung) ---
            if now_x is not None:
                nx = int(now_x)
                set_font(9, bold=True)
                painter.setPen(QtGui.QPen(C_NOW))
                painter.drawText(
                    QtCore.QRect(nx - 30, margin_top - 16, 60, 14),
                    QtCore.Qt.AlignCenter,
                    "jetzt"
                )

            # --- Achsentitel (vertikal) ---
            set_font(12, bold=True)
            painter.setPen(QtGui.QPen(C_TEMP))
            painter.save()
            painter.translate(20, margin_top + plot_h / 2)
            painter.rotate(-90)
            painter.drawText(QtCore.QRect(-110, -16, 220, 30), QtCore.Qt.AlignCenter, "Temperatur (°C)")
            painter.restore()

            painter.setPen(QtGui.QPen(C_RAIN_INK))
            painter.save()
            painter.translate(width - 18, margin_top + plot_h / 2)
            painter.rotate(90)
            painter.drawText(QtCore.QRect(-110, -16, 220, 30), QtCore.Qt.AlignCenter, "Regen (mm)")
            painter.restore()

            # --- Legende (oben rechts, mit halbtransparentem Hintergrund) ---
            leg_w, leg_h = 250, 24
            leg_x = margin_left + plot_w - leg_w
            leg_y = margin_top + 8
            painter.fillRect(leg_x, leg_y, leg_w, leg_h, QtGui.QColor(255, 255, 255, 215))
            cy = leg_y + leg_h // 2

            set_font(10)
            # Temperatur
            painter.setPen(QtGui.QPen(C_TEMP, 3))
            painter.drawLine(leg_x + 10, cy, leg_x + 34, cy)
            painter.setPen(QtGui.QPen(C_INK))
            painter.drawText(leg_x + 40, cy + 4, "Temperatur")
            # Regen
            rx = leg_x + 140
            painter.fillRect(rx, cy - 5, 24, 10, C_RAIN)
            painter.setPen(QtGui.QPen(C_INK))
            painter.drawText(rx + 30, cy + 4, "Regen")
        finally:
            painter.end()

        # Geräte-Pixeldichte am Bild vermerken, damit es 1:1 (scharf) angezeigt wird.
        img.setDevicePixelRatio(scale)
        return img

    # -------------------------------------------------------------------------
    def canvasReleaseEvent(self, event) -> None:
        # Nur Linksklick auswerten – Rechts-/Mittelklick (Verschieben, Kontextmenü) ignorieren.
        if event.button() != QtCore.Qt.LeftButton:
            return

        _log("canvasReleaseEvent ausgelöst")

        p         = event.position() if hasattr(event, "position") else event.pos()
        map_point = self.canvas.getCoordinateTransform().toMapPoint(int(p.x()), int(p.y()))

        try:
            src = QgsProject.instance().crs()
            dst = QgsCoordinateReferenceSystem("EPSG:4326")
            if not src.isValid() or not dst.isValid():
                raise RuntimeError(
                    "Ungültiges Koordinatensystem – Transformation nicht möglich."
                )

            ct  = QgsCoordinateTransform(src, dst, QgsProject.instance())
            wgs = ct.transform(map_point)

            lat, lon = wgs.y(), wgs.x()
            _log(f"Koordinaten: lat={lat}, lon={lon}")

            t, temp, rain, utc_offset = self.fetch_weather(lat, lon)
            _log(f"Wetterdaten empfangen: {len(temp)} Einträge")

            # Lokale "Jetzt"-Zeit am Ort = aktuelle UTC + utc_offset_seconds.
            now_local = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(seconds=utc_offset)
            ).replace(tzinfo=None)

            # In Geräteauflösung rendern → 1:1 anzeigen, kein unscharfer Downscale.
            try:
                dpr = float(self.iface.mainWindow().devicePixelRatioF())
            except Exception:
                dpr = 1.0

            img = self.create_png(lat, lon, t, temp, rain, now_local, scale=dpr)
            pixmap = QtGui.QPixmap.fromImage(img)
            pixmap.setDevicePixelRatio(dpr)

            dlg = QtWidgets.QDialog(self.iface.mainWindow())
            dlg.setWindowTitle("Weather Picker")
            dlg.resize(1320, 720)

            layout = QtWidgets.QVBoxLayout()

            # Bild anzeigen (ohne Skalierung → scharf)
            label_img = QtWidgets.QLabel()
            label_img.setPixmap(pixmap)
            label_img.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(label_img)

            # Quellenangabe
            label_src = QtWidgets.QLabel(
                '<a href="https://open-meteo.com">Wetterdaten/Vorhersage: open-meteo.com</a>'
            )
            label_src.setOpenExternalLinks(True)
            label_src.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(label_src)

            dlg.setLayout(layout)

            _log("Dialog wird geöffnet...")
            dlg.exec()
            _log("Dialog geschlossen")

        except Exception as e:
            import traceback
            _log(traceback.format_exc(), level=Qgis.Critical)
            QtWidgets.QMessageBox.critical(self.iface.mainWindow(), "Weather Picker", str(e))
