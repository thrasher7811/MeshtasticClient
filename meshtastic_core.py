"""
meshtastic_core.py - Core connection and device management for Meshtastic Python Client.
Wraps the official meshtastic Python library to provide a unified interface for
Serial and TCP connections with event-driven callbacks.
"""

import threading
import time
import logging
import base64
import os
from typing import Callable, Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    SERIAL = "serial"
    TCP = "tcp"


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class MeshMessage:
    """Represents a received or sent text message."""
    def __init__(self, text: str, from_id: int, to_id: int,
                 channel: int, timestamp: float, is_mine: bool = False,
                 snr: float = 0.0, rssi: int = 0):
        self.text = text
        self.from_id = from_id
        self.to_id = to_id
        self.channel = channel
        self.timestamp = timestamp
        self.is_mine = is_mine
        self.snr = snr
        self.rssi = rssi

    @property
    def from_id_hex(self) -> str:
        return f"!{self.from_id:08x}" if self.from_id else "unknown"

    @property
    def to_id_hex(self) -> str:
        if self.to_id == 0xFFFFFFFF:
            return "broadcast"
        return f"!{self.to_id:08x}" if self.to_id else "unknown"


class MeshNode:
    """Represents a node in the mesh network."""
    def __init__(self, node_dict: Dict[str, Any]):
        self.raw = node_dict
        user = node_dict.get("user", {})
        self.node_id = user.get("id", "unknown")
        self.long_name = user.get("longName", "Unknown")
        self.short_name = user.get("shortName", "?")
        self.hw_model = user.get("hwModel", "Unknown")
        self.is_licensed = user.get("isLicensed", False)

        metrics = node_dict.get("deviceMetrics", {})
        self.battery_level = metrics.get("batteryLevel", None)
        self.voltage = metrics.get("voltage", None)
        self.channel_utilization = metrics.get("channelUtilization", None)
        self.air_util_tx = metrics.get("airUtilTx", None)
        self.uptime_seconds = metrics.get("uptimeSeconds", None)

        snr_info = node_dict.get("snr", None)
        self.snr = snr_info

        last_heard = node_dict.get("lastHeard", 0)
        self.last_heard = last_heard

        pos = node_dict.get("position", {})
        self.latitude = pos.get("latitude", None)
        self.longitude = pos.get("longitude", None)
        self.altitude = pos.get("altitude", None)

        self.num = node_dict.get("num", 0)
        self.is_favorite = node_dict.get("isFavorite", False)

    @property
    def has_position(self) -> bool:
        return (self.latitude is not None and self.longitude is not None
                and self.latitude != 0 and self.longitude != 0)

    @property
    def battery_str(self) -> str:
        if self.battery_level is None:
            return "N/A"
        if self.battery_level == 101:
            return "Plugged In"
        return f"{self.battery_level}%"

    @property
    def last_heard_str(self) -> str:
        if not self.last_heard:
            return "Never"
        elapsed = time.time() - self.last_heard
        if elapsed < 60:
            return f"{int(elapsed)}s ago"
        if elapsed < 3600:
            return f"{int(elapsed/60)}m ago"
        if elapsed < 86400:
            return f"{int(elapsed/3600)}h ago"
        return f"{int(elapsed/86400)}d ago"


