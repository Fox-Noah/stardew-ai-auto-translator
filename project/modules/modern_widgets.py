import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
from typing import Dict, Any

class StyleManager:
    
    def __init__(self):
        self.styles = {
            "colors": {
                "bg": "#faf8f0",
                "fg": "#654321",
                "select_bg": "#0078d4",
                "select_fg": "#ffffff",
                "button_bg": "#e1e1e1",
                "button_fg": "#000000",
                "button_active_bg": "#d1d1d1",
                "entry_bg": "#ffffff",
                "entry_fg": "#000000",
                "frame_bg": "#faf8f0",
                "label_fg": "#654321",
                "text_bg": "#faf8f0",
                "text_fg": "#654321",
                "listbox_bg": "#faf8f0",
                "listbox_fg": "#654321",
                "listbox_select_bg": "#f4f1e8",
                "listbox_select_fg": "#654321",
                "listbox_highlight_color": "#8b4513",
                "listbox_highlight_bg": "#c8b99c",
                "translation_listbox_select_bg": "#e8f5e8",
                "translation_listbox_select_fg": "#228b22",
                "scrollbar_bg": "#e1e1e1",
                "scrollbar_trough": "#f8f9fa",
                "scrollbar_active": "#c1c1c1",
                "scrollbar_pressed": "#a1a1a1",
                "scrollbar_arrow": "#6c757d",
                "scrollbar_arrow_active": "#495057"
            },
            "fonts": {
                "default": ("Microsoft YaHei UI", 9),
                "title": ("Microsoft YaHei UI", 16, "bold"),
                "button": ("Microsoft YaHei UI", 9),
                "label": ("Microsoft YaHei UI", 9)
            }
        }
    
    def get_color(self, color_key: str) -> str:
        return self.styles['colors'].get(color_key, '#000000')
    
    def get_font(self, font_key: str) -> tuple:
        return self.styles['fonts'].get(font_key, ('Microsoft YaHei UI', 9))
    
    def apply_theme_to_root(self, root) -> None:
        try:
            style = ttk.Style()
            
            bg_color = self.get_color('bg')
            fg_color = self.get_color('fg')
            select_bg = self.get_color('select_bg')
            select_fg = self.get_color('select_fg')
            button_bg = self.get_color('button_bg')
            button_fg = self.get_color('button_fg')
            button_active_bg = self.get_color('button_active_bg')
            entry_bg = self.get_color('entry_bg')
            entry_fg = self.get_color('entry_fg')
            
            root.configure(bg=bg_color)
            
            style.theme_use('clam')
            
            style.configure('TFrame')
            style.configure('TLabelFrame', foreground=fg_color)
            style.configure('TLabelFrame.Label', foreground=fg_color)
            
            style.configure('TLabel', foreground=fg_color)
            
            style.configure('TButton', 
                          background=button_bg, 
                          foreground=button_fg,
                          borderwidth=1,
                          focuscolor='none')
            style.map('TButton',
                     background=[('active', button_active_bg),
                               ('pressed', button_active_bg)],
                     foreground=[('active', button_fg),
                               ('pressed', button_fg)])
            
            style.configure('TCombobox',
                          fieldbackground=entry_bg,
                          background=button_bg,
                          foreground=entry_fg,
                          borderwidth=1)
            style.map('TCombobox', 
                     fieldbackground=[('readonly', entry_bg)], 
                     selectbackground=[('readonly', select_bg)], 
                     selectforeground=[('readonly', select_fg)], 
                     foreground=[('readonly', entry_fg), 
                               ('!focus', entry_fg), 
                               ('focus', entry_fg)])
            
            style.configure('TEntry',
                          fieldbackground=entry_bg,
                          foreground=entry_fg,
                          borderwidth=1)
            
            style.configure('TProgressbar',
                          background=select_bg,
                          troughcolor=bg_color,
                          borderwidth=1)
            
            scrollbar_bg = self.get_color('scrollbar_bg')
            scrollbar_trough = self.get_color('scrollbar_trough')
            scrollbar_active = self.get_color('scrollbar_active')
            scrollbar_pressed = self.get_color('scrollbar_pressed')
            scrollbar_arrow = self.get_color('scrollbar_arrow')
            scrollbar_arrow_active = self.get_color('scrollbar_arrow_active')
            
            style.configure('TScrollbar',
                          background=scrollbar_bg,
                          troughcolor=scrollbar_trough,
                          borderwidth=0,
                          arrowcolor=scrollbar_arrow,
                          relief='flat',
                          width=10,
                          gripcount=0)
            style.map('TScrollbar',
                     background=[('active', scrollbar_active),
                               ('pressed', scrollbar_pressed)],
                     arrowcolor=[('active', scrollbar_arrow_active),
                               ('pressed', '#212529')],
                     troughcolor=[('active', '#f1f3f4')])
            
            style.configure('Vertical.TScrollbar',
                          background=scrollbar_bg,
                          troughcolor=scrollbar_trough,
                          borderwidth=0,
                          arrowcolor=scrollbar_arrow,
                          relief='flat',
                          width=10,
                          gripcount=0)
            style.map('Vertical.TScrollbar',
                     background=[('active', scrollbar_active),
                               ('pressed', scrollbar_pressed)],
                     arrowcolor=[('active', scrollbar_arrow_active),
                               ('pressed', '#212529')])
            
            style.configure('Horizontal.TScrollbar',
                          background=scrollbar_bg,
                          troughcolor=scrollbar_trough,
                          borderwidth=0,
                          arrowcolor=scrollbar_arrow,
                          relief='flat',
                          width=10,
                          gripcount=0)
            style.map('Horizontal.TScrollbar',
                     background=[('active', scrollbar_active),
                               ('pressed', scrollbar_pressed)],
                     arrowcolor=[('active', scrollbar_arrow_active),
                               ('pressed', '#212529')])
            
            self._apply_modern_widget_styles(root)
            
            self._apply_text_theme(root)
            
        except Exception as e:
            print(f"应用主题失败: {e}")
    
    def _apply_modern_widget_styles(self, root) -> None:
        try:
            def apply_to_children(widget):
                for child in widget.winfo_children():
                    try:
                        if hasattr(child, '__class__') and 'Modern' in child.__class__.__name__:
                            continue
                            
                        if isinstance(child, tk.Button):
                            child.configure(
                                bg=self.get_color('button_bg'),
                                fg=self.get_color('button_fg'),
                                relief='flat',
                                bd=1
                            )
                        elif isinstance(child, tk.Label):
                            child.configure(
                                fg=self.get_color('label_fg')
                            )
                        elif isinstance(child, tk.Frame):
                            child.configure(bg=self.get_color('frame_bg'))
                            
                        apply_to_children(child)
                    except Exception:
                        continue
            
            apply_to_children(root)
            
        except Exception as e:
            print(f"应用现代化组件样式失败: {e}")
    
    def _apply_text_theme(self, root) -> None:
        try:
            def apply_to_text_widgets(widget):
                for child in widget.winfo_children():
                    try:
                        if isinstance(child, tk.Text):
                            child.configure(
                                bg=self.get_color('text_bg'),
                                fg=self.get_color('text_fg'),
                                selectbackground=self.get_color('select_bg'),
                                selectforeground=self.get_color('select_fg'),
                                font=self.get_font('default')
                            )
                        apply_to_text_widgets(child)
                    except Exception:
                        continue
            
            apply_to_text_widgets(root)
            
        except Exception as e:
            print(f"应用Text组件主题失败: {e}")
    
    def apply_listbox_theme(self, listbox):
        try:
            if listbox:
                listbox.configure(
                    bg=self.get_color('entry_bg'),
                    fg=self.get_color('entry_fg'),
                    selectbackground=self.get_color('select_bg'),
                    selectforeground=self.get_color('select_fg'),
                    font=self.get_font('default')
                )
        except Exception as e:
            print(f"应用Listbox主题失败: {e}")
    
    def update_widget_styles(self, parent) -> None:
        try:
            bg_color = self.get_color('bg')
            fg_color = self.get_color('fg')
            select_bg = self.get_color('select_bg')
            select_fg = self.get_color('select_fg')
            entry_bg = self.get_color('entry_bg')
            entry_fg = self.get_color('entry_fg')
            
            for widget_name in ['original_listbox', 'translation_listbox']:
                if hasattr(parent, widget_name):
                    widget = getattr(parent, widget_name)
                    if widget:
                        widget.configure(
                            bg=entry_bg,
                            fg=entry_fg,
                            selectbackground=select_bg,
                            selectforeground=select_fg
                        )
            
            for widget_name in ['log_text']:
                if hasattr(parent, widget_name):
                    widget = getattr(parent, widget_name)
                    if widget:
                        widget.configure(
                            bg=entry_bg,
                            fg=entry_fg,
                            selectbackground=select_bg,
                            selectforeground=select_fg
                        )
                        
        except Exception as e:
            print(f"更新现有组件样式失败: {e}")
    
    def get_modern_button_colors(self) -> Dict[str, str]:
        return {
            "bg": self.get_color('button_bg'),
            "fg": self.get_color('button_fg'),
            "hover_bg": self.get_color('button_active_bg'),
            "hover_fg": self.get_color('button_fg'),
            "active_bg": self.get_color('button_active_bg')
        }

