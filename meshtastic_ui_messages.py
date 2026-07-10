"""
meshtastic_ui_messages.py - Messages/Chat view for Meshtastic Python Client.
Supports multi-channel chat and direct messages.
"""

import time
import threading
import customtkinter as ctk
from typing import Optional, List, Dict, Callable
from meshtastic_core import MeshConnection, MeshMessage, ConnectionState, MeshNode


class DirectMessageCard(ctk.CTkFrame):
    """Card widget for a node in the Direct Messages list."""

    def __init__(self, parent, node: MeshNode, on_select: Optional[Callable] = None, **kwargs):
        super().__init__(parent, corner_radius=6, **kwargs)
        self.node = node
        self.on_select = on_select
        self._build_ui()
        self.bind("<Button-1>", self._clicked)

    def _clicked(self, event=None):
        if self.on_select:
            self.on_select(self.node.num, self.node.long_name or self.node.short_name)

    def _bind_children(self, widget):
        """Recursively bind click to all child widgets so the whole card is clickable."""
        widget.bind("<Button-1>", self._clicked)
        for child in widget.winfo_children():
            self._bind_children(child)

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)

        # Avatar
        avatar = ctk.CTkFrame(self, width=32, height=32,
                              corner_radius=16,
                              fg_color="#2d8a4e")
        avatar.grid(row=0, column=0, rowspan=2, padx=(8, 8), pady=6, sticky="w")
        avatar.grid_propagate(False)

        short = self.node.short_name[:2] if self.node.short_name else "?"
        ctk.CTkLabel(avatar, text=short,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="white").place(relx=0.5, rely=0.5, anchor="center")

        # Node name
        ctk.CTkLabel(self, text=self.node.long_name or f"!{self.node.num:08x}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").grid(row=0, column=1, sticky="w", padx=(0, 8), pady=(6, 0))

        # Status row: SNR, last heard
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(0, 6))

        status_text = ""
        if self.node.snr is not None:
            status_text += f"SNR {self.node.snr:.1f}dB"
        status_text += f"  ⏱ {self.node.last_heard_str}"

        ctk.CTkLabel(status_frame, text=status_text,
                     font=ctk.CTkFont(size=10),
                     text_color="gray").pack(side="left")

        # Bind clicks on all child widgets
        self.after(0, lambda: self._bind_children(self))
        self.configure(cursor="hand2")


