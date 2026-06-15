# Meshtastic Python Client

A full-featured desktop application for interacting with [Meshtastic](https://meshtastic.org) devices, built in Python. Mirrors the functionality of the [Meshtastic Web Client](https://client.meshtastic.org).

## Features

| Feature | Description |
|---|---|
| **Connection Manager** | Connect via Serial/USB or TCP/IP network |
| **Messages** | Real-time channel chat and direct messaging |
| **Nodes** | View all mesh network nodes with signal, battery, and GPS data |
| **Map** | Interactive map displaying node positions (requires `tkintermapview`) |
| **Settings** | Full device configuration: Device Config, LoRa Radio, Channels, Module Config |
| **Device Actions** | Reboot and factory reset |

## Requirements

- Python 3.8 or newer
- A Meshtastic device connected via USB or accessible on your network

## Installation

### Windows

```bat
install.bat
```

### Linux / macOS

```bash
chmod +x install.sh run.sh
./install.sh
```

### Manual Install

```bash
pip install -r requirements.txt
```

**Required packages:**

| Package | Purpose |
|---|---|
| `meshtastic` | Official Meshtastic Python library |
| `customtkinter` | Modern tkinter UI framework |
| `pyserial` | Serial/USB communication |
| `Pillow` | Image support for the UI |
| `tkintermapview` | Interactive map widget (optional) |

> **Linux note:** For serial port access, your user must be in the `dialout` group:
> ```bash
> sudo usermod -a -G dialout $USER
> # Then log out and back in
> ```

## Running

### Windows
```bat
run.bat
```
or
```bash
python main.py
```

### Linux
```bash
./run.sh
```
or
```bash
python3 main.py
```

## Usage

1. **Launch** the application
2. Click **Connect** in the sidebar
3. Choose **Serial/USB** (select your COM port) or **TCP/Network** (enter IP:4403)
4. Navigate using the sidebar:
   - ** Messages** — Send/receive channel messages and direct messages
   - ** Map** — View node locations on an interactive map
   - ** Nodes** — Browse all discovered nodes with detailed telemetry
   - ** Settings** — Configure your device (Device, LoRa, Channels, Modules)
5. Click **Disconnect** to safely disconnect from the device

## Connection Methods

### Serial / USB
Connect your Meshtastic device via USB cable. The application will auto-detect available ports.
- Windows: `COM3`, `COM4`, etc.
- Linux: `/dev/ttyUSB0`, `/dev/ttyACM0`, etc.

### TCP / Network
Connect to a node running the HTTP API, or a node on your local network.
- Default port: `4403`
- Example: `192.168.1.100:4403`

## Architecture

```
main.py                  - Entry point and dependency check
meshtastic_core.py       - Device connection and data management
meshtastic_app.py        - Main application window and navigation
meshtastic_ui_connect.py - Connection dialog and status bar
meshtastic_ui_messages.py - Messages/chat view
meshtastic_ui_nodes.py   - Nodes list view
meshtastic_ui_map.py     - Map view
meshtastic_ui_settings.py - Settings/configuration panels
```

## License

This application uses the official [Meshtastic Python library](https://github.com/meshtastic/python) 
and references the [Meshtastic Web Client](https://github.com/meshtastic/web) for feature parity.
Meshtastic is licensed under GPL-3.0.
