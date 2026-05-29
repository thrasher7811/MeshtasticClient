"""
meshtastic_ui_map.py - Map view for Meshtastic Python Client.
Displays mesh nodes on an interactive map using tkintermapview.
Falls back to a coordinate list if tkintermapview is not installed.
"""

import customtkinter as ctk
from typing import Dict, Optional, List
from meshtastic_core import MeshConnection, MeshNode

try:
    import tkintermapview
    MAP_AVAILABLE = True
except ImportError:
    MAP_AVAILABLE = False


class MapView(ctk.CTkFrame):
    """
    Map view displaying node positions. Uses tkintermapview if available,
    otherwise shows a coordinate table as fallback.
    """

    def __init__(self, parent, connection: MeshConnection, **kwargs):
        super().__init__(parent, **kwargs)
        self.connection = connection
        self._nodes: Dict = {}
        self._markers = {}  # node_id -> marker
        self._selected_node: Optional[int] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self, height=52, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(toolbar, text="Map",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=16, pady=12)

        self.node_count = ctk.CTkLabel(toolbar, text="0 nodes with GPS",
                                       text_color="gray")
        self.node_count.grid(row=0, column=1, padx=8, pady=12)

        # Tile selector (only shown when map is available)
        if MAP_AVAILABLE:
            self.tile_var = ctk.StringVar(value="OpenStreetMap")
            tile_options = ["OpenStreetMap", "Google Normal", "Google Satellite"]
            tile_combo = ctk.CTkOptionMenu(
                toolbar, variable=self.tile_var,
                values=tile_options,
                command=self._change_tile_server,
                width=160)
            tile_combo.grid(row=0, column=3, padx=8, pady=12)

        fit_btn = ctk.CTkButton(toolbar, text="Fit All Nodes", width=110,
                                command=self._fit_nodes)
        fit_btn.grid(row=0, column=4, padx=(0, 12), pady=12)

        # Map or fallback
        if MAP_AVAILABLE:
            self._build_map()
        else:
            self._build_fallback()

    def _build_map(self):
        """Build the interactive map widget."""
        map_frame = ctk.CTkFrame(self, corner_radius=0)
        map_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        map_frame.grid_columnconfigure(0, weight=1)
        map_frame.grid_rowconfigure(0, weight=1)

        self.map_widget = tkintermapview.TkinterMapView(
            map_frame,
            width=800, height=600,
            corner_radius=0
        )
        self.map_widget.grid(row=0, column=0, sticky="nsew")
        self.map_widget.set_position(39.8283, -98.5795)  # Center of USA
        self.map_widget.set_zoom(4)

        # Node info popup frame
        self.info_frame = ctk.CTkFrame(self, width=260, corner_radius=8)
        self.info_frame.place(relx=1.0, rely=0.0, x=-8, y=60, anchor="ne")
        self.info_frame.grid_propagate(False)
        self._info_visible = False
        self.info_frame.place_forget()

    def _build_fallback(self):
        """Fallback table view when tkintermapview is not available."""
        notice = ctk.CTkFrame(self, corner_radius=8)
        notice.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        notice.grid_columnconfigure(0, weight=1)
        notice.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            notice,
            text="⚠ Map view requires tkintermapview\n"
                 "Install with: pip install tkintermapview",
            font=ctk.CTkFont(size=13),
            text_color="orange"
        ).grid(row=0, column=0, pady=(16, 8))

        # Coordinate table as fallback
        headers = ["Node", "ID", "Latitude", "Longitude", "Altitude", "Last Seen"]
        header_frame = ctk.CTkFrame(notice, corner_radius=0, height=32)
        header_frame.grid(row=1, column=0, sticky="ew")
        for i, h in enumerate(headers):
            ctk.CTkLabel(header_frame, text=h,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w").grid(row=0, column=i, padx=8, pady=4)

        self.table_frame = ctk.CTkScrollableFrame(notice, corner_radius=0)
        self.table_frame.grid(row=2, column=0, sticky="nsew")
        self.table_frame.grid_columnconfigure(list(range(6)), weight=1)
        self.table_node_rows = []

    def _change_tile_server(self, choice: str):
        """Switch between map tile providers."""
        if not MAP_AVAILABLE:
            return
        servers = {
            "OpenStreetMap": "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "Google Normal": "https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga",
            "Google Satellite": "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
        }
        if choice in servers:
            self.map_widget.set_tile_server(servers[choice])

    def _fit_nodes(self):
        """Fit the map view to show all nodes with positions."""
        nodes_with_pos = [
            MeshNode(nd) for nd in self._nodes.values()
            if MeshNode(nd).has_position
        ]
        if not nodes_with_pos:
            return

        if MAP_AVAILABLE:
            if len(nodes_with_pos) == 1:
                n = nodes_with_pos[0]
                self.map_widget.set_position(n.latitude, n.longitude)
                self.map_widget.set_zoom(12)
            else:
                lats = [n.latitude for n in nodes_with_pos]
                lons = [n.longitude for n in nodes_with_pos]
                center_lat = (max(lats) + min(lats)) / 2
                center_lon = (max(lons) + min(lons)) / 2
                self.map_widget.set_position(center_lat, center_lon)
                # Calculate appropriate zoom
                lat_span = max(lats) - min(lats)
                lon_span = max(lons) - min(lons)
                span = max(lat_span, lon_span)
                if span < 0.01:
                    zoom = 14
                elif span < 0.1:
                    zoom = 11
                elif span < 1:
                    zoom = 9
                elif span < 10:
                    zoom = 6
                else:
                    zoom = 4
                self.map_widget.set_zoom(zoom)

    def update_nodes(self, nodes_raw: Dict):
        """Update displayed nodes on the map."""
        self._nodes = nodes_raw

        nodes = [MeshNode(nd) for nd in nodes_raw.values()]
        nodes_with_pos = [n for n in nodes if n.has_position]

        self.node_count.configure(
            text=f"{len(nodes_with_pos)} node{'s' if len(nodes_with_pos) != 1 else ''} with GPS"
        )

        if MAP_AVAILABLE:
            self._update_map_markers(nodes)
        else:
            self._update_table(nodes_with_pos)

    def _update_map_markers(self, nodes: List[MeshNode]):
        """Update markers on the interactive map."""
        my_id = self.connection.get_my_node_id()
        current_ids = set()

        for node in nodes:
            if not node.has_position:
                continue

            node_id = node.num
            current_ids.add(node_id)
            is_local = (node_id == my_id)

            label = node.short_name or f"!{node_id:08x}"
            color = "#1d6fa8" if is_local else "#2d8a4e"

            def make_click_handler(n):
                def handler(marker):
                    self._show_node_info(n)
                return handler

            if node_id in self._markers:
                # Update existing marker position
                try:
                    self._markers[node_id].set_position(node.latitude, node.longitude)
                except Exception:
                    # Recreate if update fails
                    try:
                        self._markers[node_id].delete()
                    except Exception:
                        pass
                    del self._markers[node_id]

            if node_id not in self._markers:
                try:
                    marker = self.map_widget.set_marker(
                        node.latitude, node.longitude,
                        text=label,
                        marker_color_circle=color,
                        marker_color_outside=color,
                        command=make_click_handler(node)
                    )
                    self._markers[node_id] = marker
                except Exception:
                    pass

        # Remove markers for nodes that are gone
        to_remove = set(self._markers.keys()) - current_ids
        for node_id in to_remove:
            try:
                self._markers[node_id].delete()
            except Exception:
                pass
            del self._markers[node_id]

    def _update_table(self, nodes: List[MeshNode]):
        """Update the fallback coordinate table."""
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        for row, node in enumerate(nodes):
            cols = [
                node.long_name or "Unknown",
                node.node_id or f"!{node.num:08x}",
                f"{node.latitude:.6f}°" if node.latitude else "N/A",
                f"{node.longitude:.6f}°" if node.longitude else "N/A",
                f"{node.altitude}m" if node.altitude else "N/A",
                node.last_heard_str,
            ]
            bg = ("gray90", "gray20") if row % 2 == 0 else ("gray95", "gray18")
            row_frame = ctk.CTkFrame(self.table_frame, fg_color=bg, corner_radius=0)
            row_frame.grid(row=row, column=0, sticky="ew")
            self.table_frame.grid_columnconfigure(0, weight=1)

            for col_i, text in enumerate(cols):
                ctk.CTkLabel(row_frame, text=text,
                             font=ctk.CTkFont(size=12),
                             anchor="w").grid(row=0, column=col_i, padx=8, pady=4, sticky="w")

    def _show_node_info(self, node: MeshNode):
        """Show node info popup on the map."""
        if not MAP_AVAILABLE:
            return

        for widget in self.info_frame.winfo_children():
            widget.destroy()

        self.info_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.info_frame,
                     text=node.long_name or f"!{node.num:08x}",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        details = [
            ("ID", node.node_id),
            ("Hardware", node.hw_model),
            ("Battery", node.battery_str),
            ("SNR", f"{node.snr:.1f} dB" if node.snr is not None else "N/A"),
            ("Last Seen", node.last_heard_str),
            ("Lat/Lon", f"{node.latitude:.4f}, {node.longitude:.4f}"),
        ]
        if node.altitude:
            details.append(("Altitude", f"{node.altitude}m"))

        for row, (label, value) in enumerate(details, start=1):
            ctk.CTkLabel(self.info_frame,
                         text=f"{label}: {value}",
                         font=ctk.CTkFont(size=11),
                         text_color="gray", anchor="w").grid(
                row=row, column=0, padx=12, pady=1, sticky="w")

        close_btn = ctk.CTkButton(self.info_frame, text="✕", width=24, height=24,
                                  command=self.info_frame.place_forget)
        close_btn.place(relx=1.0, y=8, anchor="ne", x=-8)

        self.info_frame.place(relx=1.0, rely=0.0, x=-8, y=60, anchor="ne")
