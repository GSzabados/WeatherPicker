<div align="center">
<img src="logo.png" alt="Weather Picker" width="84" />

# Weather Picker — QGIS-Plugin

**Auf die Karte klicken → Wetterdaten inkl. 7‑Tage‑Vorschau als Diagramm.**
**Click the map → weather data incl. 7‑day forecast as a chart.**

[![QGIS](https://img.shields.io/badge/QGIS-3.16%2B-589632?logo=qgis&logoColor=white)](https://qgis.org)
[![Version](https://img.shields.io/badge/version-0.4-blue)](metadata.txt)
[![License: GPL v2](https://img.shields.io/badge/license-GPLv2-blue.svg)](LICENSE)
[![Data: Open-Meteo](https://img.shields.io/badge/data-Open--Meteo-orange)](https://open-meteo.com)
[![Data license: CC BY 4.0](https://img.shields.io/badge/data%20license-CC%20BY%204.0-lightgrey)](https://creativecommons.org/licenses/by/4.0/)
[![i18n](https://img.shields.io/badge/i18n-DE%20%7C%20EN-success)](#-sprache--language)

[Deutsch](#deutsch) · [English](#english)

</div>

---

<img src="weather_picker_Screenshot_1.png" alt="Weather Picker Screenshot" width="600" />

<a name="deutsch"></a>

## Deutsch

Einfache Wetterauskunft inklusive 7‑Tage‑Vorschau für die angeklickte Koordinate.
Temperatur‑ und Regenverlauf werden als pixelscharfes Diagramm dargestellt. Die
Daten stammen von der [Open‑Meteo‑API](https://open-meteo.com).

### Funktionen
- Temperaturkurve (geglättet) und Regenmengen in einem Diagramm
- „Jetzt"-Markierung und dezent schattierte Vergangenheit
- **Zweisprachig DE/EN** — folgt automatisch der QGIS‑Oberflächensprache
- Locale‑korrekte Datums‑ und Zahlenformate (Wochentag/Reihenfolge aus `QLocale`, Dezimaltrenner nach Sprache)
- Netzwerkabruf über den QGIS‑Netzwerk‑Manager → respektiert Proxy/Authentifizierung (z. B. NTLM/Kerberos im Firmennetz)
- Scharfes HiDPI‑Rendering (`devicePixelRatio`)

### Installation
**Aus dem QGIS‑Plugin‑Manager** (sobald veröffentlicht): *Erweiterungen → Erweiterungen verwalten und installieren → nach „Weather Picker" suchen*.

**Manuell aus ZIP:** *Erweiterungen → Aus ZIP installieren* und die Plugin‑ZIP wählen.

**Aus dem Quellcode:** Ordner in das QGIS‑Plugin‑Verzeichnis kopieren und QGIS neu starten:
- Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

### Verwendung
1. In der Werkzeugleiste **geoObserverTools** auf das **Weather Picker**‑Symbol klicken (Werkzeug aktiviert sich, Symbol bleibt eingedrückt).
2. Auf eine beliebige Stelle der **Karte klicken**.
3. Das Diagramm mit Temperatur‑ und Regenverlauf öffnet sich; unten der Quellen‑/Lizenzhinweis.
4. Erneuter Klick auf das Symbol **deaktiviert** das Werkzeug wieder.

> Das angeklickte Koordinatensystem ist beliebig — das Plugin transformiert intern nach WGS84 (EPSG:4326).

### Konfiguration
Das Plugin hat **keine eigenen Einstellungen**; das Verhalten wird über QGIS gesteuert:

| Aspekt | Steuerung |
|---|---|
| **Sprache (DE/EN)** | *Einstellungen → Optionen → Allgemein → Benutzeroberfläche* (System‑Locale überschreiben). Deutsch → DE, sonst EN. |
| **Datum/Zahlen** | Folgen der Sprache bzw. dem Regions‑Locale (z. B. `en_US` → `06/09`, `en_GB` → `09/06`). |
| **Proxy / Authentifizierung** | *Einstellungen → Optionen → Netzwerk*. |
| **Endpoint / API‑Key** | Fester, kostenloser Open‑Meteo‑Endpoint — **kein API‑Key nötig**. |
| **Timeout** | Fest 15 Sekunden; danach sauberer Abbruch. |
| **Cache** | Bewusst deaktiviert (`forceRefresh`) → immer aktuelle Daten. |

### Datenschutz
Beim Klick werden die **Koordinaten** der angeklickten Position (zusammen mit Ihrer
**IP‑Adresse**) an Open‑Meteo übertragen. Laut Open‑Meteo können Server‑Logs solche
Daten zeitweise enthalten — siehe die [Open‑Meteo‑Nutzungsbedingungen](https://open-meteo.com/en/terms).
Das Plugin selbst schreibt Koordinaten **nur gerundet (~1 km)** ins QGIS‑Log.

### Lizenz & Daten
- **Code:** [GNU GPL v2](LICENSE)
- **Wetterdaten:** © [Open‑Meteo](https://open-meteo.com), Lizenz [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Der **kostenlose** Open‑Meteo‑Endpoint ist für die **nichtkommerzielle** Nutzung vorgesehen. Für kommerzielle Nutzung bitte die Open‑Meteo‑Bedingungen beachten.

---

<a name="english"></a>
## English

Simple weather information including a 7‑day forecast for the clicked location.
Temperature and rainfall are rendered as a pixel‑sharp chart. Data is provided by the
[Open‑Meteo API](https://open-meteo.com).

### Features
- Smoothed temperature curve and rainfall in one chart
- "now" marker and subtly shaded past
- **Bilingual DE/EN** — follows the QGIS UI language automatically
- Locale‑correct date and number formats (weekday/order from `QLocale`, decimal separator by language)
- Network access via the QGIS network manager → honours proxy/authentication (e.g. NTLM/Kerberos on corporate networks)
- Sharp HiDPI rendering (`devicePixelRatio`)

### Installation
**From the QGIS Plugin Manager** (once published): *Plugins → Manage and Install Plugins → search for "Weather Picker"*.

**Manually from ZIP:** *Plugins → Install from ZIP* and pick the plugin ZIP.

**From source:** copy the folder into the QGIS plugins directory and restart QGIS:
- Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

### Usage
1. In the **geoObserverTools** toolbar, click the **Weather Picker** icon (the tool activates, icon stays pressed).
2. **Click anywhere on the map.**
3. A chart with the temperature and rainfall trend opens; the source/license note is shown at the bottom.
4. Click the icon again to **deactivate** the tool.

> Any project CRS works — the plugin transforms internally to WGS84 (EPSG:4326).

### Configuration
The plugin has **no settings of its own**; behaviour is driven by QGIS:

| Aspect | Controlled via |
|---|---|
| **Language (DE/EN)** | *Settings → Options → General → User interface* (override system locale). German → DE, otherwise EN. |
| **Date/Numbers** | Follow the language / regional locale (e.g. `en_US` → `06/09`, `en_GB` → `09/06`). |
| **Proxy / authentication** | *Settings → Options → Network*. |
| **Endpoint / API key** | Fixed free Open‑Meteo endpoint — **no API key required**. |
| **Timeout** | Fixed 15 seconds, then a clean abort. |
| **Cache** | Deliberately disabled (`forceRefresh`) → always up‑to‑date data. |

### Privacy
On click, the **coordinates** of the clicked location (together with your **IP address**)
are sent to Open‑Meteo. Per Open‑Meteo, server logs may temporarily contain such data —
see the [Open‑Meteo terms](https://open-meteo.com/en/terms). The plugin itself only logs
**rounded coordinates (~1 km)** to the QGIS log.

### License & Data
- **Code:** [GNU GPL v2](LICENSE)
- **Weather data:** © [Open‑Meteo](https://open-meteo.com), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- The **free** Open‑Meteo endpoint is intended for **non‑commercial** use. For commercial use, please review the Open‑Meteo terms.

---

<a name="-sprache--language"></a>
<div align="center">

**Autor / Author:** Mike Elstermann ([#geoObserver](https://geoobserver.de/)), Thomas Wölk
**Issues:** [github.com/geoObserver/weather_picker/issues](https://github.com/geoObserver/weather_picker/issues)

</div>
