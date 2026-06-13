"""
MVGL Tools GUI
A graphical interface for MVGLToolsCLI.exe
Supports Digimon Story: Cyber Sleuth, Time Stranger, and The Hundred Line
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import os
import re
import sys
import threading
from collections import Counter
from pathlib import Path


class ToolTip:
    def __init__(self, widget, text_func=None):
        self.widget = widget
        self.text_func = text_func
        self.window = None
        self.label = None

        if widget is not None:
            widget.bind("<Enter>", self.on_enter, add="+")
            widget.bind("<Motion>", self.on_motion, add="+")
            widget.bind("<Leave>", self.on_leave, add="+")

    def on_enter(self, event):
        self.show_at(event.x_root, event.y_root, self.get_text())

    def on_motion(self, event):
        self.show_at(event.x_root, event.y_root, self.get_text())

    def on_leave(self, _event=None):
        self.hide()

    def get_text(self):
        if callable(self.text_func):
            return self.text_func()
        return self.text_func or ""

    def show_at(self, x_root, y_root, text):
        if not text:
            self.hide()
            return

        if self.window is None:
            self.window = tk.Toplevel(self.widget)
            self.window.wm_overrideredirect(True)
            self.window.attributes("-topmost", True)
            self.label = tk.Label(
                self.window,
                text=text,
                justify=tk.LEFT,
                background="#ffffe0",
                relief=tk.SOLID,
                borderwidth=1,
                padx=8,
                pady=5,
                wraplength=520
            )
            self.label.pack()
        else:
            self.label.config(text=text)

        self.window.wm_geometry(f"+{x_root + 12}+{y_root + 18}")
        self.window.deiconify()

    def hide(self):
        if self.window is not None:
            self.window.destroy()
            self.window = None
            self.label = None


class MVGLToolsGUI:
    OPERATION_ORDER = (
        "unpack-mvgl",
        "pack-mvgl",
        "unpack-mbe",
        "pack-mbe",
        "unpack-mbe-dir",
        "pack-mbe-dir",
        "dump-structures",
        "unpack-afs2",
        "pack-afs2",
        "file-decrypt",
        "file-encrypt",
        "save-decrypt",
        "save-encrypt",
    )
    OPERATION_CONFIG = {
        "unpack-mvgl": {"source": "file", "target": "folder"},
        "pack-mvgl": {"source": "folder", "target": "file"},
        "unpack-mbe": {"source": "file", "target": "folder"},
        "pack-mbe": {"source": "folder", "target": "file"},
        "unpack-mbe-dir": {"source": "folder", "target": "folder"},
        "pack-mbe-dir": {"source": "folder", "target": "folder"},
        "dump-structures": {"source": "folder", "target": "folder"},
        "pack-afs2": {"source": "folder", "target": "file"},
        "unpack-afs2": {"source": "file", "target": "folder"},
        "file-encrypt": {"source": "file", "target": "file"},
        "file-decrypt": {"source": "file", "target": "file"},
        "save-encrypt": {"source": "file", "target": "file"},
        "save-decrypt": {"source": "file", "target": "file"},
    }
    OPERATION_LABELS = {
        "unpack-mvgl": "Extract MVGL Archive",
        "pack-mvgl": "Create MVGL Archive",
        "unpack-mbe": "Extract One MBE Table File",
        "pack-mbe": "Rebuild One MBE Table File",
        "unpack-mbe-dir": "Extract MBE Tables From Folder",
        "pack-mbe-dir": "Rebuild MBE Tables From Folder",
        "dump-structures": "Generate MBE Structure Templates",
        "unpack-afs2": "Extract AFS2 Audio Archive",
        "pack-afs2": "Create AFS2 Audio Archive",
        "file-decrypt": "Decrypt Asset File",
        "file-encrypt": "Encrypt Asset File",
        "save-decrypt": "Decrypt Save File",
        "save-encrypt": "Encrypt Save File",
    }
    OPERATION_DESCRIPTIONS = {
        "unpack-mvgl": (
            "Extracts one .mvgl archive into a folder. "
            "Use this first on Time Stranger .mvgl files before extracting MBE tables."
        ),
        "pack-mvgl": (
            "Creates a .mvgl archive from a folder. "
            "Use this after editing extracted files and rebuilding any table data."
        ),
        "unpack-mbe": (
            "Converts one .mbe game data table file into a folder of editable CSV files."
        ),
        "pack-mbe": (
            "Rebuilds one .mbe game data table file from an extracted CSV folder."
        ),
        "unpack-mbe-dir": (
            "Converts all .mbe table files found under the source folder into editable CSV folders. "
            "For Time Stranger, the default filter extracts base archives plus English text01 only."
        ),
        "pack-mbe-dir": (
            "Rebuilds many .mbe table files from extracted CSV folders while preserving folder structure."
        ),
        "dump-structures": (
            "Scans readable .mbe files and creates structure template JSON files. "
            "This is for researching unknown table layouts."
        ),
        "unpack-afs2": (
            "Extracts an AFS2 audio archive into HCA audio files. "
            "MVGLTools notes this is mainly for Cyber Sleuth."
        ),
        "pack-afs2": (
            "Creates an AFS2 audio archive from a folder of audio files. "
            "MVGLTools notes this is mainly for Cyber Sleuth."
        ),
        "file-decrypt": (
            "Decrypts one game asset file. "
            "MVGLTools notes asset encryption is currently a Cyber Sleuth feature."
        ),
        "file-encrypt": (
            "Encrypts one game asset file. "
            "MVGLTools notes asset encryption is currently a Cyber Sleuth feature."
        ),
        "save-decrypt": (
            "Decrypts one PC save file. MVGLTools currently supports this directly for Cyber Sleuth saves."
        ),
        "save-encrypt": (
            "Encrypts one PC save file. MVGLTools currently supports this directly for Cyber Sleuth saves."
        ),
    }

    FILE_TYPES = [
        ("All Files", "*.*"),
        ("MVGL Files", "*.mvgl"),
        ("MBE Files", "*.mbe"),
        ("AFS2 Files", "*.afs2"),
        ("BIN Files", "*.bin"),
    ]
    DSTS_DEFAULT_SOURCE_DIR = Path(r"D:\Digimon Modding\Time Stranger Extracted")
    DSTS_TEXT_ARCHIVE_RE = re.compile(r"_text(\d{2})\.dx11$", re.IGNORECASE)
    DSTS_ENGLISH_TEXT_CODE = "01"

    def __init__(self, root):
        self.root = root
        self.root.title("MVGL Tools GUI")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        self.app_dir = self.get_app_dir()
        self.default_mbe_extract_dir = self.app_dir / "New Extracted"
        self.default_mbe_source_dir = self.DSTS_DEFAULT_SOURCE_DIR
        self.mode_paths = {}
        self.active_mode = None
        self.operation_menu_window = None

        # Find the CLI executable
        self.cli_path = self.find_cli_executable()
        self.cli_cwd = self.find_cli_working_dir()
        
        # Create main container
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Game Selection
        row = 0
        ttk.Label(main_frame, text="Game:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.game_var = tk.StringVar(value="dsts")
        game_frame = ttk.Frame(main_frame)
        game_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        
        games = [
            ("DSCS (PC)", "dscs"),
            ("DSCS (Console/Decrypted)", "dscs-console"),
            ("Time Stranger", "dsts"),
            ("The Hundred Line", "thl")
        ]
        
        for i, (label, value) in enumerate(games):
            ttk.Radiobutton(game_frame, text=label, variable=self.game_var, 
                          value=value, command=self.on_game_change).grid(row=0, column=i, padx=5, sticky=tk.W)
        
        # Mode Selection
        row += 1
        ttk.Separator(main_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        ttk.Label(main_frame, text="Operation:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.mode_var = tk.StringVar(value=self.get_operation_label("unpack-mvgl"))
        operation_frame = ttk.Frame(main_frame)
        operation_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        operation_frame.columnconfigure(0, weight=1)
        self.operation_frame = operation_frame

        self.mode_entry = ttk.Entry(operation_frame, textvariable=self.mode_var, state='readonly')
        self.mode_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.mode_entry.bind("<Button-1>", self.toggle_operation_menu)
        self.mode_entry.bind("<Down>", self.show_operation_menu)
        self.mode_entry.bind("<Return>", self.show_operation_menu)

        self.mode_menu_btn = ttk.Button(operation_frame, text="▼", width=3, command=self.toggle_operation_menu)
        self.mode_menu_btn.grid(row=0, column=1)

        self.operation_tooltip = ToolTip(self.mode_entry, self.get_selected_operation_help)
        self.operation_dropdown_tooltip = ToolTip(None)
        
        # Source Selection
        row += 1
        ttk.Separator(main_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        ttk.Label(main_frame, text="Source:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=5)
        source_frame = ttk.Frame(main_frame)
        source_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        source_frame.columnconfigure(0, weight=1)
        
        self.source_var = tk.StringVar()
        source_entry = ttk.Entry(source_frame, textvariable=self.source_var)
        source_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.source_btn = ttk.Button(source_frame, text="Browse File", command=self.browse_source_file)
        self.source_btn.grid(row=0, column=1)
        
        self.source_dir_btn = ttk.Button(source_frame, text="Browse Folder", command=self.browse_source_folder)
        self.source_dir_btn.grid(row=0, column=2, padx=(5, 0))
        
        # Target Selection
        row += 1
        ttk.Label(main_frame, text="Target:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=5)
        target_frame = ttk.Frame(main_frame)
        target_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        target_frame.columnconfigure(0, weight=1)
        
        self.target_var = tk.StringVar()
        target_entry = ttk.Entry(target_frame, textvariable=self.target_var)
        target_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.target_btn = ttk.Button(target_frame, text="Browse File", command=self.browse_target_file)
        self.target_btn.grid(row=0, column=1)
        
        self.target_dir_btn = ttk.Button(target_frame, text="Browse Folder", command=self.browse_target_folder)
        self.target_dir_btn.grid(row=0, column=2, padx=(5, 0))
        
        # Options
        row += 1
        ttk.Separator(main_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        ttk.Label(main_frame, text="Options:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=5)
        
        options_frame = ttk.Frame(main_frame)
        options_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Compression level (only for pack-mvgl)
        ttk.Label(options_frame, text="Compression:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.compress_var = tk.StringVar(value="normal")
        compress_combo = ttk.Combobox(options_frame, textvariable=self.compress_var, width=15, state='readonly')
        compress_combo['values'] = ('normal', 'none', 'advanced')
        compress_combo.grid(row=0, column=1, sticky=tk.W)
        
        self.compress_label = options_frame.winfo_children()[0]
        self.compress_combo = compress_combo

        # Batch processing for MVGL files
        self.batch_var = tk.BooleanVar(value=False)
        self.batch_check = ttk.Checkbutton(
            options_frame,
            text="Batch extract a folder of MVGL archives",
            variable=self.batch_var,
            command=self.on_mode_change
        )
        self.batch_check.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        self.dsts_base_english_only_var = tk.BooleanVar(value=True)
        self.dsts_base_english_only_check = ttk.Checkbutton(
            options_frame,
            text="Time Stranger: extract base + English text only",
            variable=self.dsts_base_english_only_var,
            command=self.on_mode_change
        )
        self.dsts_base_english_only_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        # Execute Button
        row += 1
        ttk.Separator(main_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)
        
        self.execute_btn = ttk.Button(button_frame, text="Execute", command=self.execute_command, 
                                      style='Accent.TButton', width=20)
        self.execute_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Clear Output", command=self.clear_output, width=15).pack(side=tk.LEFT, padx=5)
        
        # Output Log
        row += 1
        ttk.Label(main_frame, text="Output:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=5)
        
        row += 1
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=15, wrap=tk.WORD, 
                                                     font=('Consolas', 9))
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # CLI Path info
        row += 1
        cli_info = ttk.Label(main_frame, text=f"CLI Tool: {self.cli_path}", 
                            foreground='gray', font=('Arial', 8))
        cli_info.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        # Initial mode setup
        self.on_mode_change()
        
        # Log initial message
        self.log_output("MVGL Tools GUI Initialized\n")
        self.log_output(f"CLI Tool Location: {self.cli_path}\n\n")
        self.log_output(f"CLI Working Folder: {self.cli_cwd}\n\n")
        self.log_output("Select game, operation, source, and target, then click Execute.\n")
        self.log_output("=" * 80 + "\n\n")

    def get_app_dir(self):
        """Return the folder where the GUI app or script lives."""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent

        return Path(__file__).resolve().parent
    
    def find_cli_executable(self):
        """Find the MVGLToolsCLI.exe executable"""
        # Check in _internal folder
        internal_path = self.app_dir / "_internal" / "MVGLToolsCLI.exe"
        if internal_path.exists():
            return str(internal_path.absolute())
        
        # Check in current directory
        current_path = self.app_dir / "MVGLToolsCLI.exe"
        if current_path.exists():
            return str(current_path.absolute())
        
        # Check in parent directory
        parent_path = self.app_dir.parent / "MVGLToolsCLI.exe"
        if parent_path.exists():
            return str(parent_path.absolute())
        
        return "MVGLToolsCLI.exe"  # Default, will fail if not found

    def find_cli_working_dir(self):
        """Run the CLI beside its structures folder whenever possible."""
        cli_path = Path(self.cli_path)
        if cli_path.is_absolute() and cli_path.exists():
            return cli_path.parent

        return self.app_dir

    def get_operation_label(self, mode):
        """Return the friendly label for a CLI operation mode."""
        return self.OPERATION_LABELS.get(mode, mode)

    def get_operation_labels(self):
        """Return operation labels in the display order."""
        return tuple(self.get_operation_label(mode) for mode in self.OPERATION_ORDER)

    def get_mode_for_label(self, label):
        """Map a friendly operation label back to the CLI mode."""
        for mode, operation_label in self.OPERATION_LABELS.items():
            if operation_label == label:
                return mode

        return label if label in self.OPERATION_CONFIG else "unpack-mvgl"

    def get_selected_mode(self):
        """Return the CLI mode represented by the current operation selection."""
        return self.get_mode_for_label(self.mode_var.get())

    def get_operation_description(self, mode):
        """Return the human-readable description for a CLI operation mode."""
        return self.OPERATION_DESCRIPTIONS.get(mode, "")

    def format_operation_help(self, mode):
        """Return tooltip text for an operation."""
        config = self.get_operation_config(mode)
        source_kind = "folder" if config["source"] == "folder" else "file"
        target_kind = "folder" if config["target"] == "folder" else "file"
        return (
            f"{self.get_operation_label(mode)}\n\n"
            f"{self.get_operation_description(mode)}\n\n"
            f"Source: {source_kind}\n"
            f"Target: {target_kind}\n"
            f"CLI mode: {mode}"
        )

    def get_selected_operation_help(self):
        """Return tooltip text for the currently selected operation."""
        return self.format_operation_help(self.get_selected_mode())

    def toggle_operation_menu(self, event=None):
        """Show or hide the custom operation picker."""
        if self.operation_menu_window is not None:
            self.hide_operation_menu()
        else:
            self.show_operation_menu()

        return "break" if event is not None else None

    def show_operation_menu(self, event=None):
        """Show the custom operation picker."""
        if self.operation_menu_window is not None:
            self.operation_menu_window.lift()
            return "break" if event is not None else None

        labels = self.get_operation_labels()
        self.operation_tooltip.hide()

        self.operation_menu_window = tk.Toplevel(self.root)
        self.operation_menu_window.wm_overrideredirect(True)
        self.operation_menu_window.attributes("-topmost", True)
        self.operation_menu_window.bind("<Escape>", lambda _event: self.hide_operation_menu())
        self.operation_menu_window.bind("<FocusOut>", lambda _event: self.root.after(80, self.hide_operation_menu))

        menu_frame = tk.Frame(self.operation_menu_window, borderwidth=1, relief=tk.SOLID)
        menu_frame.pack(fill=tk.BOTH, expand=True)

        self.operation_listbox = tk.Listbox(
            menu_frame,
            activestyle="dotbox",
            exportselection=False,
            height=min(len(labels), 13),
            selectmode=tk.SINGLE
        )
        self.operation_listbox.pack(fill=tk.BOTH, expand=True)

        for label in labels:
            self.operation_listbox.insert(tk.END, label)

        current_label = self.mode_var.get()
        if current_label in labels:
            current_index = labels.index(current_label)
            self.operation_listbox.selection_set(current_index)
            self.operation_listbox.activate(current_index)
            self.operation_listbox.see(current_index)

        self.operation_listbox.bind("<Motion>", self.on_operation_dropdown_motion, add="+")
        self.operation_listbox.bind("<Leave>", lambda _event: self.operation_dropdown_tooltip.hide(), add="+")
        self.operation_listbox.bind("<ButtonRelease-1>", self.select_operation_from_menu, add="+")
        self.operation_listbox.bind("<Return>", self.select_operation_from_menu, add="+")
        self.operation_listbox.bind("<Escape>", lambda _event: self.hide_operation_menu(), add="+")

        self.operation_menu_window.update_idletasks()
        x_root = self.operation_frame.winfo_rootx()
        y_root = self.operation_frame.winfo_rooty() + self.operation_frame.winfo_height()
        width = max(self.operation_frame.winfo_width(), self.operation_menu_window.winfo_reqwidth())
        height = self.operation_menu_window.winfo_reqheight()
        self.operation_menu_window.wm_geometry(f"{width}x{height}+{x_root}+{y_root}")
        self.operation_listbox.focus_set()

        return "break" if event is not None else None

    def hide_operation_menu(self):
        """Hide the custom operation picker."""
        self.operation_dropdown_tooltip.hide()
        if self.operation_menu_window is not None:
            self.operation_menu_window.destroy()
            self.operation_menu_window = None

    def on_operation_dropdown_motion(self, event):
        """Show operation help for the row currently under the pointer."""
        try:
            index = event.widget.nearest(event.y)
            label = event.widget.get(index)
        except Exception:
            return

        event.widget.selection_clear(0, tk.END)
        event.widget.selection_set(index)
        event.widget.activate(index)
        mode = self.get_mode_for_label(label)
        self.operation_dropdown_tooltip.show_at(event.x_root, event.y_root, self.format_operation_help(mode))

    def select_operation_from_menu(self, event=None):
        """Select the highlighted operation from the custom picker."""
        try:
            if event is not None and hasattr(event, "y"):
                index = event.widget.nearest(event.y)
            else:
                selection = self.operation_listbox.curselection()
                index = selection[0] if selection else self.operation_listbox.index(tk.ACTIVE)
            label = self.operation_listbox.get(index)
        except Exception:
            return "break"

        self.mode_var.set(label)
        self.hide_operation_menu()
        self.on_mode_change()
        return "break"

    def get_operation_config(self, mode=None):
        """Return expected source/target path types for the selected operation."""
        return self.OPERATION_CONFIG.get(mode or self.get_selected_mode(), {"source": "file", "target": "file"})

    def save_current_mode_paths(self, mode):
        """Remember paths per operation so mode switches do not mix inputs and outputs."""
        if not mode:
            return

        self.mode_paths[mode] = {
            "source": self.source_var.get().strip(),
            "target": self.target_var.get().strip(),
        }

    def apply_mode_paths(self, mode, previous_mode):
        """Restore saved paths and apply workflow defaults for common extraction steps."""
        saved_paths = self.mode_paths.get(mode, {})
        source = saved_paths.get("source", "")
        target = saved_paths.get("target", "")

        if mode == "unpack-mbe-dir":
            unpacked_mvgl_target = self.mode_paths.get("unpack-mvgl", {}).get("target", "")
            source = source or str(self.default_mbe_source_dir)
            if previous_mode == "unpack-mvgl":
                if unpacked_mvgl_target:
                    source = unpacked_mvgl_target
                target = str(self.default_mbe_extract_dir)
            elif not target:
                target = str(self.default_mbe_extract_dir)
        elif mode == "pack-mvgl" and previous_mode == "unpack-mvgl" and not source:
            source = self.mode_paths.get("unpack-mvgl", {}).get("target", "")
        elif mode == "pack-mbe-dir" and previous_mode == "unpack-mbe-dir" and not source:
            source = self.mode_paths.get("unpack-mbe-dir", {}).get("target", "")

        self.source_var.set(source)
        self.target_var.set(target)

    def on_game_change(self):
        """Refresh game-specific option states."""
        self.on_mode_change()

    def set_browse_button_states(self, source_kind, target_kind):
        """Enable only browse buttons that match the selected operation."""
        self.source_btn.config(state='normal' if source_kind == "file" else 'disabled')
        self.source_dir_btn.config(state='normal' if source_kind == "folder" else 'disabled')
        self.target_btn.config(state='normal' if target_kind == "file" else 'disabled')
        self.target_dir_btn.config(state='normal' if target_kind == "folder" else 'disabled')
    
    def on_mode_change(self, event=None):
        """Update UI based on selected mode"""
        mode = self.get_selected_mode()
        previous_mode = self.active_mode
        self.operation_tooltip.hide()
        self.operation_dropdown_tooltip.hide()

        if previous_mode != mode:
            if previous_mode is not None:
                self.save_current_mode_paths(previous_mode)
            self.apply_mode_paths(mode, previous_mode)
            self.active_mode = mode
        
        # Show/hide compression options based on mode
        if mode == "pack-mvgl":
            self.compress_label.grid()
            self.compress_combo.grid()
        else:
            self.compress_label.grid_remove()
            self.compress_combo.grid_remove()

        # Batch option only makes sense for unpack-mvgl
        batch_supported = mode == "unpack-mvgl"
        if not batch_supported:
            self.batch_var.set(False)
            self.batch_check.state(['disabled'])
        else:
            self.batch_check.state(['!disabled'])
        batch_mode = self.batch_var.get() and batch_supported

        if batch_mode:
            self.set_browse_button_states("folder", "folder")
        else:
            config = self.get_operation_config(mode)
            self.set_browse_button_states(config["source"], config["target"])

        dsts_filter_supported = mode == "unpack-mbe-dir" and self.game_var.get() == "dsts"
        if dsts_filter_supported:
            self.dsts_base_english_only_check.state(['!disabled'])
        else:
            self.dsts_base_english_only_check.state(['disabled'])
    
    def browse_source_file(self):
        """Browse for source file"""
        filename = filedialog.askopenfilename(
            title="Select Source File",
            filetypes=self.FILE_TYPES
        )
        if filename:
            self.source_var.set(filename)
    
    def browse_source_folder(self):
        """Browse for source folder"""
        foldername = filedialog.askdirectory(title="Select Source Folder")
        if foldername:
            self.source_var.set(foldername)
    
    def browse_target_file(self):
        """Browse for target file"""
        filename = filedialog.asksaveasfilename(
            title="Select Target File",
            filetypes=self.FILE_TYPES
        )
        
        if filename:
            self.target_var.set(filename)
    
    def browse_target_folder(self):
        """Browse for target folder"""
        foldername = filedialog.askdirectory(title="Select Target Folder")
        if foldername:
            self.target_var.set(foldername)
    
    def log_output(self, text):
        """Add text to output log"""
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.update_idletasks()
    
    def clear_output(self):
        """Clear the output log"""
        self.output_text.delete(1.0, tk.END)

    def normalize_user_path(self, value):
        """Make typed relative paths stable no matter where the GUI was launched from."""
        path = Path(value.strip().strip('"'))
        if path.is_absolute():
            return path

        return (self.app_dir / path).resolve()

    def validate_paths(self, mode, source, target, batch_mode=False):
        """Return an error string if paths do not match the operation contract."""
        config = {"source": "folder", "target": "folder"} if batch_mode else self.get_operation_config(mode)

        if config["source"] == "folder" and not source.is_dir():
            return f"This operation requires the source to be an existing folder:\n{source}"
        if config["source"] == "file" and not source.is_file():
            return f"This operation requires the source to be an existing file:\n{source}"

        if target.exists():
            if config["target"] == "folder" and not target.is_dir():
                return f"This operation requires the target to be a folder:\n{target}"
            if config["target"] == "file" and target.is_dir():
                return f"This operation requires the target to be a file path, not a folder:\n{target}"
        elif config["target"] == "file" and not target.parent.exists():
            return f"The target file's parent folder does not exist:\n{target.parent}"

        return None

    def should_filter_dsts_text_archives(self, mode):
        """Return whether DSTS MBE extraction should skip non-English text archives."""
        return (
            mode == "unpack-mbe-dir"
            and self.game_var.get() == "dsts"
            and self.dsts_base_english_only_var.get()
        )

    def get_dsts_archive_name(self, source_path, item_path):
        """Find the top .dx11 archive folder for a nested MBE path."""
        try:
            relative_path = item_path.relative_to(source_path)
            if relative_path.parts and relative_path.parts[0].lower().endswith(".dx11"):
                return relative_path.parts[0]
        except ValueError:
            pass

        current_path = item_path if item_path.is_dir() else item_path.parent
        for candidate in (current_path, *current_path.parents):
            if candidate.name.lower().endswith(".dx11"):
                return candidate.name

        return ""

    def should_include_dsts_archive(self, archive_name):
        """Include base archives and English text archives."""
        match = self.DSTS_TEXT_ARCHIVE_RE.search(archive_name)
        return not match or match.group(1) == self.DSTS_ENGLISH_TEXT_CODE

    def create_mbe_scan_summary(self, filter_enabled):
        """Create mutable scan counters for recursive MBE operations."""
        return {
            "filter_enabled": filter_enabled,
            "total_files": 0,
            "included_files": 0,
            "skipped_files": 0,
            "included_archives": set(),
            "skipped_archives": set(),
            "skipped_text_buckets": Counter(),
            "mixed_folders": 0,
        }

    def build_recursive_mbe_commands(self, mode, game, source_path, target_path):
        """Build recursive MBE commands while preserving paths under the target."""
        filter_dsts_text = self.should_filter_dsts_text_archives(mode)
        scan = self.create_mbe_scan_summary(filter_dsts_text)

        if mode == "unpack-mbe-dir":
            folder_files = {}
            for file_path in sorted(source_path.rglob("*")):
                if not file_path.is_file() or file_path.suffix.lower() != ".mbe":
                    continue

                scan["total_files"] += 1
                archive_name = self.get_dsts_archive_name(source_path, file_path)
                if filter_dsts_text and not self.should_include_dsts_archive(archive_name):
                    scan["skipped_files"] += 1
                    if archive_name:
                        scan["skipped_archives"].add(archive_name)
                        match = self.DSTS_TEXT_ARCHIVE_RE.search(archive_name)
                        if match:
                            scan["skipped_text_buckets"][f"text{match.group(1)}"] += 1
                    continue

                scan["included_files"] += 1
                if archive_name:
                    scan["included_archives"].add(archive_name)
                folder_files.setdefault(file_path.parent, []).append(file_path)

            commands = []
            for folder_path, mbe_files in sorted(folder_files.items()):
                relative_folder = folder_path.relative_to(source_path)
                output_folder = target_path if relative_folder == Path(".") else target_path / relative_folder
                regular_files = [path for path in folder_path.iterdir() if path.is_file()]
                only_mbe_files = len(regular_files) == len(mbe_files) and all(
                    path.suffix.lower() == ".mbe" for path in regular_files
                )

                if only_mbe_files:
                    commands.append([
                        self.cli_path,
                        f"--game={game}",
                        f"--mode=unpack-mbe-dir",
                        str(folder_path),
                        str(output_folder)
                    ])
                else:
                    scan["mixed_folders"] += 1
                    for file_path in mbe_files:
                        commands.append([
                            self.cli_path,
                            f"--game={game}",
                            f"--mode=unpack-mbe",
                            str(file_path),
                            str(output_folder)
                        ])

            return commands, scan

        elif mode == "pack-mbe-dir":
            source_folders = sorted({
                folder_path.parent
                for folder_path in source_path.rglob("*")
                if folder_path.is_dir() and folder_path.suffix.lower() == ".mbe"
            })

            commands = []
            for folder_path in source_folders:
                relative_folder = folder_path.relative_to(source_path)
                output_folder = target_path if relative_folder == Path(".") else target_path / relative_folder
                commands.append([
                    self.cli_path,
                    f"--game={game}",
                    f"--mode={mode}",
                    str(folder_path),
                    str(output_folder)
                ])

            return commands, scan

        return [], scan

    def log_mbe_scan_summary(self, mode, scan):
        """Log what recursive MBE extraction will include and skip."""
        if mode != "unpack-mbe-dir":
            return

        self.log_output(f"Scan: found {scan['total_files']} .mbe file(s).\n")
        if scan["filter_enabled"]:
            self.log_output("Filter: including base archives and English text01 archives only.\n")
            self.log_output(
                f"Included: {len(scan['included_archives'])} archive(s), "
                f"{scan['included_files']} .mbe file(s).\n"
            )
            included_archives = sorted(scan["included_archives"])
            if included_archives:
                self.log_output("Included archives:\n")
                for archive_name in included_archives:
                    self.log_output(f"  {archive_name}\n")

            self.log_output(
                f"Skipped: {len(scan['skipped_archives'])} non-English text archive(s), "
                f"{scan['skipped_files']} .mbe file(s).\n"
            )
            if scan["skipped_text_buckets"]:
                skipped_counts = ", ".join(
                    f"{bucket}={count}" for bucket, count in sorted(scan["skipped_text_buckets"].items())
                )
                self.log_output(f"Skipped text buckets: {skipped_counts}\n")

        if scan["mixed_folders"]:
            self.log_output(
                f"Note: {scan['mixed_folders']} folder(s) contain non-MBE files; "
                "those folders will be processed one .mbe at a time.\n"
            )
    
    def execute_command(self):
        """Execute the MVGLToolsCLI command"""
        # Validate inputs
        if not self.source_var.get():
            messagebox.showerror("Error", "Please select a source file or folder.")
            return
        
        if not self.target_var.get():
            messagebox.showerror("Error", "Please select a target file or folder.")
            return
        
        # Check if CLI exists
        if not os.path.exists(self.cli_path):
            messagebox.showerror("Error", f"MVGLToolsCLI.exe not found at:\n{self.cli_path}\n\nPlease ensure the executable is in the _internal folder or current directory.")
            return
        
        # Build command
        game = self.game_var.get()
        mode = self.get_selected_mode()
        self.save_current_mode_paths(mode)
        source_path = self.normalize_user_path(self.source_var.get())
        target_path = self.normalize_user_path(self.target_var.get())
        source = str(source_path)
        target = str(target_path)

        # Batch mode (only for unpack-mvgl)
        if self.batch_var.get():
            if mode != "unpack-mvgl":
                messagebox.showerror("Error", "Batch processing is available only for Extract MVGL Archive.")
                return
            
            validation_error = self.validate_paths(mode, source_path, target_path, batch_mode=True)
            if validation_error:
                messagebox.showerror("Error", validation_error)
                return
            
            target_path.mkdir(parents=True, exist_ok=True)
            mvgl_files = sorted(source_path.glob("*.mvgl"))
            
            if not mvgl_files:
                messagebox.showerror("Error", f"No .mvgl files found in:\n{source_path}")
                return
            
            commands = []
            for mvgl_file in mvgl_files:
                output_folder = target_path / mvgl_file.stem
                commands.append([
                    self.cli_path,
                    f"--game={game}",
                    f"--mode={mode}",
                    str(mvgl_file),
                    str(output_folder)
                ])
            
            self.log_output("\n" + "=" * 80 + "\n")
            self.log_output(
                f"Batch {self.get_operation_label(mode)}: preparing to extract "
                f"{len(commands)} MVGL archive(s) from {source_path} to {target_path}\n"
            )
            self.log_output("=" * 80 + "\n\n")
            
            self.execute_btn.config(state='disabled', text='Running...')
            thread = threading.Thread(target=self.run_batch_commands, args=(commands,))
            thread.daemon = True
            thread.start()
            return

        validation_error = self.validate_paths(mode, source_path, target_path)
        if validation_error:
            messagebox.showerror("Error", validation_error)
            return

        if mode in ("unpack-mbe-dir", "pack-mbe-dir"):
            commands, scan = self.build_recursive_mbe_commands(mode, game, source_path, target_path)
            if not commands:
                if mode == "unpack-mbe-dir":
                    if scan.get("skipped_files"):
                        messagebox.showerror(
                            "Error",
                            "MBE files were found, but all were skipped by the base + English filter.\n\n"
                            f"Found: {scan['total_files']}\n"
                            f"Skipped: {scan['skipped_files']}\n\n"
                            "Uncheck the Time Stranger filter to extract this folder."
                        )
                    else:
                        messagebox.showerror("Error", f"No .mbe files found in:\n{source_path}")
                else:
                    messagebox.showerror("Error", f"No extracted .mbe folders found in:\n{source_path}")
                return

            self.log_output("\n" + "=" * 80 + "\n")
            self.log_mbe_scan_summary(mode, scan)
            self.log_output(
                f"Recursive {self.get_operation_label(mode)}: processing {len(commands)} command(s) "
                f"from {source_path} to {target_path}\n"
            )
            self.log_output("=" * 80 + "\n\n")

            self.execute_btn.config(state='disabled', text='Running...')
            thread = threading.Thread(target=self.run_batch_commands, args=(commands,))
            thread.daemon = True
            thread.start()
            return
        
        cmd = [self.cli_path, f"--game={game}", f"--mode={mode}", source, target]
        
        # Add compression option for pack-mvgl
        if mode == "pack-mvgl":
            compress_level = self.compress_var.get()
            cmd.append(f"--compress={compress_level}")
        
        # Log command
        self.log_output("\n" + "=" * 80 + "\n")
        self.log_output(f"Operation: {self.get_operation_label(mode)} ({mode})\n")
        self.log_output(f"Executing: {' '.join(cmd)}\n")
        self.log_output("=" * 80 + "\n\n")
        
        # Disable execute button
        self.execute_btn.config(state='disabled', text='Running...')
        
        # Run command in thread
        thread = threading.Thread(target=self.run_command, args=(cmd,))
        thread.daemon = True
        thread.start()
    
    def _run_cli_command(self, cmd):
        """Run a CLI command and stream output; returns the return code"""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=str(self.cli_cwd),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        for line in process.stdout:
            self.root.after(0, self.log_output, line)
        
        process.wait()
        return process.returncode

    def run_command(self, cmd):
        """Run the command in a separate thread"""
        try:
            returncode = self._run_cli_command(cmd)
            
            if returncode == 0:
                self.root.after(0, self.log_output, "\n✓ Operation completed successfully!\n")
            else:
                self.root.after(0, self.log_output, f"\n✗ Operation failed with return code {returncode}\n")
        
        except Exception as e:
            self.root.after(0, self.log_output, f"\n✗ Error: {str(e)}\n")
        
        finally:
            # Re-enable execute button
            self.root.after(0, self.execute_btn.config, {'state': 'normal', 'text': 'Execute'})

    def run_batch_commands(self, commands):
        """Run multiple CLI commands sequentially for batch MVGL processing"""
        try:
            total = len(commands)
            for idx, cmd in enumerate(commands, start=1):
                source_label = Path(cmd[3]).name if len(cmd) > 3 else Path(cmd[-2]).name
                target_label = cmd[4] if len(cmd) > 4 else cmd[-1]
                self.root.after(0, self.log_output, f"\n[{idx}/{total}] {source_label} -> {target_label}\n")
                
                returncode = self._run_cli_command(cmd)
                if returncode == 0:
                    self.root.after(0, self.log_output, "✓ Completed\n")
                else:
                    self.root.after(0, self.log_output, f"✗ Failed with return code {returncode}\n")
            
            self.root.after(0, self.log_output, "\nBatch processing finished.\n")
        
        except Exception as e:
            self.root.after(0, self.log_output, f"\n✗ Error: {str(e)}\n")
        
        finally:
            self.root.after(0, self.execute_btn.config, {'state': 'normal', 'text': 'Execute'})


def main():
    root = tk.Tk()
    app = MVGLToolsGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