style_manager = StyleManager()

class ModernButton(tk.Button):
    
    def __init__(self, parent, text="", command=None, style="primary", **kwargs):
        self.styles = {
            "primary": {
                "bg": "#8b4513",
                "fg": "white",
                "hover_bg": "#a0522d",
                "hover_fg": "white",
                "active_bg": "#654321"
            },
            "success": {
                "bg": "#228b22",
                "fg": "white",
                "hover_bg": "#32cd32",
                "hover_fg": "white",
                "active_bg": "#006400"
            },
            "danger": {
                "bg": "#b22222",
                "fg": "white",
                "hover_bg": "#dc143c",
                "hover_fg": "white",
                "active_bg": "#8b0000"
            },
            "secondary": {
                "bg": "#708090",
                "fg": "white",
                "hover_bg": "#778899",
                "hover_fg": "white",
                "active_bg": "#2f4f4f"
            },
            "info": {
                "bg": "#4682b4",
                "fg": "white",
                "hover_bg": "#5f9ea0",
                "hover_fg": "white",
                "active_bg": "#2e8b57"
            },
            "warning": {
                "bg": "#daa520",
                "fg": "white",
                "hover_bg": "#ffd700",
                "hover_fg": "#8b4513",
                "active_bg": "#b8860b"
            }
        }
        
        self.current_style = self.styles.get(style, self.styles["primary"])
        
        default_kwargs = {
            "bg": self.current_style["bg"],
            "fg": self.current_style["fg"],
            "relief": "flat",
            "bd": 0,
            "padx": 12,
            "pady": 4,
            "cursor": "hand2",
            "font": ("微软雅黑", 9)
        }
        
        default_kwargs.update(kwargs)
        
        super().__init__(parent, text=text, command=command, **default_kwargs)
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)
        
    def _on_enter(self, event):
        self.config(
            bg=self.current_style["hover_bg"],
            fg=self.current_style["hover_fg"]
        )
        
    def _on_leave(self, event):
        self.config(
            bg=self.current_style["bg"],
            fg=self.current_style["fg"]
        )
        
    def _on_click(self, event):
        self.config(bg=self.current_style["active_bg"])
        
    def _on_release(self, event):
        self.config(bg=self.current_style["hover_bg"])


