
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import threading
import time
import json
import zipfile
import shutil
import requests
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Optional

from modules.gui_manager import GUIManager
from modules.ollama_manager import OllamaManager, OllamaTranslator
from modules.translation_manager import TranslationManager
from modules.config_manager import ConfigManager
from modules.file_manager import FileManager
from modules.translation_core import TranslationCore
from modules.ui_text_manager import UITextManager
from modules.modern_widgets import style_manager



class StardewValleyTranslator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("星露谷物语mod i18n AI翻译工具")
        self.root.geometry("900x600")
        self.root.minsize(880, 500)
        
        if getattr(sys, 'frozen', False):
            try:
                self.root.iconbitmap(default=sys.executable)
            except Exception as e:
                print(f"设置主窗口图标失败: {e}")
        else:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
            if os.path.exists(icon_path):
                try:
                    self.root.iconbitmap(icon_path)
                except Exception as e:
                    print(f"设置主窗口图标失败: {e}")
        
        self.file_manager = FileManager(self)
        
        self.work_dir = self.file_manager.work_dir
        self.data_dir = self.file_manager.data_dir
        self.import_dir = self.file_manager.import_dir
        self.extract_dir = self.file_manager.extract_dir
        self.i18n_dir = self.file_manager.i18n_dir
        self.compress_dir = self.file_manager.compress_dir
        
        self.config_file = self.data_dir / "config.json"
        
        self.ollama_base_url = "http://localhost:11434"
        self.ollama_model = None
        self.available_models = []
        
        self.ollama_translator = None
        
        self.config_manager = ConfigManager(self.config_file)
        
        self.ui_text_manager = UITextManager()
        
        self.gui_manager = GUIManager(self)
        
        self.style_manager = style_manager
        
        self.ollama_manager = OllamaManager(self)
        
        self.translator = self.ollama_manager.translator
        
        self.translation_manager = TranslationManager(self)
        
        self.is_translating = False
        self.translation_thread = None
        self.current_progress = 0
        self.total_progress = 0
        
        self.translation_progress = {"current": 0, "total": 0}
        
        self.available_mods = []
        self.current_mod_index = 0
        self.current_mod_path = None
        
        self.available_files = []
        self.current_file_index = 0
        
        self.target_languages = {
            "中文": "Chinese",
            "English": "English", 
            "日本語": "Japanese",
            "한국어": "Korean",
            "Français": "French",
            "Deutsch": "German",
            "Español": "Spanish",
            "Русский": "Russian",
            "Português (BR)": "Brazilian Portuguese",
            "Italiano": "Italian",
            "Türkçe": "Turkish",
            "Magyar": "Hungarian"
        }
        
        self.language_codes = {
            "中文": "zh",
            "English": "default", 
            "日本語": "ja",
            "한국어": "ko",
            "Français": "fr",
            "Deutsch": "de",
            "Español": "es",
            "Русский": "ru",
            "Português (BR)": "pt",
            "Italiano": "it",
            "Türkçe": "tr",
            "Magyar": "hu"
        }
        
        self.ui_texts = self.ui_text_manager.ui_texts
        
        self.current_ui_language = "中文"
        
        self.batch_size = 5
        self.auto_save_interval = 20
        
        self.load_config()
        
        self.target_language_var = tk.StringVar(value=self.current_ui_language)
        self.ollama_model_var = tk.StringVar(value="")
        self.batch_size_var = tk.StringVar(value=str(self.batch_size))
        self.auto_save_interval_var = tk.StringVar(value=str(self.auto_save_interval))
        
        self.create_gui()
        
        self._async_initialize()
    
    def _show_window_centered(self):
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
    
    def load_config(self):
        config = self.config_manager.load_config()
        self.current_ui_language = config.get('ui_language', '中文')
        self.ui_text_manager.set_language(self.current_ui_language)
        self.ollama_model = config.get('ollama_model', 'qwen2.5:7b')
        self.batch_size = config.get('batch_size', 5)
        self.auto_save_interval = config.get('auto_save_interval', 20)
    
    def save_config(self):
        config = {
            'ui_language': getattr(self, 'current_ui_language', '中文'),
            'ollama_model': getattr(self, 'ollama_model', 'qwen2.5:7b'),
            'batch_size': getattr(self, 'batch_size', 5),
            'auto_save_interval': getattr(self, 'auto_save_interval', 20)
        }
        for key, value in config.items():
            self.config_manager.set(key, value)
        self.config_manager.save_config()
    
    def create_gui(self):
        self.gui_manager.create_gui()
    
    def get_ui_text(self, key: str) -> str:
        return self.ui_texts.get(self.current_ui_language, {}).get(key, key)
    
    def on_language_change(self, event=None):
        selected_language = self.target_language_var.get()
        if selected_language in self.target_languages:
            self.current_ui_language = selected_language
            self.ui_text_manager.set_language(selected_language)
            self.update_ui_texts()
            self.save_config()
    
    def update_ui_texts(self):
        self.gui_manager.update_ui_texts()
    
    def log_message(self, message: str, level: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        
        print(log_entry)
        
        if hasattr(self, 'log_text'):
            self.root.after(0, self._append_log_to_gui, log_entry)
    
    def _append_log_to_gui(self, log_entry: str):
        try:
            if hasattr(self, 'log_text'):
                self.log_text.config(state=tk.NORMAL)
                
                if self.log_text.get("1.0", tk.END).strip():
                    self.log_text.insert(tk.END, "\n")
                self.log_text.insert(tk.END, log_entry)
                
                self.log_text.see(tk.END)
                
                lines = self.log_text.get("1.0", tk.END).split("\n")
                if len(lines) > 1000:
                    lines_to_delete = len(lines) - 1000
                    self.log_text.delete("1.0", f"{lines_to_delete + 1}.0")
                
                self.log_text.config(state=tk.DISABLED)
        except Exception as e:
            print(f"GUI日志输出失败: {str(e)}")
    

    
    def update_progress_display(self, current=None, total=None):
        if current is not None:
            self.translation_progress["current"] = current
        if total is not None:
            self.translation_progress["total"] = total
        
        self.root.after(0, self._update_log_frame_title)
    
    def _update_log_frame_title(self):
        base_title = self.get_ui_text("log")
        if self.translation_progress["total"] > 0:
            progress_text = f"({self.translation_progress['current']}/{self.translation_progress['total']})"
            title_with_progress = f"{base_title}{progress_text}"
        else:
            title_with_progress = base_title
        
        if hasattr(self, 'log_frame'):
            self.log_frame.config(text=title_with_progress)
    
    def update_translation_display(self, key: str, translated_text: str) -> None:
        try:
            if hasattr(self, 'gui_manager') and self.gui_manager:
                self.gui_manager.update_translation_display(key, translated_text)
        except Exception as e:
            self.log_message(self.get_ui_text("update_translation_display_failed").format(str(e)), "ERROR")
    
    
    
    def refresh_comparison_data(self):
        try:
            self.load_comparison_files()
            self.log_message(self.get_ui_text("comparison_data_refreshed"))
        except Exception as e:
            self.log_message(self.get_ui_text("refresh_comparison_data_failed").format(str(e)), "ERROR")
    
    def refresh_mod_list(self):
        self.file_manager.refresh_mod_list()
    
    def on_mod_change(self, event=None):
        self.file_manager.on_mod_change(event)
    
    def refresh_file_list(self):
        self.file_manager.refresh_file_list()
    
    def on_file_change(self, event=None):
        self.file_manager.on_file_change(event)
    
    def find_matching_original_file(self, translation_file_path, mod_name):
        original_dir = self.data_dir / "3Completei18n" / "Original"
        translation_dir = self.data_dir / "3Completei18n" / "Translation"
        
        mod_translation_dir = translation_dir / mod_name
        relative_path = translation_file_path.relative_to(mod_translation_dir)
        mod_original_dir = original_dir / mod_name
        
        direct_match = mod_original_dir / relative_path
        if direct_match.exists():
            return direct_match
        
        target_dir = mod_original_dir / relative_path.parent
        if target_dir.exists():
            json_files = list(target_dir.glob('*.json'))
            if json_files:
                default_file = target_dir / 'default.json'
                if default_file in json_files:
                    return default_file
                return json_files[0]
        
        return None
    
    
    def save_translation_files(self):
        self.file_manager.save_translation_files()
    
    
    
    

    
    def check_ollama_status(self):
        self.ollama_manager.check_server_status()
    
    def refresh_models(self):
        self.ollama_manager.refresh_models()
    
    def import_mods(self):
        self.file_manager.import_mods()
    
    def extract_mods(self):
        self.file_manager.extract_mods()
    
    def extract_i18n(self):
        self.file_manager.extract_i18n()
    
    def auto_translate(self):
        self.translation_manager.auto_translate()
    
    def start_translation(self):
        self.translation_manager.start_translation()
    
    def stop_translation(self):
        self.translation_manager.stop_translation()
    
    def reset_translation_state(self):
        self.translation_manager.reset_translation_state()
    

    

    
    def recompress_mods(self):
        self.file_manager.recompress_mods()
    
    def _async_initialize(self):
        self._show_window_centered()
        
        def initialize():
            try:
                self.root.after(0, self.log_message, self.get_ui_text("initializing_model"))
                
                if self.ollama_manager.check_server_status():
                    saved_model = self.config_manager.get_ollama_model()
                    self.ollama_model = saved_model if saved_model else "qwen2.5-coder:14b"
                    
                    self.ollama_translator = OllamaTranslator(
                        base_url=self.ollama_base_url,
                        model=self.ollama_model,
                        main_app=self
                    )
                    
                    self.root.after(0, self.log_message, self.get_ui_text("model_initialized").format(self.ollama_model))
                    
                    def load_models():
                        try:
                            models = self.ollama_manager.get_available_models()
                            if models:
                                self.available_models = models
                                if self.ollama_model not in models and models:
                                    self.ollama_model = models[0]
                                    self.config_manager.set_ollama_model(self.ollama_model)
                                    self.ollama_translator.model = self.ollama_model
                                self.root.after(0, self._update_models_ui, models)
                                self.root.after(0, self.log_message, self.get_ui_text("models_loaded").format(len(models)))
                            else:
                                self.root.after(0, self.log_message, self.get_ui_text("no_available_models"), "WARNING")
                        except Exception as e:
                            self.root.after(0, self.log_message, self.get_ui_text("model_loading_failed").format(str(e)), "WARNING")
                    
                    threading.Thread(target=load_models, daemon=True).start()
                else:
                    self.root.after(0, self.log_message, self.get_ui_text("ollama_not_installed"), "ERROR")
                
                self.root.after(100, self.refresh_mod_list)
                
            except Exception as e:
                self.root.after(0, self.log_message, f"初始化失败: {str(e)}", "ERROR")
        
        threading.Thread(target=initialize, daemon=True).start()
    
    def _update_models_ui(self, models):
        if hasattr(self, 'model_combo'):
            self.model_combo['values'] = models
            if models:
                if self.ollama_model and self.ollama_model in models:
                    self.ollama_model_var.set(self.ollama_model)
                else:
                    self.ollama_model_var.set(models[0])
                    self.ollama_model = models[0]
    
    def run(self):
        self.log_message(self.get_ui_text("app_started"))
        self.root.mainloop()


def main():
    app = StardewValleyTranslator()
    app.run()


if __name__ == "__main__":
    main()