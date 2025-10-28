# logic/attendance_manager.py

from datetime import datetime, timedelta
import calendar
import logging
import csv
import validation_utils as vutils  # <-- FIX: Added this import

logger = logging.getLogger(__name__)

class AttendanceManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def mark_leave(self, user_id, start_date_str, end_date_str, leave_type, notes):
        """Marks leave for a user over a date range."""
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            if start_date > end_date:
                return False, "Start date must be before end date."
            
            current_date = start_date
            while current_date <= end_date:
                # We only mark leave on weekdays (Mon=0, Sun=6)
                if current_date.weekday() < 5: 
                    self.db.upsert_attendance(
                        user_id, 
                        current_date.strftime('%Y-%m-%d'),
                        leave_type,
                        notes
                    )
                current_date += timedelta(days=1)
                
            return True, "Leave marked successfully."
        except Exception as e:
            logger.error(f"Error marking leave: {e}")
            return False, f"An error occurred: {e}"
            
    def get_attendance_records(self, user_id=None, start_date=None, end_date=None):
        """Fetches filterable attendance records."""
        return self.db.get_attendance(user_id, start_date, end_date)
        
    def get_attendance_summary(self, user_id, month, year):
        """Generates a summary report for a user for a given month."""
        try:
            # Get event days (holidays)
            events = self.db.get_events_for_month(month, year)
            holidays = {
                e['date'] for e in events if e['category'] == 'Holiday'
            }

            # Get user's attendance
            records = self.db.get_attendance_for_month(user_id, month, year)
            attendance_map = {r['date']: r['status'] for r in records}

            num_days_in_month = calendar.monthrange(year, month)[1]
            
            counts = {
                'Present': 0, 'Leave': 0, 'Sick Leave': 0, 
                'Personal Leave': 0, 'Absent': 0, 'Holiday': 0,
                'Weekend': 0, 'Unmarked': 0
            }
            
            total_work_days = 0
            
            for day in range(1, num_days_in_month + 1):
                date_obj = datetime(year, month, day).date()
                date_str = date_obj.strftime('%Y-%m-%d')
                
                is_weekend = date_obj.weekday() >= 5 # 5=Sat, 6=Sun
                
                if is_weekend:
                    counts['Weekend'] += 1
                elif date_str in holidays:
                    counts['Holiday'] += 1
                else:
                    # It's a "work day"
                    total_work_days += 1
                    status = attendance_map.get(date_str)
                    
                    if status in counts:
                        counts[status] += 1
                    elif status is None:
                        # Auto-mark past/present dates as Absent if unmarked
                        if date_obj <= datetime.now().date():
                            counts['Absent'] += 1
                            # Optionally auto-mark in DB:
                            # self.db.upsert_attendance(user_id, date_str, 'Absent', 'Auto-marked')
                        else:
                            counts['Unmarked'] += 1 # Future date
                    
            # Calculate percentages
            summary = f"Attendance Summary for {calendar.month_name[month]} {year}\n"
            summary += f"Total Work Days (excl. weekends/holidays): {total_work_days}\n"
            summary += "----------------------------------------------\n"
            
            for status, count in counts.items():
                if status in ['Weekend', 'Unmarked']: continue # Don't include these in %
                
                percentage = (count / total_work_days * 100) if total_work_days > 0 else 0
                summary += f"{status}: {count} days ({percentage:.1f}%)\n"
            
            present_perc = (counts['Present'] / total_work_days * 100) if total_work_days > 0 else 0
            summary += "----------------------------------------------\n"
            summary += f"Overall Attendance: {present_perc:.1f}%\n"
            
            return True, summary

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return False, f"Error: {e}"

    def export_to_csv(self, data, headers, filepath):
        """Utility to export data to a CSV file."""
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data)
            return True, f"Data exported successfully to {filepath}"
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            return False, f"Error exporting file: {e}"

    # --- Event Management ---
    
    def add_event(self, date_str, title, category):
        if not (date_str and title and category):
            return False, "All fields are required."
        if not vutils.validate_date_format(date_str):
            return False, "Invalid date format."
            
        try:
            self.db.add_event(date_str, title, category)
            return True, "Event added successfully."
        except Exception as e:
            logger.error(f"Error adding event: {e}")
            return False, f"Error: {e}"

    def get_events_for_month(self, month, year):
        return self.db.get_events_for_month(month, year)
        
    def get_events_for_day(self, date_str):
        return self.db.get_events_for_day(date_str)

    def delete_event(self, event_id):
        try:
            self.db.delete_event(event_id)
            return True, "Event deleted."
        except Exception as e:
            logger.error(f"Error deleting event {event_id}: {e}")
            return False, f"Error: {e}"