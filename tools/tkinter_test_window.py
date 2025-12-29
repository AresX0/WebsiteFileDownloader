import tkinter as tk
import pytest
try:
    root = tk.Tk()
except tk.TclError:
    pytest.skip("Skipping manual Tk window demo - Tcl/Tk not available", allow_module_level=True)
root.title("Tkinter Test Window")
root.geometry("400x200")
label = tk.Label(root, text="If you see this, Tkinter is working!", font=("Arial", 16))
label.pack(pady=40)
root.deiconify()
root.lift()
root.focus_force()
print("[DEBUG] Tkinter test window should be visible now.")
root.mainloop()