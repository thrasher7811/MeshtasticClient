"""
meshtastic_app.py - Main application window for Meshtastic Python Client.
Provides sidebar navigation and manages all views.
"""

import tkinter as tk
import customtkinter as ctk
from typing import Optional
from meshtastic_core import MeshConnection, ConnectionState
from meshtastic_ui_connect import ConnectionDialog, ConnectionStatusBar
from meshtastic_ui_messages import MessagesView
from meshtastic_ui_nodes import NodesView
from meshtastic_ui_map import MapView
from meshtastic_ui_settings import SettingsView


# Icons (Unicode symbols used as sidebar icons)
NAV_ICONS = {
    "Messages": "💬",
    "Map": "🗺",
    "Nodes": "📡",
    "Settings": "⚙",
}

NAV_PAGES = ["Messages", "Map", "Nodes", "Settings"]


class Sidebar(ctk.CTkFrame):
    """Left navigation sidebar with page buttons and device info."""

    def __init__(self, parent, on_navigate, connection: MeshConnection, **kwargs):
        super().__init__(parent, width=200, corner_radius=0, **kwargs)
        self.on_navigate = on_navigate
        self.connection = connection
        self._active_page = "Messages"
        self._nav_buttons = {}

        self.grid_rowconfigure(10, weight=1)  # Push status to bottom
        self.grid_propagate(False)

        self._build_ui()

    def _build_ui(self):
        # App logo/title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=12, pady=(16, 8), sticky="ew")

        ctk.CTkLabel(title_frame, text="📻",
                     font=ctk.CTkFont(size=24)).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkLabel(title_frame, text="Meshtastic",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=1)

        # Divider
        ctk.CTkFrame(self, height=1,
                     fg_color=("gray80", "gray30")).grid(
            row=1, column=0, sticky="ew", padx=12, pady=4)

        # Navigation buttons
        for i, page in enumerate(NAV_PAGES):
            icon = NAV_ICONS.get(page, "•")
            btn = ctk.CTkButton(
                self,
                text=f"  {icon}  {page}",
                anchor="w",
                height=36,
                corner_radius=6,
                fg_color="transparent",
                hover_color=("gray80", "gray25"),
                text_color=("gray10", "gray90"),
                font=ctk.CTkFont(size=13),
                command=lambda p=page: self._navigate(p)
            )
            btn.grid(row=2 + i, column=0, padx=8, pady=2, sticky="ew")
            self._nav_buttons[page] = btn

        # Divider
        ctk.CTkFrame(self, height=1,
                     fg_color=("gray80", "gray30")).grid(
            row=8, column=0, sticky="ew", padx=12, pady=4)

        # Theme switcher
        theme_frame = ctk.CTkFrame(self, fg_color="transparent")
        theme_frame.grid(row=9, column=0, padx=8, pady=4, sticky="ew")
        theme_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(theme_frame, text="Theme:",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(4, 4))
        self.theme_var = ctk.StringVar(value="Dark")
        theme_menu = ctk.CTkOptionMenu(
            theme_frame,
            values=["Dark", "Light", "System"],
            variable=self.theme_var,
            width=100,
            command=self._change_theme,
            font=ctk.CTkFont(size=11)
        )
        theme_menu.grid(row=0, column=1, sticky="e", padx=4)

        # Connection status at bottom
        self.status_bar = ConnectionStatusBar(
            self, self.connection, fg_color="transparent")
        self.status_bar.grid(row=10, column=0, sticky="sew", padx=4, pady=(4, 4))

        # Connect/Disconnect button
        self.conn_btn = ctk.CTkButton(
            self,
            text="Connect",
            height=32,
            corner_radius=6,
            command=self._toggle_connection
        )
        self.conn_btn.grid(row=11, column=0, padx=8, pady=(2, 12), sticky="ew")

        self._set_active("Messages")

    def _navigate(self, page: str):
        self._set_active(page)
        self.on_navigate(page)

    def _set_active(self, page: str):
        self._active_page = page
        for name, btn in self._nav_buttons.items():
            if name == page:
                btn.configure(fg_color=("gray75", "gray30"))
            else:
                btn.configure(fg_color="transparent")

    def _change_theme(self, choice: str):
        ctk.set_appearance_mode(choice)

    def _toggle_connection(self):
        if self.connection.is_connected:
            self.connection.disconnect()
        else:
            # Signal the main window to open connect dialog
            self.on_navigate("_connect")

    def update_connection_state(self, state: ConnectionState, msg: str = ""):
        self.status_bar.update_state(state, msg)
        if state == ConnectionState.CONNECTED:
            self.conn_btn.configure(text="Disconnect",
                                    fg_color="#c0392b",
                                    hover_color="#a93226")
        elif state == ConnectionState.CONNECTING:
            self.conn_btn.configure(text="Connecting...",
                                    fg_color="gray",
                                    state="disabled")
        else:
            self.conn_btn.configure(text="Connect",
                                    fg_color=("#1d6fa8", "#1d6fa8"),
                                    hover_color=("#1a5f8f", "#1a5f8f"),
                                    state="normal")


