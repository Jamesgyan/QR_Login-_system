# gui/history_panel.py
import tkinter as tk
from tkinter import ttk, filedialog
from tkcalendar import DateEntry
# This import is corrected to include show_info
from gui.gui_utils import create_treeview, clear_treeview, show_error, show_info
import csv

class HistoryPanel(ttk.Frame):
    def __init__(self, master, db_manager):
        super().__init__(master)
        self.db = db_manager
        self.user_id_map = {}
        
        self.create_widgets()
        self.populate_user_combo()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(expand=True, fill='both')

        # --- Top: Filters ---
        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=5)
        
        ttk.Label(filter_frame, text="User:").pack(side='left', padx=5)
        self.user_combo = ttk.Combobox(filter_frame, state='readonly', width=30)
        self.user_combo.pack(side='left', padx=5)
        
        ttk.Label(filter_frame, text="Start Date:").pack(side='left', padx=5)
        self.start_date = DateEntry(filter_frame, date_pattern='y-mm-dd', width=12)
        self.start_date.pack(side='left', padx=5)

        ttk.Label(filter_frame, text="End Date:").pack(side='left', padx=5)
        self.end_date = DateEntry(filter_frame, date_pattern='y-mm-dd', width=12)
        self.end_date.pack(side='left', padx=5)
        
        load_btn = ttk.Button(filter_frame, text="Load History", command=self.load_history)
        load_btn.pack(side='left', padx=10)
        
        export_btn = ttk.Button(filter_frame, text="Export to CSV", command=self.export_to_csv)
        export_btn.pack(side='left', padx=10)

        # --- Bottom: History List ---
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=10)
        
        cols = ('timestamp', 'emp_id', 'name', 'action')
        headings = ('Timestamp', 'Employee ID', 'Name', 'Action')
        self.history_tree = create_treeview(list_frame, cols, headings)
        
        self.history_tree.column('timestamp', width=180)
        self.history_tree.column('emp_id', width=120)
        self.history_tree.column('name', width=150)
        self.history_tree.column('action', width=100, anchor='center')
        
        # Tags for status
        self.history_tree.tag_configure('login', background='#DFF0D8') # Green
        self.history_tree.tag_configure('logout', background='#F2DEDE') # Red
        self.history_tree.tag_configure('force_logout', background='#EBCCD1') # Dark Red

    def populate_user_combo(self, event=None):
        """Loads all users into the combobox."""
        try:
            users = self.db.get_all_users()
            user_list = [f"{u['employee_id']} - {u['name']}" for u in users]
            self.user_id_map = {f"{u['employee_id']} - {u['name']}": u['id'] for u in users}
            
            filter_list = ["All Users"] + user_list
            self.user_combo['values'] = filter_list
            self.user_combo.current(0)
        except Exception as e:
            show_error("Error", f"Could not load users: {e}")

    def load_history(self):
        clear_treeview(self.history_tree)
        
        selected_user_str = self.user_combo.get()
        user_id = None
        if selected_user_str != "All Users":
            user_id = self.user_id_map.get(selected_user_str)
        
        start_date = self.start_date.get()
        end_date = self.end_date.get()
        
        try:
            records = self.db.get_login_history(user_id, start_date, end_date)
            for rec in records:
                values = (
                    rec['timestamp'], rec['employee_id'], rec['name'], rec['action']
                )
                tag = rec['action'].lower()
                self.history_tree.insert('', 'end', values=values, tags=(tag,))
        except Exception as e:
            show_error("Load Error", f"Failed to load history: {e}")

    def export_to_csv(self):
        """Exports the current data in the treeview to a CSV file."""
        if not self.history_tree.get_children():
            show_error("Export Error", "No data to export.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Login History As..."
        )
        
        if not filepath:
            return # User cancelled
            
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                headings = ['Timestamp', 'Employee ID', 'Name', 'Action']
                writer.writerow(headings)
                
                # Write data rows
                for item_id in self.history_tree.get_children():
                    row = self.history_tree.item(item_id)['values']
                    writer.writerow(row)
            
            # This line will now work correctly
            show_info("Export Success", f"History exported successfully to:\n{filepath}")
            
        except Exception as e:
            show_error("Export Error", f"Failed to export data: {e}")