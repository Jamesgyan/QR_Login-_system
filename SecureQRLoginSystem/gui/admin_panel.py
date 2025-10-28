# gui/admin_panel.py
import tkinter as tk
from tkinter import ttk, filedialog
from tkcalendar import Calendar, DateEntry
from gui.gui_utils import (show_info, show_error, ask_yes_no, 
                           ask_string, create_treeview, clear_treeview)
from PIL import Image, ImageTk
import os
import csv
from collections import defaultdict
from datetime import datetime
from config.settings import QR_CODE_DIR

class AdminPanel(ttk.Frame):
    def __init__(self, master, db_manager, user_manager, auth_manager):
        super().__init__(master)
        self.db = db_manager
        self.user_manager = user_manager
        self.auth_manager = auth_manager
        
        self.authenticated = False
        self.users_map = {} # For quick lookup
        self.qr_window = None # To manage QR Toplevel
        
        self.create_auth_screen()

    def create_auth_screen(self):
        """Creates the initial password prompt to access the admin panel."""
        self.auth_frame = ttk.Frame(self, padding=20)
        self.auth_frame.pack(expand=True, anchor='center')
        
        ttk.Label(self.auth_frame, text="Admin Authentication Required", 
                  font=("-size", 16, "-weight", "bold")).pack(pady=10)
        
        ttk.Label(self.auth_frame, text="Enter Admin Password:").pack(pady=5)
        
        self.admin_pass_entry = ttk.Entry(self.auth_frame, show='*')
        self.admin_pass_entry.pack(pady=5, padx=10, fill='x')
        
        auth_btn = ttk.Button(self.auth_frame, text="Authenticate", command=self.check_admin_pass)
        auth_btn.pack(pady=10)
        self.admin_pass_entry.bind("<Return>", lambda e: self.check_admin_pass())
        
    def check_admin_pass(self):
        # This is a placeholder as per the prompt.
        # A real system would hash/salt this or check against a user role.
        password = self.admin_pass_entry.get()
        if password == "admin": # Simple hardcoded password
            self.authenticated = True
            self.auth_frame.destroy()
            self.create_admin_widgets()
        else:
            show_error("Auth Failed", "Incorrect password.")

    def create_admin_widgets(self):
        """Creates the main tabbed notebook for admin functions."""
        notebook = ttk.Notebook(self)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Create frames for each tab
        self.user_mgmt_tab = ttk.Frame(notebook)
        self.leave_mgmt_tab = ttk.Frame(notebook)
        self.calendar_tab = ttk.Frame(notebook)
        self.summary_tab = ttk.Frame(notebook)
        
        notebook.add(self.user_mgmt_tab, text="User Management")
        notebook.add(self.leave_mgmt_tab, text="Leave & Attendance")
        notebook.add(self.calendar_tab, text="Company Calendar")
        notebook.add(self.summary_tab, text="Attendance Summary")
        
        # Populate each tab
        self.create_user_management_tab()
        self.create_leave_management_tab()
        self.create_calendar_tab()
        self.create_summary_tab()

    # --- 1. User Management Tab ---

    def create_user_management_tab(self):
        # Main layout
        left_frame = ttk.Frame(self.user_mgmt_tab, width=300)
        left_frame.pack(side='left', fill='y', padx=10, pady=10)
        
        right_frame = ttk.Frame(self.user_mgmt_tab)
        right_frame.pack(side='right', fill='both', expand=True, padx=10, pady=10)

        # --- Left: Add User Form ---
        form_frame = ttk.LabelFrame(left_frame, text="Add New User", padding=10)
        form_frame.pack(fill='x')
        
        ttk.Label(form_frame, text="Full Name:").grid(row=0, column=0, sticky='w', pady=2)
        self.add_name = ttk.Entry(form_frame)
        self.add_name.grid(row=0, column=1, sticky='ew', pady=2, padx=5)
        
        ttk.Label(form_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=2)
        self.add_email = ttk.Entry(form_frame)
        self.add_email.grid(row=1, column=1, sticky='ew', pady=2, padx=5)

        ttk.Label(form_frame, text="Phone (10 digits):").grid(row=2, column=0, sticky='w', pady=2)
        self.add_phone = ttk.Entry(form_frame)
        self.add_phone.grid(row=2, column=1, sticky='ew', pady=2, padx=5)

        ttk.Label(form_frame, text="Password:").grid(row=3, column=0, sticky='w', pady=2)
        self.add_pass = ttk.Entry(form_frame, show='*')
        self.add_pass.grid(row=3, column=1, sticky='ew', pady=2, padx=5)
        
        add_btn = ttk.Button(form_frame, text="Add User", command=self.add_user)
        add_btn.grid(row=4, column=0, columnspan=2, sticky='ew', pady=10)

        # --- Right: User List & Actions ---
        list_frame = ttk.LabelFrame(right_frame, text="All Users", padding=10)
        list_frame.pack(fill='both', expand=True)
        
        cols = ('id', 'emp_id', 'name', 'email', 'phone', 'status')
        headings = ('DB ID', 'Employee ID', 'Name', 'Email', 'Phone', 'Login Status')
        
        # Configure treeview
        self.user_tree = create_treeview(list_frame, cols, headings)
        self.user_tree.column('id', width=50, stretch=False)
        self.user_tree.column('emp_id', width=100, stretch=False)
        self.user_tree.column('name', width=150)
        self.user_tree.column('email', width=200)
        self.user_tree.column('phone', width=100)
        self.user_tree.column('status', width=100, anchor='center')
        
        # Tags for status
        self.user_tree.tag_configure('Logged In', background='#DFF0D8') # Green
        self.user_tree.tag_configure('Logged Out', background='#F2DEDE') # Red
        
        # --- Bottom: Action Buttons ---
        action_frame = ttk.LabelFrame(right_frame, text="User Actions", padding=10)
        action_frame.pack(fill='x', pady=10)
        
        refresh_btn = ttk.Button(action_frame, text="Refresh List", command=self.load_users)
        refresh_btn.pack(side='left', padx=5)

        reset_pass_btn = ttk.Button(action_frame, text="Reset Password", command=self.reset_password)
        reset_pass_btn.pack(side='left', padx=5)

        force_logout_btn = ttk.Button(action_frame, text="Force Logout", command=self.force_logout)
        force_logout_btn.pack(side='left', padx=5)

        view_qr_btn = ttk.Button(action_frame, text="View QR", command=self.view_qr)
        view_qr_btn.pack(side='left', padx=5)

        delete_user_btn = ttk.Button(action_frame, text="Delete User", command=self.delete_user)
        delete_user_btn.pack(side='left', padx=5)

        # Initial data load
        self.load_users()

    def get_selected_user(self):
        """Helper to get the selected user ID and Employee ID from the tree."""
        try:
            selected_item = self.user_tree.focus()
            if not selected_item:
                show_error("No User Selected", "Please select a user from the list first.")
                return None, None
            
            user_data = self.user_tree.item(selected_item)
            user_id = user_data['values'][0] # DB ID
            employee_id = user_data['values'][1] # Emp ID
            return user_id, employee_id
        except Exception:
            show_error("Error", "Could not get selected user.")
            return None, None

    def load_users(self):
        clear_treeview(self.user_tree)
        self.users_map.clear()
        try:
            users = self.user_manager.get_all_users_for_display()
            for user in users:
                values = (user['id'], user['employee_id'], user['name'], user['email'], user['phone'], user['status'])
                tag = user['status'].replace(" ", "") # 'Logged In' -> 'LoggedIn'
                self.user_tree.insert('', 'end', values=values, tags=(tag,))
                self.users_map[user['id']] = user # Store for later
        except Exception as e:
            show_error("Load Error", f"Failed to load users: {e}")
            
    def add_user(self):
        result = self.user_manager.add_user(
            self.add_name.get(),
            self.add_email.get(),
            self.add_phone.get(),
            self.add_pass.get()
        )
        if "successfully" in result:
            show_info("Success", result)
            self.load_users() # Refresh list
            # Clear form
            self.add_name.delete(0, 'end')
            self.add_email.delete(0, 'end')
            self.add_phone.delete(0, 'end')
            self.add_pass.delete(0, 'end')
        else:
            show_error("Error", result)
            
    def reset_password(self):
        user_id, _ = self.get_selected_user()
        if not user_id:
            return
            
        new_pass = ask_string("Reset Password", "Enter new password:")
        if not new_pass:
            return
            
        result = self.user_manager.reset_password(user_id, new_pass)
        show_info("Password Reset", result)

    def force_logout(self):
        user_id, _ = self.get_selected_user()
        if not user_id:
            return
            
        result = self.auth_manager.force_logout(user_id)
        show_info("Force Logout", result)
        self.load_users() # Refresh status

    def view_qr(self):
        user_id, employee_id = self.get_selected_user()
        if not employee_id:
            return
            
        qr_path = os.path.join(QR_CODE_DIR, f"{employee_id}.png")
        
        if not os.path.exists(qr_path):
            show_error("Error", f"QR code file not found for {employee_id}.")
            return

        # Create a new top-level window
        if self.qr_window and self.qr_window.winfo_exists():
            self.qr_window.destroy()
            
        self.qr_window = tk.Toplevel(self)
        self.qr_window.title(f"QR Code: {employee_id}")
        
        img = Image.open(qr_path)
        img = img.resize((300, 300), Image.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        
        qr_label = ttk.Label(self.qr_window, image=img_tk)
        qr_label.image = img_tk # Keep reference
        qr_label.pack(padx=20, pady=20)

    def delete_user(self):
        user_id, employee_id = self.get_selected_user()
        if not user_id:
            return
            
        if not ask_yes_no("Confirm Delete", f"Are you sure you want to delete {employee_id}?\nALL their attendance and login data will be PERMANENTLY deleted."):
            return
            
        result = self.user_manager.delete_user(user_id)
        show_info("Delete User", result)
        self.load_users()


    # --- 2. Leave & Attendance Tab ---

    def create_leave_management_tab(self):
        # Top frame for marking leave
        mark_frame = ttk.LabelFrame(self.leave_mgmt_tab, text="Mark Leave / Status", padding=10)
        mark_frame.pack(fill='x', padx=10, pady=10)
        
        # User selection
        ttk.Label(mark_frame, text="Select User:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.leave_user_combo = ttk.Combobox(mark_frame, state='readonly', width=30)
        self.leave_user_combo.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        # Date range
        ttk.Label(mark_frame, text="Start Date:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.leave_start_date = DateEntry(mark_frame, date_pattern='y-mm-dd', width=12)
        self.leave_start_date.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        
        ttk.Label(mark_frame, text="End Date:").grid(row=1, column=2, padx=5, pady=5, sticky='w')
        self.leave_end_date = DateEntry(mark_frame, date_pattern='y-mm-dd', width=12)
        self.leave_end_date.grid(row=1, column=3, padx=5, pady=5, sticky='w')
        
        # Leave type
        ttk.Label(mark_frame, text="Status/Leave Type:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        leave_types = ['Present', 'Leave', 'Sick Leave', 'Personal Leave', 'Absent', 'Holiday']
        self.leave_type_combo = ttk.Combobox(mark_frame, values=leave_types, state='readonly', width=20)
        self.leave_type_combo.current(1) # Default to 'Leave'
        self.leave_type_combo.grid(row=2, column=1, padx=5, pady=5, sticky='w')

        # Notes
        ttk.Label(mark_frame, text="Notes:").grid(row=3, column=0, padx=5, pady=5, sticky='nw')
        self.leave_notes = tk.Text(mark_frame, height=3, width=40)
        self.leave_notes.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky='ew')

        # Submit button
        mark_btn = ttk.Button(mark_frame, text="Mark Attendance Status", command=self.mark_leave)
        mark_btn.grid(row=4, column=0, columnspan=4, sticky='ew', pady=10)

        # Bottom frame for viewing attendance
        view_frame = ttk.LabelFrame(self.leave_mgmt_tab, text="View Attendance Records", padding=10)
        view_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Filters for view
        filter_frame = ttk.Frame(view_frame)
        filter_frame.pack(fill='x', pady=5)
        
        ttk.Label(filter_frame, text="User:").pack(side='left', padx=5)
        self.att_user_combo = ttk.Combobox(filter_frame, state='readonly', width=30)
        self.att_user_combo.pack(side='left', padx=5)
        
        ttk.Label(filter_frame, text="Start:").pack(side='left', padx=5)
        self.att_start_date = DateEntry(filter_frame, date_pattern='y-mm-dd', width=12)
        self.att_start_date.pack(side='left', padx=5)

        ttk.Label(filter_frame, text="End:").pack(side='left', padx=5)
        self.att_end_date = DateEntry(filter_frame, date_pattern='y-mm-dd', width=12)
        self.att_end_date.pack(side='left', padx=5)
        
        load_btn = ttk.Button(filter_frame, text="Load Records", command=self.load_attendance)
        load_btn.pack(side='left', padx=10)
        
        # Attendance Treeview
        att_cols = ('date', 'emp_id', 'name', 'status', 'login', 'logout', 'hours', 'notes')
        att_headings = ('Date', 'Emp ID', 'Name', 'Status', 'Login', 'Logout', 'Hours', 'Notes')
        self.attendance_tree = create_treeview(view_frame, att_cols, att_headings)
        
        for col in att_cols:
            self.attendance_tree.column(col, width=90)
        
        self.attendance_tree.column('notes', width=150) 
        self.attendance_tree.column('name', width=120)
        
        # Configure tags for status colors
        for status in leave_types:
            tag = status.replace(" ", "")
            style_name = f"{tag}.Treeview"
            # Get color from gui_utils style
            bg_color = ttk.Style().lookup(style_name, 'background')
            if bg_color:
                self.attendance_tree.tag_configure(tag, background=bg_color)
        
        # Populate user dropdowns when tab is entered
        self.leave_mgmt_tab.bind("<Visibility>", self.populate_user_combos)
        
    def populate_user_combos(self, event=None):
        """Loads all users into the comboboxes."""
        try:
            users = self.db.get_all_users()
            user_list = [f"{u['employee_id']} - {u['name']}" for u in users]
            self.user_id_map = {f"{u['employee_id']} - {u['name']}": u['id'] for u in users}
            
            # Add "All Users" to filter
            filter_list = ["All Users"] + user_list
            self.att_user_combo['values'] = filter_list
            self.att_user_combo.current(0)
            
            self.leave_user_combo['values'] = user_list
            if user_list:
                self.leave_user_combo.current(0)
        except Exception as e:
            show_error("Error", f"Could not load users: {e}")

    def mark_leave(self):
        selected_user_str = self.leave_user_combo.get()
        start_date = self.leave_start_date.get()
        end_date = self.leave_end_date.get()
        leave_type = self.leave_type_combo.get()
        notes = self.leave_notes.get("1.0", "end-1c")
        
        if not all([selected_user_str, start_date, end_date, leave_type]):
            show_error("Error", "Please fill all fields.")
            return
            
        user_id = self.user_id_map.get(selected_user_str)
        if not user_id:
            show_error("Error", "Invalid user selected.")
            return
            
        result = self.auth_manager.mark_leave(user_id, start_date, end_date, leave_type, notes)
        show_info("Mark Leave", result)
        self.load_attendance() # Refresh view

    def load_attendance(self):
        clear_treeview(self.attendance_tree)
        
        selected_user_str = self.att_user_combo.get()
        user_id = None
        if selected_user_str != "All Users":
            user_id = self.user_id_map.get(selected_user_str)
        
        start_date = self.att_start_date.get()
        end_date = self.att_end_date.get()
        
        try:
            records = self.db.get_attendance_records(user_id, start_date, end_date)
            for rec in records:
                values = (
                    rec['date'], rec['employee_id'], rec['name'], 
                    rec['status'], rec['login_time'] or 'N/A', 
                    rec['logout_time'] or 'N/A', f"{rec['hours_worked']:.2f}",
                    rec['notes'] or ''
                )
                tag = (rec['status'] or "").replace(" ", "")
                self.attendance_tree.insert('', 'end', values=values, tags=(tag,))
        except Exception as e:
            show_error("Load Error", f"Failed to load attendance: {e}")

    # --- 3. Company Calendar Tab ---

    def create_calendar_tab(self):
        cal_frame = ttk.Frame(self.calendar_tab, padding=10)
        cal_frame.pack(expand=True, fill='both')

        # Left: Calendar View
        cal_view_frame = ttk.Frame(cal_frame)
        cal_view_frame.pack(side='left', fill='both', expand=True, padx=10)
        
        self.calendar = Calendar(cal_view_frame, selectmode='day', 
                                 date_pattern='y-mm-dd',
                                 showweeknumbers=False)
        self.calendar.pack(fill='both', expand=True)
        self.calendar.bind("<<CalendarSelected>>", self.show_events_for_date)
        
        # Display for selected date's events
        self.event_display = tk.Text(cal_view_frame, height=5, width=40, state='disabled')
        self.event_display.pack(fill='x', pady=10)

        # Right: Add Event
        add_event_frame = ttk.LabelFrame(cal_frame, text="Add Event / Holiday", padding=10)
        add_event_frame.pack(side='right', fill='y', padx=10)

        ttk.Label(add_event_frame, text="Date:").pack(anchor='w', pady=2)
        self.event_date = DateEntry(add_event_frame, date_pattern='y-mm-dd', width=15)
        self.event_date.pack(fill='x', pady=2)

        ttk.Label(add_event_frame, text="Title:").pack(anchor='w', pady=5)
        self.event_title = ttk.Entry(add_event_frame, width=30)
        self.event_title.pack(fill='x', pady=2)
        
        ttk.Label(add_event_frame, text="Category:").pack(anchor='w', pady=5)
        event_types = ['Holiday', 'Event', 'Meeting', 'Celebration']
        self.event_category = ttk.Combobox(add_event_frame, values=event_types, state='readonly')
        self.event_category.current(0)
        self.event_category.pack(fill='x', pady=2)
        
        add_event_btn = ttk.Button(add_event_frame, text="Add Event", command=self.add_event)
        add_event_btn.pack(fill='x', pady=20)
        
        # Configure calendar event colors
        self.calendar.tag_config('Holiday', background='#D9EDF7', foreground='black') # Blue
        self.calendar.tag_config('Event', background='#FCF8E3', foreground='black') # Yellow
        self.calendar.tag_config('Meeting', background='#F2DEDE', foreground='black') # Red
        self.calendar.tag_config('Celebration', background='#DFF0D8', foreground='black') # Green
        
        # Load events when tab is visible
        self.calendar_tab.bind("<Visibility>", self.refresh_calendar_events)

    def refresh_calendar_events(self, event=None):
        """Clears and re-loads all events for the current calendar month."""
        self.calendar.calevent_remove('all') # Clear all events
        
        try:
            current_date = self.calendar.get_date()
            year, month, _ = map(int, current_date.split('-'))
            events = self.db.get_events_for_month(year, month)
            
            for ev in events:
                # --- THIS IS THE FIX ---
                # Convert the date string from the DB to a datetime.date object
                event_date_obj = datetime.strptime(ev['date'], '%Y-%m-%d').date()
                
                self.calendar.calevent_create(
                    date=event_date_obj,  # Use the new object here
                    text=ev['title'],
                    tags=[ev['category']]
                )
        except Exception as e:
            show_error("Calendar Error", f"Failed to load events: {e}")
        
        self.show_events_for_date() # Update text display for selected day

    def add_event(self):
        date = self.event_date.get()
        title = self.event_title.get()
        category = self.event_category.get()
        
        if not (date and title and category):
            show_error("Error", "Please fill all event fields.")
            return
            
        try:
            self.db.add_event(date, title, category)
            show_info("Success", f"Event '{title}' added on {date}.")
            self.event_title.delete(0, 'end')
            self.refresh_calendar_events()
        except Exception as e:
            show_error("Error", f"Failed to add event: {e}")

    def show_events_for_date(self, event=None):
        """Shows events for the selected date in the text box."""
        date = self.calendar.get_date()
        events = self.db.get_events_for_date(date)
        
        self.event_display.config(state='normal')
        self.event_display.delete('1.0', 'end')
        
        if not events:
            self.event_display.insert('1.0', f"No events for {date}.")
        else:
            self.event_display.insert('1.0', f"Events for {date}:\n")
            for i, ev in enumerate(events, 1):
                self.event_display.insert('end', f" {i}. [{ev['category']}] {ev['title']}\n")
                
        self.event_display.config(state='disabled')
        
    # --- 4. Attendance Summary Tab ---

    def create_summary_tab(self):
        # Top frame for filters
        filter_frame = ttk.Frame(self.summary_tab, padding=10)
        filter_frame.pack(fill='x')
        
        ttk.Label(filter_frame, text="Select Month:").pack(side='left', padx=5)
        # We need a simple way to select month/year. DateEntry is fine.
        self.summary_date = DateEntry(filter_frame, date_pattern='y-mm-dd', width=12)
        self.summary_date.pack(side='left', padx=5)
        
        gen_btn = ttk.Button(filter_frame, text="Generate Summary", command=self.generate_summary)
        gen_btn.pack(side='left', padx=10)

        # Bottom frame for the report
        report_frame = ttk.LabelFrame(self.summary_tab, text="Summary Report", padding=10)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.summary_text = tk.Text(report_frame, state='disabled', font=("Courier", 10))
        self.summary_text.pack(fill='both', expand=True)

    def generate_summary(self):
        try:
            selected_date_str = self.summary_date.get()
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d')
            year, month = selected_date.year, selected_date.month
            
            import calendar
            _, num_days = calendar.monthrange(year, month)
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{num_days}"
            
            # 1. Get all users
            users = self.db.get_all_users()
            if not users:
                self.update_summary_text("No users found.")
                return

            # 2. Get all attendance records for the month
            records = self.db.get_attendance_records(None, start_date, end_date)
            
            # 3. Get all holidays
            events = self.db.get_events_for_month(year, month)
            holidays = {ev['date'] for ev in events if ev['category'] == 'Holiday'}
            
            # 4. Calculate total working days
            total_work_days = 0
            for day in range(1, num_days + 1):
                date_str = f"{year}-{month:02d}-{day:02d}"
                # Removed "date_obj.weekday() < 5" to count all days
                if date_str not in holidays: 
                    total_work_days += 1
            
            # 5. Process data
            summary_data = defaultdict(lambda: defaultdict(int))
            for rec in records:
                summary_data[rec['user_id']][rec['status']] += 1
            
            # 6. Build report string
            report = f"Attendance Summary for: {selected_date.strftime('%B %Y')}\n"
            report += f"Total Working Days in Month (ex. Holidays): {total_work_days}\n"
            report += "="*70 + "\n\n"
            
            for user in users:
                user_id = user['id']
                stats = summary_data[user_id]
                
                present = stats.get('Present', 0)
                sick = stats.get('Sick Leave', 0)
                leave = stats.get('Leave', 0) + stats.get('Personal Leave', 0)
                absent = stats.get('Absent', 0)
                
                # Auto-mark unmarked days as Absent
                total_marked = present + sick + leave + absent
                unmarked_days = 0 
                
                if total_work_days > total_marked:
                     unmarked_days = total_work_days - total_marked
                     absent += unmarked_days
                     
                total_days = present + sick + leave + absent
                
                if total_work_days > 0:
                    present_pct = (present / total_work_days) * 100
                else:
                    present_pct = 0
                
                report += f"User: {user['name']} ({user['employee_id']})\n"
                report += f"  - Attendance Percentage: {present_pct:.1f}% ({present} / {total_work_days} days)\n"
                report += f"  - Present:       {present}\n"
                report += f"  - Sick Leave:    {sick}\n"
                report += f"  - Other Leave:   {leave}\n"
                report += f"  - Absent:        {absent} (includes {unmarked_days} unmarked work days)\n"
                report += "-"*40 + "\n"

            self.update_summary_text(report)
            
        except Exception as e:
            show_error("Summary Error", f"Failed to generate summary: {e}")

    def update_summary_text(self, text):
        self.summary_text.config(state='normal')
        self.summary_text.delete('1.0', 'end')
        self.summary_text.insert('1.0', text)
        self.summary_text.config(state='disabled')