class ModernFrame(tk.Frame):
    def __init__(self, parent, text=None, style="default", **kwargs):
        padding = kwargs.pop('padding', 5)
        super().__init__(parent, **kwargs)
        
        style_configs = {
            "default": { "relief": "flat", "bd": 1},
            "card": {"relief": "solid", "bd": 1, "highlightbackground": "#d4c4a8"},
            "section": {"relief": "flat", "bd": 0},
            "container": {"relief": "flat", "bd": 0},
            "text_area": {"relief": "solid", "bd": 1, "highlightbackground": "#c8b99c"}
        }
        
        config = style_configs.get(style, style_configs["default"])
        self.config(**config)
        
        if text:
            self._create_label_frame_effect(text, padding)
        else:
            if isinstance(padding, int):
                self.config(padx=padding, pady=padding)
    
    def _create_label_frame_effect(self, text, padding):
        self._title_label = ModernLabel(self, text=text, style="frame_title", width=50, justify=tk.LEFT)
        self._title_label.pack(anchor=tk.W, padx=padding, pady=(0, 0))
        
        content_frame = tk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=padding, pady=(0, padding))
        
        self._content_frame = content_frame
        
        self._has_title = True
        
    def pack_propagate(self, flag=None):
        if hasattr(self, '_content_frame'):
            return self._content_frame.pack_propagate(flag)
        return super().pack_propagate(flag)
        
    def winfo_children(self):
        if hasattr(self, '_content_frame'):
            children = [self._title_label] if hasattr(self, '_title_label') else []
            children.extend(self._content_frame.winfo_children())
            return children
        return super().winfo_children()
    
    def get_content_frame(self):
        if hasattr(self, '_content_frame'):
            return self._content_frame
        return self
    
    def update_text(self, text):
        if hasattr(self, '_title_label'):
            self._title_label.config(text=text)


