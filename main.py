import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

# Constants for Valve Types
TYPE_NORMALLY_OPEN = "Normally Open"
TYPE_NORMALLY_CLOSED = "Normally Closed"

class PneumaticValve:
    """
    Model representing the physical valve logic.
    """
    def __init__(self, name: str, valve_type: str):
        self.name = name
        self.valve_type = valve_type
        self._energized = False

    @property
    def is_energized(self) -> bool:
        return self._energized

    @is_energized.setter
    def is_energized(self, state: bool):
        self._energized = state

    @property
    def is_physically_open(self) -> bool:
        """
        Calculates physical state based on valve type and energy.
        NO + Energized = Closed
        NO + De-energized = Open
        NC + Energized = Open
        NC + De-energized = Closed
        """
        if self.valve_type == TYPE_NORMALLY_OPEN:
            return not self._energized
        else:
            # Normally Closed
            return self._energized

class ControllableDevice:
    """
    Model representing a simple on/off device like a pump or compressor.
    """
    def __init__(self, name: str):
        self.name = name
        self._is_on = False

    @property
    def is_on(self) -> bool:
        return self._is_on

    @is_on.setter
    def is_on(self, state: bool):
        self._is_on = state

class DeviceControlWidget(ttk.Frame):
    """
    A GUI frame to control a simple on/off device.
    """
    def __init__(self, parent, device: ControllableDevice):
        super().__init__(parent)
        self.device = device
        self.tk_is_on_var = tk.BooleanVar(value=False)

        # UI Setup
        self._setup_ui()

        # Initial status update
        self._update_status_display()

    def _setup_ui(self):
        # Frame border for visual separation
        self.config(relief="groove", padding=10, borderwidth=1)

        # 1. Device Name Label
        lbl_info = ttk.Label(self, text=self.device.name, width=25, anchor="w")
        lbl_info.pack(side="left", padx=10)

        # 2. Control Checkbox
        self.chk_control = ttk.Checkbutton(
            self,
            text="Turn ON",
            variable=self.tk_is_on_var,
            command=self._on_toggle
        )
        self.chk_control.pack(side="left", padx=20)

        # 3. Status Indicator
        self.lbl_status = tk.Label(
            self,
            text="STATUS",
            width=12,
            font=("Arial", 10, "bold"),
            relief="sunken",
            borderwidth=2
        )
        self.lbl_status.pack(side="right", padx=10)

    def _on_toggle(self):
        is_checked = self.tk_is_on_var.get()
        self.device.is_on = is_checked
        self._update_status_display()

    def _update_status_display(self):
        """
        Updates the status label color and text based on device state.
        """
        if self.device.is_on:
            self.lbl_status.config(text="ON", bg="#4CAF50", fg="white")  # Green
        else:
            self.lbl_status.config(text="OFF", bg="#F44336", fg="white")  # Red

class ValveControlWidget(ttk.Frame):
    """
    A specific GUI frame to control a single Valve object.
    """
    def __init__(self, parent, valve: PneumaticValve, on_update=None):
        super().__init__(parent)
        self.valve = valve
        self.on_update = on_update
        self.tk_energize_var = tk.BooleanVar(value=False)
        
        # UI Setup
        self._setup_ui()
        
        # Initial status update
        self._update_status_display()

    def _setup_ui(self):
        # Frame border for visual separation
        self.config(relief="groove", padding=10, borderwidth=1)
        
        # 1. Valve Name & Type Label
        info_text = f"{self.valve.name}\n({self.valve.valve_type})"
        lbl_info = ttk.Label(self, text=info_text, width=25, anchor="w")
        lbl_info.pack(side="left", padx=10)

        # 2. Control Checkbox (Controls the solenoid/coil)
        # We use command=self._on_toggle to update logic immediately
        self.chk_control = ttk.Checkbutton(
            self, 
            text="Energize Solenoid", 
            variable=self.tk_energize_var,
            command=self._on_toggle
        )
        self.chk_control.pack(side="left", padx=20)

        # 3. Status Indicator (Visual Feedback of flow)
        self.lbl_status = tk.Label(
            self, 
            text="STATUS", 
            width=12, 
            font=("Arial", 10, "bold"),
            relief="sunken",
            borderwidth=2
        )
        self.lbl_status.pack(side="right", padx=10)

    def _on_toggle(self):
        # Update the model object
        is_checked = self.tk_energize_var.get()
        self.valve.is_energized = is_checked
        
        # Update the visual display
        self._update_status_display()
        
        # Trigger external update (Diagram) if callback exists
        if self.on_update:
            self.on_update()

    def _update_status_display(self):
        """
        Updates the status label color and text based on physical flow.
        """
        if self.valve.is_physically_open:
            self.lbl_status.config(text="OPEN (Flow)", bg="#4CAF50", fg="white") # Green
        else:
            self.lbl_status.config(text="CLOSED", bg="#F44336", fg="white") # Red

    def refresh_from_model(self):
        """
        Updates the checkbox state to match the model (used when model changes externally).
        """
        self.tk_energize_var.set(self.valve.is_energized)
        self._update_status_display()

