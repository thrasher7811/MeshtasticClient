"""
meshtastic_ui_connect.py - Connection dialog and sidebar status widget.
"""

import threading
import customtkinter as ctk
from typing import Callable, Optional, List
from meshtastic_core import MeshConnection, ConnectionState, ConnectionType
from meshtastic_ui_settings import MeshConnection


class ConnectionDialog(ctk.CTkToplevel):
    """Modal dialog for connecting to a Meshtastic device."""

    def __init__(self, parent, connection: MeshConnection,
                 on_connected: Optional[Callable] = None):
        super().__init__(parent)
        self.connection = connection
        self.on_connected = on_connected

        self.title("Connect to Device")
        self.geometry("480x420")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._refresh_ports()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 480) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 420) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # Title
        title = ctk.CTkLabel(self, text="Connect to Meshtastic Device",
                             font=ctk.CTkFont(size=16, weight="bold"))
        title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Tabview for connection types
        self.tab_view = ctk.CTkTabview(self, width=440)
        self.tab_view.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        self.tab_view.add("Serial / USB")
        self.tab_view.add("TCP / Network")

        # --- Serial Tab ---
        serial_tab = self.tab_view.tab("Serial / USB")
        serial_tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(serial_tab, text="Serial Port:",
                     anchor="w").grid(row=0, column=0, sticky="w", pady=(10, 2))

        port_frame = ctk.CTkFrame(serial_tab, fg_color="transparent")
        port_frame.grid(row=1, column=0, sticky="ew")
        port_frame.grid_columnconfigure(0, weight=1)

        self.port_var = ctk.StringVar()
        self.port_combo = ctk.CTkComboBox(port_frame, variable=self.port_var,
                                          width=280)
        self.port_combo.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        refresh_btn = ctk.CTkButton(port_frame, text="↻ Refresh",
                                    width=80, command=self._refresh_ports)
        refresh_btn.grid(row=0, column=1)

        ctk.CTkLabel(serial_tab,
                     text="Connect your device via USB. The serial port will\n"
                          "appear as COM# (Windows) or /dev/ttyUSB# (Linux).",
                     text_color="gray", justify="left",
                     font=ctk.CTkFont(size=11)).grid(
            row=2, column=0, sticky="w", pady=(8, 0))

        self.serial_connect_btn = ctk.CTkButton(
            serial_tab, text="Connect via Serial",
            command=self._connect_serial,
            height=36)
        self.serial_connect_btn.grid(row=3, column=0, pady=(15, 0), sticky="ew")

        # --- TCP Tab ---
        tcp_tab = self.tab_view.tab("TCP / Network")
        tcp_tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tcp_tab, text="Host / IP Address:",
                     anchor="w").grid(row=0, column=0, sticky="w", pady=(10, 2))
        self.host_entry = ctk.CTkEntry(tcp_tab, placeholder_text="192.168.1.1 or hostname")
        self.host_entry.grid(row=1, column=0, sticky="ew")

        ctk.CTkLabel(tcp_tab, text="Port:",
                     anchor="w").grid(row=2, column=0, sticky="w", pady=(8, 2))
        self.tcp_port_entry = ctk.CTkEntry(tcp_tab, placeholder_text="4403")
        self.tcp_port_entry.insert(0, "4403")
        self.tcp_port_entry.grid(row=3, column=0, sticky="ew")

        ctk.CTkLabel(tcp_tab,
                     text="Connect to a node running HTTP API (port 4403)\n"
                          "or a node accessible via its IP address.",
                     text_color="gray", justify="left",
                     font=ctk.CTkFont(size=11)).grid(
            row=4, column=0, sticky="w", pady=(8, 0))

        self.tcp_connect_btn = ctk.CTkButton(
            tcp_tab, text="Connect via TCP",
            command=self._connect_tcp,
            height=36)
        self.tcp_connect_btn.grid(row=5, column=0, pady=(15, 0), sticky="ew")

        # --- Status area ---
        self.status_label = ctk.CTkLabel(self, text="", text_color="gray",
                                         font=ctk.CTkFont(size=12))
        self.status_label.grid(row=2, column=0, padx=20, pady=(5, 0))

        self.progress = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress.grid(row=3, column=0, padx=20, pady=(5, 5), sticky="ew")
        self.progress.grid_remove()

        # --- Cancel / Close button ---
        self.close_btn = ctk.CTkButton(self, text="Cancel", width=100,
                                       fg_color="transparent",
                                       border_width=1,
                                       command=self.destroy)
        self.close_btn.grid(row=4, column=0, pady=(0, 15))

    def _refresh_ports(self):
        ports = MeshConnection.list_serial_ports()
        if ports:
            self.port_combo.configure(values=ports)
            self.port_var.set(ports[0])
        else:
            self.port_combo.configure(values=["No ports found"])
            self.port_var.set("No ports found")

    def _set_connecting(self, connecting: bool):
        state = "disabled" if connecting else "normal"
        self.serial_connect_btn.configure(state=state)
        self.tcp_connect_btn.configure(state=state)
        if connecting:
            self.progress.grid()
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def _connect_serial(self):
        port = self.port_var.get()
        if not port or port == "No ports found":
            self.status_label.configure(text="Please select a valid serial port.",
                                        text_color="orange")
            return

        self.status_label.configure(text=f"Connecting to {port}...", text_color="gray")
        self._set_connecting(True)

        def on_state(state, msg):
            self.after(0, self._handle_state, state, msg)

        old_cb = self.connection.on_state_change
        self.connection.on_state_change = on_state
        self.connection.connect_serial(port)
        self._original_state_cb = old_cb
        conn = MeshConnection()
        conn._load_from_device()

    def _connect_tcp(self):
        host = self.host_entry.get().strip()
        port_str = self.tcp_port_entry.get().strip()

        if not host:
            self.status_label.configure(text="Please enter a host/IP address.",
                                        text_color="orange")
            return

        try:
            port = int(port_str) if port_str else 4403
        except ValueError:
            self.status_label.configure(text="Invalid port number.", text_color="red")
            return

        self.status_label.configure(text=f"Connecting to {host}:{port}...",
                                    text_color="gray")
        self._set_connecting(True)

        def on_state(state, msg):
            self.after(0, self._handle_state, state, msg)

        old_cb = self.connection.on_state_change
        self.connection.on_state_change = on_state
        self.connection.connect_tcp(host, port)
        self._original_state_cb = old_cb

    def _handle_state(self, state: ConnectionState, msg: str):
        if state == ConnectionState.CONNECTED:
            self.status_label.configure(text="✓ Connected!", text_color="green")
            self._set_connecting(False)
            # Restore original callback and notify main window of CONNECTED state
            if hasattr(self, '_original_state_cb') and self._original_state_cb:
                self.connection.on_state_change = self._original_state_cb
                self._original_state_cb(state, msg)
            if self.on_connected:
                self.on_connected()
            self.after(800, self.destroy)
        elif state == ConnectionState.ERROR:
            self.status_label.configure(text=f"✗ {msg}", text_color="red")
            self._set_connecting(False)
            if hasattr(self, '_original_state_cb') and self._original_state_cb:
                self.connection.on_state_change = self._original_state_cb
        elif state == ConnectionState.CONNECTING:
            self.status_label.configure(text=msg, text_color="gray")