class LogPanel(ctk.CTkFrame):
    """Small expandable log panel for debug output."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, height=120, corner_radius=0, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, height=28, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Log",
                     font=ctk.CTkFont(size=11),
                     text_color="gray").grid(row=0, column=0, padx=8, sticky="w")
        ctk.CTkButton(header, text="Clear", width=50, height=20,
                      command=self.clear).grid(row=0, column=1, padx=4)

        self.textbox = ctk.CTkTextbox(self, height=90, font=ctk.CTkFont(
            family="Courier", size=11))
        self.textbox.grid(row=1, column=0, sticky="nsew")

    def append(self, msg: str):
        import time
        timestamp = time.strftime("%H:%M:%S")
        self.textbox.configure(state="normal")
        self.textbox.insert("end", f"[{timestamp}] {msg}\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")


class MeshtasticApp(ctk.CTk):
    """
    Main application window for the Meshtastic Python Client.
    Mirrors the functionality of the Meshtastic web client.
    """

    def __init__(self):
        super().__init__()

        self.title("Meshtastic Client")
        self.geometry("1100x720")
        self.minsize(800, 560)

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Core connection object
        self.connection = MeshConnection()
        self.connection.on_state_change = self._on_connection_state
        self.connection.on_message_received = self._on_message_received
        self.connection.on_nodes_updated = self._on_nodes_updated
        self.connection.on_log = self._on_log

        self._current_page = "Messages"

        # Set window close handler
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._build_ui()
        self._navigate("Messages")

    def _build_ui(self):
        # Horizontal PanedWindow: sidebar (left) | content+log (right)
        self.paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL,
            sashwidth=5, sashrelief="flat", sashpad=0,
            bg="#1c1c1c"
        )
        self.paned.pack(fill="both", expand=True)

        # Sidebar (left pane)
        self.sidebar = Sidebar(
            self.paned,
            on_navigate=self._navigate,
            connection=self.connection,
            fg_color=("gray90", "gray13")
        )
        self.paned.add(self.sidebar, minsize=160, width=340, sticky="nsew")

        # Right side frame: content area + collapsible log panel
        self.right_frame = ctk.CTkFrame(self.paned, corner_radius=0)
        self.paned.add(self.right_frame, minsize=400, sticky="nsew")
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(0, weight=1)

        # Main content area (inside right frame)
        self.content = ctk.CTkFrame(self.right_frame, corner_radius=0)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        # Create all views
        self.views = {}
        self.views["Messages"] = MessagesView(self.content, self.connection)
        self.views["Map"] = MapView(self.content, self.connection)
        self.views["Nodes"] = NodesView(self.content, self.connection)
        self.views["Settings"] = SettingsView(self.content, self.connection)

        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")
            view.grid_remove()

        # Log panel (collapsible at bottom of right frame)
        self.log_visible = False
        self.log_panel = LogPanel(self.right_frame, fg_color=("gray88", "gray15"))

        # Log toggle button in sidebar
        self.log_btn = ctk.CTkButton(
            self.sidebar, text="Log", width=60, height=22,
            fg_color="transparent",
            border_width=1,
            command=self._toggle_log)
        self.log_btn.grid(row=12, column=0, padx=8, pady=(0, 8), sticky="w")

    def _navigate(self, page: str):
        if page == "_connect":
            self._open_connect_dialog()
            return

        self._current_page = page
        self.sidebar._set_active(page)

        for name, view in self.views.items():
            if name == page:
                view.grid()
            else:
                view.grid_remove()

    def _open_connect_dialog(self):
        dialog = ConnectionDialog(
            self,
            self.connection,
            on_connected=self._on_dialog_connected
        )
        dialog.focus()

    def _on_dialog_connected(self):
        """Called after successful connection from dialog."""
        if hasattr(self.views.get("Messages"), "on_connected"):
            self.views["Messages"].on_connected()
        if hasattr(self.views.get("Settings"), "on_connected"):
            self.views["Settings"].on_connected()
        # Refresh nodes immediately after connecting
        if self.connection.is_connected:
            nodes_raw = {}
            for node in self.connection.get_nodes():
                num = node.raw.get("num", id(node))
                nodes_raw[num] = node.raw
            self.views["Nodes"].update_nodes(nodes_raw)
            self.views["Map"].update_nodes(nodes_raw)
            self.views["Messages"].refresh_nodes(nodes_raw)

    def _on_connection_state(self, state: ConnectionState, msg: str):
        """Update UI on connection state change (thread-safe via after)."""
        self.after(0, self._update_connection_ui, state, msg)

    def _update_connection_ui(self, state: ConnectionState, msg: str):
        self.sidebar.update_connection_state(state, msg)
        if state == ConnectionState.CONNECTED:
            self._on_log("Device connected")
        elif state == ConnectionState.DISCONNECTED:
            self._on_log("Device disconnected")
            if hasattr(self.views.get("Settings"), "on_disconnected"):
                self.after(0, self.views["Settings"].on_disconnected)
        elif state == ConnectionState.ERROR:
            self._on_log(f"Connection error: {msg}")

    def _on_message_received(self, msg):
        """Handle incoming message (thread-safe)."""
        self.after(0, self.views["Messages"].on_message_received, msg)

    def _on_nodes_updated(self, nodes_raw: dict):
        """Handle node list update (thread-safe)."""
        def update():
            self.views["Nodes"].update_nodes(nodes_raw)
            self.views["Map"].update_nodes(nodes_raw)
            self.views["Messages"].refresh_nodes(nodes_raw)
        self.after(0, update)

    def _on_log(self, msg: str):
        """Add log message (thread-safe)."""
        self.after(0, self.log_panel.append, msg)

    def _toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_panel.grid(row=1, column=0, sticky="ew")
            self.log_btn.configure(text="Log ▼")
        else:
            self.log_panel.grid_remove()
            self.log_btn.configure(text="Log ▲")

    def on_closing(self):
        """Clean up and properly close the entire application window."""
        print("[DEBUG] on_closing() called")
        try:
            if self.connection and self.connection.is_connected:
                print("[DEBUG] Disconnecting from device...")
                try:
                    self.connection.disconnect()
                    print("[DEBUG] Disconnect successful")
                except Exception as e:
                    print(f"[DEBUG] Disconnect error: {e}")
            print("[DEBUG] Sleeping before exit...")
            import time
            time.sleep(0.1)
        finally:
            # Force exit without destroy - skip widget cleanup to avoid customtkinter bugs
            print("[DEBUG] Calling os._exit(0)...")
            import os
            os._exit(0)
