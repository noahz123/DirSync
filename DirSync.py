import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import subprocess
import os
import json
import ctypes

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

class DirSync:
    def __init__(self, root):
        # Enable DPI awareness (Windows-specific)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()

        # Use custom, crisp fonts for better text resolution
        default_font = ("Helvetica", 16)  # Choose a font and size that looks crisp
        root.option_add("*Font", default_font)
        style = ttk.Style()
        style.configure('TButton', font=default_font)
        
        self.root = root
        self.root.title("DirSync")
        icon_path = os.path.join(os.path.dirname(__file__), "DirSync.ico")
        root.iconbitmap(icon_path)
        self.root.geometry("1x1")
        self.root.minsize(400, 1)
        self.root.resizable(width=False, height=True)

        # Set up variables for system tray functionality
        self.tray_icon = None
        
        # Create menu bar
        self.menubar = tk.Menu(root)
        self.root.config(menu=self.menubar)
        
        # Create File menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Save Configuration", command=self.save_configuration)
        self.file_menu.add_command(label="Load Configuration", command=self.load_configuration)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.exit_app)
        
        # Create main frame with scrollbar
        self.canvas = tk.Canvas(root)
        self.scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.update_canvas_and_window()
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack the scrollbar and canvas
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create main frame
        self.main_frame = ttk.Frame(self.scrollable_frame, padding="20")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
        # Frame for pairs
        self.pairs_frame = ttk.Frame(self.main_frame)
        self.pairs_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        
        # Configure pairs frame columns
        self.pairs_frame.columnconfigure(0, weight=1)
        self.pairs_frame.columnconfigure(1, weight=1)
        
        # List to store source-destination pairs and their frames
        self.path_pairs = []
        self.pair_frames = []
        self.separators = []
        
        # Add initial source-destination pair
        self.add_source_dest_pair()
        
        # Control frame for buttons and progress
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        # Button frame for organizing buttons
        self.button_frame = ttk.Frame(self.control_frame)
        self.button_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        
        # Add button
        self.add_button = ttk.Button(self.button_frame, text="Add Dir Pair", command=self.add_source_dest_pair)
        self.add_button.grid(row=0, column=0, pady=10, padx=5)

        # Thread count frame
        thread_frame = ttk.Frame(self.button_frame)
        thread_frame.grid(row=0, column=1, pady=10, padx=5)
        
        ttk.Label(thread_frame, text="Thread Count:").pack(side=tk.LEFT, padx=(0, 5))
        self.thread_count = tk.StringVar(value="8")  # Default to 8 threads
        thread_entry = ttk.Entry(thread_frame, textvariable=self.thread_count, width=5)
        thread_entry.pack(side=tk.LEFT)
        
        # Interval frame for scheduling
        interval_frame = ttk.Frame(self.button_frame)
        interval_frame.grid(row=0, column=2, pady=10, padx=5)
        
        ttk.Label(interval_frame, text="Interval (hours):").pack(side=tk.LEFT, padx=(0, 5))
        self.interval_hours = tk.StringVar(value="1")  # Default to 1 hour
        interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_hours, width=5)
        interval_entry.pack(side=tk.LEFT)
        
        # Progress Bar (initially hidden)
        self.progress = ttk.Progressbar(self.control_frame, mode='indeterminate', length=100)
        self.progress.grid(row=1, column=0, columnspan=2, pady=20, sticky=tk.EW)
        self.progress.grid_remove()
        
        # Status Label
        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(self.control_frame, textvariable=self.status_var)
        self.status_label.grid(row=2, column=0, columnspan=2, pady=(0,10))
        
        self.start_mirroring_button = ttk.Button(self.control_frame, text="Start Sync", 
                                                command=lambda: self.start_copy())
        self.start_mirroring_button.grid(row=3, column=0, pady=10, sticky=tk.E)
        
        self.start_scheduled_mirroring_button = ttk.Button(self.control_frame, text="Start Scheduled Sync", 
                                                command=lambda: self.start_scheduled_copy())
        self.start_scheduled_mirroring_button.grid(row=3, column=1, pady=10, sticky=tk.W)
        
        # Add keyboard shortcuts
        self.root.bind('<Control-s>', lambda e: self.save_configuration())
        self.root.bind('<Control-o>', lambda e: self.load_configuration())
        
        # Handle close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initial window size update
        self.root.update_idletasks()
        self.update_canvas_and_window()

    def create_tray_icon(self):
        # Create an icon image for the tray
        image = Image.new('RGB', (64, 64), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 64, 64), fill=(0, 128, 255))
        draw.text((20, 20), "DS", fill="white")

        menu = Menu(MenuItem('Show', lambda: self.show_window()), MenuItem('Exit', lambda: self.exit_app()))
        self.tray_icon = Icon("DirSync", image, "DirSync", menu)

    def on_closing(self):
        # Minimize the app to the tray instead of quitting
        self.root.withdraw()
        self.create_tray_icon()
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self):
        # Restore the app window
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)

    def exit_app(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def remove_pair(self, index):
        # Remove the frame and pair from lists
        self.pair_frames[index].destroy()
        self.pair_frames.pop(index)
        self.path_pairs.pop(index)

        # Remove the separator if it exists
        if index > 0 and index - 1 < len(self.separators):
            self.separators[index - 1].destroy()
            self.separators.pop(index - 1)
        elif index < len(self.separators):
            self.separators[index].destroy()
            self.separators.pop(index)

        # Create new frames for all remaining pairs to ensure proper indexing
        old_pairs = [(source_var.get(), dest_var.get()) for source_var, dest_var in self.path_pairs]
        
        # Clear existing UI elements
        for frame in self.pair_frames:
            frame.destroy()
        for separator in self.separators:
            separator.destroy()
            
        self.pair_frames = []
        self.separators = []
        self.path_pairs = []
        
        # Recreate all pairs with correct indexing
        for source_path, dest_path in old_pairs:
            source_var = tk.StringVar(value=source_path)
            dest_var = tk.StringVar(value=dest_path)
            self.add_source_dest_pair(source_var, dest_var)

        # Update the window size
        self.update_canvas_and_window()
        
    def update_canvas_and_window(self):
        # Update canvas scrollregion
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # Get the required dimensions for all content
        required_height = self.scrollable_frame.winfo_reqheight()
        required_width = self.scrollable_frame.winfo_reqwidth() + self.scrollbar.winfo_reqwidth() + 40  # Add padding
        
        # Get screen dimensions
        screen_height = self.root.winfo_screenheight()
        screen_width = self.root.winfo_screenwidth()
        
        # Calculate maximum dimensions (80% of screen)
        max_height = int(screen_height * 0.8)
        max_width = int(screen_width * 0.8)
        
        # Set window dimensions, constrained by max values
        new_height = min(required_height, max_height)
        new_width = min(required_width, max_width)
        
        # Ensure minimum width of 400
        new_width = max(new_width, 400)
        
        # Update window geometry
        self.root.geometry(f"{int(new_width)}x{int(new_height)}")
        
        # Update canvas dimensions
        self.canvas.configure(height=new_height, width=new_width)
        
    def clear_all_pairs(self):
        # Remove all existing pair frames and separators
        for frame in self.pair_frames:
            frame.destroy()
        for separator in self.separators:
            separator.destroy()
        self.path_pairs = []
        self.pair_frames = []
        self.separators = []
        self.update_canvas_and_window()
        
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
                
            # Clear existing pairs
            self.clear_all_pairs()
            
            # Add loaded pairs
            for pair in config:
                source_path = tk.StringVar(value=pair["source"])
                dest_path = tk.StringVar(value=pair["destination"])
                self.add_source_dest_pair(source_path, dest_path)
                
            # Update status label without a popup
            self.status_var.set("Configuration loaded successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")
        
    def add_source_dest_pair(self, source_var=None, dest_var=None):
        # Calculate column and row based on number of pairs
        pair_index = len(self.path_pairs)
        column = 1 if pair_index >= 5 else 0
        row = (pair_index % 5) * 2

        # Create a frame for this pair
        pair_frame = ttk.Frame(self.pairs_frame)
        pair_frame.grid(row=row, column=column, sticky=tk.EW, pady=10, padx=(0 if column == 0 else 10))
        self.pair_frames.append(pair_frame)

        # Create variables for source and destination paths if not provided
        if source_var is None:
            source_var = tk.StringVar()
        if dest_var is None:
            dest_var = tk.StringVar()

        # Source drive section
        source_frame = ttk.Frame(pair_frame)
        source_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW)

        ttk.Label(source_frame, text=f"Source Dir {pair_index + 1}:").pack(side=tk.LEFT, pady=(0, 5))

        source_entry = ttk.Entry(pair_frame, textvariable=source_var, width=40)
        source_entry.grid(row=1, column=0, padx=5, pady=5, sticky=tk.EW)
        source_button = ttk.Button(pair_frame, text="Browse", 
                                command=lambda: self.browse_path(source_var, "Select Source Dir"))
        source_button.grid(row=1, column=1, padx=5, pady=5)

        # Destination drive section
        dest_frame = ttk.Frame(pair_frame)
        dest_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW)

        ttk.Label(dest_frame, text=f"Destination Dir {pair_index + 1}:").pack(side=tk.LEFT, pady=(0, 5))

        dest_entry = ttk.Entry(pair_frame, textvariable=dest_var, width=40)
        dest_entry.grid(row=3, column=0, padx=5, pady=5, sticky=tk.EW)
        dest_button = ttk.Button(pair_frame, text="Browse", 
                                command=lambda: self.browse_path(dest_var, "Select Destination Dir"))
        dest_button.grid(row=3, column=1, padx=5, pady=5)

        # Remove button below the source and destination entries
        remove_button = ttk.Button(pair_frame, text="Remove Dir Pair", 
                                command=lambda idx=pair_index: self.remove_pair(idx))
        # Place the button on the left side
        remove_button.grid(row=4, column=0, pady=(10, 0), sticky="W")

        # Add separator for every pair except the first one in each column
        if pair_index > 0 and pair_index != 5:  # Don't add separator between columns
            separator = ttk.Separator(self.pairs_frame, orient='horizontal')
            separator.grid(row=row - 1, column=column, sticky='ew', pady=10)
            self.separators.append(separator)

        # Configure the pair frame grid
        pair_frame.columnconfigure(0, weight=1)
        pair_frame.columnconfigure(1, weight=0)

        # Store the entries in the list
        self.path_pairs.append((source_var, dest_var))

        # Update window size
        self.root.update_idletasks()
        self.update_canvas_and_window()
            
    def browse_path(self, path_var, title):
        path = filedialog.askdirectory(title=title)
        if path:
            path_var.set(path)
            
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
                messagebox.showerror("Error", "Thread count must be a positive number")
                return False
            return True
        except ValueError:
            messagebox.showerror("Error", "Thread count must be a valid number")
            return False
    
    def start_copy(self):
        if not self.validate_paths() or not self.validate_thread_count():
            return
            gfg
        # Show and start the progress bar
        self.progress.grid()
        self.progress.start(10)
        self.status_var.set("Mirroring in progress...")
        self.start_mirroring_button.configure(state='disabled')
        
        # Run robocopy in a separate thread to prevent GUI freezing
        self.root.after(100, lambda: self.run_robocopy())
    
    def run_robocopy(self):
        try:
            thread_count = self.thread_count.get()
            for i, (source_var, dest_var) in enumerate(self.path_pairs):
                source = source_var.get()
                dest = dest_var.get()
                
                cmd = ['robocopy', source, dest, '/MIR', '/NDL', '/NFL', f'/MT:{thread_count}']
                
                process = subprocess.run(cmd, capture_output=True, text=True)
                
                if process.returncode >= 8:  # Robocopy error codes 8 and above indicate errors
                    messagebox.showerror("Error", f"Robocopy failed for pair {i + 1} with error code {process.returncode}\n{process.stderr}")
                    self.status_var.set("Copy failed")
                    break
                else:
                    self.status_var.set(f"Copy for pair {i + 1} completed")
            
            else:
                messagebox.showinfo("Success", "All copies completed successfully")
                self.status_var.set("All copies completed")
                
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.status_var.set("Copy failed")
            
        finally:
            self.progress.stop()
            self.progress.grid_remove()
            self.start_mirroring_button.configure(state='normal')

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
        
        self.status_var.set(f"Scheduled mirroring every {interval_hours} hour(s)")
        self.schedule_next_copy(interval_hours * 3600 * 1000)  # Convert hours to milliseconds

    def schedule_next_copy(self, interval_ms):
        self.start_copy()
        self.root.after(interval_ms, lambda: self.schedule_next_copy(interval_ms))

def main():
    root = tk.Tk()
    app = DirSync(root)
    root.mainloop()

if __name__ == "__main__":
    main()