class ModernEntry(tk.Entry):
    
    def __init__(self, parent, placeholder="", style="default", **kwargs):
        style_configs = {
            "default": {
                "relief": "flat",
                "bd": 1,
                "highlightthickness": 2,
                "highlightcolor": "#8b4513",
                "highlightbackground": "#c8b99c",
                "font": ("微软雅黑", 9),
                "bg": "#faf8f0",
                "fg": "#654321"
            },
            "search": {
                "relief": "flat",
                "bd": 1,
                "highlightthickness": 2,
                "highlightcolor": "#228b22",
                "highlightbackground": "#c8b99c",
                "font": ("微软雅黑", 9),
                "bg": "#f4f1e8",
                "fg": "#654321"
            },
            "error": {
                "relief": "flat",
                "bd": 1,
                "highlightthickness": 2,
                "highlightcolor": "#b22222",
                "highlightbackground": "#daa520",
                "font": ("微软雅黑", 9),
                "bg": "#fff5f5",
                "fg": "#8b0000"
            }
        }
        
        config = style_configs.get(style, style_configs["default"])
        config.update(kwargs)
        
        super().__init__(parent, **config)
        
        self._style = style
        self._style_configs = style_configs
        
        self.placeholder = placeholder
        self.placeholder_color = "#6c757d"
        self.normal_color = self.cget("fg")
        
        if placeholder:
            self._show_placeholder()
            
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        
    def _show_placeholder(self):
        self.insert(0, self.placeholder)
        self.config(fg=self.placeholder_color)
        
    def _hide_placeholder(self):
        if self.get() == self.placeholder:
            self.delete(0, tk.END)
            self.config(fg=self.normal_color)
            
    def _on_focus_in(self, event):
        self._hide_placeholder()
        config = self._style_configs.get(self._style, self._style_configs["default"])
        self.config(highlightbackground=config["highlightcolor"])
        
    def _on_focus_out(self, event):
        if not self.get():
            self._show_placeholder()
        config = self._style_configs.get(self._style, self._style_configs["default"])
        self.config(highlightbackground=config["highlightbackground"])
        
    def get_value(self):
        value = self.get()
        return "" if value == self.placeholder else value


class ModernProgressBar(ttk.Progressbar):
    
    def __init__(self, parent, **kwargs):
        style = ttk.Style()
        
        style.configure("Modern.Horizontal.TProgressbar",
                       background="#007bff",
                       troughcolor="#e9ecef",
                       borderwidth=0,
                       lightcolor="#007bff",
                       darkcolor="#007bff")
        
        default_kwargs = {
            "style": "Modern.Horizontal.TProgressbar",
            "length": 300,
            "mode": "determinate"
        }
        
        default_kwargs.update(kwargs)
        super().__init__(parent, **default_kwargs)


