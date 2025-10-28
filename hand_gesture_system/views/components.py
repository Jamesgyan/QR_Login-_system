import tkinter as tk
from tkinter import ttk, scrolledtext

class StyledButton(tk.Button):
    def __init__(self, parent, **kwargs):
        bg = kwargs.pop('bg', '#3498db')
        fg = kwargs.pop('fg', 'white')
        font = kwargs.pop('font', ('Arial', 10))
        cursor = kwargs.pop('cursor', 'hand2')
        relief = kwargs.pop('relief', tk.FLAT)
        
        super().__init__(parent, bg=bg, fg=fg, font=font, cursor=cursor, relief=relief, **kwargs)

class LogText(scrolledtext.ScrolledText):
    def __init__(self, parent, **kwargs):
        bg = kwargs.pop('bg', '#2c3e50')
        fg = kwargs.pop('fg', '#ecf0f1')
        font = kwargs.pop('font', ('Courier', 9))
        state = kwargs.pop('state', tk.DISABLED)
        
        super().__init__(parent, bg=bg, fg=fg, font=font, state=state, **kwargs)
    
    def add_message(self, message):
        self.config(state=tk.NORMAL)
        self.insert(tk.END, message + '\n')
        self.see(tk.END)
        self.config(state=tk.DISABLED)
    
    def clear(self):
        self.config(state=tk.NORMAL)
        self.delete(1.0, tk.END)
        self.config(state=tk.DISABLED)

class UserTreeview(ttk.Treeview):
    def __init__(self, parent, **kwargs):
        columns = kwargs.pop('columns', ('Name', 'Status'))
        show = kwargs.pop('show', 'headings')
        
        super().__init__(parent, columns=columns, show=show, **kwargs)
        
        self.heading('Name', text='Name')
        self.heading('Status', text='Status')
        
        self.column('Name', width=150)
        self.column('Status', width=100)
    
    def update_users(self, users, logged_in_users):
        self.delete(*self.get_children())
        for user in users:
            emp_id = user["emp_id"]
            name = user.get("name", "N/A")
            status = "🟢 Online" if emp_id in logged_in_users else "⚫ Offline"
            self.insert("", tk.END, values=(f"{name} ({emp_id})", status))