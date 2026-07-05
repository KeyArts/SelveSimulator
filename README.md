# SelveMqttServer

Selve USB-RF Gateway Simulator
A server for controlling Selve's roller motors

Emuliert das Selve USB-RF Gateway (FTDI, 115200 Baud) über ein virtuelles
serielles Port-Paar – ohne echten Stick.

## Voraussetzungen

```bash
pip install pyserial pytest
```

## Schritt 1: Tests (kein Hardware erforderlich)

```bash
cd selve_simulator
pytest tests/ -v
```

Alle Tests laufen im `LoopbackSimulator`-Modus (kein serieller Port nötig).

---

## Schritt 2: Virtuelles Port-Paar einrichten

### Linux (socat)

```bash
sudo apt install socat

# Terminal 1: Port-Paar erstellen
socat -d -d pty,raw,echo=0,link=/tmp/selve0 pty,raw,echo=0,link=/tmp/selve1
# → gibt z.B. aus: /dev/pts/3 <-> /dev/pts/4

# Terminal 2: Simulator auf Port B starten
python -m selve_sim.server --port /tmp/selve1 --loglevel DEBUG

# Terminal 3: Selve PC-Software oder Home Assistant → /tmp/selve0
```

### Windows (com0com)

1. [com0com](https://sourceforge.net/projects/com0com/) installieren
2. Im Setup-Utility: COM5 ↔ COM6 Paar erstellen
3. Simulator auf COM6 starten:
   ```
   python -m selve_sim.server --port COM6 --loglevel DEBUG
   ```
4. Selve PC-Software → COM5 verbinden

---

## Schritt 3: Home Assistant testen

In HA Selve NG Integration hinzufügen → USB-Port `/tmp/selve0` (Linux)
bzw. `COM5` (Windows) angeben.

**WICHTIG:** Den Service `selve.factory_reset_gateway` und `selve.reset`
im Simulator niemals am echten Stick ausführen, nur testen!

---

## Simulated Devices

Der Simulator startet mit:

| ID | Name                  | Typ       | Protokoll |
|----|-----------------------|-----------|-----------|
|  1 | Rollladen 1           | Shutter   | Commeo    |
|  2 | Rollladen 2           | Shutter   | Commeo    |
|  3 | Rollladen 3           | Shutter   | Commeo    |
|  5 | Jalousie Wohnzimmer   | Blind     | Commeo    |
| 10 | Iveo Markise          | Awning    | Iveo      |

Gruppe 1 enthält Geräte 1, 2, 3, 5.

---

## Protokoll-Kurzreferenz

```xml
<!-- Request -->
<?xml version="1.0" encoding="UTF-8"?>
<methodCall>
  <methodName>selve.GW.device.movePos</methodName>
  <array><int>1</int><int>50</int></array>
</methodCall>

<!-- Response (OK) -->
<?xml version="1.0" encoding="UTF-8"?>
<methodResponse>
  <array><int>1</int></array>
</methodResponse>

<!-- Response (Fault) -->
<?xml version="1.0" encoding="UTF-8"?>
<methodResponse>
  <fault><array><string>Device 99 not found</string><int>4</int></array></fault>
</methodResponse>

<!-- Unsolicited Event (after movement) -->
<?xml version="1.0" encoding="UTF-8"?>
<methodCall>
  <methodName>selve.GW.event.device.moveResult</methodName>
  <array>
    <int>1</int>   <!-- device_id -->
    <int>50</int>  <!-- position -->
    <int>50</int>  <!-- target -->
    <int>0</int>   <!-- tilt -->
    <int>0</int>   <!-- unreachable -->
  </array>
</methodCall>
```
