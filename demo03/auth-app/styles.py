# styles.py
import tkinter as tk
from tkinter import ttk

def configure_styles():
    style = ttk.Style()
    
    # Configure theme
    style.theme_use('clam')
    
    # Custom styles
    style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
    style.configure('Subtitle.TLabel', font=('Arial', 12, 'bold'))
    style.configure('Success.TLabel', foreground='#27ae60')
    style.configure('Warning.TLabel', foreground='#f39c12')
    style.configure('Error.TLabel', foreground='#e74c3c')
    
    style.configure('Accent.TButton', foreground='white', background='#3498db')
    style.configure('Success.TButton', foreground='white', background='#27ae60')
    style.configure('Danger.TButton', foreground='white', background='#e74c3c')
    
    return style