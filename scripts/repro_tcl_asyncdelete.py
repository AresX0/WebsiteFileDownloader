import threading
import tkinter as tk
from tkinter import messagebox
import time

def background_call():
    time.sleep(0.5)
    try:
        messagebox.showinfo("Background", "This is called from a background thread")
    except Exception as e:
        print("Background exception:", e)

root = tk.Tk()
root.title("Repro TCL AsyncDelete")
threading.Thread(target=background_call, daemon=True).start()
root.after(2000, root.destroy)
root.mainloop()
