# ui/calendar_panel.py

import wx
import wx.grid
import calendar
from datetime import datetime

class CalendarPanel(wx.Panel):
    def __init__(self, parent, attendance_manager):
        wx.Panel.__init__(self, parent)
        
        self.att_m = attendance_manager
        self.today = datetime.now().date()
        self.current_year = self.today.year
        self.current_month = self.today.month
        
        self.events_by_date = {} # Cache for events
        self.day_cells = {} # Map (row, col) to date_str

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # --- Navigation ---
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.prev_btn = wx.Button(self, label="< Prev")
        self.month_year_label = wx.StaticText(self, label="", style=wx.ALIGN_CENTER)
        font = self.month_year_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.month_year_label.SetFont(font)
        self.next_btn = wx.Button(self, label="Next >")
        
        nav_sizer.Add(self.prev_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        nav_sizer.Add(self.month_year_label, 1, wx.ALIGN_CENTER | wx.ALL, 5)
        nav_sizer.Add(self.next_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(nav_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # --- Calendar Grid ---
        self.calendar_grid = wx.grid.Grid(self)
        self.calendar_grid.CreateGrid(6, 7) # 6 weeks, 7 days
        self.calendar_grid.EnableEditing(False)
        self.calendar_grid.SetRowLabelSize(0)
        self.calendar_grid.SetColLabelSize(30)
        
        # Set column labels (days of the week)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            self.calendar_grid.SetColLabelValue(i, day)
            
        self.calendar_grid.AutoSizeColumns()
        for row in range(6):
            self.calendar_grid.SetRowSize(row, 60) # Taller rows
            
        main_sizer.Add(self.calendar_grid, 1, wx.EXPAND | wx.ALL, 5)
        
        # --- Event Management ---
        event_box = wx.StaticBox(self, label="Manage Events")
        event_sizer = wx.StaticBoxSizer(event_box, wx.VERTICAL)
        
        add_event_sizer = wx.FlexGridSizer(2, 4, 5, 5)
        add_event_sizer.AddGrowableCol(1)
        
        add_event_sizer.Add(wx.StaticText(self, label="Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.event_date_picker = wx.adv.DatePickerCtrl(self, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        add_event_sizer.Add(self.event_date_picker, 1, wx.EXPAND)
        
        add_event_sizer.Add(wx.StaticText(self, label="Category:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.event_category_choice = wx.Choice(self, choices=['Holiday', 'Event', 'Meeting', 'Celebration'])
        self.event_category_choice.SetSelection(0)
        add_event_sizer.Add(self.event_category_choice, 1, wx.EXPAND)
        
        add_event_sizer.Add(wx.StaticText(self, label="Title:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.event_title_ctrl = wx.TextCtrl(self)
        add_event_sizer.Add(self.event_title_ctrl, 1, wx.EXPAND)
        
        self.add_event_btn = wx.Button(self, label="Add Event")
        add_event_sizer.Add(self.add_event_btn, 0, wx.EXPAND)
        
        event_sizer.Add(add_event_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        event_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.ALL, 5)
        
        event_sizer.Add(wx.StaticText(self, label="Events for Selected Day:"), 0, wx.LEFT, 5)
        self.event_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.event_list.InsertColumn(0, "Event", width=200)
        self.event_list.InsertColumn(1, "Category", width=100)
        self.event_list.InsertColumn(2, "ID", width=0) # Hidden ID
        event_sizer.Add(self.event_list, 1, wx.EXPAND | wx.ALL, 5)
        
        self.delete_event_btn = wx.Button(self, label="Delete Selected Event")
        event_sizer.Add(self.delete_event_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        
        main_sizer.Add(event_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # --- Bindings ---
        self.prev_btn.Bind(wx.EVT_BUTTON, self.on_prev_month)
        self.next_btn.Bind(wx.EVT_BUTTON, self.on_next_month)
        self.add_event_btn.Bind(wx.EVT_BUTTON, self.on_add_event)
        self.delete_event_btn.Bind(wx.EVT_BUTTON, self.on_delete_event)
        self.calendar_grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.on_day_selected)
        
        self.Bind(wx.EVT_SHOW, self.on_show)
        
        self.SetSizer(main_sizer)

    def on_show(self, event):
        if event.IsShown():
            self.refresh_calendar()
            
    def on_prev_month(self, event):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.refresh_calendar()

    def on_next_month(self, event):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.refresh_calendar()

    def refresh_calendar(self):
        """Redraws the entire calendar grid with days and events."""
        
        # Set month/year label
        self.month_year_label.SetLabel(f"{calendar.month_name[self.current_month]} {self.current_year}")
        
        # Fetch events for this month
        try:
            events = self.att_m.get_events_for_month(self.current_month, self.current_year)
            self.events_by_date = {}
            for e in events:
                if e['date'] not in self.events_by_date:
                    self.events_by_date[e['date']] = []
                self.events_by_date[e['date']].append(e)
        except Exception as e:
            print(f"Error fetching events: {e}")
            
        # Clear grid
        self.calendar_grid.ClearGrid()
        self.day_cells = {}
        
        # Get month calendar
        month_cal = calendar.monthcalendar(self.current_year, self.current_month)
        
        # Define colors
        color_today = wx.Colour(255, 255, 200) # Light Yellow
        color_event = wx.Colour(210, 230, 255) # Light Blue
        color_holiday = wx.Colour(255, 220, 220) # Light Red
        color_other_month = wx.Colour(240, 240, 240) # Light Grey
        
        for row, week in enumerate(month_cal):
            for col, day in enumerate(week):
                self.calendar_grid.SetCellAlignment(row, col, wx.ALIGN_LEFT, wx.ALIGN_TOP)
                self.calendar_grid.SetCellBackgroundColour(row, col, wx.WHITE) # Reset
                
                if day == 0:
                    self.calendar_grid.SetCellValue(row, col, "")
                    self.calendar_grid.SetReadOnly(row, col, True)
                    self.calendar_grid.SetCellBackgroundColour(row, col, color_other_month)
                else:
                    self.calendar_grid.SetCellValue(row, col, str(day))
                    self.calendar_grid.SetReadOnly(row, col, True)
                    
                    date_str = f"{self.current_year:04d}-{self.current_month:02d}-{day:02d}"
                    self.day_cells[(row, col)] = date_str
                    
                    # Highlight today
                    if (day == self.today.day and 
                        self.current_month == self.today.month and 
                        self.current_year == self.today.year):
                        self.calendar_grid.SetCellBackgroundColour(row, col, color_today)
                        
                    # Highlight events
                    if date_str in self.events_by_date:
                        event_list = self.events_by_date[date_str]
                        is_holiday = any(e['category'] == 'Holiday' for e in event_list)
                        
                        if is_holiday:
                            self.calendar_grid.SetCellBackgroundColour(row, col, color_holiday)
                        else:
                            self.calendar_grid.SetCellBackgroundColour(row, col, color_event)
                            
                        # Add markers or event titles
                        event_titles = "\n".join([f"• {e['title']}" for e in event_list[:3]])
                        self.calendar_grid.SetCellValue(row, col, f"{day}\n{event_titles}")

    def on_day_selected(self, event):
        """When a user clicks a day in the grid."""
        row, col = event.GetRow(), event.GetCol()
        date_str = self.day_cells.get((row, col))
        
        if not date_str:
            self.event_list.DeleteAllItems()
            return

        # Set date picker
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        self.event_date_picker.SetValue(dt)
        
        # Populate event list
        self.event_list.DeleteAllItems()
        try:
            events = self.att_m.get_events_for_day(date_str)
            for e in events:
                index = self.event_list.InsertItem(self.event_list.GetItemCount(), e['title'])
                self.event_list.SetItem(index, 1, e['category'])
                self.event_list.SetItem(index, 2, str(e['id'])) # Store hidden ID
        except Exception as e:
            wx.MessageBox(f"Error fetching day events: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_add_event(self, event):
        dt = self.event_date_picker.GetValue()
        date_str = f"{dt.GetYear()}-{dt.GetMonth()+1:02d}-{dt.GetDay():02d}"
        title = self.event_title_ctrl.GetValue()
        category = self.event_category_choice.GetStringSelection()
        
        success, msg = self.att_m.add_event(date_str, title, category)
        
        if success:
            self.event_title_ctrl.Clear()
            self.refresh_calendar() # Redraw calendar with new event
            self.on_day_selected_by_date(date_str) # Re-select day to show new event
        else:
            wx.MessageBox(msg, "Error", wx.OK | wx.ICON_ERROR)
            
    def on_delete_event(self, event):
        sel_idx = self.event_list.GetFirstSelected()
        if sel_idx == -1:
            wx.MessageBox("Please select an event from the list to delete.", "Warning", wx.OK | wx.ICON_WARNING)
            return
            
        event_id = int(self.event_list.GetItemText(sel_idx, 2))
        
        success, msg = self.att_m.delete_event(event_id)
        if success:
            dt = self.event_date_picker.GetValue()
            date_str = f"{dt.GetYear()}-{dt.GetMonth()+1:02d}-{dt.GetDay():02d}"
            self.refresh_calendar()
            self.on_day_selected_by_date(date_str) # Refresh list
        else:
            wx.MessageBox(msg, "Error", wx.OK | wx.ICON_ERROR)
            
    def on_day_selected_by_date(self, date_str):
        """Simulates a click on a day given its date string."""
        for (row, col), ds in self.day_cells.items():
            if ds == date_str:
                # Create a mock event to pass to the handler
                class MockGridEvent:
                    def GetRow(self): return row
                    def GetCol(self): return col
                self.on_day_selected(MockGridEvent())
                return