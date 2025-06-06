import os
import tkinter as tk
from typing import List
import pandas as pd
import matplotlib.pyplot as plt
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from math_utils import *


class CustomNavigationToolbar(NavigationToolbar2Tk):
    '''
    Modified version that maintains navigation capabilities
    while handling idle callbacks more carefully
    '''
    def __init__(self, canvas, parent):
        super().__init__(canvas, parent)
        # Clean up any idle callbacks
        if hasattr(self, '_idle_id') and self._idle_id is not None:
            try:
                self.canvas._tkcanvas.after_cancel(self._idle_id)
                self._idle_id = None
            except Exception:
                pass

    def push_current(self):
        """Override to ensure proper state management"""
        try:
            super().push_current()
        except Exception:
            self._nav_stack.clear()
            try:
                view = NavigationToolbar2Tk._get_view(self)
                self._nav_stack.push(view)
            except Exception:
                pass

    def disconnect(self):
        """Disconnect all mpl event callbacks this toolbar created"""
        fig = self.canvas.figure
        for cid in [getattr(self, attr) for attr in dir(self) if attr.startswith('_id_')]:
            try:
                fig.canvas.mpl_disconnect(cid)
            except Exception:
                pass


class ToolbarFrame(tk.Frame):
    '''
    Specialized frame for the toolbar that ensures proper rendering
    in the CustomTkinter environment
    '''
    def __init__(self, parent):
        # Using standard tkinter Frame instead of CTkFrame for better compatibility
        super().__init__(parent, bg='white')