class FlowDiagram(tk.Canvas):
    """
    Canvas to visualize gas flow.
    Blue = Flowing Gas
    Red = No Flow
    """
    def __init__(self, parent, valves, on_valve_click=None):
        super().__init__(parent, bg="white", width=950, height=720, highlightthickness=0)
        self.valves = valves  # List of 6 PneumaticValve objects
        self.on_valve_click = on_valve_click
        self.valve_positions = [] # Store coordinates for updates
        
        # Colors
        self.COLOR_FLOW = "#2196F3"  # Blue
        self.COLOR_STOP = "#F44336"  # Red
        self.COLOR_VALVE = "#607D8B" # Grey
        
        # Generate Valve Assets (PIL Images)
        self._create_valve_images()

        self.draw_layout()
        self.update_flow()

    def _create_valve_images(self):
        """Generates transparent PNG-style images in memory using Pillow."""
        size = 64
        center = size // 2
        radius = 24
        
        def create_base():
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            # Draw Circle (White fill, Black outline)
            draw.ellipse(
                [center - radius, center - radius, center + radius, center + radius],
                fill="white", outline="black", width=3
            )
            return img, draw

        # 1. Closed Image (Red X)
        self.img_closed_pil, draw_c = create_base()
        d = 12
        draw_c.line([center - d, center - d, center + d, center + d], fill="red", width=4)
        draw_c.line([center - d, center + d, center + d, center - d], fill="red", width=4)
        self.tk_img_closed = ImageTk.PhotoImage(self.img_closed_pil)

        # 2. Open Image (Black Arrow <->)
        self.img_open_pil, draw_o = create_base()
        d_arr = 15
        draw_o.line([center - d_arr, center, center + d_arr, center], fill="black", width=3)
        # Arrow heads
        h = 5
        draw_o.line([center - d_arr, center, center - d_arr + h, center - h], fill="black", width=3)
        draw_o.line([center - d_arr, center, center - d_arr + h, center + h], fill="black", width=3)
        draw_o.line([center + d_arr, center, center + d_arr - h, center - h], fill="black", width=3)
        draw_o.line([center + d_arr, center, center + d_arr - h, center + h], fill="black", width=3)
        self.tk_img_open = ImageTk.PhotoImage(self.img_open_pil)

    def draw_layout(self):
        """Draws the static text and pipes (tags will be used to update colors)"""
        self.delete("all")
        
        # Scaling factors
        SCALE = 1.6
        X_OFF = 50
        Y_OFF = 50
        
        # Define Coordinates for nodes (Scaled up)
        start       = (X_OFF + 50*SCALE,  Y_OFF + 200*SCALE)
        v1_pos      = (X_OFF + 100*SCALE, Y_OFF + 200*SCALE)
        fork_main   = (X_OFF + 150*SCALE, Y_OFF + 200*SCALE)
        
        # Top Branch (V2)
        v2_in_turn  = (X_OFF + 150*SCALE, Y_OFF + 100*SCALE)
        v2_pos      = (X_OFF + 220*SCALE, Y_OFF + 100*SCALE)
        v2_fork     = (X_OFF + 300*SCALE, Y_OFF + 100*SCALE)
        chamber_pos = (X_OFF + 300*SCALE, Y_OFF + 50*SCALE)
        v4_pos      = (X_OFF + 360*SCALE, Y_OFF + 100*SCALE)
        
        # Bottom Branch (V3)
        v3_in_turn  = (X_OFF + 150*SCALE, Y_OFF + 300*SCALE)
        v3_pos      = (X_OFF + 220*SCALE, Y_OFF + 300*SCALE)
        v3_fork     = (X_OFF + 300*SCALE, Y_OFF + 300*SCALE)
        bottle_pos  = (X_OFF + 300*SCALE, Y_OFF + 350*SCALE)
        v5_pos      = (X_OFF + 360*SCALE, Y_OFF + 300*SCALE)
        
        # Middle (Compressor)
        comp_pos    = (X_OFF + 240*SCALE, Y_OFF + 200*SCALE) 
        comp_out_pos = (X_OFF + 330*SCALE, Y_OFF + 200*SCALE)

        # Merge & Exit
        merge_top   = (X_OFF + 420*SCALE, Y_OFF + 100*SCALE)
        merge_btm   = (X_OFF + 420*SCALE, Y_OFF + 300*SCALE)
        merge_mid   = (X_OFF + 420*SCALE, Y_OFF + 200*SCALE)
        v6_pos      = (X_OFF + 460*SCALE, Y_OFF + 200*SCALE)
        exhaust_pos = (X_OFF + 530*SCALE, Y_OFF + 200*SCALE)

        # Styles
        PIPE_W = 8
        FONT_LBL = ("Helvetica", 11, "bold")
        FONT_VALVE = ("Helvetica", 10, "bold")
        
        # Common line kwargs for cleaner look (Anti-aliasing effect via round caps)
        line_opts = {'width': PIPE_W, 'capstyle': tk.ROUND, 'joinstyle': tk.ROUND}

        # --- Draw Text Labels ---
        self.create_text(start[0], start[1]-30, text="Gas Bottle IN", font=FONT_LBL)
        self.create_text(chamber_pos[0], chamber_pos[1]-30, text="Loading\nChamber", font=FONT_LBL, justify="center")
        self.create_text(bottle_pos[0], bottle_pos[1]+40, text="Lecture\nBottle", font=FONT_LBL, justify="center")
        self.create_text(comp_pos[0], comp_pos[1]+30, text="Compressor\nIN", font=FONT_LBL, justify="center")
        self.create_text(comp_out_pos[0], comp_out_pos[1]+30, text="Compressor\nOUT", font=FONT_LBL, justify="center")
        self.create_text(exhaust_pos[0], exhaust_pos[1]+30, text="Exhaust", font=FONT_LBL)

        # --- Draw Pipes (Grouped by Nodes) ---
        # Node 0: Inlet
        self.create_line(start, v1_pos, tags="valv_1", **line_opts)
        
        # Node 1: Manifold (Between V1, V2, V3)
        self.create_line(v1_pos, fork_main, tags="valv_1", **line_opts)
        self.create_line(fork_main, comp_pos, fill=self.COLOR_FLOW, arrow=tk.LAST, arrowshape=(16, 20, 6), **line_opts)
        
        self.create_line(fork_main, v2_in_turn, v2_pos, tags="valv_2", **line_opts)
        self.create_line(fork_main, v3_in_turn, v3_pos, tags="valv_3", **line_opts)
        
        # Node 2: Chamber Side (Between V2, V4, Chamber)
        self.create_line(v2_pos, v2_fork, tags="valv_2", **line_opts)
        self.create_line(v2_fork, chamber_pos, fill=self.COLOR_FLOW, **line_opts)
        self.create_line(v2_fork, v4_pos, tags="valv_4", **line_opts)
        
        # Node 3: Bottle Side (Between V3, V5, Bottle)
        self.create_line(v3_pos, v3_fork, tags="valv_3", **line_opts)
        self.create_line(v3_fork, bottle_pos, fill=self.COLOR_FLOW, **line_opts)
        self.create_line(v3_fork, v5_pos, tags="valv_5", **line_opts)
        
        # Node 4: Merge (Between V4, V5, V6)
        self.create_line(v4_pos, merge_top, merge_mid, tags="valv_4", **line_opts)
        self.create_line(v5_pos, merge_btm, merge_mid, tags="valv_5", **line_opts)
        self.create_line(comp_out_pos, merge_mid, fill=self.COLOR_FLOW, arrow=tk.LAST, arrowshape=(16, 20, 6), **line_opts)
        self.create_line(merge_mid, v6_pos, tags="valv_6", **line_opts)
        
        # Node 5: Exhaust (After V6)
        self.create_line(v6_pos, exhaust_pos, tags="valv_6", **line_opts)

        # --- Draw Valves (Overlay) ---
        valve_coords = [
            (v1_pos, "V1"), (v2_pos, "V2"), (v3_pos, "V3"),
            (v4_pos, "V4"), (v5_pos, "V5"), (v6_pos, "V6")
        ]
        
        self.valve_positions = [] # Clear previous
        for i, ((x, y), name) in enumerate(valve_coords):
            self.valve_positions.append((x, y))
            
            # Group tag for click binding
            tag_id = f"valve_obj_{i}"
            img_tag = f"valve_img_{i}"
            
            # Draw Valve Image (Starts Closed)
            self.create_image(x, y, image=self.tk_img_closed, tags=(tag_id, img_tag))
            self.create_text(x, y-38, text=name, font=FONT_VALVE, tags=tag_id)
            
            # Bind click event
            self.tag_bind(tag_id, "<Button-1>", lambda event, idx=i: self._on_valve_click_handler(idx))

    def _on_valve_click_handler(self, index):
        valve = self.valves[index]
        # Toggle logic: Assuming user wants to flip the physical state.
        # Since logic is: Energize -> toggle physical, we toggle energized.
        valve.is_energized = not valve.is_energized
        
        # Update visuals
        self.update_flow()
        
        # Notify App to update checkboxes
        if self.on_valve_click:
            self.on_valve_click()

    def update_flow(self):
        """Calculates flow logic and updates pipe colors"""
        
        # Update colors based on direct valve ownership of the line segment
        for i, valve in enumerate(self.valves):
            tag = f"valv_{i+1}" # valv_1 to valv_6
            col = self.COLOR_FLOW if valve.is_physically_open else self.COLOR_STOP
            self.itemconfig(tag, fill=col)
            
        # Update Valve Images
        for i, valve in enumerate(self.valves):
            img_tag = f"valve_img_{i}"
            
            if valve.is_physically_open:
                self.itemconfig(img_tag, image=self.tk_img_open)
            else:
                self.itemconfig(img_tag, image=self.tk_img_closed)

class GasLoadingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gas Loading System Control")
        self.geometry("1200x750")
        
        # Main Title
        header = ttk.Label(self, text="Gas Loading System Control", font=("Helvetica", 16, "bold"))
        header.pack(pady=15)

        # Create Main Layout (Left: Controls, Right: Diagram)
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side="left", fill="y", padx=10)
        
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side="left", fill="both", expand=True, padx=10)

        # --- Setup Left Panel (Controls) ---
        valve_header = ttk.Label(left_panel, text="Pneumatic Valve Controls", font=("Helvetica", 12, "bold"))
        valve_header.pack(pady=(10, 5))

        self.valve_container = ttk.Frame(left_panel)
        self.valve_container.pack(fill="x", expand=False, padx=20)

        equip_header = ttk.Label(left_panel, text="Equipment Controls", font=("Helvetica", 12, "bold"))
        equip_header.pack(pady=(20, 5))

        self.equipment_container = ttk.Frame(left_panel)
        self.equipment_container.pack(fill="x", expand=False, padx=20)

        # --- Initialize System ---
        self.valves = []
        self.valve_widgets = [] # Keep track of widgets to sync them
        self.setup_system(right_panel)
        self.create_equipment()

    def create_equipment(self):
        equipment_configs = ["Compressor", "Vacuum Pump"]
        for name in equipment_configs:
            device_obj = ControllableDevice(name)
            row_widget = DeviceControlWidget(self.equipment_container, device_obj)
            row_widget.pack(fill="x", pady=5)

    def setup_system(self, diagram_parent):
        # 1. Define Configuration based on user diagram description
        valve_configs = [
            ("Valve 1 (Main Inlet)", TYPE_NORMALLY_CLOSED),
            ("Valve 2 (Branch A)", TYPE_NORMALLY_OPEN),
            ("Valve 3 (Branch B)", TYPE_NORMALLY_OPEN),
            ("Valve 4 (Chamber Line)", TYPE_NORMALLY_OPEN),
            ("Valve 5 (Bottle Line)", TYPE_NORMALLY_OPEN),
            ("Valve 6 (Exhaust)", TYPE_NORMALLY_CLOSED),
        ]

        # 2. Create Logic Objects
        for name, v_type in valve_configs:
            valve_obj = PneumaticValve(name, v_type)
            self.valves.append(valve_obj)

        # 3. Create Diagram (Passes reference to valves + sync callback)
        self.diagram = FlowDiagram(diagram_parent, self.valves, on_valve_click=self.sync_widgets)
        self.diagram.pack(fill="both", expand=True)
        
        # 4. Create Control Widgets (Passes reference to diagram update)
        for valve_obj in self.valves:
            row_widget = ValveControlWidget(
                self.valve_container, 
                valve_obj, 
                on_update=self.diagram.update_flow
            )
            row_widget.pack(fill="x", pady=5)
            self.valve_widgets.append(row_widget)

    def sync_widgets(self):
        """Called when diagram is clicked; updates checkboxes to match."""
        for widget in self.valve_widgets:
            widget.refresh_from_model()

if __name__ == "__main__":
    app = GasLoadingApp()
    app.mainloop()
