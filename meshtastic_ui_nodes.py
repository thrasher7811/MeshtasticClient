"""
meshtastic_ui_nodes.py - Nodes list view for Meshtastic Python Client.
Shows all discovered mesh nodes with signal, battery, position info.
"""

import time
from datetime import datetime
import customtkinter as ctk
from typing import Dict, Optional, Callable
from meshtastic_core import MeshConnection, MeshNode


ROLE_NAMES = {
    0: "CLIENT",
    1: "CLIENT_MUTE",
    2: "ROUTER",
    3: "ROUTER_CLIENT",
    4: "REPEATER",
    5: "TRACKER",
    6: "SENSOR",
    7: "TAK",
    8: "CLIENT_HIDDEN",
    9: "LOST_AND_FOUND",
    10: "TAK_TRACKER",
}

HW_MODEL_NAMES = {
    0: "UNSET",
    1: "TLORA_V2",
    2: "TLORA_V1",
    3: "TLORA_V2_1_1P6",
    4: "TBEAM",
    6: "HELTEC_V2_0",
    7: "TBEAM_V0P7",
    8: "T_ECHO",
    9: "TLORA_V1_1P3",
    10: "RAK4631",
    11: "HELTEC_V2_1",
    12: "HELTEC_V1",
    13: "LILYGO_TBEAM_S3_CORE",
    14: "RAK11200",
    15: "NANO_G1",
    16: "TLORA_V2_1_1P8",
    17: "TLORA_T3_S3",
    18: "NANO_G1_EXPLORER",
    19: "NANO_G2_ULTRA",
    20: "LORA_TYPE",
    21: "WIPHONE",
    22: "WIO_WM1110",
    23: "RAK2560",
    24: "HELTEC_HRU_3601",
    25: "HELTEC_WIRELESS_BRIDGE",
    26: "STATION_G1",
    27: "RAK11310",
    28: "SENSELORA_RP2040",
    29: "SENSELORA_S3",
    30: "CANARYONE",
    32: "RP2040_LORA",
    33: "STATION_G2",
    34: "LORA_RELAY_V1",
    36: "NRF52840DK",
    37: "PPR",
    38: "GENIEBLOCKS",
    39: "NRF52_UNKNOWN",
    40: "PORTDUINO",
    41: "ANDROID_SIM",
    42: "DIY_V1",
    43: "NRF52840_PCA10059",
    44: "DR_DEV",
    45: "M5STACK",
    46: "HELTEC_V3",
    47: "HELTEC_WSL_V3",
    48: "BETAFPV_2400_TX",
    49: "BETAFPV_900_NANO_TX",
    50: "RPI_PICO",
    51: "HELTEC_WIRELESS_TRACKER",
    52: "HELTEC_WIRELESS_PAPER",
    53: "T_DECK",
    54: "T_WATCH_S3",
    55: "PICOMPUTER_S3",
    56: "HELTEC_HT62",
    57: "EBYTE_ESP32_S3",
    58: "ESP32_S3_PICO",
    59: "ESP32_DIY_1W",
    60: "PPR_V2",
    61: "SENSELORA_S3_BETA",
    62: "CANARYONE_V2",
    63: "MESH_TAB",
    64: "HELTEC_CAPSULE_SENSOR_V3",
    65: "HELTEC_VISION_MASTER_T190",
    66: "HELTEC_VISION_MASTER_E213",
    67: "HELTEC_VISION_MASTER_E290",
    68: "HELTEC_MESH_NODE_T114",
    69: "SENSECAP_INDICATOR",
    70: "TRACKER_T1000_E",
    71: "RAK3172",
    72: "WIO_E5",
    73: "RADIOMASTER_900_BANDIT_NANO",
    74: "HELTEC_WIRELESS_PAPER_V1_0",
    75: "HELTEC_WIRELESS_TRACKER_V1_0",
    76: "UNPHONE",
    77: "TD_LORAC",
    78: "CDEBYTE_EORA_S3",
    79: "TWC_MESH_V4",
    80: "NRF52_PROMICRO_DIY",
    81: "RADIOMASTER_900_BANDIT",
    82: "ME25LS01_4Y10TD",
    83: "RP2040_FEATHER_RFM95",
    84: "M5STACK_COREBASIC",
    85: "M5STACK_CORE2",
    86: "RESERVED_0",
    255: "PRIVATE_HW",
}


