"""
Standalone Floating Desktop Toast Window.
Renders an unmissable, modern top-most toast in the bottom-right corner of the desktop,
visible on top of all applications (Antigravity, IDEs, browsers).
"""

import sys
import tkinter as tk


def show_toast(title: str, message: str, duration_ms: int = 4500):
    root = tk.Tk()
    root.withdraw()

    # Create borderless top-level popup
    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    toast.attributes("-alpha", 0.96)

    # Toast dimensions
    toast_w = 340
    toast_h = 86

    # Calculate bottom-right coordinates (above Windows taskbar)
    screen_w = toast.winfo_screenwidth()
    screen_h = toast.winfo_screenheight()
    pos_x = screen_w - toast_w - 20
    pos_y = screen_h - toast_h - 55

    toast.geometry(f"{toast_w}x{toast_h}+{pos_x}+{pos_y}")

    # Outer border container with warning accent
    container = tk.Frame(toast, bg="#dc2626", padx=2, pady=2)
    container.pack(fill="both", expand=True)

    # Inner dark body
    body = tk.Frame(container, bg="#18181b", padx=14, pady=10)
    body.pack(fill="both", expand=True)

    # Left Icon column
    icon_lbl = tk.Label(body, text="⚠️", font=("Segoe UI", 20), bg="#18181b", fg="#ef4444")
    icon_lbl.pack(side="left", padx=(0, 12), anchor="center")

    # Content column
    content_frame = tk.Frame(body, bg="#18181b")
    content_frame.pack(side="left", fill="both", expand=True)

    # Top title bar with close button
    title_row = tk.Frame(content_frame, bg="#18181b")
    title_row.pack(fill="x", expand=True)

    title_lbl = tk.Label(
        title_row,
        text=title,
        font=("Segoe UI", 10, "bold"),
        fg="#ffffff",
        bg="#18181b",
        anchor="w",
    )
    title_lbl.pack(side="left", fill="x", expand=True)

    close_btn = tk.Label(
        title_row,
        text="✕",
        font=("Segoe UI", 9),
        fg="#a1a1aa",
        bg="#18181b",
        cursor="hand2",
    )
    close_btn.pack(side="right")
    close_btn.bind("<Button-1>", lambda e: root.destroy())

    msg_lbl = tk.Label(
        content_frame,
        text=message,
        font=("Segoe UI", 9),
        fg="#e4e4e7",
        bg="#18181b",
        wraplength=260,
        justify="left",
        anchor="w",
    )
    msg_lbl.pack(fill="both", expand=True, pady=(2, 0))

    # Click anywhere to dismiss
    for widget in [container, body, icon_lbl, content_frame, title_lbl, msg_lbl]:
        widget.bind("<Button-1>", lambda e: root.destroy())

    # Auto close after duration
    toast.after(duration_ms, root.destroy)

    toast.deiconify()
    toast.lift()
    root.mainloop()


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "Posture Violation Alert"
    m = sys.argv[2] if len(sys.argv) > 2 else "Slouching detected for >10s! Please sit upright."
    d = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 4500
    show_toast(t, m, d)
