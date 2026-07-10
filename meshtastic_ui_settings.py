"""
meshtastic_ui_settings.py - Settings/configuration view for Meshtastic Python Client.
Covers Device Config, Radio/LoRa Config, Channel Config, and Module Config tabs,
mirroring the web client Settings page.
"""

import threading
import base64
import os
import customtkinter as ctk
from typing import Dict, Any, Optional, List, Union, Callable
from meshtastic_core import MeshConnection

# ---------------------------------------------------------------------------
# Enum maps: index -> name for every protobuf enum used in settings
# ---------------------------------------------------------------------------

ROLE_MAP = {
    0: "CLIENT", 1: "CLIENT_MUTE", 2: "ROUTER", 3: "ROUTER_CLIENT",
    4: "REPEATER", 5: "TRACKER", 6: "SENSOR", 7: "TAK",
    8: "CLIENT_HIDDEN", 9: "LOST_AND_FOUND", 10: "TAK_TRACKER",
}

GPS_FORMAT_MAP = {
    0: "DEC", 1: "DMS", 2: "UTM", 3: "MGRS", 4: "OLC", 5: "OSGR",
}

UNITS_MAP = {0: "METRIC", 1: "IMPERIAL"}

OLED_MAP = {0: "OLED_AUTO", 1: "OLED_SSD1306", 2: "OLED_SH1106", 3: "OLED_SH1107"}

DISPLAY_MODE_MAP = {0: "DEFAULT", 1: "TWOCOLOR", 2: "INVERTED", 3: "COLOR"}

BT_MODE_MAP = {0: "RANDOM_PIN", 1: "FIXED_PIN", 2: "NO_PIN"}

MODEM_PRESET_MAP = {
    0: "LONG_FAST", 1: "LONG_MODERATE", 2: "LONG_SLOW",
    3: "MEDIUM_SLOW", 4: "MEDIUM_FAST",
    5: "SHORT_SLOW", 6: "SHORT_FAST", 7: "SHORT_TURBO",
}

REGION_MAP = {
    0: "UNSET", 1: "US", 2: "EU_433", 3: "EU_868", 4: "CN", 5: "JP",
    6: "ANZ", 7: "KR", 8: "TW", 9: "RU", 10: "IN", 11: "NZ_865",
    12: "TH", 13: "LORA_24", 14: "UA_433", 15: "UA_868",
    16: "MY_433", 17: "MY_919", 18: "SG_923",
}

REBROADCAST_MAP = {
    0: "ALL", 1: "ALL_SKIP_DECODING", 2: "LOCAL_ONLY", 3: "KNOWN_ONLY",
}

GPS_MODE_MAP = {0: "DISABLED", 1: "ENABLED", 2: "NOT_PRESENT"}

ADDRESS_MODE_MAP = {0: "DHCP", 1: "STATIC"}

SERIAL_BAUD_MAP = {
    0: "DEFAULT", 1: "110", 2: "300", 3: "600", 4: "1200", 5: "2400",
    6: "4800", 7: "9600", 8: "19200", 9: "38400", 10: "57600",
    11: "115200", 12: "230400", 13: "460800", 14: "576000", 15: "921600",
}

SERIAL_MODE_MAP = {
    0: "DEFAULT", 1: "SIMPLE", 2: "PROTO", 3: "TEXTMSG", 4: "NMEA", 5: "CALTOPO",
}


def _map_names(enum_map: dict) -> List[str]:
    """Return sorted-by-key list of name strings from an enum map."""
    return [enum_map[k] for k in sorted(enum_map)]


def _index_to_name(enum_map: dict, index: int) -> str:
    """Convert an integer enum index to its display name, fallback to first."""
    return enum_map.get(int(index), list(enum_map.values())[0])


def _name_to_index(enum_map: dict, name: str) -> int:
    """Convert a display name back to its integer index."""
    for k, v in enum_map.items():
        if v == name:
            return k
    return 0


class LabeledEntry(ctk.CTkFrame):
    """A label + entry field combo."""
    def __init__(self, parent, label: str, default: str = "",
                 placeholder: str = "", readonly: bool = False, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=label, anchor="w",
                     font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=(0, 8), sticky="w")
        self.entry = ctk.CTkEntry(self, placeholder_text=placeholder)
        self.entry.grid(row=0, column=1, sticky="ew")
        if default:
            self.entry.insert(0, str(default))
        if readonly:
            self.entry.configure(state="readonly")

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str):
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        self.entry.insert(0, str(value))


class LabeledSwitch(ctk.CTkFrame):
    """A label + toggle switch combo."""
    def __init__(self, parent, label: str, default: bool = False,
                 description: str = "", **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.var = ctk.BooleanVar(value=default)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text=label, anchor="w",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="w")
        self.switch = ctk.CTkSwitch(top, text="", variable=self.var)
        self.switch.grid(row=0, column=1)

        if description:
            ctk.CTkLabel(self, text=description,
                         font=ctk.CTkFont(size=11),
                         text_color="gray", anchor="w",
                         wraplength=420).grid(row=1, column=0, sticky="w")

    def get(self) -> bool:
        return self.var.get()

    def set(self, value: bool):
        self.var.set(value)