def format_role_name(role_value):
    if role_value is None:
        return "Unknown"
    try:
        return ROLE_NAMES.get(int(role_value), f"Role {role_value}")
    except Exception:
        return str(role_value)


def format_hw_model_name(hw_value):
    if hw_value in (None, ""):
        return "Unknown"
    if isinstance(hw_value, str):
        return hw_value
    try:
        return HW_MODEL_NAMES.get(int(hw_value), f"Unknown ({hw_value})")
    except Exception:
        return str(hw_value)


def format_bool_name(value):
    if value is None:
        return None
    return "Yes" if value else "No"


class NodeCard(ctk.CTkFrame):
    """Card widget displaying information about a single mesh node."""

    def __init__(self, parent, node: MeshNode, is_local: bool = False,
                 on_select: Optional[Callable] = None, **kwargs):
        super().__init__(parent, corner_radius=8, **kwargs)
        self.node = node
        self.is_local = is_local
        self.on_select = on_select
        self._build_ui()
        self.bind("<Button-1>", self._clicked)

    def _clicked(self, event=None):
        if self.on_select:
            self.on_select(self.node)

    def _bind_children(self, widget):
        """Recursively bind click to all child widgets so the whole card is clickable."""
        widget.bind("<Button-1>", self._clicked)
        for child in widget.winfo_children():
            self._bind_children(child)

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)

        # Node indicator / avatar
        indicator_color = "#1d6fa8" if self.is_local else "#2d8a4e"
        avatar = ctk.CTkFrame(self, width=40, height=40,
                              corner_radius=20,
                              fg_color=indicator_color)
        avatar.grid(row=0, column=0, rowspan=3, padx=(10, 8), pady=8, sticky="w")
        avatar.grid_propagate(False)

        short = self.node.short_name[:2] if self.node.short_name else "?"
        ctk.CTkLabel(avatar, text=short,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="white").place(relx=0.5, rely=0.5, anchor="center")

        # Name row
        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(8, 0))
        name_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(name_frame,
                     text=self.node.long_name or f"!{self.node.num:08x}",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")

        if self.is_local:
            ctk.CTkLabel(name_frame, text="(This device)",
                         font=ctk.CTkFont(size=11),
                         text_color="gray").grid(row=0, column=1, padx=(6, 0))

        # Node ID + HW model
        user = self.node.raw.get("user", {}) if isinstance(self.node.raw, dict) else {}
        hw = format_hw_model_name(user.get("hwModel", getattr(self.node, "hw_model", None)))

        ctk.CTkLabel(self, text=f"{self.node.node_id}  •  {hw}",
                     font=ctk.CTkFont(size=11),
                     text_color="gray", anchor="w").grid(
            row=1, column=1, sticky="w")

        # Stats row: SNR, Battery, Position, Last heard
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=2, column=1, sticky="ew", pady=(0, 8))

        stats = []

        if self.node.snr is not None:
            snr_color = "#2d8a4e" if self.node.snr > 0 else "#c0392b"
            stats.append((f"SNR {self.node.snr:.1f}dB", snr_color))

        battery = self.node.battery_str
        if battery != "N/A":
            bat_color = "#2d8a4e" if (
                self.node.battery_level and self.node.battery_level > 20
            ) else "#e67e22"
            stats.append((f"🔋 {battery}", bat_color))

        if self.node.has_position:
            stats.append((f"📍 {self.node.latitude:.4f}, {self.node.longitude:.4f}",
                          "gray"))

        stats.append((f"⏱ {self.node.last_heard_str}", "gray"))

        for col, (text, color) in enumerate(stats):
            ctk.CTkLabel(stats_frame, text=text,
                         font=ctk.CTkFont(size=11),
                         text_color=color).grid(row=0, column=col, padx=(0, 12))

        # Bind clicks on all child widgets after UI is built
        self.after(0, lambda: self._bind_children(self))
        self.configure(cursor="hand2")