class ModernLabel(tk.Label):
    def __init__(self, parent, text="", style="default", **kwargs):
        style_configs = {
            "default": {
                "fg": "#654321",
                "font": ("Microsoft YaHei UI", 9),
                "anchor": "w"
            },
            "normal": {
                "fg": "#654321",
                "font": ("微软雅黑", 9)
            },
            "title": {
                "fg": "#654321",
                "font": ("Microsoft YaHei UI", 14, "bold"),
                "anchor": "center"
            },
            "subtitle": {
                "fg": "#8b4513",
                "font": ("微软雅黑", 11, "bold")
            },
            "muted": {
                "fg": "#a0522d",
                "font": ("微软雅黑", 8),
                "anchor": "w"
            },
            "success": {
                "fg": "#228b22",
                "font": ("微软雅黑", 9)
            },
            "danger": {
                "fg": "#b22222",
                "font": ("微软雅黑", 9)
            },
            "warning": {
                "fg": "#daa520",
                "font": ("微软雅黑", 9)
            },
            "label": {
                "fg": "#654321",
                "font": ("Microsoft YaHei UI", 9),
                "anchor": "w"
            },
            "frame_title": {
                "fg": "#8b4513",
                "font": ("Microsoft YaHei UI", 9, "bold"),
                "anchor": "w"
            }
        }
        
        config = style_configs.get(style, style_configs["default"])
        config.update(kwargs)
        
        super().__init__(parent, text=text, **config)


class ModernScrollbar(ttk.Scrollbar):
    
    def __init__(self, parent, orient="vertical", **kwargs):
        default_style = f"Modern.{orient.capitalize()}.TScrollbar"
        
        style = ttk.Style()
        
        scrollbar_bg = style_manager.get_color('scrollbar_bg')
        scrollbar_trough = style_manager.get_color('scrollbar_trough')
        scrollbar_active = style_manager.get_color('scrollbar_active')
        scrollbar_pressed = style_manager.get_color('scrollbar_pressed')
        scrollbar_arrow = style_manager.get_color('scrollbar_arrow')
        scrollbar_arrow_active = style_manager.get_color('scrollbar_arrow_active')
        
        style.configure(default_style,
                       background=scrollbar_bg,
                       troughcolor=scrollbar_trough,
                       borderwidth=0,
                       arrowcolor=scrollbar_arrow,
                       relief='flat',
                       width=8 if orient == 'vertical' else 8,
                       gripcount=0)
        
        style.map(default_style,
                 background=[('active', scrollbar_active),
                           ('pressed', scrollbar_pressed)],
                 arrowcolor=[('active', scrollbar_arrow_active),
                           ('pressed', '#212529')],
                 troughcolor=[('active', '#f1f3f4')])
        
        kwargs['style'] = default_style
        
        super().__init__(parent, orient=orient, **kwargs)
        
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
    
    def _on_enter(self, event):
        self.configure(cursor='hand2')
    
    def _on_leave(self, event):
        self.configure(cursor='')

class ModernScrollableFrame(tk.Frame):
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.v_scrollbar = ModernScrollbar(self, orient="vertical", command=self.canvas.yview)
        self.h_scrollbar = ModernScrollbar(self, orient="horizontal", command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set,
                            xscrollcommand=self.h_scrollbar.set)
        
        self.content_frame = tk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.content_frame.bind('<Configure>', self._on_frame_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.bind_all('<MouseWheel>', self._on_mousewheel)
    
    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
    
    def _on_mousewheel(self, event):
        if self.canvas.winfo_containing(event.x_root, event.y_root) == self.canvas:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def get_content_frame(self):
        return self.content_frame

def apply_modern_style_to_widget(widget, widget_type="button", style="primary"):
    if widget_type == "button":
        styles = {
            "primary": {"bg": "#007bff", "fg": "white", "relief": "flat"},
            "success": {"bg": "#28a745", "fg": "white", "relief": "flat"},
            "danger": {"bg": "#dc3545", "fg": "white", "relief": "flat"},
            "secondary": {"bg": "#6c757d", "fg": "white", "relief": "flat"}
        }
        
        if style in styles:
            widget.config(**styles[style])
            widget.config(cursor="hand2", font=("微软雅黑", 9))
            
    elif widget_type == "entry":
        widget.config(
            relief="flat",
            bd=1,
            highlightthickness=2,
            highlightcolor="#007bff",
            font=("微软雅黑", 9)
        )
        
    elif widget_type == "label":
        widget.config(
            font=("微软雅黑", 9),
            fg="#212529"
        )