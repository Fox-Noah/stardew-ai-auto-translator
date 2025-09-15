import tkinter as tk
from tkinter import ttk, messagebox
import time
import json
import re
import sys
import os
from typing import Callable, Optional, Dict, Any
from .modern_widgets import ModernButton, ModernFrame, ModernEntry, ModernLabel, apply_modern_style_to_widget, style_manager

class GUIManager:
    
    def __init__(self, parent):
        self.parent = parent
        self.root = parent.root
        self.widgets = {}
        self.callbacks = {}
        
        self.translation_progress = {"current": 0, "total": 0}
        
        self.current_selected_index = 0
        
        self.comboboxes = []
        
        self.root.bind('<Button-1>', self._on_global_click, add='+')
        
    def set_callbacks(self, callbacks: Dict[str, Callable]) -> None:
        self.callbacks = callbacks
    
    def _on_global_click(self, event):
        try:
            clicked_widget = event.widget
            
            if hasattr(self.parent, 'translation_listbox') and clicked_widget == self.parent.translation_listbox:
                return
            
            is_combo_click = False
            for combo in self.comboboxes:
                if combo and combo.winfo_exists() and clicked_widget == combo:
                    is_combo_click = True
                    break
            
            if not is_combo_click:
                self.root.after(100, self._close_all_combos)
        except Exception as e:
            pass
    
    def _close_all_combos(self):
        try:
            for combo in self.comboboxes:
                if combo and combo.winfo_exists():
                    try:
                        combo.event_generate('<Escape>')
                        combo.selection_clear()
                        self.root.focus_set()
                    except:
                        pass
        except:
            pass
    
    def _is_child_of(self, widget, parent):
        try:
            current = widget
            while current:
                if current == parent:
                    return True
                current = current.master
            return False
        except:
            return False
    

    def on_original_select(self, event):
        try:
            selection = self.parent.original_listbox.curselection()
            if selection:
                index = selection[0]
                self.current_selected_index = index
        except Exception as e:
            self.parent.log_message(f"原文选择错误: {str(e)}")

    def on_translation_select(self, event):
        try:
            selection = self.parent.translation_listbox.curselection()
            if selection:
                index = selection[0]
                self.parent.original_listbox.selection_clear(0, tk.END)
                self.parent.original_listbox.selection_set(index)
                self.parent.original_listbox.see(index)
        except Exception as e:
            self.parent.log_message(f"译文选择事件处理失败：{str(e)}")
    
    def on_shared_scrollbar(self, *args):
        self.parent.original_listbox.yview(*args)
        self.parent.translation_listbox.yview(*args)
    
    def on_shared_h_scrollbar(self, *args):
        self.parent.original_listbox.xview(*args)
        self.parent.translation_listbox.xview(*args)
    
    def on_original_h_scroll(self, *args):
        self.parent.original_h_scrollbar.set(*args)
        self.parent.translation_h_scrollbar.set(*args)
    
    def on_translation_h_scroll(self, *args):
        self.parent.translation_h_scrollbar.set(*args)
        self.parent.original_h_scrollbar.set(*args)
    
    def on_mouse_wheel(self, event):
        if event.delta:
            delta = -1 * (event.delta / 120)
        else:
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            else:
                return "break"
        
        current_top, current_bottom = self.parent.original_listbox.yview()
        
        total_items = self.parent.original_listbox.size()
        if total_items == 0:
            return "break"
        
        scroll_unit = 1.0 / total_items
        new_position = current_top + (delta * scroll_unit * 3)
        
        new_position = max(0.0, min(1.0, new_position))
        
        self.parent.original_listbox.yview_moveto(new_position)
        self.parent.translation_listbox.yview_moveto(new_position)
        
        self.parent.shared_scrollbar.set(new_position, new_position + (current_bottom - current_top))
        
        return "break"

    def on_combobox_mousewheel(self, event):
        return "break"

    def on_translation_double_click(self, event):
        try:
            index = self.parent.translation_listbox.nearest(event.y)
            
            if index < 0 or index >= self.parent.translation_listbox.size():
                return
            
            self.parent.translation_listbox.selection_clear(0, tk.END)
            self.parent.translation_listbox.selection_set(index)
            self.parent.translation_listbox.activate(index)
            
            current_translation = self.parent.translation_listbox.get(index)
            
            original_text = ""
            if hasattr(self.parent, 'current_translation_keys') and index < len(self.parent.current_translation_keys):
                key = self.parent.current_translation_keys[index]
                if hasattr(self.parent, 'current_original_data') and key in self.parent.current_original_data:
                    original_text = self.parent.current_original_data[key]
            
            self.edit_translation_dialog(index, original_text, current_translation)
            
        except Exception as e:
            self.parent.log_message(f"译文编辑失败：{str(e)}", "ERROR")
    

    

        
    def create_gui(self):
        main_frame = ModernFrame(self.root, padding=8)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.parent.title_label = ModernLabel(main_frame, text=self.parent.get_ui_text("title"), 
                                    font=style_manager.get_font('title'),
                                    style="title")
        self.parent.title_label.pack(fill=tk.X, pady=(0, 12))
        
        self.parent.config_frame = ModernFrame(main_frame, text=self.parent.get_ui_text("config"), 
                                              padding=8, style="card")
        self.parent.config_frame.pack(fill=tk.X, pady=(0, 8))
        
        config_content = ModernFrame(self.parent.config_frame, style="default")
        config_content.pack(fill=tk.X, expand=True)
        
        self.parent.target_lang_label = ModernLabel(config_content, 
                                                   text=self.parent.get_ui_text("target_language"),
                                                   style="label")
        self.parent.target_lang_label.pack(side=tk.LEFT, padx=(0, 8))
        language_combo = ttk.Combobox(config_content, textvariable=self.parent.target_language_var,
                                     values=list(self.parent.target_languages.keys()),
                                     state="readonly", width=15, font=style_manager.get_font('default'))
        language_combo.pack(side=tk.LEFT, padx=(0, 12))
        language_combo.bind('<<ComboboxSelected>>', self.parent.on_language_change)
        language_combo.bind('<MouseWheel>', self.on_combobox_mousewheel)
        self.comboboxes.append(language_combo)
        
        self.parent.model_label = ModernLabel(config_content, 
                                             text=self.parent.get_ui_text("translation_model"),
                                             style="label")
        self.parent.model_label.pack(side=tk.LEFT, padx=(0, 8))
        self.parent.model_combo = ttk.Combobox(config_content, textvariable=self.parent.ollama_model_var,
                                       state="readonly", width=20, font=style_manager.get_font('default'))
        self.parent.model_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.parent.model_combo.bind('<MouseWheel>', self.on_combobox_mousewheel)
        self.comboboxes.append(self.parent.model_combo)
        
        self.parent.refresh_models_btn = ModernButton(config_content, 
                                                     text=self.parent.get_ui_text("refresh_models"),
                                                     command=self.parent.refresh_models,
                                                     style="secondary")
        self.parent.refresh_models_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        self.parent.settings_btn = ModernButton(config_content, 
                                               text=self.parent.get_ui_text("settings_dialog"),
                                               command=self.show_settings_dialog,
                                               style="primary")
        self.parent.settings_btn.pack(side=tk.LEFT)
        
        self.parent.buttons_frame = ModernFrame(main_frame, text=self.parent.get_ui_text("functions"), 
                                               padding=8, style="card")
        self.parent.buttons_frame.pack(fill=tk.X, pady=(0, 8))
        
        buttons_content = ModernFrame(self.parent.buttons_frame.get_content_frame(), style="default")
        buttons_content.pack(fill=tk.X, expand=True)
        
        button_padx = 8
        
        self.parent.import_btn = ModernButton(buttons_content, 
                                            text=self.parent.get_ui_text("import_mod"),
                                            command=self.parent.import_mods,
                                            style="primary")
        self.parent.import_btn.pack(side=tk.LEFT, padx=(0, button_padx), fill=tk.X, expand=True)
        
        self.parent.extract_btn = ModernButton(buttons_content, 
                                             text=self.parent.get_ui_text("extract_mod"),
                                             command=self.parent.extract_mods,
                                             style="secondary")
        self.parent.extract_btn.pack(side=tk.LEFT, padx=(0, button_padx), fill=tk.X, expand=True)
        
        self.parent.extract_i18n_btn = ModernButton(buttons_content, 
                                                  text=self.parent.get_ui_text("extract_i18n"),
                                                  command=self.parent.extract_i18n,
                                                  style="info")
        self.parent.extract_i18n_btn.pack(side=tk.LEFT, padx=(0, button_padx), fill=tk.X, expand=True)
        
        self.parent.translate_btn = ModernButton(buttons_content, 
                                               text=self.parent.get_ui_text("auto_translate"),
                                               command=self.parent.auto_translate,
                                               style="success")
        self.parent.translate_btn.pack(side=tk.LEFT, padx=(0, button_padx), fill=tk.X, expand=True)
        
        self.parent.compress_btn = ModernButton(buttons_content, 
                                              text=self.parent.get_ui_text("recompress"),
                                              command=self.parent.recompress_mods,
                                              style="warning")
        self.parent.compress_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self._create_comparison_section(main_frame)
        
        self._create_log_section(main_frame)
        

    
    def _create_comparison_section(self, parent: ModernFrame) -> None:
        self.parent.compare_frame = ModernFrame(parent, text=self.parent.get_ui_text("text_comparison"), 
                                               padding=8, style="card")
        self.parent.compare_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        mod_selection_frame = ModernFrame(self.parent.compare_frame.get_content_frame(), style="section")
        mod_selection_frame.pack(fill=tk.X, pady=(0, 8))
        
        mod_row1 = ModernFrame(mod_selection_frame, style="default")
        mod_row1.pack(fill=tk.X, pady=(0, 6))
        
        self.parent.mod_label = ModernLabel(mod_row1, 
                                           text=self.parent.get_ui_text("select_mod"),
                                           style="label")
        self.parent.mod_label.pack(side=tk.LEFT, padx=(0, 8))
        self.parent.mod_combo = ttk.Combobox(mod_row1, state="readonly", width=40,
                                            font=("Microsoft YaHei UI", 9))
        self.parent.mod_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.parent.mod_combo.bind('<<ComboboxSelected>>', self.parent.on_mod_change)
        self.parent.mod_combo.bind('<MouseWheel>', self.on_combobox_mousewheel)
        self.comboboxes.append(self.parent.mod_combo)
        
        self.parent.refresh_mods_btn = ModernButton(mod_row1, 
                                                   text=self.parent.get_ui_text("refresh_mod_list"),
                                                   command=self.parent.refresh_mod_list,
                                                   style="secondary")
        self.parent.refresh_mods_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        self.parent.save_translation_btn = ModernButton(mod_row1, 
                                                       text=self.parent.get_ui_text("save_translation"), 
                                                       command=self.parent.save_translation_files,
                                                       style="success")
        self.parent.save_translation_btn.pack(side=tk.LEFT)
        
        mod_row2 = ModernFrame(mod_selection_frame, style="default")
        mod_row2.pack(side=tk.LEFT, padx=(0, 8))
        
        self.parent.clear_dirs_btn = ModernButton(mod_row2, 
                                                 text=self.parent.get_ui_text("clear_directories"), 
                                                 command=self._on_clear_directories,
                                                 style="danger")
        self.parent.clear_dirs_btn.pack(side=tk.RIGHT)
        
        self.parent.file_label = ModernLabel(mod_row2, 
                                            text=self.parent.get_ui_text("select_file"),
                                            style="label")
        self.parent.file_label.pack(side=tk.LEFT, padx=(0, 8))
        self.parent.file_combo = ttk.Combobox(mod_row2, state="readonly", width=40,
                                             font=("Microsoft YaHei UI", 9))
        self.parent.file_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.parent.file_combo.bind('<<ComboboxSelected>>', self.parent.on_file_change)
        self.parent.file_combo.bind('<MouseWheel>', self.on_combobox_mousewheel)
        self.comboboxes.append(self.parent.file_combo)
        
        container_frame = ModernFrame(self.parent.compare_frame.get_content_frame(), style="container")
        container_frame.pack(fill=tk.BOTH, expand=True)
        container_frame.columnconfigure(0, weight=1)
        container_frame.columnconfigure(1, weight=1)
        container_frame.columnconfigure(2, weight=0)
        container_frame.rowconfigure(0, weight=1)
        
        self.parent.left_frame = ModernFrame(container_frame, 
                                            text=self.parent.get_ui_text("original_text"), 
                                            padding=6, style="text_area")
        self.parent.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        
        self.parent.right_frame = ModernFrame(container_frame, 
                                             text=self.parent.get_ui_text("translation_text"), 
                                             padding=6, style="text_area")
        self.parent.right_frame.grid(row=0, column=1, sticky="nsew", padx=(3, 0))
        
        from .modern_widgets import style_manager
        self.parent.original_listbox = tk.Listbox(
            self.parent.left_frame.get_content_frame(), 
            height=12, 
            selectmode=tk.SINGLE,
            bg=style_manager.get_color('listbox_bg'),
            fg=style_manager.get_color('listbox_fg'),
            font=style_manager.get_font('default'),
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightcolor=style_manager.get_color('listbox_highlight_color'),
            highlightbackground=style_manager.get_color('listbox_highlight_bg'),
            selectbackground=style_manager.get_color('listbox_select_bg'),
            selectforeground=style_manager.get_color('listbox_select_fg')
        )
        self.parent.original_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=(2, 0))
        
        self.parent.original_h_scrollbar = ttk.Scrollbar(self.parent.left_frame.get_content_frame(), orient=tk.HORIZONTAL)
        self.parent.original_h_scrollbar.pack(fill=tk.X, padx=2, pady=(0, 2))
        self.parent.original_listbox.config(xscrollcommand=self.on_original_h_scroll)
        self.parent.original_h_scrollbar.config(command=self.on_shared_h_scrollbar)
        
        self.parent.translation_listbox = tk.Listbox(
            self.parent.right_frame.get_content_frame(), 
            height=12, 
            selectmode=tk.SINGLE,
            bg=style_manager.get_color('listbox_bg'),
            fg=style_manager.get_color('listbox_fg'),
            font=style_manager.get_font('default'),
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightcolor=style_manager.get_color('listbox_highlight_color'),
            highlightbackground=style_manager.get_color('listbox_highlight_bg'),
            selectbackground=style_manager.get_color('translation_listbox_select_bg'),
            selectforeground=style_manager.get_color('translation_listbox_select_fg')
        )
        self.parent.translation_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=(2, 0))
        
        self.parent.translation_h_scrollbar = ttk.Scrollbar(self.parent.right_frame.get_content_frame(), orient=tk.HORIZONTAL)
        self.parent.translation_h_scrollbar.pack(fill=tk.X, padx=2, pady=(0, 2))
        self.parent.translation_listbox.config(xscrollcommand=self.on_translation_h_scroll)
        self.parent.translation_h_scrollbar.config(command=self.on_shared_h_scrollbar)
        
        self.parent.shared_scrollbar = ttk.Scrollbar(container_frame, orient=tk.VERTICAL)
        self.parent.shared_scrollbar.grid(row=0, column=2, sticky="ns", padx=(2, 0))
        
        self.parent.shared_scrollbar.config(command=self.on_shared_scrollbar)
        self.parent.original_listbox.config(yscrollcommand=self.parent.shared_scrollbar.set)
        self.parent.translation_listbox.config(yscrollcommand=self.parent.shared_scrollbar.set)
        
        self.parent.original_listbox.bind('<<ListboxSelect>>', self.on_original_select)
        self.parent.translation_listbox.bind('<<ListboxSelect>>', self.on_translation_select)
        self.parent.original_listbox.bind('<MouseWheel>', self.on_mouse_wheel)
        self.parent.translation_listbox.bind('<MouseWheel>', self.on_mouse_wheel)
        self.parent.translation_listbox.bind('<Double-Button-1>', self.on_translation_double_click)
        
        self.parent.left_frame.columnconfigure(0, weight=1)
        self.parent.left_frame.rowconfigure(0, weight=1)
        self.parent.right_frame.columnconfigure(0, weight=1)
        self.parent.right_frame.rowconfigure(0, weight=1)
        self.parent.compare_frame.columnconfigure(0, weight=1)
        self.parent.compare_frame.rowconfigure(1, weight=1)
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)
        parent.columnconfigure(2, weight=0)
        parent.rowconfigure(3, weight=1)
        

        
        if hasattr(self.parent, 'style_manager'):
            self.parent.style_manager.apply_theme_to_root(self.parent.root)
            self.parent.style_manager.update_widget_styles(self.parent)
        
        self.parent.version_label = tk.Label(
            self.root,
            text="v1.1",
            font=("Microsoft YaHei UI", 8),
            fg="#666666",
            relief="flat",
            borderwidth=0
        )
        self.parent.version_label.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-0)
        
        self.parent._show_window_centered()
    
    def _create_log_section(self, parent: ModernFrame) -> None:
        self.parent.log_frame = tk.LabelFrame(parent, text="日志", bg=parent.cget('bg'))
        self.parent.log_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 8))
        
        from .modern_widgets import style_manager
        self.parent.log_text = tk.Text(
            self.parent.log_frame,
            height=3,
            wrap=tk.WORD,
            bg=style_manager.get_color('listbox_bg'),
            fg=style_manager.get_color('listbox_fg'),
            font=style_manager.get_font('default'),
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightcolor=style_manager.get_color('listbox_highlight_color'),
            highlightbackground=style_manager.get_color('listbox_highlight_bg'),
            state=tk.DISABLED
        )
        self.parent.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.parent.log_scrollbar = ttk.Scrollbar(self.parent.log_frame, orient=tk.VERTICAL)
        self.parent.log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.parent.log_text.config(yscrollcommand=self.parent.log_scrollbar.set)
        self.parent.log_scrollbar.config(command=self.parent.log_text.yview)
        
        self.parent.log_text.bind('<MouseWheel>', self.on_log_mouse_wheel)
    
    def on_log_mouse_wheel(self, event):
        if event.delta:
            delta = -1 * (event.delta / 120)
        else:
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            else:
                return "break"
        
        self.parent.log_text.yview_scroll(int(delta), "units")
        return "break"
    
    def update_ui_texts(self) -> None:
        self.root.title(self.parent.get_ui_text("title"))
        
        if hasattr(self.parent, 'title_label'):
            self.parent.title_label.config(text=self.parent.get_ui_text("title"))
        
        if hasattr(self.parent, 'config_frame'):
            self.parent.config_frame.update_text(self.parent.get_ui_text("config"))
        if hasattr(self.parent, 'target_lang_label'):
            self.parent.target_lang_label.config(text=self.parent.get_ui_text("target_language"))
        if hasattr(self.parent, 'model_label'):
            self.parent.model_label.config(text=self.parent.get_ui_text("translation_model"))
        
        if hasattr(self.parent, 'refresh_models_btn'):
            self.parent.refresh_models_btn.config(text=self.parent.get_ui_text("refresh_models"))
        
        if hasattr(self.parent, 'buttons_frame'):
            self.parent.buttons_frame.update_text(self.parent.get_ui_text("functions"))
        if hasattr(self.parent, 'import_btn'):
            self.parent.import_btn.config(text=self.parent.get_ui_text("import_mod"))
        if hasattr(self.parent, 'extract_btn'):
            self.parent.extract_btn.config(text=self.parent.get_ui_text("extract_mod"))
        if hasattr(self.parent, 'extract_i18n_btn'):
            self.parent.extract_i18n_btn.config(text=self.parent.get_ui_text("extract_i18n"))
        if hasattr(self.parent, 'translate_btn'):
            self.parent.translate_btn.config(text=self.parent.get_ui_text("auto_translate"))
        if hasattr(self.parent, 'compress_btn'):
            self.parent.compress_btn.config(text=self.parent.get_ui_text("recompress"))
        
        if hasattr(self.parent, 'compare_frame'):
            self.parent.compare_frame.update_text(self.parent.get_ui_text("text_comparison"))
        
        if hasattr(self.parent, 'left_frame'):
            self.parent.left_frame.update_text(self.parent.get_ui_text("original_text"))
        if hasattr(self.parent, 'right_frame'):
            self.parent.right_frame.update_text(self.parent.get_ui_text("translation_text"))
        
        if hasattr(self.parent, 'mod_label'):
            self.parent.mod_label.config(text=self.parent.get_ui_text("select_mod"))
        if hasattr(self.parent, 'refresh_mods_btn'):
            self.parent.refresh_mods_btn.config(text=self.parent.get_ui_text("refresh_mod_list"))
        if hasattr(self.parent, 'save_translation_btn'):
            self.parent.save_translation_btn.config(text=self.parent.get_ui_text("save_translation"))
        if hasattr(self.parent, 'clear_dirs_btn'):
            self.parent.clear_dirs_btn.config(text=self.parent.get_ui_text("clear_directories"))
        if hasattr(self.parent, 'file_label'):
            self.parent.file_label.config(text=self.parent.get_ui_text("select_file"))
        
        if hasattr(self.parent, 'settings_btn'):
            self.parent.settings_btn.config(text=self.parent.get_ui_text("settings_dialog"))
    
    def show_window_centered(self) -> None:
        self.root.update_idletasks()
        
        window_width = self.root.winfo_reqwidth()
        window_height = self.root.winfo_reqheight()
        
        if window_width < 900:
            window_width = 900
        if window_height < 600:
            window_height = 600
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.root.deiconify()
    
    def update_translate_button_text(self, is_translating: bool) -> None:
        if hasattr(self.parent, 'translate_btn'):
            if is_translating:
                self.parent.translate_btn.config(text=self.parent.get_ui_text("stop_translate"))
            else:
                self.parent.translate_btn.config(text=self.parent.get_ui_text("auto_translate"))
    
    def set_widget_state(self, widget_name: str, state: str) -> None:
        if hasattr(self.parent, widget_name):
            widget = getattr(self.parent, widget_name)
            if hasattr(widget, 'config'):
                widget.config(state=state)
    
    def update_translation_display(self, key: str, translated_text: str) -> None:
        try:
            if hasattr(self.parent, 'current_translation_keys') and key in self.parent.current_translation_keys:
                index = self.parent.current_translation_keys.index(key)
                if index < self.parent.translation_listbox.size():
                    self.parent.translation_listbox.delete(index)
                    self.parent.translation_listbox.insert(index, translated_text)
                    if hasattr(self.parent, 'current_translation_data'):
                        self.parent.current_translation_data[key] = translated_text
        except Exception as e:
            self.parent.log_message(self.parent.get_ui_text("update_translation_display_failed").format(str(e)), "ERROR")
    
    def get_ui_text(self, key: str) -> str:
        return self.parent.ui_text_manager.get_text(key)
    
    def on_language_change(self, event=None):
        selected_language = self.parent.target_language_var.get()
        if selected_language in self.parent.ui_text_manager.get_available_languages():
            self.parent.current_ui_language = selected_language
            self.parent.ui_text_manager.set_language(selected_language)
            self.update_ui_texts()
            self.parent.save_config()
    
    def log_message(self, message: str, level: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        
        print(log_entry)
    
    def update_progress_display(self, current=None, total=None):
        if current is not None:
            self.parent.translation_progress["current"] = current
        if total is not None:
            self.parent.translation_progress["total"] = total
        
        self.root.after(0, self._update_log_frame_title)
    
    def _update_log_frame_title(self):
        base_title = self.parent.get_ui_text("log")
        if self.parent.translation_progress["total"] > 0:
            progress_text = f"({self.parent.translation_progress['current']}/{self.parent.translation_progress['total']})"
            title_with_progress = f"{base_title}{progress_text}"
        else:
            title_with_progress = base_title
        
        if hasattr(self.parent, 'log_frame'):
            self.parent.log_frame.config(text=title_with_progress)
    
    def on_original_select(self, event):
        try:
            selection = self.parent.original_listbox.curselection()
            if selection:
                index = selection[0]
                self.parent.current_selected_index = index
        except Exception as e:
            self.parent.log_message(f"原文选择错误: {str(e)}")

    def on_translation_select(self, event):
        try:
            selection = self.parent.translation_listbox.curselection()
            if selection:
                index = selection[0]
                self.parent.original_listbox.selection_clear(0, tk.END)
                self.parent.original_listbox.selection_set(index)
                self.parent.original_listbox.see(index)
        except Exception as e:
            self.parent.log_message(f"译文选择事件处理失败：{str(e)}")
    
    def on_shared_scrollbar(self, *args):
        self.parent.original_listbox.yview(*args)
        self.parent.translation_listbox.yview(*args)
    
    def on_shared_h_scrollbar(self, *args):
        self.parent.original_listbox.xview(*args)
        self.parent.translation_listbox.xview(*args)
    
    def on_original_h_scroll(self, *args):
        self.parent.original_h_scrollbar.set(*args)
        self.parent.translation_h_scrollbar.set(*args)
    
    def on_translation_h_scroll(self, *args):
        self.parent.translation_h_scrollbar.set(*args)
        self.parent.original_h_scrollbar.set(*args)
    
    def on_mouse_wheel(self, event):
        if event.delta:
            delta = -1 * (event.delta / 120)
        else:
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            else:
                return "break"
        
        current_top, current_bottom = self.parent.original_listbox.yview()
        
        total_items = self.parent.original_listbox.size()
        if total_items == 0:
            return "break"
        
        scroll_unit = 1.0 / total_items
        new_position = current_top + (delta * scroll_unit * 3)
        
        new_position = max(0.0, min(1.0, new_position))
        
        self.parent.original_listbox.yview_moveto(new_position)
        self.parent.translation_listbox.yview_moveto(new_position)
        
        self.parent.shared_scrollbar.set(new_position, new_position + (current_bottom - current_top))
        
        return "break"

    def on_combobox_mousewheel(self, event):
        return "break"

    def on_translation_double_click(self, event):
        try:
            index = self.parent.translation_listbox.nearest(event.y)
            
            if index < 0 or index >= self.parent.translation_listbox.size():
                return
            
            self.parent.translation_listbox.selection_clear(0, tk.END)
            self.parent.translation_listbox.selection_set(index)
            self.parent.translation_listbox.activate(index)
            
            current_translation = self.parent.translation_listbox.get(index)
            
            original_text = ""
            if hasattr(self.parent, 'current_translation_keys') and index < len(self.parent.current_translation_keys):
                key = self.parent.current_translation_keys[index]
                if hasattr(self.parent, 'current_original_data') and key in self.parent.current_original_data:
                    original_text = self.parent.current_original_data[key]
            
            self.edit_translation_dialog(index, original_text, current_translation)
            
        except Exception as e:
            self.parent.log_message(f"译文编辑失败：{str(e)}", "ERROR")
    
    def edit_translation_dialog(self, index, original_text, current_translation):
        dialog = tk.Toplevel(self.root)
        dialog.title(self.parent.get_ui_text("edit_translation_dialog"))
        dialog.resizable(True, True)
        dialog.transient(self.root)
        
        dialog.withdraw()
        
        if getattr(sys, 'frozen', False):
            try:
                dialog.iconbitmap(default=sys.executable)
            except Exception as e:
                print(f"设置编辑对话框图标失败: {e}")
        else:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
            if os.path.exists(icon_path):
                try:
                    dialog.iconbitmap(icon_path)
                except Exception as e:
                    print(f"设置编辑对话框图标失败: {e}")
        
        main_container = ModernFrame(dialog, style="container")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=1)
        main_container.grid_rowconfigure(2, weight=0)
        main_container.grid_columnconfigure(0, weight=1)
        
        original_frame = ModernFrame(main_container, text=self.parent.get_ui_text("original_text"), style="section", padding=5)
        original_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        original_text_frame = ModernFrame(original_frame.get_content_frame(), style="default")
        original_text_frame.pack(fill=tk.BOTH, expand=True)
        
        original_text_widget = tk.Text(original_text_frame, wrap=tk.WORD, state='disabled',
                                      height=8,
                                      font=("Microsoft YaHei UI", 9),
                                      bg="#f8f9fa", fg="#495057",
                                      selectbackground="#e9ecef",
                                      selectforeground="#495057")
        original_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        original_scrollbar = ttk.Scrollbar(original_text_frame, orient=tk.VERTICAL, command=original_text_widget.yview)
        original_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        original_text_widget.config(yscrollcommand=original_scrollbar.set)
        
        original_text_widget.config(state='normal')
        original_text_widget.insert(1.0, original_text)
        original_text_widget.config(state='disabled')
        
        translation_frame = ModernFrame(main_container, text=self.parent.get_ui_text("translation"), style="section", padding=5)
        translation_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        
        translation_text_frame = ModernFrame(translation_frame.get_content_frame(), style="default")
        translation_text_frame.pack(fill=tk.BOTH, expand=True)
        
        translation_text_widget = tk.Text(translation_text_frame, wrap=tk.WORD,
                                         height=8,
                                         font=("Microsoft YaHei UI", 9),
                                         bg="#ffffff", fg="#2c3e50",
                                         selectbackground="#3498db",
                                         selectforeground="#ffffff",
                                         insertbackground="#2c3e50")
        translation_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        translation_scrollbar = ttk.Scrollbar(translation_text_frame, orient=tk.VERTICAL, command=translation_text_widget.yview)
        translation_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        translation_text_widget.config(yscrollcommand=translation_scrollbar.set)
        
        translation_text_widget.insert(1.0, current_translation)
        
        button_frame = ModernFrame(main_container, style="default", padding=5)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(0, 0))
        
        def save_edit():
            try:
                new_text = translation_text_widget.get(1.0, tk.END).strip()
                
                self.parent.translation_listbox.delete(index)
                self.parent.translation_listbox.insert(index, new_text)
                self.parent.translation_listbox.selection_set(index)
                
                if hasattr(self.parent, 'current_translation_keys') and index < len(self.parent.current_translation_keys):
                    key = self.parent.current_translation_keys[index]
                    if hasattr(self.parent, 'current_translation_data'):
                        self.parent.current_translation_data[key] = new_text
                
                self.parent.log_message(self.parent.get_ui_text("translation_updated"))
                dialog.destroy()
            except Exception as e:
                self.parent.log_message(self.parent.get_ui_text("save_translation_failed").format(str(e)), "ERROR")
        
        def cancel_edit():
            dialog.destroy()
        
        cancel_btn = ModernButton(button_frame, text=self.parent.get_ui_text("cancel"), 
                                 command=cancel_edit, style="secondary")
        cancel_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        
        save_btn = ModernButton(button_frame, text=self.parent.get_ui_text("save"), 
                               command=save_edit, style="primary")
        save_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        
        def show_dialog():
            dialog.update_idletasks()
            
            dialog.geometry("")
            dialog.update_idletasks()
            
            min_width = 800
            min_height = 600
            req_width = max(min_width, dialog.winfo_reqwidth())
            req_height = max(min_height, dialog.winfo_reqheight())
            
            x = (dialog.winfo_screenwidth() // 2) - (req_width // 2)
            y = (dialog.winfo_screenheight() // 2) - (req_height // 2)
            dialog.geometry(f"{req_width}x{req_height}+{x}+{y}")
            
            dialog.deiconify()
            dialog.grab_set()
            dialog.lift()
            dialog.focus_force()
            
            translation_text_widget.focus_set()
        
        dialog.after(50, show_dialog)
    
    def refresh_mod_list(self):
        try:
            self.parent.available_mods = []
            
            i18n_dir = self.parent.i18n_dir
            original_dir = i18n_dir / "Original"
            
            if not original_dir.exists():
                self.parent.log_message("Original目录不存在，请先提取i18n文件")
                return
            
            for mod_path in original_dir.iterdir():
                if mod_path.is_dir():
                    json_files = list(mod_path.rglob("*.json"))
                    if json_files:
                        self.parent.available_mods.append({
                            'name': mod_path.name,
                            'path': mod_path,
                            'files': json_files
                        })
            
            mod_names = [mod['name'] for mod in self.parent.available_mods]
            self.parent.mod_combo['values'] = mod_names
            
            if mod_names:
                if self.parent.current_mod_index < len(mod_names):
                    self.parent.mod_combo.current(self.parent.current_mod_index)
                else:
                    self.parent.mod_combo.current(0)
                    self.parent.current_mod_index = 0
                self.parent.log_message(self.parent.get_ui_text("found_mods").format(len(mod_names), ', '.join(mod_names)))
                self.parent.on_mod_change()
            else:
                self.parent.mod_combo.set("")
                self.parent.log_message(self.parent.get_ui_text("no_mods_found"))
                
        except Exception as e:
            self.parent.log_message(self.parent.get_ui_text("refresh_mod_list_failed").format(str(e)), "ERROR")
    
    def show_settings_dialog(self):
        try:
            settings_dialog = tk.Toplevel(self.root)
            settings_dialog.title(self.parent.get_ui_text("settings_dialog"))
            settings_dialog.resizable(False, False)
            settings_dialog.transient(self.root)
            
            from .modern_widgets import style_manager
            settings_dialog.config(bg=style_manager.get_color('bg'))
            
            if getattr(sys, 'frozen', False):
                try:
                    settings_dialog.iconbitmap(default=sys.executable)
                except Exception as e:
                    print(f"设置对话框图标失败: {e}")
            else:
                icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
                if os.path.exists(icon_path):
                    try:
                        settings_dialog.iconbitmap(icon_path)
                    except Exception as e:
                        print(f"设置对话框图标失败: {e}")
            
            main_container = ModernFrame(settings_dialog, style="container", padding=8)
            main_container.pack(fill=tk.BOTH, expand=True)
            
            batch_frame = ModernFrame(main_container, text=self.parent.get_ui_text("batch_translate_settings"), 
                                    style="card", padding=5)
            batch_frame.pack(fill=tk.X, pady=(0, 8))
            
            batch_content = ModernFrame(batch_frame.get_content_frame(), style="default")
            batch_content.pack(fill=tk.X, padx=5, pady=5)
            
            ModernLabel(batch_content, text=self.parent.get_ui_text("batch_size_label")).pack(anchor=tk.W)
            
            batch_input_frame = ModernFrame(batch_content, style="default")
            batch_input_frame.pack(fill=tk.X, pady=(5, 0))
            
            self.parent.batch_size_var = tk.StringVar(value=str(getattr(self.parent, 'batch_size', 5)))
            batch_spinbox = ttk.Spinbox(batch_input_frame, from_=1, to=20, width=10, 
                                       textvariable=self.parent.batch_size_var,
                                       font=("Microsoft YaHei UI", 9))
            batch_spinbox.pack(side=tk.LEFT)
            
            ModernLabel(batch_input_frame, text=self.parent.get_ui_text("entries_unit")).pack(side=tk.LEFT, padx=(10, 0))
            
            save_frame = ModernFrame(main_container, text=self.parent.get_ui_text("auto_save_settings"), 
                                   style="card", padding=5)
            save_frame.pack(fill=tk.X, pady=(0, 8))
            
            save_content = ModernFrame(save_frame.get_content_frame(), style="default")
            save_content.pack(fill=tk.X, padx=5, pady=5)
            
            ModernLabel(save_content, text=self.parent.get_ui_text("auto_save_interval_label")).pack(anchor=tk.W)
            
            save_input_frame = ModernFrame(save_content, style="default")
            save_input_frame.pack(fill=tk.X, pady=(5, 0))
            
            self.parent.auto_save_interval_var = tk.StringVar(value=str(getattr(self.parent, 'auto_save_interval', 20)))
            save_spinbox = ttk.Spinbox(save_input_frame, from_=1, to=100, width=10, 
                                      textvariable=self.parent.auto_save_interval_var,
                                      font=("Microsoft YaHei UI", 9))
            save_spinbox.pack(side=tk.LEFT)
            
            ModernLabel(save_input_frame, text=self.parent.get_ui_text("entries_unit")).pack(side=tk.LEFT, padx=(10, 0))
            

            
            button_frame = ModernFrame(main_container, style="default", padding=5)
            button_frame.pack(fill=tk.X, pady=(20, 0))
            
            def save_settings():
                try:
                    self.parent.batch_size = int(self.parent.batch_size_var.get())
                    self.parent.auto_save_interval = int(self.parent.auto_save_interval_var.get())
                    
                    self.parent.save_config()
                    self.parent.log_message(self.parent.get_ui_text("settings_saved"))
                    settings_dialog.destroy()
                except ValueError:
                    messagebox.showerror(self.parent.get_ui_text("error"), self.parent.get_ui_text("invalid_number_input"), parent=settings_dialog)
                except Exception as e:
                    messagebox.showerror("错误", f"保存设置时出错: {str(e)}", parent=settings_dialog)
            
            def cancel_settings():
                settings_dialog.destroy()
            
            cancel_btn = ModernButton(button_frame, text=self.parent.get_ui_text("cancel"), 
                                     command=cancel_settings, style="secondary")
            cancel_btn.pack(side=tk.RIGHT, padx=5, pady=5)
            
            save_btn = ModernButton(button_frame, text=self.parent.get_ui_text("save"), 
                                   command=save_settings, style="primary")
            save_btn.pack(side=tk.RIGHT, padx=5, pady=5)
            
            def show_dialog():
                settings_dialog.update_idletasks()
                
                settings_dialog.geometry("")
                settings_dialog.update_idletasks()
                
                min_width = 420
                req_width = max(min_width, settings_dialog.winfo_reqwidth())
                req_height = settings_dialog.winfo_reqheight()
                
                x = (settings_dialog.winfo_screenwidth() // 2) - (req_width // 2)
                y = (settings_dialog.winfo_screenheight() // 2) - (req_height // 2)
                settings_dialog.geometry(f"{req_width}x{req_height}+{x}+{y}")
                
                settings_dialog.deiconify()
                settings_dialog.grab_set()
                settings_dialog.lift()
                settings_dialog.focus_force()
            
            settings_dialog.withdraw()
            settings_dialog.after(50, show_dialog)
            
        except Exception as e:
            self.parent.log_message(f"{self.parent.get_ui_text('show_settings_dialog_failed')}: {str(e)}", "ERROR")
    

    
    def show_window_centered(self) -> None:
        self.root.update_idletasks()
        
        window_width = self.root.winfo_reqwidth()
        window_height = self.root.winfo_reqheight()
        
        if window_width < 900:
            window_width = 900
        if window_height < 600:
            window_height = 600
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.root.deiconify()
    
    def update_progress_display(self, current=None, total=None) -> None:
        if current is not None:
            self.translation_progress["current"] = current
        if total is not None:
            self.translation_progress["total"] = total
        
        self.root.after(0, self._update_log_frame_title)
    
    def _update_log_frame_title(self) -> None:
        base_title = self.ui_text_manager.get_text("log")
        if self.translation_progress["total"] > 0:
            progress_text = f"({self.translation_progress['current']}/{self.translation_progress['total']})"
            title_with_progress = f"{base_title}{progress_text}"
        else:
            title_with_progress = base_title
        
        if 'log_frame' in self.widgets:
            self.widgets['log_frame'].config(text=title_with_progress)
    
    def update_translate_button_text(self, is_translating: bool) -> None:
        if 'translate_btn' in self.widgets:
            if is_translating:
                self.widgets['translate_btn'].config(text=self.ui_text_manager.get_text("stop_translate"))
            else:
                self.widgets['translate_btn'].config(text=self.ui_text_manager.get_text("auto_translate"))
    
    def get_widget(self, name: str):
        return self.widgets.get(name)
    
    def set_widget_state(self, name: str, state: str) -> None:
        widget = self.widgets.get(name)
        if widget and hasattr(widget, 'config'):
            widget.config(state=state)
    
    def _on_language_change(self, event=None) -> None:
        if 'on_language_change' in self.callbacks:
            self.callbacks['on_language_change'](event)
    
    def _on_refresh_models(self) -> None:
        if 'on_refresh_models' in self.callbacks:
            self.callbacks['on_refresh_models']()
    
    def _on_show_settings(self) -> None:
        if 'on_show_settings' in self.callbacks:
            self.callbacks['on_show_settings']()
    
    def _on_import_mods(self) -> None:
        if 'on_import_mods' in self.callbacks:
            self.callbacks['on_import_mods']()
    
    def _on_extract_mods(self) -> None:
        if 'on_extract_mods' in self.callbacks:
            self.callbacks['on_extract_mods']()
    
    def _on_extract_i18n(self) -> None:
        if 'on_extract_i18n' in self.callbacks:
            self.callbacks['on_extract_i18n']()
    
    def _on_auto_translate(self) -> None:
        if 'on_auto_translate' in self.callbacks:
            self.callbacks['on_auto_translate']()
    
    def _on_recompress_mods(self) -> None:
        if 'on_recompress_mods' in self.callbacks:
            self.callbacks['on_recompress_mods']()
    
    def _on_mod_change(self, event=None) -> None:
        if 'on_mod_change' in self.callbacks:
            self.callbacks['on_mod_change'](event)
    
    def _on_file_change(self, event=None) -> None:
        if 'on_file_change' in self.callbacks:
            self.callbacks['on_file_change'](event)
    
    def _on_refresh_mod_list(self) -> None:
        if 'on_refresh_mod_list' in self.callbacks:
            self.callbacks['on_refresh_mod_list']()
    
    def _on_save_translation(self) -> None:
        if 'on_save_translation' in self.callbacks:
            self.callbacks['on_save_translation']()
    
    def _on_combobox_mousewheel(self, event) -> str:
        return "break"
    
    def _on_original_select(self, event) -> None:
        if 'on_original_select' in self.callbacks:
            self.callbacks['on_original_select'](event)
    
    def _on_translation_select(self, event) -> None:
        if 'on_translation_select' in self.callbacks:
            self.callbacks['on_translation_select'](event)
    
    def _on_shared_scrollbar(self, *args) -> None:
        if 'original_listbox' in self.widgets:
            self.widgets['original_listbox'].yview(*args)
        if 'translation_listbox' in self.widgets:
            self.widgets['translation_listbox'].yview(*args)
    
    def _on_shared_h_scrollbar(self, *args) -> None:
        if 'original_listbox' in self.widgets:
            self.widgets['original_listbox'].xview(*args)
        if 'translation_listbox' in self.widgets:
            self.widgets['translation_listbox'].xview(*args)
    
    def _on_original_h_scroll(self, *args) -> None:
        if 'original_h_scrollbar' in self.widgets:
            self.widgets['original_h_scrollbar'].set(*args)
        if 'translation_h_scrollbar' in self.widgets:
            self.widgets['translation_h_scrollbar'].set(*args)
    
    def _on_translation_h_scroll(self, *args) -> None:
        if 'translation_h_scrollbar' in self.widgets:
            self.widgets['translation_h_scrollbar'].set(*args)
        if 'original_h_scrollbar' in self.widgets:
            self.widgets['original_h_scrollbar'].set(*args)
    
    def _on_mouse_wheel(self, event) -> str:
        if event.delta:
            delta = -1 * (event.delta / 120)
        else:
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            else:
                return "break"
        
        if 'original_listbox' not in self.widgets:
            return "break"
            
        current_top, current_bottom = self.widgets['original_listbox'].yview()
        
        total_items = self.widgets['original_listbox'].size()
        if total_items == 0:
            return "break"
        
        scroll_unit = 1.0 / total_items
        new_position = current_top + (delta * scroll_unit * 3)
        
        new_position = max(0.0, min(1.0, new_position))
        
        self.widgets['original_listbox'].yview_moveto(new_position)
        if 'translation_listbox' in self.widgets:
            self.widgets['translation_listbox'].yview_moveto(new_position)
        
        if 'shared_scrollbar' in self.widgets:
            self.widgets['shared_scrollbar'].set(new_position, new_position + (current_bottom - current_top))
        
        return "break"
    
    def _on_translation_double_click(self, event) -> None:
        if 'on_translation_double_click' in self.callbacks:
            self.callbacks['on_translation_double_click'](event)
    
    def _on_clear_directories(self) -> None:
        self.show_clear_directories_dialog()
    
    def show_clear_directories_dialog(self):
        try:
            clear_dialog = tk.Toplevel(self.root)
            clear_dialog.title(self.parent.get_ui_text("clear_directories"))
            clear_dialog.resizable(False, False)
            clear_dialog.transient(self.root)
            
            from .modern_widgets import style_manager
            clear_dialog.config(bg=style_manager.get_color('bg'))
            
            if getattr(sys, 'frozen', False):
                try:
                    clear_dialog.iconbitmap(default=sys.executable)
                except Exception as e:
                    print(f"设置对话框图标失败: {e}")
            else:
                icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
                if os.path.exists(icon_path):
                    try:
                        clear_dialog.iconbitmap(icon_path)
                    except Exception as e:
                        print(f"设置对话框图标失败: {e}")
            
            main_container = ModernFrame(clear_dialog, style="container", padding=8)
            main_container.pack(fill=tk.BOTH, expand=True)
            
            warning_frame = ModernFrame(main_container, text=f"⚠️ {self.parent.get_ui_text('warning')}", 
                                      style="card", padding=5)
            warning_frame.pack(fill=tk.X, pady=(0, 8))
            
            warning_content = ModernFrame(warning_frame.get_content_frame(), style="default")
            warning_content.pack(fill=tk.X, padx=5, pady=5)
            
            info_text = self.parent.get_ui_text("clear_directories_message")
            info_label = ModernLabel(warning_content, text=info_text, 
                                   justify=tk.LEFT, wraplength=350)
            info_label.pack(anchor=tk.W)
            
            button_frame = ModernFrame(main_container, style="default", padding=5)
            button_frame.pack(fill=tk.X, pady=(20, 0))
            
            def confirm_clear():
                try:
                    if hasattr(self.parent, 'file_manager') and hasattr(self.parent.file_manager, 'clear_data_directories'):
                        self.parent.file_manager.clear_data_directories()
                        self.parent.log_message(self.parent.get_ui_text("clear_directories_success"))
                        clear_dialog.destroy()
                    else:
                        self.parent.log_message(self.parent.get_ui_text("clear_directories_unavailable"), "ERROR")
                except Exception as e:
                    self.parent.log_message(self.parent.get_ui_text("clear_directories_error").format(str(e)), "ERROR")
            
            def cancel_clear():
                clear_dialog.destroy()
            
            cancel_btn = ModernButton(button_frame, text=self.parent.get_ui_text("cancel"), 
                                     command=cancel_clear, style="secondary")
            cancel_btn.pack(side=tk.RIGHT, padx=5, pady=5)
            
            confirm_btn = ModernButton(button_frame, text=self.parent.get_ui_text("clear_directories_confirm"), 
                                     command=confirm_clear, style="danger")
            confirm_btn.pack(side=tk.RIGHT, padx=5, pady=5)
            
            def show_dialog():
                clear_dialog.update_idletasks()
                
                clear_dialog.geometry("")
                clear_dialog.update_idletasks()
                
                min_width = 420
                req_width = max(min_width, clear_dialog.winfo_reqwidth())
                req_height = clear_dialog.winfo_reqheight()
                
                x = (clear_dialog.winfo_screenwidth() // 2) - (req_width // 2)
                y = (clear_dialog.winfo_screenheight() // 2) - (req_height // 2)
                clear_dialog.geometry(f"{req_width}x{req_height}+{x}+{y}")
                
                clear_dialog.deiconify()
                clear_dialog.grab_set()
                clear_dialog.lift()
                clear_dialog.focus_force()
            
            clear_dialog.withdraw()
            clear_dialog.after(50, show_dialog)
            
        except Exception as e:
            self.parent.log_message(self.parent.get_ui_text("clear_directories_dialog_error").format(str(e)), "ERROR")