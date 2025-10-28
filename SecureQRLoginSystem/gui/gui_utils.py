# gui/gui_utils.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

def show_info(title, message):
    messagebox.showinfo(title, message)

def show_error(title, message):
    messagebox.showerror(title, message)
    
def ask_yes_no(title, message):
    return messagebox.askyesno(title, message)

def ask_string(title, prompt):
    return simpledialog.askstring(title, prompt)

def create_treeview(parent, columns, column_headings):
    """Creates a standard styled Treeview."""
    tree = ttk.Treeview(parent, columns=columns, show='headings')
    
    for col, heading in zip(columns, column_headings):
        tree.heading(col, text=heading)
        tree.column(col, width=100, anchor='w')
        
    # Add scrollbar
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    
    tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
    scrollbar.pack(side='right', fill='y')
    
    return tree

def clear_treeview(tree):
    for item in tree.get_children():
        tree.delete(item)

def setup_style():
    """Defines color tags for Treeviews."""
    style = ttk.Style()
    style.map("Treeview", background=[('selected', '#0078D7')])
    
    # Login/Logout colors
    style.configure("login.Treeview", background="#DFF0D8")
    style.configure("logout.Treeview", background="#F2DEDE")
    
    # Leave status colors
    style.configure("Present.Treeview", background="#DFF0D8") # Green
    style.configure("Leave.Treeview", background="#FCF8E3") # Yellow
    style.configure("Sick Leave.Treeview", background="#F2DEDE") # Red
    style.configure("Absent.Treeview", background="#EBCCD1") # Dark Red
    style.configure("Holiday.Treeview", background="#D9EDF7") # Blue