# ui/history_panel.py

import wx
import wx.adv
import csv
from datetime import datetime

class HistoryPanel(wx.Panel):
    def __init__(self, parent, db_manager, attendance_manager):
        wx.Panel.__init__(self, parent)
        
        self.db = db_manager
        self.att_m = attendance_manager # For CSV export
        self.all_users = [] # Cache for user filter
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # --- Filter Section ---
        filter_box = wx.StaticBox(self, label="Filters")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.HORIZONTAL)
        
        filter_sizer.Add(wx.StaticText(self, label="User:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.user_choice = wx.Choice(self)
        filter_sizer.Add(self.user_choice, 1, wx.EXPAND | wx.RIGHT, 10)
        
        filter_sizer.Add(wx.StaticText(self, label="Start Date:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.start_date_picker = wx.adv.DatePickerCtrl(self, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        filter_sizer.Add(self.start_date_picker, 1, wx.EXPAND | wx.RIGHT, 10)

        filter_sizer.Add(wx.StaticText(self, label="End Date:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.end_date_picker = wx.adv.DatePickerCtrl(self, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        filter_sizer.Add(self.end_date_picker, 1, wx.EXPAND | wx.RIGHT, 10)
        
        self.filter_btn = wx.Button(self, label="Filter")
        self.export_btn = wx.Button(self, label="Export CSV")
        filter_sizer.Add(self.filter_btn, 0, wx.RIGHT, 5)
        filter_sizer.Add(self.export_btn, 0)

        main_sizer.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # --- History List ---
        self.history_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_VRULES)
        self.history_list.InsertColumn(0, "Timestamp", width=160)
        self.history_list.InsertColumn(1, "Name", width=150)
        self.history_list.InsertColumn(2, "Employee ID", width=100)
        self.history_list.InsertColumn(3, "Action", width=80)
        
        main_sizer.Add(self.history_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # --- Bindings ---
        self.filter_btn.Bind(wx.EVT_BUTTON, self.on_filter)
        self.export_btn.Bind(wx.EVT_BUTTON, self.on_export)
        
        # Bind EVT_SHOW to refresh data when tab is clicked
        self.Bind(wx.EVT_SHOW, self.on_show)
        
        self.SetSizer(main_sizer)

    def on_show(self, event):
        """Called when the panel is shown."""
        if event.IsShown():
            self.refresh_user_list()
            self.on_filter(None) # Load initial data
            
    def refresh_user_list(self):
        """Updates the user dropdown filter."""
        self.user_choice.Clear()
        self.user_choice.Append("All Users")
        
        try:
            self.all_users = self.db.get_all_users()
            for user in self.all_users:
                self.user_choice.Append(f"{user['name']} ({user['employee_id']})")
            self.user_choice.SetSelection(0)
        except Exception as e:
            wx.MessageBox(f"Error loading users: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_filter(self, event):
        """Filters the login history list."""
        user_id = None
        sel = self.user_choice.GetSelection()
        if sel > 0:
            user_id = self.all_users[sel - 1]['id']
            
        # Get dates and format as YYYY-MM-DD
        start_dt = self.start_date_picker.GetValue()
        start_date = f"{start_dt.GetYear()}-{start_dt.GetMonth()+1:02d}-{start_dt.GetDay():02d}"
        
        end_dt = self.end_date_picker.GetValue()
        end_date = f"{end_dt.GetYear()}-{end_dt.GetMonth()+1:02d}-{end_dt.GetDay():02d}"

        try:
            records = self.db.get_login_history(user_id, start_date, end_date)
            self.populate_list(records)
        except Exception as e:
            wx.MessageBox(f"Error fetching history: {e}", "Error", wx.OK | wx.ICON_ERROR)
            
    def populate_list(self, records):
        """Fills the ListCtrl with data."""
        self.history_list.DeleteAllItems()
        
        for record in records:
            index = self.history_list.InsertItem(self.history_list.GetItemCount(), record['timestamp'])
            self.history_list.SetItem(index, 1, record['name'])
            self.history_list.SetItem(index, 2, record['employee_id'])
            self.history_list.SetItem(index, 3, record['action'].title())
            
            # Color-code actions
            if record['action'] == 'login':
                self.history_list.SetItemTextColour(index, wx.Colour(0, 150, 0)) # Green
            else:
                self.history_list.SetItemTextColour(index, wx.Colour(200, 0, 0)) # Red
                
    def on_export(self, event):
        """Exports the current list view to CSV."""
        with wx.FileDialog(self, "Save CSV Report", wildcard="CSV files (*.csv)|*.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return # User cancelled
                
            filepath = fileDialog.GetPath()
            try:
                # Get data from list control
                headers = ["Timestamp", "Name", "Employee ID", "Action"]
                data = []
                for i in range(self.history_list.GetItemCount()):
                    row = [
                        self.history_list.GetItemText(i, 0),
                        self.history_list.GetItemText(i, 1),
                        self.history_list.GetItemText(i, 2),
                        self.history_list.GetItemText(i, 3)
                    ]
                    data.append(row)
                
                success, msg = self.att_m.export_to_csv(data, headers, filepath)
                if success:
                    wx.MessageBox(msg, "Export Successful", wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox(msg, "Export Failed", wx.OK | wx.ICON_ERROR)
                    
            except Exception as e:
                wx.MessageBox(f"Error exporting file: {e}", "Error", wx.OK | wx.ICON_ERROR)