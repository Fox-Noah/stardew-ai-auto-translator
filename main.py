#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星露谷物语mod i18n AI翻译工具
基于 Ollama 的自动翻译工具
"""

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

# 导入自定义模块
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
        self.root.withdraw()  # 先隐藏窗口，避免初始化时的闪烁
        self.root.title("星露谷物语mod i18n AI翻译工具")  # 临时标题，将在load_config后更新
        self.root.geometry("900x600")
        self.root.minsize(880, 500)
        
        # 设置窗口图标
        if getattr(sys, 'frozen', False):
            # 打包后的exe环境，图标已内嵌在exe中
            try:
                self.root.iconbitmap(default=sys.executable)
            except Exception as e:
                print(f"设置主窗口图标失败: {e}")
        else:
            # 开发环境
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
            if os.path.exists(icon_path):
                try:
                    self.root.iconbitmap(icon_path)
                except Exception as e:
                    print(f"设置主窗口图标失败: {e}")
        
        # 初始化文件管理器（负责统一管理所有目录路径）
        self.file_manager = FileManager(self)
        
        # 从文件管理器获取目录路径引用
        self.work_dir = self.file_manager.work_dir
        self.data_dir = self.file_manager.data_dir
        self.import_dir = self.file_manager.import_dir
        self.extract_dir = self.file_manager.extract_dir
        self.i18n_dir = self.file_manager.i18n_dir
        self.compress_dir = self.file_manager.compress_dir
        
        # 配置文件路径
        self.config_file = self.data_dir / "config.json"
        
        # Ollama 配置
        self.ollama_base_url = "http://localhost:11434"
        self.ollama_model = None  # 不再硬编码，启动时自动获取
        self.available_models = []
        
        # 初始化ollama翻译器（暂时不设置模型）
        self.ollama_translator = None
        
        # 初始化配置管理器
        self.config_manager = ConfigManager(self.config_file)
        
        # 初始化UI文本管理器
        self.ui_text_manager = UITextManager()
        
        # 初始化GUI管理器
        self.gui_manager = GUIManager(self)
        
        # 初始化样式管理器
        self.style_manager = style_manager
        
        # 初始化Ollama管理器（但不立即获取模型）
        self.ollama_manager = OllamaManager(self)
        
        # 设置translator属性指向ollama_manager的translator
        self.translator = self.ollama_manager.translator
        
        # 初始化翻译管理器
        self.translation_manager = TranslationManager(self)
        
        # 翻译状态
        self.is_translating = False
        self.translation_thread = None
        self.current_progress = 0
        self.total_progress = 0
        
        # 翻译进度相关变量
        self.translation_progress = {"current": 0, "total": 0}
        
        # mod选择相关
        self.available_mods = []
        self.current_mod_index = 0
        self.current_mod_path = None
        
        # 文件选择相关
        self.available_files = []
        self.current_file_index = 0
        
        # 翻译语言配置 - 仅包含官方支持的12种语言
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
        
        # 语言代码映射 - 对应官方支持的语言代码
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
        
        # UI文本字典 - 从ui_text_manager获取
        self.ui_texts = self.ui_text_manager.ui_texts
        
        # 当前UI语言
        self.current_ui_language = "中文"
        
        # 批处理大小和自动保存间隔
        self.batch_size = 5
        self.auto_save_interval = 20
        
        # 加载配置
        self.load_config()
        
        # GUI变量
        self.target_language_var = tk.StringVar(value=self.current_ui_language)
        self.ollama_model_var = tk.StringVar(value="")
        self.batch_size_var = tk.StringVar(value=str(self.batch_size))
        self.auto_save_interval_var = tk.StringVar(value=str(self.auto_save_interval))
        
        # 创建GUI
        self.create_gui()
        
        # 异步初始化Ollama和显示窗口
        self._async_initialize()
    
    def _show_window_centered(self):
        """将窗口居中显示"""
        # 更新窗口以获取准确的尺寸
        self.root.update_idletasks()
        
        # 获取窗口尺寸
        window_width = self.root.winfo_reqwidth()
        window_height = self.root.winfo_reqheight()
        
        # 如果窗口尺寸太小，使用默认尺寸
        if window_width < 900:
            window_width = 900
        if window_height < 600:
            window_height = 600
        
        # 获取屏幕尺寸
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 计算居中位置
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # 设置窗口位置和尺寸
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 显示窗口
        self.root.deiconify()
    
    def load_config(self):
        """加载配置文件"""
        config = self.config_manager.load_config()
        self.current_ui_language = config.get('ui_language', '中文')
        self.ui_text_manager.set_language(self.current_ui_language)
        self.ollama_model = config.get('ollama_model', 'qwen2.5:7b')
        self.batch_size = config.get('batch_size', 5)
        self.auto_save_interval = config.get('auto_save_interval', 20)
    
    def save_config(self):
        """保存配置文件"""
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
        """创建图形界面"""
        self.gui_manager.create_gui()
    
    def get_ui_text(self, key: str) -> str:
        """获取界面文本"""
        return self.ui_texts.get(self.current_ui_language, {}).get(key, key)
    
    def on_language_change(self, event=None):
        """语言切换回调"""
        selected_language = self.target_language_var.get()
        # 更新界面语言（优先使用选中的语言，如果界面文本不支持则保持当前语言）
        if selected_language in self.target_languages:
            self.current_ui_language = selected_language
            self.ui_text_manager.set_language(selected_language)
            self.update_ui_texts()
            self.save_config()  # 保存语言设置
    
    def update_ui_texts(self):
        """更新界面文本"""
        self.gui_manager.update_ui_texts()
    
    def log_message(self, message: str, level: str = "INFO"):
        """记录日志消息到控制台和GUI日志区域"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        
        # 输出到控制台
        print(log_entry)
        
        # 输出到GUI日志区域
        if hasattr(self, 'log_text'):
            self.root.after(0, self._append_log_to_gui, log_entry)
    
    def _append_log_to_gui(self, log_entry: str):
        """将日志条目添加到GUI日志区域"""
        try:
            if hasattr(self, 'log_text'):
                # 启用文本框编辑
                self.log_text.config(state=tk.NORMAL)
                
                # 添加日志条目（如果不是第一条日志，先添加换行）
                if self.log_text.get("1.0", tk.END).strip():
                    self.log_text.insert(tk.END, "\n")
                self.log_text.insert(tk.END, log_entry)
                
                # 自动滚动到底部
                self.log_text.see(tk.END)
                
                # 限制日志行数，保持最新的1000行
                lines = self.log_text.get("1.0", tk.END).split("\n")
                if len(lines) > 1000:
                    # 删除最旧的行
                    lines_to_delete = len(lines) - 1000
                    self.log_text.delete("1.0", f"{lines_to_delete + 1}.0")
                
                # 禁用文本框编辑
                self.log_text.config(state=tk.DISABLED)
        except Exception as e:
            # 如果GUI日志出错，至少保证控制台输出
            print(f"GUI日志输出失败: {str(e)}")
    

    
    def update_progress_display(self, current=None, total=None):
        """更新进度显示"""
        if current is not None:
            self.translation_progress["current"] = current
        if total is not None:
            self.translation_progress["total"] = total
        
        # 更新日志框架标题以显示进度
        self.root.after(0, self._update_log_frame_title)
    
    def _update_log_frame_title(self):
        """更新日志框架标题以显示进度"""
        base_title = self.get_ui_text("log")
        if self.translation_progress["total"] > 0:
            progress_text = f"({self.translation_progress['current']}/{self.translation_progress['total']})"
            title_with_progress = f"{base_title}{progress_text}"
        else:
            title_with_progress = base_title
        
        if hasattr(self, 'log_frame'):
            self.log_frame.config(text=title_with_progress)
    
    def update_translation_display(self, key: str, translated_text: str) -> None:
        """实时更新翻译显示
        
        Args:
            key: 翻译键
            translated_text: 翻译文本
        """
        try:
            if hasattr(self, 'gui_manager') and self.gui_manager:
                self.gui_manager.update_translation_display(key, translated_text)
        except Exception as e:
            self.log_message(self.get_ui_text("update_translation_display_failed").format(str(e)), "ERROR")
    
    # GUI事件处理方法已迁移到gui_manager.py
    
    # edit_translation_dialog方法已迁移到gui_manager.py
    
    # 文件处理方法已迁移到file_manager.py
    def refresh_comparison_data(self):
        """刷新加载文本"""
        try:
            self.load_comparison_files()
            self.log_message(self.get_ui_text("comparison_data_refreshed"))
        except Exception as e:
            self.log_message(self.get_ui_text("refresh_comparison_data_failed").format(str(e)), "ERROR")
    
    def refresh_mod_list(self):
        """刷新mod列表"""
        self.file_manager.refresh_mod_list()
    
    def on_mod_change(self, event=None):
        """mod选择变化处理"""
        self.file_manager.on_mod_change(event)
    
    def refresh_file_list(self):
        """刷新当前MOD的文件列表"""
        self.file_manager.refresh_file_list()
    
    def on_file_change(self, event=None):
        """文件选择变化处理"""
        self.file_manager.on_file_change(event)
    
    def find_matching_original_file(self, translation_file_path, mod_name):
        """智能匹配原文件，优先选择default.json"""
        original_dir = self.data_dir / "3Completei18n" / "Original"
        translation_dir = self.data_dir / "3Completei18n" / "Translation"
        
        # 计算相对路径
        mod_translation_dir = translation_dir / mod_name
        relative_path = translation_file_path.relative_to(mod_translation_dir)
        mod_original_dir = original_dir / mod_name
        
        # 1. 尝试直接匹配相同的相对路径
        direct_match = mod_original_dir / relative_path
        if direct_match.exists():
            return direct_match
        
        # 2. 在相同目录下查找JSON文件，优先选择default.json
        target_dir = mod_original_dir / relative_path.parent
        if target_dir.exists():
            json_files = list(target_dir.glob('*.json'))
            if json_files:
                # 优先选择default.json
                default_file = target_dir / 'default.json'
                if default_file in json_files:
                    return default_file
                # 如果没有default.json，选择第一个JSON文件
                return json_files[0]
        
        return None
    
    # load_json_with_comments和save_json_with_original_format方法已迁移到file_manager.py
    
    def save_translation_files(self):
        """保存翻译文件"""
        self.file_manager.save_translation_files()
    
    # show_settings_dialog方法已迁移到gui_manager.py
    
    # update_translation_display方法已迁移到translation_manager.py
    
    # load_comparison_files和display_comparison_data方法已迁移到file_manager.py
    

    
    # Ollama相关方法已迁移到ollama_manager.py
    def check_ollama_status(self):
        """检查 Ollama 服务器状态"""
        self.ollama_manager.check_server_status()
    
    def refresh_models(self):
        """刷新模型列表"""
        self.ollama_manager.refresh_models()
    
    # 文件处理方法已迁移到file_manager.py
    def import_mods(self):
        """导入 MOD 文件"""
        self.file_manager.import_mods()
    
    def extract_mods(self):
        """解压 MOD 文件"""
        self.file_manager.extract_mods()
    
    def extract_i18n(self):
        """提取 i18n 文件"""
        self.file_manager.extract_i18n()
    
    # 翻译相关方法已迁移到translation_manager.py
    def auto_translate(self):
        """自动翻译或停止翻译"""
        self.translation_manager.auto_translate()
    
    def start_translation(self):
        """开始翻译"""
        self.translation_manager.start_translation()
    
    def stop_translation(self):
        """停止翻译"""
        self.translation_manager.stop_translation()
    
    def reset_translation_state(self):
        """重置翻译状态"""
        self.translation_manager.reset_translation_state()
    

    

    
    # recompress_mods方法已迁移到file_manager.py
    def recompress_mods(self):
        """打包MOD MOD"""
        self.file_manager.recompress_mods()
    
    def _async_initialize(self):
        """异步初始化，避免阻塞UI"""
        # 立即显示窗口，不等待任何初始化
        self._show_window_centered()
        
        def initialize():
            try:
                # 显示正在初始化的提示
                self.root.after(0, self.log_message, self.get_ui_text("initializing_model"))
                
                # 先刷新mod列表
                self.root.after(0, self.refresh_mod_list)
                
                # 等待一小段时间确保MOD列表刷新完成
                time.sleep(0.1)
                
                # 然后检查Ollama服务状态
                if self.ollama_manager.check_server_status():
                    # 从配置文件读取保存的模型，如果没有则使用默认值
                    saved_model = self.config_manager.get_ollama_model()
                    self.ollama_model = saved_model if saved_model else "qwen2.5-coder:14b"
                    
                    # 立即初始化翻译器，不等待模型列表
                    self.ollama_translator = OllamaTranslator(
                        base_url=self.ollama_base_url,
                        model=self.ollama_model,
                        main_app=self
                    )
                    
                    # 在主线程中显示初始化完成
                    self.root.after(0, self.log_message, self.get_ui_text("model_initialized").format(self.ollama_model))
                    
                    # 立即获取模型列表
                    def load_models():
                        try:
                            models = self.ollama_manager.get_available_models()
                            if models:
                                self.available_models = models
                                # 验证当前模型是否在列表中
                                if self.ollama_model not in models and models:
                                    self.ollama_model = models[0]
                                    self.config_manager.set_ollama_model(self.ollama_model)
                                    self.ollama_translator.model = self.ollama_model
                                # 更新UI
                                self.root.after(0, self._update_models_ui, models)
                                self.root.after(0, self.log_message, self.get_ui_text("models_loaded").format(len(models)))
                            else:
                                self.root.after(0, self.log_message, self.get_ui_text("no_available_models"), "WARNING")
                        except Exception as e:
                            self.root.after(0, self.log_message, self.get_ui_text("model_loading_failed").format(str(e)), "WARNING")
                    
                    # 在后台线程中立即加载模型列表
                    threading.Thread(target=load_models, daemon=True).start()
                else:
                    self.root.after(0, self.log_message, self.get_ui_text("ollama_not_installed"), "ERROR")
                
            except Exception as e:
                self.root.after(0, self.log_message, f"初始化失败: {str(e)}", "ERROR")
        
        # 在后台线程中执行初始化
        threading.Thread(target=initialize, daemon=True).start()
    
    def _update_models_ui(self, models):
        """更新模型UI（在主线程中调用）"""
        if hasattr(self, 'model_combo'):
            self.model_combo['values'] = models
            if models:
                # 如果当前配置的模型在列表中，使用它；否则使用第一个
                if self.ollama_model and self.ollama_model in models:
                    self.ollama_model_var.set(self.ollama_model)
                else:
                    self.ollama_model_var.set(models[0])
                    self.ollama_model = models[0]
    
    def run(self):
        """运行应用程序"""
        self.log_message(self.get_ui_text("app_started"))
        self.root.mainloop()


def main():
    """主函数"""
    app = StardewValleyTranslator()
    app.run()


if __name__ == "__main__":
    main()