class MessagesView(ctk.CTkFrame):
    """
    Full-featured messages view with channel selection, message history,
    and message send input. Mirrors the web client Messages page.
    """

    def __init__(self, parent, connection: MeshConnection, **kwargs):
        super().__init__(parent, **kwargs)
        self.connection = connection
        self._node_refresh_ms = 30_000
        self._node_refresh_job: Optional[str] = None
        self._channel_refresh_inflight = False
        self._channels: List[Dict] = [{"index": 0, "name": "Primary"}]
        self._active_channel: int = 0
        self._dm_node: Optional[int] = None  # Node ID for direct messages
        self._nodes: Dict = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_ui()
        self._schedule_nodes_refresh(initial=True)
        self.bind("<Destroy>", self._on_destroy)

    def _build_ui(self):
        # Left panel: channel list
        self.left_panel = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew")
        # Give both channel and DM lists vertical space so channel buttons are not clipped.
        self.left_panel.grid_rowconfigure(1, weight=3)
        self.left_panel.grid_rowconfigure(3, weight=2)
        self.left_panel.grid_propagate(False)

        ctk.CTkLabel(self.left_panel, text="CHANNELS",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray").grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        self.channel_frame = ctk.CTkScrollableFrame(
            self.left_panel, label_text="", corner_radius=0)
        self.channel_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.left_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.left_panel, text="DIRECT MESSAGES",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray").grid(
            row=2, column=0, padx=12, pady=(12, 4), sticky="sw")

        self.dm_frame = ctk.CTkScrollableFrame(
            self.left_panel, label_text="", corner_radius=0, height=150)
        self.dm_frame.grid(row=3, column=0, sticky="sew", padx=0, pady=0)

        # Right panel: message area
        self.right_panel = ctk.CTkFrame(self, corner_radius=0)
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=1)

        # Header
        self.header = ctk.CTkFrame(self.right_panel, height=48, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)
        self.header.grid_columnconfigure(1, weight=1)
        
        self.header_label = ctk.CTkLabel(
            self.header, text="# Primary",
            font=ctk.CTkFont(size=15, weight="bold"), anchor="w")
        self.header_label.grid(row=0, column=0, padx=16, pady=12, sticky="w")
        
        refresh_btn = ctk.CTkButton(
            self.header, text="↻", width=36, height=24,
            command=self._manual_refresh_nodes)
        refresh_btn.grid(row=0, column=1, padx=(0, 12), pady=12, sticky="e")

        # Messages area
        self.msg_frame = ctk.CTkScrollableFrame(self.right_panel, corner_radius=0)
        self.msg_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.msg_frame.grid_columnconfigure(0, weight=1)

        self._no_messages_label = ctk.CTkLabel(
            self.msg_frame,
            text="No messages yet.\nSend a message to start the conversation.",
            text_color="gray", font=ctk.CTkFont(size=13))
        self._no_messages_label.grid(row=0, column=0, pady=40)

        # Input area
        input_frame = ctk.CTkFrame(self.right_panel, height=60, corner_radius=0)
        input_frame.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        input_frame.grid_columnconfigure(0, weight=1)

        self.msg_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Send a message...",
            height=36,
            font=ctk.CTkFont(size=13))
        self.msg_entry.grid(row=0, column=0, padx=(12, 8), pady=12, sticky="ew")
        self.msg_entry.bind("<Return>", self._send_message)
        self.msg_entry.bind("<Shift-Return>", lambda e: None)  # Allow newlines

        self.send_btn = ctk.CTkButton(
            input_frame, text="Send", width=70, height=36,
            command=self._send_message)
        self.send_btn.grid(row=0, column=1, padx=(0, 12), pady=12)

        self._render_channel_list()
        self._render_dm_list()

    def _manual_refresh_nodes(self):
        """Manually refresh channel and node lists."""
        self.refresh_channels()
        self._refresh_nodes_from_connection()

    def _render_channel_list(self):
        """Render the channel buttons in the left panel."""
        for widget in self.channel_frame.winfo_children():
            widget.destroy()

        channels_sorted = sorted(self._channels, key=lambda ch: int(ch.get("index", 0)))
        for ch in channels_sorted:
            if ch.get("role", 0) == 0:
                continue  # skip disabled slots
            ch_index = ch["index"]
            ch_name = ch.get("name") or ("Primary" if ch["role"] == 1 else f"Channel {ch_index}")

            btn_color = ("gray75", "gray25") if ch_index == self._active_channel else "transparent"

            btn = ctk.CTkButton(
                self.channel_frame,
                text=f"# {ch_name}",
                anchor="w",
                fg_color=btn_color,
                hover_color=("gray70", "gray30"),
                text_color=("black", "white"),
                command=lambda idx=ch_index, name=ch_name: self._select_channel(idx, name)
            )
            btn.pack(fill="x", padx=4, pady=2)

    def _render_dm_list(self):
        """Render direct message cards for known nodes."""
        for widget in self.dm_frame.winfo_children():
            widget.destroy()

        if not self._nodes:
            ctk.CTkLabel(self.dm_frame, text="No nodes nearby",
                         text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=4)
            return

        my_id = self.connection.get_my_node_id()
        sorted_nodes = sorted(
            self._nodes.items(),
            key=lambda item: item[1].get("lastHeard", 0),
            reverse=True,
        )

        for node_num, node_data in sorted_nodes:
            if isinstance(node_num, str):
                try:
                    node_num_int = int(node_num)
                except ValueError:
                    continue
            else:
                node_num_int = node_num

            if node_num_int == my_id:
                continue

            # Create MeshNode from raw data for consistent display
            node = MeshNode(node_data)
            is_active = (self._dm_node == node_num_int)
            
            card_bg = ("gray75", "gray30") if is_active else ("gray70", "gray20")
            card = DirectMessageCard(
                self.dm_frame, node,
                on_select=self._select_dm,
                fg_color=card_bg
            )
            card.pack(fill="x", padx=4, pady=2)


    def _refresh_nodes_from_connection(self):
        """Refresh known nodes from the active connection."""
        if not self.connection.is_connected:
            self.refresh_nodes({})
            return

        nodes_raw: Dict = {}
        for node in self.connection.get_nodes():
            node_num = node.raw.get("num", node.num)
            if node_num is None:
                continue
            nodes_raw[node_num] = node.raw

        self.refresh_nodes(nodes_raw)

    def _schedule_nodes_refresh(self, initial: bool = False):
        """Schedule periodic node refresh for the DM list."""
        if self._node_refresh_job:
            try:
                self.after_cancel(self._node_refresh_job)
            except Exception:
                pass
            self._node_refresh_job = None

        delay = 1_000 if initial else self._node_refresh_ms
        self._node_refresh_job = self.after(delay, self._auto_refresh_nodes)

    def _auto_refresh_nodes(self):
        """Refresh nodes and re-schedule the next refresh."""
        self._refresh_nodes_from_connection()
        self._schedule_nodes_refresh()

    def _on_destroy(self, event=None):
        if event is not None and event.widget is not self:
            return
        if self._node_refresh_job:
            try:
                self.after_cancel(self._node_refresh_job)
            except Exception:
                pass
            self._node_refresh_job = None

    def _select_channel(self, channel_index: int, channel_name: str):
        self._active_channel = channel_index
        self._dm_node = None
        self.header_label.configure(text=f"# {channel_name}")
        self._render_channel_list()
        self._render_messages()

    def _select_dm(self, node_id: int, node_name: str):
        self._dm_node = node_id
        self.header_label.configure(text=f"@ {node_name}")
        self._render_dm_list()
        self._render_messages()

    def _send_message(self, event=None):
        text = self.msg_entry.get().strip()
        if not text:
            return

        if not self.connection.is_connected:
            self._show_toast("Not connected to a device.")
            return

        if self._dm_node:
            success = self.connection.send_text(text, destination_id=self._dm_node)
        else:
            success = self.connection.send_text(text, channel_index=self._active_channel)

        if success:
            self.msg_entry.delete(0, "end")
        else:
            self._show_toast("Failed to send message.")

    def _show_toast(self, msg: str):
        """Show a temporary status message."""
        label = ctk.CTkLabel(self, text=msg, text_color="orange",
                             font=ctk.CTkFont(size=12))
        label.place(relx=0.5, rely=0.95, anchor="center")
        self.after(3000, label.destroy)

    def _render_messages(self):
        """Re-render the message list for current channel/DM."""
        for widget in self.msg_frame.winfo_children():
            widget.destroy()

        messages = self.connection.get_messages()

        if self._dm_node:
            my_id = self.connection.get_my_node_id()
            messages = [m for m in messages if
                        (m.from_id == self._dm_node and m.to_id == my_id) or
                        (m.from_id == my_id and m.to_id == self._dm_node)]
        else:
            messages = [m for m in messages if
                        m.channel == self._active_channel and
                        m.to_id == 0xFFFFFFFF]

        if not messages:
            self._no_messages_label = ctk.CTkLabel(
                self.msg_frame,
                text="No messages yet.\nSend a message to start the conversation.",
                text_color="gray", font=ctk.CTkFont(size=13))
            self._no_messages_label.grid(row=0, column=0, pady=40)
            return

        my_id = self.connection.get_my_node_id()

        for i, msg in enumerate(messages):
            self._add_message_bubble(msg, i, my_id)

        # Scroll to bottom
        self.after(50, self._scroll_to_bottom)

    def _add_message_bubble(self, msg: MeshMessage, row: int, my_id: Optional[int]):
        """Add a single message bubble to the message frame."""
        is_mine = msg.is_mine or (my_id and msg.from_id == my_id)
        time_str = time.strftime("%H:%M", time.localtime(msg.timestamp))

        if is_mine:
            bubble_color = ("#1d6fa8", "#1a5a8a")
            align = "e"
            text_color = ("white", "white")
            text_justify = "right"
        else:
            bubble_color = ("gray80", "gray28")
            align = "w"
            text_color = ("black", "white")
            text_justify = "left"

        bubble_frame = ctk.CTkFrame(self.msg_frame, corner_radius=14, fg_color=bubble_color)
        bubble_frame.grid(row=row, column=0, sticky=align, padx=(8, 8), pady=3)
        bubble_frame.grid_columnconfigure(0, weight=1)

        inner_row = 0

        # Sender name — only shown for others' messages
        if not is_mine:
            sender = self._get_node_name(msg.from_id)
            ctk.CTkLabel(bubble_frame, text=sender,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=("gray35", "gray60"),
                         anchor="w").grid(row=inner_row, column=0, sticky="w", padx=12, pady=(7, 0))
            inner_row += 1

        # Message text
        ctk.CTkLabel(bubble_frame, text=msg.text,
                     font=ctk.CTkFont(size=13),
                     text_color=text_color,
                     wraplength=380, justify=text_justify,
                     anchor="w" if not is_mine else "e").grid(
            row=inner_row, column=0,
            sticky="ew", padx=12,
            pady=(7 if is_mine else 4, 2))
        inner_row += 1

        # Timestamp row
        ts_anchor = "e" if is_mine else "w"
        ctk.CTkLabel(bubble_frame, text=time_str,
                     font=ctk.CTkFont(size=9),
                     text_color=("gray60", "gray55")).grid(
            row=inner_row, column=0, sticky=ts_anchor, padx=12, pady=(0, 6))
        inner_row += 1

        # SNR/RSSI for received messages
        if not is_mine and (msg.snr != 0 or msg.rssi != 0):
            info_text = f"SNR: {msg.snr:.1f}dB  RSSI: {msg.rssi}dBm"
            ctk.CTkLabel(bubble_frame, text=info_text,
                         font=ctk.CTkFont(size=10),
                         text_color=("gray45", "gray55")).grid(
                row=inner_row, column=0, sticky="w", padx=12, pady=(0, 6))

    def _get_node_name(self, node_id: int) -> str:
        """Get display name for a node ID."""
        if not node_id:
            return "Unknown"
        for node_num, node_data in self._nodes.items():
            try:
                num = int(node_num)
            except (ValueError, TypeError):
                num = node_num
            if num == node_id:
                user = node_data.get("user", {})
                return (user.get("longName") or user.get("shortName") or
                        f"!{node_id:08x}")
        return f"!{node_id:08x}"

    def _scroll_to_bottom(self):
        """Scroll messages to bottom."""
        try:
            self.msg_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def on_message_received(self, msg: MeshMessage):
        """Called when a new message is received - update the view."""
        # Only re-render if we're viewing the relevant channel/DM
        relevant = False
        my_id = self.connection.get_my_node_id()

        if self._dm_node:
            if ((msg.from_id == self._dm_node and msg.to_id == my_id) or
                    (msg.from_id == my_id and msg.to_id == self._dm_node)):
                relevant = True
        elif msg.channel == self._active_channel and msg.to_id == 0xFFFFFFFF:
            relevant = True

        if relevant:
            # Remove the "no messages" placeholder if it is still showing
            children = self.msg_frame.winfo_children()
            if len(children) == 1 and isinstance(children[0], ctk.CTkLabel):
                children[0].destroy()
                children = []
            self._add_message_bubble(msg, len(children), my_id)
            self.after(50, self._scroll_to_bottom)

    def _apply_channels(self, channels: Optional[List[Dict]]):
        if channels:
            self._channels = channels
        else:
            self._channels = [{"index": 0, "name": "Primary", "role": 1, "psk": "AQ=="}]

        active_channels = [ch for ch in self._channels if ch.get("role", 0) != 0]
        active_indices = {ch.get("index", 0) for ch in active_channels}
        if self._active_channel not in active_indices:
            fallback = next((ch for ch in active_channels if ch.get("index", 0) == 0), None)
            if fallback is None and active_channels:
                fallback = active_channels[0]
            if fallback is not None:
                self._active_channel = fallback.get("index", 0)
                if self._dm_node is None:
                    fallback_name = fallback.get("name") or (
                        "Primary" if fallback.get("role", 0) == 1 else f"Channel {self._active_channel}"
                    )
                    self.header_label.configure(text=f"# {fallback_name}")

        self._render_channel_list()
        if self._dm_node is None:
            self._render_messages()

    def refresh_channels(self, channels: Optional[List[Dict]] = None):
        """Refresh channel list from device."""
        if channels is not None:
            self._apply_channels(channels)
            return

        if not self.connection.is_connected:
            self._apply_channels(None)
            return

        if self._channel_refresh_inflight:
            return
        self._channel_refresh_inflight = True

        def _do():
            try:
                latest = self.connection.get_channels()
            except Exception:
                latest = None

            def _finish():
                self._channel_refresh_inflight = False
                self._apply_channels(latest)

            self.after(0, _finish)

        threading.Thread(target=_do, daemon=True).start()

    def refresh_nodes(self, nodes: Dict):
        """Update known nodes for DM list."""
        self._nodes = nodes or {}
        self._render_dm_list()

    def on_connected(self):
        """Called when device connects."""
        self.refresh_channels()
        self._refresh_nodes_from_connection()
        self._render_messages()

    def on_disconnected(self):
        """Called when device disconnects."""
        self._channels = [{"index": 0, "name": "Primary"}]
        self._render_channel_list()
        self.refresh_nodes({})