class MeshConnection:
    """
    Manages connection to a Meshtastic device via Serial or TCP.
    Provides callbacks for UI updates.
    """

    def __init__(self):
        self._interface = None
        self._connection_type: Optional[ConnectionType] = None
        self._last_serial_port: Optional[str] = None
        self._state = ConnectionState.DISCONNECTED
        self._messages: List[MeshMessage] = []
        self._lock = threading.Lock()

        # Callbacks (set by UI)
        self.on_state_change: Optional[Callable[[ConnectionState, str], None]] = None
        self.on_message_received: Optional[Callable[[MeshMessage], None]] = None
        self.on_nodes_updated: Optional[Callable[[Dict], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    @property
    def interface(self):
        return self._interface

    def _set_state(self, state: ConnectionState, message: str = ""):
        self._state = state
        if self.on_state_change:
            self.on_state_change(state, message)

    def _log(self, msg: str):
        logger.info(msg)
        if self.on_log:
            self.on_log(msg)

    def connect_serial(self, port: str, debug: bool = False):
        """Connect to device via serial/USB port."""
        self._connect_async(ConnectionType.SERIAL, port=port, debug=debug)

    def connect_tcp(self, host: str, port: int = 4403, debug: bool = False):
        """Connect to device via TCP/HTTP."""
        self._connect_async(ConnectionType.TCP, host=host, port=port, debug=debug)

    def _connect_async(self, conn_type: ConnectionType, **kwargs):
        """Start connection in background thread."""
        thread = threading.Thread(
            target=self._do_connect,
            args=(conn_type,),
            kwargs=kwargs,
            daemon=True
        )
        thread.start()

    def _do_connect(self, conn_type: ConnectionType, **kwargs):
        """Perform the actual connection (runs in thread)."""
        self._set_state(ConnectionState.CONNECTING, "Connecting...")
        try:
            # Import here to avoid startup cost
            from pubsub import pub

            # Unsubscribe any old subscriptions
            try:
                pub.unsubscribe(self._on_receive, "meshtastic.receive")
            except Exception:
                pass
            try:
                pub.unsubscribe(self._on_connection, "meshtastic.connection.established")
            except Exception:
                pass
            try:
                pub.unsubscribe(self._on_lost, "meshtastic.connection.lost")
            except Exception:
                pass

            if conn_type == ConnectionType.SERIAL:
                import meshtastic.serial_interface
                port = kwargs.get("port")
                debug = kwargs.get("debug", False)
                self._last_serial_port = port
                self._log(f"Connecting via Serial: {port}")
                self._interface = meshtastic.serial_interface.SerialInterface(
                    devPath=port,
                    debugOut=None,
                    noProto=False
                )
            elif conn_type == ConnectionType.TCP:
                import meshtastic.tcp_interface
                host = kwargs.get("host")
                tcp_port = kwargs.get("port", 4403)
                debug = kwargs.get("debug", False)
                self._log(f"Connecting via TCP: {host}:{tcp_port}")
                self._interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=host,
                    portNumber=tcp_port,
                    debugOut=None
                )

            # Subscribe to events
            pub.subscribe(self._on_receive, "meshtastic.receive")
            pub.subscribe(self._on_connection, "meshtastic.connection.established")
            pub.subscribe(self._on_lost, "meshtastic.connection.lost")

            self._connection_type = conn_type
            self._set_state(ConnectionState.CONNECTED, "Connected")
            self._log("Connection established")

            # Trigger initial node update
            if self.on_nodes_updated and self._interface:
                self.on_nodes_updated(self._interface.nodes or {})

        except Exception as e:
            error_msg = str(e)
            self._log(f"Connection failed: {error_msg}")
            self._set_state(ConnectionState.ERROR, f"Error: {error_msg}")
            self._interface = None

    def _on_receive(self, packet, interface):
        """Called when a packet is received."""
        try:
            decoded = packet.get("decoded", {})
            portnum = decoded.get("portnum", "")

            if portnum == "TEXT_MESSAGE_APP":
                text = decoded.get("text", "")
                from_id = packet.get("from", 0)
                to_id = packet.get("to", 0xFFFFFFFF)
                channel = packet.get("channel", 0)
                timestamp = time.time()
                snr = packet.get("rxSnr", 0.0)
                rssi = packet.get("rxRssi", 0)

                msg = MeshMessage(
                    text=text,
                    from_id=from_id,
                    to_id=to_id,
                    channel=channel,
                    timestamp=timestamp,
                    is_mine=False,
                    snr=snr,
                    rssi=rssi
                )
                with self._lock:
                    self._messages.append(msg)

                if self.on_message_received:
                    self.on_message_received(msg)

            # Trigger node update for any packet
            if self.on_nodes_updated and self._interface:
                self.on_nodes_updated(self._interface.nodes or {})

        except Exception as e:
            self._log(f"Error processing received packet: {e}")

    def _on_connection(self, interface, topic=None):
        """Called when connection is established."""
        self._log("Device connection confirmed")
        if self.on_nodes_updated and self._interface:
            self.on_nodes_updated(self._interface.nodes or {})

    def _on_lost(self, interface, topic=None):
        """Called when connection is lost."""
        self._log("Connection lost")
        self._set_state(ConnectionState.DISCONNECTED, "Connection lost")

    def disconnect(self):
        """Disconnect from the device."""
        try:
            if self._interface:
                self._interface.close()
                self._interface = None
            self._set_state(ConnectionState.DISCONNECTED, "Disconnected")
            self._log("Disconnected")
        except Exception as e:
            self._log(f"Error during disconnect: {e}")

    def send_text(self, text: str, channel_index: int = 0,
                  destination_id: Optional[int] = None) -> bool:
        """Send a text message."""
        if not self.is_connected or not self._interface:
            return False
        try:
            if destination_id:
                self._interface.sendText(
                    text,
                    destinationId=destination_id,
                    channelIndex=channel_index
                )
            else:
                self._interface.sendText(text, channelIndex=channel_index)

            # Create local message entry
            my_id = self.get_my_node_id()
            msg = MeshMessage(
                text=text,
                from_id=my_id or 0,
                to_id=destination_id or 0xFFFFFFFF,
                channel=channel_index,
                timestamp=time.time(),
                is_mine=True
            )
            with self._lock:
                self._messages.append(msg)
            if self.on_message_received:
                self.on_message_received(msg)
            return True
        except Exception as e:
            self._log(f"Failed to send message: {e}")
            return False

    def get_my_node_id(self) -> Optional[int]:
        """Get the node ID of the connected device."""
        try:
            if self._interface and self._interface.myInfo:
                return self._interface.myInfo.my_node_num
        except Exception:
            pass
        return None

    def get_nodes(self) -> List[MeshNode]:
        """Get list of all known nodes."""
        if not self._interface or not self._interface.nodes:
            return []
        nodes = []
        for node_num, node_data in self._interface.nodes.items():
            nodes.append(MeshNode(node_data))
        return nodes

    def get_channels(self) -> List[Dict]:
        """Get all 8 channel slots with name, role, and psk."""
        if not self._interface:
            return []
        try:
            local_node = self._interface.localNode
            if not local_node:
                return [{"index": 0, "name": "Primary", "role": 1, "psk": "AQ=="}]
            channels = getattr(local_node, "channels", None)
            result = []
            items = channels.values() if isinstance(channels, dict) else (channels or [])
            for ch in items:
                role = getattr(ch, "role", 0)
                settings = getattr(ch, "settings", None)
                name = getattr(settings, "name", "") if settings else ""
                index = getattr(ch, "index", 0)
                psk = getattr(settings, "psk", b"") if settings else b""
                # Encode PSK as base64 for display/editing
                psk_b64 = base64.b64encode(psk).decode() if psk else ""
                if not name and role == 1:
                    name = "Primary"
                result.append({
                    "index": index,
                    "name":  name,
                    "role":  role,
                    "psk":   psk_b64,
                })
            result.sort(key=lambda c: c["index"])
            if result:
                return result
        except Exception as e:
            self._log(f"Error getting channels: {e}")
        return [{"index": 0, "name": "Primary", "role": 1, "psk": "AQ=="}]

    def save_channel(self, index: int, name: str, role: int, psk_bytes: bytes) -> tuple:
        """Write a channel slot to the device."""
        if not self._interface or not self._interface.localNode:
            return False, "Not connected"
        try:
            local_node = self._interface.localNode
            channels = getattr(local_node, "channels", {})
            if index not in channels:
                return False, f"Channel slot {index} not found on device"
            ch = channels[index]
            ch.role = role
            ch.settings.name = name
            ch.settings.psk = psk_bytes
            local_node.writeChannel(index)
            self._log(f"Channel {index} saved: name='{name}', role={role}")
            return True, f"Channel {index} saved"
        except Exception as e:
            self._log(f"Error saving channel {index}: {e}")
            return False, str(e)

    def delete_channel(self, index: int) -> tuple:
        """Disable a channel slot (set role to DISABLED)."""
        if not self._interface or not self._interface.localNode:
            return False, "Not connected"
        if index == 0:
            return False, "Cannot delete the Primary channel"
        try:
            local_node = self._interface.localNode
            channels = getattr(local_node, "channels", {})
            if index not in channels:
                return False, f"Channel slot {index} not found"
            ch = channels[index]
            ch.role = 0  # DISABLED
            ch.settings.name = ""
            ch.settings.psk = b""
            local_node.writeChannel(index)
            self._log(f"Channel {index} deleted (disabled)")
            return True, f"Channel {index} deleted"
        except Exception as e:
            self._log(f"Error deleting channel {index}: {e}")
            return False, str(e)

    @staticmethod
    def _f(obj, field, default=None):
        """Safely get a field from a protobuf sub-message using getattr."""
        try:
            return getattr(obj, field, default)
        except Exception:
            return default

    def get_device_config(self) -> Dict[str, Any]:
        """Get device configuration as a dictionary."""
        if not self._interface:
            return {}
        try:
            local_node = self._interface.localNode
            if not local_node:
                return {}
            cfg = getattr(local_node, "localConfig", None)
            if cfg is None:
                return {}

            f = self._f
            dev = getattr(cfg, "device", None)
            pos = getattr(cfg, "position", None)
            pwr = getattr(cfg, "power", None)
            net = getattr(cfg, "network", None)
            disp = getattr(cfg, "display", None)
            lora = getattr(cfg, "lora", None)
            bt = getattr(cfg, "bluetooth", None)

            return {
                "device": {
                    "role": f(dev, "role", 0),
                    "serial_enabled": f(dev, "serial_enabled", True),
                    "debug_log_enabled": f(dev, "debug_log_enabled", False),
                    "node_info_broadcast_secs": f(dev, "node_info_broadcast_secs", 900),
                    "rebroadcast_mode": f(dev, "rebroadcast_mode", 0),
                    "button_gpio": f(dev, "button_gpio", 0),
                    "buzzer_gpio": f(dev, "buzzer_gpio", 0),
                },
                "position": {
                    "gps_enabled": f(pos, "gps_enabled", False),
                    "gps_update_interval": f(pos, "gps_update_interval", 0),
                    "position_broadcast_secs": f(pos, "position_broadcast_secs", 900),
                    "fixed_position": f(pos, "fixed_position", False),
                    "gps_mode": f(pos, "gps_mode", 0),
                },
                "power": {
                    "is_power_saving": f(pwr, "is_power_saving", False),
                    "on_battery_shutdown_after_secs": f(pwr, "on_battery_shutdown_after_secs", 0),
                    "ls_secs": f(pwr, "ls_secs", 300),
                    "min_wake_secs": f(pwr, "min_wake_secs", 10),
                    "wait_bluetooth_secs": f(pwr, "wait_bluetooth_secs", 60),
                    "sds_secs": f(pwr, "sds_secs", 0),
                },
                "network": {
                    "wifi_enabled": f(net, "wifi_enabled", False),
                    "wifi_ssid": f(net, "wifi_ssid", ""),
                    "ntp_server": f(net, "ntp_server", "0.pool.ntp.org"),
                    "eth_enabled": f(net, "eth_enabled", False),
                    "address_mode": f(net, "address_mode", 0),
                },
                "display": {
                    "screen_on_secs": f(disp, "screen_on_secs", 0),
                    "gps_format": f(disp, "gps_format", 0),
                    "auto_screen_carousel_secs": f(disp, "auto_screen_carousel_secs", 0),
                    "compass_north_top": f(disp, "compass_north_top", False),
                    "flip_screen": f(disp, "flip_screen", False),
                    "units": f(disp, "units", 0),
                    "oled": f(disp, "oled", 0),
                    "displaymode": f(disp, "displaymode", 0),
                    "heading_bold": f(disp, "heading_bold", False),
                    "wake_on_tap_or_motion": f(disp, "wake_on_tap_or_motion", False),
                },
                "lora": {
                    "use_preset": f(lora, "use_preset", True),
                    "modem_preset": f(lora, "modem_preset", 0),
                    "region": f(lora, "region", 0),
                    "hop_limit": f(lora, "hop_limit", 3),
                    "tx_enabled": f(lora, "tx_enabled", True),
                    "tx_power": f(lora, "tx_power", 0),
                    "channel_num": f(lora, "channel_num", 0),
                    "ignore_mqtt": f(lora, "ignore_mqtt", False),
                    "override_duty_cycle": f(lora, "override_duty_cycle", False),
                    "sx126x_rx_boosted_gain": f(lora, "sx126x_rx_boosted_gain", False),
                    "override_frequency": f(lora, "override_frequency", 0.0),
                    "pa_fan_disabled": f(lora, "pa_fan_disabled", False),
                },
                "bluetooth": {
                    "enabled": f(bt, "enabled", True),
                    "mode": f(bt, "mode", 0),
                    "fixed_pin": f(bt, "fixed_pin", 123456),
                },
            }
        except Exception as e:
            self._log(f"Error getting device config: {e}")
        return {}

    def get_module_config(self) -> Dict[str, Any]:
        """Get module configuration."""
        if not self._interface:
            return {}
        try:
            local_node = self._interface.localNode
            if not local_node:
                return {}
            mc = getattr(local_node, "moduleConfig", None)
            if mc is None:
                return {}

            f = self._f
            mqtt = getattr(mc, "mqtt", None)
            serial = getattr(mc, "serial", None)
            tele = getattr(mc, "telemetry", None)
            # Meshtastic proto uses "store_forward" in some versions, "storeForward" in others
            sf = getattr(mc, "store_and_forward",
                 getattr(mc, "store_forward",
                 getattr(mc, "storeForward", None)))
            rt = getattr(mc, "range_test",
                getattr(mc, "rangeTest", None))
            ni = getattr(mc, "neighbor_info",
                getattr(mc, "neighborInfo", None))

            return {
                "mqtt": {
                    "enabled": f(mqtt, "enabled", False),
                    "address": f(mqtt, "address", "mqtt.meshtastic.org"),
                    "username": f(mqtt, "username", "meshdev"),
                    "encryption_enabled": f(mqtt, "encryption_enabled", False),
                    "json_enabled": f(mqtt, "json_enabled", False),
                    "tls_enabled": f(mqtt, "tls_enabled", False),
                    "root": f(mqtt, "root", ""),
                    "proxy_to_client_enabled": f(mqtt, "proxy_to_client_enabled", False),
                    "map_reporting_enabled": f(mqtt, "map_reporting_enabled", False),
                },
                "serial": {
                    "enabled": f(serial, "enabled", False),
                    "echo": f(serial, "echo", False),
                    "rxd": f(serial, "rxd", 0),
                    "txd": f(serial, "txd", 0),
                    "baud": f(serial, "baud", 0),
                    "timeout": f(serial, "timeout", 0),
                    "mode": f(serial, "mode", 0),
                    "override_console_serial_port": f(serial, "override_console_serial_port", False),
                },
                "telemetry": {
                    "device_update_interval": f(tele, "device_update_interval", 0),
                    "environment_update_interval": f(tele, "environment_update_interval", 0),
                    "environment_measurement_enabled": f(tele, "environment_measurement_enabled", False),
                    "air_quality_interval": f(tele, "air_quality_interval", 0),
                    "environment_screen_enabled": f(tele, "environment_screen_enabled", False),
                    "power_measurement_enabled": f(tele, "power_measurement_enabled", False),
                },
                "store_and_forward": {
                    "enabled": f(sf, "enabled", False),
                    "heartbeat": f(sf, "heartbeat", False),
                    "records": f(sf, "records", 0),
                    "history_return_window": f(sf, "history_return_window", 0),
                    "history_return_max": f(sf, "history_return_max", 0),
                },
                "range_test": {
                    "enabled": f(rt, "enabled", False),
                    "sender": f(rt, "sender", 0),
                    "save": f(rt, "save", False),
                },
                "neighbor_info": {
                    "enabled": f(ni, "enabled", False),
                    "update_interval": f(ni, "update_interval", 0),
                    "transmit_over_lora": f(ni, "transmit_over_lora", False),
                },
            }
        except Exception as e:
            self._log(f"Error getting module config: {e}")
        return {}

    def get_owner(self) -> dict:
        """Return the current long name and short name from localNode."""
        if not self._interface:
            return {"long_name": "", "short_name": ""}
        try:
            # getMyNodeInfo() returns a dict: {"num": ..., "user": {"longName": ..., "shortName": ...}, ...}
            node_info = self._interface.getMyNodeInfo()
            if node_info:
                user = node_info.get("user", {})
                return {
                    "long_name":  user.get("longName", ""),
                    "short_name": user.get("shortName", ""),
                }
        except Exception:
            pass
        # Fallback: scan nodes dict for our own node number
        try:
            my_num = getattr(self._interface.myInfo, "my_node_num", None)
            if my_num and self._interface.nodes:
                for node in self._interface.nodes.values():
                    if node.get("num") == my_num:
                        user = node.get("user", {})
                        return {
                            "long_name":  user.get("longName", ""),
                            "short_name": user.get("shortName", ""),
                        }
            self._log(f"get_owner: could not find own node (my_num={my_num})")
        except Exception as e:
            self._log(f"Error getting owner: {e}")
        return {"long_name": "", "short_name": ""}

    def set_owner(self, long_name: str, short_name: str) -> tuple:
        """Set the long name and short name on the connected device."""
        if not self._interface or not self._interface.localNode:
            return False, "Not connected"
        long_name = long_name.strip()
        short_name = short_name.strip()
        if not long_name:
            return False, "Long name cannot be empty"
        if not short_name:
            return False, "Short name cannot be empty"
        if len(short_name) > 4:
            return False, "Short name must be 4 characters or fewer"
        try:
            self._interface.localNode.setOwner(long_name=long_name, short_name=short_name)
            self._log(f"Owner set: long='{long_name}', short='{short_name}'")
            return True, f"Name updated to '{long_name}' / '{short_name}'"
        except Exception as e:
            self._log(f"Error setting owner: {e}")
            return False, str(e)

    def save_device_config(self, config: Dict[str, Any]) -> tuple:
        """Write device/position/power/network/display/bluetooth config to device."""
        if not self._interface or not self._interface.localNode:
            return False, "Not connected"
        local_node = self._interface.localNode
        cfg = getattr(local_node, "localConfig", None)
        if cfg is None:
            return False, "Could not access localConfig"

        # Map section name → (proto sub-object, list of field names)
        sections = {
            "device":    (getattr(cfg, "device",    None),
                          ["role", "serial_enabled", "debug_log_enabled",
                           "node_info_broadcast_secs", "rebroadcast_mode"]),
            "position":  (getattr(cfg, "position",  None),
                          ["gps_mode", "gps_enabled", "fixed_position",
                           "gps_update_interval", "position_broadcast_secs"]),
            "power":     (getattr(cfg, "power",     None),
                          ["is_power_saving", "on_battery_shutdown_after_secs", "ls_secs"]),
            "network":   (getattr(cfg, "network",   None),
                          ["wifi_enabled", "wifi_ssid", "wifi_psk",
                           "ntp_server", "eth_enabled", "address_mode"]),
            "display":   (getattr(cfg, "display",   None),
                          ["screen_on_secs", "flip_screen", "compass_north_top",
                           "gps_format", "units", "oled", "displaymode"]),
            "bluetooth": (getattr(cfg, "bluetooth", None),
                          ["enabled", "mode", "fixed_pin"]),
        }

        saved, errors = [], []
        for section_name, (obj, fields) in sections.items():
            section_data = config.get(section_name, {})
            if not section_data or obj is None:
                continue
            for field in fields:
                value = section_data.get(field)
                if value is None:
                    continue
                try:
                    setattr(obj, field, value)
                except Exception as e:
                    errors.append(f"{section_name}.{field}: {e}")
            try:
                local_node.writeConfig(section_name)
                saved.append(section_name)
            except Exception as e:
                errors.append(f"writeConfig({section_name}): {e}")

        if errors:
            self._log(f"Save device config errors: {'; '.join(errors)}")
        if saved:
            self._log(f"Saved device config sections: {', '.join(saved)}")
            return True, f"Saved: {', '.join(saved)}"
        return False, f"Nothing saved. {'; '.join(errors)}"

    def save_radio_config(self, config: Dict[str, Any]) -> tuple:
        """Write LoRa radio config to device."""
        if not self._interface or not self._interface.localNode:
            return False, "Not connected"
        local_node = self._interface.localNode
        cfg = getattr(local_node, "localConfig", None)
        if cfg is None:
            return False, "Could not access localConfig"

        lora = getattr(cfg, "lora", None)
        if lora is None:
            return False, "Could not access lora config"

        fields = ["use_preset", "modem_preset", "region", "hop_limit",
                  "tx_enabled", "tx_power", "channel_num", "ignore_mqtt",
                  "override_duty_cycle", "sx126x_rx_boosted_gain"]
        lora_data = config.get("lora", {})
        errors = []
        for field in fields:
            value = lora_data.get(field)
            if value is None:
                continue
            try:
                setattr(lora, field, value)
            except Exception as e:
                errors.append(f"lora.{field}: {e}")
        try:
            local_node.writeConfig("lora")
            self._log("Saved lora config")
            return True, "Saved: lora"
        except Exception as e:
            errors.append(f"writeConfig(lora): {e}")
            return False, "; ".join(errors)

    def save_module_config(self, config: Dict[str, Any]) -> tuple:
        """Write module config to device."""
        if not self._interface or not self._interface.localNode:
            return False, "Not connected"
        local_node = self._interface.localNode
        mc = getattr(local_node, "moduleConfig", None)
        if mc is None:
            return False, "Could not access moduleConfig"

        # module section → (attribute name(s) to try, fields)
        module_sections = {
            "mqtt":      (["mqtt"],
                          ["enabled", "address", "username", "password",
                           "encryption_enabled", "json_enabled", "tls_enabled"]),
            "telemetry": (["telemetry"],
                          ["device_update_interval", "environment_measurement_enabled",
                           "environment_update_interval", "air_quality_interval"]),
            "serial":    (["serial"],
                          ["enabled", "echo", "baud", "mode"]),
            "store_and_forward": (["store_and_forward", "store_forward", "storeForward"],
                          ["enabled", "heartbeat", "records", "history_return_window"]),
            "range_test":     (["range_test", "rangeTest"],
                          ["enabled", "sender", "save"]),
            "neighbor_info":  (["neighbor_info", "neighborInfo"],
                          ["enabled", "update_interval"]),
        }

        saved, errors = [], []
        for section_key, (attr_names, fields) in module_sections.items():
            section_data = config.get(section_key, {})
            if not section_data:
                continue
            # Find the actual proto sub-object (name varies by firmware)
            obj = None
            actual_attr = None
            for attr in attr_names:
                obj = getattr(mc, attr, None)
                if obj is not None:
                    actual_attr = attr
                    break
            if obj is None:
                continue
            for field in fields:
                value = section_data.get(field)
                if value is None:
                    continue
                try:
                    setattr(obj, field, value)
                except Exception as e:
                    errors.append(f"{actual_attr}.{field}: {e}")
            # writeConfig section name: try the actual attribute name used by firmware
            try:
                local_node.writeConfig(actual_attr)
                saved.append(actual_attr)
            except Exception as e:
                errors.append(f"writeConfig({actual_attr}): {e}")

        if errors:
            self._log(f"Save module config errors: {'; '.join(errors)}")
        if saved:
            self._log(f"Saved module config sections: {', '.join(saved)}")
            return True, f"Saved: {', '.join(saved)}"
        return False, f"Nothing saved. {'; '.join(errors)}"

    def reboot_device(self, seconds: int = 5):
        """Reboot the connected device."""
        if self._interface and self._interface.localNode:
            try:
                self._interface.localNode.reboot(seconds)
                self._log(f"Reboot scheduled in {seconds}s")
            except Exception as e:
                self._log(f"Reboot failed: {e}")

    def reboot_and_reconnect(self, reboot_delay: int = 5, reconnect_wait: int = 10):
        """Reboot device then automatically reconnect on the last serial port."""
        if not self._interface or not self._interface.localNode:
            return False, "Not connected"
        port = self._last_serial_port
        if not port:
            return False, "No serial port recorded — cannot reconnect"

        def _do():
            try:
                self._interface.localNode.reboot(reboot_delay)
                self._log(f"Reboot initiated. Reconnecting in {reboot_delay + reconnect_wait}s…")
            except Exception as e:
                self._log(f"Reboot failed: {e}")
                return
            # Wait for device to reboot then disconnect cleanly
            import time
            time.sleep(reboot_delay + 2)
            try:
                self.disconnect()
            except Exception:
                pass
            time.sleep(reconnect_wait)
            self._log(f"Reconnecting to {port}…")
            self.connect_serial(port)

        threading.Thread(target=_do, daemon=True).start()
        return True, f"Rebooting and reconnecting to {port}…"

    def factory_reset(self):
        """Factory reset the device."""
        if self._interface and self._interface.localNode:
            try:
                self._interface.localNode.factoryReset()
                self._log("Factory reset initiated")
            except Exception as e:
                self._log(f"Factory reset failed: {e}")

    def get_messages(self, channel: Optional[int] = None) -> List[MeshMessage]:
        """Get stored messages, optionally filtered by channel."""
        with self._lock:
            if channel is None:
                return list(self._messages)
            return [m for m in self._messages if m.channel == channel]

    @staticmethod
    def list_serial_ports() -> List[str]:
        """List available serial ports."""
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            return [p.device for p in ports]
        except ImportError:
            return []

    def get_node_info(self) -> Dict[str, Any]:
        """Get info about the connected local node."""
        if not self._interface:
            return {}
        try:
            info = {}
            if self._interface.myInfo:
                info["my_node_num"] = self._interface.myInfo.my_node_num
            if self._interface.metadata:
                meta = self._interface.metadata
                info["firmware_version"] = getattr(meta, "firmware_version", "unknown")
                info["device_state_version"] = getattr(meta, "device_state_version", 0)
                info["can_shutdown"] = getattr(meta, "canShutdown", False)
                info["has_wifi"] = getattr(meta, "hasWifi", False)
                info["has_bluetooth"] = getattr(meta, "hasBluetooth", False)
                info["has_eth"] = getattr(meta, "hasEth", False)
                info["role"] = getattr(meta, "role", 0)
            return info
        except Exception as e:
            self._log(f"Error getting node info: {e}")
            return {}