#GUI fabrication
class RamanApp(ctk.CTk):
    '''
    Main GUI class for Raman Spectra Integrator
    This class creates the main window, sidebar, and content area for the application.
    '''
    def __init__(self):
        super().__init__()
        self.recursive_var = tk.BooleanVar(value=False)
        self.tk.eval('proc bgerror {args} {}')
        self.report_callback_exception = lambda exc, val, tb: None
        self.title("Raman Spectra Integrator")
        self.geometry("1450x850")
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.coordinates = {}
        self.range_labels = []

        #Folder or individual files
        self.file_paths: List[str] = []
        
        # Store after callbacks for cleanup
        self.after_ids = []
        
        # Track canvases and toolbars for cleanup
        self.canvas = None
        self.toolbar = None
        self.toolbar_frame = None  # Add reference to toolbar frame
        
        # Store results and figures
        self.results = {}
        self.figs = {}
        self.current_file = None
        self._orig_paths = {}

        # DEFERRED COMPONENTS - Initialize as None
        self.content_frame = None
        self.results_frame = None
        self.display_frame = None
        self.areas_panel = None
        self.plot_frame = None
        self.file_label = None
        self.file_container = None
        self.file_buttons = []

        self.ratios_entry = None
        self.math_entry = None

        # Create minimal layout - just sidebar initially
        self.create_minimal_layout()
        
        # Bind cleanup to window close
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def create_minimal_layout(self):
        """
        Create only the essential UI components needed for initial interaction.
        Heavy components (matplotlib, scrollable frames) are deferred.
        """
        # Configure columns/rows for resizing
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create sidebar frame only
        self.sidebar = ctk.CTkFrame(self, width=380)
        self.sidebar.grid(row=0, column=0, padx=(10, 0), pady=10, sticky="nsew")
        self.sidebar.grid_rowconfigure(13, weight=1)
        self.sidebar.grid_propagate(False)  # Prevent sidebar from shrinking

        # Create placeholder for content frame (will be built later)
        self.content_placeholder = ctk.CTkLabel(
            self, 
            text="Click 'Run Analysis' or browse files to begin",
            font=ctk.CTkFont(size=16)
        )
        self.content_placeholder.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Setup sidebar immediately (lightweight)
        self.setup_sidebar()

    def _ensure_content_frame(self):
        """
        Build the heavy content frame components only when first needed.
        This includes the matplotlib-backed results area and scrollable components.
        """
        if self.content_frame is not None:
            return  # Already built

        # Remove placeholder
        if hasattr(self, 'content_placeholder'):
            self.content_placeholder.destroy()
            del self.content_placeholder

        # Create main content frame
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Now build the heavy content components
        self.setup_content()

    def _ensure_file_container(self):
        """Build the file list container only when first needed."""
        if self.file_container is not None:
            return  # Already built

        self.file_container = ctk.CTkScrollableFrame(self.sidebar)
        self.file_container.grid(
            row=13, column=0, padx=10, pady=(1, 0), sticky="nsew"
        )

    def _preview_selection(self):
        """Populate results & plots for the selected folder/files with no ranges."""
        # Ensure content frame exists before proceeding
        self._ensure_content_frame()
        self._ensure_file_container()

        # close any leftover figures from the last run/preview
        for fig in self.figs.values():
            plt.close(fig)

        # clear out anything left over
        self._cleanup_plots()
        for btn in self.file_buttons:
            btn.destroy()

        self.file_buttons = []
        self.results = {}
        self.figs = {}
        self.current_file = None
        self._orig_paths.clear()

        # decide inputs exactly like in _run()
        if self.file_paths:
            inputs = list(self.file_paths)
        else:
            folder = self.folder_entry.get()
            if not folder or not os.path.isdir(folder):
                return
            # MODIFIED: optionally recurse into sub-folders
            if self.recursive_var.get():
                inputs = []
                for root, _, files in os.walk(folder):
                    for f in files:
                        if f.lower().endswith(('.txt', '.spc')):
                            inputs.append(os.path.join(root, f))
                inputs.sort()
            else:
                inputs = [
                    os.path.join(folder, f)
                    for f in sorted(os.listdir(folder))
                    if f.lower().endswith(('.txt', '.spc'))
                ]

        # compute only the raw plot (empty ranges → just raw traces)
        for p in inputs:
            r, f, c = compute_areas_and_figures_on_file(p, [])
            self.results.update(r)
            self.figs.update(f)
            self.coordinates.update(c)

            for fname in r.keys():
                # 'results' was keyed by basename, so store its full path
                self._orig_paths[fname] = p

        # show them in the sidebar and auto-open the first one:
        self._populate_file_list()
        if self.file_buttons:
            self.file_buttons[0].invoke()

    def create_layout(self):
        """
        DEPRECATED: This method is replaced by create_minimal_layout and _ensure_content_frame.
        Kept for compatibility but not used in optimized version.
        """
        pass

    def setup_sidebar(self):
        # Folder / file selection
        folder_label = ctk.CTkLabel(self.sidebar, text="Spectra Input:")
        folder_label.grid(row=0, column=0, padx=10, pady=(10,0), sticky="w")

        folder_frame = ctk.CTkFrame(self.sidebar)
        folder_frame.grid(row=1, column=0, padx=10, pady=(5,10), sticky="ew")
        folder_frame.grid_columnconfigure((0,1,2), weight=1)

        self.folder_entry = ctk.CTkEntry(folder_frame)
        self.folder_entry.grid(row=0, column=0, padx=(0,5), sticky="ew")

        ctk.CTkButton(
            folder_frame, text="Browse Folder", command=self._browse_folder, width=80
        ).grid(row=0, column=1, padx=5)
        ctk.CTkButton(
            folder_frame, text="Add Files", command=self._browse_files, width=80
        ).grid(row=0, column=2)

        # Ranges
        ranges_label = ctk.CTkLabel(self.sidebar, text="Ranges (x_min, x_max; ...):")
        ranges_label.grid(row=2, column=0, padx=10, pady=(15,0), sticky="w")
        self.ranges_entry = ctk.CTkEntry(self.sidebar)
        self.ranges_entry.grid(row=3, column=0, padx=10, sticky="ew")

        ratio_label = ctk.CTkLabel(self.sidebar, text="Ratios (e.g., 1/2;3/1):")
        ratio_label.grid(row=4, column=0, padx=10, pady=(10,0), sticky="w")
        self.ratios_entry = ctk.CTkEntry(self.sidebar)
        self.ratios_entry.grid(row=5, column=0, padx=10, sticky="ew")

        math_label = ctk.CTkLabel(self.sidebar, text="Spectral Math (e.g., 1/(2+3)):")
        math_label.grid(row=6, column=0, padx=10, pady=(10,0), sticky="w")
        self.math_entry = ctk.CTkEntry(self.sidebar)
        self.math_entry.grid(row=7, column=0, padx=10, sticky="ew")

        # Process sub-folders checkbox
        self.recursive_cb = ctk.CTkCheckBox(
            self.sidebar,
            text="Process sub-folders",
            variable=self.recursive_var
        )
        self.recursive_cb.grid(row=8, column=0, padx=10, pady=(5, 0), sticky="w")

        # Run & Export buttons
        ctk.CTkButton(
            self.sidebar, text="Run Analysis", command=self._run
        ).grid(row=9, column=0, padx=10, pady=(5, 2), sticky="ew")
        ctk.CTkButton(
            self.sidebar, text="Export to Excel", command=self._export_results
        ).grid(row=10, column=0, padx=10, pady=(2, 2), sticky="ew")

        # File list (lightweight components only)
        ctk.CTkLabel(self.sidebar, text="Available Files:").grid(
            row=11, column=0, padx=10, pady=(1, 0), sticky="w"
        )
        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Search files...")
        self.search_entry.grid(
            row=12, column=0, padx=10, pady=(1, 0), sticky="ew"
        )
        self.search_entry.bind("<KeyRelease>", self._filter_files)

        # NOTE: file_container is deferred and created in _ensure_file_container()
    
    def _browse_folder(self):
        d = tk.filedialog.askdirectory()
        if d:
            self.file_paths = []
            self.folder_entry.delete(0,'end')
            self.folder_entry.insert(0, d)
            self._preview_selection()

    def _browse_files(self):
        files = tk.filedialog.askopenfilenames(
            filetypes=[("Spectra","*.txt *.spc")]
        )
        if files:
            self.file_paths = list(files)
            self.folder_entry.delete(0,'end')
            self.folder_entry.insert(0, f"{len(files)} files selected")
            self._preview_selection()

    def _export_results(self):
        """
        Export integration results to Excel with detailed logging:
        1) Rows generation: one row per spectrum (MAP) or file (single).
        2) Pivot into wide form so each range is its own column.
        3) Compute all pairwise range ratios and their inverses.
        4) Drop Spectrum # if all values are 1.
        5) Write Excel via explicit ExcelWriter; verify success.
        """
        print("Entering _export_results")

        if not self.results:
            print("No results to export.")
            return self._show_error("No results to export.")

        # Ask user where to save
        path = tk.filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")]
        )
        print(f"User selected path: {path}")
        if not path:
            print("Save dialog canceled.")
            return

        # 1) Build rows
        rows = []
        for fname, areas in self.results.items():
            coords     = self.coordinates.get(fname, [])
            is_map     = len(coords) > 0
            multi_spec = any(isinstance(v, list) and len(v) > 1 for v in areas.values())

            if multi_spec:
                # MAP file: one row per spectrum
                n = max(len(v) for v in areas.values())
                coord_names = ["X_Coordinate", "Y_Coordinate", "Z_Coordinate"]
                for idx in range(n):
                    row = {"Filename": fname, "Spectrum #": idx + 1}
                    # dynamic coords
                    if is_map and idx < len(coords):
                        for dim, cval in enumerate(coords[idx]):
                            if dim < len(coord_names):
                                row[coord_names[dim]] = cval
                    # area values
                    for (xmin, xmax), vals in areas.items():
                        key = f"{int(xmin)}–{int(xmax)}"
                        row[key] = float(vals[idx]) if idx < len(vals) else 0.0
                    rows.append(row)
            else:
                # single-spectrum file (or multi single): one row per file
                row = {"Filename": fname}
                for (xmin, xmax), vals in areas.items():
                    key = f"{int(xmin)}–{int(xmax)}"
                    val = vals[0] if isinstance(vals, list) else vals
                    row[key] = float(val)
                rows.append(row)

        df = pd.DataFrame(rows)
        print("Built DataFrame for export, shape:", df.shape)

        # 2) Pivot wide
        coord_names = ["X_Coordinate", "Y_Coordinate", "Z_Coordinate"]
        coord_cols  = [cn for cn in coord_names if cn in df.columns]
        index_cols  = ["Filename"] + (["Spectrum #"] if "Spectrum #" in df.columns else []) + coord_cols
        value_cols  = [c for c in df.columns if c not in index_cols]

        wide = (
            df.pivot_table(index=index_cols, values=value_cols, aggfunc="first")
            .reset_index()
        )
        print("Pivoted wide DataFrame, shape:", wide.shape)

        # 3) Custom ratios and spectral math
        ratio_exprs = [r.strip() for r in (self.ratios_entry.get() or "").split(';') if r.strip()]
        math_exprs  = [r.strip() for r in (self.math_entry.get() or "").split(';') if r.strip()]

        from math_utils import evaluate_formulas
        base_cols = [c for c in value_cols if not c.endswith("_Coordinate")]

        ratio_df = pd.DataFrame()
        math_df  = pd.DataFrame()
        if ratio_exprs:
            ratio_vals = evaluate_formulas(wide, ratio_exprs, base_cols)
            ratio_df = pd.concat([wide[index_cols], ratio_vals], axis=1)

        if math_exprs:
            math_vals = evaluate_formulas(wide, math_exprs, base_cols)
            math_df = pd.concat([wide[index_cols], math_vals], axis=1)

        # 4) Drop redundant Spectrum #
        if "Spectrum #" in wide.columns and wide["Spectrum #"].nunique() == 1:
            wide.drop(columns="Spectrum #", inplace=True)
            print("Dropped Spectrum # column")

        try:
            from pandas import ExcelWriter
            import os

            with ExcelWriter(path, engine="openpyxl") as writer:
                # Integration results
                wide.to_excel(writer, sheet_name="Integration", index=False)

                if not ratio_df.empty:
                    ratio_df.to_excel(writer, sheet_name="Ratios", index=False)

                if not math_df.empty:
                    math_df.to_excel(writer, sheet_name="Spectral Math", index=False)

            # verify & notify…
            if not os.path.exists(path):
                raise IOError(f"File not found at: {path}")
            CTkMessagebox(title="Success", message=f"Saved to:\n{path}", icon="check")

        except Exception as e:
            self._show_error(f"Failed to save Excel:\n{e}")

    def setup_content(self):
        """
        Setup the content area for displaying results and plots.
        This is now called only when first needed (deferred initialization).
        """
        # --- results_frame & header ---
        self.results_frame = ctk.CTkFrame(self.content_frame)
        self.results_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.results_frame.grid_columnconfigure(0, weight=1)
        self.results_frame.grid_rowconfigure(1, weight=1)

        self.file_label = ctk.CTkLabel(
            self.results_frame,
            text="No file selected",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.file_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # --- main display frame ---
        self.display_frame = ctk.CTkFrame(self.results_frame)
        self.display_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        self.display_frame.grid_columnconfigure(1, weight=1)
        self.display_frame.grid_rowconfigure(0, weight=1)

        # 1) container for scrollable results
        container = ctk.CTkFrame(self.display_frame)
        container.grid(row=0, column=0, sticky="nsew", padx=(10,0), pady=10)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # 2) canvas + scrollbars
        canvas = tk.Canvas(container, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")

        vbar = ctk.CTkScrollbar(container, orientation="vertical", command=canvas.yview)
        vbar.grid(row=0, column=1, sticky="ns")
        hbar = ctk.CTkScrollbar(container, orientation="horizontal", command=canvas.xview)
        hbar.grid(row=1, column=0, sticky="ew")

        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        # 3) the actual frame in which you .pack() your result‐rows
        self.areas_panel = ctk.CTkFrame(canvas)
        canvas.create_window((0,0), window=self.areas_panel, anchor="nw")

        # 4) update scrollregion whenever content changes
        self.areas_panel.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # title
        areas_title = ctk.CTkLabel(
            self.areas_panel,
            text="Integration Results",
            font=ctk.CTkFont(weight="bold")
        )
        areas_title.pack(anchor="w", padx=10, pady=10)

        # 5) plot frame
        self.plot_frame = ctk.CTkFrame(self.display_frame)
        self.plot_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.plot_frame.grid_columnconfigure(0, weight=1)
        self.plot_frame.grid_rowconfigure(0, weight=1)

    def _browse(self):
        '''
        Opens a directory selection and updates the folder entry field with the selected path
        '''
        d = tk.filedialog.askdirectory()
        if d:
            self.folder_entry.delete(0, 'end')
            self.folder_entry.insert(0, d)

    def _run(self):
        # Ensure content frame exists before proceeding
        self._ensure_content_frame()
        self._ensure_file_container()

        # close any leftover figures from the last run
        for fig in self.figs.values():
            plt.close(fig)

        # cleanup
        self._cleanup_plots()
        for btn in self.file_buttons:
            btn.destroy()
        self.file_buttons = []
        self.results = {}
        self.figs = {}
        self.current_file = None
        self._orig_paths.clear()

        # parse ranges
        raw = self.ranges_entry.get()
        try:
            rngs = [tuple(map(float, p.split(','))) for p in raw.split(';')]
        except Exception:
            return self._show_error("Invalid range format.")

        self.range_labels = [f"{int(r[0])}–{int(r[1])}" for r in rngs]

        # figure out what the user picked
        if self.file_paths:
            inputs = list(self.file_paths)
        else:
            folder = self.folder_entry.get()
            if not folder or not os.path.isdir(folder):
                return self._show_error("Please select a valid folder or files.")
            # MODIFIED: optionally recurse into sub-folders
            if self.recursive_var.get():
                inputs = []
                for root, _, files in os.walk(folder):
                    for f in files:
                        if f.lower().endswith(('.txt', '.spc')):
                            inputs.append(os.path.join(root, f))
                inputs.sort()
            else:
                inputs = [
                    os.path.join(folder, f)
                    for f in sorted(os.listdir(folder))
                    if f.lower().endswith(('.txt', '.spc'))
                ]

        if not inputs:
            return self._show_error("No spectra found to process.")

        self.file_label.configure(text="Processing… please wait.")
        self.update_idletasks()

        # now process each *file* by calling a helper that works on a single path
        for p in inputs:
            # compute_areas_and_figures expects a FOLDER; for a single file
            # we can just wrap it in a one-file "folder" simulator:
            results, figs, coords = compute_areas_and_figures_on_file(p, rngs)
            self.results.update(results)
            self.figs.update(figs)
            self.coordinates.update(coords)

            for fname in results.keys():
                # 'results' was keyed by basename, so store its full path
                self._orig_paths[fname] = p

        # done
        self.file_label.configure(text="No file selected")
        self._populate_file_list()
        if self.file_buttons:
            self.file_buttons[0].invoke()

    def _filter_files(self, event=None):
        # Only filter if file_container exists
        if self.file_container is None:
            return
            
        search_text = self.search_entry.get().lower()
        
        # Hide/show buttons based on search
        for btn in self.file_buttons:
            # Get display name (without .txt extension)
            display_name = btn.cget("text").lower()
            
            if search_text in display_name:
                btn.grid()
            else:
                btn.grid_remove()

    def _populate_file_list(self):
        '''
        Create one button per spectrum file in the scrollable sidebar.
        Ensure file_container exists before populating.
        '''
        # Ensure file container is built
        self._ensure_file_container()
        
        # Create buttons for each file
        for i, filename in enumerate(sorted(self.results.keys())):
            # Remove .txt extension for display
            display_name = filename[:-4] if filename.lower().endswith('.txt') else filename
            
            btn = ctk.CTkButton(
                self.file_container, 
                text=display_name,
                anchor="w",
                height=30,
                corner_radius=4,
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray75", "gray25"),
                command=lambda f=filename: self._display_file(f)
            )
            # Store the original filename as an attribute for later reference
            btn.original_filename = filename
            
            btn.grid(row=i, column=0, padx=5, pady=2, sticky="ew")
            self.file_buttons.append(btn)

    def _display_file(self, filename):
        """
        Display the selected file's results and plot.
        Updates the areas panel and plot frame with the results for the selected file.
        """
        # Ensure content frame exists
        self._ensure_content_frame()
        
        # 1) Clear previous plot and areas
        self._cleanup_plots()
        for child in self.areas_panel.winfo_children()[1:]:
            child.destroy()

        # 2) Update selection state
        self.current_file = filename
        display_name = filename.rsplit('.',1)[0]
        self.file_label.configure(text=display_name)
        for btn in self.file_buttons:
            btn.configure(fg_color=("gray75","gray30") if btn.original_filename==filename else "transparent")

        # 3) Populate areas panel
        for (xmin, xmax), area in self.results[filename].items():
            row = ctk.CTkFrame(self.areas_panel)
            row.pack(fill="x", padx=10, pady=5)

            lbl = ctk.CTkLabel(row, text=f"{int(xmin)}–{int(xmax)}:", font=ctk.CTkFont(weight="bold"))
            lbl.pack(side="left")

            if isinstance(area, list):
                txt = ", ".join(f"{a:.1f}" for a in area)
            else:
                txt = f"{area:.1f}"
            val = ctk.CTkLabel(row, text=txt, wraplength=200)
            val.pack(side="left", padx=(5,0))

        # 4) Create plot frame and canvas
        fig = self.figs[filename]
        
        # IMPORTANT: Create a fresh canvas each time to avoid state conflicts
        self.canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        self.canvas.draw()
        widget = self.canvas.get_tk_widget()
        widget.grid(row=0, column=0, sticky="nsew")

        # 5) Create a standard tkinter Frame for the toolbar
        self.toolbar_frame = ToolbarFrame(self.plot_frame)
        self.toolbar_frame.grid(row=1, column=0, sticky="ew")
        
        # 6) Create a fresh toolbar instance to reset navigation state
        self.toolbar = CustomNavigationToolbar(self.canvas, self.toolbar_frame)
        self.toolbar.update()
        
        # Configure toolbar to ensure buttons are visible
        self.toolbar.config(background='white')
        for button in self.toolbar.winfo_children():
            if isinstance(button, tk.Button):
                button.config(background='white')
        
        # 7) Force matplotlib to reset the view to fit all data
        # This ensures the zoom starts from a clean state
        for ax in fig.get_axes():
            ax.autoscale(enable=True)
            ax.relim()
            ax.autoscale_view()
        
        # Redraw the canvas after resetting the view
        self.canvas.draw_idle()
        
        # 8) Ensure plot_frame expands
        self.plot_frame.grid_rowconfigure(0, weight=1)
        self.plot_frame.grid_columnconfigure(0, weight=1)

    def _show_error(self, message):
        """Show error message dialog"""
        CTkMessagebox(title="Error", message=message, icon="cancel")

    def _cleanup_plots(self):
        """Clean up matplotlib canvas, callbacks, and toolbar from the plot_frame."""
        # 1) Disconnect and destroy toolbar
        if self.toolbar:
            try:
                self.toolbar.disconnect()
            except Exception:
                pass
            self.toolbar.destroy()
            self.toolbar = None
        if self.toolbar_frame:
            self.toolbar_frame.destroy()
            self.toolbar_frame = None

        # 2) Clean up canvas and its callbacks
        if self.canvas:
            fig = self.canvas.figure
            widget = self.canvas.get_tk_widget()

            # disconnect all matplotlib callbacks on this canvas
            try:
                for event_name, cbmap in self.canvas.callbacks.callbacks.items():
                    for cid in list(cbmap):
                        try:
                            self.canvas.mpl_disconnect(cid)
                        except Exception:
                            pass
            except Exception:
                pass

            # close the figure
            try:
                plt.close(fig)
            except Exception:
                pass

            # destroy the widget
            try:
                widget.destroy()
            except Exception:
                pass

            self.canvas = None

    def _cleanup_after_callbacks(self):
        """Cancel all scheduled 'after' callbacks"""
        # Cancel our own after callbacks
        for after_id in self.after_ids:
            self.after_cancel(after_id)
        
        # Handle customtkinter's internal after callbacks
        # This is a workaround since we can't directly access all of them
        if hasattr(ctk, '_after_callbacks'):
            for after_id in ctk._after_callbacks:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
                    
        # Clean matplotlib's pending callbacks
        fig_manager = plt._pylab_helpers.Gcf.get_all_fig_managers()
        for manager in fig_manager:
            if hasattr(manager, 'canvas') and hasattr(manager.canvas, '_tkcanvas'):
                ids = manager.canvas._tkcanvas.tk.call('after', 'info')
                for after_id in str(ids).split():
                    try:
                        manager.canvas._tkcanvas.after_cancel(after_id)
                    except Exception:
                        pass

    def _on_closing(self):
        """Handle cleanup when window is closed"""
        # Clean up plots
        self._cleanup_plots()
        
        # Clean up after callbacks
        self._cleanup_after_callbacks()
        
        # Close all remaining matplotlib figures
        plt.close('all')
        
        # Destroy the window
        self.destroy()