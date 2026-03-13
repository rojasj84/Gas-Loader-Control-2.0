import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw, ImageTk
import math
import json
import os

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

        # 2. Status Indicator / Button
        self.lbl_status = tk.Label(
            self,
            text="STATUS",
            width=12,
            font=("Arial", 10, "bold"),
            relief="raised",
            borderwidth=2,
            cursor="hand2"
        )
        self.lbl_status.pack(side="right", padx=10)
        self.lbl_status.bind("<Button-1>", lambda e: self._on_toggle())

    def _on_toggle(self):
        # Safety: Ignore clicks if currently in cool-down (debounce)
        if getattr(self, "_debounce", False):
            return
        self._debounce = True
        self.after(500, lambda: setattr(self, "_debounce", False))

        self.device.is_on = not self.device.is_on
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
        
        # UI Setup
        self._setup_ui()
        
        # Initial status update
        self._update_status_display()

    def _setup_ui(self):
        # Frame border for visual separation
        self.config(relief="groove", padding=2, borderwidth=1)
        
        # 1. Valve Name & Type Label
        info_text = f"{self.valve.name}"
        lbl_info = ttk.Label(self, text=info_text, width=22, anchor="w")
        lbl_info.pack(side="left", padx=5)

        # 2. Status Indicator / Button
        self.lbl_status = tk.Label(
            self, 
            text="STS", 
            width=12, 
            font=("Arial", 9, "bold"),
            relief="raised",
            borderwidth=2,
            cursor="hand2"
        )
        self.lbl_status.pack(side="right", padx=5)
        self.lbl_status.bind("<Button-1>", lambda e: self._on_toggle())

    def _on_toggle(self):
        # Safety: Ignore clicks if currently in cool-down (debounce)
        if getattr(self, "_debounce", False):
            return
        self._debounce = True
        self.after(500, lambda: setattr(self, "_debounce", False))

        # Update the model object
        self.valve.is_energized = not self.valve.is_energized
        
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
            self.lbl_status.config(text="OPEN", bg="#4CAF50", fg="white") # Green
        else:
            self.lbl_status.config(text="CLOSED", bg="#F44336", fg="white") # Red

    def refresh_from_model(self):
        """
        Updates the status display to match the model (used when model changes externally).
        """
        self._update_status_display()