class ConnectionStatusBar(ctk.CTkFrame):
    """Compact status bar showing connection state."""

    def __init__(self, parent, connection: MeshConnection, **kwargs):
        super().__init__(parent, **kwargs)
        self.connection = connection
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)

        self.indicator = ctk.CTkLabel(self, text="●", text_color="gray",
                                      font=ctk.CTkFont(size=14))
        self.indicator.grid(row=0, column=0, padx=(8, 4), pady=4)

        self.status_text = ctk.CTkLabel(self, text="Not connected",
                                        anchor="w", font=ctk.CTkFont(size=12))
        self.status_text.grid(row=0, column=1, sticky="w", pady=4)

    def update_state(self, state: ConnectionState, msg: str = ""):
        colors = {
            ConnectionState.CONNECTED: "green",
            ConnectionState.CONNECTING: "orange",
            ConnectionState.DISCONNECTED: "gray",
            ConnectionState.ERROR: "red",
        }
        labels = {
            ConnectionState.CONNECTED: "Connected",
            ConnectionState.CONNECTING: "Connecting...",
            ConnectionState.DISCONNECTED: "Not connected",
            ConnectionState.ERROR: f"Error: {msg}",
        }
        color = colors.get(state, "gray")
        label = labels.get(state, msg)
        self.indicator.configure(text_color=color)
        self.status_text.configure(text=label)
