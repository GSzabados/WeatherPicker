import os
import tempfile
import requests

from qgis.PyQt import QtWidgets, QtGui, QtCore
from qgis.core import (
    Qgis,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform
)
from qgis.gui import QgsMapTool


# =============================================================================
# Qt5 / Qt6 Enum-Kompatibilität (QGIS 3 & QGIS 4)
# =============================================================================
if not hasattr(QtGui.QImage, "Format_ARGB32"):
    # QImage
    QtGui.QImage.Format_ARGB32        = QtGui.QImage.Format.Format_ARGB32
    # QPainter
    QtGui.QPainter.Antialiasing       = QtGui.QPainter.RenderHint.Antialiasing
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
    # Qt TransformationMode
    QtCore.Qt.SmoothTransformation    = QtCore.Qt.TransformationMode.SmoothTransformation


# =============================================================================
# Plugin-Klasse
# =============================================================================
class WeatherPickerPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.toolbar = None
        self.action = None
        self.actions = []

    def initGui(self):
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
            # Fallback: Standard-QGIS-Icon, falls logo.png nicht gefunden
            icon = QtGui.QIcon(":/images/themes/default/mActionIdentify.svg")
            self.iface.messageBar().pushMessage(
                "Weather Picker",
                f"Icon nicht gefunden: {icon_path} – Fallback-Icon wird verwendet.",
                level=Qgis.Warning
            )

        # --- Button / Action anlegen ---
        self.action = QtWidgets.QAction(icon, "Weather Picker", self.iface.mainWindow())
        self.action.setToolTip("Weather Picker – Auf Karte klicken für Wetterdaten")
        self.action.setCheckable(True)
        self.action.triggered.connect(self.activate_tool)

        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def activate_tool(self):
        self.tool = WeatherPickerTool(self.canvas, self.action)
        self.canvas.setMapTool(self.tool)

        self.iface.messageBar().pushMessage(
            "Weather Picker",
            "Click map to get weather data & 7 day forecast as PNG",
            level=Qgis.Info
        )

    def unload(self):
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

    def __init__(self, canvas, action=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.action = action

    def deactivate(self):
        """Wird aufgerufen, wenn ein anderes Werkzeug aktiviert wird."""
        if self.action:
            self.action.setChecked(False)
        super().deactivate()

    # -------------------------------------------------------------------------
    def fetch_weather(self, lat, lon):
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,rain"
            "&past_days=2&forecast_days=7&timezone=auto"
        )
        data = requests.get(url, timeout=15).json()
        return (
            data["hourly"]["time"],
            data["hourly"]["temperature_2m"],
            data["hourly"]["rain"]
        )

    # -------------------------------------------------------------------------
    def create_png(self, lat, lon, times, temp, rain):

        width, height = 1200, 500

        img = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)
        img.fill(QtGui.QColor("white"))

        painter = QtGui.QPainter(img)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # --- Abstände (Margins) ---
        margin_left   = 80
        margin_right  = 80
        margin_top    = 50
        margin_bottom = 80

        plot_w = width  - margin_left - margin_right
        plot_h = height - margin_top  - margin_bottom

        n = len(temp)

        max_t, min_t = max(temp), min(temp)
        max_r = max(rain) if max(rain) > 0 else 1

        # --- Hilfsfunktionen ---
        def x(i):
            return margin_left + i * plot_w / max(n - 1, 1)

        def yt(v):
            return height - margin_bottom - (v - min_t) / (max_t - min_t + 0.001) * plot_h

        def yr(v):
            return height - margin_bottom - (v / (max_r + 0.001)) * plot_h

        # --- Rahmen zeichnen ---
        painter.setPen(QtGui.QPen(QtGui.QColor("black"), 1))
        painter.drawRect(margin_left, margin_top, plot_w, plot_h)

        # --- Horizontale Gitterlinien + Y-Achsen-Labels ---
        font = QtGui.QFont("Arial", 12)
        painter.setFont(font)

        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            frac = i / num_y_ticks
            t_val = min_t + frac * (max_t - min_t)
            y_pos = int(yt(t_val))

            # Gitternetz
            painter.setPen(QtGui.QPen(QtGui.QColor("#cccccc"), 1, QtCore.Qt.DashLine))
            painter.drawLine(margin_left, y_pos, margin_left + plot_w, y_pos)

            # Tick-Label links (Temperatur)
            painter.setPen(QtGui.QPen(QtGui.QColor("red"), 1))
            painter.drawText(
                QtCore.QRect(0, y_pos - 10, margin_left - 5, 20),
                QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                f"{t_val:.1f}°C"
            )

            # Tick-Label rechts (Regen)
            r_val = frac * max_r
            painter.setPen(QtGui.QPen(QtGui.QColor("blue"), 1))
            painter.drawText(
                QtCore.QRect(margin_left + plot_w + 5, y_pos - 10, margin_right - 5, 20),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                f"{r_val:.1f} mm"
            )

        # --- X-Achse: Datumsmarkierungen (alle 24 h = 1 Tag) ---
        font_x = QtGui.QFont("Arial", 12)
        painter.setFont(font_x)

        step = 24
        for i in range(0, n, step):
            x_pos    = int(x(i))
            date_str = times[i][:10]  # "YYYY-MM-DD"

            painter.setPen(QtGui.QPen(QtGui.QColor("black"), 1))
            painter.drawLine(x_pos, height - margin_bottom, x_pos, height - margin_bottom + 5)

            # Datum schräg (35°)
            painter.save()
            painter.translate(x_pos + 4, height - margin_bottom + 8)
            painter.rotate(35)
            painter.drawText(0, 0, date_str)
            painter.restore()

        # --- Achsentitel ---
        bold_font = QtGui.QFont("Arial", 14, QtGui.QFont.Bold)
        painter.setFont(bold_font)

        # Links: "Temperature (°C)" – vertikal
        painter.setPen(QtGui.QPen(QtGui.QColor("red"), 1))
        painter.save()
        painter.translate(15, height // 2)
        painter.rotate(-90)
        painter.drawText(
            QtCore.QRect(-100, -15, 200, 30),
            QtCore.Qt.AlignCenter,
            "Temperature (°C)"
        )
        painter.restore()

        # Rechts: "Rain (mm)" – vertikal
        painter.setPen(QtGui.QPen(QtGui.QColor("blue"), 1))
        painter.save()
        painter.translate(width - 15, height // 2)
        painter.rotate(90)
        painter.drawText(
            QtCore.QRect(-100, -15, 200, 30),
            QtCore.Qt.AlignCenter,
            "Rain (mm)"
        )
        painter.restore()

        # Unten: "Date"
        painter.setPen(QtGui.QPen(QtGui.QColor("black"), 1))
        painter.setFont(QtGui.QFont("Arial", 12))
        painter.drawText(
            QtCore.QRect(margin_left, height - 18, plot_w, 18),
            QtCore.Qt.AlignCenter,
            "Date"
        )

        # --- Diagrammtitel ---
        painter.setFont(QtGui.QFont("Arial", 14, QtGui.QFont.Bold))
        painter.setPen(QtGui.QPen(QtGui.QColor("black"), 1))
        painter.drawText(
            QtCore.QRect(margin_left, 5, plot_w, margin_top - 5),
            QtCore.Qt.AlignCenter,
            f"Weather data & 7 day forecast – Location: Lat {lat:.4f}, Lon {lon:.4f}"
        )

        # --- Legende ---
        lx, ly = margin_left + 10, margin_top + 10
        painter.setPen(QtGui.QPen(QtGui.QColor("red"), 2))
        painter.drawLine(lx, ly + 6, lx + 25, ly + 6)
        painter.setPen(QtGui.QPen(QtGui.QColor("black"), 1))
        painter.setFont(QtGui.QFont("Arial", 12))
        painter.drawText(lx + 30, ly + 11, "Temperature (°C)")

        ly2 = ly + 20
        painter.setPen(QtGui.QPen(QtGui.QColor("blue"), 4))
        painter.drawLine(lx, ly2 + 6, lx + 25, ly2 + 6)
        painter.setPen(QtGui.QPen(QtGui.QColor("black"), 1))
        painter.drawText(lx + 30, ly2 + 11, "Rain (mm)")

        # --- Datenlinie Temperatur (rot) ---
        pen_t = QtGui.QPen(QtGui.QColor("red"), 2)
        painter.setPen(pen_t)
        for i in range(n - 1):
            painter.drawLine(
                QtCore.QPointF(x(i),     yt(temp[i])),
                QtCore.QPointF(x(i + 1), yt(temp[i + 1]))
            )

        # --- Datenbalken Regen (blau, halbtransparent) ---
        bar_color = QtGui.QColor(0, 100, 255, 120)
        bar_w = max(1, int(plot_w / n * 0.7))
        for i in range(n):
            if rain[i] > 0:
                x_pos  = int(x(i)) - bar_w // 2
                y_top  = int(yr(rain[i]))
                y_base = height - margin_bottom
                painter.fillRect(x_pos, y_top, bar_w, y_base - y_top, bar_color)

        painter.end()

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img.save(tmp.name)

        return tmp.name, img

    # -------------------------------------------------------------------------
    def canvasReleaseEvent(self, event):
        print(">>> canvasReleaseEvent ausgelöst")

        p         = event.position() if hasattr(event, "position") else event.pos()
        map_point = self.canvas.getCoordinateTransform().toMapPoint(int(p.x()), int(p.y()))

        src = QgsProject.instance().crs()
        dst = QgsCoordinateReferenceSystem("EPSG:4326")
        ct  = QgsCoordinateTransform(src, dst, QgsProject.instance())
        wgs = ct.transform(map_point)

        lat, lon = wgs.y(), wgs.x()
        print(f">>> Koordinaten: lat={lat}, lon={lon}")

        try:
            t, temp, rain = self.fetch_weather(lat, lon)
            print(f">>> Wetterdaten empfangen: {len(temp)} Einträge")

            png, img = self.create_png(lat, lon, t, temp, rain)
            print(f">>> PNG erstellt: {png}")

            pixmap = QtGui.QPixmap.fromImage(img)

            dlg = QtWidgets.QDialog()
            dlg.setWindowTitle("Weather Picker")
            dlg.resize(1100, 560)

            layout = QtWidgets.QVBoxLayout()

            # Bild anzeigen
            label_img = QtWidgets.QLabel()
            label_img.setPixmap(
                pixmap.scaledToWidth(1100, QtCore.Qt.SmoothTransformation)
            )
            label_img.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(label_img)

            # Quellenangabe
            label_src = QtWidgets.QLabel(
                '<a href="https://open-meteo.com">Weather data/forecast: open-meteo.com</a>'
            )
            label_src.setOpenExternalLinks(True)
            label_src.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(label_src)

            dlg.setLayout(layout)

            print(">>> Dialog wird geöffnet...")
            dlg.exec()
            print(">>> Dialog geschlossen")

            # Temporäre Datei aufräumen
            try:
                os.remove(png)
            except Exception:
                pass

        except Exception as e:
            import traceback
            print(">>> FEHLER:")
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(None, "Error", str(e))