class PressureGauge(tk.Canvas):
    """
    A visual pressure gauge widget using Pillow for high-quality super-sampled rendering.
    """
    def __init__(self, parent, min_val, max_val, title, size=160, **kwargs):
        super().__init__(parent, width=size, height=size + 40, bg="#2b2b2b", highlightthickness=0, **kwargs)
        self.min_val = min_val
        self.max_val = max_val
        self.title_text = title
        self.size = size
        self.cx = size / 2
        self.cy = size / 2
        self.current_val = min_val
        
        # Pre-render the static dial face (background)
        self._create_face_image()
        
        # Create canvas item for the gauge image
        self.img_item = self.create_image(0, 0, anchor="nw")
        
        # Overlay Text (Crisper when drawn natively by Tkinter on top)
        self.create_text(self.cx, self.cy + 40, text=self.title_text, font=("Helvetica", 9, "bold"), fill="#b0b0b0")
        self.text_val = self.create_text(self.cx, self.size + 20, text=str(min_val), font=("Helvetica", 16, "bold"), fill="white")
        
        self.set_value(min_val)

    def _create_face_image(self):
        """Generates the static background using super-sampling for smoothness."""
        scale = 4
        s_size = self.size * scale
        
        img = Image.new("RGBA", (s_size, s_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 1. Dark Face with Light Border
        margin = 2 * scale
        draw.ellipse([margin, margin, s_size-margin, s_size-margin], fill="#383838", outline="#90A4AE", width=3*scale)
        
        # 2. Colored Arcs (PIL angles: 0 is 3 o'clock, clockwise)
        # We map the 270 deg span: SW (135 deg) to SE (405 deg)
        rect = [margin + 10*scale, margin + 10*scale, s_size - margin - 10*scale, s_size - margin - 10*scale]
        width_px = 12 * scale
        
        # Green (0-70%): 135 to 324 (189 deg span)
        draw.arc(rect, start=135, end=324, fill="#4CAF50", width=width_px)
        # Yellow (70-90%): 324 to 378 (54 deg span)
        draw.arc(rect, start=324, end=378, fill="#FFC107", width=width_px)
        # Red (90-100%): 378 to 405 (27 deg span)
        draw.arc(rect, start=378, end=405, fill="#F44336", width=width_px)
        
        self.base_image = img

    def set_value(self, val):
        """Updates the needle position and text readout."""
        self.current_val = max(self.min_val, min(val, self.max_val))
        
        # Update text
        self.itemconfig(self.text_val, text=f"{int(self.current_val)}")
        
        # Create composition for needle
        img = self.base_image.copy()
        draw = ImageDraw.Draw(img)
        
        scale = 4
        s_size = self.size * scale
        cx, cy = s_size / 2, s_size / 2
        
        # Calculate angle
        # 0 value = 225 degrees (SW), Max value = -45 degrees (SE)
        pct = (self.current_val - self.min_val) / (self.max_val - self.min_val)
        angle_deg = 225 - (pct * 270)
        angle_rad = math.radians(angle_deg)
        
        # Needle Geometry
        tip_r = (self.size / 2 - 15) * scale
        tip_x = cx + tip_r * math.cos(angle_rad)
        tip_y = cy - tip_r * math.sin(angle_rad) # Canvas Y is inverted relative to standard math
        
        # Draw Needle
        draw.line([cx, cy, tip_x, tip_y], fill="white", width=4*scale)
        # Hub
        hub_r = 6 * scale
        draw.ellipse([cx-hub_r, cy-hub_r, cx+hub_r, cy+hub_r], fill="white")
        
        # Resize with LANCZOS for quality
        if hasattr(Image, "Resampling"):
            resample = Image.Resampling.LANCZOS
        else:
            resample = Image.LANCZOS
            
        self.tk_image = ImageTk.PhotoImage(img.resize((self.size, self.size), resample))
        self.itemconfig(self.img_item, image=self.tk_image)

class FlowDiagram(tk.Canvas):
    """
    Canvas to visualize gas flow.
    Blue = Flowing Gas
    Red = No Flow
    """
    def __init__(self, parent, valves, on_valve_click=None):
        super().__init__(parent, bg="#2b2b2b", width=1200, height=720, highlightthickness=0)
        self.valves = valves  # List of 6 PneumaticValve objects
        self.on_valve_click = on_valve_click
        self.valve_positions = [] # Store coordinates for updates
        
        # Colors
        self.COLOR_FLOW = "#2196F3"  # Blue
        self.COLOR_STOP = "#F44336"  # Red
        self.COLOR_VALVE = "#607D8B" # Grey
        
        # Generate Valve Assets (PIL Images)
        self._create_valve_images()
        # Generate Compressor Asset
        self._create_compressor_image()
        
        # Initialize Pressure Gauges
        self.gauge_inlet = PressureGauge(self, 0, 5000, "INLET PSI")
        self.gauge_chamber = PressureGauge(self, 0, 30000, "CHAMBER PSI")
        self.gauge_bottle = PressureGauge(self, 0, 5000, "BOTTLE PSI")

        self.draw_layout()
        self.update_flow()

    def _create_valve_images(self):
        """Generates more modern, visually appealing valve images in memory using Pillow."""
        # Target size for the UI
        target_size = 64

        # Super-sampling setup (Draw 4x larger, then resize down)
        scale = 4
        size = target_size * scale
        center = size // 2
        radius = 24 * scale

        # Colors for the new design
        VALVE_BODY_COLOR = "#B0BEC5"  # Blue Grey
        VALVE_BORDER_COLOR = "white"   # White border for Dark Mode
        OPEN_INDICATOR_COLOR = "#66BB6A" # Green
        CLOSED_INDICATOR_COLOR = "#EF5350" # Red

        def create_valve_icon(state: str):
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Draw valve body (circle)
            draw.ellipse(
                [center - radius, center - radius, center + radius, center + radius],
                fill=VALVE_BODY_COLOR, outline=VALVE_BORDER_COLOR, width=3 * scale
            )

            # Draw state indicator (a rotating bar)
            indicator_width = 18 * scale
            indicator_height = 6 * scale
            corner_rad = 3 * scale

            if state == 'open':
                # Horizontal bar for OPEN
                draw.rounded_rectangle(
                    [center - indicator_width, center - indicator_height,
                     center + indicator_width, center + indicator_height],
                    radius=corner_rad, fill=OPEN_INDICATOR_COLOR, outline="black", width=1 * scale
                )
            else: # 'closed'
                # Vertical bar for CLOSED
                draw.rounded_rectangle(
                    [center - indicator_height, center - indicator_width,
                     center + indicator_height, center + indicator_width],
                    radius=corner_rad, fill=CLOSED_INDICATOR_COLOR, outline="black", width=1 * scale
                )

            # Resize with LANCZOS for high-quality anti-aliasing
            # Check for Resampling enum (Pillow >= 9.1.0) or fallback to module constant
            if hasattr(Image, "Resampling"):
                resample_mode = Image.Resampling.LANCZOS
            else:
                resample_mode = Image.LANCZOS
            
            return img.resize((target_size, target_size), resample_mode)

        # 1. Closed Image (Red X)
        self.img_closed_pil = create_valve_icon(state='closed')
        self.tk_img_closed = ImageTk.PhotoImage(self.img_closed_pil)

        # 2. Open Image (Black Arrow <->)
        self.img_open_pil = create_valve_icon(state='open')
        self.tk_img_open = ImageTk.PhotoImage(self.img_open_pil)

    def _create_compressor_image(self):
        """Generates a refined icon of the compressor to show a reciprocating system."""
        # Target size (Width x Height)
        target_w, target_h = 160, 100
        scale = 4  # Super-sample for smoothness
        w, h = target_w * scale, target_h * scale

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Colors harmonized with the rest of the diagram
        COLOR_BLUE = "#1565C0"
        COLOR_DARK_BLUE = "#0D47A1"
        COLOR_METAL = "#B0BEC5"      # Same as valve body
        COLOR_DARK_METAL = "#78909C"
        COLOR_SKID = "#455A64"

        # 1. Skid Base
        skid_h = 12 * scale
        draw.rectangle([10*scale, h - skid_h, w - 10*scale, h], fill=COLOR_SKID)

        # Define component dimensions
        head_w = 35 * scale
        head_h = 70 * scale
        head_y = h - skid_h - head_h

        center_w = 50 * scale
        center_h = 50 * scale
        center_x = (w - center_w) // 2
        center_y = h - skid_h - center_h

        # 2. Connecting Rod Housings (drawn first to appear behind main components)
        rod_h = 40 * scale  # Shorter than crankcase
        rod_y = center_y + (center_h - rod_h) / 2  # Vertically centered with crankcase

        # Left housing - fills the gap between head and center
        draw.rectangle(
            [15*scale + head_w, rod_y, center_x, rod_y + rod_h],
            fill=COLOR_METAL, outline=COLOR_DARK_METAL, width=1*scale
        )
        # Right housing - fills the gap
        draw.rectangle(
            [center_x + center_w, rod_y, w - 15*scale - head_w, rod_y + rod_h],
            fill=COLOR_METAL, outline=COLOR_DARK_METAL, width=1*scale
        )

        # 3. Main Cylinders (drawn on top of housing edges)
        # Left Head
        draw.rounded_rectangle(
            [15*scale, head_y, 15*scale + head_w, head_y + head_h],
            radius=4*scale, fill=COLOR_BLUE, outline=COLOR_DARK_BLUE, width=2*scale
        )
        draw.rounded_rectangle(
            [w - 15*scale - head_w, head_y, w - 15*scale, head_y + head_h],
            radius=4*scale, fill=COLOR_BLUE, outline=COLOR_DARK_BLUE, width=2*scale
        )

        # 4. Central Crankcase/Motor (drawn on top of housing edges)
        draw.rectangle(
            [center_x, center_y, center_x + center_w, center_y + center_h],
            fill=COLOR_DARK_BLUE, outline="white", width=2*scale
        )

        # 5. Top Overhead Pipe (Cooler/Bypass)
        top_pipe_y = head_y - 15 * scale
        draw.rectangle([center_x + 10*scale, top_pipe_y, center_x + center_w - 10*scale, top_pipe_y + 8*scale], fill=COLOR_METAL)
        draw.rectangle([center_x + 10*scale, top_pipe_y, center_x + 15*scale, center_y], fill=COLOR_METAL) # Left Riser
        draw.rectangle([center_x + center_w - 15*scale, top_pipe_y, center_x + center_w - 10*scale, center_y], fill=COLOR_METAL) # Right Riser

        # Resize with LANCZOS
        if hasattr(Image, "Resampling"):
            resample_mode = Image.Resampling.LANCZOS
        else:
            resample_mode = Image.LANCZOS

        self.img_comp_pil = img.resize((target_w, target_h), resample_mode)
        self.tk_img_comp = ImageTk.PhotoImage(self.img_comp_pil)

    def draw_layout(self):
        """Draws the static text and pipes (tags will be used to update colors)"""
        self.delete("all")
        
        # Scaling factors
        SCALE = 1.5
        X_OFF = 220
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
        self.create_text(start[0], start[1]-30, text="Gas Bottle IN", font=FONT_LBL, fill="white")
        self.create_text(chamber_pos[0], chamber_pos[1]-30, text="Loading\nChamber", font=FONT_LBL, justify="center", fill="white")
        self.create_text(bottle_pos[0], bottle_pos[1]+40, text="Lecture\nBottle", font=FONT_LBL, justify="center", fill="white")
        # Moved labels down (+65) to accommodate the new compressor image
        self.create_text(comp_pos[0], comp_pos[1]+65, text="Compressor\nIN", font=FONT_LBL, justify="center", fill="white")
        self.create_text(comp_out_pos[0], comp_out_pos[1]+65, text="Compressor\nOUT", font=FONT_LBL, justify="center", fill="white")
        self.create_text(exhaust_pos[0], exhaust_pos[1]+30, text="Exhaust", font=FONT_LBL, fill="white")

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

        # --- Draw Equipment ---
        # Center the compressor image between the IN and OUT nodes
        comp_mid_x = (comp_pos[0] + comp_out_pos[0]) / 2
        self.create_image(comp_mid_x, comp_pos[1], image=self.tk_img_comp, tags="compressor")
        
        # --- Place Gauges (Window Objects) ---
        self.create_window(start[0] - 60, start[1] + 20, window=self.gauge_inlet, anchor="e")
        # Reposition gauges to the right of the merge line to avoid overlaps
        self.create_window(merge_top[0] + 40, chamber_pos[1], window=self.gauge_chamber, anchor="w")
        self.create_window(merge_btm[0] + 40, bottle_pos[1], window=self.gauge_bottle, anchor="w")

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
            self.create_text(x, y-38, text=name, font=FONT_VALVE, tags=tag_id, fill="white")
            
            # Bind click event
            self.tag_bind(tag_id, "<Button-1>", lambda event, idx=i: self._on_valve_click_handler(idx))

    def _on_valve_click_handler(self, index):
        # Safety: Ignore clicks if currently in cool-down (debounce)
        if getattr(self, "_debounce", False):
            return
        self._debounce = True
        self.after(500, lambda: setattr(self, "_debounce", False))

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

class SafetyConfigWindow(tk.Toplevel):
    """
    A popup window for configuring overpressure safety limits.
    """
    CHAMBER_ABS_MAX = 25000
    BOTTLE_ABS_MAX = 5000

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent # parent is the GasLoadingApp instance

        self.title("Overpressure Safety")
        self.transient(parent)
        self.grab_set() # Modal behavior
        self.resizable(False, False)

        # Use parent's style for dark mode consistency
        style = ttk.Style(self)
        style.theme_use('clam')
        BG_COLOR = "#2b2b2b"
        FG_COLOR = "white"
        BORDER_COLOR = "#444444"
        LIGHT_COLOR = "#3a3a3a"
        DARK_COLOR = "#1c1c1c"
        
        self.configure(bg=BG_COLOR)
        style.configure("TFrame", background=BG_COLOR, bordercolor=BORDER_COLOR, lightcolor=LIGHT_COLOR, darkcolor=DARK_COLOR)
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR)
        style.configure("TLabelframe", background=BG_COLOR, bordercolor=BORDER_COLOR, lightcolor=LIGHT_COLOR, darkcolor=DARK_COLOR)
        style.configure("TLabelframe.Label", background=BG_COLOR, foreground=FG_COLOR)
        style.configure("TButton", background=BG_COLOR, foreground=FG_COLOR, bordercolor=BORDER_COLOR, lightcolor=LIGHT_COLOR, darkcolor=DARK_COLOR)

        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        # --- Data Variables ---
        self.chamber_limit_var = tk.StringVar(value=str(self.parent.chamber_pressure_limit))
        self.bottle_limit_var = tk.StringVar(value=str(self.parent.bottle_pressure_limit))

        # --- Chamber Pressure Setting ---
        chamber_frame = ttk.LabelFrame(main_frame, text="Chamber Pressure Limit", padding=10)
        chamber_frame.pack(fill="x", pady=5)

        ttk.Label(chamber_frame, text=f"(Absolute Max: {self.CHAMBER_ABS_MAX} PSI)").pack(anchor="w")
        chamber_entry = ttk.Entry(chamber_frame, textvariable=self.chamber_limit_var, width=15, font=("Helvetica", 12))
        chamber_entry.pack(pady=5, anchor="w")

        # --- Bottle Pressure Setting ---
        bottle_frame = ttk.LabelFrame(main_frame, text="Lecture Bottle Pressure Limit", padding=10)
        bottle_frame.pack(fill="x", pady=5)

        ttk.Label(bottle_frame, text=f"(Absolute Max: {self.BOTTLE_ABS_MAX} PSI)").pack(anchor="w")
        bottle_entry = ttk.Entry(bottle_frame, textvariable=self.bottle_limit_var, width=15, font=("Helvetica", 12))
        bottle_entry.pack(pady=5, anchor="w")

        # --- Buttons ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(20, 0))

        save_btn = ttk.Button(btn_frame, text="Save", command=self._on_save)
        save_btn.pack(side="right", padx=5)

        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.destroy)
        cancel_btn.pack(side="right")

    def _on_save(self):
        try:
            chamber_val = int(self.chamber_limit_var.get())
            if not (0 < chamber_val <= self.CHAMBER_ABS_MAX):
                messagebox.showerror("Invalid Value", f"Chamber pressure must be between 1 and {self.CHAMBER_ABS_MAX}.", parent=self)
                return

            bottle_val = int(self.bottle_limit_var.get())
            if not (0 < bottle_val <= self.BOTTLE_ABS_MAX):
                messagebox.showerror("Invalid Value", f"Bottle pressure must be between 1 and {self.BOTTLE_ABS_MAX}.", parent=self)
                return

            self.parent.chamber_pressure_limit = chamber_val
            self.parent.bottle_pressure_limit = bottle_val
            self.parent.save_config()
            self.destroy()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid integer numbers for pressure limits.", parent=self)

