"""Dark mode theme manager for SKCC Awards GUI applications."""

import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
from typing import Dict, Any, Optional


class ThemeManager:
    """Manages light/dark themes for tkinter applications."""

    def __init__(self):
        self.current_theme = "light"
        self.config_file = Path.home() / ".skcc_awards" / "theme_config.json"
        self.themes = {
            "light": {
                "bg": "#ffffff",
                "fg": "#000000",
                "select_bg": "#0078d4",
                "select_fg": "#ffffff",
                "entry_bg": "#ffffff",
                "entry_fg": "#000000",
                "button_bg": "#f0f0f0",
                "button_fg": "#000000",
                "frame_bg": "#f0f0f0",
                "text_bg": "#ffffff",
                "text_fg": "#000000",
                "treeview_bg": "#ffffff",
                "treeview_fg": "#000000",
                "treeview_select": "#0078d4",
                "status_bg": "#f0f0f0",
                "status_fg": "#000000",
            },
            "dark": {
                "bg": "#1a1a1a",
                "fg": "#f0f0f0",
                "select_bg": "#0078d4",
                "select_fg": "#ffffff",
                "entry_bg": "#2a2a2a",
                "entry_fg": "#f0f0f0",
                "button_bg": "#3a3a3a",
                "button_fg": "#f0f0f0",
                "frame_bg": "#1a1a1a",
                "text_bg": "#242424",
                "text_fg": "#f0f0f0",
                "treeview_bg": "#242424",
                "treeview_fg": "#f0f0f0",
                "treeview_select": "#0078d4",
                "status_bg": "#2a2a2a",
                "status_fg": "#f0f0f0",
            },
        }
        self._load_theme_preference()

    def _load_theme_preference(self) -> None:
        """Load theme preference from config file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                    self.current_theme = config.get("theme", "light")
        except Exception:
            self.current_theme = "light"

    def _save_theme_preference(self) -> None:
        """Save theme preference to config file."""
        try:
            self.config_file.parent.mkdir(exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump({"theme": self.current_theme}, f)
        except Exception:
            pass  # Fail silently if we can't save

    def get_colors(self, theme_name: Optional[str] = None) -> Dict[str, str]:
        """Get color scheme for the specified theme."""
        theme = theme_name or self.current_theme
        return self.themes.get(theme, self.themes["light"])

    def toggle_theme(self) -> str:
        """Toggle between light and dark themes."""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self._save_theme_preference()
        return self.current_theme

    def set_theme(self, theme_name: str) -> None:
        """Set specific theme."""
        if theme_name in self.themes:
            self.current_theme = theme_name
            self._save_theme_preference()

    def apply_theme(self, root: tk.Misc, theme_name: Optional[str] = None) -> None:
        """Apply theme to a tkinter window and all its widgets."""
        colors = self.get_colors(theme_name)

        # Configure root window (if it's a Tk or Toplevel)
        if isinstance(root, (tk.Tk, tk.Toplevel)):
            root.configure(bg=colors["bg"])

        # Configure ttk styles
        style = ttk.Style()

        # Configure common ttk widgets
        style.configure("TFrame", background=colors["frame_bg"])
        style.configure("TLabel", background=colors["frame_bg"], foreground=colors["fg"])
        style.configure(
            "TButton",
            background=colors["button_bg"],
            foreground=colors["button_fg"],
            relief="raised",
            borderwidth=1,
        )
        style.map(
            "TButton",
            background=[
                ("active", colors["select_bg"]),
                ("pressed", colors["select_bg"]),
            ],
            foreground=[
                ("active", colors["select_fg"]),
                ("pressed", colors["select_fg"]),
            ],
        )
        style.configure(
            "TEntry",
            fieldbackground=colors["entry_bg"],
            foreground=colors["entry_fg"],
            borderwidth=1,
            relief="solid",
        )
        style.configure("TCheckbutton", background=colors["frame_bg"], foreground=colors["fg"])
        style.configure(
            "TCombobox",
            fieldbackground=colors["entry_bg"],
            foreground=colors["entry_fg"],
        )

        # Configure Treeview
        style.configure(
            "Treeview",
            background=colors["treeview_bg"],
            foreground=colors["treeview_fg"],
            fieldbackground=colors["treeview_bg"],
        )
        style.configure(
            "Treeview.Heading",
            background=colors["button_bg"],
            foreground=colors["button_fg"],
        )
        style.map(
            "Treeview",
            background=[("selected", colors["treeview_select"])],
            foreground=[("selected", colors["select_fg"])],
        )

        # Configure Text widgets (need to be done individually)
        self._apply_to_text_widgets(root, colors)

        # Configure Listbox widgets
        self._apply_to_listbox_widgets(root, colors)

        # Configure Entry and Label widgets
        self._apply_to_tk_widgets(root, colors)

    def _apply_to_text_widgets(self, parent: tk.Misc, colors: Dict[str, str]) -> None:
        """Apply theme to Text widgets recursively."""
        for child in parent.winfo_children():
            if isinstance(child, tk.Text):
                child.configure(
                    bg=colors["text_bg"],
                    fg=colors["text_fg"],
                    selectbackground=colors["select_bg"],
                    selectforeground=colors["select_fg"],
                    insertbackground=colors["fg"],
                )
            elif hasattr(child, "winfo_children"):
                self._apply_to_text_widgets(child, colors)

    def _apply_to_listbox_widgets(self, parent: tk.Misc, colors: Dict[str, str]) -> None:
        """Apply theme to Listbox widgets recursively."""
        for child in parent.winfo_children():
            if isinstance(child, tk.Listbox):
                child.configure(
                    bg=colors["text_bg"],
                    fg=colors["text_fg"],
                    selectbackground=colors["select_bg"],
                    selectforeground=colors["select_fg"],
                )
            elif hasattr(child, "winfo_children"):
                self._apply_to_listbox_widgets(child, colors)

    def _apply_to_tk_widgets(self, parent: tk.Misc, colors: Dict[str, str]) -> None:
        """Apply theme to regular tk widgets recursively."""
        for child in parent.winfo_children():
            if isinstance(child, tk.Entry):
                child.configure(
                    bg=colors["entry_bg"],
                    fg=colors["entry_fg"],
                    selectbackground=colors["select_bg"],
                    selectforeground=colors["select_fg"],
                    insertbackground=colors["entry_fg"],
                )
            elif isinstance(child, tk.Label):
                child.configure(bg=colors["frame_bg"], fg=colors["fg"])
            elif isinstance(child, tk.Button):
                child.configure(
                    bg=colors["button_bg"],
                    fg=colors["button_fg"],
                    activebackground=colors["select_bg"],
                    activeforeground=colors["select_fg"],
                )
            elif isinstance(child, tk.Frame):
                child.configure(bg=colors["frame_bg"])
            elif hasattr(child, "winfo_children"):
                self._apply_to_tk_widgets(child, colors)


# Global theme manager instance
theme_manager = ThemeManager()
