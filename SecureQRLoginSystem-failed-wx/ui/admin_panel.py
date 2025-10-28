# ui/admin_panel.py

import wx
import wx.adv
import wx.lib.sized_controls as sc
import calendar  # <-- FIX: Added this import
from datetime import datetime
import validation_utils as vutils
from .calendar_panel import CalendarPanel # Import the calendar

class AdminPanel(wx.Panel):
    def __init__(self, parent, user_m, att_m, db_m, qr_h):
        wx.Panel.__init__(self, parent)
        
        self.user_m = user_m
        self.att_m = att_m
        self.db = db_m
        self.qr_h = qr_h
        
        self.all_users_cache = [] # Cache for dropdowns
        
        # Main sizer for this panel
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create the notebook for Admin sections
        self.notebook = wx.Notebook(self)
        
        # --- 1. User Management Tab ---
        self.user_mgmt_panel = self.create_user_mgmt_panel(self.notebook)
        self.notebook.AddPage(self.user_mgmt_panel, "User Management")
        
        # --- 2. Leave & Attendance Tab ---
        self.leave_mgmt_panel = self.create_leave_mgmt_panel(self.notebook)
        self.notebook.AddPage(self.leave_mgmt_panel, "Leave & Attendance")
        
        main_sizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(main_sizer)
        
        self.Bind(wx.EVT_SHOW, self.on_show)

    def on_show(self, event):
        """When the Admin panel is shown, refresh its data."""
        if event.IsShown():
            self.refresh_all_user_data()

    def refresh_all_user_data(self):
        """Refreshes all user lists across all sub-panels."""
        try:
            self.all_users_cache = self.user_m.get_all_users_with_status()
            
            # Refresh User Management list
            self.populate_user_list()
            
            # Refresh user dropdowns in Leave panels
            self.populate_user_dropdown(self.leave_user_choice)
            # Add "All Users" to the view attendance dropdown
            self.populate_user_dropdown(self.view_att_user_choice, include_all=True) 
            self.populate_user_dropdown(self.summary_user_choice)

        except Exception as e:
            wx.MessageBox(f"Error refreshing user data: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def populate_user_dropdown(self, choice_ctrl, include_all=False):
        """Helper to populate a wx.Choice with users."""
        choice_ctrl.Clear()
        if include_all:
            choice_ctrl.Append("All Users")
            
        for user in self.all_users_cache:
            choice_ctrl.Append(f"{user['name']} ({user['employee_id']})")
        
        if choice_ctrl.GetCount() > 0:
            choice_ctrl.SetSelection(0)

    # --- Panel 1: User Management ---

    def create_user_mgmt_panel(self, parent):
        panel = wx.Panel(parent)
        
        # Splitter window: Forms on left, List on right
        splitter = wx.SplitterWindow(panel)
        left_panel = wx.Panel(splitter)
        right_panel = wx.Panel(splitter)
        
        # --- Left Panel (Forms) ---
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add User form
        add_box = wx.StaticBox(left_panel, label="Add New User")
        add_sizer = wx.StaticBoxSizer(add_box, wx.VERTICAL)
        add_grid = wx.FlexGridSizer(5, 2, 5, 5)
        add_grid.AddGrowableCol(1)
        
        add_grid.Add(wx.StaticText(left_panel, label="Name:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.add_name = wx.TextCtrl(left_panel)
        add_grid.Add(self.add_name, 1, wx.EXPAND)
        
        add_grid.Add(wx.StaticText(left_panel, label="Email:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.add_email = wx.TextCtrl(left_panel)
        add_grid.Add(self.add_email, 1, wx.EXPAND)
        
        add_grid.Add(wx.StaticText(left_panel, label="Phone (10 digits):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.add_phone = wx.TextCtrl(left_panel)
        add_grid.Add(self.add_phone, 1, wx.EXPAND)
        
        add_grid.Add(wx.StaticText(left_panel, label="Password:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.add_pass = wx.TextCtrl(left_panel, style=wx.TE_PASSWORD)
        add_grid.Add(self.add_pass, 1, wx.EXPAND)
        
        add_grid.Add((0,0)) # Spacer
        self.add_user_btn = wx.Button(left_panel, label="Add User")
        add_grid.Add(self.add_user_btn, 1, wx.EXPAND)
        
        add_sizer.Add(add_grid, 1, wx.EXPAND | wx.ALL, 5)
        left_sizer.Add(add_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Manage User form
        manage_box = wx.StaticBox(left_panel, label="Manage Selected User")
        manage_sizer = wx.StaticBoxSizer(manage_box, wx.VERTICAL)
        
        self.manage_user_text = wx.StaticText(left_panel, label="Select a user from the list ->")
        manage_sizer.Add(self.manage_user_text, 0, wx.ALL, 5)
        
        self.reset_pass_btn = wx.Button(left_panel, label="Reset Password")
        self.force_logout_btn = wx.Button(left_panel, label="Force Logout")
        self.view_qr_btn = wx.Button(left_panel, label="View QR Code")
        self.delete_user_btn = wx.Button(left_panel, label="Delete User")
        
        manage_sizer.Add(self.reset_pass_btn, 0, wx.EXPAND | wx.ALL, 5)
        manage_sizer.Add(self.force_logout_btn, 0, wx.EXPAND | wx.ALL, 5)
        manage_sizer.Add(self.view_qr_btn, 0, wx.EXPAND | wx.ALL, 5)
        manage_sizer.Add(self.delete_user_btn, 0, wx.EXPAND | wx.ALL, 5)
        
        self.reset_pass_btn.Disable()
        self.force_logout_btn.Disable()
        self.view_qr_btn.Disable()
        self.delete_user_btn.Disable()

        left_sizer.Add(manage_sizer, 0, wx.EXPAND | wx.ALL, 5)
        left_panel.SetSizer(left_sizer)

        # --- Right Panel (List) ---
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        self.user_list = wx.ListCtrl(right_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES)
        self.user_list.InsertColumn(0, "ID", width=0) # Hidden
        self.user_list.InsertColumn(1, "Employee ID", width=100)
        self.user_list.InsertColumn(2, "Name", width=150)
        self.user_list.InsertColumn(3, "Email", width=200)
        self.user_list.InsertColumn(4, "Phone", width=100)
        self.user_list.InsertColumn(5, "Status", width=100)
        
        right_sizer.Add(self.user_list, 1, wx.EXPAND | wx.ALL, 5)
        right_panel.SetSizer(right_sizer)
        
        # --- Splitter Setup ---
        splitter.SplitVertically(left_panel, right_panel, 300)
        splitter.SetMinimumPaneSize(250)
        
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel_sizer.Add(splitter, 1, wx.EXPAND)
        panel.SetSizer(panel_sizer)
        
        # --- Bindings ---
        self.add_user_btn.Bind(wx.EVT_BUTTON, self.on_add_user)
        self.user_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_user_selected)
        self.reset_pass_btn.Bind(wx.EVT_BUTTON, self.on_reset_password)
        self.force_logout_btn.Bind(wx.EVT_BUTTON, self.on_force_logout)
        self.view_qr_btn.Bind(wx.EVT_BUTTON, self.on_view_qr)
        self.delete_user_btn.Bind(wx.EVT_BUTTON, self.on_delete_user)

        return panel
        
    def populate_user_list(self):
        """Fills the admin user ListCtrl with data from cache."""
        self.user_list.DeleteAllItems()
        for user in self.all_users_cache:
            index = self.user_list.InsertItem(self.user_list.GetItemCount(), str(user['id']))
            self.user_list.SetItem(index, 1, user['employee_id'])
            self.user_list.SetItem(index, 2, user['name'])
            self.user_list.SetItem(index, 3, user['email'])
            self.user_list.SetItem(index, 4, user['phone'])
            
            status = "Logged In" if user['is_logged_in'] else "Logged Out"
            self.user_list.SetItem(index, 5, status)
            if user['is_logged_in']:
                self.user_list.SetItemTextColour(index, wx.Colour(0, 150, 0))
            else:
                self.user_list.SetItemTextColour(index, wx.Colour(200, 0, 0))

    def get_selected_user_id(self):
        """Helper to get the user ID from the selected list item."""
        sel_idx = self.user_list.GetFirstSelected()
        if sel_idx == -1:
            return None, None
        
        user_id = int(self.user_list.GetItemText(sel_idx, 0))
        user_name = self.user_list.GetItemText(sel_idx, 2)
        return user_id, user_name

    def on_user_selected(self, event):
        """Enables manage buttons when a user is selected."""
        user_id, user_name = self.get_selected_user_id()
        if user_id:
            self.manage_user_text.SetLabel(f"Managing: {user_name}")
            self.reset_pass_btn.Enable()
            self.force_logout_btn.Enable()
            self.view_qr_btn.Enable()
            self.delete_user_btn.Enable()
        else:
            self.manage_user_text.SetLabel("Select a user from the list ->")
            self.reset_pass_btn.Disable()
            self.force_logout_btn.Disable()
            self.view_qr_btn.Disable()
            self.delete_user_btn.Disable()

    def on_add_user(self, event):
        name = self.add_name.GetValue()
        email = self.add_email.GetValue()
        phone = self.add_phone.GetValue()
        password = self.add_pass.GetValue()
        
        success, msg = self.user_m.add_user(name, email, phone, password)
        
        if success:
            wx.MessageBox(f"User {msg['employee_id']} added successfully.", "Success", wx.OK | wx.ICON_INFORMATION)
            self.add_name.Clear()
            self.add_email.Clear()
            self.add_phone.Clear()
            self.add_pass.Clear()
            self.refresh_all_user_data() # Refresh lists
        else:
            wx.MessageBox(msg, "Error", wx.OK | wx.ICON_ERROR)

    def on_reset_password(self, event):
        user_id, user_name = self.get_selected_user_id()
        if not user_id: return
        
        dlg = wx.PasswordEntryDialog(self, f"Enter new password for {user_name}:", "Reset Password")
        if dlg.ShowModal() == wx.ID_OK:
            new_pass = dlg.GetValue()
            if not new_pass:
                wx.MessageBox("Password cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
                return
            
            success, msg = self.user_m.reset_password(user_id, new_pass)
            wx.MessageBox(msg, "Status", wx.OK | wx.ICON_INFORMATION)
        dlg.Destroy()
        
    def on_force_logout(self, event):
        user_id, user_name = self.get_selected_user_id()
        if not user_id: return
        
        success, msg = self.user_m.force_logout(user_id)
        wx.MessageBox(msg, "Status", wx.OK | wx.ICON_INFORMATION)
        self.refresh_all_user_data() # Refresh list to show new status
        
    def on_view_qr(self, event):
        sel_idx = self.user_list.GetFirstSelected()
        if sel_idx == -1: return
        
        emp_id = self.user_list.GetItemText(sel_idx, 1)
        name = self.user_list.GetItemText(sel_idx, 2)
        qr_path = self.qr_h.qr_dir / f"{emp_id}.png"
        
        if not qr_path.exists():
            wx.MessageBox("QR Code file not found. It may need to be regenerated.", "Error", wx.OK | wx.ICON_ERROR)
            return
            
        # Show QR code in a simple dialog
        img = wx.Image(str(qr_path), wx.BITMAP_TYPE_PNG)
        bmp = img.ConvertToBitmap()
        dlg = sc.SizedDialog(self, -1, f"QR Code for {name} ({emp_id})")
        panel = dlg.GetSizedParent()
        wx.StaticBitmap(panel, -1, bmp)
        dlg.SetButtonSizer(dlg.CreateStdDialogButtonSizer(wx.OK))
        dlg.ShowModal()
        dlg.Destroy()

    def on_delete_user(self, event):
        user_id, user_name = self.get_selected_user_id()
        if not user_id: return
        
        dlg = wx.MessageDialog(self, f"Are you sure you want to delete {user_name}?\n"
                                     "This will delete ALL their login history and attendance records.",
                               "Confirm Delete", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
        
        if dlg.ShowModal() == wx.ID_YES:
            success, msg = self.user_m.delete_user(user_id)
            wx.MessageBox(msg, "Status", wx.OK | wx.ICON_INFORMATION)
            self.refresh_all_user_data() # Refresh lists
            self.on_user_selected(None) # Disable buttons after deletion
        dlg.Destroy()
        
    # --- Panel 2: Leave & Attendance ---

    def create_leave_mgmt_panel(self, parent):
        """This panel holds the 4-tab notebook for attendance."""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sub_notebook = wx.Notebook(panel)
        
        # Tab 1: Mark Leave
        mark_leave_tab = self.create_mark_leave_tab(sub_notebook)
        sub_notebook.AddPage(mark_leave_tab, "Mark Leave")
        
        # Tab 2: View Attendance
        view_att_tab = self.create_view_attendance_tab(sub_notebook)
        sub_notebook.AddPage(view_att_tab, "View Attendance")
        
        # Tab 3: Company Calendar
        # We re-use the CalendarPanel class
        calendar_tab = CalendarPanel(sub_notebook, self.att_m)
        sub_notebook.AddPage(calendar_tab, "Company Calendar")
        
        # Tab 4: Attendance Summary
        summary_tab = self.create_summary_tab(sub_notebook)
        sub_notebook.AddPage(summary_tab, "Attendance Summary")

        sizer.Add(sub_notebook, 1, wx.EXPAND)
        panel.SetSizer(sizer)
        return panel

    def create_mark_leave_tab(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        box = wx.StaticBox(panel, label="Mark Leave / Absence / Holiday for User(s)")
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        grid = wx.FlexGridSizer(5, 2, 5, 5)
        grid.AddGrowableCol(1)
        
        grid.Add(wx.StaticText(panel, label="User:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.leave_user_choice = wx.Choice(panel)
        grid.Add(self.leave_user_choice, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="Start Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.leave_start_date = wx.adv.DatePickerCtrl(panel, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        grid.Add(self.leave_start_date, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="End Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.leave_end_date = wx.adv.DatePickerCtrl(panel, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        grid.Add(self.leave_end_date, 1, wx.EXPAND)

        grid.Add(wx.StaticText(panel, label="Leave Type:"), 0, wx.ALIGN_CENTER_VERTICAL)
        leave_types = ['Leave', 'Sick Leave', 'Personal Leave', 'Absent', 'Holiday']
        self.leave_type_choice = wx.Choice(panel, choices=leave_types)
        self.leave_type_choice.SetSelection(0)
        grid.Add(self.leave_type_choice, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="Notes:"), 0, wx.ALIGN_TOP)
        self.leave_notes = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        grid.Add(self.leave_notes, 1, wx.EXPAND)
        
        box_sizer.Add(grid, 1, wx.EXPAND | wx.ALL, 5)
        
        self.mark_leave_btn = wx.Button(panel, label="Mark Attendance")
        box_sizer.Add(self.mark_leave_btn, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(box_sizer, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)
        
        self.mark_leave_btn.Bind(wx.EVT_BUTTON, self.on_mark_leave)
        
        return panel

    def on_mark_leave(self, event):
        sel_idx = self.leave_user_choice.GetSelection()
        if sel_idx == -1:
            wx.MessageBox("Please select a user.", "Error", wx.OK | wx.ICON_ERROR)
            return
            
        user_id = self.all_users_cache[sel_idx]['id']
        
        start_dt = self.leave_start_date.GetValue()
        start_date = f"{start_dt.GetYear()}-{start_dt.GetMonth()+1:02d}-{start_dt.GetDay():02d}"
        
        end_dt = self.leave_end_date.GetValue()
        end_date = f"{end_dt.GetYear()}-{end_dt.GetMonth()+1:02d}-{end_dt.GetDay():02d}"

        leave_type = self.leave_type_choice.GetStringSelection()
        notes = self.leave_notes.GetValue()
        
        success, msg = self.att_m.mark_leave(user_id, start_date, end_date, leave_type, notes)
        
        if success:
            wx.MessageBox(msg, "Success", wx.OK | wx.ICON_INFORMATION)
            self.leave_notes.Clear()
        else:
            wx.MessageBox(msg, "Error", wx.OK | wx.ICON_ERROR)

    def create_view_attendance_tab(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Filters
        filter_box = wx.StaticBox(panel, label="Filters")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.HORIZONTAL)
        
        filter_sizer.Add(wx.StaticText(panel, label="User:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.view_att_user_choice = wx.Choice(panel)
        filter_sizer.Add(self.view_att_user_choice, 1, wx.EXPAND | wx.RIGHT, 10)
        
        filter_sizer.Add(wx.StaticText(panel, label="Start Date:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.view_att_start_date = wx.adv.DatePickerCtrl(panel, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        filter_sizer.Add(self.view_att_start_date, 1, wx.EXPAND | wx.RIGHT, 10)

        filter_sizer.Add(wx.StaticText(panel, label="End Date:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.view_att_end_date = wx.adv.DatePickerCtrl(panel, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        filter_sizer.Add(self.view_att_end_date, 1, wx.EXPAND | wx.RIGHT, 10)
        
        self.view_att_filter_btn = wx.Button(panel, label="Filter")
        self.view_att_export_btn = wx.Button(panel, label="Export CSV")
        filter_sizer.Add(self.view_att_filter_btn, 0, wx.RIGHT, 5)
        filter_sizer.Add(self.view_att_export_btn, 0)
        sizer.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # List
        self.att_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_VRULES)
        self.att_list.InsertColumn(0, "Name", width=150)
        self.att_list.InsertColumn(1, "Date", width=100)
        self.att_list.InsertColumn(2, "Status", width=100)
        self.att_list.InsertColumn(3, "Login", width=80)
        self.att_list.InsertColumn(4, "Logout", width=80)
        self.att_list.InsertColumn(5, "Hours", width=60)
        self.att_list.InsertColumn(6, "Notes", width=200)
        sizer.Add(self.att_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        panel.SetSizer(sizer)
        
        self.view_att_filter_btn.Bind(wx.EVT_BUTTON, self.on_filter_attendance)
        self.view_att_export_btn.Bind(wx.EVT_BUTTON, self.on_export_attendance)
        
        # Note: "All Users" is now added in refresh_all_user_data
        
        return panel

    def on_filter_attendance(self, event):
        user_id = None
        sel = self.view_att_user_choice.GetSelection()
        if sel > 0: # 0 is "All Users"
            user_id = self.all_users_cache[sel - 1]['id']
            
        start_dt = self.view_att_start_date.GetValue()
        start_date = f"{start_dt.GetYear()}-{start_dt.GetMonth()+1:02d}-{start_dt.GetDay():02d}"
        
        end_dt = self.view_att_end_date.GetValue()
        end_date = f"{end_dt.GetYear()}-{end_dt.GetMonth()+1:02d}-{end_dt.GetDay():02d}"

        try:
            records = self.att_m.get_attendance_records(user_id, start_date, end_date)
            self.populate_attendance_list(records)
        except Exception as e:
            wx.MessageBox(f"Error fetching attendance: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def populate_attendance_list(self, records):
        self.att_list.DeleteAllItems()
        
        status_colors = {
            "Present": wx.Colour(0, 150, 0),
            "Leave": wx.Colour(255, 100, 0),
            "Sick Leave": wx.Colour(255, 0, 255),
            "Personal Leave": wx.Colour(0, 100, 255),
            "Absent": wx.Colour(200, 0, 0),
            "Holiday": wx.Colour(0, 150, 150)
        }
        
        for r in records:
            index = self.att_list.InsertItem(self.att_list.GetItemCount(), r['name'])
            self.att_list.SetItem(index, 1, r['date'])
            self.att_list.SetItem(index, 2, r['status'])
            self.att_list.SetItem(index, 3, r['login_time'] or "---")
            self.att_list.SetItem(index, 4, r['logout_time'] or "---")
            self.att_list.SetItem(index, 5, str(r['hours_worked']) if r['hours_worked'] > 0 else "---")
            self.att_list.SetItem(index, 6, r['notes'] or "")
            
            if r['status'] in status_colors:
                self.att_list.SetItemTextColour(index, status_colors[r['status']])

    def on_export_attendance(self, event):
        with wx.FileDialog(self, "Save Attendance Report", wildcard="CSV files (*.csv)|*.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            filepath = fileDialog.GetPath()
            
            try:
                headers = ["Name", "Date", "Status", "Login", "Logout", "Hours", "Notes"]
                data = []
                for i in range(self.att_list.GetItemCount()):
                    row = [self.att_list.GetItemText(i, j) for j in range(7)]
                    data.append(row)
                
                success, msg = self.att_m.export_to_csv(data, headers, filepath)
                if success:
                    wx.MessageBox(msg, "Export Successful", wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox(msg, "Export Failed", wx.OK | wx.ICON_ERROR)
            except Exception as e:
                wx.MessageBox(f"Error exporting file: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def create_summary_tab(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        box = wx.StaticBox(panel, label="Generate Monthly Summary")
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        filter_sizer = wx.FlexGridSizer(1, 6, 5, 5) # Changed to 6 columns
        filter_sizer.AddGrowableCol(1) # Grow the user choice column
        
        filter_sizer.Add(wx.StaticText(panel, label="User:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.summary_user_choice = wx.Choice(panel)
        filter_sizer.Add(self.summary_user_choice, 1, wx.EXPAND)
        
        filter_sizer.Add(wx.StaticText(panel, label="Month:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
        months = [calendar.month_name[i] for i in range(1, 13)]
        self.summary_month_choice = wx.Choice(panel, choices=months)
        self.summary_month_choice.SetSelection(datetime.now().month - 1)
        filter_sizer.Add(self.summary_month_choice, 0, wx.EXPAND) # No grow
        
        filter_sizer.Add(wx.StaticText(panel, label="Year:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
        current_year = datetime.now().year
        years = [str(y) for y in range(current_year - 5, current_year + 2)]
        self.summary_year_ctrl = wx.ComboBox(panel, value=str(current_year), choices=years, style=wx.CB_READONLY)
        filter_sizer.Add(self.summary_year_ctrl, 0, wx.EXPAND) # No grow
        
        box_sizer.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        self.generate_summary_btn = wx.Button(panel, label="Generate Summary")
        box_sizer.Add(self.generate_summary_btn, 0, wx.EXPAND | wx.ALL, 5)
        
        self.summary_report_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_MONOSPACED)
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.summary_report_text.SetFont(font)
        box_sizer.Add(self.summary_report_text, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(box_sizer, 1, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)
        
        self.generate_summary_btn.Bind(wx.EVT_BUTTON, self.on_generate_summary)
        
        return panel

    def on_generate_summary(self, event):
        sel_idx = self.summary_user_choice.GetSelection()
        if sel_idx == -1:
            wx.MessageBox("Please select a user.", "Error", wx.OK | wx.ICON_ERROR)
            return
            
        user_id = self.all_users_cache[sel_idx]['id']
        month = self.summary_month_choice.GetSelection() + 1
        year = int(self.summary_year_ctrl.GetValue())
        
        success, report = self.att_m.get_attendance_summary(user_id, month, year)
        
        if success:
            self.summary_report_text.SetValue(report)
        else:
            self.summary_report_text.SetValue(f"Failed to generate report:\n{report}")