class RelayConfigWindow(tk.Toplevel):
    """
    A popup window to map software devices to physical Denkovi Relay IDs.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Relay Assignment")
        self.geometry("500x600")
        self.transient(parent)
        self.grab_set()
        
        # Theme Setup
        style = ttk.Style(self)
        style.theme_use('clam')
        BG_COLOR = "#2b2b2b"
        FG_COLOR = "white"
        self.configure(bg=BG_COLOR)
        
        # Header
        lbl_header = ttk.Label(self, text="Map Devices to Relay Board (1-16)", font=("Helvetica", 14, "bold"))
        lbl_header.pack(pady=15)

        # Scrollable Frame for entries
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=20, pady=5)
        
        self.combos = {} # {device_name: Combobox}

        # Collect all configurable devices
        # 1. Valves
        devices = [v.name for v in self.parent.valves]
        # 2. Compressor
        devices.append(self.parent.comp_device.name)
        # 3. Other Equipment
        devices.extend([d.name for d in self.parent.equipment_devices])

        # Relay Options: None + 1..16
        options = ["None"] + [str(i) for i in range(1, 17)]

        for dev_name in devices:
            row = ttk.Frame(container)
            row.pack(fill="x", pady=5)
            
            lbl = ttk.Label(row, text=dev_name, width=30, anchor="w")
            lbl.pack(side="left")
            
            current_relay = self.parent.relay_assignments.get(dev_name, "None")
            
            cb = ttk.Combobox(row, values=options, state="readonly", width=10)
            cb.set(current_relay)
            cb.pack(side="right")
            
            self.combos[dev_name] = cb

        # Save Button
        btn_save = ttk.Button(self, text="Save Assignments", command=self._on_save)
        btn_save.pack(pady=20)

    def _on_save(self):
        # Update parent assignments
        for dev_name, cb in self.combos.items():
            val = cb.get()
            if val == "None":
                if dev_name in self.parent.relay_assignments:
                    del self.parent.relay_assignments[dev_name]
            else:
                self.parent.relay_assignments[dev_name] = int(val)
        
        self.parent.save_config()
        self.destroy()

class SensorConfigWindow(tk.Toplevel):
    """
    A popup window to map pressure sensors to NI USB-6001 Analog Input channels.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Sensor Assignment")
        self.geometry("450x450")
        self.transient(parent)
        self.grab_set()

        # Theme Setup
        style = ttk.Style(self)
        style.theme_use('clam')
        BG_COLOR = "#2b2b2b"
        self.configure(bg=BG_COLOR)

        # Header
        lbl_header = ttk.Label(self, text="Map Sensors to Differential Pairs", font=("Helvetica", 12, "bold"))
        lbl_header.pack(pady=15)

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=20, pady=5)

        self.combos = {}
        
        # Sensor Names defined in requirements
        sensors = [
            "Inlet Pressure",
            "Chamber Pressure",
            "Lecture Bottle Pressure",
            "Air Drive Pressure"
        ]
        
        # Differential Pair Mapping for NI USB-6001
        self.diff_map = {
            0: "ai0 (+) & ai4 (-)",
            1: "ai1 (+) & ai5 (-)",
            2: "ai2 (+) & ai6 (-)",
            3: "ai3 (+) & ai7 (-)"
        }
        options = ["None"] + list(self.diff_map.values())

        for sensor_name in sensors:
            row = ttk.Frame(container)
            row.pack(fill="x", pady=5)
            
            lbl = ttk.Label(row, text=sensor_name, width=25, anchor="w")
            lbl.pack(side="left")
            
            # Retrieve current setting and convert to Pair String
            current_int = self.parent.sensor_assignments.get(sensor_name, None)
            current_val = "None"
            if current_int is not None and current_int in self.diff_map:
                current_val = self.diff_map[current_int]
            
            cb = ttk.Combobox(row, values=options, state="readonly", width=10)
            cb.set(current_val)
            cb.pack(side="right")
            
            self.combos[sensor_name] = cb

        # Save Button
        btn_save = ttk.Button(self, text="Save Assignments", command=self._on_save)
        btn_save.pack(pady=20)

    def _on_save(self):
        for name, cb in self.combos.items():
            val = cb.get()
            if val == "None":
                if name in self.parent.sensor_assignments:
                    del self.parent.sensor_assignments[name]
            else:
                # Reverse lookup the integer index from the pair string
                for k, v in self.diff_map.items():
                    if v == val:
                        self.parent.sensor_assignments[name] = k
                        break
        
        self.parent.save_config()
        self.destroy()

