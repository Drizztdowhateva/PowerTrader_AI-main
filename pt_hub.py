
from __future__ import annotations
# Helper: format float as percentage string
def _fmt_pct(val):
    try:
        return f"{val*100:.1f}%"
    except Exception:
        return "0.0%"
# Version: 2026-01-09
# - Fixed: Start All button in Controls/Health now always clickable (removed training-gate disable)
# - Toggle button properly shows "Start All" / "Stop All" based on runner/trader state
# - Stops neural (pt_thinker.py), trader (pt_trader.py), and all trainers when clicking "Stop All"

import os
import sys
import json
import time
import math
import queue
import threading
import subprocess
import shutil
import glob
import bisect
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter
from matplotlib.transforms import blended_transform_factory

DARK_BG = "#070B10"
DARK_BG2 = "#0B1220"
DARK_PANEL = "#0E1626"
DARK_PANEL2 = "#121C2F"
DARK_BORDER = "#243044"
DARK_FG = "#C7D1DB"
DARK_MUTED = "#8B949E"
DARK_ACCENT = "#00FF66"   
DARK_ACCENT2 = "#00E5FF"   
DARK_SELECT_BG = "#17324A"
DARK_SELECT_FG = "#00FF66"


# Global scale applied to chart figure sizes (1.0 = 100%).
# Set to 0.95 to reduce chart size by 5%.
CHART_SCALE = 0.95

@dataclass
class _WrapItem:
    w: tk.Widget
    padx: Tuple[int, int] = (0, 0)
    pady: Tuple[int, int] = (0, 0)


class WrapFrame(ttk.Frame):

    def __init__(self, parent: tk.Widget, orientation: str = "vertical", **kwargs: Any) -> None:
        """A simple container that lays out added widgets.

        orientation: "vertical" (default) places items in a column.
        orientation: "horizontal" places items in a single row.
        """
        super().__init__(parent, **kwargs)
        self._items: List[_WrapItem] = []
        self._reflow_pending = False
        self._in_reflow = False
        self._orientation = str(orientation or "vertical").lower()
        self.bind("<Configure>", self._schedule_reflow)

    def add(self, widget: tk.Widget, padx: Tuple[int, int] = (0, 0), pady: Tuple[int, int] = (0, 0)) -> None:
        self._items.append(_WrapItem(widget, padx=padx, pady=pady))
        self._schedule_reflow()

    def clear(self, destroy_widgets: bool = True) -> None:

        for it in list(self._items):
            try:
                it.w.grid_forget()
            except Exception:
                pass
            if destroy_widgets:
                try:
                    it.w.destroy()
                except Exception:
                    pass
        self._items = []
        self._schedule_reflow()

    def _schedule_reflow(self, event: Optional[Any] = None) -> None:
        if self._reflow_pending:
            return
        self._reflow_pending = True
        self.after_idle(self._reflow)

    def _reflow(self) -> None:
        # Support both vertical and horizontal layouts. Vertical places each
        # widget on its own row. Horizontal places widgets on a single row
        # across increasing columns (no wrapping).
        self._reflow_pending = False
        if self._in_reflow:
            return
        self._in_reflow = True
        try:
            for w in self._items:
                try:
                    w.w.grid_forget()
                except Exception:
                    pass

            if self._orientation == "horizontal":
                # Try to wrap items across multiple rows to fit the available width.
                try:
                    self.update_idletasks()
                except Exception:
                    pass
                avail_w = max(1, self.winfo_width() or 1)
                # If _nowrap is set, force a single left-to-right row (scrollable)
                if getattr(self, "_nowrap", False):
                    row = 0
                    col = 0
                    for it in self._items:
                        try:
                            it.w.grid(row=row, column=col, padx=it.padx, pady=it.pady, sticky="w")
                        except Exception:
                            try:
                                it.w.grid(row=row, column=col)
                            except Exception:
                                pass
                        col += 1
                else:
                    row = 0
                    col = 0
                    used_w = 0
                    for it in self._items:
                        try:
                            req_w = int(it.w.winfo_reqwidth() or 0)
                        except Exception:
                            req_w = 0
                        # pad left+right
                        pad_w = int((it.padx[0] or 0) + (it.padx[1] or 0))
                        total_w = req_w + pad_w

                        # If item doesn't fit on current row, move to next row
                        if col > 0 and (used_w + total_w) > avail_w:
                            row += 1
                            col = 0
                            used_w = 0

                        try:
                            it.w.grid(row=row, column=col, padx=it.padx, pady=it.pady, sticky="nw")
                        except Exception:
                            try:
                                it.w.grid(row=row, column=col)
                            except Exception:
                                pass

                        used_w += total_w
                        col += 1
            else:
                row = 0
                for it in self._items:
                    try:
                        it.w.grid(row=row, column=0, padx=it.padx, pady=it.pady, sticky="nw")
                    except Exception:
                        try:
                            it.w.grid(row=row, column=0)
                        except Exception:
                            pass
                    row += 1
        finally:
            self._in_reflow = False

# Compact NeuralSignalTile class (module-level)
class NeuralSignalTile(ttk.Frame):
    """Compact tile showing neural long/short levels for a coin."""

    def restore_bar_positions(self):
        """Restore bar positions from saved signal files after chart refresh (full precision)."""
        import os
        market_dir = os.path.join('./PowerTrader_AI', self.coin, '.market') if self.coin != 'BTC' else os.path.join('./PowerTrader_AI', '.market')
        long_path = os.path.join(market_dir, 'long_dca_signal.txt')
        short_path = os.path.join(market_dir, 'short_dca_signal.txt')
        def read_level(path):
            try:
                with open(path, 'r') as f:
                    val = f.read().strip()
                    return float(val)
            except Exception:
                return 0.0
        long_level = read_level(long_path)
        short_level = read_level(short_path)
        # Convert from 0-10 float to internal 0-1000
        self.set_values(long_level * (self._levels / self._display_levels), short_level * (self._levels / self._display_levels))

    def __init__(self, parent: tk.Widget, coin: str, bar_height: int = 56, display_levels: int = 10) -> None:
        super().__init__(parent)
        self.coin = coin
        self._display_levels = int(display_levels)  # Display 0-10 to user
        self._levels = 1000  # Internal resolution: 0-1000 for smooth dragging

        self._bar_h = int(bar_height)
        self._bar_w = 12
        self._gap = 16
        self._pad = 6

        self._base_fill = DARK_PANEL
        self._long_fill = "blue"
        self._short_fill = "orange"

        self._hover_on = False
        self._normal_canvas_bg = DARK_PANEL2
        self._hover_canvas_bg = DARK_PANEL
        self._normal_border = DARK_BORDER
        self._hover_border = DARK_ACCENT
        self._normal_fg = DARK_FG
        self._hover_fg = DARK_ACCENT

        self.title_lbl = ttk.Label(self, text=coin)
        self.title_lbl.pack(anchor="center")

        w = (self._pad * 2) + (self._bar_w * 2) + self._gap
        h = (self._pad * 2) + self._bar_h

        self.canvas = tk.Canvas(
            self,
            width=w,
            height=h,
            bg=self._normal_canvas_bg,
            highlightthickness=1,
            highlightbackground=self._normal_border,
        )
        self.canvas.pack(padx=2, pady=(2, 0))

        x0 = self._pad
        x1 = x0 + self._bar_w
        x2 = x1 + self._gap
        x3 = x2 + self._bar_w
        yb = self._pad + self._bar_h

        self._long_segs: List[int] = []
        self._short_segs: List[int] = []

        for seg in range(self._display_levels):
            y_top = int(round(yb - ((seg + 1) * self._bar_h / self._display_levels)))
            y_bot = int(round(yb - (seg * self._bar_h / self._display_levels)))
            self._long_segs.append(
                self.canvas.create_rectangle(x0, y_top, x1, y_bot, fill=self._base_fill, outline=DARK_BORDER, width=1)
            )
            self._short_segs.append(
                self.canvas.create_rectangle(x2, y_top, x3, y_bot, fill=self._base_fill, outline=DARK_BORDER, width=1)
            )

        trade_y = int(round(yb - (2 * self._bar_h / self._display_levels)))
        self.canvas.create_line(x0, trade_y, x1, trade_y, fill=DARK_FG, width=2)

        self.value_lbl = ttk.Label(self, text="L:0 S:0")
        self.value_lbl.pack(anchor="center", pady=(1, 0))

        # Dragging state
        self._dragging_bar = None  # 'long' or 'short'
        self._drag_start_y = None
        self._drag_start_level = None
        
        # Bind mouse events for dragging
        # Always re-bind events to ensure tooltip and drag work after refresh
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self.canvas.bind('<Motion>', self._on_hover)
        self.canvas.bind('<Leave>', self._on_leave)
        
        # Store current values
        self._current_long = 0
        self._current_short = 0
        
        # Tooltip for showing level descriptions
        self._tooltip = None
        self._tooltip_window = None
        
        self.set_values(0, 0)

    def _on_hover(self, event) -> None:
        """Show tooltip with level description when hovering."""
        try:
            x = event.x
            y = event.y
            
            # Calculate bar positions
            x0 = self._pad
            x1 = x0 + self._bar_w
            x2 = x1 + self._gap
            x3 = x2 + self._bar_w
            
            # Determine which bar and which level
            bar_type = None
            if x0 <= x <= x1:
                bar_type = 'long'
                current_level = self._current_long
            elif x2 <= x <= x3:
                bar_type = 'short'
                current_level = self._current_short
            
            if bar_type:
                # Convert internal level (0-1000) to display level (0-10)
                display_level = self._internal_to_display(current_level)
                float_level = (current_level / self._levels) * self._display_levels
                # Format as dollar value $X.XXX
                dollar_value = f"${float_level:.3f}"
                # Level descriptions
                level_desc = {
                    0: "No signal",
                    1: "Very weak signal",
                    2: "Weak signal",
                    3: "Moderate signal",
                    4: "Good signal",
                    5: "Strong signal",
                    6: "Very strong signal",
                    7: "Maximum signal",
                    8: "Extreme signal",
                    9: "Ultra signal",
                    10: "Peak signal"
                }
                desc = level_desc.get(display_level, "Unknown")
                signal_name = "LONG (Buy)" if bar_type == 'long' else "SHORT (Sell)"
                # Create tooltip text with integer neural level and dollar value
                # If under chart (DCA drag), show value to 3 decimals only
                # Always show float to 3 decimals for drag lines
                if hasattr(self, 'is_dca_tile') and self.is_dca_tile:
                    tooltip_text = f"{float(float_level):.3f}"
                elif bar_type == 'dca' or bar_type == 'buy' or bar_type == 'sell':
                    tooltip_text = f"{float_level:.3f}"
                else:
                    tooltip_text = f"{signal_name}: Level {display_level}\n{desc}\nValue: {float_level:.3f}\n\nDrag to adjust"
                
                # Show tooltip near cursor
                if self._tooltip:
                    try:
                        self._tooltip.destroy()
                    except Exception:
                        pass
                
                self._tooltip = tk.Toplevel(self)
                self._tooltip.wm_overrideredirect(True)
                self._tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                
                label = tk.Label(
                    self._tooltip,
                    text=tooltip_text,
                    background="#2b2b2b",
                    foreground="#e0e0e0",
                    relief="solid",
                    borderwidth=1,
                    padx=8,
                    pady=4,
                    font=("TkDefaultFont", 9)
                )
                label.pack()
                return
            
            # Not hovering over a bar - hide tooltip
            if self._tooltip:
                try:
                    self._tooltip.destroy()
                    self._tooltip = None
                except Exception:
                    pass
                    
        except Exception:
            pass
    
    def _on_press(self, event) -> str:
        """Start dragging when user clicks on a bar. Snap to clicked level."""
        try:
            x = event.x
            y = event.y
            
            # Calculate bar x positions
            x0 = self._pad
            x1 = x0 + self._bar_w
            x2 = x1 + self._gap
            x3 = x2 + self._bar_w
            
            # Convert y position to level (snap on click)
            clicked_level = self._y_to_level(y)
            
            # Check if click is on long bar (left)
            if x0 <= x <= x1:
                self._dragging_bar = 'long'
                self._drag_start_y = y
                self._drag_start_level = clicked_level
                # Snap to clicked level immediately
                self.set_values(clicked_level, self._current_short)
                self._write_signal_file('long', clicked_level)
                # Trigger immediate chart refresh
                try:
                    self.event_generate("<<NeuralLevelChanged>>", when="tail")
                except Exception:
                    pass
                return "break"  # Stop event propagation
            # Check if click is on short bar (right)
            elif x2 <= x <= x3:
                self._dragging_bar = 'short'
                self._drag_start_y = y
                self._drag_start_level = clicked_level
                # Snap to clicked level immediately
                self.set_values(self._current_long, clicked_level)
                self._write_signal_file('short', clicked_level)
                # Trigger immediate chart refresh
                try:
                    self.event_generate("<<NeuralLevelChanged>>", when="tail")
                except Exception:
                    pass
                return "break"  # Stop event propagation
        except Exception:
            pass
        return "break"  # Always stop propagation for canvas clicks
    
    def _y_to_level(self, y: int) -> int:
        """Convert y coordinate to level (0 to _levels)."""
        try:
            # Invert y because canvas y increases downward
            normalized = 1.0 - (y / self._bar_h)
            level = int(round(normalized * self._levels))
            return max(0, min(level, self._levels))
        except Exception:
            return 0
    
    def _on_drag(self, event) -> str:
        """Update bar level as user drags, with live chart updates. Uses 0-100 internal resolution."""
        if not self._dragging_bar or self._drag_start_y is None or self._drag_start_level is None:
            return "break"
        
        try:
            y = event.y
            # Convert y position directly to level (0-100)
            new_level = self._y_to_level(y)
            
            # Update the appropriate bar and write to file (only if changed)
            if self._dragging_bar == 'long':
                if new_level != self._current_long:
                    self.set_values(new_level, self._current_short)
                    self._write_signal_file('long', new_level)
                    # Trigger chart refresh during drag for real-time flag updates
                    try:
                        self.event_generate("<<NeuralLevelChanged>>", when="tail")
                    except Exception:
                        pass
            elif self._dragging_bar == 'short':
                if new_level != self._current_short:
                    self.set_values(self._current_long, new_level)
                    self._write_signal_file('short', new_level)
                    # Trigger chart refresh during drag for real-time flag updates
                    try:
                        self.event_generate("<<NeuralLevelChanged>>", when="tail")
                    except Exception:
                        pass
        except Exception:
            pass
        return "break"  # Stop event propagation
    
    def _on_release(self, event) -> str:
        """Finish dragging - just cleanup since we already wrote during drag."""
        # Hide tooltip on release
        self._hide_tooltip()
        
        if not self._dragging_bar:
            return "break"
        
        try:
            # Final chart refresh to ensure everything is in sync
            try:
                self.event_generate("<<NeuralLevelChanged>>", when="tail")
            except Exception:
                pass
        except Exception as e:
            print(f"Error on release: {e}")
        finally:
            self._dragging_bar = None
            self._drag_start_y = None
            self._drag_start_level = None
        return "break"  # Stop event propagation
    
    def _on_leave(self, event) -> None:
        """Hide tooltip when mouse leaves the widget."""
        self._hide_tooltip()
    
    def _hide_tooltip(self) -> None:
        """Helper method to hide and destroy the tooltip."""
        if self._tooltip:
            try:
                self._tooltip.destroy()
                self._tooltip = None
            except Exception:
                pass
    
    def _write_signal_file(self, signal_type: str, level: int) -> None:
        """Write the signal level to the appropriate file. Converts internal (0-1000) to display (0-10)."""
        try:
            # Convert internal level (0-1000) to display level (0-10) for file
            display_level = self._internal_to_display(level)
            
            # Import here to avoid circular dependencies
            import os
            
            # Determine the folder for this coin
            # Try to get main_neural_dir from parent app settings
            folder = None
            try:
                # Navigate up to PowerTraderHub to get settings
                widget = self
                while widget:
                    if hasattr(widget, 'settings') and isinstance(getattr(widget, 'settings', None), dict):
                        main_dir = getattr(widget, 'settings').get('main_neural_dir', './PowerTrader_AI')
                        if self.coin == 'BTC':
                            folder = main_dir
                        else:
                            folder = os.path.join(main_dir, self.coin)
                        break
                    widget = widget.master if hasattr(widget, 'master') else None
            except Exception:
                pass
            
            if not folder:
                folder = f'./PowerTrader_AI/{self.coin}' if self.coin != 'BTC' else './PowerTrader_AI'
            
            # Ensure .market subfolder exists
            market_dir = os.path.join(folder, '.market')
            os.makedirs(market_dir, exist_ok=True)
            
            # Write to file in .market subfolder
            filename = f'{signal_type}_dca_signal.txt'
            filepath = os.path.join(market_dir, filename)
            
            with open(filepath, 'w') as f:
                f.write(str(display_level))
            
            print(f"[{self.coin}] Updated {signal_type} signal to {display_level} (internal: {level})")
            
        except Exception as e:
            print(f"[{self.coin}] Error writing {signal_type} signal file: {e}")

    def set_hover(self, on: bool) -> None:
        if bool(on) == bool(self._hover_on):
            return
        self._hover_on = bool(on)
        try:
            if self._hover_on:
                self.canvas.configure(bg=self._hover_canvas_bg, highlightbackground=self._hover_border, highlightthickness=2)
                self.title_lbl.configure(foreground=self._hover_fg)
                self.value_lbl.configure(foreground=self._hover_fg)
            else:
                self.canvas.configure(bg=self._normal_canvas_bg, highlightbackground=self._normal_border, highlightthickness=1)
                self.title_lbl.configure(foreground=self._normal_fg)
                self.value_lbl.configure(foreground=self._normal_fg)
        except Exception:
            pass

    def _clamp_level(self, value: Any) -> int:
        """Clamp value to internal range (0-1000)."""
        try:
            v = int(float(value))
        except Exception:
            v = 0
        return max(0, min(v, self._levels))

    def _display_to_internal(self, display_level: int) -> int:
        """Convert display level (0-10) to internal level (0-1000)."""
        # Map 0-10 to 0-1000 evenly
        return int((display_level / self._display_levels) * self._levels)

    def _internal_to_display(self, internal_level: int) -> int:
        """Convert internal level (0-1000) to display level (0-10)."""
        # Map 0-1000 to 0-10
        return int(round((internal_level / self._levels) * self._display_levels))

    def _set_level(self, seg_ids: List[int], level: int, active_fill: str) -> None:
        """Set visual bar level. Level is in internal range (0-100)."""
        # Clear all segments
        for rid in seg_ids:
            self.canvas.itemconfigure(rid, fill=self._base_fill)
        if level <= 0:
            return
        
        # Calculate how many of the 7 visual segments to fill based on 0-100 value
        display_level = self._internal_to_display(level)
        if display_level <= 0:
            return
        idx = display_level - 1
        if idx < 0:
            return
        if idx >= len(seg_ids):
            idx = len(seg_ids) - 1
        for i in range(idx + 1):
            self.canvas.itemconfigure(seg_ids[i], fill=active_fill)

    def set_values(self, long_sig: Any, short_sig: Any) -> None:
        """Set values. Expects internal levels (0-1000) or will convert from display (0-10) if reading from file."""
        ls = self._clamp_level(long_sig)
        ss = self._clamp_level(short_sig)
        
        # If values are in display range (0-10), convert to internal (0-1000)
        if ls <= self._display_levels:
            ls = self._display_to_internal(ls)
        if ss <= self._display_levels:
            ss = self._display_to_internal(ss)
        
        self._current_long = ls
        self._current_short = ss
        
        # Show display values in label (0-10)
        display_long = self._internal_to_display(ls)
        display_short = self._internal_to_display(ss)
        self.value_lbl.config(text=f"L:{display_long} S:{display_short}")
        
        self._set_level(self._long_segs, ls, self._long_fill)
        self._set_level(self._short_segs, ss, self._short_fill)
    
    def destroy(self):
        """Clean up tooltip when destroying widget."""
        try:
            if self._tooltip:
                self._tooltip.destroy()
        except Exception:
            pass
        super().destroy()


# -----------------------------
# Settings / Paths
# -----------------------------

DEFAULT_SETTINGS = {
    "main_neural_dir": "./PowerTrader_AI",
    "coins": ["BTC", "ETH", "XRP", "BNB", "DOGE"],
    "available_coins": ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "TRX", "DOT", "MATIC", "LINK", "UNI", "SHIB", "LTC"],
    "default_timeframe": "1hour",
    "timeframes": [
        "1min", "5min", "15min", "30min",
        "1hour", "2hour", "4hour", "8hour", "12hour",
        "1day", "1week"
    ],
    "candles_limit": 120,
    "ui_refresh_seconds": 1.0,
    "chart_refresh_seconds": 10.0,
    "hub_data_dir": "",  # if blank, defaults to <this_dir>/hub_data
    "script_neural_runner2": "pt_thinker.py",
    "script_neural_trainer": "pt_trainer.py",
    "script_trader": "pt_trader.py",
    "auto_start_scripts": False,
    "use_kucoin_api": False,
    # Exchange enable/disable flags
    "exchange_binance_enabled": False,
    "exchange_kraken_enabled": False,
    "exchange_coinbase_enabled": False,
    "exchange_bybit_enabled": False,
    "exchange_robinhood_enabled": False,
    "exchange_kucoin_enabled": False,
    # Per-coin long/short sell prices (initialized on first boot with 2% margin)
    "coin_long_sell_prices": {},  # {"BTC": 93000.00, "ETH": 3500.00, ...}
    "coin_short_sell_prices": {},  # {"BTC": 89000.00, "ETH": 3300.00, ...}
}




SETTINGS_FILE = "gui_settings.json"


def _safe_read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _safe_write_json(path: str, data: Dict[str, Any]) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _read_trade_history_jsonl(path: str) -> List[Dict[str, Any]]:
    """
    Reads hub_data/trade_history.jsonl written by pt_trader.py.
    Returns a list of dicts (only buy/sell rows).
    """
    out: List[Dict[str, Any]] = []
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        obj = json.loads(ln)
                        side = str(obj.get("side", "")).lower().strip()
                        if side not in ("buy", "sell"):
                            continue
                        out.append(obj)
                    except Exception:
                        continue
    except Exception:
        pass
    return out


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _open_in_file_manager(path: str) -> None:
    """Open the given path in the system file manager (cross-platform)."""
    try:
        p = os.path.abspath(path)
        if os.name == "nt":
            os.startfile(p)  # type: ignore[attr-defined]
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", p])
            return
        subprocess.Popen(["xdg-open", p])
    except Exception as e:
        try:
            messagebox.showerror("Couldn't open folder", f"Tried to open:\n{path}\n\nError:\n{e}")
        except Exception:
            pass



def _fmt_money(x: float) -> str:
    """Format a USD *amount* (account value, position value, etc.) as dollars with 2 decimals."""
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "N/A"


def _fmt_price(x: Any) -> str:
    """
    Format a USD *price/level* with dynamic decimals based on magnitude.
    Examples:
      50234.12   -> $50,234.12
      123.4567   -> $123.457
      1.234567   -> $1.2346
      0.06234567 -> $0.062346
      0.00012345 -> $0.00012345
    """
    try:
        if x is None:
            return "N/A"

        try:
            # Convert internal level (0-1000) to display level (0-10) as float
            float_level = (level / self._levels) * self._display_levels
            import os
            folder = None
            try:
                widget = self
                while widget:
                    if hasattr(widget, 'settings') and isinstance(getattr(widget, 'settings', None), dict):
                        main_dir = getattr(widget, 'settings').get('main_neural_dir', './PowerTrader_AI')
                        if self.coin == 'BTC':
                            folder = main_dir
                        else:
                            folder = os.path.join(main_dir, self.coin)
                        break
                    widget = widget.master if hasattr(widget, 'master') else None
            except Exception:
                pass
            if not folder:
                folder = f'./PowerTrader_AI/{self.coin}' if self.coin != 'BTC' else './PowerTrader_AI'
            market_dir = os.path.join(folder, '.market')
            os.makedirs(market_dir, exist_ok=True)
            filename = f'{signal_type}_dca_signal.txt'
            filepath = os.path.join(market_dir, filename)
            with open(filepath, 'w') as f:
                f.write(f"{float_level:.3f}")
            print(f"[{self.coin}] Updated {signal_type} signal to {float_level:.3f} (internal: {level})")
        except Exception as e:
            print(f"[{self.coin}] Error writing {signal_type} signal file: {e}")
    except Exception:
        return "N/A"


def _now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _fmt_uptime(seconds: float) -> str:
    try:
        s = int(max(0, int(seconds)))
        days, rem = divmod(s, 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        if days > 0:
            return f"{days}d {hours:02d}:{mins:02d}:{secs:02d}"
        return f"{hours}:{mins:02d}:{secs:02d}"
    except Exception:
        return "N/A"


# -----------------------------
# Neural folder detection
# -----------------------------

def build_coin_folders(main_dir: str, coins: List[str]) -> Dict[str, str]:
    """
    Mirrors your convention:
      BTC uses main_dir directly
      other coins typically have subfolders inside main_dir (auto-detected)

    Returns { "BTC": "...", "ETH": "...", ... }
    """
    out: Dict[str, str] = {}
    # Normalize to an absolute Path (avoid returning relative paths which later cause double-prefixing)
    md = Path(main_dir) if main_dir else Path.cwd()
    if not md.is_absolute():
        md = (Path.cwd() / md)
    # Resolve without strict to avoid errors if path doesn't exist yet
    try:
        md = md.resolve(strict=False)
    except Exception:
        md = md.absolute()

    # BTC folder (absolute)
    out["BTC"] = str(md)

    # Auto-detect subfolders
    if md.is_dir():
        for p in md.iterdir():
            if not p.is_dir():
                continue
            name = p.name
            sym = name.upper().strip()
            if sym in coins and sym != "BTC":
                out[sym] = str(p.resolve(strict=False))

    # Fallbacks for missing ones
    for c in coins:
        c = c.upper().strip()
        if c not in out:
            out[c] = str((md / c).resolve(strict=False))  # best-effort fallback (absolute)

    return out


def read_price_levels_from_html(path: str) -> List[float]:
    """
    pt_thinker writes a python-list-like string into low_bound_prices.html / high_bound_prices.html.

    Example (commas often remain):
        "43210.1, 43100.0, 42950.5"

    So we normalize separators before parsing.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()

        if not raw:
            return []

        # Normalize common separators that pt_thinker can leave behind
        raw = (
            raw.replace(",", " ")
               .replace("[", " ")
               .replace("]", " ")
               .replace("'", " ")
        )

        vals: List[float] = []
        for tok in raw.split():
            try:
                v = float(tok)

                # Filter obvious sentinel values used by pt_thinker for "inactive" slots
                if v <= 0:
                    continue
                if v >= 9e15:  # pt_thinker uses 99999999999999999
                    continue


                vals.append(v)
            except Exception:
                pass

        # De-dupe while preserving order (small rounding to avoid float-noise duplicates)
        out: List[float] = []
        seen = set()
        for v in vals:
            key = round(v, 12)
            if key in seen:
                continue
            seen.add(key)
            out.append(v)

        return out
    except Exception:
        return []



def read_int_from_file(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        return int(float(raw))
    except Exception:
        return 0


def read_short_signal(folder: str) -> int:
    txt = os.path.join(folder, "short_dca_signal.txt")
    if os.path.isfile(txt):
        return read_int_from_file(txt)
    else:
        return 0


# -----------------------------
# Candle fetching (KuCoin)
# -----------------------------

class CandleFetcher:
    """
    Uses kucoin-python if available; otherwise falls back to KuCoin REST via requests.
    """
    def __init__(self):
        self._mode = "kucoin_client"
        self._market = None
        try:
            from kucoin.client import Market  # type: ignore
            self._market = Market(url="https://api.kucoin.com")
        except Exception:
            self._mode = "rest"
            self._market = None

        if self._mode == "rest":
            import requests  # local import
            self._requests = requests

        # Small in-memory cache to keep timeframe switching snappy.
        # key: (pair, timeframe, limit) -> (saved_time_epoch, candles)
        self._cache: Dict[Tuple[str, str, int], Tuple[float, List[dict]]] = {}
        self._cache_ttl_seconds: float = 10.0


    def get_klines(self, symbol: str, timeframe: str, limit: int = 120) -> List[Dict[str, Any]]:
        """
        Returns candles oldest->newest as:
          [{"ts": int, "open": float, "high": float, "low": float, "close": float}, ...]
        """
        symbol = symbol.upper().strip()

        # Your neural uses USDT pairs on KuCoin (ex: BTC-USDT)
        pair = f"{symbol}-USDT"
        limit = int(limit or 0)

        now = time.time()
        cache_key = (pair, timeframe, limit)
        cached = self._cache.get(cache_key)
        if cached and (now - float(cached[0])) <= float(self._cache_ttl_seconds):
            return cached[1]

        # rough window (timeframe-dependent) so we get enough candles
        tf_seconds = {
            "1min": 60, "5min": 300, "15min": 900, "30min": 1800,
            "1hour": 3600, "2hour": 7200, "4hour": 14400, "8hour": 28800, "12hour": 43200,
            "1day": 86400, "1week": 604800
        }.get(timeframe, 3600)

        end_at = int(now)
        start_at = end_at - (tf_seconds * max(200, (limit + 50) if limit else 250))

        if self._mode == "kucoin_client" and self._market is not None:
            try:
                # IMPORTANT: limit the server response by passing startAt/endAt.
                # This avoids downloading a huge default kline set every switch.
                try:
                    raw = self._market.get_kline(pair, timeframe, startAt=start_at, endAt=end_at)  # type: ignore
                except Exception:
                    # fallback if that client version doesn't accept kwargs
                    raw = self._market.get_kline(pair, timeframe)  # returns newest->oldest

                candles: List[dict] = []
                for row in raw:
                    # KuCoin kline row format:
                    # [time, open, close, high, low, volume, turnover]
                    ts = int(float(row[0]))
                    o = float(row[1]); c = float(row[2]); h = float(row[3]); l = float(row[4])
                    candles.append({"ts": ts, "open": o, "high": h, "low": l, "close": c})
                candles.sort(key=lambda x: x["ts"])
                if limit and len(candles) > limit:
                    candles = candles[-limit:]

                self._cache[cache_key] = (now, candles)
                return candles
            except Exception:
                return []

        # REST fallback
        try:
            url = "https://api.kucoin.com/api/v1/market/candles"
            params = {"symbol": pair, "type": timeframe, "startAt": start_at, "endAt": end_at}
            resp = self._requests.get(url, params=params, timeout=10)
            j = resp.json()
            data = j.get("data", [])  # newest->oldest
            candles: List[dict] = []
            for row in data:
                ts = int(float(row[0]))
                o = float(row[1]); c = float(row[2]); h = float(row[3]); l = float(row[4])
                candles.append({"ts": ts, "open": o, "high": h, "low": l, "close": c})
            candles.sort(key=lambda x: x["ts"])
            if limit and len(candles) > limit:
                candles = candles[-limit:]

            self._cache[cache_key] = (now, candles)
            return candles
        except Exception:
            return []



# -----------------------------
# Chart widget
# -----------------------------

class CandleChart(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        fetcher: CandleFetcher,
        coin: str,
        settings_getter,
        trade_history_path: str,
    ):
        super().__init__(parent)
        self.fetcher = fetcher
        self.coin = coin
        self.settings_getter = settings_getter
        self.trade_history_path = trade_history_path

        self.timeframe_var = tk.StringVar(value=self.settings_getter()["default_timeframe"])


        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)

        ttk.Label(top, text=f"{coin} chart").pack(side="left")

        ttk.Label(top, text="Timeframe:").pack(side="left", padx=(12, 4))
        self.tf_combo = ttk.Combobox(
            top,
            textvariable=self.timeframe_var,
            values=self.settings_getter()["timeframes"],
            state="readonly",
            width=10,
        )
        self.tf_combo.pack(side="left")

        # Debounce rapid timeframe changes so redraws don't stack
        self._tf_after_id = None

        def _debounced_tf_change(*_):
            try:
                if self._tf_after_id:
                    self.after_cancel(self._tf_after_id)
            except Exception:
                pass

            def _do():
                # Ask the hub to refresh charts on the next tick (single refresh)
                try:
                    self.event_generate("<<TimeframeChanged>>", when="tail")
                except Exception:
                    pass

            self._tf_after_id = self.after(120, _do)

        self.tf_combo.bind("<<ComboboxSelected>>", _debounced_tf_change)


        self.neural_status_label = ttk.Label(top, text="Neural: N/A")
        self.neural_status_label.pack(side="left", padx=(12, 0))

        self.last_update_label = ttk.Label(top, text="Last: N/A")
        self.last_update_label.pack(side="right")

        # Figure
        # IMPORTANT: keep a stable DPI and resize the figure to the widget's pixel size.
        # On Windows scaling, trying to "sync DPI" via winfo_fpixels("1i") can produce the
        # exact right-side blank/covered region you're seeing.
        self.fig = Figure(figsize=(6.5 * CHART_SCALE, 3.5 * CHART_SCALE), dpi=100)
        self.fig.patch.set_facecolor(DARK_BG)

        # Use tighter margins so the plot fills the available widget area while
        # still leaving room for x-tick labels and a small right margin for price labels.
        self.fig.subplots_adjust(left=0.06, right=0.88, bottom=0.12, top=0.95)

        self.ax = self.fig.add_subplot(111)
        self._apply_dark_chart_style()
        self.ax.set_title(f"{coin}", color=DARK_FG)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg=DARK_BG)

        # Remove horizontal padding here so the chart widget truly fills the container.
        self.canvas_widget.pack(fill="both", expand=True, padx=0, pady=(0, 6))

        # Draggable neural levels state
        self._dragging_line = None
        self._dragging_is_long = None
        self._drag_original_price = None
        self._neural_lines_long = []
        self._neural_lines_short = []
        self._current_folder = ""
        
        # Draggable buy/sell price lines
        self._buy_line = None
        self._sell_line = None
        self._buy_price = None
        self._sell_price = None
        self._trail_line = None
        self._trail_price = None
        self._dca_line = None
        self._dca_price = None
        self._dragging_type = None  # 'long', 'short', 'buy', 'sell', 'trail', or 'dca'
        
        # Connect mouse events for dragging neural levels - AFTER canvas is packed
        self._mouse_cids = []
        try:
            # Use Tkinter bindings instead of matplotlib's event system for more reliable interaction
            self.canvas_widget.bind('<Button-1>', self._tk_on_mouse_press, add='+')
            self.canvas_widget.bind('<B1-Motion>', self._tk_on_mouse_move, add='+')
            self.canvas_widget.bind('<ButtonRelease-1>', self._tk_on_mouse_release, add='+')
            self.canvas_widget.bind('<Motion>', self._tk_on_hover, add='+')
            print(f"[CandleChart {coin}] Tkinter mouse event handlers connected to {self.canvas_widget}")
        except Exception as e:
            print(f"[CandleChart {coin}] Error connecting events: {e}")
        
        # Add hover indicator text (shows when mouse is near a draggable line)
        self._hover_text = None

        # Keep the matplotlib figure EXACTLY the same pixel size as the Tk widget.
        # FigureCanvasTkAgg already sizes its backing PhotoImage to e.width/e.height.
        # Multiplying by tk scaling here makes the renderer larger than the PhotoImage,
        # which produces the "blank/covered strip" on the right.
        self._last_canvas_px = (0, 0)
        self._resize_after_id = None

        def _on_canvas_configure(e):
            try:
                w = int(e.width)
                h = int(e.height)
                if w <= 1 or h <= 1:
                    return

                if (w, h) == self._last_canvas_px:
                    return
                self._last_canvas_px = (w, h)

                dpi = float(self.fig.get_dpi() or 100.0)
                self.fig.set_size_inches(w / dpi, h / dpi, forward=True)

                # Debounce redraws during live resize
                if self._resize_after_id:
                    try:
                        self.after_cancel(self._resize_after_id)
                    except Exception:
                        pass
                self._resize_after_id = self.after_idle(self.canvas.draw_idle)
            except Exception:
                pass

        self.canvas_widget.bind("<Configure>", _on_canvas_configure, add="+")







        self._last_refresh = 0.0


    def _apply_dark_chart_style(self) -> None:
        """Apply dark styling (called on init and after every ax.clear())."""
        try:
            self.fig.patch.set_facecolor(DARK_BG)
            self.ax.set_facecolor(DARK_PANEL)
            self.ax.tick_params(colors=DARK_FG)
            for spine in self.ax.spines.values():
                spine.set_color(DARK_BORDER)
            self.ax.grid(True, color=DARK_BORDER, linewidth=0.6, alpha=0.35)
        except Exception:
            pass

    def refresh(
        self,
        coin_folders: Dict[str, str],
        current_buy_price: Optional[float] = None,
        current_sell_price: Optional[float] = None,
        trail_line: Optional[float] = None,
        dca_line_price: Optional[float] = None,
    ) -> None:


        cfg = self.settings_getter()

        tf = self.timeframe_var.get().strip()
        limit = int(cfg.get("candles_limit", 120))

        candles = self.fetcher.get_klines(self.coin, tf, limit=limit)

        folder = coin_folders.get(self.coin, "")
        market_dir = os.path.join(folder, ".market") if folder else ""
        low_path = os.path.join(market_dir, "low_bound_prices.html") if market_dir else ""
        high_path = os.path.join(market_dir, "high_bound_prices.html") if market_dir else ""

        # --- Cached neural reads (per path, by mtime) ---
        if not hasattr(self, "_neural_cache"):
            self._neural_cache = {}  # path -> (mtime, value)

        def _cached(path: str, loader, default):
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                return default
            hit = self._neural_cache.get(path)
            if hit and hit[0] == mtime:
                return hit[1]
            v = loader(path)
            self._neural_cache[path] = (mtime, v)
            return v

        long_levels = _cached(low_path, read_price_levels_from_html, []) if market_dir else []
        short_levels = _cached(high_path, read_price_levels_from_html, []) if market_dir else []

        long_sig_path = os.path.join(market_dir, "long_dca_signal.txt") if market_dir else ""
        long_sig = _cached(long_sig_path, read_int_from_file, 0) if market_dir else 0
        short_sig = read_short_signal(market_dir) if market_dir else 0

        # --- Avoid full ax.clear() (expensive). Just clear artists. ---
        try:
            self.ax.lines.clear()
            self.ax.patches.clear()
            self.ax.collections.clear()  # scatter dots live here
            self.ax.texts.clear()        # labels/annotations live here
        except Exception:
            # fallback if matplotlib version lacks .clear() on these lists
            self.ax.cla()
            self._apply_dark_chart_style()


        if not candles:
            self.ax.set_title(f"{self.coin} ({tf}) - no candles", color=DARK_FG)
            self.canvas.draw_idle()
            return


        # Candlestick drawing (green up / red down) - batch rectangles
        xs = getattr(self, "_xs", None)
        if not xs or len(xs) != len(candles):
            xs = list(range(len(candles)))
            self._xs = xs

        rects = []
        for i, c in enumerate(candles):
            o = float(c["open"])
            cl = float(c["close"])
            h = float(c["high"])
            l = float(c["low"])

            up = cl >= o
            candle_color = "green" if up else "red"

            # wick
            self.ax.plot([i, i], [l, h], linewidth=1, color=candle_color)

            # body
            bottom = min(o, cl)
            height = abs(cl - o)
            if height < 1e-12:
                height = 1e-12

            rects.append(
                Rectangle(
                    (i - 0.35, bottom),
                    0.7,
                    height,
                    facecolor=candle_color,
                    edgecolor=candle_color,
                    linewidth=1,
                    alpha=0.9,
                )
            )

        for r in rects:
            self.ax.add_patch(r)

        # Lock y-limits to candle range so overlay lines can go offscreen without expanding the chart.
        try:
            y_low = min(float(c["low"]) for c in candles)
            y_high = max(float(c["high"]) for c in candles)
            pad = (y_high - y_low) * 0.03
            if not math.isfinite(pad) or pad <= 0:
                pad = max(abs(y_low) * 0.001, 1e-6)
            self.ax.set_ylim(y_low - pad, y_high + pad)
        except Exception:
            pass



        # Overlay Neural levels (blue long, orange short)
        self._neural_lines_long = []
        self._neural_lines_short = []
        self._current_folder = folder
        
        print(f"[{self.coin}] Populating neural lines: {len(long_levels)} long, {len(short_levels)} short")
        
        for lv in long_levels:
            try:
                line = self.ax.axhline(y=float(lv), linewidth=1, color="blue", alpha=0.8, picker=5)
                self._neural_lines_long.append((line, float(lv)))
                print(f"  Added LONG line at {float(lv):.2f}")
            except Exception as e:
                print(f"  Error adding LONG line: {e}")

        for lv in short_levels:
            try:
                line = self.ax.axhline(y=float(lv), linewidth=1, color="orange", alpha=0.8, picker=5)
                self._neural_lines_short.append((line, float(lv)))
                print(f"  Added SHORT line at {float(lv):.2f}")
            except Exception as e:
                print(f"  Error adding SHORT line: {e}")
        
        print(f"[{self.coin}] Total stored: {len(self._neural_lines_long)} long, {len(self._neural_lines_short)} short")


        # Overlay Trailing PM line (sell) and next DCA line (make them draggable)
        self._trail_line = None
        self._trail_price = None
        self._dca_line = None
        self._dca_price = None
        
        try:
            if trail_line is not None and float(trail_line) > 0:
                self._trail_price = float(trail_line)
                self._trail_line = self.ax.axhline(y=self._trail_price, linewidth=1.5, color="green", alpha=0.95, picker=5)
        except Exception:
            pass

        try:
            if dca_line_price is not None and float(dca_line_price) > 0:
                self._dca_price = float(dca_line_price)
                self._dca_line = self.ax.axhline(y=self._dca_price, linewidth=1.5, color="red", alpha=0.95, picker=5)
        except Exception:
            pass

        # Overlay current ask/bid prices (make them draggable)
        self._buy_line = None
        self._buy_price = None
        self._sell_line = None
        self._sell_price = None
        
        try:
            if current_buy_price is not None and float(current_buy_price) > 0:
                self._buy_price = float(current_buy_price)
                self._buy_line = self.ax.axhline(y=self._buy_price, linewidth=1.5, color="purple", alpha=0.95, picker=5)
        except Exception:
            pass

        try:
            if current_sell_price is not None and float(current_sell_price) > 0:
                self._sell_price = float(current_sell_price)
                self._sell_line = self.ax.axhline(y=self._sell_price, linewidth=1.5, color="teal", alpha=0.95, picker=5)
        except Exception:
            pass

        # Right-side price labels (so you can read Bid/Ask/DCA/Sell at a glance)
        try:
            trans = blended_transform_factory(self.ax.transAxes, self.ax.transData)
            used_y: List[float] = []
            y0, y1 = self.ax.get_ylim()
            y_pad = max((y1 - y0) * 0.012, 1e-9)

            def _label_right(y: Optional[float], tag: str, color: str) -> None:
                if y is None:
                    return
                try:
                    yy = float(y)
                    if (not math.isfinite(yy)) or yy <= 0:
                        return
                except Exception:
                    return

                # Nudge labels apart if levels are very close
                for prev in used_y:
                    if abs(yy - prev) < y_pad:
                        yy = prev + y_pad
                used_y.append(yy)

                self.ax.text(
                    1.01,
                    yy,
                    f"{tag} {_fmt_price(yy)}",
                    transform=trans,
                    ha="left",
                    va="center",
                    fontsize=8,
                    color=color,
                    bbox=dict(
                        facecolor=DARK_BG2,
                        edgecolor=color,
                        boxstyle="round,pad=0.18",
                        alpha=0.85,
                    ),
                    zorder=20,
                    clip_on=False,
                )



            # Map to your terminology: Ask=buy line, Bid=sell line
            _label_right(current_buy_price, "ASK", "purple")
            _label_right(current_sell_price, "BID", "teal")
            _label_right(dca_line_price, "DCA", "red")
            _label_right(trail_line, "SELL", "green")
        except Exception:
            pass



        # --- Trade dots (BUY / DCA / SELL) for THIS coin only ---
        try:
            trades = _read_trade_history_jsonl(self.trade_history_path) if self.trade_history_path else []
            if trades:
                candle_ts = [int(c["ts"]) for c in candles]  # oldest->newest
                t_min = float(candle_ts[0])
                t_max = float(candle_ts[-1])

                for tr in trades:
                    sym = str(tr.get("symbol", "")).upper()
                    base = sym.split("-")[0].strip() if sym else ""
                    if base != self.coin.upper().strip():
                        continue

                    side = str(tr.get("side", "")).lower().strip()
                    tag = str(tr.get("tag") or "").upper().strip()

                    if side == "buy":
                        label = "DCA" if tag == "DCA" else "BUY"
                        color = "purple" if tag == "DCA" else "red"
                    elif side == "sell":
                        label = "SELL"
                        color = "green"
                    else:
                        continue

                    tts = tr.get("ts", None)
                    if tts is None:
                        continue
                    try:
                        tts = float(tts)
                    except Exception:
                        continue
                    if tts < t_min or tts > t_max:
                        continue

                    i = bisect.bisect_left(candle_ts, tts)
                    if i <= 0:
                        idx = 0
                    elif i >= len(candle_ts):
                        idx = len(candle_ts) - 1
                    else:
                        idx = i if abs(candle_ts[i] - tts) < abs(tts - candle_ts[i - 1]) else (i - 1)

                    # y = trade price if present, else candle close
                    y = None
                    try:
                        p = tr.get("price", None)
                        if p is not None and float(p) > 0:
                            y = float(p)
                    except Exception:
                        y = None
                    if y is None:
                        try:
                            y = float(candles[idx].get("close", 0.0))
                        except Exception:
                            y = None
                    if y is None:
                        continue

                    x = idx
                    self.ax.scatter([x], [y], s=35, color=color, zorder=6)
                    self.ax.annotate(
                        label,
                        (x, y),
                        textcoords="offset points",
                        xytext=(0, 10),
                        ha="center",
                        fontsize=8,
                        color=DARK_FG,
                        zorder=7,
                    )
        except Exception:
            pass


        self.ax.set_xlim(-0.5, (len(candles) - 0.5) + 0.6)

        self.ax.set_title(f"{self.coin} ({tf})", color=DARK_FG)



        # x tick labels (date + time) - evenly spaced, never overlapping duplicates
        n = len(candles)
        want = 5  # keep it readable even when the window is narrow
        if n <= want:
            idxs = list(range(n))
        else:
            step = (n - 1) / float(want - 1)
            idxs = []
            last = -1
            for j in range(want):
                i = int(round(j * step))
                if i <= last:
                    i = last + 1
                if i >= n:
                    i = n - 1
                idxs.append(i)
                last = i

        tick_x = [xs[i] for i in idxs]
        tick_lbl = [
            time.strftime("%Y-%m-%d\n%H:%M", time.localtime(int(candles[i].get("ts", 0))))
            for i in idxs
        ]

        try:
            self.ax.minorticks_off()
            self.ax.set_xticks(tick_x)
            self.ax.set_xticklabels(tick_lbl)
            self.ax.tick_params(axis="x", labelsize=8)
        except Exception:
            pass


        self.canvas.draw_idle()


        # Build descriptive status with signal levels and line counts
        long_count = len(long_levels)
        short_count = len(short_levels)
        status_text = f"Neural: LONG={long_sig} ({long_count} lines) | SHORT={short_sig} ({short_count} lines)"
        if long_count > 0 or short_count > 0 or self._buy_line is not None or self._sell_line is not None:
            status_text += " | Drag blue/orange/purple/teal lines to adjust"
        self.neural_status_label.config(text=status_text)

        # show file update time if possible
        last_ts = None
        try:
            if os.path.isfile(low_path):
                last_ts = os.path.getmtime(low_path)
            elif os.path.isfile(high_path):
                last_ts = os.path.getmtime(high_path)
        except Exception:
            last_ts = None

        if last_ts:
            self.last_update_label.config(text=f"Last: {time.strftime('%H:%M:%S', time.localtime(last_ts))}")
        else:
            self.last_update_label.config(text="Last: N/A")

    def _tk_on_mouse_press(self, event):
        """Tkinter mouse press handler - converts to matplotlib coordinates."""
        print(f"[TK PRESS] Event received: x={event.x}, y={event.y}, widget={event.widget}")
        try:
            # Convert Tkinter coordinates to matplotlib display coordinates
            # event.x, event.y are relative to canvas widget
            display_x = event.x
            display_y = self.canvas.get_tk_widget().winfo_height() - event.y
            
            # Convert display coordinates to data coordinates
            inv = self.ax.transData.inverted()
            x_data, y_data = inv.transform((display_x, display_y))
            
            # Check if click is inside axes
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            if not (xlim[0] <= x_data <= xlim[1] and ylim[0] <= y_data <= ylim[1]):
                return
            
            # Calculate tolerance
            y_range = ylim[1] - ylim[0]
            tolerance = y_range * 0.05
            
            print(f"[TK Mouse Press] y_data={y_data:.2f}, checking {len(self._neural_lines_long)} long, {len(self._neural_lines_short)} short")
            
            # Check trail line (green - trailing PM sell)
            if self._trail_line is not None and self._trail_price is not None:
                if abs(y_data - self._trail_price) < tolerance:
                    self._dragging_line = self._trail_line
                    self._dragging_type = 'trail'
                    self._drag_original_price = self._trail_price
                    self._trail_line.set_linewidth(3)
                    self._trail_line.set_alpha(1.0)
                    self._trail_line.set_color('lime')
                    self.canvas_widget.config(cursor="sb_v_double_arrow")
                    self.canvas.draw_idle()
                    print(f"Started dragging TRAIL line at {self._trail_price:.2f}")
                    return
            
            # Check DCA line (red)
            if self._dca_line is not None and self._dca_price is not None:
                if abs(y_data - self._dca_price) < tolerance:
                    self._dragging_line = self._dca_line
                    self._dragging_type = 'dca'
                    self._drag_original_price = self._dca_price
                    self._dca_line.set_linewidth(3)
                    self._dca_line.set_alpha(1.0)
                    self._dca_line.set_color('salmon')
                    self.canvas_widget.config(cursor="sb_v_double_arrow")
                    self.canvas.draw_idle()
                    print(f"Started dragging DCA line at {self._dca_price:.2f}")
                    return
            
            # Check buy line (purple)
            if self._buy_line is not None and self._buy_price is not None:
                if abs(y_data - self._buy_price) < tolerance:
                    self._dragging_line = self._buy_line
                    self._dragging_type = 'buy'
                    self._drag_original_price = self._buy_price
                    self._buy_line.set_linewidth(3)
                    self._buy_line.set_alpha(1.0)
                    self._buy_line.set_color('magenta')
                    self.canvas_widget.config(cursor="sb_v_double_arrow")
                    self.canvas.draw_idle()
                    print(f"Started dragging BUY line at {self._buy_price:.2f}")
                    return
            
            # Check sell line (teal)
            if self._sell_line is not None and self._sell_price is not None:
                if abs(y_data - self._sell_price) < tolerance:
                    self._dragging_line = self._sell_line
                    self._dragging_type = 'sell'
                    self._drag_original_price = self._sell_price
                    self._sell_line.set_linewidth(3)
                    self._sell_line.set_alpha(1.0)
                    self._sell_line.set_color('aqua')
                    self.canvas_widget.config(cursor="sb_v_double_arrow")
                    self.canvas.draw_idle()
                    print(f"Started dragging SELL line at {self._sell_price:.2f}")
                    return
            
            # Check long lines
            for line, price in self._neural_lines_long:
                if abs(y_data - price) < tolerance:
                    self._dragging_line = line
                    self._dragging_type = 'long'
                    self._drag_original_price = price
                    line.set_linewidth(3)
                    line.set_alpha(1.0)
                    line.set_color('cyan')
                    # Set dragging cursor
                    self.canvas_widget.config(cursor="sb_v_double_arrow")
                    self.canvas.draw_idle()
                    print(f"Started dragging LONG line at {price:.2f}")
                    return
            
            # Check short lines
            for line, price in self._neural_lines_short:
                if abs(y_data - price) < tolerance:
                    self._dragging_line = line
                    self._dragging_type = 'short'
                    self._drag_original_price = price
                    line.set_linewidth(3)
                    line.set_alpha(1.0)
                    line.set_color('yellow')
                    # Set dragging cursor
                    self.canvas_widget.config(cursor="sb_v_double_arrow")
                    self.canvas.draw_idle()
                    print(f"Started dragging SHORT line at {price:.2f}")
                    return
        except Exception as e:
            print(f"Error in mouse press: {e}")
    
    def _tk_on_mouse_move(self, event):
        """Tkinter mouse move handler for dragging."""
        if self._dragging_line is None:
            return
        
        try:
            display_x = event.x
            display_y = self.canvas.get_tk_widget().winfo_height() - event.y
            
            inv = self.ax.transData.inverted()
            x_data, y_data = inv.transform((display_x, display_y))
            
            # Update line position
            self._dragging_line.set_ydata([y_data, y_data])
            self.canvas.draw_idle()
        except Exception as e:
            print(f"Error in mouse move: {e}")
    
    def _tk_on_mouse_release(self, event):
        """Tkinter mouse release handler to save changes."""
        if self._dragging_line is None:
            return
        
        try:
            new_price = float(self._dragging_line.get_ydata()[0])
            
            if self._dragging_type == 'trail':
                self._trail_price = new_price
                self._save_trading_line_price(new_price, line_type='trail')
                self._dragging_line.set_linewidth(1.5)
                self._dragging_line.set_alpha(0.95)
                self._dragging_line.set_color('green')
                print(f"TRAIL (sell) price adjusted: {self._drag_original_price:.2f} -> {new_price:.2f}")
            elif self._dragging_type == 'dca':
                self._dca_price = new_price
                self._save_trading_line_price(new_price, line_type='dca')
                self._dragging_line.set_linewidth(1.5)
                self._dragging_line.set_alpha(0.95)
                self._dragging_line.set_color('red')
                print(f"DCA price adjusted: {self._drag_original_price:.2f} -> {new_price:.2f}")
            elif self._dragging_type == 'buy':
                self._buy_price = new_price
                self._save_trading_line_price(new_price, line_type='buy')
                self._dragging_line.set_linewidth(1.5)
                self._dragging_line.set_alpha(0.95)
                self._dragging_line.set_color('purple')
                print(f"BUY price adjusted: {self._drag_original_price:.2f} -> {new_price:.2f}")
            elif self._dragging_type == 'sell':
                self._sell_price = new_price
                self._save_trading_line_price(new_price, line_type='sell')
                self._dragging_line.set_linewidth(1.5)
                self._dragging_line.set_alpha(0.95)
                self._dragging_line.set_color('teal')
                print(f"SELL price adjusted: {self._drag_original_price:.2f} -> {new_price:.2f}")
            elif self._dragging_type == 'long':
                for i, (line, price) in enumerate(self._neural_lines_long):
                    if line == self._dragging_line:
                        self._neural_lines_long[i] = (line, new_price)
                        break
                prices = sorted([p for _, p in self._neural_lines_long], reverse=True)
                self._save_neural_levels(prices, is_long=True)
                self._dragging_line.set_linewidth(1)
                self._dragging_line.set_alpha(0.8)
                self._dragging_line.set_color('blue')
                print(f"LONG level saved: {self._drag_original_price:.2f} -> {new_price:.2f}")
            elif self._dragging_type == 'short':
                for i, (line, price) in enumerate(self._neural_lines_short):
                    if line == self._dragging_line:
                        self._neural_lines_short[i] = (line, new_price)
                        break
                prices = sorted([p for _, p in self._neural_lines_short])
                self._save_neural_levels(prices, is_long=False)
                self._dragging_line.set_linewidth(1)
                self._dragging_line.set_alpha(0.8)
                self._dragging_line.set_color('orange')
                print(f"SHORT level saved: {self._drag_original_price:.2f} -> {new_price:.2f}")
        except Exception as e:
            print(f"Error in mouse release: {e}")
        finally:
            # Reset cursor
            self.canvas_widget.config(cursor="")
            self._dragging_line = None
            self._dragging_is_long = None
            self._dragging_type = None
            self._drag_original_price = None
            self.canvas.draw_idle()
    
    def _tk_on_hover(self, event):
        """Tkinter hover handler to show tooltip and change cursor."""
        if self._dragging_line is not None:
            return
        
        try:
            display_x = event.x
            display_y = self.canvas.get_tk_widget().winfo_height() - event.y
            
            inv = self.ax.transData.inverted()
            x_data, y_data = inv.transform((display_x, display_y))
            
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            if not (xlim[0] <= x_data <= xlim[1] and ylim[0] <= y_data <= ylim[1]):
                if self._hover_text is not None:
                    self._hover_text.remove()
                    self._hover_text = None
                    self.canvas.draw_idle()
                # Reset cursor
                self.canvas_widget.config(cursor="")
                return
            
            y_range = ylim[1] - ylim[0]
            tolerance = y_range * 0.05
            
            hovered_price = None
            hovered_type = None
            
            # Check trail line (green)
            if self._trail_line is not None and self._trail_price is not None:
                if abs(y_data - self._trail_price) < tolerance:
                    hovered_price = self._trail_price
                    hovered_type = "TRAIL/SELL"
            
            # Check DCA line (red)
            if hovered_price is None and self._dca_line is not None and self._dca_price is not None:
                if abs(y_data - self._dca_price) < tolerance:
                    hovered_price = self._dca_price
                    hovered_type = "DCA"
            
            # Check buy line
            if hovered_price is None and self._buy_line is not None and self._buy_price is not None:
                if abs(y_data - self._buy_price) < tolerance:
                    hovered_price = self._buy_price
                    hovered_type = "BUY"
            
            # Check sell line
            if hovered_price is None and self._sell_line is not None and self._sell_price is not None:
                if abs(y_data - self._sell_price) < tolerance:
                    hovered_price = self._sell_price
                    hovered_type = "SELL"
            
            # Check neural lines
            if hovered_price is None:
                for line, price in self._neural_lines_long:
                    if abs(y_data - price) < tolerance:
                        hovered_price = price
                        hovered_type = "LONG"
                        break
            
            if hovered_price is None:
                for line, price in self._neural_lines_short:
                    if abs(y_data - price) < tolerance:
                        hovered_price = price
                        hovered_type = "SHORT"
                        break
            
            if hovered_price is not None:
                # Change cursor to indicate draggability
                self.canvas_widget.config(cursor="sb_v_double_arrow")
                
                if self._hover_text is not None:
                    self._hover_text.remove()
                self._hover_text = self.ax.text(
                    0.02, 0.98,
                    f"Drag to move {hovered_type} level: {hovered_price:.3f}",
                    transform=self.ax.transAxes,
                    fontsize=9,
                    color=DARK_ACCENT,
                    bbox=dict(boxstyle='round', facecolor=DARK_PANEL, alpha=0.9, edgecolor=DARK_ACCENT),
                    verticalalignment='top',
                    zorder=1000
                )
                self.canvas.draw_idle()
            else:
                # Reset cursor when not hovering over a line
                self.canvas_widget.config(cursor="")
                
                if self._hover_text is not None:
                    self._hover_text.remove()
                    self._hover_text = None
                    self.canvas.draw_idle()
        except Exception:
            pass

    def _on_mouse_press(self, event):
        """Handle mouse press to start dragging a neural level line."""
        print(f"[Mouse Press] button={event.button}, inaxes={event.inaxes==self.ax}, x={event.x}, y={event.y}, ydata={event.ydata}")
        
        if event.inaxes != self.ax or event.button != 1:
            return
        
        y = event.ydata
        if y is None:
            return
        
        # Calculate tolerance in data units (5% of y-axis range)
        y_range = self.ax.get_ylim()[1] - self.ax.get_ylim()[0]
        tolerance = y_range * 0.05
        
        print(f"[Mouse Press] Checking {len(self._neural_lines_long)} long lines, {len(self._neural_lines_short)} short lines, tolerance={tolerance:.2f}")
        
        # Check if click is near any long level line (blue)
        for line, price in self._neural_lines_long:
            if abs(y - price) < tolerance:
                self._dragging_line = line
                self._dragging_is_long = True
                self._drag_original_price = price
                line.set_linewidth(3)
                line.set_alpha(1.0)
                line.set_color('cyan')  # Change to cyan while dragging
                self.canvas.draw_idle()
                print(f"[Mouse Press] Started dragging LONG line at {price:.2f}")
                return
        
        # Check if click is near any short level line (orange)
        for line, price in self._neural_lines_short:
            if abs(y - price) < tolerance:
                self._dragging_line = line
                self._dragging_is_long = False
                self._drag_original_price = price
                line.set_linewidth(3)
                line.set_alpha(1.0)
                line.set_color('yellow')  # Change to yellow while dragging
                self.canvas.draw_idle()
                print(f"[Mouse Press] Started dragging SHORT line at {price:.2f}")
                return
    
    def _on_mouse_move(self, event):
        """Handle mouse move to drag the selected line or show hover indicator."""
        # If dragging, update line position
        if self._dragging_line is not None:
            if event.inaxes != self.ax:
                return
            
            y = event.ydata
            if y is None:
                return
            
            self._dragging_line.set_ydata([y, y])
            self.canvas.draw_idle()
            return
        
        # If not dragging, show hover effect when near a line
        if event.inaxes != self.ax:
            # Remove hover indicator if we leave the axes
            if self._hover_text is not None:
                try:
                    self._hover_text.remove()
                    self._hover_text = None
                    self.canvas.draw_idle()
                except Exception:
                    pass
            return
        
        y = event.ydata
        if y is None:
            return
        
        # Calculate tolerance
        y_range = self.ax.get_ylim()[1] - self.ax.get_ylim()[0]
        tolerance = y_range * 0.05
        
        # Check if hovering near any neural line
        hovered_price = None
        hovered_type = None
        
        for line, price in self._neural_lines_long:
            if abs(y - price) < tolerance:
                hovered_price = price
                hovered_type = "LONG"
                break
        
        if hovered_price is None:
            for line, price in self._neural_lines_short:
                if abs(y - price) < tolerance:
                    hovered_price = price
                    hovered_type = "SHORT"
                    break
        
        # Update hover indicator
        if hovered_price is not None:
            if self._hover_text is not None:
                try:
                    self._hover_text.remove()
                except Exception:
                    pass
            try:
                self._hover_text = self.ax.text(
                    0.02, 0.98, 
                    f"Click & drag to move {hovered_type} level: ${hovered_price:.2f}",
                    transform=self.ax.transAxes,
                    fontsize=9,
                    color=DARK_ACCENT,
                    bbox=dict(boxstyle='round', facecolor=DARK_PANEL, alpha=0.9, edgecolor=DARK_ACCENT),
                    verticalalignment='top',
                    zorder=1000
                )
                self.canvas.draw_idle()
            except Exception:
                pass
        else:
            # Remove hover indicator if not near any line
            if self._hover_text is not None:
                try:
                    self._hover_text.remove()
                    self._hover_text = None
                    self.canvas.draw_idle()
                except Exception:
                    pass
    
    def _on_mouse_release(self, event):
        """Handle mouse release to finalize the drag and save new level."""
        if self._dragging_line is None:
            return
        
        try:
            # Get new price value
            new_price = float(self._dragging_line.get_ydata()[0])
            
            # Find and update the price in the appropriate list
            if self._dragging_is_long:
                for i, (line, price) in enumerate(self._neural_lines_long):
                    if line == self._dragging_line:
                        self._neural_lines_long[i] = (line, new_price)
                        break
                # Save updated long levels
                prices = sorted([p for _, p in self._neural_lines_long], reverse=True)
                self._save_neural_levels(prices, is_long=True)
                # Restore line appearance
                self._dragging_line.set_linewidth(1)
                self._dragging_line.set_alpha(0.8)
                self._dragging_line.set_color('blue')
            else:
                for i, (line, price) in enumerate(self._neural_lines_short):
                    if line == self._dragging_line:
                        self._neural_lines_short[i] = (line, new_price)
                        break
                # Save updated short levels
                prices = sorted([p for _, p in self._neural_lines_short])
                self._save_neural_levels(prices, is_long=False)
                # Restore line appearance
                self._dragging_line.set_linewidth(1)
                self._dragging_line.set_alpha(0.8)
                self._dragging_line.set_color('orange')
            
            print(f"Neural level adjusted: {'LONG' if self._dragging_is_long else 'SHORT'} {self._drag_original_price:.2f} -> {new_price:.2f}")
        except Exception as e:
            print(f"Error saving neural level: {e}")
        finally:
            self._dragging_line = None
            self._dragging_is_long = None
            self._drag_original_price = None
            self.canvas.draw_idle()
    
    def _save_trading_line_price(self, price, line_type='buy'):
        """Save adjusted trading line price override to coin folder.
        
        Args:
            price: The new price value
            line_type: 'buy', 'sell', 'trail', or 'dca'
        """
        if not self._current_folder:
            return
        
        try:
            filename_map = {
                'buy': 'manual_buy_price.txt',
                'sell': 'manual_sell_price.txt',
                'trail': 'manual_trail_price.txt',
                'dca': 'manual_dca_price.txt'
            }
            filename = filename_map.get(line_type, 'manual_price.txt')
            path = os.path.join(self._current_folder, filename)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(str(price))
            
            print(f"Saved manual {line_type.upper()} price override: ${price:.2f}")
        except Exception as e:
            print(f"Error writing {line_type} price override: {e}")
    
    def _save_neural_levels(self, prices, is_long=True):
        """Save adjusted neural levels back to the HTML files and update signal count."""
        if not self._current_folder:
            return
        
        try:
            market_dir = os.path.join(self._current_folder, ".market")
            os.makedirs(market_dir, exist_ok=True)
            
            filename = "low_bound_prices.html" if is_long else "high_bound_prices.html"
            path = os.path.join(market_dir, filename)
            
            # Write prices as space-separated values (matching pt_thinker format)
            with open(path, "w", encoding="utf-8") as f:
                f.write(" ".join([str(p) for p in prices]))
            
            print(f"Saved {'long' if is_long else 'short'} neural levels to {filename}: {len(prices)} levels")
            
            # Also update the signal count file to match the number of price levels
            # The signal represents how many levels are active (capped at 7 for display)
            signal_count = min(len(prices), 7)
            signal_filename = "long_dca_signal.txt" if is_long else "short_dca_signal.txt"
            signal_path = os.path.join(market_dir, signal_filename)
            
            with open(signal_path, "w", encoding="utf-8") as f:
                f.write(str(signal_count))
            
            print(f"Updated {'long' if is_long else 'short'} signal to {signal_count}")
            
            # Notify parent hub to refresh the neural overview tiles
            try:
                widget = self
                while widget:
                    if hasattr(widget, '_refresh_neural_overview') and callable(getattr(widget, '_refresh_neural_overview', None)):
                        widget._refresh_neural_overview()
                        print(f"Triggered neural overview refresh")
                        break
                    widget = widget.master if hasattr(widget, 'master') else None
            except Exception as e:
                print(f"Note: Could not trigger neural overview refresh: {e}")
                
        except Exception as e:
            print(f"Error writing neural levels file: {e}")


# -----------------------------
# Account Value chart widget
# -----------------------------

class AccountValueChart(ttk.Frame):
    def __init__(self, parent: tk.Widget, history_path: str, trade_history_path: str, max_points: int = 250):
        super().__init__(parent)
        self.history_path = history_path
        self.trade_history_path = trade_history_path
        # Hard-cap to 250 points max (account value chart only)
        self.max_points = min(int(max_points or 0) or 250, 250)
        self._last_mtime: Optional[float] = None


        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)

        ttk.Label(top, text="Account value").pack(side="left")
        self.last_update_label = ttk.Label(top, text="Last: N/A")
        self.last_update_label.pack(side="right")

        self.fig = Figure(figsize=(6.5 * CHART_SCALE, 3.5 * CHART_SCALE), dpi=100)
        self.fig.patch.set_facecolor(DARK_BG)

        # Use tighter margins so the plot fills the available widget area while
        # still leaving room for x-tick labels and a small right margin for price labels.
        self.fig.subplots_adjust(left=0.06, right=0.88, bottom=0.12, top=0.95)

        self.ax = self.fig.add_subplot(111)
        self._apply_dark_chart_style()
        self.ax.set_title("Account Value", color=DARK_FG)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg=DARK_BG)

        # Remove horizontal padding here so the chart widget truly fills the container.
        self.canvas_widget.pack(fill="both", expand=True, padx=0, pady=(0, 6))

        # Keep the matplotlib figure EXACTLY the same pixel size as the Tk widget.
        # FigureCanvasTkAgg already sizes its backing PhotoImage to e.width/e.height.
        # Multiplying by tk scaling here makes the renderer larger than the PhotoImage,
        # which produces the "blank/covered strip" on the right.
        self._last_canvas_px = (0, 0)
        self._resize_after_id = None

        def _on_canvas_configure(e):
            try:
                w = int(e.width)
                h = int(e.height)
                if w <= 1 or h <= 1:
                    return

                if (w, h) == self._last_canvas_px:
                    return
                self._last_canvas_px = (w, h)

                dpi = float(self.fig.get_dpi() or 100.0)
                self.fig.set_size_inches(w / dpi, h / dpi, forward=True)

                # Debounce redraws during live resize
                if self._resize_after_id:
                    try:
                        self.after_cancel(self._resize_after_id)
                    except Exception:
                        pass
                self._resize_after_id = self.after_idle(self.canvas.draw_idle)
            except Exception:
                pass

        self.canvas_widget.bind("<Configure>", _on_canvas_configure, add="+")








    def _apply_dark_chart_style(self) -> None:
        try:
            self.fig.patch.set_facecolor(DARK_BG)
            self.ax.set_facecolor(DARK_PANEL)
            self.ax.tick_params(colors=DARK_FG)
            for spine in self.ax.spines.values():
                spine.set_color(DARK_BORDER)
            self.ax.grid(True, color=DARK_BORDER, linewidth=0.6, alpha=0.35)
        except Exception:
            pass

    def refresh(self) -> None:
        path = self.history_path

        # mtime cache so we don't redraw if nothing changed (account history OR trade history)
        try:
            m_hist = os.path.getmtime(path)
        except Exception:
            m_hist = None

        try:
            m_trades = os.path.getmtime(self.trade_history_path) if self.trade_history_path else None
        except Exception:
            m_trades = None

        candidates = [m for m in (m_hist, m_trades) if m is not None]
        mtime = max(candidates) if candidates else None

        if mtime is not None and self._last_mtime == mtime:
            return
        self._last_mtime = mtime


        points: List[Tuple[float, float]] = []

        try:
            if os.path.isfile(path):
                # Read the FULL history so the chart shows from the very beginning
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()

                for ln in lines:
                    try:
                        obj = json.loads(ln)
                        ts = obj.get("ts", None)
                        v = obj.get("total_account_value", None)
                        if ts is None or v is None:
                            continue

                        tsf = float(ts)
                        vf = float(v)

                        # Drop obviously invalid points early
                        if (not math.isfinite(tsf)) or (not math.isfinite(vf)) or (vf <= 0.0):
                            continue

                        points.append((tsf, vf))
                    except Exception:
                        continue
        except Exception:
            points = []

        # ---- Clean up history so single-tick bogus dips/spikes don't render ----
        if points:
            # Ensure chronological order
            points.sort(key=lambda x: x[0])

            # De-dupe identical timestamps (keep the latest occurrence)
            dedup: List[Tuple[float, float]] = []
            for tsf, vf in points:
                if dedup and tsf == dedup[-1][0]:
                    dedup[-1] = (tsf, vf)
                else:
                    dedup.append((tsf, vf))
            points = dedup


        # Downsample to <= 250 points by AVERAGING buckets instead of skipping points.
        # This keeps the chart visually stable when new nearby values arrive.
        max_keep = min(max(2, int(self.max_points or 250)), 250)
        n = len(points)

        if n > max_keep:
            bucket_size = n / float(max_keep)
            new_points: List[Tuple[float, float]] = []

            for i in range(max_keep):
                start = int(i * bucket_size)
                end = int((i + 1) * bucket_size)
                if end <= start:
                    end = start + 1
                if start >= n:
                    break
                if end > n:
                    end = n

                bucket = points[start:end]
                if not bucket:
                    continue

                # Average timestamp and account value within the bucket
                avg_ts = sum(p[0] for p in bucket) / len(bucket)
                avg_val = sum(p[1] for p in bucket) / len(bucket)

                new_points.append((avg_ts, avg_val))

            points = new_points


        # clear artists (fast) / fallback to cla()
        try:
            self.ax.lines.clear()
            self.ax.patches.clear()
            self.ax.collections.clear()  # scatter dots live here
            self.ax.texts.clear()        # labels/annotations live here
        except Exception:
            self.ax.cla()
            self._apply_dark_chart_style()


        if not points:
            self.ax.set_title("Account Value - no data", color=DARK_FG)
            self.last_update_label.config(text="Last: N/A")
            self.canvas.draw_idle()
            return

        xs = list(range(len(points)))
        # Only show cent-level changes (hide sub-cent noise)
        ys = [round(p[1], 2) for p in points]

        self.ax.plot(xs, ys, linewidth=1.5)

        # --- Trade dots (BUY / DCA / SELL) for ALL coins ---
        try:
            trades = _read_trade_history_jsonl(self.trade_history_path) if self.trade_history_path else []
            if trades:
                ts_list = [float(p[0]) for p in points]  # matches xs/ys indices
                t_min = ts_list[0]
                t_max = ts_list[-1]

                for tr in trades:
                    # Determine label/color
                    side = str(tr.get("side", "")).lower().strip()
                    tag = str(tr.get("tag", "")).upper().strip()

                    if side == "buy":
                        action_label = "DCA" if tag == "DCA" else "BUY"
                        color = "purple" if tag == "DCA" else "red"
                    elif side == "sell":
                        action_label = "SELL"
                        color = "green"
                    else:
                        continue

                    # Prefix with coin (so the dot says which coin it is)
                    sym = str(tr.get("symbol", "")).upper().strip()
                    coin_tag = (sym.split("-")[0].split("/")[0].strip() if sym else "") or (sym or "?")
                    label = f"{coin_tag} {action_label}"

                    tts = tr.get("ts")
                    try:
                        tts = float(tts or 0.0)
                    except Exception:
                        continue
                    if tts < t_min or tts > t_max:
                        continue

                    # nearest account-value point
                    i = bisect.bisect_left(ts_list, tts)
                    if i <= 0:
                        idx = 0
                    elif i >= len(ts_list):
                        idx = len(ts_list) - 1
                    else:
                        idx = i if abs(ts_list[i] - tts) < abs(tts - ts_list[i - 1]) else (i - 1)

                    x = idx
                    y = ys[idx]

                    self.ax.scatter([x], [y], s=30, color=color, zorder=6)
                    self.ax.annotate(
                        label,
                        (x, y),
                        textcoords="offset points",
                        xytext=(0, 10),
                        ha="center",
                        fontsize=8,
                        color=DARK_FG,
                        zorder=7,
                    )

        except Exception:
            pass

        # Force 2 decimals on the y-axis labels (account value chart only)
        try:
            self.ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _pos: f"${y:,.2f}"))
        except Exception:
            pass


        # x labels: show a few timestamps (date + time) - evenly spaced, never overlapping duplicates
        n = len(points)
        want = 5
        if n <= want:
            idxs = list(range(n))
        else:
            step = (n - 1) / float(want - 1)
            idxs = []
            last = -1
            for j in range(want):
                i = int(round(j * step))
                if i <= last:
                    i = last + 1
                if i >= n:
                    i = n - 1
                idxs.append(i)
                last = i

        tick_x = [xs[i] for i in idxs]
        tick_lbl = [time.strftime("%Y-%m-%d\n%H:%M:%S", time.localtime(points[i][0])) for i in idxs]
        try:
            self.ax.minorticks_off()
            self.ax.set_xticks(tick_x)
            self.ax.set_xticklabels(tick_lbl)
            self.ax.tick_params(axis="x", labelsize=8)
        except Exception:
            pass





        self.ax.set_xlim(-0.5, (len(points) - 0.5) + 0.6)

        try:
            last_value = ys[-1]
            if last_value < 0:
                # Use red color for deficit warning in chart title
                title_text = f"Account Value ({_fmt_money(last_value)}) "
                self.ax.set_title(title_text, color=DARK_FG)
                # Add red warning text above the title
                self.ax.text(0.5, 1.02, "***Deficit**", 
                           transform=self.ax.transAxes, ha='center', va='bottom',
                           color='red', fontsize=10, weight='bold')
                self.ax.set_title(title_text.strip(), color=DARK_FG)
            else:
                title_text = f"Account Value ({_fmt_money(last_value)})"
                self.ax.set_title(title_text, color=DARK_FG)
        except Exception:
            self.ax.set_title("Account Value", color=DARK_FG)

        try:
            self.last_update_label.config(
                text=f"Last: {time.strftime('%H:%M:%S', time.localtime(points[-1][0]))}"
            )
        except Exception:
            self.last_update_label.config(text="Last: N/A")

        self.canvas.draw_idle()



# -----------------------------
# Hub App
# -----------------------------

@dataclass
class ProcInfo:
    name: str
    path: str
    proc: Optional[subprocess.Popen] = None
    start_time: Optional[float] = None



@dataclass
class LogProc:
    """
    A running process with a live log queue for stdout/stderr lines.
    """
    info: ProcInfo
    log_q: "queue.Queue[str]"
    thread: Optional[threading.Thread] = None
    is_trainer: bool = False
    coin: Optional[str] = None



class PowerTraderHub(tk.Tk):
    def __init__(self):
        super().__init__(className="powertraderai")
        
        # Set window title (will be updated based on dry_run_mode)
        self._base_title = "Power Trader AI"
        self.title(self._base_title)
        
        # CRITICAL for Wayland/Dash to Dock: Set WM_CLASS immediately
        # Use simple lowercase no-hyphen format for best Wayland compatibility
        try:
            self.wm_class("powertraderai", "powertraderai")
        except Exception:
            pass
        
        # Set icon name
        try:
            self.wm_iconname("Power Trader AI")
        except Exception:
            pass
        
        # Wayland-specific window properties
        try:
            self.attributes('-type', 'normal')
        except Exception:
            pass
        
        try:
            self.overrideredirect(False)
        except Exception:
            pass
        
        try:
            self.transient(None)
        except Exception:
            pass
        
        try:
            self.protocol("WM_DELETE_WINDOW", self.quit)
        except Exception:
            pass
        
        # CRITICAL: Force window properties to be sent to compositor
        try:
            self.update_idletasks()
            self.update()
        except Exception:
            pass
        
        self.geometry("1400x820")

        # Set window icon from PNG file
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "PowerTrader.png")
            if os.path.exists(icon_path):
                icon = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, icon)
                # Keep reference to prevent garbage collection
                self._icon = icon
        except Exception as e:
            print(f"Could not load icon: {e}")

        # Hard minimum window size so the UI can't be shrunk to a point where panes vanish.
        # (Keeps things usable even if someone aggressively resizes.)
        self.minsize(980, 640)

        # Debounce map for panedwindow clamp operations
        self._paned_clamp_after_ids: Dict[str, str] = {}

        # Force one and only one theme: dark mode everywhere.
        self._apply_forced_dark_mode()

        self.settings = self._load_settings()

        # Snapshot of last-saved sash positions so we can detect changes
        try:
            self._last_saved_sashes = dict(self.settings.get("pane_sashes", {}) or {})
        except Exception:
            self._last_saved_sashes = {}

        # Restore saved window geometry if present
        try:
            geom = self.settings.get("window_geometry")
            if isinstance(geom, str) and geom:
                try:
                    self.geometry(geom)
                except Exception:
                    pass
        except Exception:
            pass
        
        # Start maximized (not fullscreen) to allow OS window manager shortcuts
        try:
            self.state('zoomed')  # Works on Windows/Linux
        except Exception:
            try:
                # Fallback for some Linux window managers
                self.attributes('-zoomed', True)
            except Exception:
                pass
        
        # Bind F11 to toggle fullscreen and Escape to exit fullscreen
        self.bind('<F11>', lambda e: self.attributes('-fullscreen', not self.attributes('-fullscreen')))
        self.bind('<Escape>', lambda e: self.attributes('-fullscreen', False))

        self.project_dir = os.path.abspath(os.path.dirname(__file__))

        # hub data dir
        hub_dir = self.settings.get("hub_data_dir") or os.path.join(self.project_dir, "hub_data")
        self.hub_dir = os.path.abspath(hub_dir)
        _ensure_dir(self.hub_dir)

        # file paths written by pt_trader.py (after edits below)
        self.trader_status_path = os.path.join(self.hub_dir, "trader_status.json")
        self.trade_history_path = os.path.join(self.hub_dir, "trade_history.jsonl")
        self.pnl_ledger_path = os.path.join(self.hub_dir, "pnl_ledger.json")
        self.account_value_history_path = os.path.join(self.hub_dir, "account_value_history.jsonl")
        
        # Ensure trade_history.jsonl exists (create empty file if missing)
        try:
            if not os.path.isfile(self.trade_history_path):
                with open(self.trade_history_path, "w", encoding="utf-8") as f:
                    pass  # Create empty file
        except Exception:
            pass

        # file written by pt_thinker.py (runner readiness gate used for Start All)
        self.runner_ready_path = os.path.join(self.hub_dir, "runner_ready.json")


        # internal: when Start All is pressed, we start the runner first and only start the trader once ready
        self._auto_start_trader_pending = False
        
        # internal: when Start All is pressed before training, auto-start runner after training completes
        self._auto_start_runner_after_training = False


        # cache latest trader status so charts can overlay buy/sell lines
        self._last_positions: Dict[str, dict] = {}

        # account value chart widget (created in _build_layout)
        self.account_chart = None



        # coin folders (neural outputs)
        self.coins = [c.upper().strip() for c in self.settings["coins"]]

        # On startup (like on Settings-save), create missing alt folders and copy the trainer into them.
        self._ensure_alt_coin_folders_and_trainer_on_startup()

        # Rebuild folder map after potential folder creation
        self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)

        # Ensure initial trainer status files exist for each coin (default NOT_TRAINED)
        try:
            for coin in self.coins:
                try:
                    coin_u = (coin or "").strip().upper()
                    folder = self.coin_folders.get(coin_u) or self.coin_folders.get(coin) or self.project_dir
                    if not folder:
                        continue
                    status_path = os.path.join(folder, "trainer_status.json")
                    if not os.path.isfile(status_path):
                        st = {"state": "NOT_TRAINED"}
                        try:
                            os.makedirs(folder, exist_ok=True)
                        except Exception:
                            pass
                        try:
                            with open(status_path, "w", encoding="utf-8") as f:
                                json.dump(st, f)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        # Normalize stray TRAINING states left from previous runs: if a status file
        # claims "TRAINING" but no trainer is actually running in this GUI session,
        # default it to NOT_TRAINED so BTC doesn't incorrectly show as training.
        try:
            for coin in self.coins:
                try:
                    coin_u = (coin or "").strip().upper()
                    folder = self.coin_folders.get(coin_u) or self.project_dir
                    status_path = os.path.join(folder, "trainer_status.json")
                    st = _safe_read_json(status_path)
                    if isinstance(st, dict) and str(st.get("state", "")).upper() == "TRAINING":
                        try:
                            _safe_write_json(status_path, {"state": "NOT_TRAINED"})
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass


        # scripts
        self.proc_neural = ProcInfo(
            name="Neural Runner",
            path=os.path.abspath(os.path.join(self.project_dir, self.settings["script_neural_runner2"]))
        )
        self.proc_trader = ProcInfo(
            name="Trader",
            path=os.path.abspath(os.path.join(self.project_dir, self.settings["script_trader"]))
        )

        self.proc_trainer_path = os.path.abspath(os.path.join(self.project_dir, self.settings["script_neural_trainer"]))

        # live log queues
        self.runner_log_q: "queue.Queue[str]" = queue.Queue()
        self.trader_log_q: "queue.Queue[str]" = queue.Queue()

        # trainers: coin -> LogProc
        self.trainers: Dict[str, LogProc] = {}

        self.fetcher = CandleFetcher()


        self.fetcher = CandleFetcher()

        self._build_menu()
        self._build_layout()

        # Refresh charts immediately when a timeframe is changed (don't wait for the 10s throttle).
        self.bind_all("<<TimeframeChanged>>", self._on_timeframe_changed)
        
        # Refresh charts immediately when neural level bars are dragged
        self.bind_all("<<NeuralLevelChanged>>", self._on_neural_level_changed)

        self._last_chart_refresh = 0.0

        # Poll Robinhood account balance on startup if API is enabled
        self._poll_initial_account_balance()

        if bool(self.settings.get("auto_start_scripts", False)):
            self.start_all_scripts()

        # F11 toggles maximize/fullscreen for convenience
        try:
            self.bind("<F11>", lambda _e: self._toggle_maximize())
        except Exception:
            pass

        self.after(250, self._tick)

        self.protocol("WM_DELETE_WINDOW", self._on_close)


    # ---- forced dark mode ----

    def _apply_forced_dark_mode(self) -> None:
        """Force a single, global, non-optional dark theme."""
        # Root background (handles the areas behind ttk widgets)
        try:
            self.configure(bg=DARK_BG)
        except Exception:
            pass

        # Defaults for classic Tk widgets (Text/Listbox/Menu) created later
        try:
            self.option_add("*Text.background", DARK_PANEL)
            self.option_add("*Text.foreground", DARK_FG)
            self.option_add("*Text.insertBackground", DARK_FG)
            self.option_add("*Text.selectBackground", DARK_SELECT_BG)
            self.option_add("*Text.selectForeground", DARK_SELECT_FG)

            self.option_add("*Listbox.background", DARK_PANEL)
            self.option_add("*Listbox.foreground", DARK_FG)
            self.option_add("*Listbox.selectBackground", DARK_SELECT_BG)
            self.option_add("*Listbox.selectForeground", DARK_SELECT_FG)

            self.option_add("*Menu.background", DARK_BG2)
            self.option_add("*Menu.foreground", DARK_FG)
            self.option_add("*Menu.activeBackground", DARK_SELECT_BG)
            self.option_add("*Menu.activeForeground", DARK_SELECT_FG)
        except Exception:
            pass

        style = ttk.Style(self)

        # Pick a theme that is actually recolorable (Windows 'vista' theme ignores many color configs)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Base defaults
        try:
            style.configure(".", background=DARK_BG, foreground=DARK_FG)
        except Exception:
            pass

        # Containers / text
        for name in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton"):
            try:
                style.configure(name, background=DARK_BG, foreground=DARK_FG)
            except Exception:
                pass

        try:
            style.configure("TLabelframe", background=DARK_BG, foreground=DARK_FG, bordercolor=DARK_BORDER)
            style.configure("TLabelframe.Label", background=DARK_BG, foreground=DARK_ACCENT)
        except Exception:
            pass

        try:
            style.configure("TSeparator", background=DARK_BORDER)
        except Exception:
            pass

        # Buttons
        try:
            style.configure(
                "TButton",
                background=DARK_BG2,
                foreground=DARK_FG,
                bordercolor=DARK_BORDER,
                focusthickness=1,
                focuscolor=DARK_ACCENT,
                padding=(10, 6),
            )
            style.map(
                "TButton",
                background=[
                    ("active", DARK_PANEL2),
                    ("pressed", DARK_PANEL),
                    ("disabled", DARK_BG2),
                ],
                foreground=[
                    ("active", DARK_ACCENT),
                    ("disabled", DARK_MUTED),
                ],
                bordercolor=[
                    ("active", DARK_ACCENT2),
                    ("focus", DARK_ACCENT),
                ],
            )
        except Exception:
            pass

        # Entries / combos
        try:
            style.configure(
                "TEntry",
                fieldbackground=DARK_PANEL,
                foreground=DARK_FG,
                bordercolor=DARK_BORDER,
                insertcolor=DARK_FG,
            )
        except Exception:
            pass

        try:
            style.configure(
                "TCombobox",
                fieldbackground=DARK_PANEL,
                background=DARK_PANEL,
                foreground=DARK_FG,
                bordercolor=DARK_BORDER,
                arrowcolor=DARK_ACCENT,
            )
            style.map(
                "TCombobox",
                fieldbackground=[
                    ("readonly", DARK_PANEL),
                    ("focus", DARK_PANEL2),
                ],
                foreground=[("readonly", DARK_FG)],
                background=[("readonly", DARK_PANEL)],
            )
        except Exception:
            pass

        # Notebooks
        try:
            style.configure("TNotebook", background=DARK_BG, bordercolor=DARK_BORDER)
            style.configure("TNotebook.Tab", background=DARK_BG2, foreground=DARK_FG, padding=(10, 6))
            style.map(
                "TNotebook.Tab",
                background=[
                    ("selected", DARK_PANEL),
                    ("active", DARK_PANEL2),
                ],
                foreground=[
                    ("selected", DARK_ACCENT),
                    ("active", DARK_ACCENT2),
                ],
            )

            # Charts tabs need to wrap to multiple lines. ttk.Notebook can't do that,
            # so we hide the Notebook's native tabs and render our own wrapping tab bar.
            #
            # IMPORTANT: the layout must exclude Notebook.tab entirely, and on some themes
            # you must keep Notebook.padding for proper sizing; otherwise the tab strip
            # can still render.
            style.configure("HiddenTabs.TNotebook", tabmargins=0)
            style.layout(
                "HiddenTabs.TNotebook",
                [
                    (
                        "Notebook.padding",
                        {
                            "sticky": "nswe",
                            "children": [
                                ("Notebook.client", {"sticky": "nswe"}),
                            ],
                        },
                    )
                ],
            )

            # Wrapping chart-tab buttons (normal + selected)
            style.configure(
                "ChartTab.TButton",
                background=DARK_BG2,
                foreground=DARK_FG,
                bordercolor=DARK_BORDER,
                padding=(10, 6),
            )
            style.map(
                "ChartTab.TButton",
                background=[("active", DARK_PANEL2), ("pressed", DARK_PANEL)],
                foreground=[("active", DARK_ACCENT2)],
                bordercolor=[("active", DARK_ACCENT2), ("focus", DARK_ACCENT)],
            )

            style.configure(
                "ChartTabSelected.TButton",
                background=DARK_PANEL,
                foreground=DARK_ACCENT,
                bordercolor=DARK_ACCENT2,
                padding=(10, 6),
            )
        except Exception:
            pass


        # Treeview (Current Trades table)
        try:
            style.configure(
                "Treeview",
                background=DARK_PANEL,
                fieldbackground=DARK_PANEL,
                foreground=DARK_FG,
                bordercolor=DARK_BORDER,
                lightcolor=DARK_BORDER,
                darkcolor=DARK_BORDER,
            )
            style.map(
                "Treeview",
                background=[("selected", DARK_SELECT_BG)],
                foreground=[("selected", DARK_SELECT_FG)],
            )

            style.configure("Treeview.Heading", background=DARK_BG2, foreground=DARK_ACCENT, relief="flat")
            style.map(
                "Treeview.Heading",
                background=[("active", DARK_PANEL2)],
                foreground=[("active", DARK_ACCENT2)],
            )
        except Exception:
            pass

        # Panedwindows / scrollbars
        try:
            style.configure("TPanedwindow", background=DARK_BG)
        except Exception:
            pass

        for sb in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            try:
                style.configure(
                    sb,
                    background=DARK_BG2,
                    troughcolor=DARK_BG,
                    bordercolor=DARK_BORDER,
                    arrowcolor=DARK_ACCENT,
                )
            except Exception:
                pass

    # ---- settings ----

    def _load_settings(self) -> dict:
        data = _safe_read_json(SETTINGS_FILE)
        if not isinstance(data, dict):
            data = {}

        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        # normalize
        merged["coins"] = [c.upper().strip() for c in merged.get("coins", [])]
        
        # Initialize default long/short sell prices on first boot (with 2% margin)
        self._initialize_coin_prices_if_needed(merged)
        
        return merged
    
    def _initialize_coin_prices_if_needed(self, settings: dict) -> None:
        """Initialize long/short sell prices with 2% margin if not already set."""
        if "coin_long_sell_prices" not in settings:
            settings["coin_long_sell_prices"] = {}
        if "coin_short_sell_prices" not in settings:
            settings["coin_short_sell_prices"] = {}
        
        long_prices = settings["coin_long_sell_prices"]
        short_prices = settings["coin_short_sell_prices"]
        coins = settings.get("coins", [])
        
        needs_save = False
        
        for coin in coins:
            coin_upper = coin.upper().strip()
            
            # Skip if already has both prices set
            if coin_upper in long_prices and coin_upper in short_prices:
                continue
            
            # Try to read current price from file
            price_file = os.path.join(self.project_dir if hasattr(self, 'project_dir') else os.path.dirname(__file__), 
                                     f"{coin_upper}_current_price.txt")
            
            current_price = None
            try:
                if os.path.isfile(price_file):
                    with open(price_file, "r", encoding="utf-8") as f:
                        current_price = float((f.read() or "").strip())
            except Exception:
                pass
            
            # Set defaults with 2% margin if we have a price
            if current_price and current_price > 0:
                if coin_upper not in long_prices:
                    # Long sell: 2% above current price
                    long_prices[coin_upper] = round(current_price * 1.02, 8)
                    needs_save = True
                
                if coin_upper not in short_prices:
                    # Short sell: 2% below current price
                    short_prices[coin_upper] = round(current_price * 0.98, 8)
                    needs_save = True
        
        # Save settings if we added any defaults
        if needs_save:
            try:
                _safe_write_json(SETTINGS_FILE, settings)
            except Exception:
                pass

    def _save_settings(self) -> None:
        _safe_write_json(SETTINGS_FILE, self.settings)
    
    def get_coin_long_sell_price(self, coin: str) -> Optional[float]:
        """Get the long sell price for a coin."""
        coin_upper = coin.upper().strip()
        return self.settings.get("coin_long_sell_prices", {}).get(coin_upper)
    
    def get_coin_short_sell_price(self, coin: str) -> Optional[float]:
        """Get the short sell price for a coin."""
        coin_upper = coin.upper().strip()
        return self.settings.get("coin_short_sell_prices", {}).get(coin_upper)
    
    def set_coin_long_sell_price(self, coin: str, price: float) -> None:
        """Set and persist the long sell price for a coin."""
        coin_upper = coin.upper().strip()
        if "coin_long_sell_prices" not in self.settings:
            self.settings["coin_long_sell_prices"] = {}
        self.settings["coin_long_sell_prices"][coin_upper] = float(price)
        self._save_settings()
    
    def set_coin_short_sell_price(self, coin: str, price: float) -> None:
        """Set and persist the short sell price for a coin."""
        coin_upper = coin.upper().strip()
        if "coin_short_sell_prices" not in self.settings:
            self.settings["coin_short_sell_prices"] = {}
        self.settings["coin_short_sell_prices"][coin_upper] = float(price)
        self._save_settings()

    def _poll_initial_account_balance(self) -> None:
        """Poll Robinhood account balance on startup if API is enabled and credentials exist."""
        try:
            # Check if Robinhood API is enabled
            if not self.settings.get("use_robinhood_api", False):
                return
            if not self.settings.get("exchange_robinhood_enabled", False):
                return
            
            # Check if credentials exist
            r_key_path = os.path.join(self.project_dir, "r_key.txt")
            r_secret_path = os.path.join(self.project_dir, "r_secret.txt")
            
            if not os.path.isfile(r_key_path) or not os.path.isfile(r_secret_path):
                return
            
            # Import necessary modules
            import base64
            import time
            import requests
            from nacl.signing import SigningKey
            
            # Read credentials
            with open(r_key_path, "r") as f:
                api_key = f.read().strip()
            with open(r_secret_path, "r") as f:
                base64_private_key = f.read().strip()
            
            if not api_key or not base64_private_key:
                return
            
            # Initialize signing key
            raw_private = base64.b64decode(base64_private_key)
            private_key = SigningKey(raw_private)
            
            # Make API request to get account
            base_url = "https://trading.robinhood.com"
            path = "/api/v1/crypto/trading/accounts/"
            method = "GET"
            timestamp = int(time.time())
            body = ""
            
            message_to_sign = f"{api_key}{timestamp}{path}{method}{body}"
            signed = private_key.sign(message_to_sign.encode("utf-8"))
            signature_b64 = base64.b64encode(signed.signature).decode("utf-8")
            
            headers = {
                "x-api-key": api_key,
                "x-timestamp": str(timestamp),
                "x-signature": signature_b64,
            }
            
            response = requests.get(f"{base_url}{path}", headers=headers, timeout=10)
            
            if response.status_code == 200:
                account = response.json()
                
                # Extract buying power (try multiple field names)
                buying_power = None
                if isinstance(account, dict):
                    if "results" in account and isinstance(account["results"], list) and len(account["results"]) > 0:
                        acct_data = account["results"][0]
                    else:
                        acct_data = account
                    
                    for field in ["buying_power", "cash", "cash_balance", "available_cash", "buying_power_amount"]:
                        if field in acct_data and acct_data[field] is not None:
                            buying_power = float(acct_data[field])
                            break
                
                # Update trader status file with initial balance
                if buying_power is not None:
                    status = {
                        "timestamp": time.time(),
                        "account": {
                            "total_account_value": buying_power,
                            "buying_power": buying_power,
                            "holdings_sell_value": 0.0,
                            "holdings_buy_value": 0.0,
                            "percent_in_trade": 0.0,
                            "pm_start_pct_no_dca": 5.0,
                            "pm_start_pct_with_dca": 2.5,
                            "trailing_gap_pct": 0.5,
                        },
                        "positions": {},
                    }
                    _safe_write_json(self.trader_status_path, status)
        except Exception:
            # Silently fail - don't interrupt startup if API check fails
            pass

    def _on_close(self) -> None:
        """Close the application and save window size and layout."""
        try:
            # Save current window geometry
            geom = self.geometry()
            if geom:
                self.settings["window_geometry"] = geom
            
            # Save pane sash positions
            s = self.settings.setdefault("pane_sashes", {})
            if hasattr(self, "_pw_outer") and self._pw_outer:
                try:
                    s["outer"] = int(self._pw_outer.sashpos(0))
                except Exception:
                    pass
            if hasattr(self, "_pw_left_split") and self._pw_left_split:
                try:
                    s["left_split"] = int(self._pw_left_split.sashpos(0))
                except Exception:
                    pass
            if hasattr(self, "_pw_right_split") and self._pw_right_split:
                try:
                    s["right_split"] = int(self._pw_right_split.sashpos(0))
                except Exception:
                    pass
            if hasattr(self, "_pw_right_bottom_split") and self._pw_right_bottom_split:
                try:
                    s["right_bottom_split"] = int(self._pw_right_bottom_split.sashpos(0))
                except Exception:
                    pass
            
            # Save to disk
            self._save_settings()
        except Exception:
            pass
        
        # Stop all running scripts before closing
        try:
            self.stop_all_scripts()
        except Exception:
            pass
        
        self.destroy()

    def _open_readme(self) -> None:
        """Open the README.md in the user's default application."""
        readme_path = Path(__file__).parent / "README.md"
        
        if not readme_path.exists():
            messagebox.showerror(
                "File Not Found",
                f"README not found at:\n{readme_path}\n\n"
                "Please ensure README.md exists in the application directory."
            )
            return
        
        try:
            import platform
            import subprocess
            
            system = platform.system()
            if system == "Windows":
                os.startfile(str(readme_path))
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(readme_path)], check=True)
            else:  # Linux and others
                subprocess.run(["xdg-open", str(readme_path)], check=True)
        except Exception as e:
            messagebox.showerror(
                "Error Opening File",
                f"Could not open README.md:\n{e}\n\n"
                f"Please open manually: {readme_path}"
            )

    def _open_trading_guide(self) -> None:
        """Open the Trading101.md guide in the user's default application."""
        guide_path = Path(__file__).parent / "Trading101.md"
        
        if not guide_path.exists():
            messagebox.showerror(
                "File Not Found",
                f"Trading guide not found at:\n{guide_path}\n\n"
                "Please ensure Trading101.md exists in the application directory."
            )
            return
        
        try:
            import platform
            import subprocess
            
            system = platform.system()
            if system == "Windows":
                os.startfile(str(guide_path))
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(guide_path)], check=True)
            else:  # Linux and others
                subprocess.run(["xdg-open", str(guide_path)], check=True)
        except Exception as e:
            messagebox.showerror(
                "Error Opening File",
                f"Could not open Trading101.md:\n{e}\n\n"
                f"Please open manually: {guide_path}"
            )

    def _open_resize_dialog(self) -> None:
        """Opens a dialog to resize the main window."""
        dialog = tk.Toplevel(self)
        dialog.title("Resize Window")
        dialog.transient(self)
        dialog.resizable(False, False)
        
        # Configure dark mode styling for the dialog
        dialog.configure(bg=DARK_BG2)
        
        # Parse current geometry
        current_geom = self.geometry()
        # Format: WIDTHxHEIGHT+X+Y
        try:
            size_part, *pos_parts = current_geom.split('+')
            width_str, height_str = size_part.split('x')
            current_width = int(width_str)
            current_height = int(height_str)
        except Exception:
            current_width = 1400
            current_height = 820
        
        # Create dialog content
        frame = ttk.Frame(dialog, style="Dark.TFrame")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Width field
        ttk.Label(
            frame,
            text="Width:",
            style="Dark.TLabel"
        ).grid(row=0, column=0, sticky="w", pady=5)
        
        width_var = tk.StringVar(value=str(current_width))
        width_entry = ttk.Entry(
            frame,
            textvariable=width_var,
            width=10,
            style="Dark.TEntry"
        )
        width_entry.grid(row=0, column=1, pady=5, padx=(10, 0), sticky="ew")
        
        ttk.Label(
            frame,
            text="px",
            style="Dark.TLabel"
        ).grid(row=0, column=2, sticky="w", padx=(5, 0), pady=5)
        
        # Height field
        ttk.Label(
            frame,
            text="Height:",
            style="Dark.TLabel"
        ).grid(row=1, column=0, sticky="w", pady=5)
        
        height_var = tk.StringVar(value=str(current_height))
        height_entry = ttk.Entry(
            frame,
            textvariable=height_var,
            width=10,
            style="Dark.TEntry"
        )
        height_entry.grid(row=1, column=1, pady=5, padx=(10, 0), sticky="ew")
        
        ttk.Label(
            frame,
            text="px",
            style="Dark.TLabel"
        ).grid(row=1, column=2, sticky="w", padx=(5, 0), pady=5)
        
        # Preset buttons frame
        preset_frame = ttk.Frame(frame, style="Dark.TFrame")
        preset_frame.grid(row=2, column=0, columnspan=3, pady=(15, 10), sticky="ew")
        
        ttk.Label(
            preset_frame,
            text="Quick presets:",
            style="Dark.TLabel"
        ).pack(anchor="w", pady=(0, 5))
        
        presets = [
            ("1280x720", 1280, 720),
            ("1400x820", 1400, 820),
            ("1600x900", 1600, 900),
            ("1920x1080", 1920, 1080),
        ]
        
        preset_btn_frame = ttk.Frame(preset_frame, style="Dark.TFrame")
        preset_btn_frame.pack(fill="x")
        
        for i, (label, w, h) in enumerate(presets):
            btn = ttk.Button(
                preset_btn_frame,
                text=label,
                style="Dark.TButton",
                command=lambda w=w, h=h: (width_var.set(str(w)), height_var.set(str(h)))
            )
            btn.pack(side="left", padx=(0, 5) if i < len(presets)-1 else 0)
        
        # Buttons frame
        btn_frame = ttk.Frame(frame, style="Dark.TFrame")
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0), sticky="e")
        
        def apply_size():
            try:
                new_width = int(width_var.get())
                new_height = int(height_var.get())
                
                # Validate reasonable bounds
                if new_width < 800:
                    error_msg = (
                        f"Width validation failed\n\n"
                        f"Entered value: {new_width} px\n"
                        f"Minimum required: 800 px\n\n"
                        f"Please enter a width of at least 800 pixels."
                    )
                    messagebox.showwarning("Invalid Size", error_msg, parent=dialog)
                    return
                if new_height < 600:
                    error_msg = (
                        f"Height validation failed\n\n"
                        f"Entered value: {new_height} px\n"
                        f"Minimum required: 600 px\n\n"
                        f"Please enter a height of at least 600 pixels."
                    )
                    messagebox.showwarning("Invalid Size", error_msg, parent=dialog)
                    return
                if new_width > 4000 or new_height > 4000:
                    error_msg = (
                        f"Dimension validation failed\n\n"
                        f"Entered dimensions: {new_width} x {new_height} px\n"
                        f"Maximum allowed: 4000 x 4000 px\n\n"
                        f"Please enter dimensions less than 4000 pixels."
                    )
                    messagebox.showwarning("Invalid Size", error_msg, parent=dialog)
                    return
                
                # Apply new geometry (preserve position)
                current_geom = self.geometry()
                try:
                    size_part, *pos_parts = current_geom.split('+')
                    if len(pos_parts) >= 2:
                        new_geom = f"{new_width}x{new_height}+{pos_parts[0]}+{pos_parts[1]}"
                    else:
                        new_geom = f"{new_width}x{new_height}"
                except Exception:
                    new_geom = f"{new_width}x{new_height}"
                
                self.geometry(new_geom)
                
                # Update settings
                self.settings["window_geometry"] = new_geom
                _safe_write_json(SETTINGS_FILE, self.settings)
                
                dialog.destroy()
                messagebox.showinfo("Window Resized", f"Window size updated to {new_width}x{new_height}")
                
            except ValueError as e:
                error_msg = (
                    f"Invalid input format\n\n"
                    f"Width entered: {width_var.get()}\n"
                    f"Height entered: {height_var.get()}\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please enter valid numeric values for both width and height."
                )
                messagebox.showerror("Invalid Input", error_msg, parent=dialog)
            except Exception as e:
                error_msg = (
                    f"Failed to resize window\n\n"
                    f"Attempted size: {width_var.get()} x {height_var.get()}\n"
                    f"Current geometry: {self.geometry()}\n\n"
                    f"Error type: {type(e).__name__}\n"
                    f"Error details: {str(e)}\n\n"
                    f"Please try again or contact support with this error message."
                )
                messagebox.showerror("Error", error_msg, parent=dialog)
        
        ttk.Button(
            btn_frame,
            text="Apply",
            style="Dark.TButton",
            command=apply_size
        ).pack(side="left", padx=(0, 5))
        
        ttk.Button(
            btn_frame,
            text="Cancel",
            style="Dark.TButton",
            command=dialog.destroy
        ).pack(side="left")
        
        # Center the dialog on the main window
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Make dialog modal
        dialog.grab_set()
        width_entry.focus_set()
        width_entry.select_range(0, tk.END)

    def _save_layout_defaults(self) -> None:
        """Save current window geometry and pane sash positions into settings (without exiting)."""
        try:
            geom = None
            try:
                geom = self.geometry()
            except Exception:
                geom = None
            if geom:
                try:
                    self.settings["window_geometry"] = geom
                except Exception:
                    pass

            s = self.settings.setdefault("pane_sashes", {})
            try:
                if hasattr(self, "_pw_outer") and getattr(self, "_pw_outer"):
                    try:
                        s["outer"] = int(self._pw_outer.sashpos(0))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if hasattr(self, "_pw_left_split") and getattr(self, "_pw_left_split"):
                    try:
                        s["left_split"] = int(self._pw_left_split.sashpos(0))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if hasattr(self, "_pw_right_split") and getattr(self, "_pw_right_split"):
                    try:
                        s["right_split"] = int(self._pw_right_split.sashpos(0))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if hasattr(self, "_pw_right_bottom_split") and getattr(self, "_pw_right_bottom_split"):
                    try:
                        s["right_bottom_split"] = int(self._pw_right_bottom_split.sashpos(0))
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                self._save_settings()
                try:
                    messagebox.showinfo("Saved layout", "Saved current layout as the default.")
                except Exception:
                    pass
            except Exception:
                try:
                    messagebox.showerror("Save failed", "Couldn't save layout settings.")
                except Exception:
                    pass
        except Exception:
            try:
                messagebox.showerror("Save failed", "Couldn't save layout settings.")
            except Exception:
                pass

        try:
            self.destroy()
        except Exception:
            try:
                self.quit()
            except Exception:
                pass

    def _settings_getter(self) -> dict:
        return self.settings

    def _ensure_alt_coin_folders_and_trainer_on_startup(self) -> None:
        """
        Startup behavior (mirrors Settings-save behavior):
        - For every alt coin in the coin list that does NOT have its folder yet:
            - create the folder
            - copy neural_trainer.py from the MAIN (BTC) folder into the new folder
        """
        try:
            coins = [str(c).strip().upper() for c in (self.settings.get("coins") or []) if str(c).strip()]
            main_dir = Path(self.settings.get("main_neural_dir") or self.project_dir or os.getcwd())

            trainer_name = os.path.basename(str(self.settings.get("script_neural_trainer", "neural_trainer.py")))

            # Source trainer: MAIN folder (BTC folder)
            src_main_trainer = main_dir / trainer_name

            # Best-effort fallback if the main folder doesn't have it (keeps behavior robust)
            src_cfg_trainer = str(self.settings.get("script_neural_trainer", trainer_name))
            src_trainer_path = str(src_main_trainer) if src_main_trainer.is_file() else src_cfg_trainer

            for coin in coins:
                if coin == "BTC":
                    continue  # BTC uses main folder; no per-coin folder needed

                coin_dir = main_dir / coin

                created = False
                if not coin_dir.is_dir():
                    coin_dir.mkdir(parents=True, exist_ok=True)
                    created = True

                # Only copy into folders created at startup (per your request)
                if created:
                    dst_trainer_path = os.path.join(coin_dir, trainer_name)
                    if (not os.path.isfile(dst_trainer_path)) and os.path.isfile(src_trainer_path):
                        shutil.copy2(src_trainer_path, dst_trainer_path)
        except Exception:
            pass

    # ---- menu / layout ----


    def _build_menu(self) -> None:
        menubar = tk.Menu(
            self,
            bg=DARK_BG2,
            fg=DARK_FG,
            activebackground=DARK_SELECT_BG,
            activeforeground=DARK_SELECT_FG,
            bd=0,
            relief="flat",
        )

        m_file = tk.Menu(
            menubar,
            tearoff=0,
            bg=DARK_BG2,
            fg=DARK_FG,
            activebackground=DARK_SELECT_BG,
            activeforeground=DARK_SELECT_FG,
        )
        m_file.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=m_file)

        m_settings = tk.Menu(
            menubar,
            tearoff=0,
            bg=DARK_BG2,
            fg=DARK_FG,
            activebackground=DARK_SELECT_BG,
            activeforeground=DARK_SELECT_FG,
        )
        m_settings.add_command(label="Settings...", command=self.open_settings_dialog)
        menubar.add_cascade(label="Settings", menu=m_settings)

        m_scripts = tk.Menu(
            menubar,
            tearoff=0,
            bg=DARK_BG2,
            fg=DARK_FG,
            activebackground=DARK_SELECT_BG,
            activeforeground=DARK_SELECT_FG,
        )
        m_scripts.add_command(label="Start All", command=self.start_all_scripts)
        m_scripts.add_command(label="Stop All", command=self.stop_all_scripts)
        # Training-specific actions
        m_scripts.add_separator()
        m_scripts.add_command(label="Start All Training", command=self.train_all_coins)
        m_scripts.add_command(label="Stop All Training", command=self.stop_all_trainers)
        m_scripts.add_separator()
        m_scripts.add_command(label="Start Neural Runner", command=self.start_neural)
        m_scripts.add_command(label="Stop Neural Runner", command=self.stop_neural)
        m_scripts.add_separator()
        m_scripts.add_command(label="Start Trader", command=self.start_trader)
        m_scripts.add_command(label="Stop Trader", command=self.stop_trader)
        menubar.add_cascade(label="Scripts", menu=m_scripts)

        # Help menu
        m_help = tk.Menu(
            menubar,
            tearoff=0,
            bg=DARK_BG2,
            fg=DARK_FG,
            activebackground=DARK_SELECT_BG,
            activeforeground=DARK_SELECT_FG,
        )
        m_help.add_command(label="README", command=self._open_readme)
        m_help.add_command(label="How To Trade", command=self._open_trading_guide)
        menubar.add_cascade(label="Help", menu=m_help)

        # Layout menu removed - replaced with collapsible sections

        self.config(menu=menubar)

    def _toggle_dry_run_mode(self) -> None:
        """Toggle DRY RUN mode - uses saved trained models without requiring fresh training, and NO REAL TRADES."""
        enabled = self.dry_run_var.get()
        self.settings["dry_run_mode"] = enabled
        self._save_settings()
        
        # Update window title
        try:
            if enabled:
                self.title(f"⚠️ DRY RUN MODE ⚠️ - {self._base_title}")
            else:
                self.title(self._base_title)
        except Exception:
            pass
        
        # Update indicator label
        try:
            if enabled:
                self.lbl_dry_run_indicator.config(text="⚠ DRY RUN MODE: No real trades will execute")
            else:
                self.lbl_dry_run_indicator.config(text="")
        except Exception:
            pass
        if enabled:
            messagebox.showinfo(
                "DRY RUN Mode Enabled",
                "DRY RUN Mode is now ON.\n\n"
                "• Uses previously saved trained models without requiring fresh training\n"
                "• Neural Runner and Trader can start immediately if models exist\n"
                "• ⚠ NO REAL TRADES will be executed - testing mode only\n"
                "• All buy/sell signals will be logged but not sent to the exchange"
            )
        else:
            messagebox.showinfo(
                "DRY RUN Mode Disabled",
                "DRY RUN Mode is now OFF.\n\n"
                "Fresh training will be required before starting Neural Runner and Trader."
            )

    def _build_layout(self) -> None:
        outer = ttk.Panedwindow(self, orient="horizontal")
        outer.pack(fill="both", expand=True)

        # LEFT + RIGHT panes
        left = ttk.Frame(outer)
        right = ttk.Frame(outer)

        outer.add(left, weight=1)
        outer.add(right, weight=2)

        # Prevent the outer (left/right) panes from being collapsible to 0 width
        try:
            outer.paneconfigure(left, minsize=360)
            outer.paneconfigure(right, minsize=520)
        except Exception:
            pass

        # LEFT: vertical split (Controls, Live Output)
        left_split = ttk.Panedwindow(left, orient="vertical")
        left_split.pack(fill="both", expand=True, padx=8, pady=8)


        # RIGHT: vertical split (Charts on top, Trades+History underneath)
        right_split = ttk.Panedwindow(right, orient="vertical")
        right_split.pack(fill="both", expand=True, padx=8, pady=8)

        # Keep references so we can clamp sash positions later
        self._pw_outer = outer
        self._pw_left_split = left_split
        self._pw_right_split = right_split

        # Clamp panes when the user releases a sash or the window resizes
        outer.bind("<Configure>", lambda e: self._schedule_paned_clamp(self._pw_outer))
        outer.bind("<ButtonRelease-1>", lambda e: (
            setattr(self, "_user_moved_outer", True),
            self._schedule_paned_clamp(self._pw_outer),
            self._schedule_save_sashes(),
        ))

        left_split.bind("<Configure>", lambda e: self._schedule_paned_clamp(self._pw_left_split))
        left_split.bind("<ButtonRelease-1>", lambda e: (
            setattr(self, "_user_moved_left_split", True),
            self._schedule_paned_clamp(self._pw_left_split),
            self._schedule_save_sashes(),
            self._check_left_split_minimize(),
        ))

        right_split.bind("<Configure>", lambda e: self._schedule_paned_clamp(self._pw_right_split))
        right_split.bind("<ButtonRelease-1>", lambda e: (
            setattr(self, "_user_moved_right_split", True),
            self._schedule_paned_clamp(self._pw_right_split),
            self._schedule_save_sashes(),
        ))

        # Set a startup default width that matches the screenshot (so left has room for Neural Levels).
        def _init_outer_sash_once():
            try:
                if getattr(self, "_did_init_outer_sash", False):
                    return

                # If the user already moved it, never override it.
                if getattr(self, "_user_moved_outer", False):
                    self._did_init_outer_sash = True
                    return

                # If we saved a previous sash position, restore it now.
                try:
                    saved = self.settings.get("pane_sashes", {}).get("outer")
                    if isinstance(saved, int):
                        outer.sashpos(0, int(saved))
                        self._did_init_outer_sash = True
                        return
                except Exception:
                    pass

                total = outer.winfo_width()
                if total <= 2:
                    self.after(10, _init_outer_sash_once)
                    return

                min_left = 360
                min_right = 520
                desired_left = 470  # ~matches your screenshot
                target = max(min_left, min(total - min_right, desired_left))
                outer.sashpos(0, int(target))

                self._did_init_outer_sash = True
            except Exception:
                pass

        self.after_idle(_init_outer_sash_once)

        # Global safety: on some themes/platforms, the mouse events land on the sash element,
        # not the panedwindow widget, so the widget-level binds won't always fire.
        # NOTE: Only bind Button-1 (left click), NOT Button-4/Button-5 (Linux scroll wheel)
        self.bind_all("<ButtonRelease-1>", lambda e: (
            self._schedule_paned_clamp(getattr(self, "_pw_outer", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_left_split", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_right_split", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_right_bottom_split", None)),
            self._schedule_save_sashes(),
        ), add="+")


        # ----------------------------
        # LEFT: 1) Controls / Health (pane)
        # ----------------------------
        top_controls = ttk.LabelFrame(left_split, text="Controls / Health")

        # Training progress bar (at the very top)
        progress_frame = ttk.Frame(top_controls)
        progress_frame.pack(fill="x", expand=False, padx=6, pady=(6, 0))
        
        self.training_progress_label = ttk.Label(progress_frame, text="Training Progress: 0%")
        self.training_progress_label.pack(anchor="w", pady=(0, 2))
        
        self.training_progress = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            length=200,
            mode="determinate",
            maximum=100
        )
        self.training_progress.pack(fill="x", pady=(0, 6))
        self.training_progress["value"] = 0

        # Layout requirement:
        #   - Buttons (full width) ABOVE
        #   - Dual section BELOW:
        #       LEFT  = Status + Account + Profit
        #       RIGHT = Training
        buttons_bar = ttk.Frame(top_controls)
        buttons_bar.pack(fill="x", expand=False, padx=0, pady=0)

        info_row = ttk.Frame(top_controls)
        info_row.pack(fill="x", expand=False, padx=0, pady=0)

        # LEFT column (status + account/profit)
        controls_left = ttk.Frame(info_row)
        controls_left.pack(side="left", fill="both", expand=True)
        
        # DRY RUN toggle switch (prominent at top)
        dry_run_frame = ttk.LabelFrame(controls_left, text="⚠️ Trading Mode", padding=(6, 6))
        dry_run_frame.pack(fill="x", padx=6, pady=(6, 12))
        
        self.dry_run_var = tk.BooleanVar(value=bool(self.settings.get("dry_run_mode", False)))
        
        # Create toggle switch style button
        toggle_frame = ttk.Frame(dry_run_frame)
        toggle_frame.pack(fill="x")
        
        ttk.Label(toggle_frame, text="DRY RUN Mode:", font=("TkDefaultFont", 10, "bold")).pack(side="left", padx=(0, 10))
        
        dry_run_check = ttk.Checkbutton(
            toggle_frame,
            text="Testing (No Real Trades)",
            variable=self.dry_run_var,
            command=self._toggle_dry_run_mode,
            style="Switch.TCheckbutton"
        )
        dry_run_check.pack(side="left")
        
        # Initialize title based on current mode
        if self.dry_run_var.get():
            self.title(f"⚠️ DRY RUN MODE ⚠️ - {self._base_title}")
        else:
            self.title(self._base_title)

        # RIGHT column (training)
        training_section = ttk.LabelFrame(info_row, text="Training")
        training_section.pack(side="right", fill="both", expand=False, padx=6, pady=6)

        training_left = ttk.Frame(training_section)
        training_left.pack(side="left", fill="both", expand=True)

        # Train coin selector (so you can choose what "Train Selected" targets)
        train_row = ttk.Frame(training_left)
        train_row.pack(fill="x", padx=6, pady=(6, 0))

        self.train_coin_var = tk.StringVar(value=(self.coins[0] if self.coins else ""))
        ttk.Label(train_row, text="Train coin:").pack(side="left")
        self.train_coin_combo = ttk.Combobox(
            train_row,
            textvariable=self.train_coin_var,
            values=self.coins,
            width=8,
            state="readonly",
        )
        self.train_coin_combo.pack(side="left", padx=(6, 0))

        def _sync_train_coin(*_):
            try:
                # keep the Trainers tab dropdown in sync (if present)
                self.trainer_coin_var.set(self.train_coin_var.get())
            except Exception:
                pass

        self.train_coin_combo.bind("<<ComboboxSelected>>", _sync_train_coin)
        _sync_train_coin()



        # Fixed controls bar (stable layout; no wrapping/reflow on resize)
        # Wrapped in a scrollable canvas so buttons are never cut off when the window is resized.
        btn_scroll_wrap = ttk.Frame(buttons_bar)
        btn_scroll_wrap.pack(fill="x", expand=False, padx=6, pady=6)

        btn_canvas = tk.Canvas(btn_scroll_wrap, bg=DARK_BG, highlightthickness=0, bd=0, height=1)
        btn_scroll_y = ttk.Scrollbar(btn_scroll_wrap, orient="vertical", command=btn_canvas.yview)
        btn_scroll_x = ttk.Scrollbar(btn_scroll_wrap, orient="horizontal", command=btn_canvas.xview)
        btn_canvas.configure(yscrollcommand=btn_scroll_y.set, xscrollcommand=btn_scroll_x.set)


        btn_scroll_wrap.grid_columnconfigure(0, weight=1)
        btn_scroll_wrap.grid_rowconfigure(0, weight=0)

        btn_canvas.grid(row=0, column=0, sticky="ew")
        btn_scroll_y.grid(row=0, column=1, sticky="ns")
        btn_scroll_x.grid(row=1, column=0, sticky="ew")


        # Start hidden; we only show scrollbars when needed.
        btn_scroll_y.grid_remove()
        btn_scroll_x.grid_remove()

        btn_inner = ttk.Frame(btn_canvas)
        _btn_inner_id = btn_canvas.create_window((0, 0), window=btn_inner, anchor="nw")

        def _btn_update_scrollbars(event=None):
            try:
                # Always keep scrollregion accurate
                btn_canvas.configure(scrollregion=btn_canvas.bbox("all"))
                sr = btn_canvas.bbox("all")
                if not sr:
                    return

                # --- KEY FIX ---
                # Resize the canvas height to the buttons' requested height so there is no
                # dead/empty gap above the horizontal scrollbar.
                try:
                    desired_h = max(1, int(btn_inner.winfo_reqheight()))
                    cur_h = int(btn_canvas.cget("height") or 0)
                    if cur_h != desired_h:
                        btn_canvas.configure(height=desired_h)
                except Exception:
                    pass

                x0, y0, x1, y1 = sr
                cw = btn_canvas.winfo_width()
                ch = btn_canvas.winfo_height()

                need_x = (x1 - x0) > (cw + 1)
                need_y = (y1 - y0) > (ch + 1)

                if need_x:
                    btn_scroll_x.grid()
                else:
                    btn_scroll_x.grid_remove()
                    btn_canvas.xview_moveto(0)

                if need_y:
                    btn_scroll_y.grid()
                else:
                    btn_scroll_y.grid_remove()
                    btn_canvas.yview_moveto(0)
            except Exception:
                pass


        def _btn_canvas_on_configure(event=None):
            try:
                # Keep the inner window pinned to top-left
                btn_canvas.coords(_btn_inner_id, 0, 0)
            except Exception:
                pass
            _btn_update_scrollbars()

        btn_inner.bind("<Configure>", _btn_update_scrollbars)
        btn_canvas.bind("<Configure>", _btn_canvas_on_configure)

        # The original button layout (unchanged), placed inside the scrollable inner frame.
        btn_bar = ttk.Frame(btn_inner)
        btn_bar.pack(fill="x", expand=False)

        # Keep groups left-aligned; the spacer column absorbs extra width.
        btn_bar.grid_columnconfigure(0, weight=0)
        btn_bar.grid_columnconfigure(1, weight=0)
        btn_bar.grid_columnconfigure(2, weight=1)

        BTN_W = 14

        # (Start All button moved into the left-side info section above Account.)
        train_group = ttk.Frame(btn_bar)
        train_group.grid(row=0, column=0, sticky="w", padx=(0, 18), pady=(0, 6))


        # One more pass after layout so scrollbars reflect the true initial size.
        self.after_idle(_btn_update_scrollbars)






        self.lbl_neural = ttk.Label(controls_left, text="Neural: stopped")
        self.lbl_neural.pack(anchor="w", padx=6, pady=(0, 2))

        self.lbl_trader = ttk.Label(controls_left, text="Trader: stopped")
        self.lbl_trader.pack(anchor="w", padx=6, pady=(0, 6))

        # DRY RUN mode indicator (warning label when active)
        self.lbl_dry_run_indicator = ttk.Label(
            controls_left, 
            text="", 
            foreground="orange", 
            font=("TkDefaultFont", 9, "bold")
        )
        self.lbl_dry_run_indicator.pack(anchor="w", padx=6, pady=(0, 6))
        # Set initial state based on settings
        if self.settings.get("dry_run_mode", False):
            self.lbl_dry_run_indicator.config(text="⚠ DRY RUN MODE: No real trades will execute")

        self.lbl_last_status = ttk.Label(controls_left, text="Last status: N/A")
        self.lbl_last_status.pack(anchor="w", padx=6, pady=(0, 2))

        # Trader uptime (runtime) shown below last status
        self.lbl_trader_uptime = ttk.Label(controls_left, text="Trader uptime: N/A")
        self.lbl_trader_uptime.pack(anchor="w", padx=6, pady=(0, 6))


        # ----------------------------
        # Training section (everything training-specific lives here)
        # ----------------------------
        train_buttons_row = ttk.Frame(training_left)
        train_buttons_row.pack(fill="x", padx=6, pady=(6, 6))

        ttk.Button(train_buttons_row, text="Train Selected", command=self.train_selected_coin).pack(anchor="w", pady=(0, 2), fill="x")
        ttk.Button(train_buttons_row, text="Reset & Train Selected", command=self.reset_and_train_selected).pack(anchor="w", pady=(0, 6), fill="x")
        ttk.Button(train_buttons_row, text="Train All", command=self.train_all_coins).pack(anchor="w", pady=(0, 2), fill="x")
        ttk.Button(train_buttons_row, text="Reset & Train All", command=self.reset_and_train_all).pack(anchor="w", fill="x")

        # Training status (per-coin + gating reason)
        self.lbl_training_overview = ttk.Label(training_left, text="Training: N/A")
        self.lbl_training_overview.pack(anchor="w", padx=6, pady=(0, 2))

        self.lbl_flow_hint = ttk.Label(training_left, text="Flow: Train → Start All")
        self.lbl_flow_hint.pack(anchor="w", padx=6, pady=(0, 6))

        self.training_list = tk.Listbox(
            training_left,
            height=5,
            bg=DARK_PANEL,
            fg=DARK_FG,
            selectbackground=DARK_SELECT_BG,
            selectforeground=DARK_SELECT_FG,
            highlightbackground=DARK_BORDER,
            highlightcolor=DARK_ACCENT,
            activestyle="none",
        )
        self.training_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))


        # Start All (moved here: LEFT side of the dual section, directly above Account)
        start_all_row = ttk.Frame(controls_left)
        start_all_row.pack(fill="x", padx=6, pady=(0, 6))

        self.btn_start_all = ttk.Button(
            start_all_row,
            text="Start All",
            width=9,
            command=self.start_all_scripts,
        )
        self.btn_start_all.pack(side="left", padx=(0, 2))
        
        self.btn_stop_all = ttk.Button(
            start_all_row,
            text="Stop All",
            width=9,
            command=self.stop_all_scripts,
        )
        self.btn_stop_all.pack(side="left", padx=(2, 0))


        # Account info (LEFT column, under status) - Always visible
        acct_box = ttk.LabelFrame(controls_left, text="Account")
        acct_box.pack(fill="x", padx=6, pady=6)

        self.lbl_acct_total_value = ttk.Label(acct_box, text="Total Account Value: N/A")
        self.lbl_acct_total_value.pack(anchor="w", padx=6, pady=(2, 0))

        self.lbl_acct_holdings_value = ttk.Label(acct_box, text="Holdings Value: N/A")
        self.lbl_acct_holdings_value.pack(anchor="w", padx=6, pady=(2, 0))

        self.lbl_acct_buying_power = ttk.Label(acct_box, text="Buying Power: N/A")
        self.lbl_acct_buying_power.pack(anchor="w", padx=6, pady=(2, 0))

        self.lbl_acct_percent_in_trade = ttk.Label(acct_box, text="Percent In Trade: N/A")
        self.lbl_acct_percent_in_trade.pack(anchor="w", padx=6, pady=(2, 0))

        # DCA affordability
        self.lbl_acct_dca_spread = ttk.Label(acct_box, text="DCA Levels (spread): N/A")
        self.lbl_acct_dca_spread.pack(anchor="w", padx=6, pady=(2, 0))

        self.lbl_acct_dca_single = ttk.Label(acct_box, text="DCA Levels (single): N/A")
        self.lbl_acct_dca_single.pack(anchor="w", padx=6, pady=(2, 0))

        self.lbl_pnl = ttk.Label(acct_box, text="Total P&L: N/A")
        self.lbl_pnl.pack(anchor="w", padx=6, pady=(2, 2))



        # Neural levels overview (spans FULL width under the dual section) - Collapsible and larger
        # Shows the current LONG/SHORT level (0..7) for every coin at once.
        neural_header = ttk.Frame(top_controls)
        neural_header.pack(fill="x", padx=6, pady=(0, 0))
        
        self.neural_collapsed = tk.BooleanVar(value=False)
        self.neural_toggle_btn = ttk.Button(neural_header, text="▼ Neural Levels (0–7)", command=self._toggle_neural)
        self.neural_toggle_btn.pack(side="left", fill="x", expand=True)
        
        neural_box = ttk.Frame(top_controls)
        neural_box.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.neural_content = neural_box

        legend = ttk.Frame(neural_box)
        legend.pack(fill="x", padx=6, pady=(4, 0))

        ttk.Label(legend, text="Bars show signal strength (0-10) | Blue=Long | Orange=Short").pack(side="left")
        ttk.Label(legend, text="  •  ").pack(side="left")
        ttk.Label(legend, text="Hover bars for details | Drag to adjust").pack(side="left")

        self.lbl_neural_overview_last = ttk.Label(legend, text="Last: N/A")
        self.lbl_neural_overview_last.pack(side="right")

        # Scrollable area for tiles (auto-hides the scrollbar if everything fits)
        neural_viewport = ttk.Frame(neural_box)
        neural_viewport.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        neural_viewport.grid_rowconfigure(0, weight=1)
        neural_viewport.grid_columnconfigure(0, weight=1)

        self._neural_overview_canvas = tk.Canvas(
            neural_viewport,
            bg=DARK_PANEL2,
            highlightthickness=1,
            highlightbackground=DARK_BORDER,
            bd=0,
        )
        self._neural_overview_canvas.grid(row=0, column=0, sticky="nsew")

        # Horizontal scrollbar so tiles lay out left-to-right and remain accessible
        self._neural_overview_scroll = ttk.Scrollbar(
            neural_viewport,
            orient="horizontal",
            command=self._neural_overview_canvas.xview,
        )
        self._neural_overview_scroll.grid(row=1, column=0, sticky="ew")

        self._neural_overview_canvas.configure(xscrollcommand=self._neural_overview_scroll.set)

        self.neural_wrap = WrapFrame(self._neural_overview_canvas, orientation="horizontal")
        # For neural overview we prefer a single left-to-right row that scrolls
        # horizontally rather than wrapping into multiple rows.
        try:
            self.neural_wrap._nowrap = True
        except Exception:
            pass
        self._neural_overview_window = self._neural_overview_canvas.create_window(
            (0, 0),
            window=self.neural_wrap,
            anchor="nw",
        )

        def _update_neural_overview_scrollbars(event=None) -> None:
            """Update scrollregion + hide/show the scrollbar depending on overflow."""
            try:
                c = self._neural_overview_canvas
                win = self._neural_overview_window

                c.update_idletasks()
                bbox = c.bbox(win)
                if not bbox:
                    self._neural_overview_scroll.grid_remove()
                    return

                c.configure(scrollregion=bbox)
                content_w = int(bbox[2] - bbox[0])
                view_w = int(c.winfo_width())

                if content_w > (view_w + 1):
                    try:
                        self._neural_overview_scroll.grid()
                    except Exception:
                        pass
                else:
                    try:
                        self._neural_overview_scroll.grid_remove()
                        c.xview_moveto(0)
                    except Exception:
                        pass
            except Exception:
                pass

        def _on_neural_canvas_configure(e) -> None:
            # Keep the inner wrap frame exactly the canvas width so wrapping works.
            try:
                self._neural_overview_canvas.itemconfigure(self._neural_overview_window, width=int(e.width))
            except Exception:
                pass
            _update_neural_overview_scrollbars()

        self._neural_overview_canvas.bind("<Configure>", _on_neural_canvas_configure, add="+")
        self.neural_wrap.bind("<Configure>", _update_neural_overview_scrollbars, add="+")
        self._update_neural_overview_scrollbars = _update_neural_overview_scrollbars

        # Mousewheel scroll inside the tiles area
        def _wheel(e):
            try:
                if self._neural_overview_scroll.winfo_ismapped():
                    # Scroll horizontally with mouse wheel
                    delta = getattr(e, 'delta', 0)
                    if delta:
                        self._neural_overview_canvas.xview_scroll(int(-1 * (delta / 120)), "units")
                    else:
                        # Linux: Button-4 = scroll up (left), Button-5 = scroll down (right)
                        if e.num == 4:
                            self._neural_overview_canvas.xview_scroll(-1, "units")
                        elif e.num == 5:
                            self._neural_overview_canvas.xview_scroll(1, "units")
            except Exception:
                pass

        self._neural_overview_canvas.bind("<Enter>", lambda _e: self._neural_overview_canvas.focus_set(), add="+")
        self._neural_overview_canvas.bind("<MouseWheel>", _wheel, add="+")
        self._neural_overview_canvas.bind("<Button-4>", _wheel, add="+")  # Linux scroll left
        self._neural_overview_canvas.bind("<Button-5>", _wheel, add="+")  # Linux scroll right

        # tiles by coin
        self.neural_tiles: Dict[str, NeuralSignalTile] = {}
        # small cache: path -> (mtime, value)
        self._neural_overview_cache: Dict[str, Tuple[float, Any]] = {}

        self._rebuild_neural_overview()
        try:
            self.after_idle(self._update_neural_overview_scrollbars)
        except Exception:
            pass
        
        # Verify all coin tiles were created
        try:
            if len(self.neural_tiles) != len(self.coins):
                print(f"Warning: Neural tiles mismatch - expected {len(self.coins)}, got {len(self.neural_tiles)}")
        except Exception:
            pass








        # ----------------------------
        # LEFT: 3) Live Output (pane)
        # ----------------------------

        # Half-size fixed-width font for live logs (Runner/Trader/Trainers)
        _base = tkfont.nametofont("TkFixedFont")
        _half = max(6, int(round(abs(int(_base.cget("size"))) / 2.0)))
        self._live_log_font = _base.copy()
        self._live_log_font.configure(size=_half)

        logs_outer = ttk.Frame(left_split)
        
        logs_header = ttk.Frame(logs_outer)
        logs_header.pack(fill="x", padx=6, pady=(6, 0))
        
        self.logs_collapsed = tk.BooleanVar(value=False)
        self.logs_toggle_btn = ttk.Button(logs_header, text="▼ Live Output", command=self._toggle_logs)
        self.logs_toggle_btn.pack(side="left", fill="x", expand=True)
        
        logs_frame = ttk.Frame(logs_outer)
        logs_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.logs_content = logs_frame
        
        self.logs_nb = ttk.Notebook(logs_frame)
        self.logs_nb.pack(fill="both", expand=True)


        # Runner tab
        runner_tab = ttk.Frame(self.logs_nb)
        self.logs_nb.add(runner_tab, text="Runner")
        self.runner_text = tk.Text(
            runner_tab,
            height=8,
            wrap="none",
            font=self._live_log_font,
            bg=DARK_PANEL,
            fg=DARK_FG,
            insertbackground=DARK_FG,
            selectbackground=DARK_SELECT_BG,
            selectforeground=DARK_SELECT_FG,
            highlightbackground=DARK_BORDER,
            highlightcolor=DARK_ACCENT,
        )

        runner_scroll = ttk.Scrollbar(runner_tab, orient="vertical", command=self.runner_text.yview)
        self.runner_text.configure(yscrollcommand=runner_scroll.set)
        self.runner_text.pack(side="left", fill="both", expand=True)
        runner_scroll.pack(side="right", fill="y")

        # Trader tab
        trader_tab = ttk.Frame(self.logs_nb)
        self.logs_nb.add(trader_tab, text="Trader")
        self.trader_text = tk.Text(
            trader_tab,
            height=8,
            wrap="none",
            font=self._live_log_font,
            bg=DARK_PANEL,
            fg=DARK_FG,
            insertbackground=DARK_FG,
            selectbackground=DARK_SELECT_BG,
            selectforeground=DARK_SELECT_FG,
            highlightbackground=DARK_BORDER,
            highlightcolor=DARK_ACCENT,
        )

        trader_scroll = ttk.Scrollbar(trader_tab, orient="vertical", command=self.trader_text.yview)
        self.trader_text.configure(yscrollcommand=trader_scroll.set)
        self.trader_text.pack(side="left", fill="both", expand=True)
        trader_scroll.pack(side="right", fill="y")

        # Trainers tab (multi-coin)
        trainer_tab = ttk.Frame(self.logs_nb)
        self.logs_nb.add(trainer_tab, text="Trainers")

        top_bar = ttk.Frame(trainer_tab)
        top_bar.pack(fill="x", padx=6, pady=6)

        self.trainer_coin_var = tk.StringVar(value=(self.coins[0] if self.coins else "BTC"))
        ttk.Label(top_bar, text="Coin:").pack(side="left")
        self.trainer_coin_combo = ttk.Combobox(
            top_bar,
            textvariable=self.trainer_coin_var,
            values=self.coins,
            state="readonly",
            width=8
        )
        self.trainer_coin_combo.pack(side="left", padx=(6, 12))

        ttk.Button(top_bar, text="Start Trainer", command=self.start_trainer_for_selected_coin).pack(side="left")
        ttk.Button(top_bar, text="Stop Trainer", command=self.stop_trainer_for_selected_coin).pack(side="left", padx=(6, 0))

        self.trainer_status_lbl = ttk.Label(top_bar, text="(no trainers running)")
        self.trainer_status_lbl.pack(side="left", padx=(12, 0))

        self.trainer_text = tk.Text(
            trainer_tab,
            height=8,
            wrap="none",
            font=self._live_log_font,
            bg=DARK_PANEL,
            fg=DARK_FG,
            insertbackground=DARK_FG,
            selectbackground=DARK_SELECT_BG,
            selectforeground=DARK_SELECT_FG,
            highlightbackground=DARK_BORDER,
            highlightcolor=DARK_ACCENT,
        )

        trainer_scroll = ttk.Scrollbar(trainer_tab, orient="vertical", command=self.trainer_text.yview)
        self.trainer_text.configure(yscrollcommand=trainer_scroll.set)
        self.trainer_text.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=(0, 6))
        trainer_scroll.pack(side="right", fill="y", padx=(0, 6), pady=(0, 6))

        # Enable mousewheel scrolling for all text widgets
        def _on_mousewheel(event, text_widget):
            scroll_direction = -1 if event.delta > 0 else 1
            text_widget.yview_scroll(scroll_direction, "units")
            return "break"

        self.runner_text.bind("<MouseWheel>", lambda e: _on_mousewheel(e, self.runner_text))
        self.runner_text.bind("<Button-4>", lambda e: _on_mousewheel(e, self.runner_text))  # Linux scroll up
        self.runner_text.bind("<Button-5>", lambda e: _on_mousewheel(e, self.runner_text))  # Linux scroll down

        self.trader_text.bind("<MouseWheel>", lambda e: _on_mousewheel(e, self.trader_text))
        self.trader_text.bind("<Button-4>", lambda e: _on_mousewheel(e, self.trader_text))  # Linux scroll up
        self.trader_text.bind("<Button-5>", lambda e: _on_mousewheel(e, self.trader_text))  # Linux scroll down

        self.trainer_text.bind("<MouseWheel>", lambda e: _on_mousewheel(e, self.trainer_text))
        self.trainer_text.bind("<Button-4>", lambda e: _on_mousewheel(e, self.trainer_text))  # Linux scroll up
        self.trainer_text.bind("<Button-5>", lambda e: _on_mousewheel(e, self.trainer_text))  # Linux scroll down

        # Add left panes (no trades/history on the left anymore)
        # Neural Levels (top_controls) gets more weight to be larger
        left_split.add(top_controls, weight=3)
        left_split.add(logs_outer, weight=1)

        try:
            # Ensure the top pane can't start (or be clamped) too small to show Neural Levels.
            left_split.paneconfigure(top_controls, minsize=300)
            left_split.paneconfigure(logs_outer, minsize=250)
        except Exception:
            pass

        def _init_left_split_sash_once():
            try:
                if getattr(self, "_did_init_left_split_sash", False):
                    return

                # If the user already moved the sash, never override it.
                if getattr(self, "_user_moved_left_split", False):
                    self._did_init_left_split_sash = True
                    return

                # Restore saved sash position for left_split if present
                try:
                    saved = self.settings.get("pane_sashes", {}).get("left_split")
                    if isinstance(saved, int):
                        left_split.sashpos(0, int(saved))
                        self._did_init_left_split_sash = True
                        return
                except Exception:
                    pass

                total = left_split.winfo_height()
                if total <= 2:
                    self.after(10, _init_left_split_sash_once)
                    return

                min_top = 360
                min_bottom = 140

                # Prefer a smaller Live Output bottom pane by default.
                desired_bottom = 300
                target = total - max(min_bottom, desired_bottom)
                target = max(min_top, min(total - min_bottom, target))

                left_split.sashpos(0, int(target))
                self._did_init_left_split_sash = True
            except Exception:
                pass

        self.after_idle(_init_left_split_sash_once)






        # ----------------------------
        # RIGHT TOP: Charts (tabs)
        # ----------------------------
        charts_frame = ttk.LabelFrame(right_split, text="Charts (Neural lines overlaid)")
        self._charts_frame = charts_frame

        # Container for side-by-side layout: tabs on left, charts on right
        charts_layout = ttk.Frame(charts_frame)
        charts_layout.pack(fill="both", expand=True, padx=6, pady=6)

        # LEFT: Tabs bar (vertical stack of buttons)
        tabs_viewport = ttk.Frame(charts_layout)
        tabs_viewport.pack(side="left", fill="y", padx=(0, 6))

        # Use WrapFrame in vertical orientation for stacked tab buttons
        self.chart_tabs_bar = WrapFrame(tabs_viewport, orientation="vertical")
        self.chart_tabs_bar.pack(fill="both", expand=True)

        # Update function to ensure tabs are laid out properly
        def _update_tabs_layout(event=None) -> None:
            try:
                self.chart_tabs_bar._schedule_reflow()
            except Exception:
                pass

        self.chart_tabs_bar.bind("<Configure>", _update_tabs_layout, add="+")

        # RIGHT: Page container for charts (fills remaining space)
        self.chart_pages_container = ttk.Frame(charts_layout)
        self.chart_pages_container.pack(side="right", fill="both", expand=True)


        self._chart_tab_buttons: Dict[str, ttk.Button] = {}
        self.chart_pages: Dict[str, ttk.Frame] = {}
        self._current_chart_page: str = "ACCOUNT"

        def _show_page(name: str) -> None:
            self._current_chart_page = name
            # hide all pages
            for f in self.chart_pages.values():
                try:
                    f.pack_forget()
                except Exception:
                    pass
            # show selected
            f = self.chart_pages.get(name)
            if f is not None:
                f.pack(fill="both", expand=True)

            # style selected tab
            for txt, b in self._chart_tab_buttons.items():
                try:
                    b.configure(style=("ChartTabSelected.TButton" if txt == name else "ChartTab.TButton"))
                except Exception:
                    pass

            # Immediately refresh the newly shown coin chart so candles appear right away
            # (even if trader/neural scripts are not running yet).
            try:
                tab = str(name or "").strip().upper()
                if tab and tab != "ACCOUNT":
                    coin = tab
                    chart = self.charts.get(coin)
                    if chart:
                        def _do_refresh_visible():
                            try:
                                # Ensure coin folders exist (best-effort; fast)
                                try:
                                    cf_sig = (self.settings.get("main_neural_dir"), tuple(self.coins))
                                    if getattr(self, "_coin_folders_sig", None) != cf_sig:
                                        self._coin_folders_sig = cf_sig
                                        self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)
                                except Exception:
                                    pass

                                pos = self._last_positions.get(coin, {}) if isinstance(self._last_positions, dict) else {}
                                buy_px = pos.get("current_buy_price", None)
                                sell_px = pos.get("current_sell_price", None)
                                trail_line = pos.get("trail_line", None)
                                dca_line_price = pos.get("dca_line_price", None)

                                chart.refresh(
                                    self.coin_folders,
                                    current_buy_price=buy_px,
                                    current_sell_price=sell_px,
                                    trail_line=trail_line,
                                    dca_line_price=dca_line_price,
                                )
                            except Exception:
                                pass

                        self.after(1, _do_refresh_visible)
            except Exception:
                pass


        self._show_chart_page = _show_page  # used by _rebuild_coin_chart_tabs()

        # ACCOUNT page
        acct_page = ttk.Frame(self.chart_pages_container)
        self.chart_pages["ACCOUNT"] = acct_page

        acct_btn = ttk.Button(
            self.chart_tabs_bar,
            text="ACCOUNT",
            style="ChartTab.TButton",
            command=lambda: self._show_chart_page("ACCOUNT"),
        )
        self.chart_tabs_bar.add(acct_btn, padx=(0, 6), pady=(0, 6))
        self._chart_tab_buttons["ACCOUNT"] = acct_btn

        self.account_chart = AccountValueChart(
            acct_page,
            self.account_value_history_path,
            self.trade_history_path,
        )
        self.account_chart.pack(fill="both", expand=True)

        # Coin pages
        self.charts: Dict[str, CandleChart] = {}
        for coin in self.coins:
            page = ttk.Frame(self.chart_pages_container)
            self.chart_pages[coin] = page

            btn = ttk.Button(
                self.chart_tabs_bar,
                text=coin,
                style="ChartTab.TButton",
                command=lambda c=coin: self._show_chart_page(c),
            )
            self.chart_tabs_bar.add(btn, padx=(0, 6), pady=(0, 6))
            self._chart_tab_buttons[coin] = btn

            chart = CandleChart(page, self.fetcher, coin, self._settings_getter, self.trade_history_path)
            chart.pack(fill="both", expand=True)
            self.charts[coin] = chart

        # show initial page
        self._show_chart_page("ACCOUNT")
        
        # Force tabs layout update after initial load to ensure all tabs are visible
        try:
            self.after_idle(lambda: self.chart_tabs_bar._schedule_reflow())
        except Exception:
            pass
        
        # Verify all chart tabs were created
        try:
            expected = len(self.coins) + 1  # coins + ACCOUNT
            if len(self._chart_tab_buttons) != expected:
                print(f"Warning: Chart tabs mismatch - expected {expected}, got {len(self._chart_tab_buttons)}")
        except Exception:
            pass





        # ----------------------------
        # RIGHT BOTTOM: Current Trades + Trade History (stacked)
        # ----------------------------
        right_bottom_split = ttk.Panedwindow(right_split, orient="vertical")
        self._pw_right_bottom_split = right_bottom_split

        right_bottom_split.bind("<Configure>", lambda e: self._schedule_paned_clamp(self._pw_right_bottom_split))
        right_bottom_split.bind("<ButtonRelease-1>", lambda e: (
            setattr(self, "_user_moved_right_bottom_split", True),
            self._schedule_paned_clamp(self._pw_right_bottom_split),
            self._schedule_save_sashes(),
        ))

        # Current trades (top)
        trades_frame = ttk.LabelFrame(right_bottom_split, text="Current Trades")

        cols = (
            "coin",
            "qty",
            "value",          # <-- right after qty
            "avg_cost",
            "buy_price",
            "buy_pnl",
            "sell_price",
            "sell_pnl",
            "dca_stages",
            "dca_24h",
            "next_dca",
            "trail_line",     # keep trail line column
        )

        header_labels = {
            "coin": "Coin",
            "qty": "Qty",
            "value": "Value",
            "avg_cost": "Avg Cost",
            "buy_price": "Ask Price",
            "buy_pnl": "DCA PnL",
            "sell_price": "Bid Price",
            "sell_pnl": "Sell PnL",
            "dca_stages": "DCA Stage",
            "dca_24h": "DCA 24h",
            "next_dca": "Next DCA",
            "trail_line": "Trail Line",
        }

        trades_table_wrap = ttk.Frame(trades_frame)
        trades_table_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        self.trades_tree = ttk.Treeview(
            trades_table_wrap,
            columns=cols,
            show="headings",
            height=10
        )
        for c in cols:
            self.trades_tree.heading(c, text=header_labels.get(c, c))
            self.trades_tree.column(c, width=110, anchor="center", stretch=True)

        # Reasonable starting widths (they will be dynamically scaled on resize)
        self.trades_tree.column("coin", width=70)
        self.trades_tree.column("qty", width=95)
        self.trades_tree.column("value", width=110)
        self.trades_tree.column("next_dca", width=160)
        self.trades_tree.column("dca_stages", width=90)
        self.trades_tree.column("dca_24h", width=80)

        ysb = ttk.Scrollbar(trades_table_wrap, orient="vertical", command=self.trades_tree.yview)
        xsb = ttk.Scrollbar(trades_table_wrap, orient="horizontal", command=self.trades_tree.xview)
        self.trades_tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.trades_tree.pack(side="top", fill="both", expand=True)
        xsb.pack(side="bottom", fill="x")
        ysb.pack(side="right", fill="y")
        
        # Enable mousewheel scrolling for trades tree
        def _on_trades_mousewheel(event):
            scroll_direction = -1 if event.delta > 0 else 1
            self.trades_tree.yview_scroll(scroll_direction, "units")
            return "break"
        
        self.trades_tree.bind("<MouseWheel>", _on_trades_mousewheel)
        self.trades_tree.bind("<Button-4>", lambda e: self.trades_tree.yview_scroll(-3, "units"))  # Linux scroll up
        self.trades_tree.bind("<Button-5>", lambda e: self.trades_tree.yview_scroll(3, "units"))   # Linux scroll down

        def _resize_trades_columns(*_):
            # Scale the initial column widths proportionally so the table always fits the current window.
            try:
                total_w = int(self.trades_tree.winfo_width())
            except Exception:
                return
            if total_w <= 1:
                return

            try:
                sb_w = int(ysb.winfo_width() or 0)
            except Exception:
                sb_w = 0

            avail = max(200, total_w - sb_w - 8)

            base = {
                "coin": 70,
                "qty": 95,
                "value": 110,
                "avg_cost": 110,
                "buy_price": 110,
                "buy_pnl": 110,
                "sell_price": 110,
                "sell_pnl": 110,
                "dca_stages": 90,
                "dca_24h": 80,
                "next_dca": 160,
                "trail_line": 110,
            }
            base_total = sum(base.get(c, 110) for c in cols) or 1
            scale = avail / base_total

            for c in cols:
                w = int(base.get(c, 110) * scale)
                self.trades_tree.column(c, width=max(60, min(420, w)))

        self.trades_tree.bind("<Configure>", lambda e: self.after_idle(_resize_trades_columns))
        self.after_idle(_resize_trades_columns)


        # Trade history (bottom)
        hist_frame = ttk.LabelFrame(right_bottom_split, text="Trade History (scroll)")

        hist_wrap = ttk.Frame(hist_frame)
        hist_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        self.hist_list = tk.Listbox(
            hist_wrap,
            height=10,
            bg=DARK_PANEL,
            fg=DARK_FG,
            selectbackground=DARK_SELECT_BG,
            selectforeground=DARK_SELECT_FG,
            highlightbackground=DARK_BORDER,
            highlightcolor=DARK_ACCENT,
            activestyle="none",
        )
        ysb2 = ttk.Scrollbar(hist_wrap, orient="vertical", command=self.hist_list.yview)
        self.hist_list.configure(yscrollcommand=ysb2.set)

        self.hist_list.pack(side="left", fill="both", expand=True)
        ysb2.pack(side="right", fill="y")
        
        # Enable mousewheel scrolling for trade history listbox
        def _on_hist_mousewheel(event):
            scroll_direction = -1 if event.delta > 0 else 1
            self.hist_list.yview_scroll(scroll_direction, "units")
            return "break"
        
        self.hist_list.bind("<MouseWheel>", _on_hist_mousewheel)
        self.hist_list.bind("<Button-4>", lambda e: self.hist_list.yview_scroll(-3, "units"))  # Linux scroll up
        self.hist_list.bind("<Button-5>", lambda e: self.hist_list.yview_scroll(3, "units"))   # Linux scroll down


        # Assemble right side
        right_split.add(charts_frame, weight=3)
        right_split.add(right_bottom_split, weight=2)

        right_bottom_split.add(trades_frame, weight=2)
        right_bottom_split.add(hist_frame, weight=1)

        try:
            # Screenshot-style sizing: don't force Charts to be enormous by default.
            right_split.paneconfigure(charts_frame, minsize=360)
            right_split.paneconfigure(right_bottom_split, minsize=220)
        except Exception:
            pass

        try:
            right_bottom_split.paneconfigure(trades_frame, minsize=140)
            right_bottom_split.paneconfigure(hist_frame, minsize=120)
        except Exception:
            pass

        # Startup defaults to match the screenshot (but never override if user already dragged).
        def _init_right_split_sash_once():
            try:
                if getattr(self, "_did_init_right_split_sash", False):
                    return

                if getattr(self, "_user_moved_right_split", False):
                    self._did_init_right_split_sash = True
                    return

                # Restore saved sash position for right_split if present
                try:
                    saved = self.settings.get("pane_sashes", {}).get("right_split")
                    if isinstance(saved, int):
                        right_split.sashpos(0, int(saved))
                        self._did_init_right_split_sash = True
                        return
                except Exception:
                    pass

                total = right_split.winfo_height()
                if total <= 2:
                    self.after(10, _init_right_split_sash_once)
                    return

                min_top = 360
                min_bottom = 220
                desired_top = 410  # ~matches screenshot chart pane height
                target = max(min_top, min(total - min_bottom, desired_top))

                right_split.sashpos(0, int(target))
                self._did_init_right_split_sash = True
            except Exception:
                pass

        def _init_right_bottom_split_sash_once():
            try:
                if getattr(self, "_did_init_right_bottom_split_sash", False):
                    return

                if getattr(self, "_user_moved_right_bottom_split", False):
                    self._did_init_right_bottom_split_sash = True
                    return

                # Restore saved sash position for right_bottom_split if present
                try:
                    saved = self.settings.get("pane_sashes", {}).get("right_bottom_split")
                    if isinstance(saved, int):
                        right_bottom_split.sashpos(0, int(saved))
                        self._did_init_right_bottom_split_sash = True
                        return
                except Exception:
                    pass

                total = right_bottom_split.winfo_height()
                if total <= 2:
                    self.after(10, _init_right_bottom_split_sash_once)
                    return

                min_top = 140
                min_bottom = 120
                desired_top = 280  # more space for Current Trades (like screenshot)
                target = max(min_top, min(total - min_bottom, desired_top))

                right_bottom_split.sashpos(0, int(target))
                self._did_init_right_bottom_split_sash = True
            except Exception:
                pass

        self.after_idle(_init_right_split_sash_once)
        self.after_idle(_init_right_bottom_split_sash_once)

        # Initial clamp once everything is laid out
        self.after_idle(lambda: (
            self._schedule_paned_clamp(getattr(self, "_pw_outer", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_left_split", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_right_split", None)),
            self._schedule_paned_clamp(getattr(self, "_pw_right_bottom_split", None)),
        ))

        # Apply saved layout explicitly once everything is up; this ensures sash
        # positions are restored and that canvases (charts, neural overview)
        # receive a final resize/redraw so sizes actually persist visually.
        try:
            self.after_idle(self._apply_saved_layout)
        except Exception:
            pass


        # status bar
        self.status = ttk.Label(self, text="Ready", anchor="w")
        self.status.pack(fill="x", side="bottom")



    # ---- panedwindow anti-collapse helpers ----

    def _check_left_split_minimize(self) -> None:
        """Check if left split logs panel should be minimized to small size."""
        try:
            if not hasattr(self, "_pw_left_split") or not self._pw_left_split:
                return
            
            total_height = self._pw_left_split.winfo_height()
            if total_height <= 2:
                return
            
            sash_pos = int(self._pw_left_split.sashpos(0))
            
            # If sash is within 80px of the bottom (minimizing logs panel)
            minimize_threshold = 80
            if total_height - sash_pos < minimize_threshold:
                # Resize to compact size (leaving ~50px for logs panel)
                compact_size = 50
                target_pos = total_height - compact_size
                self._pw_left_split.sashpos(0, max(0, target_pos))
                self._schedule_save_sashes()
        except Exception:
            pass

    def _schedule_paned_clamp(self, pw: ttk.Panedwindow) -> None:
        """
        Debounced clamp so we don't fight the geometry manager mid-resize.

        IMPORTANT: use `after(1, ...)` instead of `after_idle(...)` so it still runs
        while the mouse is held during sash dragging (Tk often doesn't go "idle"
        until after the drag ends, which is exactly when panes can vanish).
        """
        try:
            if not pw or not int(pw.winfo_exists()):
                return
        except Exception:
            return

        key = str(pw)
        if key in self._paned_clamp_after_ids:
            return

        def _run():
            try:
                self._paned_clamp_after_ids.pop(key, None)
            except Exception:
                pass
            self._clamp_panedwindow_sashes(pw)

        try:
            self._paned_clamp_after_ids[key] = self.after(1, _run)
        except Exception:
            pass


    def _clamp_panedwindow_sashes(self, pw: ttk.Panedwindow) -> None:
        """
        Enforces each pane's configured 'minsize' by clamping sash positions.

        NOTE:
        ttk.Panedwindow.paneconfigure(pane) typically returns dict values like:
            {"minsize": ("minsize", "minsize", "Minsize", "140"), ...}
        so we MUST pull the last element when it's a tuple/list.
        """
        try:
            if not pw or not int(pw.winfo_exists()):
                return

            panes = list(pw.panes())
            if len(panes) < 2:
                return

            orient = str(pw.cget("orient"))
            total = pw.winfo_height() if orient == "vertical" else pw.winfo_width()
            if total <= 2:
                return

            def _get_minsize(pane_id) -> int:
                try:
                    cfg = pw.paneconfigure(pane_id)
                    ms = cfg.get("minsize", 0)

                    # ttk returns tuples like ('minsize','minsize','Minsize','140')
                    if isinstance(ms, (tuple, list)) and ms:
                        ms = ms[-1]

                    # sometimes it's already int/float-like, sometimes it's a string
                    return max(0, int(float(ms)))
                except Exception:
                    return 0

            mins: List[int] = [_get_minsize(p) for p in panes]

            # If total space is smaller than sum(mins), we still clamp as best-effort
            # by scaling mins down proportionally but never letting a pane hit 0.
            if sum(mins) >= total:
                # best-effort: keep every pane at least 24px so it can’t disappear
                floor = 24
                mins = [max(floor, m) for m in mins]

                # if even floors don't fit, just stop here (window minsize should prevent this)
                if sum(mins) >= total:
                    return

            # Two-pass clamp so constraints settle even with multiple sashes
            for _ in range(2):
                for i in range(len(panes) - 1):
                    min_pos = sum(mins[: i + 1])
                    max_pos = total - sum(mins[i + 1 :])

                    try:
                        cur = int(pw.sashpos(i))
                    except Exception:
                        continue

                    new = max(min_pos, min(max_pos, cur))
                    if new != cur:
                        try:
                            pw.sashpos(i, new)
                        except Exception:
                            pass


        except Exception:
            pass


    def _schedule_save_sashes(self, delay: int = 700) -> None:
        """Debounced save of current sash positions to settings file."""
        try:
            if getattr(self, "_save_sash_after_id", None):
                try:
                    self.after_cancel(self._save_sash_after_id)
                except Exception:
                    pass

            def _do_save():
                try:
                    self._save_current_sashes()
                except Exception:
                    pass

            try:
                self._save_sash_after_id = self.after(int(delay), _do_save)
            except Exception:
                try:
                    _do_save()
                except Exception:
                    pass
        except Exception:
            pass


    def _save_current_sashes(self) -> None:
        """Read current sash positions and write them to settings immediately."""
        try:
            s = self.settings.setdefault("pane_sashes", {})

            try:
                if hasattr(self, "_pw_outer") and getattr(self, "_pw_outer"):
                    try:
                        s["outer"] = int(self._pw_outer.sashpos(0))
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                if hasattr(self, "_pw_left_split") and getattr(self, "_pw_left_split"):
                    try:
                        s["left_split"] = int(self._pw_left_split.sashpos(0))
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                if hasattr(self, "_pw_right_split") and getattr(self, "_pw_right_split"):
                    try:
                        s["right_split"] = int(self._pw_right_split.sashpos(0))
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                if hasattr(self, "_pw_right_bottom_split") and getattr(self, "_pw_right_bottom_split"):
                    try:
                        s["right_bottom_split"] = int(self._pw_right_bottom_split.sashpos(0))
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                self._save_settings()
            except Exception:
                pass
        except Exception:
            pass


    def _read_current_sashes(self) -> dict:
        """Return a dict of current sash positions for the main panedwindows."""
        out = {}
        try:
            try:
                if hasattr(self, "_pw_outer") and getattr(self, "_pw_outer"):
                    out["outer"] = int(self._pw_outer.sashpos(0))
            except Exception:
                pass
            try:
                if hasattr(self, "_pw_left_split") and getattr(self, "_pw_left_split"):
                    out["left_split"] = int(self._pw_left_split.sashpos(0))
            except Exception:
                pass
            try:
                if hasattr(self, "_pw_right_split") and getattr(self, "_pw_right_split"):
                    out["right_split"] = int(self._pw_right_split.sashpos(0))
            except Exception:
                pass
            try:
                if hasattr(self, "_pw_right_bottom_split") and getattr(self, "_pw_right_bottom_split"):
                    out["right_bottom_split"] = int(self._pw_right_bottom_split.sashpos(0))
            except Exception:
                pass
        except Exception:
            pass
        return out


    def _ensure_outer_sash_restored(self, saved_outer: int, attempts: int = 4, delay_ms: int = 120) -> None:
        """Try to apply the saved outer sash position several times as layout settles.

        Some platforms report sash events on internal widgets; restoring immediately
        can race with geometry management. Retry a few times with delays.
        """
        try:
            if not isinstance(saved_outer, int):
                return

            def _try_set(i: int = 0):
                try:
                    if not (hasattr(self, "_pw_outer") and getattr(self, "_pw_outer") and int(self._pw_outer.winfo_exists())):
                        # schedule next attempt
                        if i + 1 < attempts:
                            self.after(delay_ms, lambda: _try_set(i + 1))
                        return

                    total = self._pw_outer.winfo_width()
                    if total and int(total) > 2:
                        try:
                            self._pw_outer.sashpos(0, int(saved_outer))
                        except Exception:
                            pass

                    # also clamp to enforce minsize
                    try:
                        self._schedule_paned_clamp(self._pw_outer)
                    except Exception:
                        pass
                except Exception:
                    pass

                if i + 1 < attempts:
                    try:
                        self.after(delay_ms, lambda: _try_set(i + 1))
                    except Exception:
                        pass

            try:
                self.after(10, lambda: _try_set(0))
            except Exception:
                pass
        except Exception:
            pass


    def _apply_saved_layout(self) -> None:
        """Apply saved sash positions and trigger canvas redraws so sizes persist."""
        try:
            s = self.settings.get("pane_sashes", {}) or {}

            try:
                outer_saved = s.get("outer")
                if isinstance(outer_saved, int) and hasattr(self, "_pw_outer") and getattr(self, "_pw_outer"):
                    try:
                        self._pw_outer.sashpos(0, int(outer_saved))
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                left_saved = s.get("left_split")
                if isinstance(left_saved, int) and hasattr(self, "_pw_left_split") and getattr(self, "_pw_left_split"):
                    try:
                        self._pw_left_split.sashpos(0, int(left_saved))
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                right_saved = s.get("right_split")
                if isinstance(right_saved, int) and hasattr(self, "_pw_right_split") and getattr(self, "_pw_right_split"):
                    try:
                        self._pw_right_split.sashpos(0, int(right_saved))
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                rb_saved = s.get("right_bottom_split")
                if isinstance(rb_saved, int) and hasattr(self, "_pw_right_bottom_split") and getattr(self, "_pw_right_bottom_split"):
                    try:
                        self._pw_right_bottom_split.sashpos(0, int(rb_saved))
                    except Exception:
                        pass
            except Exception:
                pass

            # Let geometry settle then force canvases to recompute and redraw
            try:
                self.update_idletasks()
            except Exception:
                pass

            # Ensure outer sash is applied robustly: schedule a few retries
            try:
                if isinstance(outer_saved, int):
                    try:
                        self._ensure_outer_sash_restored(int(outer_saved))
                    except Exception:
                        pass
            except Exception:
                pass

            # Refresh charts
            try:
                if getattr(self, "charts", None):
                    for c in list(self.charts.values()):
                        try:
                            w = c.canvas.get_tk_widget()
                            w.update_idletasks()
                            try:
                                c.canvas.draw_idle()
                            except Exception:
                                pass
                        except Exception:
                            pass
            except Exception:
                pass

            # Account chart
            try:
                if getattr(self, "account_chart", None):
                    try:
                        w = self.account_chart.canvas.get_tk_widget()
                        w.update_idletasks()
                        try:
                            self.account_chart.canvas.draw_idle()
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass

            # Neural overview scrollregion update
            try:
                if getattr(self, "_update_neural_overview_scrollbars", None):
                    try:
                        self._update_neural_overview_scrollbars()
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception:
            pass



    # ---- process control ----


    def _reader_thread(self, proc: subprocess.Popen, q: "queue.Queue[str]", prefix: str) -> None:
        try:
            # line-buffered text mode
            while True:
                line = proc.stdout.readline() if proc.stdout else ""
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
                    continue
                q.put(f"{prefix}{line.rstrip()}")
        except Exception:
            pass
        finally:
            q.put(f"{prefix}[process exited]")

    def _start_process(self, p: ProcInfo, log_q: Optional["queue.Queue[str]"] = None, prefix: str = "") -> None:
        if p.proc and p.proc.poll() is None:
            return
        if not os.path.isfile(p.path):
            messagebox.showerror("Missing script", f"Cannot find: {p.path}")
            return

        env = os.environ.copy()
        env["POWERTRADER_HUB_DIR"] = self.hub_dir  # so rhcb writes where GUI reads

        try:
            p.proc = subprocess.Popen(
                [sys.executable, "-u", p.path],  # -u for unbuffered prints
                cwd=self.project_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            # record launch time for uptime display
            try:
                p.start_time = time.time()
            except Exception:
                p.start_time = None
            if log_q is not None:
                t = threading.Thread(target=self._reader_thread, args=(p.proc, log_q, prefix), daemon=True)
                t.start()
        except Exception as e:
            messagebox.showerror("Failed to start", f"{p.name} failed to start:\n{e}")


    def _stop_process(self, p: ProcInfo) -> None:
        if not p.proc or p.proc.poll() is not None:
            return
        try:
            p.proc.terminate()
        except Exception:
            pass
        try:
            p.start_time = None
        except Exception:
            pass

    def start_neural(self) -> None:
        # Reset runner-ready gate file (prevents stale "ready" from a prior run)
        try:
            with open(self.runner_ready_path, "w", encoding="utf-8") as f:
                json.dump({"timestamp": time.time(), "ready": False, "stage": "starting"}, f)
        except Exception:
            pass

        # Pass KuCoin usage flag to the runner process via env var so the
        # runner can choose a safe fallback when the `kucoin` package is
        # not available. Value is '1' (enabled) or '0' (disabled).
        try:
            os.environ["USE_KUCOIN_API"] = "1" if bool(self.settings.get("use_kucoin_api", True)) else "0"
        except Exception:
            pass

        self._start_process(self.proc_neural, log_q=self.runner_log_q, prefix="[RUNNER] ")


    def start_trader(self) -> None:
        self._start_process(self.proc_trader, log_q=self.trader_log_q, prefix="[TRADER] ")


    def stop_neural(self) -> None:
        self._stop_process(self.proc_neural)



    def stop_trader(self) -> None:
        self._stop_process(self.proc_trader)

    def toggle_all_scripts(self) -> None:
        neural_running = bool(self.proc_neural.proc and self.proc_neural.proc.poll() is None)
        trader_running = bool(self.proc_trader.proc and self.proc_trader.proc.poll() is None)

        # If anything is running (or we're waiting on runner readiness), toggle means "stop"
        if neural_running or trader_running or bool(getattr(self, "_auto_start_trader_pending", False)):
            self.stop_all_scripts()
            return

        # Otherwise, toggle means "start"
        self.start_all_scripts()

    def _toggle_neural(self) -> None:
        """Toggle Neural Levels section collapse/expand."""
        collapsed = self.neural_collapsed.get()
        if collapsed:
            self.neural_content.pack(fill="both", expand=True, padx=6, pady=(0, 6))
            self.neural_toggle_btn.config(text="▼ Neural Levels (0–7)")
            self.neural_collapsed.set(False)
        else:
            self.neural_content.pack_forget()
            self.neural_toggle_btn.config(text="► Neural Levels (0–7)")
            self.neural_collapsed.set(True)

    def _toggle_logs(self) -> None:
        """Toggle Live Output section collapse/expand."""
        collapsed = self.logs_collapsed.get()
        if collapsed:
            self.logs_content.pack(fill="both", expand=True, padx=6, pady=(0, 6))
            self.logs_toggle_btn.config(text="▼ Live Output")
            self.logs_collapsed.set(False)
        else:
            self.logs_content.pack_forget()
            self.logs_toggle_btn.config(text="► Live Output")
            self.logs_collapsed.set(True)

    def _read_runner_ready(self) -> Dict[str, Any]:
        try:
            if os.path.isfile(self.runner_ready_path):
                with open(self.runner_ready_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {"ready": False}

    def _poll_runner_ready_then_start_trader(self) -> None:
        # Cancelled or already started
        if not bool(getattr(self, "_auto_start_trader_pending", False)):
            return

        # If runner died, stop waiting
        if not (self.proc_neural.proc and self.proc_neural.proc.poll() is None):
            print("[Hub] Neural runner is not running. Cancelling trader auto-start.")
            self._auto_start_trader_pending = False
            return

        st = self._read_runner_ready()
        if bool(st.get("ready", False)):
            print("[Hub] Runner is ready. Starting trader now.")
            self._auto_start_trader_pending = False

            # Start trader if not already running
            if not (self.proc_trader.proc and self.proc_trader.proc.poll() is None):
                self.start_trader()
            return

        # Not ready yet — keep polling (max 20 attempts = 5 seconds)
        poll_count = getattr(self, "_trader_poll_count", 0)
        self._trader_poll_count = poll_count + 1
        
        if self._trader_poll_count > 20:
            print("[Hub] Timed out waiting for runner ready. Starting trader anyway.")
            self._auto_start_trader_pending = False
            if not (self.proc_trader.proc and self.proc_trader.proc.poll() is None):
                self.start_trader()
            return
        
        try:
            self.after(250, self._poll_runner_ready_then_start_trader)
        except Exception:
            pass

    def start_all_scripts(self) -> None:
        # Enforce flow: Train All → wait for completion → Neural → Trader
        # Always start training first and wait for it to complete before starting neural/trader
        messagebox.showinfo(
            "Starting All",
            "Starting training first, then Neural Runner and Trader will follow automatically for all trained coins."
        )
        self._auto_start_runner_after_training = True
        self.train_all_coins()
        # After training completes, _start_neural_then_trader will be called automatically by _tick()

    def _start_neural_then_trader(self) -> None:
        """Helper to start neural runner and trader for all trained coins."""
        self._auto_start_trader_pending = True
        self._trader_poll_count = 0  # Reset poll counter
        trained_coins = [c for c in self.coins if self._coin_is_trained(c)]
        for coin in trained_coins:
            self.start_neural_for_coin(coin)
        try:
            self.after(500, lambda: self._poll_runner_ready_then_start_trader_for_coins(trained_coins))
        except Exception:
            pass

    def start_neural_for_coin(self, coin: str) -> None:
        """Start neural runner for a specific coin."""
        coin = coin.strip().upper()
        if not coin:
            return

        # Match the runner's folder convention:
        #   BTC runs from the main neural folder
        #   Alts run from their own coin subfolder
        coin_cwd = self.coin_folders.get(coin, self.project_dir)

        runner_name = os.path.basename(str(self.settings.get("script_neural_runner2", "pt_thinker.py")))

        # If an alt coin folder doesn't exist yet, create it and copy the runner script from the main (BTC) folder.
        if coin != "BTC":
            try:
                if not os.path.isdir(coin_cwd):
                    os.makedirs(coin_cwd, exist_ok=True)
                src_main_folder = self.coin_folders.get("BTC", self.project_dir)
                src_runner_path = os.path.join(src_main_folder, runner_name)
                dst_runner_path = os.path.join(coin_cwd, runner_name)
                if os.path.isfile(src_runner_path):
                    shutil.copy2(src_runner_path, dst_runner_path)
            except Exception:
                pass

        runner_path = os.path.abspath(os.path.join(coin_cwd, runner_name))
        if not os.path.isfile(runner_path):
            fallback = os.path.abspath(os.path.join(self.project_dir, runner_name))
            proc_runner = getattr(self, 'proc_neural_path', None)
            if proc_runner and os.path.isfile(proc_runner):
                fallback = proc_runner
            if os.path.isfile(fallback):
                runner_path = os.path.abspath(fallback)
            else:
                messagebox.showerror(
                    "Missing runner",
                    f"Cannot find neural runner for {coin} at:\n{runner_path}"
                )
                return

        # Prevent duplicate runner for same coin
        if hasattr(self, 'neural_runners') and coin in self.neural_runners and self.neural_runners[coin].proc and self.neural_runners[coin].proc.poll() is None:
            return

        q = queue.Queue()
        info = ProcInfo(name=f"NeuralRunner-{coin}", path=runner_path)
        env = os.environ.copy()
        env["POWERTRADER_HUB_DIR"] = self.hub_dir
        env["USE_KUCOIN_API"] = "1" if bool(self.settings.get("use_kucoin_api", True)) else "0"
        try:
            python_exec = os.path.join(self.project_dir, ".venv", "bin", "python")
            if not os.path.isfile(python_exec):
                python_exec = sys.executable
            info.proc = subprocess.Popen(
                [python_exec, "-u", info.path, coin],
                cwd=coin_cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            t = threading.Thread(target=self._reader_thread, args=(info.proc, q, f"[{coin}-RUNNER] "), daemon=True)
            t.start()
            if not hasattr(self, 'neural_runners'):
                self.neural_runners = {}
            self.neural_runners[coin] = LogProc(info=info, log_q=q, thread=t, is_trainer=False, coin=coin)
        except Exception as e:
            messagebox.showerror("Failed to start", f"Neural runner for {coin} failed to start:\n{e}")

    def _poll_runner_ready_then_start_trader_for_coins(self, coins: list) -> None:
        # Cancelled or already started
        if not bool(getattr(self, "_auto_start_trader_pending", False)):
            return

        # If runner died, stop waiting
        if not (self.proc_neural.proc and self.proc_neural.proc.poll() is None):
            print("[Hub] Neural runner is not running. Cancelling trader auto-start.")
            self._auto_start_trader_pending = False
            return

        st = self._read_runner_ready()
        if bool(st.get("ready", False)):
            print("[Hub] Runner is ready. Starting trader now for all trained coins.")
            self._auto_start_trader_pending = False
            for coin in coins:
                self.start_trader_for_coin(coin)
            return

        # Not ready yet — keep polling (max 20 attempts = 5 seconds)
        poll_count = getattr(self, "_trader_poll_count", 0)
        self._trader_poll_count = poll_count + 1
        if self._trader_poll_count > 20:
            print("[Hub] Timed out waiting for runner ready. Starting trader anyway for all trained coins.")
            self._auto_start_trader_pending = False
            for coin in coins:
                self.start_trader_for_coin(coin)
            return

        try:
            self.after(250, lambda: self._poll_runner_ready_then_start_trader_for_coins(coins))
        except Exception:
            pass

    def start_trader_for_coin(self, coin: str) -> None:
        """Start trader for a specific coin."""
        # Implement logic to start trader for the given coin
        # This is a placeholder; actual implementation may need to set up per-coin trader processes
        # For now, fallback to start_trader if only one trader is supported
        self.start_trader()


    def _coin_is_trained(self, coin: str) -> bool:
        coin = coin.upper().strip()
        folder = self.coin_folders.get(coin, "")
        if not folder or not os.path.isdir(folder):
            return False

        # In DRY RUN mode, check for saved model marker file
        if self.settings.get("dry_run_mode", False):
            model_marker = os.path.join(folder, "trained_model_saved.txt")
            if os.path.isfile(model_marker):
                return True

        # Check trainer status - FINISHED means trained, TRAINING means not trained yet
        try:
            st = _safe_read_json(os.path.join(folder, "trainer_status.json"))
            if isinstance(st, dict):
                state = str(st.get("state", "")).upper()
                # If explicitly FINISHED, consider it trained (even if it restarts later)
                if state == "FINISHED":
                    return True
                # If explicitly TRAINED (saved model state), consider it trained
                if state == "TRAINED":
                    return True
                # If currently TRAINING and no completion timestamp, not trained yet
                if state == "TRAINING":
                    # Check if we have a recent completion timestamp - if so, it's trained
                    # (trainer may restart after finishing, but initial training is done)
                    stamp_path = os.path.join(folder, "trainer_last_training_time.txt")
                    if os.path.isfile(stamp_path):
                        try:
                            with open(stamp_path, "r", encoding="utf-8") as f:
                                ts = float((f.read() or "").strip() or "0")
                            if ts > 0 and (time.time() - ts) <= (14 * 24 * 60 * 60):
                                return True
                        except Exception:
                            pass
                    return False
        except Exception:
            pass

        # Fallback: check timestamp file (for legacy or external trainers)
        stamp_path = os.path.join(folder, "trainer_last_training_time.txt")
        try:
            if not os.path.isfile(stamp_path):
                return False
            with open(stamp_path, "r", encoding="utf-8") as f:
                raw = (f.read() or "").strip()
            ts = float(raw) if raw else 0.0
            if ts <= 0:
                return False
            return (time.time() - ts) <= (14 * 24 * 60 * 60)
        except Exception:
            return False

    def _running_trainers(self) -> List[str]:
        running: List[str] = []

        # Trainers launched by this GUI instance
        for c, lp in self.trainers.items():
            try:
                if lp.info.proc and lp.info.proc.poll() is None:
                    running.append(c)
            except Exception:
                pass

        # Trainers launched elsewhere: look at per-coin status file
        for c in self.coins:
            try:
                coin = (c or "").strip().upper()
                folder = self.coin_folders.get(coin, "")
                if not folder or not os.path.isdir(folder):
                    continue

                status_path = os.path.join(folder, "trainer_status.json")
                st = _safe_read_json(status_path)

                if isinstance(st, dict) and str(st.get("state", "")).upper() == "TRAINING":
                    stamp_path = os.path.join(folder, "trainer_last_training_time.txt")

                    try:
                        if os.path.isfile(stamp_path) and os.path.isfile(status_path):
                            if os.path.getmtime(stamp_path) >= os.path.getmtime(status_path):
                                continue
                    except Exception:
                        pass

                    running.append(coin)
            except Exception:
                pass

        # de-dupe while preserving order
        out: List[str] = []
        seen = set()
        for c in running:
            cc = (c or "").strip().upper()
            if cc and cc not in seen:
                seen.add(cc)
                out.append(cc)
        return out



    def _training_status_map(self) -> Dict[str, str]:
        """
        Returns {coin: "TRAINED" | "TRAINING" | "NOT TRAINED"}.
        
        Priority: A coin that has completed initial training (has timestamp file + FINISHED state seen)
        is marked TRAINED even if the trainer process is still running in continuous training mode.
        """
        running = set(self._running_trainers())
        out: Dict[str, str] = {}
        for c in self.coins:
            # Check if trained first - this captures coins that completed initial training
            # even if the trainer is continuing to run for ongoing optimization
            if self._coin_is_trained(c):
                out[c] = "TRAINED"
            elif c in running:
                out[c] = "TRAINING"
            else:
                out[c] = "NOT TRAINED"
        return out

    def _clear_training_data(self, coin: str) -> int:
        """Clear all training memory files for a specific coin. Returns number of files deleted."""
        coin = coin.strip().upper()
        coin_cwd = self.coin_folders.get(coin, self.project_dir)
        
        patterns = [
            "trainer_last_training_time.txt",
            "trainer_status.json",
            "trainer_last_start_time.txt",
            "killer.txt",
            "memories_*.txt",
            "memory_weights_*.txt",
            "memory_weights_high_*.txt",
            "memory_weights_low_*.txt",
            "neural_perfect_threshold_*.txt",
        ]
        
        deleted = 0
        for pat in patterns:
            for fp in glob.glob(os.path.join(coin_cwd, pat)):
                try:
                    os.remove(fp)
                    deleted += 1
                except Exception:
                    pass
        return deleted

    def train_selected_coin(self) -> None:
        coin = (getattr(self, 'train_coin_var', self.trainer_coin_var).get() or "").strip().upper()

        if not coin:
            return
        # Reuse the trainers pane runner — start trainer for selected coin
        self.start_trainer_for_selected_coin()

    def reset_and_train_selected(self) -> None:
        """Clear training data for selected coin, then start training."""
        coin = (getattr(self, 'train_coin_var', self.trainer_coin_var).get() or "").strip().upper()
        
        if not coin:
            return
        
        # Clear the training data first
        deleted = self._clear_training_data(coin)
        
        if deleted:
            try:
                self.status.config(text=f"Cleared {deleted} training file(s) for {coin}")
            except Exception:
                pass
        
        # Now start training
        self.start_trainer_for_selected_coin()

    def train_all_coins(self) -> None:
        """Start trainers for every coin in parallel without blocking the GUI."""
        # Stop the Neural Runner once before starting any training
        self.stop_neural()
        
        def launch_all_trainers() -> None:
            """Background thread to launch all trainer subprocesses."""
            try:
                threads = []
                for c in self.coins:
                    def start_trainer(coin: str) -> None:
                        try:
                            self._start_single_trainer(coin)
                        except Exception as e:
                            print(f"Error starting trainer for {coin}: {e}")
                    
                    t = threading.Thread(target=start_trainer, args=(c,), daemon=True)
                    t.start()
                    threads.append(t)
                    # Small delay between launches to avoid resource contention
                    time.sleep(0.1)
                
                # Wait for all launches to complete (in background thread, not GUI)
                for t in threads:
                    t.join(timeout=5.0)
            except Exception as e:
                print(f"Error in train_all_coins: {e}")
        
        # Launch everything in a single background thread to avoid freezing the GUI
        launcher = threading.Thread(target=launch_all_trainers, daemon=True)
        launcher.start()

    def reset_and_train_all(self) -> None:
        """Clear training data for all coins, then start training them all."""
        # Stop the Neural Runner once before starting any training
        self.stop_neural()
        
        def launch_all_with_reset() -> None:
            """Background thread to clear data then launch all trainer subprocesses."""
            try:
                # First pass: clear all training data
                total_deleted = 0
                for c in self.coins:
                    deleted = self._clear_training_data(c)
                    total_deleted += deleted
                
                if total_deleted:
                    try:
                        self.status.config(text=f"Cleared {total_deleted} training file(s) across all coins")
                    except Exception:
                        pass
                
                # Small delay after deletion
                time.sleep(0.2)
                
                # Second pass: start all trainers
                threads = []
                for c in self.coins:
                    def start_trainer(coin: str) -> None:
                        try:
                            self._start_single_trainer(coin)
                        except Exception as e:
                            print(f"Error starting trainer for {coin}: {e}")
                    
                    t = threading.Thread(target=start_trainer, args=(c,), daemon=True)
                    t.start()
                    threads.append(t)
                    # Small delay between launches to avoid resource contention
                    time.sleep(0.1)
                
                # Wait for all launches to complete (in background thread, not GUI)
                for t in threads:
                    t.join(timeout=5.0)
            except Exception as e:
                print(f"Error in reset_and_train_all: {e}")
        
        # Launch everything in a single background thread to avoid freezing the GUI
        launcher = threading.Thread(target=launch_all_with_reset, daemon=True)
        launcher.start()

    def start_trainer_for_selected_coin(self) -> None:
        """Start trainer for the currently selected coin (stops neural first)."""
        coin = (self.trainer_coin_var.get() or "").strip().upper()
        if not coin:
            return

        # Stop the Neural Runner before any training starts (training modifies artifacts the runner reads)
        self.stop_neural()
        
        # Start the trainer
        self._start_single_trainer(coin)
    
    def _start_single_trainer(self, coin: str) -> None:
        """Internal method to start a trainer for a specific coin (no neural stop)."""
        coin = coin.strip().upper()
        if not coin:
            return

        # --- IMPORTANT ---
        # Match the trader's folder convention:
        #   BTC runs from the main neural folder
        #   Alts run from their own coin subfolder
        coin_cwd = self.coin_folders.get(coin, self.project_dir)

        # Use the trainer script that lives INSIDE that coin's folder so outputs land in the right place.
        trainer_name = os.path.basename(str(self.settings.get("script_neural_trainer", "pt_trainer.py")))

        # If an alt coin folder doesn't exist yet, create it and copy the trainer script from the main (BTC) folder.
        # (Also: overwrite to avoid running stale trainer copies in alt folders.)

        if coin != "BTC":
            try:
                if not os.path.isdir(coin_cwd):
                    os.makedirs(coin_cwd, exist_ok=True)

                src_main_folder = self.coin_folders.get("BTC", self.project_dir)
                src_trainer_path = os.path.join(src_main_folder, trainer_name)
                dst_trainer_path = os.path.join(coin_cwd, trainer_name)

                if os.path.isfile(src_trainer_path):
                    shutil.copy2(src_trainer_path, dst_trainer_path)
            except Exception:
                pass

        trainer_path = os.path.abspath(os.path.join(coin_cwd, trainer_name))

        # Fallback: if BTC's trainer isn't found in the main neural folder, try the project's trainer
        if not os.path.isfile(trainer_path):
            fallback = os.path.abspath(os.path.join(self.project_dir, trainer_name))
            proc_trainer = getattr(self, 'proc_trainer_path', None)
            if proc_trainer and os.path.isfile(proc_trainer):
                fallback = proc_trainer

            if os.path.isfile(fallback):
                trainer_path = os.path.abspath(fallback)
            else:
                messagebox.showerror(
                    "Missing trainer",
                    f"Cannot find trainer for {coin} at:\n{trainer_path}"
                )
                return

        if coin in self.trainers and self.trainers[coin].info.proc and self.trainers[coin].info.proc.poll() is None:
            return

        q: "queue.Queue[str]" = queue.Queue()
        info = ProcInfo(name=f"Trainer-{coin}", path=trainer_path)

        env = os.environ.copy()
        env["POWERTRADER_HUB_DIR"] = self.hub_dir

        try:
            # IMPORTANT: pass `coin` so neural_trainer trains the correct market instead of defaulting to BTC
            # Prefer the project's virtualenv python if available so trainers inherit installed packages
            python_exec = os.path.join(self.project_dir, ".venv", "bin", "python")
            if not os.path.isfile(python_exec):
                python_exec = sys.executable

            info.proc = subprocess.Popen(
                [python_exec, "-u", info.path, coin],
                cwd=coin_cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            t = threading.Thread(target=self._reader_thread, args=(info.proc, q, f"[{coin}] "), daemon=True)
            t.start()

            self.trainers[coin] = LogProc(info=info, log_q=q, thread=t, is_trainer=True, coin=coin)
            # write a per-coin status file so other hub instances or restarts can see this trainer as running
            try:
                status_path = os.path.join(coin_cwd, "trainer_status.json")
                from datetime import datetime
                st = {
                    "state": "TRAINING",
                    "pid": info.proc.pid if info.proc else None,
                    "start_time": datetime.utcnow().isoformat() + "Z",
                }
                try:
                    with open(status_path, "w", encoding="utf-8") as f:
                        json.dump(st, f)
                except Exception:
                    pass
            except Exception:
                pass

            # update trainer status label immediately
            try:
                running = [c for c, lp in self.trainers.items() if lp.info.proc and lp.info.proc.poll() is None]
                self.trainer_status_lbl.config(text=f"running: {', '.join(running)}" if running else "(no trainers running)")
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Failed to start", f"Trainer for {coin} failed to start:\n{e}")




    def stop_trainer_for_selected_coin(self) -> None:
        coin = (self.trainer_coin_var.get() or "").strip().upper()
        lp = self.trainers.get(coin)
        if not lp or not lp.info.proc or lp.info.proc.poll() is not None:
            return
        try:
            lp.info.proc.terminate()
        except Exception:
            pass

        # write a per-coin status file marking the trainer as stopped and refresh label
        try:
            coin_cwd = self.coin_folders.get(coin, self.project_dir)
            status_path = os.path.join(coin_cwd, "trainer_status.json")
            from datetime import datetime
            st = {
                "state": "STOPPED",
                "pid": lp.info.proc.pid if lp.info.proc else None,
                "stop_time": datetime.utcnow().isoformat() + "Z",
            }
            try:
                with open(status_path, "w", encoding="utf-8") as f:
                    json.dump(st, f)
            except Exception:
                pass
        except Exception:
            pass

        try:
            running = [c for c, lp in self.trainers.items() if lp.info.proc and lp.info.proc.poll() is None]
            self.trainer_status_lbl.config(text=f"running: {', '.join(running)}" if running else "(no trainers running)")
        except Exception:
            pass


    def stop_all_trainers(self) -> None:
        """Stop all trainer processes managed by this GUI instance (best-effort)."""
        try:
            for coin, lp in list(self.trainers.items()):
                try:
                    if lp and lp.info.proc and lp.info.proc.poll() is None:
                        try:
                            lp.info.proc.terminate()
                        except Exception:
                            pass

                        # write per-coin status file marking stopped
                        try:
                            coin_cwd = self.coin_folders.get(coin, self.project_dir)
                            status_path = os.path.join(coin_cwd, "trainer_status.json")
                            from datetime import datetime
                            st = {
                                "state": "STOPPED",
                                "pid": lp.info.proc.pid if lp.info.proc else None,
                                "stop_time": datetime.utcnow().isoformat() + "Z",
                            }
                            try:
                                with open(status_path, "w", encoding="utf-8") as f:
                                    json.dump(st, f)
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass

            # refresh trainer status label
            try:
                running = [c for c, lp in self.trainers.items() if lp.info.proc and lp.info.proc.poll() is None]
                self.trainer_status_lbl.config(text=f"running: {', '.join(running)}" if running else "(no trainers running)")
            except Exception:
                pass
        except Exception:
            pass


    def stop_all_scripts(self) -> None:
        # Cancel any pending "wait for runner then start trader"
        self._auto_start_trader_pending = False

        # Stop in reverse order: Trader → Neural → Train
        # Step 1: Stop Trader first
        self.stop_trader()
        
        # Step 2: Stop Neural Runner
        self.stop_neural()

        # Step 3: Stop any running trainers launched by this GUI instance
        try:
            for coin, lp in list(self.trainers.items()):
                try:
                    if lp and lp.info.proc and lp.info.proc.poll() is None:
                        try:
                            lp.info.proc.terminate()
                        except Exception:
                            pass

                        # write per-coin status file marking stopped
                        try:
                            coin_cwd = self.coin_folders.get(coin, self.project_dir)
                            status_path = os.path.join(coin_cwd, "trainer_status.json")
                            from datetime import datetime
                            st = {
                                "state": "STOPPED",
                                "pid": lp.info.proc.pid if lp.info.proc else None,
                                "stop_time": datetime.utcnow().isoformat() + "Z",
                            }
                            try:
                                with open(status_path, "w", encoding="utf-8") as f:
                                    json.dump(st, f)
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass

            # refresh trainer status label
            try:
                running = [c for c, lp in self.trainers.items() if lp.info.proc and lp.info.proc.poll() is None]
                self.trainer_status_lbl.config(text=f"running: {', '.join(running)}" if running else "(no trainers running)")
            except Exception:
                pass
        except Exception:
            pass

        # Also reset the runner-ready gate file (best-effort)
        try:
            with open(self.runner_ready_path, "w", encoding="utf-8") as f:
                json.dump({"timestamp": time.time(), "ready": False, "stage": "stopped"}, f)
        except Exception:
            pass


    def _on_neural_level_changed(self, event) -> None:
        """
        Immediate chart redraw when neural level bars are dragged.
        Updates the chart flags (ASK, BID, DCA, SELL) on the right side in real-time.
        """
        try:
            # Find which coin was updated by looking at the widget that generated the event
            widget = getattr(event, "widget", None)
            coin = None
            
            # Navigate up to find the NeuralSignalTile and get its coin
            if widget:
                temp = widget
                while temp and coin is None:
                    if hasattr(temp, "coin"):
                        coin = getattr(temp, "coin", None)
                        break
                    try:
                        temp = temp.master
                    except Exception:
                        break
            
            if not coin:
                # If we can't determine the coin, refresh the currently visible chart
                coin = getattr(self, "_current_chart_page", None)
            
            if coin:
                coin = str(coin).strip().upper()
                chart = self.charts.get(coin)
                if chart:
                    self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)
                    
                    pos = self._last_positions.get(coin, {}) if isinstance(self._last_positions, dict) else {}
                    buy_px = pos.get("current_buy_price", None)
                    sell_px = pos.get("current_sell_price", None)
                    trail_line = pos.get("trail_line", None)
                    dca_line_price = pos.get("dca_line_price", None)
                    
                    chart.refresh(
                        self.coin_folders,
                        current_buy_price=buy_px,
                        current_sell_price=sell_px,
                        trail_line=trail_line,
                        dca_line_price=dca_line_price,
                    )
                    
                    # Keep the periodic refresh behavior consistent
                    self._last_chart_refresh = time.time()
        except Exception:
            pass
    
    def _on_timeframe_changed(self, event) -> None:
        """
        Immediate redraw when the user changes a timeframe in any CandleChart.
        Avoids waiting for the chart_refresh_seconds throttle in _tick().
        """
        try:
            chart = getattr(event, "widget", None)
            if not isinstance(chart, CandleChart):
                return

            coin = getattr(chart, "coin", None)
            if not coin:
                return

            self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)

            pos = self._last_positions.get(coin, {}) if isinstance(self._last_positions, dict) else {}
            buy_px = pos.get("current_buy_price", None)
            sell_px = pos.get("current_sell_price", None)
            trail_line = pos.get("trail_line", None)
            dca_line_price = pos.get("dca_line_price", None)

            chart.refresh(
                self.coin_folders,
                current_buy_price=buy_px,
                current_sell_price=sell_px,
                trail_line=trail_line,
                dca_line_price=dca_line_price,
            )

            # Keep the periodic refresh behavior consistent (prevents an immediate full refresh right after this).
            self._last_chart_refresh = time.time()
        except Exception:
            pass

        # Periodically detect sash position changes and persist them.
        try:
            try:
                current = self._read_current_sashes()
                if current and current != getattr(self, "_last_saved_sashes", {}):
                    try:
                        # Update snapshot and save
                        self._last_saved_sashes = dict(current)
                        self._save_current_sashes()
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    # ---- refresh loop ----
    def _drain_queue_to_text(self, q: "queue.Queue[str]", txt: tk.Text, max_lines: int = 2500) -> None:

        try:
            changed = False
            while True:
                line = q.get_nowait()
                txt.insert("end", line + "\n")
                changed = True
        except queue.Empty:
            pass
        except Exception:
            pass

        if changed:
            # trim very old lines
            try:
                current = int(txt.index("end-1c").split(".")[0])
                if current > max_lines:
                    txt.delete("1.0", f"{current - max_lines}.0")
            except Exception:
                pass
            txt.see("end")


    def _toggle_maximize(self) -> None:
        """Toggle window maximize/fullscreen state (bound to F11)."""
        try:
            # Try WM state toggling first
            st = str(self.state() or "")
            if st == "normal":
                try:
                    self.state("zoomed")
                    return
                except Exception:
                    pass

            if st == "zoomed":
                try:
                    self.state("normal")
                    return
                except Exception:
                    pass

            # Fallback: toggle fullscreen attribute
            cur = bool(self.attributes("-fullscreen") if "-fullscreen" in self.attributes() else False)
            self.attributes("-fullscreen", not cur)
        except Exception:
            try:
                # best-effort fallback
                self.attributes("-fullscreen", True)
            except Exception:
                pass

    def _tick(self) -> None:
        # process labels
        neural_running = bool(self.proc_neural.proc and self.proc_neural.proc.poll() is None)
        trader_running = bool(self.proc_trader.proc and self.proc_trader.proc.poll() is None)

        self.lbl_neural.config(text=f"Neural: {'running' if neural_running else 'stopped'}")
        self.lbl_trader.config(text=f"Trader: {'running' if trader_running else 'stopped'}")

        # --- flow gating: Train -> Start All ---
        status_map = self._training_status_map()
        all_trained = all(v == "TRAINED" for v in status_map.values()) if status_map else False

        # Update training progress bar (with mtime caching to avoid redundant I/O)
        try:
            if hasattr(self, "training_progress") and hasattr(self, "training_progress_label"):
                if not hasattr(self, "_trainer_status_cache"):
                    self._trainer_status_cache = {}  # {coin: {"mtime": float, "data": dict}}
                
                total_coins = len(status_map) if status_map else 1
                trained_count = sum(1 for v in status_map.values() if v == "TRAINED") if status_map else 0
                training_count = sum(1 for v in status_map.values() if v == "TRAINING") if status_map else 0
                
                # Calculate overall progress including partial progress of training coins
                total_progress = float(trained_count)
                training_details = []
                for c in self.coins:
                    if status_map.get(c) == "TRAINING":
                        try:
                            folder = self.coin_folders.get(c, self.project_dir)
                            status_file = os.path.join(folder, "trainer_status.json")
                            
                            # Check mtime before reading (massive I/O savings)
                            if os.path.exists(status_file):
                                try:
                                    mtime = os.path.getmtime(status_file)
                                    cached = self._trainer_status_cache.get(c, {})
                                    if cached.get("mtime") == mtime and "data" in cached:
                                        st = cached["data"]
                                    else:
                                        with open(status_file, "r", encoding="utf-8") as f:
                                            st = json.load(f)
                                        self._trainer_status_cache[c] = {"mtime": mtime, "data": st}
                                except Exception:
                                    st = {}
                                
                                coin_progress = int(st.get("progress_pct", 0)) if st and isinstance(st, dict) else 0
                                coin_progress = max(0, min(100, coin_progress))  # Clamp to 0-100
                                total_progress += (coin_progress / 100.0)
                                if coin_progress > 0:
                                    training_details.append(f"{c} {coin_progress}%")
                                else:
                                    training_details.append(f"{c} 0%")
                            else:
                                training_details.append(f"{c} starting...")
                        except Exception as e:
                            training_details.append(f"{c} 0%")
                
                progress_pct = min(100, max(0, int((total_progress / total_coins) * 100))) if total_coins > 0 else 0
                try:
                    self.training_progress["value"] = progress_pct
                except Exception:
                    pass
                
                if training_count > 0:
                    details = ", ".join(training_details) if training_details else f"{training_count} in progress"
                    self.training_progress_label.config(text=f"Training: {progress_pct}% ({details})")
                elif progress_pct == 100:
                    self.training_progress_label.config(text=f"Training: {progress_pct}% (Complete)")
                else:
                    self.training_progress_label.config(text=f"Training Progress: {progress_pct}% ({total_coins - trained_count} not trained)")
        except Exception:
            pass

        # Auto-start runner after training completes if flag is set (with 5ms delays between steps)
        if all_trained and self._auto_start_runner_after_training:
            self._auto_start_runner_after_training = False
            self._auto_start_trader_pending = True
            # Wait 5ms after training completes, then start neural
            self.after(5, self._start_neural_then_trader)

        # Start All and Stop All buttons are always enabled
        try:
            self.btn_start_all.configure(state="normal")
            self.btn_stop_all.configure(state="normal")
        except Exception:
            pass

        # Training overview + per-coin list
        try:
            training_running = [c for c, s in status_map.items() if s == "TRAINING"]
            not_trained = [c for c, s in status_map.items() if s == "NOT TRAINED"]

            if training_running:
                self.lbl_training_overview.config(text=f"Training: RUNNING ({', '.join(training_running)})")
            elif not_trained:
                self.lbl_training_overview.config(text=f"Training: REQUIRED ({len(not_trained)} not trained)")
            else:
                self.lbl_training_overview.config(text="Training: READY (all trained)")

            # show each coin status with progress for training coins (ONLY redraw if changed)
            # Reuse cached data from above to avoid duplicate file reads
            progress_map = {}
            for c in self.coins:
                if status_map.get(c) == "TRAINING":
                    try:
                        if hasattr(self, "_trainer_status_cache"):
                            cached = self._trainer_status_cache.get(c, {})
                            st = cached.get("data", {})
                            progress_map[c] = st.get("progress_pct", 0) if st else 0
                        else:
                            folder = self.coin_folders.get(c, self.project_dir)
                            st = _safe_read_json(os.path.join(folder, "trainer_status.json"))
                            progress_map[c] = st.get("progress_pct", 0) if st else 0
                    except Exception:
                        progress_map[c] = 0
            
            sig = tuple((c, status_map.get(c, "N/A"), progress_map.get(c, 0)) for c in self.coins)
            if getattr(self, "_last_training_sig", None) != sig:
                self._last_training_sig = sig
                self.training_list.delete(0, "end")
                for c, st, pct in sig:
                    if st == "TRAINING" and pct > 0:
                        self.training_list.insert("end", f"{c}: {st} ({pct}%)")
                    else:
                        self.training_list.insert("end", f"{c}: {st}")

            # show gating hint (Start All handles the runner->ready->trader sequence)
            if not all_trained:
                self.lbl_flow_hint.config(text="Flow: Train All → then Start All")
            elif self._auto_start_trader_pending:
                self.lbl_flow_hint.config(text="Flow: Starting runner → waiting for ready → trader will auto-start")
            elif neural_running or trader_running:
                self.lbl_flow_hint.config(text="Flow: Running (use the button to stop)")
            else:
                self.lbl_flow_hint.config(text="Flow: Start All")
        except Exception:
            pass

        # neural overview bars (mtime-cached inside)
        self._refresh_neural_overview()

        # trader status -> current trades table (now mtime-cached inside)
        self._refresh_trader_status()

        # pnl ledger -> realized profit (now mtime-cached inside)
        self._refresh_pnl()

        # trade history (now mtime-cached inside)
        self._refresh_trade_history()


        # charts (throttle)
        now = time.time()
        if (now - self._last_chart_refresh) >= float(self.settings.get("chart_refresh_seconds", 10.0)):
            # account value chart (internally mtime-cached already)
            try:
                if self.account_chart:
                    self.account_chart.refresh()
            except Exception:
                pass

            # Only rebuild coin_folders when inputs change (avoids directory scans every refresh)
            try:
                cf_sig = (self.settings.get("main_neural_dir"), tuple(self.coins))
                if getattr(self, "_coin_folders_sig", None) != cf_sig:
                    self._coin_folders_sig = cf_sig
                    self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)
            except Exception:
                try:
                    self.coin_folders = build_coin_folders(self.settings["main_neural_dir"], self.coins)
                except Exception:
                    pass

            # Refresh ONLY the currently visible coin tab (prevents O(N_coins) network/plot stalls)
            selected_tab = None

            # Primary: our custom chart pages (multi-row tab buttons)
            try:
                selected_tab = getattr(self, "_current_chart_page", None)
            except Exception:
                selected_tab = None

            # Fallback: old notebook-based UI (if it exists)
            if not selected_tab:
                try:
                    if hasattr(self, "nb") and self.nb:
                        selected_tab = self.nb.tab(self.nb.select(), "text")
                except Exception:
                    selected_tab = None

            if selected_tab and str(selected_tab).strip().upper() != "ACCOUNT":
                coin = str(selected_tab).strip().upper()
                chart = self.charts.get(coin)
                if chart:
                    pos = self._last_positions.get(coin, {}) if isinstance(self._last_positions, dict) else {}
                    buy_px = pos.get("current_buy_price", None)
                    sell_px = pos.get("current_sell_price", None)
                    trail_line = pos.get("trail_line", None)
                    dca_line_price = pos.get("dca_line_price", None)
                    try:
                        chart.refresh(
                            self.coin_folders,
                            current_buy_price=buy_px,
                            current_sell_price=sell_px,
                            trail_line=trail_line,
                            dca_line_price=dca_line_price,
                        )
                    except Exception:
                        pass


            self._last_chart_refresh = now

        # drain logs into panes
        self._drain_queue_to_text(self.runner_log_q, self.runner_text)
        self._drain_queue_to_text(self.trader_log_q, self.trader_text)

        # trainer logs: show selected trainer output
        try:
            sel = (self.trainer_coin_var.get() or "").strip().upper()
            running = [c for c, lp in self.trainers.items() if lp.info.proc and lp.info.proc.poll() is None]
            self.trainer_status_lbl.config(text=f"running: {', '.join(running)}" if running else "(no trainers running)")

            lp = self.trainers.get(sel)
            if lp:
                self._drain_queue_to_text(lp.log_q, self.trainer_text)
        except Exception:
            pass

        self.status.config(text=f"{_now_str()} | hub_dir={self.hub_dir}")
        self.after(int(float(self.settings.get("ui_refresh_seconds", 1.0)) * 1000), self._tick)



    def _refresh_trader_status(self) -> None:
        # mtime cache: rebuilding the whole tree every tick is expensive with many rows
        try:
            mtime = os.path.getmtime(self.trader_status_path)
        except Exception:
            mtime = None

        if getattr(self, "_last_trader_status_mtime", object()) == mtime:
            return
        self._last_trader_status_mtime = mtime

        data = _safe_read_json(self.trader_status_path)
        if not data:
            self.lbl_last_status.config(text="Last status: N/A (no trader_status.json yet)")

            # account summary (right-side status area)
            try:
                self.lbl_acct_total_value.config(text="Total Account Value: N/A")
                self.lbl_acct_holdings_value.config(text="Holdings Value: N/A")
                self.lbl_acct_buying_power.config(text="Buying Power: N/A")
                self.lbl_acct_percent_in_trade.config(text="Percent In Trade: N/A")

                # DCA affordability
                self.lbl_acct_dca_spread.config(text="DCA Levels (spread): N/A")
                self.lbl_acct_dca_single.config(text="DCA Levels (single): N/A")
            except Exception:
                pass

            # clear tree (once; subsequent ticks are mtime-short-circuited)
            for iid in self.trades_tree.get_children():
                self.trades_tree.delete(iid)
            return



        ts = data.get("timestamp")
        try:
            if isinstance(ts, (int, float)):
                self.lbl_last_status.config(text=f"Last status: {time.strftime('%H:%M:%S', time.localtime(ts))}")
            else:
                self.lbl_last_status.config(text="Last status: (unknown timestamp)")
        except Exception:
            self.lbl_last_status.config(text="Last status: (timestamp parse error)")

        # Update trader uptime (if we started the trader process via the hub)
        try:
            start_time = getattr(self.proc_trader, "start_time", None)
            if self.proc_trader.proc and (self.proc_trader.proc.poll() is None) and start_time is not None:
                elapsed = time.time() - float(start_time)
                self.lbl_trader_uptime.config(text=f"Trader uptime: {_fmt_uptime(elapsed)}")
            else:
                # If trader isn't running or we don't have a start_time, indicate stopped
                self.lbl_trader_uptime.config(text="Trader uptime: stopped")
        except Exception:
            try:
                self.lbl_trader_uptime.config(text="Trader uptime: N/A")
            except Exception:
                pass

        # --- account summary (same info the trader prints above current trades) ---
        acct = data.get("account", {}) or {}
        try:
            total_val = float(acct.get("total_account_value", 0.0) or 0.0)

            self.lbl_acct_total_value.config(
                text=f"Total Account Value: {_fmt_money(acct.get('total_account_value', 0.0) or 0.0)}"
            )
            self.lbl_acct_holdings_value.config(
                text=f"Holdings Value: {_fmt_money(acct.get('holdings_sell_value', 0.0) or 0.0)}"
            )
            
            # Buying power with deficit warning in red
            buying_power = acct.get('buying_power', 0.0) or 0.0
            bp_text = f"Buying Power: {_fmt_money(buying_power)}"
            is_deficit = False
            try:
                if buying_power is not None and float(buying_power) < 0:
                    bp_text += " ***Deficit**"
                    is_deficit = True
            except Exception:
                pass
            self.lbl_acct_buying_power.config(
                text=bp_text,
                foreground="red" if is_deficit else DARK_FG
            )

            pit = acct.get("percent_in_trade", 0.0)
            try:
                pit_txt = f"{float(pit or 0.0):.2f}%"
            except Exception:
                pit_txt = "N/A"
            self.lbl_acct_percent_in_trade.config(text=f"Percent In Trade: {pit_txt}")

            # -------------------------
            # DCA affordability
            # - Entry allocation mirrors pt_trader.py: total_val * (0.00005 / N) with min $0.50
            # - Each DCA buy mirrors pt_trader.py: dca_amount = value * 2  (=> total scales ~3x per DCA)
            # -------------------------
            coins = getattr(self, "coins", None) or []
            n = len(coins) if len(coins) > 0 else 1

            spread_levels = 0
            single_levels = 0

            if total_val > 0.0:
                # Spread across all coins
                alloc_spread = total_val * (0.00005 / n)
                if alloc_spread < 0.5:
                    alloc_spread = 0.5

                required = alloc_spread * n  # initial buys for all coins
                while required > 0.0 and (required * 3.0) <= (total_val + 1e-9):
                    required *= 3.0
                    spread_levels += 1

                # All DCA into a single coin
                alloc_single = total_val * 0.00005
                if alloc_single < 0.5:
                    alloc_single = 0.5

                required = alloc_single  # initial buy for one coin
                while required > 0.0 and (required * 3.0) <= (total_val + 1e-9):
                    required *= 3.0
                    single_levels += 1

            # Show labels + number (one line each)
            self.lbl_acct_dca_spread.config(text=f"DCA Levels (spread): {spread_levels}")
            self.lbl_acct_dca_single.config(text=f"DCA Levels (single): {single_levels}")


        except Exception:
            pass


        positions = data.get("positions", {}) or {}
        self._last_positions = positions

        # --- precompute per-coin DCA count in rolling 24h (and after last SELL for that coin) ---
        dca_24h_by_coin: Dict[str, int] = {}
        try:
            now = time.time()
            window_floor = now - (24 * 3600)

            trades = _read_trade_history_jsonl(self.trade_history_path) if self.trade_history_path else []

            last_sell_ts: Dict[str, float] = {}
            for tr in trades:
                sym = str(tr.get("symbol", "")).upper().strip()
                base = sym.split("-")[0].strip() if sym else ""
                if not base:
                    continue

                side = str(tr.get("side", "")).lower().strip()
                if side != "sell":
                    continue

                try:
                    tsf = float(tr.get("ts", 0))
                except Exception:
                    continue

                prev = float(last_sell_ts.get(base, 0.0))
                if tsf > prev:
                    last_sell_ts[base] = tsf

            for tr in trades:
                sym = str(tr.get("symbol", "")).upper().strip()
                base = sym.split("-")[0].strip() if sym else ""
                if not base:
                    continue

                side = str(tr.get("side", "")).lower().strip()
                if side != "buy":
                    continue

                tag = str(tr.get("tag") or "").upper().strip()
                if tag != "DCA":
                    continue

                try:
                    tsf = float(tr.get("ts", 0))
                except Exception:
                    continue

                start_ts = max(window_floor, float(last_sell_ts.get(base, 0.0)))
                if tsf >= start_ts:
                    dca_24h_by_coin[base] = int(dca_24h_by_coin.get(base, 0)) + 1
        except Exception:
            dca_24h_by_coin = {}

        # rebuild tree (only when file changes)
        for iid in self.trades_tree.get_children():
            self.trades_tree.delete(iid)

        for sym, pos in positions.items():
            coin = sym
            qty = pos.get("quantity", 0.0)

            # Hide "not in trade" rows (0 qty), but keep them in _last_positions for chart overlays
            try:
                if float(qty) <= 0.0:
                    continue
            except Exception:
                continue

            value = pos.get("value_usd", 0.0)
            avg_cost = pos.get("avg_cost_basis", 0.0)

            buy_price = pos.get("current_buy_price", 0.0)
            buy_pnl = pos.get("gain_loss_pct_buy", 0.0)

            sell_price = pos.get("current_sell_price", 0.0)
            sell_pnl = pos.get("gain_loss_pct_sell", 0.0)

            dca_stages = pos.get("dca_triggered_stages", 0)
            dca_24h = int(dca_24h_by_coin.get(str(coin).upper().strip(), 0))
            next_dca = pos.get("next_dca_display", "")

            trail_line = pos.get("trail_line", 0.0)

            self.trades_tree.insert(
                "",
                "end",
                values=(
                    coin,
                    f"{qty:.8f}".rstrip("0").rstrip("."),
                    _fmt_money(value),       # position value (USD)
                    _fmt_price(avg_cost),    # per-unit price (USD) -> dynamic decimals
                    _fmt_price(buy_price),
                    _fmt_pct(buy_pnl),
                    _fmt_price(sell_price),
                    _fmt_pct(sell_pnl),
                    dca_stages,
                    dca_24h,
                    next_dca,
                    _fmt_price(trail_line),  # trail line is a price level
                ),
            )








    def _refresh_pnl(self) -> None:
        # Check mtime for both ledger and trader status (since we need both for total P&L)
        try:
            ledger_mtime = os.path.getmtime(self.pnl_ledger_path)
        except Exception:
            ledger_mtime = None
        
        try:
            trader_mtime = os.path.getmtime(self.trader_status_path)
        except Exception:
            trader_mtime = None
        
        cache_key = (ledger_mtime, trader_mtime)
        if getattr(self, "_last_pnl_cache_key", object()) == cache_key:
            return
        self._last_pnl_cache_key = cache_key

        # Get realized P&L from ledger
        realized_pnl = 0.0
        data = _safe_read_json(self.pnl_ledger_path)
        if data:
            realized_pnl = float(data.get("total_realized_profit_usd", 0.0))
        
        # Calculate unrealized P&L from open positions
        unrealized_pnl = 0.0
        try:
            trader_data = _safe_read_json(self.trader_status_path)
            if trader_data:
                positions = trader_data.get("positions", {})
                for sym, pos in positions.items():
                    try:
                        qty = float(pos.get("quantity", 0.0))
                        if qty <= 0.0:
                            continue
                        
                        avg_cost = float(pos.get("avg_cost_basis", 0.0))
                        current_price = float(pos.get("current_sell_price", 0.0))
                        
                        if avg_cost > 0.0 and current_price > 0.0:
                            unrealized_pnl += (current_price - avg_cost) * qty
                    except Exception:
                        continue
        except Exception:
            pass
        
        # Total P&L = realized + unrealized
        total_pnl = realized_pnl + unrealized_pnl
        self.lbl_pnl.config(text=f"Total P&L: {_fmt_money(total_pnl)}")


    def _refresh_trade_history(self) -> None:
        # mtime cache: avoid reading/parsing/rebuilding the list every tick
        try:
            mtime = os.path.getmtime(self.trade_history_path)
        except Exception:
            mtime = None

        if getattr(self, "_last_trade_history_mtime", object()) == mtime:
            return
        self._last_trade_history_mtime = mtime

        if not os.path.isfile(self.trade_history_path):
            self.hist_list.delete(0, "end")
            self.hist_list.insert("end", "(no trade_history.jsonl yet)")
            return

        # show last N lines
        try:
            with open(self.trade_history_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return

        lines = lines[-250:]  # cap for UI
        self.hist_list.delete(0, "end")
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ts = obj.get("ts", None)
                tss = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if isinstance(ts, (int, float)) else "?"
                side = str(obj.get("side", "")).upper()
                tag = str(obj.get("tag", "") or "").upper()

                sym = obj.get("symbol", "")
                qty = obj.get("qty", "")
                px = obj.get("price", None)
                pnl = obj.get("realized_profit_usd", None)

                pnl_pct = obj.get("pnl_pct", None)

                px_txt = _fmt_price(px) if px is not None else "N/A"

                action = side
                if tag:
                    action = f"{side}/{tag}"

                txt = f"{tss} | {action:10s} {sym:5s} | qty={qty} | px={px_txt}"

                # Show the exact trade-time PnL%:
                # - DCA buys: show the BUY-side PnL (how far below avg cost it was when it bought)
                # - sells: show the SELL-side PnL (how far above/below avg cost it sold)
                show_trade_pnl_pct = None
                if side == "SELL":
                    show_trade_pnl_pct = pnl_pct
                elif side == "BUY" and tag == "DCA":
                    show_trade_pnl_pct = pnl_pct

                if show_trade_pnl_pct is not None:
                    try:
                        txt += f" | pnl@trade={_fmt_pct(float(show_trade_pnl_pct))}"
                    except Exception:
                        txt += f" | pnl@trade={show_trade_pnl_pct}"

                if pnl is not None:
                    try:
                        txt += f" | realized={float(pnl):+.2f}"
                    except Exception:
                        txt += f" | realized={pnl}"

                self.hist_list.insert("end", txt)
            except Exception:
                self.hist_list.insert("end", line)



    def _refresh_coin_dependent_ui(self, prev_coins: List[str]) -> None:
        """
        After settings change: refresh every coin-driven UI element:
          - Training dropdown (Train coin)
          - Trainers tab dropdown (Coin)
          - Chart tabs (Notebook): add/remove tabs to match current coin list
          - Neural overview tiles (new): add/remove tiles to match current coin list
        """
        # Rebuild dependent pieces
        self.coins = [c.upper().strip() for c in (self.settings.get("coins") or []) if c.strip()]
        self.coin_folders = build_coin_folders(self.settings.get("main_neural_dir") or self.project_dir, self.coins)

        # Refresh coin dropdowns (they don't auto-update)
        try:
            # Training pane dropdown
            if hasattr(self, "train_coin_combo") and self.train_coin_combo.winfo_exists():
                self.train_coin_combo["values"] = self.coins
                cur = (self.train_coin_var.get() or "").strip().upper() if hasattr(self, "train_coin_var") else ""
                if self.coins and cur not in self.coins:
                    self.train_coin_var.set(self.coins[0])

            # Trainers tab dropdown
            if hasattr(self, "trainer_coin_combo") and self.trainer_coin_combo.winfo_exists():
                self.trainer_coin_combo["values"] = self.coins
                cur = (self.trainer_coin_var.get() or "").strip().upper() if hasattr(self, "trainer_coin_var") else ""
                if self.coins and cur not in self.coins:
                    self.trainer_coin_var.set(self.coins[0])

            # Keep both selectors aligned if both exist
            if hasattr(self, "train_coin_var") and hasattr(self, "trainer_coin_var"):
                if self.train_coin_var.get():
                    self.trainer_coin_var.set(self.train_coin_var.get())
        except Exception:
            pass

        # Ensure each coin has an initial trainer_status.json; default to NOT_TRAINED when missing
        try:
            for coin in self.coins:
                try:
                    coin_u = (coin or "").strip().upper()
                    folder = self.coin_folders.get(coin_u) or self.coin_folders.get(coin) or self.project_dir
                    if not folder:
                        continue
                    status_path = os.path.join(folder, "trainer_status.json")
                    if not os.path.isfile(status_path):
                        st = {"state": "NOT_TRAINED"}
                        try:
                            os.makedirs(folder, exist_ok=True)
                        except Exception:
                            pass
                        try:
                            with open(status_path, "w", encoding="utf-8") as f:
                                json.dump(st, f)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        # Rebuild neural overview tiles (if the widget exists)
        try:
            if hasattr(self, "neural_wrap") and self.neural_wrap.winfo_exists():
                self._rebuild_neural_overview()
                self._refresh_neural_overview()
        except Exception:
            pass

        # Rebuild chart tabs if the coin list changed
        try:
            prev_set = set([str(c).strip().upper() for c in (prev_coins or []) if str(c).strip()])
            if prev_set != set(self.coins):
                self._rebuild_coin_chart_tabs()
        except Exception:
            pass


    def _rebuild_neural_overview(self) -> None:
        """
        Recreate the coin tiles in the left-side Neural Signals box to match self.coins.
        Uses WrapFrame so it automatically breaks into multiple rows.
        Adds hover highlighting and click-to-open chart.
        """
        if not hasattr(self, "neural_wrap") or self.neural_wrap is None:
            return

        # Clear old tiles
        try:
            if hasattr(self.neural_wrap, "clear"):
                self.neural_wrap.clear(destroy_widgets=True)
            else:
                for ch in list(self.neural_wrap.winfo_children()):
                    ch.destroy()
        except Exception:
            pass

        self.neural_tiles = {}

        for coin in (self.coins or []):
            tile = NeuralSignalTile(self.neural_wrap, coin)

            # --- Hover highlighting (real, visible) ---
            def _on_enter(_e=None, t=tile):
                try:
                    t.set_hover(True)
                except Exception:
                    pass

            def _on_leave(_e=None, t=tile):
                # Avoid flicker: when moving between child widgets, ignore "leave" if pointer is still inside tile.
                try:
                    x = t.winfo_pointerx()
                    y = t.winfo_pointery()
                    w = t.winfo_containing(x, y)
                    while w is not None:
                        if w == t:
                            return
                        w = getattr(w, "master", None)
                except Exception:
                    pass

                try:
                    t.set_hover(False)
                except Exception:
                    pass

            tile.bind("<Enter>", _on_enter, add="+")
            tile.bind("<Leave>", _on_leave, add="+")
            try:
                for w in tile.winfo_children():
                    w.bind("<Enter>", _on_enter, add="+")
                    w.bind("<Leave>", _on_leave, add="+")
            except Exception:
                pass

            # --- Click: open chart page ---
            def _open_coin_chart(_e=None, c=coin):
                try:
                    fn = getattr(self, "_show_chart_page", None)
                    if callable(fn):
                        fn(str(c).strip().upper())
                except Exception:
                    pass

            # Bind click to tile and labels, but NOT to canvas (canvas has drag handlers)
            tile.bind("<Button-1>", _open_coin_chart, add="+")
            try:
                for w in tile.winfo_children():
                    # Skip the canvas - it has its own drag handlers
                    if not isinstance(w, tk.Canvas):
                        w.bind("<Button-1>", _open_coin_chart, add="+")
            except Exception:
                pass

            self.neural_wrap.add(tile, padx=(0, 6), pady=(0, 6))
            self.neural_tiles[coin] = tile

        # Layout and scrollbar refresh
        try:
            self.neural_wrap._schedule_reflow()
        except Exception:
            pass

        try:
            fn = getattr(self, "_update_neural_overview_scrollbars", None)
            if callable(fn):
                self.after_idle(fn)
        except Exception:
            pass






    def _refresh_neural_overview(self) -> None:
        """
        Update each coin tile with long/short neural signals.
        Uses mtime caching so it's cheap to call every UI tick.
        """
        if not hasattr(self, "neural_tiles"):
            return

        # Keep coin_folders aligned with current settings/coins
        try:
            sig = (str(self.settings.get("main_neural_dir") or ""), tuple(self.coins or []))
            if getattr(self, "_coin_folders_sig", None) != sig:
                self._coin_folders_sig = sig
                self.coin_folders = build_coin_folders(self.settings.get("main_neural_dir") or self.project_dir, self.coins)
        except Exception:
            pass

        if not hasattr(self, "_neural_overview_cache"):
            self._neural_overview_cache = {}  # path -> (mtime, value)

        def _cached(path: str, loader, default: Any):
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                return default, None

            hit = self._neural_overview_cache.get(path)
            if hit and hit[0] == mtime:
                return hit[1], mtime

            v = loader(path)
            self._neural_overview_cache[path] = (mtime, v)
            return v, mtime

        def _load_short_from_memory_json(path: str) -> int:
            try:
                obj = _safe_read_json(path) or {}
                return int(float(obj.get("short_dca_signal", 0)))
            except Exception:
                return 0

        latest_ts = None

        for coin, tile in list(self.neural_tiles.items()):
            folder = ""
            try:
                folder = (self.coin_folders or {}).get(coin, "")
            except Exception:
                folder = ""

            if not folder or not os.path.isdir(folder):
                tile.set_values(0, 0)
                continue

            long_sig = 0
            short_sig = 0
            mt_candidates: List[float] = []

            # Long signal (check .market subfolder)
            market_dir = os.path.join(folder, ".market")
            long_path = os.path.join(market_dir, "long_dca_signal.txt")
            if os.path.isfile(long_path):
                long_sig, mt = _cached(long_path, read_int_from_file, 0)
                if mt:
                    mt_candidates.append(float(mt))

            # Short signal (prefer txt in .market; fallback to memory.json in main folder)
            short_txt = os.path.join(market_dir, "short_dca_signal.txt")
            if os.path.isfile(short_txt):
                short_sig, mt = _cached(short_txt, read_int_from_file, 0)
                if mt:
                    mt_candidates.append(float(mt))
            else:
                mem = os.path.join(folder, "memory.json")
                if os.path.isfile(mem):
                    short_sig, mt = _cached(mem, _load_short_from_memory_json, 0)
                    if mt:
                        mt_candidates.append(float(mt))

            tile.set_values(long_sig, short_sig)

            if mt_candidates:
                mx = max(mt_candidates)
                latest_ts = mx if (latest_ts is None or mx > latest_ts) else latest_ts

        # Update "Last:" label
        try:
            if hasattr(self, "lbl_neural_overview_last") and self.lbl_neural_overview_last.winfo_exists():
                if latest_ts:
                    self.lbl_neural_overview_last.config(
                        text=f"Last: {time.strftime('%H:%M:%S', time.localtime(float(latest_ts)))}"
                    )
                else:
                    self.lbl_neural_overview_last.config(text="Last: N/A")
        except Exception:
            pass



    def _rebuild_coin_chart_tabs(self) -> None:
        """
        Ensure the Charts multi-row tab bar + pages match self.coins.
        Keeps the ACCOUNT page intact and preserves the currently selected page when possible.
        """
        charts_frame = getattr(self, "_charts_frame", None)
        if charts_frame is None or (hasattr(charts_frame, "winfo_exists") and not charts_frame.winfo_exists()):
            return

        # Remember selected page (coin or ACCOUNT)
        selected = getattr(self, "_current_chart_page", "ACCOUNT")
        if selected not in (["ACCOUNT"] + list(self.coins)):
            selected = "ACCOUNT"

        # Destroy existing tab bar + pages container (clean rebuild)
        try:
            if hasattr(self, "chart_tabs_bar") and self.chart_tabs_bar.winfo_exists():
                self.chart_tabs_bar.destroy()
        except Exception:
            pass

        try:
            if hasattr(self, "chart_pages_container") and self.chart_pages_container.winfo_exists():
                self.chart_pages_container.destroy()
        except Exception:
            pass

        # Recreate - side-by-side layout: tabs on left, charts on right
        charts_layout = ttk.Frame(charts_frame)
        charts_layout.pack(fill="both", expand=True, padx=6, pady=6)

        # LEFT: Tabs bar (vertical stack of buttons)
        tabs_viewport = ttk.Frame(charts_layout)
        tabs_viewport.pack(side="left", fill="y", padx=(0, 6))

        # Use WrapFrame in vertical orientation for stacked tab buttons
        self.chart_tabs_bar = WrapFrame(tabs_viewport, orientation="vertical")
        self.chart_tabs_bar.pack(fill="both", expand=True)

        # Update function to ensure tabs are laid out properly
        def _update_tabs_layout(event=None) -> None:
            try:
                self.chart_tabs_bar._schedule_reflow()
            except Exception:
                pass

        self.chart_tabs_bar.bind("<Configure>", _update_tabs_layout, add="+")

        # RIGHT: Page container for charts (fills remaining space)
        self.chart_pages_container = ttk.Frame(charts_layout)
        self.chart_pages_container.pack(side="right", fill="both", expand=True)

        self._chart_tab_buttons = {}
        self.chart_pages = {}
        self._current_chart_page = selected

        def _show_page(name: str) -> None:
            self._current_chart_page = name
            for f in self.chart_pages.values():
                try:
                    f.pack_forget()
                except Exception:
                    pass
            f = self.chart_pages.get(name)
            if f is not None:
                f.pack(fill="both", expand=True)

            for txt, b in self._chart_tab_buttons.items():
                try:
                    b.configure(style=("ChartTabSelected.TButton" if txt == name else "ChartTab.TButton"))
                except Exception:
                    pass

        self._show_chart_page = _show_page

        # ACCOUNT page
        acct_page = ttk.Frame(self.chart_pages_container)
        self.chart_pages["ACCOUNT"] = acct_page

        acct_btn = ttk.Button(
            self.chart_tabs_bar,
            text="ACCOUNT",
            style="ChartTab.TButton",
            command=lambda: self._show_chart_page("ACCOUNT"),
        )
        self.chart_tabs_bar.add(acct_btn, padx=(0, 6), pady=(0, 6))
        self._chart_tab_buttons["ACCOUNT"] = acct_btn

        self.account_chart = AccountValueChart(
            acct_page,
            self.account_value_history_path,
            self.trade_history_path,
        )
        self.account_chart.pack(fill="both", expand=True)

        # Coin pages
        self.charts = {}
        for coin in self.coins:
            page = ttk.Frame(self.chart_pages_container)
            self.chart_pages[coin] = page

            btn = ttk.Button(
                self.chart_tabs_bar,
                text=coin,
                style="ChartTab.TButton",
                command=lambda c=coin: self._show_chart_page(c),
            )
            self.chart_tabs_bar.add(btn, padx=(0, 6), pady=(0, 6))
            self._chart_tab_buttons[coin] = btn

            chart = CandleChart(page, self.fetcher, coin, self._settings_getter, self.trade_history_path)
            chart.pack(fill="both", expand=True)
            self.charts[coin] = chart

        # Restore selection
        self._show_chart_page(selected)




    # ---- settings dialog ----

    def open_settings_dialog(self) -> None:

        win = tk.Toplevel(self)
        win.title("Settings")
        # Big enough for the bottom buttons on most screens + still scrolls if someone resizes smaller.
        win.geometry("860x680")
        win.minsize(760, 560)
        win.configure(bg=DARK_BG)

        # Scrollable settings content (auto-hides the scrollbar if everything fits),
        # using the same pattern as the Neural Levels scrollbar.
        viewport = ttk.Frame(win)
        viewport.pack(fill="both", expand=True, padx=12, pady=12)
        viewport.grid_rowconfigure(0, weight=1)
        viewport.grid_columnconfigure(0, weight=1)

        settings_canvas = tk.Canvas(
            viewport,
            bg=DARK_BG,
            highlightthickness=1,
            highlightbackground=DARK_BORDER,
            bd=0,
        )
        settings_canvas.grid(row=0, column=0, sticky="nsew")

        settings_scroll = ttk.Scrollbar(
            viewport,
            orient="vertical",
            command=settings_canvas.yview,
        )
        settings_scroll.grid(row=0, column=1, sticky="ns")

        settings_canvas.configure(yscrollcommand=settings_scroll.set)

        frm = ttk.Frame(settings_canvas)
        settings_window = settings_canvas.create_window((0, 0), window=frm, anchor="nw")

        def _update_settings_scrollbars(event=None) -> None:
            """Update scrollregion + hide/show the scrollbar depending on overflow."""
            try:
                c = settings_canvas
                win_id = settings_window

                c.update_idletasks()
                bbox = c.bbox(win_id)
                if not bbox:
                    settings_scroll.grid_remove()
                    return

                c.configure(scrollregion=bbox)
                content_h = int(bbox[3] - bbox[1])
                view_h = int(c.winfo_height())

                if content_h > (view_h + 1):
                    settings_scroll.grid()
                else:
                    settings_scroll.grid_remove()
                    try:
                        c.yview_moveto(0)
                    except Exception:
                        pass
            except Exception:
                pass

        def _on_settings_canvas_configure(e) -> None:
            # Keep the inner frame exactly the canvas width so wrapping is correct.
            try:
                settings_canvas.itemconfigure(settings_window, width=int(e.width))
            except Exception:
                pass
            _update_settings_scrollbars()

        settings_canvas.bind("<Configure>", _on_settings_canvas_configure, add="+")
        frm.bind("<Configure>", _update_settings_scrollbars, add="+")

        # Enhanced touchpad/mousewheel support
        def _on_mousewheel(e):
            """Handle mouse wheel and touchpad scrolling events."""
            try:
                if settings_scroll.winfo_ismapped():
                    # Windows/Mac mousewheel: delta is typically ±120
                    # Adjust sensitivity: smaller divisor = more sensitive
                    scroll_units = int(-1 * (e.delta / 120)) if e.delta else 0
                    if scroll_units != 0:
                        settings_canvas.yview_scroll(scroll_units, "units")
            except Exception:
                pass

        def _on_linux_scroll(e, direction):
            """Handle Linux scroll events (Button-4 and Button-5)."""
            try:
                if settings_scroll.winfo_ismapped():
                    settings_canvas.yview_scroll(direction, "units")
            except Exception:
                pass

        settings_canvas.bind("<MouseWheel>", _on_mousewheel, add="+")  # Windows / Mac / Touchpad
        settings_canvas.bind("<Button-4>", lambda _e: _on_linux_scroll(_e, -3), add="+")  # Linux scroll up
        settings_canvas.bind("<Button-5>", lambda _e: _on_linux_scroll(_e, 3), add="+")   # Linux scroll down
        
        # Ensure canvas focus for scroll events
        settings_canvas.bind("<Enter>", lambda _e: settings_canvas.focus_set(), add="+")

        # Make the entry column expand
        frm.columnconfigure(0, weight=0)  # labels
        frm.columnconfigure(1, weight=1)  # entries
        frm.columnconfigure(2, weight=0)  # browse buttons

        def add_row(r: int, label: str, var: tk.Variable, browse: Optional[str] = None):
            """
            browse: "dir" to attach a directory chooser, else None.
            """
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)

            ent = ttk.Entry(frm, textvariable=var)
            ent.grid(row=r, column=1, sticky="ew", pady=6)

            if browse == "dir":
                def do_browse():
                    picked = filedialog.askdirectory()
                    if picked:
                        var.set(picked)
                ttk.Button(frm, text="Browse", command=do_browse).grid(row=r, column=2, sticky="e", padx=(10, 0), pady=6)
            else:
                # keep column alignment consistent
                ttk.Label(frm, text="").grid(row=r, column=2, sticky="e", padx=(10, 0), pady=6)

        main_dir_var = tk.StringVar(value=self.settings["main_neural_dir"])
        hub_dir_var = tk.StringVar(value=self.settings.get("hub_data_dir", ""))

        neural_script_var = tk.StringVar(value=self.settings["script_neural_runner2"])
        trainer_script_var = tk.StringVar(value=self.settings.get("script_neural_trainer", "pt_trainer.py"))
        trader_script_var = tk.StringVar(value=self.settings["script_trader"])

        ui_refresh_var = tk.StringVar(value=str(self.settings["ui_refresh_seconds"]))
        chart_refresh_var = tk.StringVar(value=str(self.settings["chart_refresh_seconds"]))
        candles_limit_var = tk.StringVar(value=str(self.settings["candles_limit"]))
        auto_start_var = tk.BooleanVar(value=bool(self.settings.get("auto_start_scripts", False)))
        robinhood_var = tk.BooleanVar(value=bool(self.settings.get("use_robinhood_api", False)))
        kucoin_var = tk.BooleanVar(value=bool(self.settings.get("use_kucoin_api", False)))
        
        # Exchange enable/disable flags
        binance_enabled_var = tk.BooleanVar(value=bool(self.settings.get("exchange_binance_enabled", False)))
        kraken_enabled_var = tk.BooleanVar(value=bool(self.settings.get("exchange_kraken_enabled", False)))
        coinbase_enabled_var = tk.BooleanVar(value=bool(self.settings.get("exchange_coinbase_enabled", False)))
        bybit_enabled_var = tk.BooleanVar(value=bool(self.settings.get("exchange_bybit_enabled", False)))
        robinhood_enabled_var = tk.BooleanVar(value=bool(self.settings.get("exchange_robinhood_enabled", False)))
        kucoin_enabled_var = tk.BooleanVar(value=bool(self.settings.get("exchange_kucoin_enabled", False)))

        r = 0
        add_row(r, "Main neural folder:", main_dir_var, browse="dir"); r += 1
        
        # Coin selection with enable/disable checkboxes
        ttk.Label(frm, text="Coins to trade:").grid(row=r, column=0, sticky="nw", padx=(0, 10), pady=6)
        
        coins_frame = ttk.Frame(frm)
        coins_frame.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        
        available_coins = self.settings.get("available_coins", ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "TRX", "DOT", "MATIC", "LINK", "UNI", "SHIB", "LTC"])
        current_coins = [c.upper().strip() for c in self.settings.get("coins", [])]
        
        coin_vars = {}
        for i, coin in enumerate(available_coins):
            var = tk.BooleanVar(value=(coin in current_coins))
            coin_vars[coin] = var
            cb = ttk.Checkbutton(coins_frame, text=coin, variable=var)
            cb.grid(row=i // 5, column=i % 5, sticky="w", padx=8, pady=2)
        
        r += 1
        
        add_row(r, "Hub data dir (optional):", hub_dir_var, browse="dir"); r += 1

        # Neural timeframes selection (independent checkboxes)
        ttk.Label(frm, text="Neural level timeframes:").grid(row=r, column=0, sticky="nw", padx=(0, 10), pady=6)
        
        neural_frame = ttk.Frame(frm)
        neural_frame.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        
        all_tfs = ["1min", "5min", "15min", "30min", "1hour", "2hour", "4hour", "8hour", "12hour", "1day", "1week"]
        current_neural_tfs = self.settings.get("neural_timeframes", ["1hour", "2hour", "4hour", "8hour", "12hour", "1day", "1week"])
        
        neural_tf_vars = {}
        for i, tf in enumerate(all_tfs):
            var = tk.BooleanVar(value=(tf in current_neural_tfs))
            neural_tf_vars[tf] = var
            cb = ttk.Checkbutton(neural_frame, text=tf, variable=var)
            cb.grid(row=i // 4, column=i % 4, sticky="w", padx=4, pady=2)
        
        r += 1
        
        # Neural levels range (0-7)
        ttk.Label(frm, text="Neural levels range:").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
        
        range_frame = ttk.Frame(frm)
        range_frame.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        
        neural_min_var = tk.StringVar(value=str(self.settings.get("neural_levels_min", 0)))
        neural_max_var = tk.StringVar(value=str(self.settings.get("neural_levels_max", 7)))
        
        ttk.Label(range_frame, text="Min (0-7):").pack(side="left", padx=(0, 4))
        ttk.Entry(range_frame, textvariable=neural_min_var, width=5).pack(side="left", padx=(0, 12))
        ttk.Label(range_frame, text="Max (0-7):").pack(side="left", padx=(0, 4))
        ttk.Entry(range_frame, textvariable=neural_max_var, width=5).pack(side="left")
        ttk.Label(range_frame, text="(controls which levels N0-N7 to use)", foreground=DARK_MUTED).pack(side="left", padx=(12, 0))
        
        r += 1

        ttk.Separator(frm, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=10); r += 1

        add_row(r, "pt_thinker.py path:", neural_script_var); r += 1
        add_row(r, "pt_trainer.py path:", trainer_script_var); r += 1
        add_row(r, "pt_trader.py path:", trader_script_var); r += 1

        # --- Robinhood API setup (writes r_key.txt + r_secret.txt used by pt_trader.py) ---
        def _api_paths() -> Tuple[str, str]:
            key_path = os.path.join(self.project_dir, "r_key.txt")
            secret_path = os.path.join(self.project_dir, "r_secret.txt")
            return key_path, secret_path

        def _kucoin_paths() -> Tuple[str, str, str]:
            key_path = os.path.join(self.project_dir, "ku_key.txt")
            secret_path = os.path.join(self.project_dir, "ku_secret.txt")
            pass_path = os.path.join(self.project_dir, "ku_passphrase.txt")
            return key_path, secret_path, pass_path

        def _read_api_files() -> Tuple[str, str]:
            key_path, secret_path = _api_paths()
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    k = (f.read() or "").strip()
            except Exception:
                k = ""
            try:
                with open(secret_path, "r", encoding="utf-8") as f:
                    s = (f.read() or "").strip()
            except Exception:
                s = ""
            return k, s

        def _read_kucoin_files() -> Tuple[str, str, str]:
            k_path, s_path, p_path = _kucoin_paths()
            try:
                with open(k_path, "r", encoding="utf-8") as f:
                    k = (f.read() or "").strip()
            except Exception:
                k = ""
            try:
                with open(s_path, "r", encoding="utf-8") as f:
                    s = (f.read() or "").strip()
            except Exception:
                s = ""
            try:
                with open(p_path, "r", encoding="utf-8") as f:
                    p = (f.read() or "").strip()
            except Exception:
                p = ""
            return k, s, p

        api_status_var = tk.StringVar(value="")
        kucoin_status_var = tk.StringVar(value="")
        binance_status_var = tk.StringVar(value="")
        kraken_status_var = tk.StringVar(value="")
        coinbase_status_var = tk.StringVar(value="")
        bybit_status_var = tk.StringVar(value="")

        def _refresh_api_status() -> None:
            key_path, secret_path = _api_paths()
            k, s = _read_api_files()

            # Respect the enable checkbox in the settings dialog
            try:
                if not bool(robinhood_var.get()):
                    api_status_var.set("Disabled (disabled in settings)")
                    return
            except Exception:
                pass

            missing = []
            if not k:
                missing.append("r_key.txt (API Key)")
            if not s:
                missing.append("r_secret.txt (PRIVATE key)")

            if missing:
                api_status_var.set("Not configured ❌ (missing " + ", ".join(missing) + ")")
            else:
                api_status_var.set("Configured ✅ (credentials found)")

        def _open_api_folder() -> None:
            """Open the folder where r_key.txt / r_secret.txt live."""
            try:
                folder = os.path.abspath(self.project_dir)
                if os.name == "nt":
                    os.startfile(folder)  # type: ignore[attr-defined]
                    return
                if sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                    return
                subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                messagebox.showerror("Couldn't open folder", f"Tried to open:\n{self.project_dir}\n\nError:\n{e}")

        def _clear_api_files() -> None:
            """Delete r_key.txt / r_secret.txt (with a big confirmation)."""
            key_path, secret_path = _api_paths()
            if not messagebox.askyesno(
                "Delete API credentials?",
                "This will delete:\n"
                f"  {key_path}\n"
                f"  {secret_path}\n\n"
                "After deleting, the trader can NOT authenticate until you run the setup wizard again.\n\n"
                "Are you sure you want to delete these files?"
            ):
                return

            try:
                if os.path.isfile(key_path):
                    os.remove(key_path)
                if os.path.isfile(secret_path):
                    os.remove(secret_path)
            except Exception as e:
                messagebox.showerror("Delete failed", f"Couldn't delete the files:\n\n{e}")
                return

            _refresh_api_status()
            messagebox.showinfo("Deleted", "Deleted r_key.txt and r_secret.txt.")

        def _open_robinhood_api_wizard() -> None:
            """
            Beginner-friendly wizard that creates + stores Robinhood Crypto Trading API credentials.

            What we store:
              - r_key.txt    = your Robinhood *API Key* (safe-ish to store, still treat as sensitive)
              - r_secret.txt = your *PRIVATE key* (treat like a password — never share it)
            """
            import webbrowser
            import base64
            import platform
            from datetime import datetime
            import time

            # Friendly dependency errors (laymen-proof)
            try:
                from cryptography.hazmat.primitives.asymmetric import ed25519
                from cryptography.hazmat.primitives import serialization
            except Exception:
                messagebox.showerror(
                    "Missing dependency",
                    "The 'cryptography' package is required for Robinhood API setup.\n\n"
                    "Fix: open a Command Prompt / Terminal in this folder and run:\n"
                    "  pip install cryptography\n\n"
                    "Then re-open this Setup Wizard."
                )
                return

            try:
                import requests  # for the 'Test credentials' button
            except Exception:
                requests = None

            wiz = tk.Toplevel(win)
            wiz.title("Robinhood API Setup")
            # Big enough to show the bottom buttons, but still scrolls if the window is resized smaller.
            wiz.geometry("980x720")
            wiz.minsize(860, 620)
            wiz.configure(bg=DARK_BG)

            # Scrollable content area (same pattern as the Neural Levels scrollbar).
            viewport = ttk.Frame(wiz)
            viewport.pack(fill="both", expand=True, padx=12, pady=12)
            viewport.grid_rowconfigure(0, weight=1)
            viewport.grid_columnconfigure(0, weight=1)

            wiz_canvas = tk.Canvas(
                viewport,
                bg=DARK_BG,
                highlightthickness=1,
                highlightbackground=DARK_BORDER,
                bd=0,
            )
            wiz_canvas.grid(row=0, column=0, sticky="nsew")

            wiz_scroll = ttk.Scrollbar(viewport, orient="vertical", command=wiz_canvas.yview)
            wiz_scroll.grid(row=0, column=1, sticky="ns")
            wiz_canvas.configure(yscrollcommand=wiz_scroll.set)

            container = ttk.Frame(wiz_canvas)
            wiz_window = wiz_canvas.create_window((0, 0), window=container, anchor="nw")
            container.columnconfigure(0, weight=1)

            def _update_wiz_scrollbars(event=None) -> None:
                """Update scrollregion + hide/show the scrollbar depending on overflow."""
                try:
                    c = wiz_canvas
                    win_id = wiz_window

                    c.update_idletasks()
                    bbox = c.bbox(win_id)
                    if not bbox:
                        wiz_scroll.grid_remove()
                        return

                    c.configure(scrollregion=bbox)
                    content_h = int(bbox[3] - bbox[1])
                    view_h = int(c.winfo_height())

                    if content_h > (view_h + 1):
                        wiz_scroll.grid()
                    else:
                        wiz_scroll.grid_remove()
                        try:
                            c.yview_moveto(0)
                        except Exception:
                            pass
                except Exception:
                    pass

            def _on_wiz_canvas_configure(e) -> None:
                # Keep the inner frame exactly the canvas width so labels wrap nicely.
                try:
                    wiz_canvas.itemconfigure(wiz_window, width=int(e.width))
                except Exception:
                    pass
                _update_wiz_scrollbars()

            wiz_canvas.bind("<Configure>", _on_wiz_canvas_configure, add="+")
            container.bind("<Configure>", _update_wiz_scrollbars, add="+")

            def _wheel(e):
                try:
                    if wiz_scroll.winfo_ismapped():
                        wiz_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
                except Exception:
                    pass

            wiz_canvas.bind("<Enter>", lambda _e: wiz_canvas.focus_set(), add="+")
            wiz_canvas.bind("<MouseWheel>", _wheel, add="+")  # Windows / Mac
            wiz_canvas.bind("<Button-4>", lambda _e: wiz_canvas.yview_scroll(-3, "units"), add="+")  # Linux
            wiz_canvas.bind("<Button-5>", lambda _e: wiz_canvas.yview_scroll(3, "units"), add="+")   # Linux


            key_path, secret_path = _api_paths()

            # Load any existing credentials so users can update without re-generating keys.
            existing_api_key, existing_private_b64 = _read_api_files()
            private_b64_state = {"value": (existing_private_b64 or "").strip()}

            # -----------------------------
            # Helpers (open folder, copy, etc.)
            # -----------------------------
            def _open_in_file_manager(path: str) -> None:
                try:
                    p = os.path.abspath(path)
                    if os.name == "nt":
                        os.startfile(p)  # type: ignore[attr-defined]
                        return
                    if sys.platform == "darwin":
                        subprocess.Popen(["open", p])
                        return
                    subprocess.Popen(["xdg-open", p])
                except Exception as e:
                    messagebox.showerror("Couldn't open folder", f"Tried to open:\n{path}\n\nError:\n{e}")

            def _copy_to_clipboard(txt: str, title: str = "Copied") -> None:
                try:
                    wiz.clipboard_clear()
                    wiz.clipboard_append(txt)
                    messagebox.showinfo(title, "Copied to clipboard.")
                except Exception:
                    pass

            def _mask_path(p: str) -> str:
                try:
                    return os.path.abspath(p)
                except Exception:
                    return p

            # -----------------------------
            # Big, beginner-friendly instructions
            # -----------------------------
            intro = (
                "This trader uses Robinhood's Crypto Trading API credentials.\n\n"
                "You only do this once. When finished, pt_trader.py can authenticate automatically.\n\n"
                "✅ What you will do in this window:\n"
                "  1) Generate a Public Key + Private Key (Ed25519).\n"
                "  2) Copy the PUBLIC key and paste it into Robinhood to create an API credential.\n"
                "  3) Robinhood will show you an API Key (usually starts with 'rh...'). Copy it.\n"
                "  4) Paste that API Key back here and click Save.\n\n"
                "🧭 EXACTLY where to paste the Public Key on Robinhood (desktop web is best):\n"
                "  A) Log in to Robinhood on a computer.\n"
                "  B) Click Account (top-right) → Settings.\n"
                "  C) Click Crypto.\n"
                "  D) Scroll down to API Trading and click + Add Key (or Add key).\n"
                "  E) Paste the Public Key into the Public key field.\n"
                "  F) Give it any name (example: PowerTrader).\n"
                "  G) Permissions: this TRADER needs READ + TRADE. (READ-only cannot place orders.)\n"
                "  H) Click Save. Robinhood shows your API Key — copy it right away (it may only show once).\n\n"
                "📱 Mobile note: if you can't find API Trading in the app, use robinhood.com in a browser.\n\n"
                "This wizard will save two files in the same folder as pt_hub.py:\n"
                "  - r_key.txt    (your API Key)\n"
                "  - r_secret.txt (your PRIVATE key in base64)  ← keep this secret like a password\n"
            )

            intro_lbl = ttk.Label(container, text=intro, justify="left")
            intro_lbl.grid(row=0, column=0, sticky="ew", pady=(0, 10))

            top_btns = ttk.Frame(container)
            top_btns.grid(row=1, column=0, sticky="ew", pady=(0, 10))
            top_btns.columnconfigure(0, weight=1)

            def open_robinhood_page():
                # Robinhood entry point. User will still need to click into Settings → Crypto → API Trading.
                webbrowser.open("https://robinhood.com/account/crypto")

            ttk.Button(top_btns, text="Open Robinhood API Credentials page (Crypto)", command=open_robinhood_page).pack(side="left")
            ttk.Button(top_btns, text="Open Robinhood Crypto Trading API docs", command=lambda: webbrowser.open("https://docs.robinhood.com/crypto/trading/")).pack(side="left", padx=8)
            ttk.Button(top_btns, text="Open Folder With r_key.txt / r_secret.txt", command=lambda: _open_in_file_manager(self.project_dir)).pack(side="left", padx=8)

            # -----------------------------
            # Step 1 — Generate keys
            # -----------------------------
            step1 = ttk.LabelFrame(container, text="Step 1 — Generate your keys (click once)")
            step1.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
            step1.columnconfigure(0, weight=1)

            ttk.Label(step1, text="Public Key (this is what you paste into Robinhood):").grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))

            pub_box = tk.Text(step1, height=4, wrap="none")
            pub_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(6, 10))
            pub_box.configure(bg=DARK_PANEL, fg=DARK_FG, insertbackground=DARK_FG)

            def _render_public_from_private_b64(priv_b64: str) -> str:
                """Return Robinhood-compatible Public Key: base64(raw_ed25519_public_key_32_bytes)."""
                try:
                    raw = base64.b64decode(priv_b64)

                    # Accept either:
                    #   - 32 bytes: Ed25519 seed
                    #   - 64 bytes: NaCl/tweetnacl secretKey (seed + public)
                    if len(raw) == 64:
                        seed = raw[:32]
                    elif len(raw) == 32:
                        seed = raw
                    else:
                        return ""

                    pk = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
                    pub_raw = pk.public_key().public_bytes(
                        encoding=serialization.Encoding.Raw,
                        format=serialization.PublicFormat.Raw,
                    )
                    return base64.b64encode(pub_raw).decode("utf-8")
                except Exception:
                    return ""

            def _set_pub_text(txt: str) -> None:
                try:
                    pub_box.delete("1.0", "end")
                    pub_box.insert("1.0", txt or "")
                except Exception:
                    pass

            # If already configured before, show the public key again (derived from stored private key)
            if private_b64_state["value"]:
                _set_pub_text(_render_public_from_private_b64(private_b64_state["value"]))

            def generate_keys():
                # Generate an Ed25519 keypair (Robinhood expects base64 raw public key bytes)
                priv = ed25519.Ed25519PrivateKey.generate()
                pub = priv.public_key()

                seed = priv.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption(),
                )
                pub_raw = pub.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )

                # Store PRIVATE key as base64(seed32) because pt_thinker.py uses nacl.signing.SigningKey(seed)
                # and it requires exactly 32 bytes.
                private_b64_state["value"] = base64.b64encode(seed).decode("utf-8")

                # Show what you paste into Robinhood: base64(raw public key)
                _set_pub_text(base64.b64encode(pub_raw).decode("utf-8"))


                messagebox.showinfo(
                    "Step 1 complete",
                    "Public/Private keys generated.\n\n"
                    "Next (Robinhood):\n"
                    "  1) Click 'Copy Public Key' in this window\n"
                    "  2) On Robinhood (desktop web): Account → Settings → Crypto\n"
                    "  3) Scroll to 'API Trading' → click '+ Add Key'\n"
                    "  4) Paste the Public Key (base64) into the 'Public key' field\n"
                    "  5) Enable permissions READ + TRADE (this trader needs both), then Save\n"
                    "  6) Robinhood shows an API Key (usually starts with 'rh...') — copy it right away\n\n"
                    "Then come back here and paste that API Key into the 'API Key' box."
                )



            def copy_public_key():
                txt = (pub_box.get("1.0", "end") or "").strip()
                if not txt:
                    messagebox.showwarning("Nothing to copy", "Click 'Generate Keys' first.")
                    return
                _copy_to_clipboard(txt, title="Public Key copied")

            step1_btns = ttk.Frame(step1)
            step1_btns.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))
            ttk.Button(step1_btns, text="Generate Keys", command=generate_keys).pack(side="left")
            ttk.Button(step1_btns, text="Copy Public Key", command=copy_public_key).pack(side="left", padx=8)

            # -----------------------------
            # Step 2 — Paste API key (from Robinhood)
            # -----------------------------
            step2 = ttk.LabelFrame(container, text="Step 2 — Paste your Robinhood API Key here")
            step2.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
            step2.columnconfigure(0, weight=1)

            step2_help = (
                "In Robinhood, after you add the Public Key, Robinhood will show an API Key.\n"
                "Paste that API Key below. (It often starts with 'rh.'.)"
            )
            ttk.Label(step2, text=step2_help, justify="left").grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))

            api_key_var = tk.StringVar(value=existing_api_key or "")
            api_ent = ttk.Entry(step2, textvariable=api_key_var)
            api_ent.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 10))

            def _test_credentials() -> None:
                try:
                    wiz.lift()
                    wiz.focus_force()
                    wiz.attributes("-topmost", True)
                except Exception:
                    pass
                api_key = (api_key_var.get() or "").strip()
                priv_b64 = (private_b64_state.get("value") or "").strip()

                if not requests:
                    messagebox.showerror(
                        "Missing dependency",
                        "The 'requests' package is required for the Test button.\n\n"
                        "Fix: pip install requests\n\n"
                        "(You can still Save without testing.)"
                    )
                    return

                if not priv_b64:
                    messagebox.showerror("Missing private key", "Step 1: click 'Generate Keys' first.")
                    return
                if not api_key:
                    messagebox.showerror("Missing API key", "Paste the API key from Robinhood into Step 2 first.")
                    return

                # Safe test: market-data endpoint (no trading)
                base_url = "https://trading.robinhood.com"
                path = "/api/v1/crypto/marketdata/best_bid_ask/?symbol=BTC-USD"
                method = "GET"
                body = ""
                ts = int(time.time())
                msg = f"{api_key}{ts}{path}{method}{body}".encode("utf-8")

                try:
                    raw = base64.b64decode(priv_b64)

                    # Accept either:
                    #   - 32 bytes: Ed25519 seed
                    #   - 64 bytes: NaCl/tweetnacl secretKey (seed + public)
                    if len(raw) == 64:
                        seed = raw[:32]
                    elif len(raw) == 32:
                        seed = raw
                    else:
                        raise ValueError(f"Unexpected private key length: {len(raw)} bytes (expected 32 or 64)")

                    pk = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
                    sig_b64 = base64.b64encode(pk.sign(msg)).decode("utf-8")
                except Exception as e:
                    messagebox.showerror("Bad private key", f"Couldn't use your private key (r_secret.txt).\n\nError:\n{e}")
                    return


                headers = {
                    "x-api-key": api_key,
                    "x-timestamp": str(ts),
                    "x-signature": sig_b64,
                    "Content-Type": "application/json",
                }

                try:
                    resp = requests.get(f"{base_url}{path}", headers=headers, timeout=10)
                    if resp.status_code >= 400:
                        # Give layman-friendly hints for common failures
                        hint = ""
                        if resp.status_code in (401, 403):
                            hint = (
                                "\n\nCommon fixes:\n"
                                "  • Make sure you pasted the API Key (not the public key).\n"
                                "  • In Robinhood, ensure the key has permissions READ + TRADE.\n"
                                "  • If you just created the key, wait 30–60 seconds and try again.\n"
                            )
                        messagebox.showerror("Test failed", f"Robinhood returned HTTP {resp.status_code}.\n\n{resp.text}{hint}")
                        return

                    data = resp.json()
                    # Try to show something reassuring
                    ask = None
                    try:
                        if data.get("results"):
                            ask = data["results"][0].get("ask_inclusive_of_buy_spread")
                    except Exception:
                        pass

                    messagebox.showinfo(
                        "Test successful",
                        "✅ Your API Key + Private Key worked!\n\n"
                        "Robinhood responded successfully.\n"
                        f"BTC-USD ask (example): {ask if ask is not None else 'received'}\n\n"
                        "Next: click Save."
                    )
                except Exception as e:
                    messagebox.showerror("Test failed", f"Couldn't reach Robinhood.\n\nError:\n{e}")
                finally:
                    try:
                        wiz.attributes("-topmost", False)
                    except Exception:
                        pass

            step2_btns = ttk.Frame(step2)
            step2_btns.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))
            ttk.Button(step2_btns, text="Test Credentials (safe, no trading)", command=_test_credentials).pack(side="left")

            # -----------------------------
            # Step 3 — Save
            # -----------------------------
            step3 = ttk.LabelFrame(container, text="Step 3 — Save to files (required)")
            step3.grid(row=4, column=0, sticky="nsew")
            step3.columnconfigure(0, weight=1)

            ack_var = tk.BooleanVar(value=False)
            ack = ttk.Checkbutton(
                step3,
                text="I understand r_secret.txt is PRIVATE and I will not share it.",
                variable=ack_var,
            )
            ack.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))

            save_btns = ttk.Frame(step3)
            save_btns.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 12))

            def do_save():
                api_key = (api_key_var.get() or "").strip()
                priv_b64 = (private_b64_state.get("value") or "").strip()

                if not priv_b64:
                    messagebox.showerror("Missing private key", "Step 1: click 'Generate Keys' first.")
                    return

                # Normalize private key so pt_thinker.py can load it:
                # - Accept 32 bytes (seed) OR 64 bytes (seed+pub) from older hub versions
                # - Save ONLY base64(seed32) to r_secret.txt
                try:
                    raw = base64.b64decode(priv_b64)
                    if len(raw) == 64:
                        raw = raw[:32]
                        priv_b64 = base64.b64encode(raw).decode("utf-8")
                        private_b64_state["value"] = priv_b64  # keep UI state consistent
                    elif len(raw) != 32:
                        messagebox.showerror(
                            "Bad private key",
                            f"Your private key decodes to {len(raw)} bytes, but it must be 32 bytes.\n\n"
                            "Click 'Generate Keys' again to create a fresh keypair."
                        )
                        return
                except Exception as e:
                    messagebox.showerror(
                        "Bad private key",
                        f"Couldn't decode the private key as base64.\n\nError:\n{e}"
                    )
                    return

                if not api_key:
                    messagebox.showerror("Missing API key", "Step 2: paste your API key from Robinhood first.")
                    return
                if not bool(ack_var.get()):
                    messagebox.showwarning(
                        "Please confirm",
                        "For safety, please check the box confirming you understand r_secret.txt is private."
                    )
                    return


                # Small sanity warning (don’t block, just help)
                if len(api_key) < 10:
                    if not messagebox.askyesno(
                        "API key looks short",
                        "That API key looks unusually short. Are you sure you pasted the API Key from Robinhood?"
                    ):
                        return

                # Back up existing files (so user can undo mistakes)
                try:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    if os.path.isfile(key_path):
                        shutil.copy2(key_path, f"{key_path}.bak_{ts}")
                    if os.path.isfile(secret_path):
                        shutil.copy2(secret_path, f"{secret_path}.bak_{ts}")
                except Exception:
                    pass

                try:
                    with open(key_path, "w", encoding="utf-8") as f:
                        f.write(api_key)
                    with open(secret_path, "w", encoding="utf-8") as f:
                        f.write(priv_b64)
                except Exception as e:
                    messagebox.showerror("Save failed", f"Couldn't write the credential files.\n\nError:\n{e}")
                    return

                _refresh_api_status()
                try:
                    wiz.lift()
                    wiz.attributes("-topmost", True)
                except Exception:
                    pass
                try:
                    messagebox.showinfo(
                        "Saved",
                        "✅ Saved!\n\n"
                        "The trader will automatically read these files next time it starts:\n"
                        f"  API Key → {_mask_path(key_path)}\n"
                        f"  Private Key → {_mask_path(secret_path)}\n\n"
                        "Next steps:\n"
                        "  1) Close this window\n"
                        "  2) Start the trader (pt_trader.py)\n"
                        "If something fails, come back here and click 'Test Credentials'.",
                        parent=wiz,
                    )
                except Exception:
                    try:
                        messagebox.showinfo("Saved", "✅ Saved!", parent=wiz)
                    except Exception:
                        pass
                try:
                    wiz.attributes("-topmost", False)
                except Exception:
                    pass
                wiz.destroy()

            ttk.Button(save_btns, text="Save", command=do_save).pack(side="left")
            ttk.Button(save_btns, text="Close", command=wiz.destroy).pack(side="left", padx=8)

        # -----------------------------
        # KuCoin API setup (simple wizard)
        # -----------------------------
        def _refresh_kucoin_status() -> None:
            k, s, p = _read_kucoin_files()
            try:
                enabled = bool(kucoin_var.get())
            except Exception:
                enabled = bool(self.settings.get("use_kucoin_api", True))

            if k and s and p and enabled:
                kucoin_status_var.set("Configured")
            elif k or s or p:
                kucoin_status_var.set("Partial credentials")
            else:
                # Leave empty so the Setup Wizard button is more prominent
                kucoin_status_var.set("")

        # Placeholder wizards for future exchange platforms
        def _binance_paths() -> Tuple[str, str]:
            key_path = os.path.join(self.project_dir, "binance_key.txt")
            secret_path = os.path.join(self.project_dir, "binance_secret.txt")
            return key_path, secret_path

        def _read_binance_files() -> Tuple[str, str]:
            key_path, secret_path = _binance_paths()
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    k = (f.read() or "").strip()
            except Exception:
                k = ""
            try:
                with open(secret_path, "r", encoding="utf-8") as f:
                    s = (f.read() or "").strip()
            except Exception:
                s = ""
            return k, s

        def _refresh_binance_status() -> None:
            k, s = _read_binance_files()
            try:
                enabled = bool(binance_enabled_var.get())
            except Exception:
                enabled = bool(self.settings.get("exchange_binance_enabled", False))

            if k and s and enabled:
                binance_status_var.set("Configured")
            elif k or s:
                binance_status_var.set("Partial credentials")
            else:
                binance_status_var.set("")

        def _open_binance_api_wizard() -> None:
            """Binance API setup wizard."""
            wiz = tk.Toplevel(win)
            wiz.title("Binance API Setup")
            wiz.geometry("900x650")
            wiz.minsize(800, 550)
            wiz.configure(bg=DARK_BG)

            viewport = ttk.Frame(wiz)
            viewport.pack(fill="both", expand=True, padx=12, pady=12)
            viewport.grid_rowconfigure(0, weight=1)
            viewport.grid_columnconfigure(0, weight=1)

            wiz_canvas = tk.Canvas(viewport, bg=DARK_BG, highlightthickness=1, highlightbackground=DARK_BORDER, bd=0)
            wiz_canvas.grid(row=0, column=0, sticky="nsew")

            wiz_scroll = ttk.Scrollbar(viewport, orient="vertical", command=wiz_canvas.yview)
            wiz_scroll.grid(row=0, column=1, sticky="ns")
            wiz_canvas.configure(yscrollcommand=wiz_scroll.set)

            container = ttk.Frame(wiz_canvas)
            wiz_window = wiz_canvas.create_window((0, 0), window=container, anchor="nw")
            container.columnconfigure(0, weight=1)

            def _update_scrollbars(event=None):
                try:
                    c = wiz_canvas
                    c.update_idletasks()
                    bbox = c.bbox(wiz_window)
                    if not bbox:
                        wiz_scroll.grid_remove()
                        return
                    c.configure(scrollregion=bbox)
                    content_h = int(bbox[3] - bbox[1])
                    view_h = int(c.winfo_height())
                    if content_h > (view_h + 1):
                        wiz_scroll.grid()
                    else:
                        wiz_scroll.grid_remove()
                        try:
                            c.yview_moveto(0)
                        except Exception:
                            pass
                except Exception:
                    pass

            def _on_canvas_configure(e):
                try:
                    wiz_canvas.itemconfigure(wiz_window, width=int(e.width))
                except Exception:
                    pass
                _update_scrollbars()

            wiz_canvas.bind("<Configure>", _on_canvas_configure, add="+")
            container.bind("<Configure>", _update_scrollbars, add="+")

            def _wheel(e):
                try:
                    if wiz_scroll.winfo_ismapped():
                        wiz_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
                except Exception:
                    pass

            wiz_canvas.bind("<Enter>", lambda _e: wiz_canvas.focus_set(), add="+")
            wiz_canvas.bind("<MouseWheel>", _wheel, add="+")
            wiz_canvas.bind("<Button-4>", lambda _e: wiz_canvas.yview_scroll(-3, "units"), add="+")
            wiz_canvas.bind("<Button-5>", lambda _e: wiz_canvas.yview_scroll(3, "units"), add="+")

            frm = ttk.Frame(container, padding=12)
            frm.pack(fill="both", expand=True)
            frm.columnconfigure(0, weight=1)

            intro_text = (
                "📊 Binance Spot & Futures Trading Setup\n\n"
                "This wizard configures Binance API credentials for trading and market data.\n\n"
                "✅ Steps:\n"
                "  1) Go to: https://www.binance.com/en/my/settings/api-management\n"
                "  2) Create a new API key (e.g., 'PowerTrader')\n"
                "  3) Copy your API Key and Secret, paste them below\n"
                "  4) Click Save to store credentials\n"
                "  5) (Optional) Click Test to verify"
            )
            ttk.Label(frm, text=intro_text, justify="left", wraplength=850).pack(fill="x", pady=(0, 12))

            # Step 1 — where to create keys
            step1 = ttk.LabelFrame(frm, text="Step 1 — Create API credentials (website)")
            step1.pack(fill="x", pady=(0, 8))
            ttk.Label(step1, text="Create an API key on Binance and copy the API Key + Secret.").grid(row=0, column=0, sticky="w", padx=10, pady=6)
            def _open_binance_page():
                try:
                    import webbrowser
                    webbrowser.open("https://www.binance.com/en/my/settings/api-management")
                except Exception:
                    pass
            ttk.Button(step1, text="Open Binance API page", command=_open_binance_page).grid(row=0, column=1, sticky="e", padx=10)

            ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=8)

            # Step 2 — paste keys
            step2 = ttk.LabelFrame(frm, text="Step 2 — Paste your API Key and Secret")
            step2.pack(fill="both", expand=False, pady=(0, 10), padx=2)

            key_var = tk.StringVar(value="")
            secret_var = tk.StringVar(value="")

            bk, bs = _read_binance_files()
            key_var.set(bk)
            secret_var.set(bs)

            row_frm = ttk.Frame(step2)
            row_frm.pack(fill="x", pady=6)
            row_frm.columnconfigure(1, weight=1)

            ttk.Label(row_frm, text="API Key:").grid(row=0, column=0, sticky="w", padx=(0, 8))
            key_ent = ttk.Entry(row_frm, textvariable=key_var, width=60, show="*")
            key_ent.grid(row=0, column=1, sticky="ew")
            key_reveal = tk.BooleanVar(value=False)
            def _toggle_kraken_key():
                try:
                    key_ent.configure(show="" if key_reveal.get() else "*")
                except Exception:
                    pass
            ttk.Checkbutton(row_frm, text="Reveal", variable=key_reveal, command=_toggle_kraken_key).grid(row=0, column=2, padx=(8,0))

            row_frm2 = ttk.Frame(step2)
            row_frm2.pack(fill="x", pady=6)
            row_frm2.columnconfigure(1, weight=1)

            ttk.Label(row_frm2, text="API Secret:").grid(row=0, column=0, sticky="w", padx=(0, 8))
            ttk.Entry(row_frm2, textvariable=secret_var, width=60, show="*").grid(row=0, column=1, sticky="ew")

            def do_test():
                try:
                    try:
                        wiz.lift()
                        wiz.focus_force()
                        wiz.attributes("-topmost", True)
                    except Exception:
                        pass
                    import requests
                    k, s = key_var.get().strip(), secret_var.get().strip()
                    if not k or not s:
                        messagebox.showwarning("Missing credentials", "Please enter both API Key and Secret.")
                        try:
                            wiz.attributes("-topmost", False)
                        except Exception:
                            pass
                        return
                    # Test public endpoint (no auth needed)
                    resp = requests.get("https://api.binance.com/api/v3/time", timeout=5)
                    if resp.status_code == 200:
                        messagebox.showinfo("Test successful", "✅ Connected to Binance public API.")
                    else:
                        messagebox.showwarning("Test failed", f"Binance returned: {resp.status_code}")
                except Exception as e:
                    messagebox.showerror("Test error", f"Connection test failed:\n{e}")
                finally:
                    try:
                        wiz.attributes("-topmost", False)
                    except Exception:
                        pass

            def do_save():
                try:
                    k = key_var.get().strip()
                    s = secret_var.get().strip()
                    if not k or not s:
                        messagebox.showwarning("Missing", "Both API Key and Secret are required.")
                        return
                    key_path, secret_path = _binance_paths()
                    with open(key_path, "w", encoding="utf-8") as f:
                        f.write(k)
                    with open(secret_path, "w", encoding="utf-8") as f:
                        f.write(s)
                    messagebox.showinfo("Saved", "✅ Binance credentials saved.\nFile: binance_key.txt, binance_secret.txt")
                    wiz.destroy()
                except Exception as e:
                    messagebox.showerror("Save failed", f"Couldn't save credentials:\n{e}")

            step3 = ttk.LabelFrame(frm, text="Step 3 — Save to files (required)")
            step3.pack(fill="x", pady=(12, 0))
            btns = ttk.Frame(step3)
            btns.pack(fill="x", pady=(6, 0))
            ttk.Button(btns, text="Test", command=do_test).pack(side="left", padx=4)
            ttk.Button(btns, text="Save", command=do_save).pack(side="left", padx=4)
            ttk.Button(btns, text="Close", command=wiz.destroy).pack(side="left", padx=4)

        def _kraken_paths() -> Tuple[str, str]:
            key_path = os.path.join(self.project_dir, "kraken_key.txt")
            secret_path = os.path.join(self.project_dir, "kraken_secret.txt")
            return key_path, secret_path

        def _read_kraken_files() -> Tuple[str, str]:
            key_path, secret_path = _kraken_paths()
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    k = (f.read() or "").strip()
            except Exception:
                k = ""
            try:
                with open(secret_path, "r", encoding="utf-8") as f:
                    s = (f.read() or "").strip()
            except Exception:
                s = ""
            return k, s

        def _refresh_kraken_status() -> None:
            k, s = _read_kraken_files()
            try:
                enabled = bool(kraken_enabled_var.get())
            except Exception:
                enabled = bool(self.settings.get("exchange_kraken_enabled", False))

            if k and s and enabled:
                kraken_status_var.set("Configured")
            elif k or s:
                kraken_status_var.set("Partial credentials")
            else:
                kraken_status_var.set("")

        def _open_kraken_api_wizard() -> None:
            """Kraken API setup wizard."""
            wiz = tk.Toplevel(win)
            wiz.title("Kraken API Setup")
            wiz.geometry("900x650")
            wiz.minsize(800, 550)
            wiz.configure(bg=DARK_BG)

            viewport = ttk.Frame(wiz)
            viewport.pack(fill="both", expand=True, padx=12, pady=12)
            viewport.grid_rowconfigure(0, weight=1)
            viewport.grid_columnconfigure(0, weight=1)

            wiz_canvas = tk.Canvas(viewport, bg=DARK_BG, highlightthickness=1, highlightbackground=DARK_BORDER, bd=0)
            wiz_canvas.grid(row=0, column=0, sticky="nsew")

            wiz_scroll = ttk.Scrollbar(viewport, orient="vertical", command=wiz_canvas.yview)
            wiz_scroll.grid(row=0, column=1, sticky="ns")
            wiz_canvas.configure(yscrollcommand=wiz_scroll.set)

            container = ttk.Frame(wiz_canvas)
            wiz_window = wiz_canvas.create_window((0, 0), window=container, anchor="nw")
            container.columnconfigure(0, weight=1)

            def _update_scrollbars(event=None):
                try:
                    c = wiz_canvas
                    c.update_idletasks()
                    bbox = c.bbox(wiz_window)
                    if not bbox:
                        wiz_scroll.grid_remove()
                        return
                    c.configure(scrollregion=bbox)
                    content_h = int(bbox[3] - bbox[1])
                    view_h = int(c.winfo_height())
                    if content_h > (view_h + 1):
                        wiz_scroll.grid()
                    else:
                        wiz_scroll.grid_remove()
                        try:
                            c.yview_moveto(0)
                        except Exception:
                            pass
                except Exception:
                    pass

            def _on_canvas_configure(e):
                try:
                    wiz_canvas.itemconfigure(wiz_window, width=int(e.width))
                except Exception:
                    pass
                _update_scrollbars()

            wiz_canvas.bind("<Configure>", _on_canvas_configure, add="+")
            container.bind("<Configure>", _update_scrollbars, add="+")

            def _wheel(e):
                try:
                    if wiz_scroll.winfo_ismapped():
                        wiz_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
                except Exception:
                    pass

            wiz_canvas.bind("<Enter>", lambda _e: wiz_canvas.focus_set(), add="+")
            wiz_canvas.bind("<MouseWheel>", _wheel, add="+")
            wiz_canvas.bind("<Button-4>", lambda _e: wiz_canvas.yview_scroll(-3, "units"), add="+")
            wiz_canvas.bind("<Button-5>", lambda _e: wiz_canvas.yview_scroll(3, "units"), add="+")

            frm = ttk.Frame(container, padding=12)
            frm.pack(fill="both", expand=True)
            frm.columnconfigure(0, weight=1)

            intro_text = (
                "🏛️ Kraken Spot & Futures Trading Setup\n\n"
                "This wizard configures Kraken API credentials for trading and market data.\n\n"
                "✅ Steps:\n"
                "  1) Go to: https://www.kraken.com/u/settings/api\n"
                "  2) Click 'Generate New Key'\n"
                "  3) Name: 'PowerTrader', Select permissions: 'Query Funds', 'Query Open Orders', 'Query Closed Orders', 'Create & Modify Orders'\n"
                "  4) Copy your API Key and Private Key\n"
                "  5) Paste them below and click Save"
            )
            ttk.Label(frm, text=intro_text, justify="left", wraplength=850).pack(fill="x", pady=(0, 12))

            ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=8)

            key_var = tk.StringVar(value="")
            secret_var = tk.StringVar(value="")

            kk, ks = _read_kraken_files()
            key_var.set(kk)
            secret_var.set(ks)

            row_frm = ttk.Frame(frm)
            row_frm.pack(fill="x", pady=6)
            row_frm.columnconfigure(1, weight=1)

            ttk.Label(row_frm, text="API Key:").grid(row=0, column=0, sticky="w", padx=(0, 8))
            ttk.Entry(row_frm, textvariable=key_var, width=60).grid(row=0, column=1, sticky="ew")

            row_frm2 = ttk.Frame(frm)
            row_frm2.pack(fill="x", pady=6)
            row_frm2.columnconfigure(1, weight=1)

            ttk.Label(row_frm2, text="Private Key:").grid(row=0, column=0, sticky="w", padx=(0, 8))
            secret_ent = ttk.Entry(row_frm2, textvariable=secret_var, width=60, show="*")
            secret_ent.grid(row=0, column=1, sticky="ew")
            secret_reveal = tk.BooleanVar(value=False)
            def _toggle_kraken_secret():
                try:
                    secret_ent.configure(show="" if secret_reveal.get() else "*")
                except Exception:
                    pass
            ttk.Checkbutton(row_frm2, text="Reveal", variable=secret_reveal, command=_toggle_kraken_secret).grid(row=0, column=2, padx=(8,0))

            def do_test():
                try:
                    try:
                        wiz.lift()
                        wiz.focus_force()
                        wiz.attributes("-topmost", True)
                    except Exception:
                        pass
                    import requests
                    k, s = key_var.get().strip(), secret_var.get().strip()
                    if not k or not s:
                        messagebox.showwarning("Missing credentials", "Please enter both API Key and Private Key.")
                        try:
                            wiz.attributes("-topmost", False)
                        except Exception:
                            pass
                        return
                    # Test public endpoint
                    resp = requests.get("https://api.kraken.com/0/public/Time", timeout=5)
                    if resp.status_code == 200:
                        messagebox.showinfo("Test successful", "✅ Connected to Kraken public API.")
                    else:
                        messagebox.showwarning("Test failed", f"Kraken returned: {resp.status_code}")
                except Exception as e:
                    messagebox.showerror("Test error", f"Connection test failed:\n{e}")
                finally:
                    try:
                        wiz.attributes("-topmost", False)
                    except Exception:
                        pass

            def do_save():
                try:
                    k = key_var.get().strip()
                    s = secret_var.get().strip()
                    if not k or not s:
                        messagebox.showwarning("Missing", "Both API Key and Private Key are required.")
                        return
                    key_path, secret_path = _kraken_paths()
                    with open(key_path, "w", encoding="utf-8") as f:
                        f.write(k)
                    with open(secret_path, "w", encoding="utf-8") as f:
                        f.write(s)
                    messagebox.showinfo("Saved", "✅ Kraken credentials saved.\nFile: kraken_key.txt, kraken_secret.txt")
                    wiz.destroy()
                except Exception as e:
                    messagebox.showerror("Save failed", f"Couldn't save credentials:\n{e}")

            step3 = ttk.LabelFrame(frm, text="Step 3 — Save to files (required)")
            step3.pack(fill="x", pady=(12, 0))
            btns = ttk.Frame(step3)
            btns.pack(fill="x", pady=(6, 0))
            ttk.Button(btns, text="Test", command=do_test).pack(side="left", padx=4)
            ttk.Button(btns, text="Save", command=do_save).pack(side="left", padx=4)
            ttk.Button(btns, text="Close", command=wiz.destroy).pack(side="left", padx=4)

        def _coinbase_paths() -> Tuple[str, str]:
            key_path = os.path.join(self.project_dir, "coinbase_key.txt")
            secret_path = os.path.join(self.project_dir, "coinbase_secret.txt")
            return key_path, secret_path

        def _read_coinbase_files() -> Tuple[str, str]:
            key_path, secret_path = _coinbase_paths()
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    k = (f.read() or "").strip()
            except Exception:
                k = ""
            try:
                with open(secret_path, "r", encoding="utf-8") as f:
                    s = (f.read() or "").strip()
            except Exception:
                s = ""
            return k, s

        def _refresh_coinbase_status() -> None:
            k, s = _read_coinbase_files()
            try:
                enabled = bool(coinbase_enabled_var.get())
            except Exception:
                enabled = bool(self.settings.get("exchange_coinbase_enabled", False))

            if k and s and enabled:
                coinbase_status_var.set("Configured")
            elif k or s:
                coinbase_status_var.set("Partial credentials")
            else:
                coinbase_status_var.set("")

        def _open_coinbase_api_wizard() -> None:
            """Coinbase API setup wizard."""
            wiz = tk.Toplevel(win)
            wiz.title("Coinbase API Setup")
            wiz.geometry("900x650")
            wiz.minsize(800, 550)
            wiz.configure(bg=DARK_BG)

            viewport = ttk.Frame(wiz)
            viewport.pack(fill="both", expand=True, padx=12, pady=12)
            viewport.grid_rowconfigure(0, weight=1)
            viewport.grid_columnconfigure(0, weight=1)

            wiz_canvas = tk.Canvas(viewport, bg=DARK_BG, highlightthickness=1, highlightbackground=DARK_BORDER, bd=0)
            wiz_canvas.grid(row=0, column=0, sticky="nsew")

            wiz_scroll = ttk.Scrollbar(viewport, orient="vertical", command=wiz_canvas.yview)
            wiz_scroll.grid(row=0, column=1, sticky="ns")
            wiz_canvas.configure(yscrollcommand=wiz_scroll.set)

            container = ttk.Frame(wiz_canvas)
            wiz_window = wiz_canvas.create_window((0, 0), window=container, anchor="nw")
            container.columnconfigure(0, weight=1)

            def _update_scrollbars(event=None):
                try:
                    c = wiz_canvas
                    c.update_idletasks()
                    bbox = c.bbox(wiz_window)
                    if not bbox:
                        wiz_scroll.grid_remove()
                        return
                    c.configure(scrollregion=bbox)
                    content_h = int(bbox[3] - bbox[1])
                    view_h = int(c.winfo_height())
                    if content_h > (view_h + 1):
                        wiz_scroll.grid()
                    else:
                        wiz_scroll.grid_remove()
                        try:
                            c.yview_moveto(0)
                        except Exception:
                            pass
                except Exception:
                    pass

            def _on_canvas_configure(e):
                try:
                    wiz_canvas.itemconfigure(wiz_window, width=int(e.width))
                except Exception:
                    pass
                _update_scrollbars()

            wiz_canvas.bind("<Configure>", _on_canvas_configure, add="+")
            container.bind("<Configure>", _update_scrollbars, add="+")

            def _wheel(e):
                try:
                    if wiz_scroll.winfo_ismapped():
                        wiz_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
                except Exception:
                    pass

            wiz_canvas.bind("<Enter>", lambda _e: wiz_canvas.focus_set(), add="+")
            wiz_canvas.bind("<MouseWheel>", _wheel, add="+")
            wiz_canvas.bind("<Button-4>", lambda _e: wiz_canvas.yview_scroll(-3, "units"), add="+")
            wiz_canvas.bind("<Button-5>", lambda _e: wiz_canvas.yview_scroll(3, "units"), add="+")

            frm = ttk.Frame(container, padding=12)
            frm.pack(fill="both", expand=True)
            frm.columnconfigure(0, weight=1)

            intro_text = (
                "🪙 Coinbase Advanced Trading Setup\n\n"
                "This wizard configures Coinbase API credentials for trading and market data.\n\n"
                "✅ Steps:\n"
                "  1) Go to: https://coinbase.com/settings/api (requires Pro account)\n"
                "  2) Click 'New API Key'\n"
                "  3) Give it a name: 'PowerTrader'\n"
                "  4) Enable permissions: 'wallet:accounts:read', 'wallet:sells:create', 'wallet:buys:create'\n"
                "  5) Copy the API Key and Secret Passphrase\n"
                "  6) Paste them below and click Save"
            )
            ttk.Label(frm, text=intro_text, justify="left", wraplength=850).pack(fill="x", pady=(0, 12))

            ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=8)

            key_var = tk.StringVar(value="")
            secret_var = tk.StringVar(value="")

            ck, cs = _read_coinbase_files()
            key_var.set(ck)
            secret_var.set(cs)

            row_frm = ttk.Frame(frm)
            row_frm.pack(fill="x", pady=6)
            row_frm.columnconfigure(1, weight=1)

            ttk.Label(row_frm, text="API Key:").grid(row=0, column=0, sticky="w", padx=(0, 8))
            ttk.Entry(row_frm, textvariable=key_var, width=60).grid(row=0, column=1, sticky="ew")

            row_frm2 = ttk.Frame(frm)
            row_frm2.pack(fill="x", pady=6)
            row_frm2.columnconfigure(1, weight=1)

            ttk.Label(row_frm2, text="Secret:").grid(row=0, column=0, sticky="w", padx=(0, 8))
            ttk.Entry(row_frm2, textvariable=secret_var, width=60, show="*").grid(row=0, column=1, sticky="ew")

            def do_test():
                try:
                    try:
                        wiz.lift()
                        wiz.focus_force()
                        wiz.attributes("-topmost", True)
                    except Exception:
                        pass
                    import requests
                    k, s = key_var.get().strip(), secret_var.get().strip()
                    if not k or not s:
                        messagebox.showwarning("Missing credentials", "Please enter both API Key and Secret.")
                        try:
                            wiz.attributes("-topmost", False)
                        except Exception:
                            pass
                        return
                    # Test public endpoint
                    resp = requests.get("https://api.coinbase.com/v2/exchange-rates?currency=USD", timeout=5)
                    if resp.status_code == 200:
                        messagebox.showinfo("Test successful", "✅ Connected to Coinbase public API.")
                    else:
                        messagebox.showwarning("Test failed", f"Coinbase returned: {resp.status_code}")
                except Exception as e:
                    messagebox.showerror("Test error", f"Connection test failed:\n{e}")
                finally:
                    try:
                        wiz.attributes("-topmost", False)
                    except Exception:
                        pass

            def do_save():
                try:
                    k = key_var.get().strip()
                    s = secret_var.get().strip()
                    if not k or not s:
                        messagebox.showwarning("Missing", "Both API Key and Secret are required.")
                        return
                    key_path, secret_path = _coinbase_paths()
                    with open(key_path, "w", encoding="utf-8") as f:
                        f.write(k)
                    with open(secret_path, "w", encoding="utf-8") as f:
                        f.write(s)
                    messagebox.showinfo("Saved", "✅ Coinbase credentials saved.\nFile: coinbase_key.txt, coinbase_secret.txt")
                    wiz.destroy()
                except Exception as e:
                    messagebox.showerror("Save failed", f"Couldn't save credentials:\n{e}")

            btns = ttk.Frame(frm)
            btns.pack(fill="x", pady=(12, 0))
            ttk.Button(btns, text="Test", command=do_test).pack(side="left", padx=4)
            ttk.Button(btns, text="Save", command=do_save).pack(side="left", padx=4)
            ttk.Button(btns, text="Close", command=wiz.destroy).pack(side="left", padx=4)

        def _bybit_paths() -> Tuple[str, str]:
            key_path = os.path.join(self.project_dir, "bybit_key.txt")
            secret_path = os.path.join(self.project_dir, "bybit_secret.txt")
            return key_path, secret_path

        def _read_bybit_files() -> Tuple[str, str]:
            key_path, secret_path = _bybit_paths()
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    k = (f.read() or "").strip()
            except Exception:
                k = ""
            try:
                with open(secret_path, "r", encoding="utf-8") as f:
                    s = (f.read() or "").strip()
            except Exception:
                s = ""
            return k, s

        def _refresh_bybit_status() -> None:
            k, s = _read_bybit_files()
            try:
                enabled = bool(bybit_enabled_var.get())
            except Exception:
                enabled = bool(self.settings.get("exchange_bybit_enabled", False))

            if k and s and enabled:
                bybit_status_var.set("Configured")
            elif k or s:
                bybit_status_var.set("Partial credentials")
            else:
                bybit_status_var.set("")

        def _open_bybit_api_wizard() -> None:
            """Bybit API setup wizard."""
            wiz = tk.Toplevel(win)
            wiz.title("Bybit API Setup")
            wiz.geometry("900x650")
            wiz.minsize(800, 550)
            wiz.configure(bg=DARK_BG)

            viewport = ttk.Frame(wiz)
            viewport.pack(fill="both", expand=True, padx=12, pady=12)
            viewport.grid_rowconfigure(0, weight=1)
            viewport.grid_columnconfigure(0, weight=1)

            wiz_canvas = tk.Canvas(viewport, bg=DARK_BG, highlightthickness=1, highlightbackground=DARK_BORDER, bd=0)
            wiz_canvas.grid(row=0, column=0, sticky="nsew")

            wiz_scroll = ttk.Scrollbar(viewport, orient="vertical", command=wiz_canvas.yview)
            wiz_scroll.grid(row=0, column=1, sticky="ns")
            wiz_canvas.configure(yscrollcommand=wiz_scroll.set)

            container = ttk.Frame(wiz_canvas)
            wiz_window = wiz_canvas.create_window((0, 0), window=container, anchor="nw")
            container.columnconfigure(0, weight=1)

            def _update_scrollbars(event=None):
                try:
                    c = wiz_canvas
                    c.update_idletasks()
                    bbox = c.bbox(wiz_window)
                    if not bbox:
                        wiz_scroll.grid_remove()
                        return
                    c.configure(scrollregion=bbox)
                    content_h = int(bbox[3] - bbox[1])
                    view_h = int(c.winfo_height())
                    if content_h > (view_h + 1):
                        wiz_scroll.grid()
                    else:
                        wiz_scroll.grid_remove()
                        try:
                            c.yview_moveto(0)
                        except Exception:
                            pass
                except Exception:
                    pass

            def _on_canvas_configure(e):
                try:
                    wiz_canvas.itemconfigure(wiz_window, width=int(e.width))
                except Exception:
                    pass
                _update_scrollbars()

            wiz_canvas.bind("<Configure>", _on_canvas_configure, add="+")
            container.bind("<Configure>", _update_scrollbars, add="+")

            def _wheel(e):
                try:
                    if wiz_scroll.winfo_ismapped():
                        wiz_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
                except Exception:
                    pass

            wiz_canvas.bind("<Enter>", lambda _e: wiz_canvas.focus_set(), add="+")
            wiz_canvas.bind("<MouseWheel>", _wheel, add="+")
            wiz_canvas.bind("<Button-4>", lambda _e: wiz_canvas.yview_scroll(-3, "units"), add="+")
            wiz_canvas.bind("<Button-5>", lambda _e: wiz_canvas.yview_scroll(3, "units"), add="+")

            frm = ttk.Frame(container, padding=12)
            frm.pack(fill="both", expand=True)
            frm.columnconfigure(0, weight=1)

            intro_text = (
                "⚡ Bybit Spot & Derivatives Trading Setup\n\n"
                "This wizard configures Bybit API credentials for trading and market data.\n\n"
                "✅ Steps:\n"
                "  1) Go to: https://www.bybit.com/en/user-center/api-management\n"
                "  2) Click 'Create New Key'\n"
                "  3) Set permissions: 'Account', 'Orders', 'Exchange'\n"
                "  4) Copy your API Key and Secret Key\n"
                "  5) Paste them below and click Save\n"
                "  6) (Optional) Set IP whitelist to your current IP for security"
            )
            ttk.Label(frm, text=intro_text, justify="left", wraplength=850).pack(fill="x", pady=(0, 12))

            ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=8)

            key_var = tk.StringVar(value="")
            secret_var = tk.StringVar(value="")

            byk, bys = _read_bybit_files()
            key_var.set(byk)
            secret_var.set(bys)

            row_frm = ttk.Frame(frm)
            row_frm.pack(fill="x", pady=6)
            row_frm.columnconfigure(1, weight=1)

            ttk.Label(row_frm, text="API Key:").grid(row=0, column=0, sticky="w", padx=(0, 8))
            ttk.Entry(row_frm, textvariable=key_var, width=60).grid(row=0, column=1, sticky="ew")

            row_frm2 = ttk.Frame(frm)
            row_frm2.pack(fill="x", pady=6)
            row_frm2.columnconfigure(1, weight=1)

            ttk.Label(row_frm2, text="Secret Key:").grid(row=0, column=0, sticky="w", padx=(0, 8))
            ttk.Entry(row_frm2, textvariable=secret_var, width=60, show="*").grid(row=0, column=1, sticky="ew")

            def do_test():
                try:
                    try:
                        wiz.lift()
                        wiz.focus_force()
                        wiz.attributes("-topmost", True)
                    except Exception:
                        pass
                    import requests
                    k, s = key_var.get().strip(), secret_var.get().strip()
                    if not k or not s:
                        messagebox.showwarning("Missing credentials", "Please enter both API Key and Secret Key.")
                        try:
                            wiz.attributes("-topmost", False)
                        except Exception:
                            pass
                        return
                    # Test public endpoint
                    resp = requests.get("https://api.bybit.com/v5/market/time", timeout=5)
                    if resp.status_code == 200:
                        messagebox.showinfo("Test successful", "✅ Connected to Bybit public API.")
                    else:
                        messagebox.showwarning("Test failed", f"Bybit returned: {resp.status_code}")
                except Exception as e:
                    messagebox.showerror("Test error", f"Connection test failed:\n{e}")
                finally:
                    try:
                        wiz.attributes("-topmost", False)
                    except Exception:
                        pass

            def do_save():
                try:
                    k = key_var.get().strip()
                    s = secret_var.get().strip()
                    if not k or not s:
                        messagebox.showwarning("Missing", "Both API Key and Secret Key are required.")
                        return
                    key_path, secret_path = _bybit_paths()
                    with open(key_path, "w", encoding="utf-8") as f:
                        f.write(k)
                    with open(secret_path, "w", encoding="utf-8") as f:
                        f.write(s)
                    messagebox.showinfo("Saved", "✅ Bybit credentials saved.\nFile: bybit_key.txt, bybit_secret.txt")
                    wiz.destroy()
                except Exception as e:
                    messagebox.showerror("Save failed", f"Couldn't save credentials:\n{e}")

            btns = ttk.Frame(frm)
            btns.pack(fill="x", pady=(12, 0))
            ttk.Button(btns, text="Test", command=do_test).pack(side="left", padx=4)
            ttk.Button(btns, text="Save", command=do_save).pack(side="left", padx=4)
            ttk.Button(btns, text="Close", command=wiz.destroy).pack(side="left", padx=4)

        def _open_kucoin_api_wizard() -> None:
            try:
                import webbrowser
            except Exception:
                webbrowser = None

                try:
                    import requests
                except Exception:
                    requests = None

                wiz = tk.Toplevel(win)
                wiz.title("KuCoin API Setup")
                wiz.geometry("640x420")
                wiz.minsize(520, 380)

                frm2 = ttk.Frame(wiz, padding=12)
                frm2.pack(fill="both", expand=True)

                ttk.Label(frm2, text="Enter your KuCoin API credentials below.", justify="left").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

                api_key_var = tk.StringVar(value="")
                api_secret_var = tk.StringVar(value="")
                api_pass_var = tk.StringVar(value="")

                ek, es, ep = _read_kucoin_files()
                api_key_var.set(ek)
                api_secret_var.set(es)
                api_pass_var.set(ep)

                ttk.Label(frm2, text="API Key:").grid(row=1, column=0, sticky="w", pady=6)
                ttk.Entry(frm2, textvariable=api_key_var, width=60).grid(row=1, column=1, columnspan=2, sticky="ew", pady=6)

                ttk.Label(frm2, text="API Secret:").grid(row=2, column=0, sticky="w", pady=6)
                ttk.Entry(frm2, textvariable=api_secret_var, width=60, show="*").grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)

                ttk.Label(frm2, text="Passphrase:").grid(row=3, column=0, sticky="w", pady=6)
                ttk.Entry(frm2, textvariable=api_pass_var, width=60, show="*").grid(row=3, column=1, columnspan=2, sticky="ew", pady=6)

                btns2 = ttk.Frame(frm2)
                btns2.grid(row=4, column=0, columnspan=3, sticky="ew", pady=12)
                btns2.columnconfigure(0, weight=1)

                def do_save_kucoin():
                    k_path, s_path, p_path = _kucoin_paths()
                    try:
                        with open(k_path, "w", encoding="utf-8") as f:
                            f.write((api_key_var.get() or "").strip())
                        with open(s_path, "w", encoding="utf-8") as f:
                            f.write((api_secret_var.get() or "").strip())
                        with open(p_path, "w", encoding="utf-8") as f:
                            f.write((api_pass_var.get() or "").strip())
                    except Exception as e:
                        try:
                            messagebox.showerror("Save failed", f"Couldn't write the credential files.\n\nError:\n{e}", parent=wiz)
                        except Exception:
                            messagebox.showerror("Save failed", f"Couldn't write the credential files.\n\nError:\n{e}")
                        return
                    _refresh_kucoin_status()
                    try:
                        wiz.lift()
                        wiz.attributes("-topmost", True)
                    except Exception:
                        pass
                    try:
                        messagebox.showinfo("Saved", "✅ KuCoin credentials saved to project folder.", parent=wiz)
                    except Exception:
                        messagebox.showinfo("Saved", "✅ KuCoin credentials saved to project folder.")
                    try:
                        wiz.attributes("-topmost", False)
                    except Exception:
                        pass
                    wiz.destroy()

                def do_test_kucoin():
                    # Simple test: try importing kucoin and make a public market call if available
                    try:
                        from kucoin.client import Market
                    except Exception as e:
                        messagebox.showerror("Missing package", "The 'kucoin-python' package isn't installed in the trainer environment.")
                        return
                    try:
                        m = Market()
                        ticks = m.get_tickers()
                        try:
                            wiz.lift()
                            wiz.focus_force()
                            wiz.attributes("-topmost", True)
                        except Exception:
                            pass
                        messagebox.showinfo("Success", "Public market request succeeded (kucoin package OK).", parent=wiz)
                        try:
                            wiz.attributes("-topmost", False)
                        except Exception:
                            pass
                    except Exception as e:
                        try:
                            wiz.lift()
                            wiz.focus_force()
                            wiz.attributes("-topmost", True)
                        except Exception:
                            pass
                        messagebox.showerror("Test failed", f"KuCoin test request failed:\n{e}", parent=wiz)
                        try:
                            wiz.attributes("-topmost", False)
                        except Exception:
                            pass

                ttk.Button(btns2, text="Save", command=do_save_kucoin).pack(side="left")
                ttk.Button(btns2, text="Test (public)", command=do_test_kucoin).pack(side="left", padx=8)
                ttk.Button(btns2, text="Close", command=wiz.destroy).pack(side="left", padx=8)



        ttk.Separator(frm, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=10); r += 1

        # API Options - Additional Exchange Platforms
        ttk.Label(frm, text="API Options:", font=("Arial", 10, "bold")).grid(row=r, column=0, sticky="w", pady=(8, 4)); r += 1
        
        # Helper functions for clearing credential files
        def _clear_robinhood_files():
            try:
                rb_key_path = Path(self.project_dir) / "r_key.txt"
                rb_secret_path = Path(self.project_dir) / "r_secret.txt"
                if rb_key_path.exists():
                    rb_key_path.unlink()
                if rb_secret_path.exists():
                    rb_secret_path.unlink()
                messagebox.showinfo("Success", "Robinhood credential files cleared.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear Robinhood files: {e}")
            _refresh_api_status()
        
        def _clear_kucoin_files():
            try:
                kc_key_path = Path(self.project_dir) / "kucoin_key.txt"
                kc_secret_path = Path(self.project_dir) / "kucoin_secret.txt"
                if kc_key_path.exists():
                    kc_key_path.unlink()
                if kc_secret_path.exists():
                    kc_secret_path.unlink()
                messagebox.showinfo("Success", "KuCoin credential files cleared.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear KuCoin files: {e}")
        
        def _clear_binance_files():
            try:
                binance_key_path = Path(self.project_dir) / "binance_key.txt"
                binance_secret_path = Path(self.project_dir) / "binance_secret.txt"
                if binance_key_path.exists():
                    binance_key_path.unlink()
                if binance_secret_path.exists():
                    binance_secret_path.unlink()
                messagebox.showinfo("Success", "Binance credential files cleared.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear Binance files: {e}")
            try:
                _refresh_binance_status()
            except Exception:
                pass
        
        def _clear_kraken_files():
            try:
                kraken_key_path = Path(self.project_dir) / "kraken_key.txt"
                kraken_secret_path = Path(self.project_dir) / "kraken_secret.txt"
                if kraken_key_path.exists():
                    kraken_key_path.unlink()
                if kraken_secret_path.exists():
                    kraken_secret_path.unlink()
                messagebox.showinfo("Success", "Kraken credential files cleared.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear Kraken files: {e}")
            try:
                _refresh_kraken_status()
            except Exception:
                pass
        
        def _clear_coinbase_files():
            try:
                coinbase_key_path = Path(self.project_dir) / "coinbase_key.txt"
                coinbase_secret_path = Path(self.project_dir) / "coinbase_secret.txt"
                if coinbase_key_path.exists():
                    coinbase_key_path.unlink()
                if coinbase_secret_path.exists():
                    coinbase_secret_path.unlink()
                messagebox.showinfo("Success", "Coinbase credential files cleared.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear Coinbase files: {e}")
            try:
                _refresh_coinbase_status()
            except Exception:
                pass
        
        def _clear_bybit_files():
            try:
                bybit_key_path = Path(self.project_dir) / "bybit_key.txt"
                bybit_secret_path = Path(self.project_dir) / "bybit_secret.txt"
                if bybit_key_path.exists():
                    bybit_key_path.unlink()
                if bybit_secret_path.exists():
                    bybit_secret_path.unlink()
                messagebox.showinfo("Success", "Bybit credential files cleared.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear Bybit files: {e}")
            try:
                _refresh_bybit_status()
            except Exception:
                pass
        
        # Robinhood API row
        ttk.Label(frm, text="Robinhood API:").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
        
        robinhood_row = ttk.Frame(frm)
        robinhood_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        robinhood_row.columnconfigure(2, weight=1)
        
        robinhood_checkbox = ttk.Checkbutton(robinhood_row, variable=robinhood_enabled_var)
        robinhood_checkbox.grid(row=0, column=0, sticky="w")
        robinhood_setup_btn = ttk.Button(robinhood_row, text="Setup Wizard", command=_open_robinhood_api_wizard)
        robinhood_setup_btn.grid(row=0, column=1, sticky="w", padx=(6, 8))
        robinhood_label = ttk.Label(robinhood_row, text="Crypto trading", foreground=DARK_MUTED)
        robinhood_label.grid(row=0, column=2, sticky="w")
        robinhood_status_lbl = ttk.Label(robinhood_row, textvariable=api_status_var, foreground=DARK_MUTED)
        robinhood_status_lbl.grid(row=0, column=5, sticky="e", padx=(8, 0))
        robinhood_open_btn = ttk.Button(robinhood_row, text="Open Folder", command=lambda: _open_in_file_manager(self.project_dir))
        robinhood_open_btn.grid(row=0, column=3, sticky="e", padx=(8, 0))
        robinhood_clear_btn = ttk.Button(robinhood_row, text="Clear", command=_clear_robinhood_files)
        robinhood_clear_btn.grid(row=0, column=4, sticky="e", padx=(8, 0))
        
        r += 1
        
        # KuCoin API row
        ttk.Label(frm, text="KuCoin API:").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
        
        kucoin_row = ttk.Frame(frm)
        kucoin_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        kucoin_row.columnconfigure(2, weight=1)
        
        kucoin_checkbox = ttk.Checkbutton(kucoin_row, variable=kucoin_enabled_var)
        kucoin_checkbox.grid(row=0, column=0, sticky="w")
        kucoin_setup_btn = ttk.Button(kucoin_row, text="Setup Wizard", command=_open_kucoin_api_wizard)
        kucoin_setup_btn.grid(row=0, column=1, sticky="w", padx=(6, 8))
        kucoin_label = ttk.Label(kucoin_row, text="Market data & trading", foreground=DARK_MUTED)
        kucoin_label.grid(row=0, column=2, sticky="w")
        kucoin_status_lbl = ttk.Label(kucoin_row, textvariable=kucoin_status_var, foreground=DARK_MUTED)
        kucoin_status_lbl.grid(row=0, column=5, sticky="e", padx=(8, 0))
        kucoin_open_btn = ttk.Button(kucoin_row, text="Open Folder", command=lambda: _open_in_file_manager(self.project_dir))
        kucoin_open_btn.grid(row=0, column=3, sticky="e", padx=(8, 0))
        kucoin_clear_btn = ttk.Button(kucoin_row, text="Clear", command=_clear_kucoin_files)
        kucoin_clear_btn.grid(row=0, column=4, sticky="e", padx=(8, 0))
        
        r += 1
        
        # Binance API row
        ttk.Label(frm, text="Binance API:").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
        
        binance_row = ttk.Frame(frm)
        binance_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        binance_row.columnconfigure(2, weight=1)
        
        binance_checkbox = ttk.Checkbutton(binance_row, variable=binance_enabled_var)
        binance_checkbox.grid(row=0, column=0, sticky="w")
        binance_setup_btn = ttk.Button(binance_row, text="Setup Wizard", command=_open_binance_api_wizard)
        binance_setup_btn.grid(row=0, column=1, sticky="w", padx=(6, 8))
        binance_label = ttk.Label(binance_row, text="Spot & Futures", foreground=DARK_MUTED)
        binance_label.grid(row=0, column=2, sticky="w")
        binance_status_lbl = ttk.Label(binance_row, textvariable=binance_status_var, foreground=DARK_MUTED)
        binance_status_lbl.grid(row=0, column=5, sticky="e", padx=(8, 0))
        binance_open_btn = ttk.Button(binance_row, text="Open Folder", command=lambda: _open_in_file_manager(self.project_dir))
        binance_open_btn.grid(row=0, column=3, sticky="e", padx=(8, 0))
        binance_clear_btn = ttk.Button(binance_row, text="Clear", command=_clear_binance_files)
        binance_clear_btn.grid(row=0, column=4, sticky="e", padx=(8, 0))
        
        r += 1
        
        # Kraken API row
        ttk.Label(frm, text="Kraken API:").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
        
        kraken_row = ttk.Frame(frm)
        kraken_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        kraken_row.columnconfigure(2, weight=1)
        
        kraken_checkbox = ttk.Checkbutton(kraken_row, variable=kraken_enabled_var)
        kraken_checkbox.grid(row=0, column=0, sticky="w")
        kraken_setup_btn = ttk.Button(kraken_row, text="Setup Wizard", command=_open_kraken_api_wizard)
        kraken_setup_btn.grid(row=0, column=1, sticky="w", padx=(6, 8))
        kraken_label = ttk.Label(kraken_row, text="European exchange", foreground=DARK_MUTED)
        kraken_label.grid(row=0, column=2, sticky="w")
        kraken_status_lbl = ttk.Label(kraken_row, textvariable=kraken_status_var, foreground=DARK_MUTED)
        kraken_status_lbl.grid(row=0, column=5, sticky="e", padx=(8, 0))
        kraken_open_btn = ttk.Button(kraken_row, text="Open Folder", command=lambda: _open_in_file_manager(self.project_dir))
        kraken_open_btn.grid(row=0, column=3, sticky="e", padx=(8, 0))
        kraken_clear_btn = ttk.Button(kraken_row, text="Clear", command=_clear_kraken_files)
        kraken_clear_btn.grid(row=0, column=4, sticky="e", padx=(8, 0))
        
        r += 1
        
        # Coinbase API row
        ttk.Label(frm, text="Coinbase API:").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
        
        coinbase_row = ttk.Frame(frm)
        coinbase_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        coinbase_row.columnconfigure(2, weight=1)
        
        coinbase_checkbox = ttk.Checkbutton(coinbase_row, variable=coinbase_enabled_var)
        coinbase_checkbox.grid(row=0, column=0, sticky="w")
        coinbase_setup_btn = ttk.Button(coinbase_row, text="Setup Wizard", command=_open_coinbase_api_wizard)
        coinbase_setup_btn.grid(row=0, column=1, sticky="w", padx=(6, 8))
        coinbase_label = ttk.Label(coinbase_row, text="US-based exchange", foreground=DARK_MUTED)
        coinbase_label.grid(row=0, column=2, sticky="w")
        coinbase_status_lbl = ttk.Label(coinbase_row, textvariable=coinbase_status_var, foreground=DARK_MUTED)
        coinbase_status_lbl.grid(row=0, column=5, sticky="e", padx=(8, 0))
        coinbase_open_btn = ttk.Button(coinbase_row, text="Open Folder", command=lambda: _open_in_file_manager(self.project_dir))
        coinbase_open_btn.grid(row=0, column=3, sticky="e", padx=(8, 0))
        coinbase_clear_btn = ttk.Button(coinbase_row, text="Clear", command=_clear_coinbase_files)
        coinbase_clear_btn.grid(row=0, column=4, sticky="e", padx=(8, 0))
        
        r += 1
        
        # Bybit API row
        ttk.Label(frm, text="Bybit API:").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=6)
        
        bybit_row = ttk.Frame(frm)
        bybit_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        bybit_row.columnconfigure(2, weight=1)
        
        bybit_checkbox = ttk.Checkbutton(bybit_row, variable=bybit_enabled_var)
        bybit_checkbox.grid(row=0, column=0, sticky="w")
        bybit_setup_btn = ttk.Button(bybit_row, text="Setup Wizard", command=_open_bybit_api_wizard)
        bybit_setup_btn.grid(row=0, column=1, sticky="w", padx=(6, 8))
        bybit_label = ttk.Label(bybit_row, text="Derivatives platform", foreground=DARK_MUTED)
        bybit_label.grid(row=0, column=2, sticky="w")
        bybit_status_lbl = ttk.Label(bybit_row, textvariable=bybit_status_var, foreground=DARK_MUTED)
        bybit_status_lbl.grid(row=0, column=5, sticky="e", padx=(8, 0))
        bybit_open_btn = ttk.Button(bybit_row, text="Open Folder", command=lambda: _open_in_file_manager(self.project_dir))
        bybit_open_btn.grid(row=0, column=3, sticky="e", padx=(8, 0))
        bybit_clear_btn = ttk.Button(bybit_row, text="Clear", command=_clear_bybit_files)
        bybit_clear_btn.grid(row=0, column=4, sticky="e", padx=(8, 0))
        
        r += 1

        # Initialize inline credential status labels
        try:
            _refresh_api_status()
        except Exception:
            pass
        try:
            _refresh_kucoin_status()
        except Exception:
            pass
        try:
            _refresh_binance_status()
        except Exception:
            pass
        try:
            _refresh_kraken_status()
        except Exception:
            pass
        try:
            _refresh_coinbase_status()
        except Exception:
            pass
        try:
            _refresh_bybit_status()
        except Exception:
            pass

        ttk.Separator(frm, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=10); r += 1


        add_row(r, "UI refresh seconds:", ui_refresh_var); r += 1
        add_row(r, "Chart refresh seconds:", chart_refresh_var); r += 1
        add_row(r, "Candles limit:", candles_limit_var); r += 1

        chk = ttk.Checkbutton(frm, text="Auto start scripts on GUI launch", variable=auto_start_var)
        chk.grid(row=r, column=0, columnspan=3, sticky="w", pady=(10, 0)); r += 1

        r += 1

        btns = ttk.Frame(frm)
        btns.grid(row=r, column=0, columnspan=3, sticky="ew", pady=14)
        btns.columnconfigure(0, weight=1)

        def save():
            try:
                # Track coins before changes so we can detect newly added coins
                prev_coins = set([str(c).strip().upper() for c in (self.settings.get("coins") or []) if str(c).strip()])

                self.settings["main_neural_dir"] = main_dir_var.get().strip()
                self.settings["coins"] = [coin for coin, var in coin_vars.items() if var.get()]
                self.settings["hub_data_dir"] = hub_dir_var.get().strip()
                self.settings["script_neural_runner2"] = neural_script_var.get().strip()
                self.settings["script_neural_trainer"] = trainer_script_var.get().strip()
                self.settings["script_trader"] = trader_script_var.get().strip()

                self.settings["ui_refresh_seconds"] = float(ui_refresh_var.get().strip())
                self.settings["chart_refresh_seconds"] = float(chart_refresh_var.get().strip())
                self.settings["candles_limit"] = int(float(candles_limit_var.get().strip()))
                
                # Save selected neural timeframes
                selected_tfs = [tf for tf, var in neural_tf_vars.items() if var.get()]
                if not selected_tfs:
                    selected_tfs = ["1hour"]  # ensure at least one is selected
                self.settings["neural_timeframes"] = selected_tfs
                
                # Save neural levels range
                try:
                    min_level = max(0, min(7, int(neural_min_var.get().strip())))
                    max_level = max(0, min(7, int(neural_max_var.get().strip())))
                    if min_level > max_level:
                        min_level, max_level = max_level, min_level
                    self.settings["neural_levels_min"] = min_level
                    self.settings["neural_levels_max"] = max_level
                except Exception:
                    self.settings["neural_levels_min"] = 0
                    self.settings["neural_levels_max"] = 7
                
                self.settings["auto_start_scripts"] = bool(auto_start_var.get())
                self.settings["use_kucoin_api"] = bool(kucoin_var.get())
                self.settings["use_robinhood_api"] = bool(robinhood_var.get())
                
                # Exchange enable/disable flags
                self.settings["exchange_robinhood_enabled"] = bool(robinhood_enabled_var.get())
                self.settings["exchange_kucoin_enabled"] = bool(kucoin_enabled_var.get())
                self.settings["exchange_binance_enabled"] = bool(binance_enabled_var.get())
                self.settings["exchange_kraken_enabled"] = bool(kraken_enabled_var.get())
                self.settings["exchange_coinbase_enabled"] = bool(coinbase_enabled_var.get())
                self.settings["exchange_bybit_enabled"] = bool(bybit_enabled_var.get())
                
                self._save_settings()

                # If new coin(s) were added and their training folder doesn't exist yet,
                # create the folder and copy neural_trainer.py into it RIGHT AFTER saving settings.
                try:
                    new_coins = [c.strip().upper() for c in (self.settings.get("coins") or []) if c.strip()]
                    added = [c for c in new_coins if c and c not in prev_coins]

                    main_dir = self.settings.get("main_neural_dir") or self.project_dir
                    trainer_name = os.path.basename(str(self.settings.get("script_neural_trainer", "neural_trainer.py")))

                    # Best-effort resolve source trainer path:
                    # Prefer trainer living in the main (BTC) folder; fallback to the configured trainer path.
                    src_main_trainer = os.path.join(main_dir, trainer_name)
                    src_cfg_trainer = str(self.settings.get("script_neural_trainer", trainer_name))
                    src_trainer_path = src_main_trainer if os.path.isfile(src_main_trainer) else src_cfg_trainer

                    for coin in added:
                        if coin == "BTC":
                            continue  # BTC uses main folder; no per-coin folder needed

                        coin_dir = os.path.join(main_dir, coin)
                        if not os.path.isdir(coin_dir):
                            os.makedirs(coin_dir, exist_ok=True)

                        dst_trainer_path = os.path.join(coin_dir, trainer_name)
                        if (not os.path.isfile(dst_trainer_path)) and os.path.isfile(src_trainer_path):
                            shutil.copy2(src_trainer_path, dst_trainer_path)
                except Exception:
                    pass

                # Refresh all coin-driven UI (dropdowns + chart tabs)
                self._refresh_coin_dependent_ui(list(prev_coins))

                try:
                    win.lift()
                    win.attributes("-topmost", True)
                except Exception:
                    pass
                try:
                    messagebox.showinfo("Saved", "Settings saved.", parent=win)
                except Exception:
                    try:
                        messagebox.showinfo("Saved", "Settings saved.")
                    except Exception:
                        pass
                try:
                    win.attributes("-topmost", False)
                except Exception:
                    pass
                win.destroy()


            except Exception as e:
                try:
                    messagebox.showerror("Error", f"Failed to save settings:\n{e}", parent=win)
                except Exception:
                    messagebox.showerror("Error", f"Failed to save settings:\n{e}")


        ttk.Button(btns, text="Save", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=8)


if __name__ == "__main__":
    app = PowerTraderHub()
    app.mainloop()