class NodeDetailPanel(ctk.CTkFrame):
    """Sidebar panel showing detailed node information."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Node Details",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        self.content = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.content.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._empty_label = ctk.CTkLabel(
            self.content, text="Select a node to see details",
            text_color="gray")
        self._empty_label.grid(row=0, column=0, pady=20)

    def show_node(self, node: MeshNode):
        """Display details for the selected node."""
        for widget in self.content.winfo_children():
            widget.destroy()

        sections = self._build_sections(node)
        if not sections:
            self._show_empty()
            return

        for row, (title, fields) in enumerate(sections):
            section = ctk.CTkFrame(self.content, corner_radius=8)
            section.grid(row=row, column=0, padx=12, pady=(0, 12), sticky="ew")
            section.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                section,
                text=title,
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w"
            ).grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 6), sticky="w")

            for idx, (label, value) in enumerate(fields, start=1):
                ctk.CTkLabel(
                    section,
                    text=label + ":",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    anchor="w"
                ).grid(row=idx, column=0, padx=12, pady=(0, 4), sticky="nw")
                ctk.CTkLabel(
                    section,
                    text=str(value),
                    font=ctk.CTkFont(size=11),
                    anchor="w",
                    justify="left",
                    wraplength=200,
                    text_color="gray"
                ).grid(row=idx, column=1, padx=12, pady=(0, 4), sticky="w")

    def _build_sections(self, node: MeshNode):
        raw = node.raw if isinstance(node.raw, dict) else {}
        user = raw.get("user", {}) if isinstance(raw.get("user", {}), dict) else {}
        metadata = raw.get("metadata", {}) if isinstance(raw.get("metadata", {}), dict) else {}
        device_metrics = raw.get("deviceMetrics", {}) if isinstance(raw.get("deviceMetrics", {}), dict) else {}
        position = raw.get("position", {}) if isinstance(raw.get("position", {}), dict) else {}
        environment = raw.get("environmentMetrics", {}) if isinstance(raw.get("environmentMetrics", {}), dict) else {}
        local_stats = raw.get("localStats", {}) if isinstance(raw.get("localStats", {}), dict) else {}

        sections = []

        identity_fields = []
        identity_fields.extend(self._field_list([
            ("Long Name", node.long_name),
            ("Short Name", node.short_name),
            ("Node ID", node.node_id),
            ("Node Number", f"{node.num} / 0x{node.num:08x}"),
            ("Hardware", format_hw_model_name(user.get("hwModel", node.hw_model))),
            ("Role", format_role_name(user.get("role"))),
            ("Favorite", format_bool_name(node.is_favorite)),
            ("Licensed", format_bool_name(node.is_licensed)),
            ("Public Key Match", self._status_value(user.get("keyMatch"))),
            ("Signed Node", self._status_value(raw.get("hasXeddsaSigned") or raw.get("isSigned"))),
            ("Messaging", "Unmonitored" if user.get("unmessagable") else "Allowed"),
        ]))
        self._add_section(sections, "Identity", identity_fields)

        radio_fields = []
        radio_fields.extend(self._field_list([
            ("Last Heard", self._format_epoch(node.last_heard)),
            ("First Heard", self._format_epoch(raw.get("firstHeard"))),
            ("Hops Away", raw.get("hopsAway")),
            ("Via MQTT", format_bool_name(raw.get("viaMqtt"))),
            ("SNR", f"{node.snr:.1f} dB" if node.snr is not None else None),
            ("RSSI", f"{raw.get('rssi')} dB" if raw.get("rssi") is not None else None),
            ("Channel", raw.get("channel")),
        ]))
        self._add_section(sections, "Radio Status", radio_fields)

        device_fields = []
        device_fields.extend(self._field_list([
            ("Battery", node.battery_str),
            ("Voltage", self._format_float(node.voltage, "V", digits=2)),
            ("Channel Util.", self._format_percent(node.channel_utilization)),
            ("Air Util TX", self._format_percent(node.air_util_tx)),
            ("Uptime", self._format_uptime(node.uptime_seconds)),
        ]))
        device_fields.extend(self._dict_fields(device_metrics, [
            ("batteryLevel", "Battery Level", self._format_percent),
            ("voltage", "Voltage", lambda v: self._format_float(v, "V", digits=2)),
            ("channelUtilization", "Channel Util.", self._format_percent),
            ("airUtilTx", "Air Util TX", self._format_percent),
            ("uptimeSeconds", "Uptime Seconds", self._format_uptime),
        ]))
        self._add_section(sections, "Device Metrics", device_fields)

        position_fields = []
        position_fields.extend(self._field_list([
            ("Latitude", self._format_float(node.latitude, "°", digits=6)),
            ("Longitude", self._format_float(node.longitude, "°", digits=6)),
            ("Altitude", self._format_float(node.altitude, "m", digits=0)),
        ]))
        position_fields.extend(self._dict_fields(position, [
            ("latitude", "Latitude", lambda v: self._format_float(v, "°", digits=6)),
            ("longitude", "Longitude", lambda v: self._format_float(v, "°", digits=6)),
            ("altitude", "Altitude", lambda v: self._format_float(v, "m", digits=0)),
            ("precision", "Precision", lambda v: self._format_float(v, "m", digits=0)),
            ("heading", "Heading", lambda v: self._format_float(v, "°", digits=0)),
            ("speed", "Speed", lambda v: self._format_float(v, "m/s", digits=1)),
        ]))
        self._add_section(sections, "Position", position_fields)

        environment_fields = self._dict_fields(environment, None)
        self._add_section(sections, "Environment Metrics", environment_fields)

        local_stats_fields = self._dict_fields(local_stats, None)
        self._add_section(sections, "Local Stats", local_stats_fields)

        metadata_fields = self._field_list([
            ("Firmware Version", metadata.get("firmwareVersion")),
            ("Metadata Version", metadata.get("version")),
        ])
        metadata_fields.extend(self._dict_fields(metadata, [
            ("firmwareVersion", "Firmware Version", None),
            ("version", "Metadata Version", None),
        ]))
        self._add_section(sections, "Metadata", metadata_fields)

        extra_fields = self._field_list([
            ("Raw Keys", ", ".join(sorted(raw.keys())) if raw else None),
        ])
        self._add_section(sections, "Available Data", extra_fields)

        return sections

    def _field_list(self, pairs):
        fields = []
        for label, value in pairs:
            if value is None:
                continue
            if isinstance(value, str):
                if value.strip() == "":
                    continue
            fields.append((label, value))
        return fields

    def _add_section(self, sections, title, fields):
        if fields:
            sections.append((title, fields))

    def _dict_fields(self, data, field_specs):
        if not isinstance(data, dict) or not data:
            return []
        fields = []
        if field_specs:
            for key, label, formatter in field_specs:
                if key not in data:
                    continue
                value = data.get(key)
                if value is None:
                    continue
                if formatter:
                    rendered = formatter(value)
                else:
                    rendered = self._format_value(value)
                if rendered is not None:
                    fields.append((label, rendered))

        if not field_specs:
            skip_keys = set()
        else:
            skip_keys = {item[0] for item in field_specs}

        for key in sorted(data.keys()):
            if key in skip_keys:
                continue
            value = data.get(key)
            if value is None:
                continue
            rendered = self._format_value(value)
            if rendered is None:
                continue
            fields.append((self._labelize(key), rendered))
        return fields

    def _labelize(self, value):
        text = str(value)
        parts = []
        current = []
        for char in text:
            if char.isupper() and current:
                parts.append("".join(current))
                current = [char]
            elif char in {"_", "-", "."}:
                if current:
                    parts.append("".join(current))
                    current = []
            else:
                current.append(char)
        if current:
            parts.append("".join(current))
        return " ".join(part.capitalize() if part.islower() else part for part in parts) if parts else text

    def _format_value(self, value):
        if value is None:
            return None
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (int, float)):
            if isinstance(value, float):
                return f"{value:g}"
            return str(value)
        if isinstance(value, dict):
            if not value:
                return None
            return ", ".join(f"{self._labelize(k)}={self._format_value(v)}" for k, v in value.items() if self._format_value(v) is not None)
        if isinstance(value, (list, tuple, set)):
            rendered = [self._format_value(v) for v in value if self._format_value(v) is not None]
            return ", ".join(rendered) if rendered else None
        text = str(value)
        return text if text.strip() else None

    def _status_value(self, value):
        if value is None:
            return None
        if isinstance(value, bool):
            return "Verified" if value else "Mismatch"
        return self._format_value(value)

    def _format_float(self, value, suffix="", digits=2):
        if value is None:
            return None
        try:
            number = float(value)
        except Exception:
            return self._format_value(value)
        formatted = f"{number:.{digits}f}" if digits > 0 else f"{number:.0f}"
        return f"{formatted}{suffix}"

    def _format_percent(self, value):
        if value is None:
            return None
        return self._format_float(value, "%", digits=1)

    def _format_epoch(self, value):
        if not value:
            return None
        try:
            ts = float(value)
        except Exception:
            return self._format_value(value)
        relative = MeshNode({"lastHeard": ts}).last_heard_str
        absolute = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        return f"{relative} ({absolute})"

    def _format_uptime(self, seconds) -> str:
        if not seconds:
            return "N/A"
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}h {m}m"
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"


class NodesView(ctk.CTkFrame):
    """
    Full nodes list view. Mirrors the web client Nodes page.
    Shows node cards with a detail panel on the right.
    """

    def __init__(self, parent, connection: MeshConnection, **kwargs):
        super().__init__(parent, **kwargs)
        self.connection = connection
        self._nodes: Dict = {}
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *a: self._refresh_list())

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self, height=52, corner_radius=0)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(toolbar, text="Nodes",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=16, pady=12)

        self.search_entry = ctk.CTkEntry(
            toolbar,
            placeholder_text="Search nodes...",
            textvariable=self._search_var,
            width=220)
        self.search_entry.grid(row=0, column=1, padx=8, pady=12, sticky="w")

        self.count_label = ctk.CTkLabel(toolbar, text="0 nodes",
                                        text_color="gray")
        self.count_label.grid(row=0, column=2, padx=16, pady=12)

        refresh_btn = ctk.CTkButton(toolbar, text="↻", width=36,
                                    command=self._manual_refresh)
        refresh_btn.grid(row=0, column=3, padx=(0, 12), pady=12)

        # Node list
        self.node_list = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.node_list.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.node_list.grid_columnconfigure(0, weight=1)

        # Detail panel
        self.detail_panel = NodeDetailPanel(self, width=280, corner_radius=0)
        self.detail_panel.grid(row=1, column=1, sticky="nsew")

        self._show_empty()

    def _show_empty(self):
        for widget in self.node_list.winfo_children():
            widget.destroy()
        ctk.CTkLabel(self.node_list,
                     text="No nodes discovered yet.\nConnect to a device to see nearby nodes.",
                     text_color="gray",
                     font=ctk.CTkFont(size=13)).grid(row=0, column=0, pady=40)

    def _manual_refresh(self):
        if self.connection.is_connected:
            nodes = {}
            for n in self.connection.get_nodes():
                nodes[n.num] = n.raw
            self.update_nodes(nodes)

    def update_nodes(self, nodes_raw: Dict):
        """Update the displayed nodes list."""
        self._nodes = nodes_raw
        self._refresh_list()

    def _refresh_list(self):
        for widget in self.node_list.winfo_children():
            widget.destroy()

        if not self._nodes:
            self._show_empty()
            return

        search = self._search_var.get().lower()
        my_id = self.connection.get_my_node_id()

        nodes = [MeshNode(nd) for nd in self._nodes.values()]

        # Sort: local node first, then by last_heard
        nodes.sort(key=lambda n: (
            0 if n.num == my_id else 1,
            -(n.last_heard or 0)
        ))

        # Filter by search
        if search:
            nodes = [n for n in nodes if
                     search in (n.long_name or "").lower() or
                     search in (n.short_name or "").lower() or
                     search in (n.node_id or "").lower()]

        self.count_label.configure(text=f"{len(nodes)} node{'s' if len(nodes) != 1 else ''}")

        if not nodes:
            ctk.CTkLabel(self.node_list, text="No nodes match your search.",
                         text_color="gray").grid(row=0, column=0, pady=20)
            return

        for i, node in enumerate(nodes):
            is_local = (node.num == my_id)
            card = NodeCard(self.node_list, node, is_local=is_local,
                            on_select=self.detail_panel.show_node)
            card.grid(row=i, column=0, sticky="ew", padx=8, pady=4)
