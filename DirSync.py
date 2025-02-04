import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import subprocess
import os
import json
import ctypes
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import threading
import sys

class DirSync:
    def __init__(self, root):
        # Enable DPI awareness (Windows-specific)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()

        # Use a crisp font for better resolution
        default_font = ("Helvetica", 16)
        root.option_add("*Font", default_font)
        style = ttk.Style()
        style.configure('TButton', font=default_font)

        self.root = root
        self.root.title("DirSync")
        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(sys._MEIPASS, 'DirSync.ico')
        else:
            icon_path = 'DirSync.ico'
        print(icon_path)
        root.iconbitmap(icon_path)
        self.root.minsize(700, 500)
        self.root.resizable(width=False, height=True)

        # For system tray functionality
        self.tray_icon = None

        # Track running sync process and scheduling
        self.robocopy_process = None
        self.is_scheduled = False
        self.schedule_id = None

        # Create the menu bar
        self.menubar = tk.Menu(root)
        self.root.config(menu=self.menubar)
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Save Configuration", command=self.save_configuration)
        self.file_menu.add_command(label="Load Configuration", command=self.load_configuration)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.exit_app)

        # Create the main frame
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

        # Create a frame to hold all source/destination pair frames
        self.pairs_frame = ttk.Frame(self.main_frame)
        self.pairs_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW)

        # **Create the control frame BEFORE adding any pairs**
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, pady=10)
        self.control_frame.columnconfigure(0, weight=1)
        self.control_frame.columnconfigure(1, weight=1)

        # Lists to store variables and pair frames
        self.path_pairs = []    # List of tuples: (source_var, dest_var)
        self.pair_frames = []   # List of the pair Frame widgets
        self.separators = []    # List of separator widgets

        # Now add an initial source/destination pair
        self.add_source_dest_pair()

        # Create a button frame for organizing buttons inside control_frame
        self.button_frame = ttk.Frame(self.control_frame)
        self.button_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        self.button_frame.columnconfigure(0, weight=1)
        self.button_frame.columnconfigure(1, weight=1)
        self.button_frame.columnconfigure(2, weight=1)

        # "Add Pair" button
        self.add_button = ttk.Button(self.button_frame, text="Add Pair", command=self.add_source_dest_pair)
        self.add_button.grid(row=0, column=0, pady=10, padx=5)

        # Thread count input
        thread_frame = ttk.Frame(self.button_frame)
        thread_frame.grid(row=0, column=1, pady=10, padx=5)
        ttk.Label(thread_frame, text="Thread Count:").pack(side=tk.LEFT, padx=(0, 5))
        self.thread_count = tk.StringVar(value="8")
        thread_entry = ttk.Entry(thread_frame, textvariable=self.thread_count, width=5)
        thread_entry.pack(side=tk.LEFT)

        # Interval (for scheduled sync) input
        interval_frame = ttk.Frame(self.button_frame)
        interval_frame.grid(row=0, column=2, pady=10, padx=5)
        ttk.Label(interval_frame, text="Interval (Hours):").pack(side=tk.LEFT, padx=(0, 5))
        self.interval_hours = tk.StringVar(value="1")
        interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_hours, width=5)
        interval_entry.pack(side=tk.LEFT)

        # Progress bar (initially hidden)
        self.progress = ttk.Progressbar(self.control_frame, mode='indeterminate', length=100)
        self.progress.grid(row=1, column=0, columnspan=2, pady=20, sticky=tk.EW)
        self.progress.grid_remove()

        # Status label
        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(self.control_frame, textvariable=self.status_var)
        self.status_label.grid(row=2, column=0, columnspan=2, pady=(0, 10))

        # Sync control buttons
        sync_button_frame = ttk.Frame(self.control_frame)
        sync_button_frame.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.EW)
        sync_button_frame.columnconfigure(0, weight=1)
        sync_button_frame.columnconfigure(1, weight=1)
        self.start_mirroring_button = ttk.Button(sync_button_frame, text="Start Sync", command=self.toggle_sync)
        self.start_mirroring_button.grid(row=0, column=0, padx=(0, 5), sticky=tk.E)
        self.start_scheduled_mirroring_button = ttk.Button(sync_button_frame, text="Start Scheduled Sync", command=self.toggle_scheduled_sync)
        self.start_scheduled_mirroring_button.grid(row=0, column=1, padx=(5, 0), sticky=tk.W)

        # Keyboard shortcuts
        self.root.bind('<Control-s>', lambda e: self.save_configuration())
        self.root.bind('<Control-o>', lambda e: self.load_configuration())

        # Handle the close window event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.update_idletasks()

    # ----------------- System Tray Functions -----------------
    def create_tray_icon(self):
        image = Image.new('RGB', (64, 64), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 64, 64), fill=(0, 128, 255))
        draw.text((20, 20), "DS", fill="white")
        menu = Menu(MenuItem('Show', lambda: self.show_window()), MenuItem('Exit', lambda: self.exit_app()))
        self.tray_icon = Icon("DirSync", image, "DirSync", menu)

    def on_closing(self):
        # Instead of quitting, minimize to tray.
        self.root.withdraw()
        self.create_tray_icon()
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)

    def exit_app(self):
        self.stop_sync()  # Stop any running sync process
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    # ----------------- Layout and Sizing Helpers -----------------
    def update_window_size(self):
        """Adjust the main window size based on the content in pairs_frame and control_frame."""
        self.root.update_idletasks()
        
        # Calculate the required height.
        pairs_height = self.pairs_frame.winfo_reqheight()
        control_height = self.control_frame.winfo_reqheight()
        required_height = pairs_height + control_height + 60  # extra padding
        
        # Calculate the required width.
        pairs_width = self.pairs_frame.winfo_reqwidth()
        control_width = self.control_frame.winfo_reqwidth()
        # Ensure a minimum width of 700 (or your desired minimum)
        required_width = max(pairs_width, control_width, 700)
        
        # Limit the new dimensions to a percentage of the screen size.
        screen_height = self.root.winfo_screenheight()
        screen_width = self.root.winfo_screenwidth()
        new_height = min(required_height, int(screen_height * 0.8))
        new_width = min(required_width, int(screen_width * 0.8))
        
        # Update the window geometry.
        self.root.geometry(f"{new_width}x{new_height}")


    def layout_pairs(self):
        """
        Rearrange all the pair frames in the pairs_frame.
        Pairs are arranged with a maximum of five per column.
        A separator is added between consecutive pairs in the same column.
        """
        # Remove any existing separators.
        for sep in self.separators:
            sep.destroy()
        self.separators = []

        max_per_column = 5
        for i, pair_frame in enumerate(self.pair_frames):
            col = i // max_per_column
            row = (i % max_per_column) * 2  # leave room for a separator row
            pair_frame.grid(row=row, column=col, sticky="ew", padx=(10 if col > 0 else 0), pady=5)

            # Update label texts inside the pair frame to show the new pair number.
            for child in pair_frame.winfo_children():
                if isinstance(child, ttk.Frame):
                    for subchild in child.winfo_children():
                        if isinstance(subchild, ttk.Label):
                            text = subchild.cget("text")
                            if "Source Directory" in text:
                                subchild.config(text=f"Source Directory {i+1}:")
                            elif "Destination Directory" in text:
                                subchild.config(text=f"Destination Directory {i+1}:")
                elif isinstance(child, ttk.Label):
                    text = child.cget("text")
                    if "Source Directory" in text:
                        child.config(text=f"Source Directory {i+1}:")
                    elif "Destination Directory" in text:
                        child.config(text=f"Destination Directory {i+1}:")

            # Add a separator if the next pair is in the same column.
            if i < len(self.pair_frames) - 1 and (i // max_per_column == (i+1) // max_per_column):
                sep = ttk.Separator(self.pairs_frame, orient='horizontal')
                sep.grid(row=row+1, column=col, sticky="ew", padx=(10 if col > 0 else 0), pady=(0,5))
                self.separators.append(sep)

        self.update_window_size()

    # ----------------- Pair Management -----------------
    def remove_pair_by_frame(self, frame):
        """Remove a pair given its frame, then re-layout all pairs."""
        try:
            idx = self.pair_frames.index(frame)
        except ValueError:
            return
        frame.destroy()
        self.pair_frames.pop(idx)
        self.path_pairs.pop(idx)
        self.layout_pairs()

    def clear_all_pairs(self):
        for frame in self.pair_frames:
            frame.destroy()
        for sep in self.separators:
            sep.destroy()
        self.path_pairs = []
        self.pair_frames = []
        self.separators = []

    def add_source_dest_pair(self, source_var=None, dest_var=None):
        """Add a new source/destination pair. If source_var/dest_var are provided, use them."""
        if source_var is None:
            source_var = tk.StringVar()
        if dest_var is None:
            dest_var = tk.StringVar()

        # Create a frame for this pair.
        pair_frame = ttk.Frame(self.pairs_frame, padding=5)
        # Allow the entry column to expand
        pair_frame.columnconfigure(1, weight=1)

        # --- Source Row ---
        source_label = ttk.Label(pair_frame, text=f"Source Directory {len(self.pair_frames)+1}:")
        source_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        source_entry = ttk.Entry(pair_frame, textvariable=source_var, width=40)
        source_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        source_button = ttk.Button(pair_frame, text="Browse",
                                   command=lambda: self.browse_path(source_var, "Select Source Directory"))
        source_button.grid(row=0, column=2, padx=5, pady=5)

        # --- Destination Row ---
        dest_label = ttk.Label(pair_frame, text=f"Destination Directory {len(self.pair_frames)+1}:")
        dest_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)

        dest_entry = ttk.Entry(pair_frame, textvariable=dest_var, width=40)
        dest_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        dest_button = ttk.Button(pair_frame, text="Browse",
                                 command=lambda: self.browse_path(dest_var, "Select Destination Directory"))
        dest_button.grid(row=1, column=2, padx=5, pady=5)

        # --- Remove Button (spanning all columns) ---
        remove_button = ttk.Button(pair_frame, text="Remove Pair",
                                   command=lambda pf=pair_frame: self.remove_pair_by_frame(pf))
        remove_button.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=(10, 0))

        # Append the new pair's widgets to our lists and re-layout.
        self.pair_frames.append(pair_frame)
        self.path_pairs.append((source_var, dest_var))
        self.layout_pairs()

    def browse_path(self, path_var, title):
        path = filedialog.askdirectory(title=title)
        if path:
            path_var.set(path)

    # ----------------- Configuration Save/Load -----------------
    def save_configuration(self):
        if not self.path_pairs:
            messagebox.showwarning("Warning", "No paths to save")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Configuration File"
        )
        if not file_path:
            return
        config = []
        for source_var, dest_var in self.path_pairs:
            config.append({
                "source": source_var.get(),
                "destination": dest_var.get()
            })
        try:
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=4)
            self.status_var.set("Configuration saved successfully")
            messagebox.showinfo("Success", "Configuration saved successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    def load_configuration(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Configuration File"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
            self.clear_all_pairs()
            for pair in config:
                source_path = tk.StringVar(value=pair["source"])
                dest_path = tk.StringVar(value=pair["destination"])
                self.add_source_dest_pair(source_path, dest_path)
            self.status_var.set("Configuration loaded successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")

    # ----------------- Path and Thread Validation -----------------
    def validate_paths(self):
        for i, (source_var, dest_var) in enumerate(self.path_pairs):
            source = source_var.get()
            dest = dest_var.get()
            if not source or not dest:
                messagebox.showerror("Error", f"Please select both source and destination for pair {i + 1}")
                return False
            if not os.path.exists(source):
                messagebox.showerror("Error", f"Source Dir {i + 1} does not exist")
                return False
            if not os.path.exists(dest):
                messagebox.showerror("Error", f"Destination Dir {i + 1} does not exist")
                return False
        return True

    def validate_thread_count(self):
        try:
            thread_count = int(self.thread_count.get())
            if thread_count <= 0:
                messagebox.showerror("Error", "Thread count must be above 0")
                return False
            if thread_count > 12:
                messagebox.showerror("Error", "Thread count must be 12 or fewer")
                return False
            return True
        except ValueError:
            messagebox.showerror("Error", "Thread count must be a valid number")
            return False

    # ----------------- Sync Operations -----------------
    def toggle_sync(self):
        if self.robocopy_process is None:
            self.start_copy()
        else:
            self.stop_sync()

    def toggle_scheduled_sync(self):
        if not self.is_scheduled:
            self.start_scheduled_copy()
        else:
            self.stop_scheduled_sync()

    def start_copy(self):
        if not self.validate_paths() or not self.validate_thread_count():
            return
        self.progress.grid()
        self.progress.start(10)
        self.status_var.set("Mirroring in progress...")
        self.start_mirroring_button.configure(text="Stop Sync")
        # Run robocopy in a separate thread so the GUI does not freeze.
        self.root.after(100, lambda: threading.Thread(target=self.run_robocopy, daemon=True).start())

    def stop_sync(self):
        if self.robocopy_process:
            self.robocopy_process.terminate()
            self.robocopy_process = None
            self.progress.stop()
            self.progress.grid_remove()
            self.status_var.set("Sync stopped")
            self.start_mirroring_button.configure(text="Start Sync")

    def run_robocopy(self):
        try:
            thread_count = self.thread_count.get()
            for i, (source_var, dest_var) in enumerate(self.path_pairs):
                if self.robocopy_process is None:
                    break
                source = source_var.get()
                dest = dest_var.get()
                cmd = ['robocopy', source, dest, '/Z', '/J', '/MIR', '/NDL', '/NFL', f'/MT:{thread_count}']
                self.robocopy_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                returncode = self.robocopy_process.wait()
                if returncode >= 8:  # Robocopy error codes 8 and above indicate errors
                    messagebox.showerror("Error", f"Robocopy failed for pair {i + 1} with error code {returncode}")
                    self.status_var.set("Copy failed")
                    break
                else:
                    self.status_var.set(f"Copy for pair {i + 1} completed")
            else:
                if self.robocopy_process is not None:
                    messagebox.showinfo("Success", "All copies completed successfully")
                    self.status_var.set("All copies completed")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.status_var.set("Copy failed")
        finally:
            self.robocopy_process = None
            self.progress.stop()
            self.progress.grid_remove()
            self.start_mirroring_button.configure(text="Start Sync")

    def start_scheduled_copy(self):
        if not self.validate_paths() or not self.validate_thread_count():
            return
        try:
            interval_hours = int(self.interval_hours.get())
            if interval_hours <= 0:
                messagebox.showerror("Error", "Interval must be a positive number")
                return
        except ValueError:
            messagebox.showerror("Error", "Interval must be a valid number")
            return
        self.is_scheduled = True
        self.start_scheduled_mirroring_button.configure(text="Stop Scheduled Sync")
        self.status_var.set(f"Scheduled mirroring every {interval_hours} hour(s)")
        self.schedule_next_copy(interval_hours * 3600 * 1000)  # Convert hours to milliseconds

    def schedule_next_copy(self, interval_ms):
        if self.is_scheduled:
            self.start_copy()
            self.schedule_id = self.root.after(interval_ms, lambda: self.schedule_next_copy(interval_ms))

def main():
    root = tk.Tk()
    app = DirSync(root)
    root.mainloop()

if __name__ == "__main__":
    main()