class GasLoadingApp(tk.Tk):
    CONFIG_FILE = "config.json"

    def __init__(self):
        super().__init__()
        self.title("Gas Loading System Control")
        self.geometry("1600x900")
        
        # --- Menu Bar Setup ---
        self._setup_menu()
        
        # --- Dark Mode Theme Setup ---
        BG_COLOR = "#2b2b2b"
        FG_COLOR = "white"
        
        self.configure(bg=BG_COLOR)
        
        style = ttk.Style(self)
        style.theme_use('clam') # 'clam' theme allows for easier color customization
        
        # Dark Mode Theme Configuration
        BORDER_COLOR = "#444444"
        LIGHT_COLOR = "#3a3a3a"
        DARK_COLOR = "#1c1c1c"
        
        style.configure("TFrame", background=BG_COLOR, bordercolor=BORDER_COLOR, lightcolor=LIGHT_COLOR, darkcolor=DARK_COLOR)
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR)
        style.configure("TCheckbutton", background=BG_COLOR, foreground=FG_COLOR, indicatorcolor=BG_COLOR, activebackground=BG_COLOR, activeforeground=FG_COLOR)
        style.configure("TButton", background=BG_COLOR, foreground=FG_COLOR, bordercolor=BORDER_COLOR, lightcolor=LIGHT_COLOR, darkcolor=DARK_COLOR)
        style.configure("TLabelframe", background=BG_COLOR, bordercolor=BORDER_COLOR, lightcolor=LIGHT_COLOR, darkcolor=DARK_COLOR)
        style.configure("TLabelframe.Label", background=BG_COLOR, foreground=FG_COLOR)
        
        # --- Header Section ---
        header_frame = ttk.Frame(self)
        header_frame.pack(side="top", fill="x", padx=20, pady=15)
        
        # 1. Logo (Top Left)
        try:
            logo_path = "/home/javierrojas/Programming/Gas Loader Control 2.0/Logo_CarnegieScience_primary_white_RGB.png"
            pil_img = Image.open(logo_path)
            
            # Resize with Super Sampling (LANCZOS)
            target_h = 120
            aspect_ratio = pil_img.width / pil_img.height
            target_w = int(target_h * aspect_ratio)
            
            if hasattr(Image, "Resampling"):
                resample_mode = Image.Resampling.LANCZOS
            else:
                resample_mode = Image.LANCZOS
                
            pil_img = pil_img.resize((target_w, target_h), resample_mode)
            self.tk_logo_img = ImageTk.PhotoImage(pil_img)
            
            lbl_logo = ttk.Label(header_frame, image=self.tk_logo_img)
            lbl_logo.pack(side="left")
        except Exception as e:
            print(f"Error loading logo: {e}")

        # 2. Main Title (Right of the logo)
        lbl_title = ttk.Label(header_frame, text="Gas Loading System Control", font=("Helvetica", 22, "bold"))
        lbl_title.pack(side="left", padx=15)

        # Create Main Layout (Left: Controls, Right: Diagram)
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side="left", fill="y", padx=10)
        
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side="left", fill="both", expand=True, padx=10)

        # --- Setup Left Panel (Controls) ---
        # 1. Pneumatics Frame (Air Drive + Compressor + Valves)
        self.pneu_frame = ttk.LabelFrame(left_panel, text="Pneumatics", padding=10)
        self.pneu_frame.pack(fill="x", padx=10, pady=10)

        # Air Drive Display
        self.frm_air_drive = ttk.Frame(self.pneu_frame, relief="groove", padding=5, borderwidth=1)
        self.frm_air_drive.pack(fill="x", pady=(0, 10))
        
        ttk.Label(self.frm_air_drive, text="Air Drive System", font=("Helvetica", 11)).pack(side="left", padx=5)
        self.lbl_air_drive = ttk.Label(self.frm_air_drive, text="0 PSI", font=("Helvetica", 11, "bold"), foreground="#29B6F6")
        self.lbl_air_drive.pack(side="right", padx=5)

        # Compressor (Pneumatic Driven)
        self.comp_device = ControllableDevice("Compressor")
        self.comp_widget = DeviceControlWidget(self.pneu_frame, self.comp_device)
        self.comp_widget.pack(fill="x", pady=5)

        # Valves
        ttk.Label(self.pneu_frame, text="Valves", font=("Helvetica", 11, "bold")).pack(pady=(10, 5), anchor="w")
        self.valve_container = ttk.Frame(self.pneu_frame)
        self.valve_container.pack(fill="x", expand=False)

        # 2. Electric Equipment Frame
        self.equip_frame = ttk.LabelFrame(left_panel, text="Electric Equipment", padding=10)
        self.equip_frame.pack(fill="x", padx=10, pady=10)

        self.equipment_container = ttk.Frame(self.equip_frame)
        self.equipment_container.pack(fill="x", expand=False)

        # --- Initialize System ---
        self.valves = []
        self.valve_widgets = [] # Keep track of widgets to sync them

        # --- Safety Configuration (with defaults) ---
        self.relay_assignments = {} # { "Device Name": RelayID_int }
        self.sensor_assignments = {} # { "Sensor Name": Channel_int }
        self.chamber_pressure_limit = 25000
        self.bottle_pressure_limit = 5000
        self.load_config()

        self.setup_system(right_panel)
        self.create_equipment()

    def create_equipment(self):
        self.equipment_devices = []
        equipment_configs = ["Vacuum Pump", "Motor CW", "Motor CCW"]
        for name in equipment_configs:
            device_obj = ControllableDevice(name)
            self.equipment_devices.append(device_obj)
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

    def load_config(self):
        """Loads user settings from JSON file."""
        if not os.path.exists(self.CONFIG_FILE):
            return

        try:
            with open(self.CONFIG_FILE, "r") as f:
                data = json.load(f)
                self.chamber_pressure_limit = data.get("chamber_pressure_limit", 25000)
                self.bottle_pressure_limit = data.get("bottle_pressure_limit", 5000)
                self.relay_assignments = data.get("relay_assignments", {})
                self.sensor_assignments = data.get("sensor_assignments", {})
        except Exception as e:
            print(f"Error loading configuration: {e}")

    def save_config(self):
        """Saves current settings to JSON file."""
        data = {
            "chamber_pressure_limit": self.chamber_pressure_limit,
            "bottle_pressure_limit": self.bottle_pressure_limit,
            "relay_assignments": self.relay_assignments,
            "sensor_assignments": self.sensor_assignments
        }
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            messagebox.showerror("Configuration Error", f"Failed to save settings: {e}")

    def _setup_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.quit)

        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuration", menu=config_menu)

        config_menu.add_command(label="Overpressure Safety", command=self._open_safety_config)
        config_menu.add_command(label="Relay Assignment", command=self._open_relay_config)
        config_menu.add_command(label="Sensor Assignment", command=self._open_sensor_config)

    def _open_safety_config(self):
        config_window = SafetyConfigWindow(self)
        config_window.wait_window() # Wait until the config window is closed

    def _open_relay_config(self):
        RelayConfigWindow(self)

    def _open_sensor_config(self):
        SensorConfigWindow(self)

if __name__ == "__main__":
    app = GasLoadingApp()
    app.mainloop()