class LabeledOption(ctk.CTkFrame):
    """
    A label + option menu combo.
    Pass enum_map (dict of int->str) to enable automatic int↔name conversion.
    get() returns the integer index when enum_map is set.
    set() accepts either an int index or a string name.
    """
    def __init__(self, parent, label: str, values: list,
                 default: str = "", enum_map: dict = None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self._enum_map = enum_map  # int -> str
        ctk.CTkLabel(self, text=label, anchor="w",
                     font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=(0, 8), sticky="w")
        self.var = ctk.StringVar(value=default or (values[0] if values else ""))
        self.menu = ctk.CTkOptionMenu(self, variable=self.var, values=values)
        self.menu.grid(row=0, column=1, sticky="ew")

    def get(self) -> Union[int, str]:
        """Return integer index if enum_map is set, otherwise the string value."""
        name = self.var.get()
        if self._enum_map is not None:
            return _name_to_index(self._enum_map, name)
        return name

    def get_name(self) -> str:
        """Always return the display name string."""
        return self.var.get()

    def set(self, value: Union[int, str]):
        """Accept an int index or a string name; display the name."""
        if self._enum_map is not None and isinstance(value, (int, float)):
            name = _index_to_name(self._enum_map, int(value))
        else:
            name = str(value)
        # Only set if the name is a valid option
        if self._enum_map is not None:
            valid = list(self._enum_map.values())
        else:
            valid = None
        if valid is None or name in valid:
            self.var.set(name)
        elif valid:
            self.var.set(valid[0])


class SectionFrame(ctk.CTkFrame):
    """A labeled section with a divider."""
    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, corner_radius=8, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")
        self._row = 1

    def add_widget(self, widget: ctk.CTkBaseClass):
        widget.grid(row=self._row, column=0, padx=12, pady=4, sticky="ew")
        self._row += 1
        return widget

    def add_spacer(self):
        ctk.CTkFrame(self, height=2, fg_color=("gray80", "gray30")).grid(
            row=self._row, column=0, padx=12, pady=4, sticky="ew")
        self._row += 1


class DeviceConfigTab(ctk.CTkScrollableFrame):
    """Device Config settings tab."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._widgets = {}
        self._build_ui()

    def _build_ui(self):
        # Device section
        device_sec = SectionFrame(self, title="Device")
        device_sec.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["role"] = device_sec.add_widget(
            LabeledOption(device_sec, "Role", _map_names(ROLE_MAP),
                          enum_map=ROLE_MAP))
        self._widgets["serial_enabled"] = device_sec.add_widget(
            LabeledSwitch(device_sec, "Serial Enabled",
                          description="Enable the serial console on UART"))
        self._widgets["debug_log_enabled"] = device_sec.add_widget(
            LabeledSwitch(device_sec, "Debug Log Enabled",
                          description="Enable debug log output on the serial console"))
        self._widgets["node_info_broadcast_secs"] = device_sec.add_widget(
            LabeledEntry(device_sec, "Node Info Broadcast Interval (s)",
                         placeholder="900"))
        self._widgets["rebroadcast_mode"] = device_sec.add_widget(
            LabeledOption(device_sec, "Rebroadcast Mode", _map_names(REBROADCAST_MAP),
                          enum_map=REBROADCAST_MAP))

        # Position section
        pos_sec = SectionFrame(self, title="Position")
        pos_sec.grid(row=1, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["gps_mode"] = pos_sec.add_widget(
            LabeledOption(pos_sec, "GPS Mode", _map_names(GPS_MODE_MAP),
                          enum_map=GPS_MODE_MAP))
        self._widgets["gps_enabled"] = pos_sec.add_widget(
            LabeledSwitch(pos_sec, "GPS Enabled",
                          description="Enable the GPS module on this device"))
        self._widgets["fixed_position"] = pos_sec.add_widget(
            LabeledSwitch(pos_sec, "Fixed Position",
                          description="Use a manually set fixed position"))
        self._widgets["gps_update_interval"] = pos_sec.add_widget(
            LabeledEntry(pos_sec, "GPS Update Interval (s)", placeholder="0 = default"))
        self._widgets["position_broadcast_secs"] = pos_sec.add_widget(
            LabeledEntry(pos_sec, "Position Broadcast Interval (s)", placeholder="900"))

        # Power section
        power_sec = SectionFrame(self, title="Power")
        power_sec.grid(row=2, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["is_power_saving"] = power_sec.add_widget(
            LabeledSwitch(power_sec, "Power Saving Mode",
                          description="Enable power saving features for battery-operated nodes"))
        self._widgets["on_battery_shutdown_after_secs"] = power_sec.add_widget(
            LabeledEntry(power_sec, "Battery Shutdown After (s)", placeholder="0 = never"))
        self._widgets["ls_secs"] = power_sec.add_widget(
            LabeledEntry(power_sec, "Light Sleep Duration (s)", placeholder="300"))

        # Network section
        net_sec = SectionFrame(self, title="Network")
        net_sec.grid(row=3, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["wifi_enabled"] = net_sec.add_widget(
            LabeledSwitch(net_sec, "WiFi Enabled"))
        self._widgets["wifi_ssid"] = net_sec.add_widget(
            LabeledEntry(net_sec, "WiFi SSID", placeholder="Network name"))
        self._widgets["wifi_psk"] = net_sec.add_widget(
            LabeledEntry(net_sec, "WiFi Password", placeholder="Password"))
        self._widgets["ntp_server"] = net_sec.add_widget(
            LabeledEntry(net_sec, "NTP Server", placeholder="0.pool.ntp.org"))
        self._widgets["eth_enabled"] = net_sec.add_widget(
            LabeledSwitch(net_sec, "Ethernet Enabled"))
        self._widgets["address_mode"] = net_sec.add_widget(
            LabeledOption(net_sec, "Address Mode", _map_names(ADDRESS_MODE_MAP),
                          enum_map=ADDRESS_MODE_MAP))

        # Display section
        disp_sec = SectionFrame(self, title="Display")
        disp_sec.grid(row=4, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["screen_on_secs"] = disp_sec.add_widget(
            LabeledEntry(disp_sec, "Screen On Duration (s)", placeholder="0 = always"))
        self._widgets["flip_screen"] = disp_sec.add_widget(
            LabeledSwitch(disp_sec, "Flip Screen"))
        self._widgets["compass_north_top"] = disp_sec.add_widget(
            LabeledSwitch(disp_sec, "Compass North Top"))
        self._widgets["gps_format"] = disp_sec.add_widget(
            LabeledOption(disp_sec, "GPS Coordinate Format", _map_names(GPS_FORMAT_MAP),
                          enum_map=GPS_FORMAT_MAP))
        self._widgets["units"] = disp_sec.add_widget(
            LabeledOption(disp_sec, "Display Units", _map_names(UNITS_MAP),
                          enum_map=UNITS_MAP))
        self._widgets["oled"] = disp_sec.add_widget(
            LabeledOption(disp_sec, "OLED Type", _map_names(OLED_MAP),
                          enum_map=OLED_MAP))
        self._widgets["displaymode"] = disp_sec.add_widget(
            LabeledOption(disp_sec, "Display Mode", _map_names(DISPLAY_MODE_MAP),
                          enum_map=DISPLAY_MODE_MAP))

        # Bluetooth section
        bt_sec = SectionFrame(self, title="Bluetooth")
        bt_sec.grid(row=5, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["bluetooth_enabled"] = bt_sec.add_widget(
            LabeledSwitch(bt_sec, "Bluetooth Enabled"))
        self._widgets["bluetooth_mode"] = bt_sec.add_widget(
            LabeledOption(bt_sec, "Pairing Mode", _map_names(BT_MODE_MAP),
                          enum_map=BT_MODE_MAP))
        self._widgets["fixed_pin"] = bt_sec.add_widget(
            LabeledEntry(bt_sec, "Fixed PIN", placeholder="123456"))

    def load_config(self, config: Dict[str, Any]):
        """Populate fields from device config dict."""
        mapping = {
            "role":                        ("device",   "role"),
            "serial_enabled":              ("device",   "serial_enabled"),
            "debug_log_enabled":           ("device",   "debug_log_enabled"),
            "node_info_broadcast_secs":    ("device",   "node_info_broadcast_secs"),
            "rebroadcast_mode":            ("device",   "rebroadcast_mode"),
            "gps_mode":                    ("position", "gps_mode"),
            "gps_enabled":                 ("position", "gps_enabled"),
            "fixed_position":              ("position", "fixed_position"),
            "gps_update_interval":         ("position", "gps_update_interval"),
            "position_broadcast_secs":     ("position", "position_broadcast_secs"),
            "is_power_saving":             ("power",    "is_power_saving"),
            "on_battery_shutdown_after_secs": ("power", "on_battery_shutdown_after_secs"),
            "ls_secs":                     ("power",    "ls_secs"),
            "wifi_enabled":                ("network",  "wifi_enabled"),
            "wifi_ssid":                   ("network",  "wifi_ssid"),
            "ntp_server":                  ("network",  "ntp_server"),
            "eth_enabled":                 ("network",  "eth_enabled"),
            "address_mode":                ("network",  "address_mode"),
            "screen_on_secs":              ("display",  "screen_on_secs"),
            "flip_screen":                 ("display",  "flip_screen"),
            "compass_north_top":           ("display",  "compass_north_top"),
            "gps_format":                  ("display",  "gps_format"),
            "units":                       ("display",  "units"),
            "oled":                        ("display",  "oled"),
            "displaymode":                 ("display",  "displaymode"),
            "bluetooth_enabled":           ("bluetooth","enabled"),
            "bluetooth_mode":              ("bluetooth","mode"),
            "fixed_pin":                   ("bluetooth","fixed_pin"),
        }
        for widget_key, (section, field) in mapping.items():
            value = config.get(section, {}).get(field)
            if value is not None and widget_key in self._widgets:
                try:
                    self._widgets[widget_key].set(value)
                except Exception:
                    pass


    def get_config(self) -> Dict[str, Any]:
        """Collect current widget values into a saveable config dict."""
        def _int(key):
            try:
                v = self._widgets[key].get()
                return int(v) if v not in (None, "") else None
            except (ValueError, TypeError):
                return None

        def _bool(key):
            return bool(self._widgets[key].get())

        def _str(key):
            v = self._widgets[key].get()
            return str(v) if v not in (None, "") else None

        def _enum(key):
            return self._widgets[key].get()  # int via enum_map

        return {
            "device": {
                "role":                     _enum("role"),
                "serial_enabled":           _bool("serial_enabled"),
                "debug_log_enabled":        _bool("debug_log_enabled"),
                "node_info_broadcast_secs": _int("node_info_broadcast_secs"),
                "rebroadcast_mode":         _enum("rebroadcast_mode"),
            },
            "position": {
                "gps_mode":                 _enum("gps_mode"),
                "gps_enabled":              _bool("gps_enabled"),
                "fixed_position":           _bool("fixed_position"),
                "gps_update_interval":      _int("gps_update_interval"),
                "position_broadcast_secs":  _int("position_broadcast_secs"),
            },
            "power": {
                "is_power_saving":                  _bool("is_power_saving"),
                "on_battery_shutdown_after_secs":   _int("on_battery_shutdown_after_secs"),
                "ls_secs":                          _int("ls_secs"),
            },
            "network": {
                "wifi_enabled":  _bool("wifi_enabled"),
                "wifi_ssid":     _str("wifi_ssid"),
                "wifi_psk":      _str("wifi_psk"),
                "ntp_server":    _str("ntp_server"),
                "eth_enabled":   _bool("eth_enabled"),
                "address_mode":  _enum("address_mode"),
            },
            "display": {
                "screen_on_secs":     _int("screen_on_secs"),
                "flip_screen":        _bool("flip_screen"),
                "compass_north_top":  _bool("compass_north_top"),
                "gps_format":         _enum("gps_format"),
                "units":              _enum("units"),
                "oled":               _enum("oled"),
                "displaymode":        _enum("displaymode"),
            },
            "bluetooth": {
                "enabled":   _bool("bluetooth_enabled"),
                "mode":      _enum("bluetooth_mode"),
                "fixed_pin": _int("fixed_pin"),
            },
        }


class RadioConfigTab(ctk.CTkScrollableFrame):
    """LoRa Radio Config settings tab."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._widgets = {}
        self._build_ui()

    def _build_ui(self):
        lora_sec = SectionFrame(self, title="LoRa Radio")
        lora_sec.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["use_preset"] = lora_sec.add_widget(
            LabeledSwitch(lora_sec, "Use Preset Modem Config",
                          description="Use a predefined modem preset instead of custom settings"))

        self._widgets["modem_preset"] = lora_sec.add_widget(
            LabeledOption(lora_sec, "Modem Preset", _map_names(MODEM_PRESET_MAP),
                          enum_map=MODEM_PRESET_MAP))

        self._widgets["region"] = lora_sec.add_widget(
            LabeledOption(lora_sec, "Region", _map_names(REGION_MAP),
                          enum_map=REGION_MAP))

        self._widgets["hop_limit"] = lora_sec.add_widget(
            LabeledEntry(lora_sec, "Hop Limit", placeholder="3"))
        self._widgets["tx_enabled"] = lora_sec.add_widget(
            LabeledSwitch(lora_sec, "Transmit Enabled",
                          description="Allow the radio to transmit messages"))
        self._widgets["tx_power"] = lora_sec.add_widget(
            LabeledEntry(lora_sec, "TX Power (dBm)", placeholder="0 = max"))
        self._widgets["channel_num"] = lora_sec.add_widget(
            LabeledEntry(lora_sec, "Channel Number", placeholder="0 = auto"))
        self._widgets["ignore_mqtt"] = lora_sec.add_widget(
            LabeledSwitch(lora_sec, "Ignore MQTT",
                          description="Ignore messages that are forwarded over MQTT"))
        self._widgets["override_duty_cycle"] = lora_sec.add_widget(
            LabeledSwitch(lora_sec, "Override Duty Cycle",
                          description="Override the duty cycle limit (use with caution)"))
        self._widgets["sx126x_rx_boosted_gain"] = lora_sec.add_widget(
            LabeledSwitch(lora_sec, "SX126X Boosted RX Gain",
                          description="Enable boosted receive gain on SX1262/SX1268 chips"))

    def load_config(self, config: Dict[str, Any]):
        lora = config.get("lora", {})
        mapping = {
            "use_preset": "use_preset",
            "modem_preset": "modem_preset",
            "region": "region",
            "hop_limit": "hop_limit",
            "tx_enabled": "tx_enabled",
            "tx_power": "tx_power",
            "channel_num": "channel_num",
            "ignore_mqtt": "ignore_mqtt",
            "override_duty_cycle": "override_duty_cycle",
            "sx126x_rx_boosted_gain": "sx126x_rx_boosted_gain",
        }
        for widget_key, field in mapping.items():
            value = lora.get(field)
            if value is not None and widget_key in self._widgets:
                try:
                    self._widgets[widget_key].set(value)
                except Exception:
                    pass

    def get_config(self) -> Dict[str, Any]:
        """Collect current widget values into a saveable lora config dict."""
        def _int(key):
            try:
                v = self._widgets[key].get()
                return int(v) if v not in (None, "") else None
            except (ValueError, TypeError):
                return None

        return {
            "lora": {
                "use_preset":            bool(self._widgets["use_preset"].get()),
                "modem_preset":          self._widgets["modem_preset"].get(),
                "region":                self._widgets["region"].get(),
                "hop_limit":             _int("hop_limit"),
                "tx_enabled":            bool(self._widgets["tx_enabled"].get()),
                "tx_power":              _int("tx_power"),
                "channel_num":           _int("channel_num"),
                "ignore_mqtt":           bool(self._widgets["ignore_mqtt"].get()),
                "override_duty_cycle":   bool(self._widgets["override_duty_cycle"].get()),
                "sx126x_rx_boosted_gain":bool(self._widgets["sx126x_rx_boosted_gain"].get()),
            }
        }


class ModuleConfigTab(ctk.CTkScrollableFrame):
    """Module Config settings tab."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._widgets = {}
        self._build_ui()

    def _build_ui(self):
        # MQTT
        mqtt_sec = SectionFrame(self, title="MQTT")
        mqtt_sec.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["mqtt_enabled"] = mqtt_sec.add_widget(
            LabeledSwitch(mqtt_sec, "MQTT Enabled",
                          description="Forward mesh packets to an MQTT broker"))
        self._widgets["mqtt_address"] = mqtt_sec.add_widget(
            LabeledEntry(mqtt_sec, "MQTT Server", placeholder="mqtt.meshtastic.org"))
        self._widgets["mqtt_username"] = mqtt_sec.add_widget(
            LabeledEntry(mqtt_sec, "MQTT Username", placeholder="meshdev"))
        self._widgets["mqtt_password"] = mqtt_sec.add_widget(
            LabeledEntry(mqtt_sec, "MQTT Password", placeholder="large4cats"))
        self._widgets["mqtt_encryption_enabled"] = mqtt_sec.add_widget(
            LabeledSwitch(mqtt_sec, "MQTT Encryption",
                          description="Encrypt MQTT messages with PSK"))
        self._widgets["mqtt_json_enabled"] = mqtt_sec.add_widget(
            LabeledSwitch(mqtt_sec, "MQTT JSON",
                          description="Publish decoded JSON payloads to MQTT"))
        self._widgets["mqtt_tls_enabled"] = mqtt_sec.add_widget(
            LabeledSwitch(mqtt_sec, "MQTT TLS",
                          description="Use TLS/SSL for MQTT connection"))

        # Telemetry
        tele_sec = SectionFrame(self, title="Telemetry")
        tele_sec.grid(row=1, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["device_update_interval"] = tele_sec.add_widget(
            LabeledEntry(tele_sec, "Device Update Interval (s)", placeholder="0 = default"))
        self._widgets["environment_measurement_enabled"] = tele_sec.add_widget(
            LabeledSwitch(tele_sec, "Environment Sensor Enabled"))
        self._widgets["environment_update_interval"] = tele_sec.add_widget(
            LabeledEntry(tele_sec, "Environment Update Interval (s)", placeholder="0 = default"))
        self._widgets["air_quality_interval"] = tele_sec.add_widget(
            LabeledEntry(tele_sec, "Air Quality Interval (s)", placeholder="0 = default"))

        # Serial Module
        ser_sec = SectionFrame(self, title="Serial Module")
        ser_sec.grid(row=2, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["serial_module_enabled"] = ser_sec.add_widget(
            LabeledSwitch(ser_sec, "Serial Module Enabled"))
        self._widgets["serial_module_echo"] = ser_sec.add_widget(
            LabeledSwitch(ser_sec, "Echo",
                          description="Echo received packets back to the serial port"))
        self._widgets["serial_module_baud"] = ser_sec.add_widget(
            LabeledOption(ser_sec, "Baud Rate", _map_names(SERIAL_BAUD_MAP),
                          enum_map=SERIAL_BAUD_MAP))
        self._widgets["serial_module_mode"] = ser_sec.add_widget(
            LabeledOption(ser_sec, "Mode", _map_names(SERIAL_MODE_MAP),
                          enum_map=SERIAL_MODE_MAP))

        # Store & Forward
        sf_sec = SectionFrame(self, title="Store & Forward")
        sf_sec.grid(row=3, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["sf_enabled"] = sf_sec.add_widget(
            LabeledSwitch(sf_sec, "Store & Forward Enabled",
                          description="Enable store and forward for offline nodes"))
        self._widgets["sf_heartbeat"] = sf_sec.add_widget(
            LabeledSwitch(sf_sec, "Heartbeat"))
        self._widgets["sf_records"] = sf_sec.add_widget(
            LabeledEntry(sf_sec, "Max Records", placeholder="0 = default"))
        self._widgets["sf_history_return_window"] = sf_sec.add_widget(
            LabeledEntry(sf_sec, "History Return Window (s)", placeholder="0 = default"))

        # Range Test
        rt_sec = SectionFrame(self, title="Range Test")
        rt_sec.grid(row=4, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["rt_enabled"] = rt_sec.add_widget(
            LabeledSwitch(rt_sec, "Range Test Enabled"))
        self._widgets["rt_sender"] = rt_sec.add_widget(
            LabeledEntry(rt_sec, "Sender Interval (s)", placeholder="0 = disabled"))
        self._widgets["rt_save"] = rt_sec.add_widget(
            LabeledSwitch(rt_sec, "Save CSV",
                          description="Save range test results to a CSV file"))

        # Neighbor Info
        ni_sec = SectionFrame(self, title="Neighbor Info")
        ni_sec.grid(row=5, column=0, padx=8, pady=8, sticky="ew")

        self._widgets["ni_enabled"] = ni_sec.add_widget(
            LabeledSwitch(ni_sec, "Neighbor Info Enabled",
                          description="Broadcast neighbor info packets"))
        self._widgets["ni_update_interval"] = ni_sec.add_widget(
            LabeledEntry(ni_sec, "Update Interval (s)", placeholder="0 = default"))

    def load_config(self, config: Dict[str, Any]):
        mqtt = config.get("mqtt", {})
        tele = config.get("telemetry", {})
        serial = config.get("serial", {})
        sf = config.get("store_and_forward", {})
        rt = config.get("range_test", {})
        ni = config.get("neighbor_info", {})

        pairs = [
            ("mqtt_enabled",                    mqtt.get("enabled")),
            ("mqtt_address",                    mqtt.get("address")),
            ("mqtt_username",                   mqtt.get("username")),
            ("mqtt_encryption_enabled",         mqtt.get("encryption_enabled")),
            ("mqtt_json_enabled",               mqtt.get("json_enabled")),
            ("mqtt_tls_enabled",                mqtt.get("tls_enabled")),
            ("device_update_interval",          tele.get("device_update_interval")),
            ("environment_measurement_enabled", tele.get("environment_measurement_enabled")),
            ("environment_update_interval",     tele.get("environment_update_interval")),
            ("air_quality_interval",            tele.get("air_quality_interval")),
            ("serial_module_enabled",           serial.get("enabled")),
            ("serial_module_echo",              serial.get("echo")),
            ("serial_module_baud",              serial.get("baud")),   # int -> name via enum_map
            ("serial_module_mode",              serial.get("mode")),   # int -> name via enum_map
            ("sf_enabled",                      sf.get("enabled")),
            ("sf_heartbeat",                    sf.get("heartbeat")),
            ("sf_records",                      sf.get("records")),
            ("sf_history_return_window",        sf.get("history_return_window")),
            ("rt_enabled",                      rt.get("enabled")),
            ("rt_sender",                       rt.get("sender")),
            ("rt_save",                         rt.get("save")),
            ("ni_enabled",                      ni.get("enabled")),
            ("ni_update_interval",              ni.get("update_interval")),
        ]
        for key, value in pairs:
            if value is not None and key in self._widgets:
                try:
                    self._widgets[key].set(value)
                except Exception:
                    pass

    def get_config(self) -> Dict[str, Any]:
        """Collect current widget values into a saveable module config dict."""
        def _int(key):
            try:
                v = self._widgets[key].get()
                return int(v) if v not in (None, "") else None
            except (ValueError, TypeError):
                return None

        def _bool(key):
            return bool(self._widgets[key].get())

        def _enum(key):
            return self._widgets[key].get()  # int via enum_map

        return {
            "mqtt": {
                "enabled":              _bool("mqtt_enabled"),
                "address":              self._widgets["mqtt_address"].get() or None,
                "username":             self._widgets["mqtt_username"].get() or None,
                "encryption_enabled":   _bool("mqtt_encryption_enabled"),
                "json_enabled":         _bool("mqtt_json_enabled"),
                "tls_enabled":          _bool("mqtt_tls_enabled"),
            },
            "telemetry": {
                "device_update_interval":           _int("device_update_interval"),
                "environment_measurement_enabled":  _bool("environment_measurement_enabled"),
                "environment_update_interval":      _int("environment_update_interval"),
                "air_quality_interval":             _int("air_quality_interval"),
            },
            "serial": {
                "enabled": _bool("serial_module_enabled"),
                "echo":    _bool("serial_module_echo"),
                "baud":    _enum("serial_module_baud"),
                "mode":    _enum("serial_module_mode"),
            },
            "store_and_forward": {
                "enabled":              _bool("sf_enabled"),
                "heartbeat":            _bool("sf_heartbeat"),
                "records":              _int("sf_records"),
                "history_return_window":_int("sf_history_return_window"),
            },
            "range_test": {
                "enabled": _bool("rt_enabled"),
                "sender":  _int("rt_sender"),
                "save":    _bool("rt_save"),
            },
            "neighbor_info": {
                "enabled":         _bool("ni_enabled"),
                "update_interval": _int("ni_update_interval"),
            },
        }


class ChannelEditDialog(ctk.CTkToplevel):
    """Dialog to create or edit a channel."""

    PSK_DEFAULT = "Default Key (AQ==)"
    PSK_NONE    = "No Encryption"
    PSK_RANDOM  = "Generate Random 256-bit Key"
    PSK_CUSTOM  = "Custom (Base64)"

    def __init__(self, parent, channel: dict = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.result = None
        self._generated_psk = None
        ch = channel or {}
        is_new = (ch.get("role", 0) == 0)

        self.title("Add Channel" if is_new else f"Edit Channel {ch.get('index', '')}")
        self.geometry("480x380")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        frame.grid_columnconfigure(1, weight=1)

        row = 0

        # Channel index (read-only display)
        ctk.CTkLabel(frame, text="Slot Index:", anchor="w").grid(
            row=row, column=0, padx=8, pady=6, sticky="w")
        ctk.CTkLabel(frame, text=str(ch.get("index", "?")),
                     text_color="gray").grid(row=row, column=1, padx=8, pady=6, sticky="w")
        row += 1

        # Channel name
        ctk.CTkLabel(frame, text="Channel Name:", anchor="w").grid(
            row=row, column=0, padx=8, pady=6, sticky="w")
        self._name_entry = ctk.CTkEntry(frame, placeholder_text="e.g. MyChannel")
        self._name_entry.grid(row=row, column=1, padx=8, pady=6, sticky="ew")
        existing_name = ch.get("name", "")
        if existing_name and existing_name != "Primary":
            self._name_entry.insert(0, existing_name)
        row += 1

        # Role (only show for non-primary)
        self._is_primary = (ch.get("role", 0) == 1)
        if not self._is_primary:
            ctk.CTkLabel(frame, text="Role:", anchor="w").grid(
                row=row, column=0, padx=8, pady=6, sticky="w")
            self._role_var = ctk.StringVar(value="SECONDARY")
            ctk.CTkOptionMenu(frame, variable=self._role_var,
                              values=["SECONDARY"]).grid(
                row=row, column=1, padx=8, pady=6, sticky="w")
            row += 1

        # PSK type
        ctk.CTkLabel(frame, text="Encryption Key:", anchor="w").grid(
            row=row, column=0, padx=8, pady=6, sticky="w")
        existing_psk = ch.get("psk", "")
        if existing_psk == "AQ==":
            default_psk_type = self.PSK_DEFAULT
        elif not existing_psk or existing_psk == "AA==":
            default_psk_type = self.PSK_NONE
        else:
            default_psk_type = self.PSK_CUSTOM

        self._psk_type = ctk.StringVar(value=default_psk_type)
        psk_menu = ctk.CTkOptionMenu(
            frame, variable=self._psk_type,
            values=[self.PSK_DEFAULT, self.PSK_NONE,
                    self.PSK_RANDOM, self.PSK_CUSTOM],
            command=self._on_psk_type_change)
        psk_menu.grid(row=row, column=1, padx=8, pady=6, sticky="ew")
        row += 1

        # Custom PSK entry
        ctk.CTkLabel(frame, text="Custom Key (Base64):", anchor="w").grid(
            row=row, column=0, padx=8, pady=6, sticky="w")
        self._psk_entry = ctk.CTkEntry(frame, placeholder_text="Base64-encoded key bytes")
        self._psk_entry.grid(row=row, column=1, padx=8, pady=6, sticky="ew")
        if default_psk_type == self.PSK_CUSTOM:
            self._psk_entry.insert(0, existing_psk)
        row += 1

        self._on_psk_type_change(default_psk_type)

        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(12, 4))
        ctk.CTkButton(btn_frame, text="Save", width=100,
                      command=self._save).grid(row=0, column=0, padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", width=100,
                      fg_color="gray", hover_color="#555",
                      command=self.destroy).grid(row=0, column=1, padx=8)

    def _on_psk_type_change(self, val):
        state = "normal" if val == self.PSK_CUSTOM else "disabled"
        self._psk_entry.configure(state=state)
        if val == self.PSK_RANDOM:
            self._psk_entry.configure(state="normal")
            new_key = base64.b64encode(os.urandom(32)).decode()
            self._psk_entry.delete(0, "end")
            self._psk_entry.insert(0, new_key)
            self._psk_entry.configure(state="disabled")
            self._generated_psk = new_key
        else:
            self._generated_psk = None

    def _save(self):
        name = self._name_entry.get().strip()
        
        if not name:
            self._show_error("Channel name cannot be empty.")
            return
        
        role = 1 if self._is_primary else 2  # PRIMARY=1, SECONDARY=2
        psk_type = self._psk_type.get()

        if psk_type == self.PSK_DEFAULT:
            psk_bytes = bytes([1])
        elif psk_type == self.PSK_NONE:
            psk_bytes = bytes([0])
        elif psk_type == self.PSK_RANDOM:
            raw = self._generated_psk or base64.b64encode(os.urandom(32)).decode()
            psk_bytes = base64.b64decode(raw)
        else:  # CUSTOM
            raw = self._psk_entry.get().strip()
            if not raw:
                self._show_error("Custom key cannot be empty.")
                return
            try:
                psk_bytes = base64.b64decode(raw)
            except Exception:
                self._show_error("Invalid Base64 key.")
                return
            if len(psk_bytes) not in (0, 1, 16, 32):
                self._show_error("Key must be 0, 1, 16, or 32 bytes.")
                return

        self.result = {"name": name, "role": role, "psk_bytes": psk_bytes}
        self.destroy()

    def _show_error(self, msg):
        ctk.CTkLabel(self, text=msg, text_color="red").grid(
            row=99, column=0, padx=16, pady=4)


class ChannelConfigTab(ctk.CTkScrollableFrame):
    """Channel configuration tab — view, add, edit, and delete channels."""

    MAX_CHANNELS = 8

    def __init__(self, parent, connection: MeshConnection,
                 on_channels_changed: Optional[Callable[[List[Dict]], None]] = None,
                 **kwargs):
        super().__init__(parent, **kwargs)
        self.connection = connection
        self._on_channels_changed = on_channels_changed
        self._channels: list = []
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Channel Configuration",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w")

        self._add_btn = ctk.CTkButton(
            header, text="＋ Add Channel", width=130,
            fg_color="#1a7a3c", hover_color="#145e2e",
            command=self._add_channel)
        self._add_btn.grid(row=0, column=1, padx=(8, 0))

        self._status = ctk.CTkLabel(self, text="", text_color="gray",
                                    font=ctk.CTkFont(size=11))
        self._status.grid(row=1, column=0, padx=12, pady=(0, 4), sticky="w")

        self.channel_container = ctk.CTkFrame(self, corner_radius=0,
                                              fg_color="transparent")
        self.channel_container.grid(row=2, column=0, sticky="ew")
        self.channel_container.grid_columnconfigure(0, weight=1)

    def load_channels(self, channels: list):
        self._channels = channels or []
        self._render()

    def _render(self):
        for w in self.channel_container.winfo_children():
            w.destroy()

        if not self._channels:
            ctk.CTkLabel(self.channel_container,
                         text="No channel data available. Connect to a device.",
                         text_color="gray").grid(row=0, column=0, pady=12)
            return

        role_labels = {0: "DISABLED", 1: "PRIMARY", 2: "SECONDARY"}

        for i, ch in enumerate(self._channels):
            role = ch.get("role", 0)
            if role == 0:
                continue  # don't show disabled slots in the list
            self._render_channel_row(i, ch, role_labels)

        # Show disabled slots as "empty" add targets
        active_indices = {ch["index"] for ch in self._channels if ch.get("role", 0) != 0}
        for ch in self._channels:
            if ch.get("role", 0) == 0 and ch["index"] > 0:
                idx = ch["index"]
                row_frame = ctk.CTkFrame(self.channel_container,
                                         fg_color="transparent")
                row_frame.grid(row=idx + 100, column=0, padx=8, pady=2, sticky="ew")
                row_frame.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(row_frame, text=str(idx), width=24,
                             font=ctk.CTkFont(size=11),
                             text_color="#555", anchor="center").grid(
                    row=0, column=0, padx=(8, 4))
                ctk.CTkLabel(row_frame, text="— empty slot —",
                             text_color="#555",
                             font=ctk.CTkFont(size=11)).grid(
                    row=0, column=1, padx=4, sticky="w")

    def _render_channel_row(self, list_idx: int, ch: dict, role_labels: dict):
        idx   = ch.get("index", list_idx)
        name  = ch.get("name") or ("Primary" if idx == 0 else f"Channel {idx}")
        role  = ch.get("role", 0)
        psk   = ch.get("psk", "")

        if psk == "AQ==":
            enc_label, enc_color = "🔒 Default Key", "#2ecc71"
        elif not psk or psk == "AA==":
            enc_label, enc_color = "🔓 No Encryption", "orange"
        else:
            enc_label, enc_color = "🔑 Custom Key", "#3498db"

        frame = ctk.CTkFrame(self.channel_container, corner_radius=8)
        frame.grid(row=list_idx, column=0, padx=8, pady=4, sticky="ew")
        frame.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(frame, text=str(idx),
                     font=ctk.CTkFont(size=12, weight="bold"),
                     width=24, anchor="center").grid(
            row=0, column=0, padx=(8, 4), pady=8)

        ctk.CTkLabel(frame, text=name,
                     font=ctk.CTkFont(size=13), anchor="w").grid(
            row=0, column=1, padx=4, pady=8, sticky="w")

        ctk.CTkLabel(frame, text=enc_label,
                     font=ctk.CTkFont(size=11),
                     text_color=enc_color).grid(row=0, column=2, padx=8, pady=8, sticky="w")

        role_color = "#1d6fa8" if role == 1 else "gray"
        ctk.CTkLabel(frame, text=role_labels.get(role, "?"),
                     font=ctk.CTkFont(size=11),
                     text_color=role_color).grid(row=0, column=3, padx=8, pady=8)

        ctk.CTkButton(frame, text="✎ Edit", width=70,
                      command=lambda c=ch: self._edit_channel(c)).grid(
            row=0, column=4, padx=(4, 2), pady=6)

        if role != 1:  # can't delete primary
            ctk.CTkButton(frame, text="✕", width=36,
                          fg_color="#c0392b", hover_color="#a93226",
                          command=lambda c=ch: self._delete_channel(c)).grid(
                row=0, column=5, padx=(2, 8), pady=6)

    def _add_channel(self):
        if not self.connection.is_connected:
            self._status.configure(text="Not connected.", text_color="orange")
            return

        # Refresh from device and pick the next available non-primary slot.
        channels = self.connection.get_channels()
        self.load_channels(channels)
        next_slot = next(
            (ch for ch in channels if ch.get("index", -1) > 0 and ch.get("role", 0) == 0),
            None
        )
        if next_slot is None:
            self._status.configure(text="All 8 channel slots are in use.", text_color="orange")
            return

        dlg = ChannelEditDialog(self, channel=next_slot)
        self.wait_window(dlg)
        if dlg.result:
            self._save_channel(next_slot["index"], dlg.result)

    def _edit_channel(self, ch: dict):
        if not self.connection.is_connected:
            self._status.configure(text="Not connected.", text_color="orange")
            return
        dlg = ChannelEditDialog(self, channel=ch)
        self.wait_window(dlg)
        if dlg.result:
            self._save_channel(ch["index"], dlg.result)

    def _save_channel(self, index: int, result: dict):
        self._status.configure(text="Saving…", text_color="gray")

        def _do():
            ok, msg = self.connection.save_channel(
                index, result["name"], result["role"], result["psk_bytes"])
            if ok:
                msg = f"✓ {msg}"
            else:
                msg = f"✗ {msg}"
            color = "green" if ok else "red"
            if ok:
                # Reload channels from device
                channels = self.connection.get_channels()
                self.after(0, lambda: self.load_channels(channels))
                if self._on_channels_changed:
                    self.after(0, lambda: self._on_channels_changed(channels))
            self.after(0, lambda: self._status.configure(text=msg, text_color=color))
            self.after(5000, lambda: self._status.configure(text="", text_color="gray"))

        threading.Thread(target=_do, daemon=True).start()

    def _delete_channel(self, ch: dict):
        idx = ch["index"]
        dlg = ctk.CTkInputDialog(
            title="Delete Channel",
            text=f"Type 'DELETE' to remove channel {idx} '{ch.get('name', '')}':")
        if (dlg.get_input() or "").strip().upper() != "DELETE":
            return
        self._status.configure(text="Deleting…", text_color="gray")

        def _do():
            ok, msg = self.connection.delete_channel(idx)
            if ok:
                msg = f"✓ {msg}"
            else:
                msg = f"✗ {msg}"
            color = "green" if ok else "red"
            if ok:
                channels = self.connection.get_channels()
                self.after(0, lambda: self.load_channels(channels))
                if self._on_channels_changed:
                    self.after(0, lambda: self._on_channels_changed(channels))
            self.after(0, lambda: self._status.configure(text=msg, text_color=color))
            self.after(5000, lambda: self._status.configure(text="", text_color="gray"))

        threading.Thread(target=_do, daemon=True).start()


class DeviceActionsTab(ctk.CTkScrollableFrame):
    """Device actions: reboot, factory reset, etc."""

    def __init__(self, parent, connection: MeshConnection, **kwargs):
        super().__init__(parent, **kwargs)
        self.connection = connection
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Device Actions",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        # Reboot
        reboot_sec = SectionFrame(self, title="Reboot Device")
        reboot_sec.grid(row=1, column=0, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(reboot_sec,
                     text="Restart the device. It will reconnect automatically.",
                     text_color="gray",
                     font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="w")

        btn_row = ctk.CTkFrame(reboot_sec, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="w")

        self._reboot_btn = ctk.CTkButton(
            btn_row,
            text="Reboot Device",
            fg_color="#e67e22",
            hover_color="#d35400",
            command=self._reboot)
        self._reboot_btn.grid(row=0, column=0, padx=(0, 8))

        self._reboot_reconnect_btn = ctk.CTkButton(
            btn_row,
            text="Reboot & Reconnect",
            fg_color="#2980b9",
            hover_color="#1a6fa0",
            command=self._reboot_and_reconnect)
        self._reboot_reconnect_btn.grid(row=0, column=1)

        # Factory Reset
        reset_sec = SectionFrame(self, title="Factory Reset")
        reset_sec.grid(row=2, column=0, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(reset_sec,
                     text="⚠ This will erase ALL device configuration.\n"
                          "The device will return to factory defaults.",
                     text_color="orange",
                     font=ctk.CTkFont(size=12),
                     justify="left").grid(
            row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        reset_btn = ctk.CTkButton(
            reset_sec,
            text="Factory Reset",
            fg_color="#c0392b",
            hover_color="#a93226",
            command=self._factory_reset)
        reset_btn.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="w")

        # Status
        self.status_label = ctk.CTkLabel(self, text="",
                                         font=ctk.CTkFont(size=12))
        self.status_label.grid(row=3, column=0, padx=12, pady=8, sticky="w")

    def _reboot(self):
        if not self.connection.is_connected:
            self.status_label.configure(text="Not connected to a device.", text_color="orange")
            return
        self.connection.reboot_device()
        self.status_label.configure(text="Reboot initiated.", text_color="green")

    def _reboot_and_reconnect(self):
        if not self.connection.is_connected:
            self.status_label.configure(text="Not connected to a device.", text_color="orange")
            return
        ok, msg = self.connection.reboot_and_reconnect()
        color = "green" if ok else "red"
        self.status_label.configure(text=msg, text_color=color)

    def update_connection_state(self, connected: bool):
        """Enable or disable action buttons based on connection state."""
        state = "normal" if connected else "disabled"
        self._reboot_btn.configure(state=state)
        self._reboot_reconnect_btn.configure(state=state)

    def _factory_reset(self):
        if not self.connection.is_connected:
            self.status_label.configure(text="Not connected to a device.", text_color="orange")
            return
        # Confirm dialog
        dialog = ctk.CTkInputDialog(
            title="Factory Reset Confirmation",
            text="Type 'RESET' to confirm factory reset:"
        )
        result = dialog.get_input()
        if result and result.strip().upper() == "RESET":
            self.connection.factory_reset()
            self.status_label.configure(text="Factory reset initiated.", text_color="orange")
        else:
            self.status_label.configure(text="Factory reset cancelled.", text_color="gray")


class UserConfigTab(ctk.CTkScrollableFrame):
    """Tab for editing the node's long name and short name."""

    def __init__(self, parent, connection: MeshConnection, **kwargs):
        super().__init__(parent, **kwargs)
        self.connection = connection
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    def _build_ui(self):
        sec = SectionFrame(self, title="Node Identity")
        sec.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        self._long_name = sec.add_widget(
            LabeledEntry(sec, "Long Name", placeholder="My Meshtastic Node"))
        self._short_name = sec.add_widget(
            LabeledEntry(sec, "Short Name (max 4 chars)", placeholder="MESH"))

        ctk.CTkLabel(self,
                     text="Long Name: displayed in the app and on other devices' node lists.\n"
                          "Short Name: 1–4 characters shown on the node map and in brief displays.",
                     text_color="gray",
                     font=ctk.CTkFont(size=11),
                     justify="left", anchor="w", wraplength=440).grid(
            row=1, column=0, padx=20, pady=(4, 16), sticky="w")

    def load_owner(self, owner: dict):
        self._long_name.set(owner.get("long_name", ""))
        self._short_name.set(owner.get("short_name", ""))

    def get_owner(self) -> dict:
        return {
            "long_name":  self._long_name.get().strip(),
            "short_name": self._short_name.get().strip(),
        }


class SettingsView(ctk.CTkFrame):
    """
    Full settings view with tabs for Device Config, Radio Config,
    Channels, Module Config, and Device Actions.
    """

    def __init__(self, parent, connection: MeshConnection,
                 on_channels_changed: Optional[Callable[[List[Dict]], None]] = None,
                 **kwargs):
        super().__init__(parent, **kwargs)
        self.connection = connection
        self._on_channels_changed = on_channels_changed
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_ui()

    def _build_ui(self):
        # Header with save button
        header = ctk.CTkFrame(self, height=52, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Settings",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=16, pady=12)

        self.status_label = ctk.CTkLabel(header, text="",
                                         text_color="gray",
                                         font=ctk.CTkFont(size=12))
        self.status_label.grid(row=0, column=1, padx=8, pady=12, sticky="w")

        refresh_btn = ctk.CTkButton(header, text="↻ Refresh", width=90,
                                    command=self._load_from_device)
        refresh_btn.grid(row=0, column=2, padx=(0, 4), pady=12)

        save_btn = ctk.CTkButton(header, text="💾 Save", width=90,
                                 fg_color="#1a7a3c", hover_color="#145e2e",
                                 command=self._save_current_tab)
        save_btn.grid(row=0, column=3, padx=(0, 8), pady=12)

        # Tabs
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        for tab_name in ["User", "Device Config", "Radio Config", "Channels",
                         "Module Config", "Actions"]:
            self.tabs.add(tab_name)

        # User tab
        user_tab = self.tabs.tab("User")
        user_tab.grid_columnconfigure(0, weight=1)
        user_tab.grid_rowconfigure(0, weight=1)
        self.user_config_tab = UserConfigTab(user_tab, self.connection)
        self.user_config_tab.grid(row=0, column=0, sticky="nsew")

        # Device Config tab
        dc_tab = self.tabs.tab("Device Config")
        dc_tab.grid_columnconfigure(0, weight=1)
        dc_tab.grid_rowconfigure(0, weight=1)
        self.device_config_tab = DeviceConfigTab(dc_tab)
        self.device_config_tab.grid(row=0, column=0, sticky="nsew")

        # Radio Config tab
        rc_tab = self.tabs.tab("Radio Config")
        rc_tab.grid_columnconfigure(0, weight=1)
        rc_tab.grid_rowconfigure(0, weight=1)
        self.radio_config_tab = RadioConfigTab(rc_tab)
        self.radio_config_tab.grid(row=0, column=0, sticky="nsew")

        # Channels tab
        ch_tab = self.tabs.tab("Channels")
        ch_tab.grid_columnconfigure(0, weight=1)
        ch_tab.grid_rowconfigure(0, weight=1)
        self.channel_tab = ChannelConfigTab(
            ch_tab,
            self.connection,
            on_channels_changed=self._on_channels_changed
        )
        self.channel_tab.grid(row=0, column=0, sticky="nsew")

        # Module Config tab
        mc_tab = self.tabs.tab("Module Config")
        mc_tab.grid_columnconfigure(0, weight=1)
        mc_tab.grid_rowconfigure(0, weight=1)
        self.module_config_tab = ModuleConfigTab(mc_tab)
        self.module_config_tab.grid(row=0, column=0, sticky="nsew")

        # Actions tab
        act_tab = self.tabs.tab("Actions")
        act_tab.grid_columnconfigure(0, weight=1)
        act_tab.grid_rowconfigure(0, weight=1)
        self.actions_tab = DeviceActionsTab(act_tab, self.connection)
        self.actions_tab.grid(row=0, column=0, sticky="nsew")
        self.actions_tab.update_connection_state(False)  # disabled until connected

    def _load_from_device(self):
        if not self.connection.is_connected:
            self.status_label.configure(text="Not connected.", text_color="orange")
            return

        self.status_label.configure(text="Loading config...", text_color="gray")

        def _do_load():
            device_cfg = self.connection.get_device_config()
            module_cfg = self.connection.get_module_config()
            channels = self.connection.get_channels()
            owner = self.connection.get_owner()

            def _apply():
                self.user_config_tab.load_owner(owner)
                if device_cfg:
                    self.device_config_tab.load_config(device_cfg)
                    self.radio_config_tab.load_config(device_cfg)
                    self.status_label.configure(
                        text="Config loaded.", text_color="green")
                else:
                    self.status_label.configure(
                        text="Could not load device config.", text_color="orange")
                if module_cfg:
                    self.module_config_tab.load_config(module_cfg)
                self.channel_tab.load_channels(channels)
                if self._on_channels_changed:
                    self._on_channels_changed(channels)

            self.after(0, _apply)

        threading.Thread(target=_do_load, daemon=True).start()
    
    def on_connected(self):
        """Called when device connects — load all config from device."""
        self.actions_tab.update_connection_state(True)
        self._load_from_device()

    def on_disconnected(self):
        """Called when device disconnects."""
        self.actions_tab.update_connection_state(False)

    def _save_current_tab(self):
        """Save the currently visible config tab back to the device."""
        if not self.connection.is_connected:
            self.status_label.configure(text="Not connected.", text_color="orange")
            return

        active = self.tabs.get()

        if active == "Channels" or active == "Actions":
            self.status_label.configure(
                text=f"'{active}' tab is not saveable here.", text_color="orange")
            return

        self.status_label.configure(text="Saving...", text_color="gray")

        def _do_save():
            if active == "User":
                owner = self.user_config_tab.get_owner()
                ok, msg = self.connection.set_owner(
                    owner["long_name"], owner["short_name"])
            elif active == "Device Config":
                cfg = self.device_config_tab.get_config()
                ok, msg = self.connection.save_device_config(cfg)
            elif active == "Radio Config":
                cfg = self.radio_config_tab.get_config()
                ok, msg = self.connection.save_radio_config(cfg)
            elif active == "Module Config":
                cfg = self.module_config_tab.get_config()
                ok, msg = self.connection.save_module_config(cfg)
            else:
                ok, msg = False, "Unknown tab"

            if ok:
                msg = f"✓ {msg}"
            else:
                msg = f"✗ {msg}"

            color = "green" if ok else "red"
            self.after(0, lambda: self.status_label.configure(text=msg, text_color=color))
            # Clear status after 5s
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))

        threading.Thread(target=_do_save, daemon=True).start()
