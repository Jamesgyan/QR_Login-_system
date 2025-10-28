# Color scheme and styling constants
COLORS = {
    'primary': '#2c3e50',
    'secondary': '#34495e',
    'accent': '#3498db',
    'success': '#27ae60',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'light': '#ecf0f1',
    'dark': '#2c3e50'
}

FONTS = {
    'title': ('Arial', 24, 'bold'),
    'heading': ('Arial', 16, 'bold'),
    'subheading': ('Arial', 12, 'bold'),
    'normal': ('Arial', 10),
    'small': ('Arial', 9)
}

STYLES = {
    'button_primary': {'bg': COLORS['accent'], 'fg': 'white'},
    'button_success': {'bg': COLORS['success'], 'fg': 'white'},
    'button_danger': {'bg': COLORS['danger'], 'fg': 'white'},
    'button_warning': {'bg': COLORS['warning'], 'fg': 'white'},
    'frame_dark': {'bg': COLORS['secondary']},
    'frame_light': {'bg': COLORS['light']}
}