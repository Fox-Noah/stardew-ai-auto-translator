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
    """GUI界面管理类"""
    
    def __init__(self, parent):
        """初始化GUI管理器"""
        self.parent = parent
        self.root = parent.root
        self.widgets = {}
        self.callbacks = {}
        
        # 翻译进度相关变量
        self.translation_progress = {"current": 0, "total": 0}
        
        # 当前选中的索引
        self.current_selected_index = 0
        
        # 存储所有下拉菜单组件的引用
        self.comboboxes = []
        
        # 绑定全局点击事件来处理下拉菜单取消选中
        self.root.bind('<Button-1>', self._on_global_click, add='+')
        
    def set_callbacks(self, callbacks: Dict[str, Callable]) -> None:
        """设置回调函数
        
        Args:
            callbacks: 回调函数字典
        """
        self.callbacks = callbacks
    
    def _on_global_click(self, event):
        """全局点击事件处理器，用于取消下拉菜单选中状态"""
        try:
            clicked_widget = event.widget
            
            # 检查是否点击了翻译列表框，如果是则不处理
            if hasattr(self.parent, 'translation_listbox') and clicked_widget == self.parent.translation_listbox:
                return
            
            # 检查是否点击了任何下拉菜单
            is_combo_click = False
            for combo in self.comboboxes:
                if combo and combo.winfo_exists() and clicked_widget == combo:
                    is_combo_click = True
                    break
            
            # 如果不是点击下拉菜单本身，延迟一点时间后关闭下拉菜单
            # 这样可以让下拉菜单有时间正常展开
            if not is_combo_click:
                self.root.after(100, self._close_all_combos)
        except Exception as e:
            # 静默处理异常，避免影响正常功能
            pass
    
    def _close_all_combos(self):
        """关闭所有下拉菜单并取消选中状态"""
        try:
            for combo in self.comboboxes:
                if combo and combo.winfo_exists():
                    try:
                        # 关闭下拉菜单
                        combo.event_generate('<Escape>')
                        # 取消选中状态，移除焦点
                        combo.selection_clear()
                        # 将焦点转移到主窗口
                        self.root.focus_set()
                    except:
                        pass
        except:
            pass
    
    def _is_child_of(self, widget, parent):
        """检查widget是否是parent的子组件"""
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
        """原文列表选择事件"""
        try:
            selection = self.parent.original_listbox.curselection()
            if selection:
                index = selection[0]
                # 记录当前选中的索引
                self.current_selected_index = index
        except Exception as e:
            self.parent.log_message(f"原文选择错误: {str(e)}")

    def on_translation_select(self, event):
        """译文列表选择事件"""
        try:
            selection = self.parent.translation_listbox.curselection()
            if selection:
                index = selection[0]
                # 同步选择原文列表框的相同项目
                self.parent.original_listbox.selection_clear(0, tk.END)
                self.parent.original_listbox.selection_set(index)
                self.parent.original_listbox.see(index)
        except Exception as e:
            self.parent.log_message(f"译文选择事件处理失败：{str(e)}")
    
    def on_shared_scrollbar(self, *args):
        """共用垂直滚动条操作回调"""
        # 同时滚动原文列表框和译文列表框
        self.parent.original_listbox.yview(*args)
        self.parent.translation_listbox.yview(*args)
    
    def on_shared_h_scrollbar(self, *args):
        """共用水平滚动条操作回调"""
        # 同时水平滚动原文列表框和译文列表框
        self.parent.original_listbox.xview(*args)
        self.parent.translation_listbox.xview(*args)
    
    def on_original_h_scroll(self, *args):
        """原文水平滚动回调"""
        # 更新原文滚动条
        self.parent.original_h_scrollbar.set(*args)
        # 同步译文滚动条
        self.parent.translation_h_scrollbar.set(*args)
    
    def on_translation_h_scroll(self, *args):
        """译文水平滚动回调"""
        # 更新译文滚动条
        self.parent.translation_h_scrollbar.set(*args)
        # 同步原文滚动条
        self.parent.original_h_scrollbar.set(*args)
    
    def on_mouse_wheel(self, event):
        """鼠标滚轮事件处理"""
        # 计算滚动量
        if event.delta:
            # Windows系统
            delta = -1 * (event.delta / 120)
        else:
            # Linux系统
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            else:
                return "break"  # 阻止默认行为
        
        # 获取当前滚动位置
        current_top, current_bottom = self.parent.original_listbox.yview()
        
        # 计算新的滚动位置
        # 获取列表框总行数
        total_items = self.parent.original_listbox.size()
        if total_items == 0:
            return "break"  # 阻止默认行为
        
        # 计算每个单位的滚动比例
        scroll_unit = 1.0 / total_items
        new_position = current_top + (delta * scroll_unit * 3)  # 乘以3增加滚动速度
        
        # 限制滚动范围
        new_position = max(0.0, min(1.0, new_position))
        
        # 手动同步滚动两个框
        self.parent.original_listbox.yview_moveto(new_position)
        self.parent.translation_listbox.yview_moveto(new_position)
        
        # 同步更新共用滚动条位置
        self.parent.shared_scrollbar.set(new_position, new_position + (current_bottom - current_top))
        
        return "break"  # 阻止默认滚动行为

    def on_combobox_mousewheel(self, event):
        """下拉菜单框滚轮事件处理 - 阻止滚轮选择"""
        return "break"  # 阻止默认滚轮行为

    def on_translation_double_click(self, event):
        """译文双击编辑事件"""
        try:
            # 从事件中获取点击位置的索引
            index = self.parent.translation_listbox.nearest(event.y)
            
            # 检查索引是否有效
            if index < 0 or index >= self.parent.translation_listbox.size():
                return
            
            # 选中该条目
            self.parent.translation_listbox.selection_clear(0, tk.END)
            self.parent.translation_listbox.selection_set(index)
            self.parent.translation_listbox.activate(index)
            
            current_translation = self.parent.translation_listbox.get(index)
            
            # 获取对应的原文
            original_text = ""
            if hasattr(self.parent, 'current_translation_keys') and index < len(self.parent.current_translation_keys):
                key = self.parent.current_translation_keys[index]
                if hasattr(self.parent, 'current_original_data') and key in self.parent.current_original_data:
                    original_text = self.parent.current_original_data[key]
            
            self.edit_translation_dialog(index, original_text, current_translation)
            
        except Exception as e:
            self.parent.log_message(f"译文编辑失败：{str(e)}", "ERROR")
    

    

        
    def create_gui(self):
        """创建图形界面"""
        # 主框架 - 使用现代化框架
        main_frame = ModernFrame(self.root, padding=8)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 标题 - 使用现代化标签
        self.parent.title_label = ModernLabel(main_frame, text=self.parent.get_ui_text("title"), 
                                    font=style_manager.get_font('title'),
                                    style="title")
        self.parent.title_label.pack(fill=tk.X, pady=(0, 12))
        
        # 配置区域 - 使用现代化框架
        self.parent.config_frame = ModernFrame(main_frame, text=self.parent.get_ui_text("config"), 
                                              padding=8, style="card")
        self.parent.config_frame.pack(fill=tk.X, pady=(0, 8))
        
        # 配置内容容器 - 水平排列
        config_content = ModernFrame(self.parent.config_frame, style="default")
        config_content.pack(fill=tk.X, expand=True)
        
        # 目标语言选择
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
        # 添加到下拉菜单列表中
        self.comboboxes.append(language_combo)
        
        # Ollama 模型选择
        self.parent.model_label = ModernLabel(config_content, 
                                             text=self.parent.get_ui_text("translation_model"),
                                             style="label")
        self.parent.model_label.pack(side=tk.LEFT, padx=(0, 8))
        self.parent.model_combo = ttk.Combobox(config_content, textvariable=self.parent.ollama_model_var,
                                       state="readonly", width=20, font=style_manager.get_font('default'))
        self.parent.model_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.parent.model_combo.bind('<MouseWheel>', self.on_combobox_mousewheel)
        # 添加到下拉菜单列表中
        self.comboboxes.append(self.parent.model_combo)
        
        # 刷新模型按钮
        self.parent.refresh_models_btn = ModernButton(config_content, 
                                                     text=self.parent.get_ui_text("refresh_models"),
                                                     command=self.parent.refresh_models,
                                                     style="secondary")
        self.parent.refresh_models_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # 设置按钮
        self.parent.settings_btn = ModernButton(config_content, 
                                               text=self.parent.get_ui_text("settings_dialog"),
                                               command=self.show_settings_dialog,
                                               style="primary")
        self.parent.settings_btn.pack(side=tk.LEFT)
        
        # 功能按钮区域 - 使用现代化框架
        self.parent.buttons_frame = ModernFrame(main_frame, text=self.parent.get_ui_text("functions"), 
                                               padding=8, style="card")
        self.parent.buttons_frame.pack(fill=tk.X, pady=(0, 8))
        
        # 按钮容器 - 水平排列
        buttons_content = ModernFrame(self.parent.buttons_frame.get_content_frame(), style="default")
        buttons_content.pack(fill=tk.X, expand=True)
        
        # 按钮样式配置
        button_padx = 8
        
        # 导入 MOD 按钮
        self.parent.import_btn = ModernButton(buttons_content, 
                                            text=self.parent.get_ui_text("import_mod"),
                                            command=self.parent.import_mods,
                                            style="primary")
        self.parent.import_btn.pack(side=tk.LEFT, padx=(0, button_padx), fill=tk.X, expand=True)
        
        # 解压 MOD 按钮
        self.parent.extract_btn = ModernButton(buttons_content, 
                                             text=self.parent.get_ui_text("extract_mod"),
                                             command=self.parent.extract_mods,
                                             style="secondary")
        self.parent.extract_btn.pack(side=tk.LEFT, padx=(0, button_padx), fill=tk.X, expand=True)
        
        # 提取 i18n 按钮
        self.parent.extract_i18n_btn = ModernButton(buttons_content, 
                                                  text=self.parent.get_ui_text("extract_i18n"),
                                                  command=self.parent.extract_i18n,
                                                  style="info")
        self.parent.extract_i18n_btn.pack(side=tk.LEFT, padx=(0, button_padx), fill=tk.X, expand=True)
        
        # 自动翻译按钮
        self.parent.translate_btn = ModernButton(buttons_content, 
                                               text=self.parent.get_ui_text("auto_translate"),
                                               command=self.parent.auto_translate,
                                               style="success")
        self.parent.translate_btn.pack(side=tk.LEFT, padx=(0, button_padx), fill=tk.X, expand=True)
        
        # 打包MOD按钮
        self.parent.compress_btn = ModernButton(buttons_content, 
                                              text=self.parent.get_ui_text("recompress"),
                                              command=self.parent.recompress_mods,
                                              style="warning")
        self.parent.compress_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 创建文本对比区域
        self._create_comparison_section(main_frame)
        
        # 创建日志区域
        self._create_log_section(main_frame)
        

    
    def _create_comparison_section(self, parent: ModernFrame) -> None:
        """创建文本对比区域"""
        # 文本对比区域 - 使用现代化框架
        self.parent.compare_frame = ModernFrame(parent, text=self.parent.get_ui_text("text_comparison"), 
                                               padding=8, style="card")
        self.parent.compare_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        # 文本对比顶部MOD选择区域
        mod_selection_frame = ModernFrame(self.parent.compare_frame.get_content_frame(), style="section")
        mod_selection_frame.pack(fill=tk.X, pady=(0, 8))
        
        # 第一行容器：MOD选择
        mod_row1 = ModernFrame(mod_selection_frame, style="default")
        mod_row1.pack(fill=tk.X, pady=(0, 6))
        
        # MOD选择控件
        self.parent.mod_label = ModernLabel(mod_row1, 
                                           text=self.parent.get_ui_text("select_mod"),
                                           style="label")
        self.parent.mod_label.pack(side=tk.LEFT, padx=(0, 8))
        self.parent.mod_combo = ttk.Combobox(mod_row1, state="readonly", width=40,
                                            font=("Microsoft YaHei UI", 9))
        self.parent.mod_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.parent.mod_combo.bind('<<ComboboxSelected>>', self.parent.on_mod_change)
        self.parent.mod_combo.bind('<MouseWheel>', self.on_combobox_mousewheel)
        # 添加到下拉菜单列表中
        self.comboboxes.append(self.parent.mod_combo)
        
        # 刷新MOD列表按钮
        self.parent.refresh_mods_btn = ModernButton(mod_row1, 
                                                   text=self.parent.get_ui_text("refresh_mod_list"),
                                                   command=self.parent.refresh_mod_list,
                                                   style="secondary")
        self.parent.refresh_mods_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # 保存翻译按钮
        self.parent.save_translation_btn = ModernButton(mod_row1, 
                                                       text=self.parent.get_ui_text("save_translation"), 
                                                       command=self.parent.save_translation_files,
                                                       style="success")
        self.parent.save_translation_btn.pack(side=tk.LEFT)
        
        # 第二行容器：文件选择
        mod_row2 = ModernFrame(mod_selection_frame, style="default")
        mod_row2.pack(side=tk.LEFT, padx=(0, 8))
        
        # 清空目录按钮 - 放在第二行右边
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
        # 添加到下拉菜单列表中
        self.comboboxes.append(self.parent.file_combo)
        
        # 创建均等分布的容器框架
        container_frame = ModernFrame(self.parent.compare_frame.get_content_frame(), style="container")
        container_frame.pack(fill=tk.BOTH, expand=True)
        container_frame.columnconfigure(0, weight=1)  # 左侧列权重1
        container_frame.columnconfigure(1, weight=1)  # 右侧列权重1
        container_frame.columnconfigure(2, weight=0)  # 滚动条列权重0（固定宽度）
        container_frame.rowconfigure(0, weight=1)  # 设置行权重确保垂直拉伸
        
        # 左侧原文框架 - 使用现代化框架
        self.parent.left_frame = ModernFrame(container_frame, 
                                            text=self.parent.get_ui_text("original_text"), 
                                            padding=6, style="text_area")
        self.parent.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        
        # 右侧译文框架 - 使用现代化框架
        self.parent.right_frame = ModernFrame(container_frame, 
                                             text=self.parent.get_ui_text("translation_text"), 
                                             padding=6, style="text_area")
        self.parent.right_frame.grid(row=0, column=1, sticky="nsew", padx=(3, 0))
        
        # 原文列表框和滚动条
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
        
        # 原文横向滚动条
        self.parent.original_h_scrollbar = ttk.Scrollbar(self.parent.left_frame.get_content_frame(), orient=tk.HORIZONTAL)
        self.parent.original_h_scrollbar.pack(fill=tk.X, padx=2, pady=(0, 2))
        self.parent.original_listbox.config(xscrollcommand=self.on_original_h_scroll)
        self.parent.original_h_scrollbar.config(command=self.on_shared_h_scrollbar)
        
        # 译文列表框和滚动条
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
        
        # 译文横向滚动条
        self.parent.translation_h_scrollbar = ttk.Scrollbar(self.parent.right_frame.get_content_frame(), orient=tk.HORIZONTAL)
        self.parent.translation_h_scrollbar.pack(fill=tk.X, padx=2, pady=(0, 2))
        self.parent.translation_listbox.config(xscrollcommand=self.on_translation_h_scroll)
        self.parent.translation_h_scrollbar.config(command=self.on_shared_h_scrollbar)
        
        # 共享垂直滚动条
        self.parent.shared_scrollbar = ttk.Scrollbar(container_frame, orient=tk.VERTICAL)
        self.parent.shared_scrollbar.grid(row=0, column=2, sticky="ns", padx=(2, 0))
        
        # 绑定垂直滚动条
        self.parent.shared_scrollbar.config(command=self.on_shared_scrollbar)
        self.parent.original_listbox.config(yscrollcommand=self.parent.shared_scrollbar.set)
        self.parent.translation_listbox.config(yscrollcommand=self.parent.shared_scrollbar.set)
        
        # 绑定事件
        self.parent.original_listbox.bind('<<ListboxSelect>>', self.on_original_select)
        self.parent.translation_listbox.bind('<<ListboxSelect>>', self.on_translation_select)
        self.parent.original_listbox.bind('<MouseWheel>', self.on_mouse_wheel)
        self.parent.translation_listbox.bind('<MouseWheel>', self.on_mouse_wheel)
        # 绑定双击编辑事件
        self.parent.translation_listbox.bind('<Double-Button-1>', self.on_translation_double_click)
        
        # 配置网格权重
        self.parent.left_frame.columnconfigure(0, weight=1)
        self.parent.left_frame.rowconfigure(0, weight=1)
        self.parent.right_frame.columnconfigure(0, weight=1)
        self.parent.right_frame.rowconfigure(0, weight=1)
        self.parent.compare_frame.columnconfigure(0, weight=1)
        self.parent.compare_frame.rowconfigure(1, weight=1)
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)
        parent.columnconfigure(2, weight=0)
        parent.rowconfigure(3, weight=1)
        

        
        # 应用主题
        if hasattr(self.parent, 'style_manager'):
            self.parent.style_manager.apply_theme_to_root(self.parent.root)
            self.parent.style_manager.update_widget_styles(self.parent)
        
        # 版本标识 - 右下角显示
        self.parent.version_label = tk.Label(
            self.root,
            text="v1.2",
            font=("Microsoft YaHei UI", 8),
            fg="#666666",
            relief="flat",
            borderwidth=0
        )
        self.parent.version_label.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-0)
        
        # 显示窗口
        self.parent._show_window_centered()
    
    def _create_log_section(self, parent: ModernFrame) -> None:
        """创建日志区域"""
        # 日志区域 - 创建容器框架用于布局
        self.parent.log_frame = tk.LabelFrame(parent, text="日志", bg=parent.cget('bg'))
        self.parent.log_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 8))
        
        # 日志文本框
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
        
        # 日志垂直滚动条
        self.parent.log_scrollbar = ttk.Scrollbar(self.parent.log_frame, orient=tk.VERTICAL)
        self.parent.log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定滚动条
        self.parent.log_text.config(yscrollcommand=self.parent.log_scrollbar.set)
        self.parent.log_scrollbar.config(command=self.parent.log_text.yview)
        
        # 绑定鼠标滚轮事件
        self.parent.log_text.bind('<MouseWheel>', self.on_log_mouse_wheel)
    
    def on_log_mouse_wheel(self, event):
        """日志区域鼠标滚轮事件处理"""
        # 计算滚动量
        if event.delta:
            # Windows系统
            delta = -1 * (event.delta / 120)
        else:
            # Linux系统
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            else:
                return "break"
        
        # 滚动日志文本框
        self.parent.log_text.yview_scroll(int(delta), "units")
        return "break"
    
    def update_ui_texts(self) -> None:
        """更新界面文本"""
        # 更新窗口标题
        self.root.title(self.parent.get_ui_text("title"))
        
        # 更新顶部标题标签
        if hasattr(self.parent, 'title_label'):
            self.parent.title_label.config(text=self.parent.get_ui_text("title"))
        
        # 更新标签文本
        if hasattr(self.parent, 'config_frame'):
            self.parent.config_frame.update_text(self.parent.get_ui_text("config"))
        if hasattr(self.parent, 'target_lang_label'):
            self.parent.target_lang_label.config(text=self.parent.get_ui_text("target_language"))
        if hasattr(self.parent, 'model_label'):
            self.parent.model_label.config(text=self.parent.get_ui_text("translation_model"))
        
        # 更新刷新模型按钮文本
        if hasattr(self.parent, 'refresh_models_btn'):
            self.parent.refresh_models_btn.config(text=self.parent.get_ui_text("refresh_models"))
        
        # 更新功能按钮区域
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
        
        # 更新文本对比区域标题
        if hasattr(self.parent, 'compare_frame'):
            self.parent.compare_frame.update_text(self.parent.get_ui_text("text_comparison"))
        
        # 更新文本对比区域内部框架标题
        if hasattr(self.parent, 'left_frame'):
            self.parent.left_frame.update_text(self.parent.get_ui_text("original_text"))
        if hasattr(self.parent, 'right_frame'):
            self.parent.right_frame.update_text(self.parent.get_ui_text("translation_text"))
        
        # 更新MOD选择区域的控件文本
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
        
        # 更新设置按钮文本
        if hasattr(self.parent, 'settings_btn'):
            self.parent.settings_btn.config(text=self.parent.get_ui_text("settings_dialog"))
    
    def show_window_centered(self) -> None:
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
    
    def update_translate_button_text(self, is_translating: bool) -> None:
        """更新翻译按钮文本
        
        Args:
            is_translating: 是否正在翻译
        """
        if hasattr(self.parent, 'translate_btn'):
            if is_translating:
                self.parent.translate_btn.config(text=self.parent.get_ui_text("stop_translate"))
            else:
                self.parent.translate_btn.config(text=self.parent.get_ui_text("auto_translate"))
    
    def set_widget_state(self, widget_name: str, state: str) -> None:
        """设置控件状态
        
        Args:
            widget_name: 控件名称
            state: 状态（normal, disabled等）
        """
        if hasattr(self.parent, widget_name):
            widget = getattr(self.parent, widget_name)
            if hasattr(widget, 'config'):
                widget.config(state=state)
    
    def update_translation_display(self, key: str, translated_text: str) -> None:
        """实时更新翻译显示
        
        Args:
            key: 翻译键
            translated_text: 翻译文本
        """
        try:
            if hasattr(self.parent, 'current_translation_keys') and key in self.parent.current_translation_keys:
                index = self.parent.current_translation_keys.index(key)
                if index < self.parent.translation_listbox.size():
                    self.parent.translation_listbox.delete(index)
                    self.parent.translation_listbox.insert(index, translated_text)
                    # 更新当前翻译数据
                    if hasattr(self.parent, 'current_translation_data'):
                        self.parent.current_translation_data[key] = translated_text
        except Exception as e:
            self.parent.log_message(self.parent.get_ui_text("update_translation_display_failed").format(str(e)), "ERROR")
    
    def get_ui_text(self, key: str) -> str:
        """获取界面文本"""
        return self.parent.ui_text_manager.get_text(key)
    
    def on_language_change(self, event=None):
        """语言切换回调"""
        selected_language = self.parent.target_language_var.get()
        # 更新界面语言（优先使用选中的语言，如果界面文本不支持则保持当前语言）
        if selected_language in self.parent.ui_text_manager.get_available_languages():
            self.parent.current_ui_language = selected_language
            self.parent.ui_text_manager.set_language(selected_language)
            self.update_ui_texts()
            self.parent.save_config()  # 保存语言设置
    
    def log_message(self, message: str, level: str = "INFO"):
        """记录日志消息到控制台"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        
        # 输出到控制台
        print(log_entry)
    
    def update_progress_display(self, current=None, total=None):
        """更新进度显示"""
        if current is not None:
            self.parent.translation_progress["current"] = current
        if total is not None:
            self.parent.translation_progress["total"] = total
        
        # 更新日志框架标题以显示进度
        self.root.after(0, self._update_log_frame_title)
    
    def _update_log_frame_title(self):
        """更新日志框架标题以显示进度"""
        base_title = self.parent.get_ui_text("log")
        if self.parent.translation_progress["total"] > 0:
            progress_text = f"({self.parent.translation_progress['current']}/{self.parent.translation_progress['total']})"
            title_with_progress = f"{base_title}{progress_text}"
        else:
            title_with_progress = base_title
        
        if hasattr(self.parent, 'log_frame'):
            self.parent.log_frame.config(text=title_with_progress)
    
    def on_original_select(self, event):
        """原文列表选择事件"""
        try:
            selection = self.parent.original_listbox.curselection()
            if selection:
                index = selection[0]
                # 记录当前选中的索引
                self.parent.current_selected_index = index
        except Exception as e:
            self.parent.log_message(f"原文选择错误: {str(e)}")

    def on_translation_select(self, event):
        """译文列表选择事件"""
        try:
            selection = self.parent.translation_listbox.curselection()
            if selection:
                index = selection[0]
                # 同步选择原文列表框的相同项目
                self.parent.original_listbox.selection_clear(0, tk.END)
                self.parent.original_listbox.selection_set(index)
                self.parent.original_listbox.see(index)
        except Exception as e:
            self.parent.log_message(f"译文选择事件处理失败：{str(e)}")
    
    def on_shared_scrollbar(self, *args):
        """共用垂直滚动条操作回调"""
        # 同时滚动原文列表框和译文列表框
        self.parent.original_listbox.yview(*args)
        self.parent.translation_listbox.yview(*args)
    
    def on_shared_h_scrollbar(self, *args):
        """共用水平滚动条操作回调"""
        # 同时水平滚动原文列表框和译文列表框
        self.parent.original_listbox.xview(*args)
        self.parent.translation_listbox.xview(*args)
    
    def on_original_h_scroll(self, *args):
        """原文水平滚动回调"""
        # 更新原文滚动条
        self.parent.original_h_scrollbar.set(*args)
        # 同步译文滚动条
        self.parent.translation_h_scrollbar.set(*args)
    
    def on_translation_h_scroll(self, *args):
        """译文水平滚动回调"""
        # 更新译文滚动条
        self.parent.translation_h_scrollbar.set(*args)
        # 同步原文滚动条
        self.parent.original_h_scrollbar.set(*args)
    
    def on_mouse_wheel(self, event):
        """鼠标滚轮事件处理"""
        # 计算滚动量
        if event.delta:
            # Windows系统
            delta = -1 * (event.delta / 120)
        else:
            # Linux系统
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            else:
                return "break"  # 阻止默认行为
        
        # 获取当前滚动位置
        current_top, current_bottom = self.parent.original_listbox.yview()
        
        # 计算新的滚动位置
        # 获取列表框总行数
        total_items = self.parent.original_listbox.size()
        if total_items == 0:
            return "break"  # 阻止默认行为
        
        # 计算每个单位的滚动比例
        scroll_unit = 1.0 / total_items
        new_position = current_top + (delta * scroll_unit * 3)  # 乘以3增加滚动速度
        
        # 限制滚动范围
        new_position = max(0.0, min(1.0, new_position))
        
        # 手动同步滚动两个框
        self.parent.original_listbox.yview_moveto(new_position)
        self.parent.translation_listbox.yview_moveto(new_position)
        
        # 同步更新共用滚动条位置
        self.parent.shared_scrollbar.set(new_position, new_position + (current_bottom - current_top))
        
        return "break"  # 阻止默认滚动行为

    def on_combobox_mousewheel(self, event):
        """下拉菜单框滚轮事件处理 - 阻止滚轮选择"""
        return "break"  # 阻止默认滚轮行为

    def on_translation_double_click(self, event):
        """译文双击编辑事件"""
        try:
            # 从事件中获取点击位置的索引
            index = self.parent.translation_listbox.nearest(event.y)
            
            # 检查索引是否有效
            if index < 0 or index >= self.parent.translation_listbox.size():
                return
            
            # 选中该条目
            self.parent.translation_listbox.selection_clear(0, tk.END)
            self.parent.translation_listbox.selection_set(index)
            self.parent.translation_listbox.activate(index)
            
            current_translation = self.parent.translation_listbox.get(index)
            
            # 获取对应的原文
            original_text = ""
            if hasattr(self.parent, 'current_translation_keys') and index < len(self.parent.current_translation_keys):
                key = self.parent.current_translation_keys[index]
                if hasattr(self.parent, 'current_original_data') and key in self.parent.current_original_data:
                    original_text = self.parent.current_original_data[key]
            
            self.edit_translation_dialog(index, original_text, current_translation)
            
        except Exception as e:
            self.parent.log_message(f"译文编辑失败：{str(e)}", "ERROR")
    
    def edit_translation_dialog(self, index, original_text, current_translation):
        """显示翻译编辑对话框"""
        # 创建自定义对话框，但先不显示
        dialog = tk.Toplevel(self.root)
        dialog.title(self.parent.get_ui_text("edit_translation_dialog"))
        dialog.resizable(True, True)
        dialog.transient(self.root)
        
        # 先隐藏窗口，等组件初始化完成后再显示
        dialog.withdraw()
        
        # 设置对话框图标
        if getattr(sys, 'frozen', False):
            # 打包后的exe环境，使用内嵌图标
            try:
                dialog.iconbitmap(default=sys.executable)
            except Exception as e:
                print(f"设置编辑对话框图标失败: {e}")
        else:
            # 开发环境
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
            if os.path.exists(icon_path):
                try:
                    dialog.iconbitmap(icon_path)
                except Exception as e:
                    print(f"设置编辑对话框图标失败: {e}")
        
        # 创建主容器框架
        main_container = ModernFrame(dialog, style="container")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 配置主容器的网格权重，确保5:5布局
        main_container.grid_rowconfigure(0, weight=1)  # 原文区域权重1
        main_container.grid_rowconfigure(1, weight=1)  # 翻译区域权重1
        main_container.grid_rowconfigure(2, weight=0)  # 按钮区域权重0（固定高度）
        main_container.grid_columnconfigure(0, weight=1)
        
        # 原文显示框架 - 占用50%高度
        original_frame = ModernFrame(main_container, text=self.parent.get_ui_text("original_text"), style="section", padding=5)
        original_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        # 原文文本框架（包含滚动条）
        original_text_frame = ModernFrame(original_frame.get_content_frame(), style="default")
        original_text_frame.pack(fill=tk.BOTH, expand=True)
        
        original_text_widget = tk.Text(original_text_frame, wrap=tk.WORD, state='disabled',
                                      height=8,
                                      font=("Microsoft YaHei UI", 9),
                                      bg="#f8f9fa", fg="#495057",
                                      selectbackground="#e9ecef",
                                      selectforeground="#495057")
        original_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 原文滚动条
        original_scrollbar = ttk.Scrollbar(original_text_frame, orient=tk.VERTICAL, command=original_text_widget.yview)
        original_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        original_text_widget.config(yscrollcommand=original_scrollbar.set)
        
        # 插入原文内容
        original_text_widget.config(state='normal')
        original_text_widget.insert(1.0, original_text)
        original_text_widget.config(state='disabled')
        
        # 翻译编辑框架 - 占用50%高度
        translation_frame = ModernFrame(main_container, text=self.parent.get_ui_text("translation"), style="section", padding=5)
        translation_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        
        # 翻译文本框架（包含滚动条）
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
        
        # 翻译滚动条
        translation_scrollbar = ttk.Scrollbar(translation_text_frame, orient=tk.VERTICAL, command=translation_text_widget.yview)
        translation_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        translation_text_widget.config(yscrollcommand=translation_scrollbar.set)
        
        # 插入翻译内容
        translation_text_widget.insert(1.0, current_translation)
        
        # 按钮区域
        button_frame = ModernFrame(main_container, style="default", padding=5)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(0, 0))
        
        def save_edit():
            """保存编辑"""
            try:
                new_text = translation_text_widget.get(1.0, tk.END).strip()
                
                # 更新列表框显示
                self.parent.translation_listbox.delete(index)
                self.parent.translation_listbox.insert(index, new_text)
                self.parent.translation_listbox.selection_set(index)
                
                # 更新当前翻译数据
                if hasattr(self.parent, 'current_translation_keys') and index < len(self.parent.current_translation_keys):
                    key = self.parent.current_translation_keys[index]
                    if hasattr(self.parent, 'current_translation_data'):
                        self.parent.current_translation_data[key] = new_text
                
                self.parent.log_message(self.parent.get_ui_text("translation_updated"))
                dialog.destroy()
            except Exception as e:
                self.parent.log_message(self.parent.get_ui_text("save_translation_failed").format(str(e)), "ERROR")
        
        def cancel_edit():
            """取消编辑"""
            dialog.destroy()
        
        # 创建现代化按钮
        cancel_btn = ModernButton(button_frame, text=self.parent.get_ui_text("cancel"), 
                                 command=cancel_edit, style="secondary")
        cancel_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        
        save_btn = ModernButton(button_frame, text=self.parent.get_ui_text("save"), 
                               command=save_edit, style="primary")
        save_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 所有组件创建完成后，显示对话框
        def show_dialog():
            """在所有组件初始化完成后显示对话框"""
            # 更新窗口以确保所有组件都已渲染
            dialog.update_idletasks()
            
            # 设置窗口自适应大小和居中显示
            dialog.geometry("")  # 清除固定尺寸，让窗口自适应
            dialog.update_idletasks()
            
            # 设置最小宽度和高度，让窗口自适应
            min_width = 800
            min_height = 600
            req_width = max(min_width, dialog.winfo_reqwidth())
            req_height = max(min_height, dialog.winfo_reqheight())
            
            # 居中显示
            x = (dialog.winfo_screenwidth() // 2) - (req_width // 2)
            y = (dialog.winfo_screenheight() // 2) - (req_height // 2)
            dialog.geometry(f"{req_width}x{req_height}+{x}+{y}")
            
            # 显示窗口并获取焦点
            dialog.deiconify()
            dialog.grab_set()
            dialog.lift()
            dialog.focus_force()
            
            # 设置文本框焦点
            translation_text_widget.focus_set()
        
        # 延迟显示对话框，确保所有组件都已完全初始化
        dialog.after(50, show_dialog)
    
    def refresh_mod_list(self):
        """刷新mod列表"""
        try:
            self.parent.available_mods = []
            
            # 获取i18n目录
            i18n_dir = self.parent.i18n_dir
            original_dir = i18n_dir / "Original"
            
            if not original_dir.exists():
                self.parent.log_message("Original目录不存在，请先提取i18n文件")
                return
            
            # 查找所有mod目录（包含JSON文件的目录）
            for mod_path in original_dir.iterdir():
                if mod_path.is_dir():
                    # 检查是否包含JSON文件
                    json_files = list(mod_path.rglob("*.json"))
                    if json_files:
                        self.parent.available_mods.append({
                            'name': mod_path.name,
                            'path': mod_path,
                            'files': json_files
                        })
            
            # 更新下拉框
            mod_names = [mod['name'] for mod in self.parent.available_mods]
            self.parent.mod_combo['values'] = mod_names
            
            if mod_names:
                if self.parent.current_mod_index < len(mod_names):
                    self.parent.mod_combo.current(self.parent.current_mod_index)
                else:
                    self.parent.mod_combo.current(0)
                    self.parent.current_mod_index = 0
                self.parent.log_message(self.parent.get_ui_text("found_mods").format(len(mod_names), ', '.join(mod_names)))
                # 自动加载当前选择的MOD文本
                self.parent.on_mod_change()
            else:
                self.parent.mod_combo.set("")
                self.parent.log_message(self.parent.get_ui_text("no_mods_found"))
                
        except Exception as e:
            self.parent.log_message(self.parent.get_ui_text("refresh_mod_list_failed").format(str(e)), "ERROR")
    
    def show_settings_dialog(self):
        """显示设置对话框"""
        try:
            # 创建现代化设置对话框
            settings_dialog = tk.Toplevel(self.root)
            settings_dialog.title(self.parent.get_ui_text("settings_dialog"))
            settings_dialog.resizable(False, False)
            settings_dialog.transient(self.root)
            
            # 应用现代化样式到对话框
            from .modern_widgets import style_manager
            settings_dialog.config(bg=style_manager.get_color('bg'))
            
            # 设置对话框图标
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
            
            # 主容器
            main_container = ModernFrame(settings_dialog, style="container", padding=8)
            main_container.pack(fill=tk.BOTH, expand=True)
            
            # 批量翻译设置
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
            
            # 自动保存设置
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
            

            
            # 按钮区域
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
            
            # 创建现代化按钮
            cancel_btn = ModernButton(button_frame, text=self.parent.get_ui_text("cancel"), 
                                     command=cancel_settings, style="secondary")
            cancel_btn.pack(side=tk.RIGHT, padx=5, pady=5)
            
            save_btn = ModernButton(button_frame, text=self.parent.get_ui_text("save"), 
                                   command=save_settings, style="primary")
            save_btn.pack(side=tk.RIGHT, padx=5, pady=5)
            
            # 延迟显示对话框以确保正确居中
            def show_dialog():
                # 设置窗口自适应大小和居中显示
                settings_dialog.update_idletasks()
                
                # 获取窗口实际需要的尺寸
                settings_dialog.geometry("")  # 清除固定尺寸，让窗口自适应
                settings_dialog.update_idletasks()
                
                # 设置最小宽度，让高度自适应
                min_width = 420
                req_width = max(min_width, settings_dialog.winfo_reqwidth())
                req_height = settings_dialog.winfo_reqheight()
                
                # 居中显示
                x = (settings_dialog.winfo_screenwidth() // 2) - (req_width // 2)
                y = (settings_dialog.winfo_screenheight() // 2) - (req_height // 2)
                settings_dialog.geometry(f"{req_width}x{req_height}+{x}+{y}")
                
                # 显示窗口并获取焦点
                settings_dialog.deiconify()
                settings_dialog.grab_set()
                settings_dialog.lift()
                settings_dialog.focus_force()
            
            # 初始隐藏对话框
            settings_dialog.withdraw()
            # 延迟显示
            settings_dialog.after(50, show_dialog)
            
        except Exception as e:
            self.parent.log_message(f"{self.parent.get_ui_text('show_settings_dialog_failed')}: {str(e)}", "ERROR")
    

    
    def show_window_centered(self) -> None:
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
    
    def update_progress_display(self, current=None, total=None) -> None:
        """更新进度显示
        
        Args:
            current: 当前进度
            total: 总进度
        """
        if current is not None:
            self.translation_progress["current"] = current
        if total is not None:
            self.translation_progress["total"] = total
        
        # 更新日志框架标题以显示进度
        self.root.after(0, self._update_log_frame_title)
    
    def _update_log_frame_title(self) -> None:
        """更新日志框架标题以显示进度"""
        base_title = self.ui_text_manager.get_text("log")
        if self.translation_progress["total"] > 0:
            progress_text = f"({self.translation_progress['current']}/{self.translation_progress['total']})"
            title_with_progress = f"{base_title}{progress_text}"
        else:
            title_with_progress = base_title
        
        if 'log_frame' in self.widgets:
            self.widgets['log_frame'].config(text=title_with_progress)
    
    def update_translate_button_text(self, is_translating: bool) -> None:
        """更新翻译按钮文本
        
        Args:
            is_translating: 是否正在翻译
        """
        if 'translate_btn' in self.widgets:
            if is_translating:
                self.widgets['translate_btn'].config(text=self.ui_text_manager.get_text("stop_translate"))
            else:
                self.widgets['translate_btn'].config(text=self.ui_text_manager.get_text("auto_translate"))
    
    def get_widget(self, name: str):
        """获取控件
        
        Args:
            name: 控件名称
            
        Returns:
            控件对象或None
        """
        return self.widgets.get(name)
    
    def set_widget_state(self, name: str, state: str) -> None:
        """设置控件状态
        
        Args:
            name: 控件名称
            state: 状态（normal, disabled等）
        """
        widget = self.widgets.get(name)
        if widget and hasattr(widget, 'config'):
            widget.config(state=state)
    
    # 事件处理方法
    def _on_language_change(self, event=None) -> None:
        """语言切换回调"""
        if 'on_language_change' in self.callbacks:
            self.callbacks['on_language_change'](event)
    
    def _on_refresh_models(self) -> None:
        """刷新模型回调"""
        if 'on_refresh_models' in self.callbacks:
            self.callbacks['on_refresh_models']()
    
    def _on_show_settings(self) -> None:
        """显示设置回调"""
        if 'on_show_settings' in self.callbacks:
            self.callbacks['on_show_settings']()
    
    def _on_import_mods(self) -> None:
        """导入MOD回调"""
        if 'on_import_mods' in self.callbacks:
            self.callbacks['on_import_mods']()
    
    def _on_extract_mods(self) -> None:
        """解压MOD回调"""
        if 'on_extract_mods' in self.callbacks:
            self.callbacks['on_extract_mods']()
    
    def _on_extract_i18n(self) -> None:
        """提取i18n回调"""
        if 'on_extract_i18n' in self.callbacks:
            self.callbacks['on_extract_i18n']()
    
    def _on_auto_translate(self) -> None:
        """自动翻译回调"""
        if 'on_auto_translate' in self.callbacks:
            self.callbacks['on_auto_translate']()
    
    def _on_recompress_mods(self) -> None:
        """打包MODMOD回调"""
        if 'on_recompress_mods' in self.callbacks:
            self.callbacks['on_recompress_mods']()
    
    def _on_mod_change(self, event=None) -> None:
        """MOD选择变化回调"""
        if 'on_mod_change' in self.callbacks:
            self.callbacks['on_mod_change'](event)
    
    def _on_file_change(self, event=None) -> None:
        """文件选择变化回调"""
        if 'on_file_change' in self.callbacks:
            self.callbacks['on_file_change'](event)
    
    def _on_refresh_mod_list(self) -> None:
        """刷新MOD列表回调"""
        if 'on_refresh_mod_list' in self.callbacks:
            self.callbacks['on_refresh_mod_list']()
    
    def _on_save_translation(self) -> None:
        """保存翻译回调"""
        if 'on_save_translation' in self.callbacks:
            self.callbacks['on_save_translation']()
    
    def _on_combobox_mousewheel(self, event) -> str:
        """下拉菜单框滚轮事件处理 - 阻止滚轮选择"""
        return "break"  # 阻止默认滚轮行为
    
    def _on_original_select(self, event) -> None:
        """原文列表选择事件"""
        if 'on_original_select' in self.callbacks:
            self.callbacks['on_original_select'](event)
    
    def _on_translation_select(self, event) -> None:
        """译文列表选择事件"""
        if 'on_translation_select' in self.callbacks:
            self.callbacks['on_translation_select'](event)
    
    def _on_shared_scrollbar(self, *args) -> None:
        """共用垂直滚动条操作回调"""
        # 同时滚动原文列表框和译文列表框
        if 'original_listbox' in self.widgets:
            self.widgets['original_listbox'].yview(*args)
        if 'translation_listbox' in self.widgets:
            self.widgets['translation_listbox'].yview(*args)
    
    def _on_shared_h_scrollbar(self, *args) -> None:
        """共用水平滚动条操作回调"""
        # 同时水平滚动原文列表框和译文列表框
        if 'original_listbox' in self.widgets:
            self.widgets['original_listbox'].xview(*args)
        if 'translation_listbox' in self.widgets:
            self.widgets['translation_listbox'].xview(*args)
    
    def _on_original_h_scroll(self, *args) -> None:
        """原文水平滚动回调"""
        # 更新原文滚动条
        if 'original_h_scrollbar' in self.widgets:
            self.widgets['original_h_scrollbar'].set(*args)
        # 同步译文滚动条
        if 'translation_h_scrollbar' in self.widgets:
            self.widgets['translation_h_scrollbar'].set(*args)
    
    def _on_translation_h_scroll(self, *args) -> None:
        """译文水平滚动回调"""
        # 更新译文滚动条
        if 'translation_h_scrollbar' in self.widgets:
            self.widgets['translation_h_scrollbar'].set(*args)
        # 同步原文滚动条
        if 'original_h_scrollbar' in self.widgets:
            self.widgets['original_h_scrollbar'].set(*args)
    
    def _on_mouse_wheel(self, event) -> str:
        """鼠标滚轮事件处理"""
        # 计算滚动量
        if event.delta:
            # Windows系统
            delta = -1 * (event.delta / 120)
        else:
            # Linux系统
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            else:
                return "break"  # 阻止默认行为
        
        # 获取当前滚动位置
        if 'original_listbox' not in self.widgets:
            return "break"
            
        current_top, current_bottom = self.widgets['original_listbox'].yview()
        
        # 计算新的滚动位置
        # 获取列表框总行数
        total_items = self.widgets['original_listbox'].size()
        if total_items == 0:
            return "break"  # 阻止默认行为
        
        # 计算每个单位的滚动比例
        scroll_unit = 1.0 / total_items
        new_position = current_top + (delta * scroll_unit * 3)  # 乘以3增加滚动速度
        
        # 限制滚动范围
        new_position = max(0.0, min(1.0, new_position))
        
        # 手动同步滚动两个框
        self.widgets['original_listbox'].yview_moveto(new_position)
        if 'translation_listbox' in self.widgets:
            self.widgets['translation_listbox'].yview_moveto(new_position)
        
        # 同步更新共用滚动条位置
        if 'shared_scrollbar' in self.widgets:
            self.widgets['shared_scrollbar'].set(new_position, new_position + (current_bottom - current_top))
        
        return "break"  # 阻止默认滚动行为
    
    def _on_translation_double_click(self, event) -> None:
        """译文双击编辑事件"""
        if 'on_translation_double_click' in self.callbacks:
            self.callbacks['on_translation_double_click'](event)
    
    def _on_clear_directories(self) -> None:
        """清空目录按钮点击事件处理"""
        self.show_clear_directories_dialog()
    
    def show_clear_directories_dialog(self):
        """显示清空目录确认对话框"""
        try:
            # 创建现代化清空目录对话框
            clear_dialog = tk.Toplevel(self.root)
            clear_dialog.title(self.parent.get_ui_text("clear_directories"))
            clear_dialog.resizable(False, False)
            clear_dialog.transient(self.root)
            
            # 应用现代化样式到对话框
            from .modern_widgets import style_manager
            clear_dialog.config(bg=style_manager.get_color('bg'))
            
            # 设置对话框图标
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
            
            # 主容器
            main_container = ModernFrame(clear_dialog, style="container", padding=8)
            main_container.pack(fill=tk.BOTH, expand=True)
            
            # 警告信息区域
            warning_frame = ModernFrame(main_container, text=f"⚠️ {self.parent.get_ui_text('warning')}", 
                                      style="card", padding=5)
            warning_frame.pack(fill=tk.X, pady=(0, 8))
            
            warning_content = ModernFrame(warning_frame.get_content_frame(), style="default")
            warning_content.pack(fill=tk.X, padx=5, pady=5)
            
            # 说明文本
            info_text = self.parent.get_ui_text("clear_directories_message")
            info_label = ModernLabel(warning_content, text=info_text, 
                                   justify=tk.LEFT, wraplength=350)
            info_label.pack(anchor=tk.W)
            
            # 按钮区域
            button_frame = ModernFrame(main_container, style="default", padding=5)
            button_frame.pack(fill=tk.X, pady=(20, 0))
            
            def confirm_clear():
                """确认清空目录"""
                try:
                    # 调用文件管理器的清空方法
                    if hasattr(self.parent, 'file_manager') and hasattr(self.parent.file_manager, 'clear_data_directories'):
                        self.parent.file_manager.clear_data_directories()
                        self.parent.log_message(self.parent.get_ui_text("clear_directories_success"))
                        clear_dialog.destroy()
                    else:
                        self.parent.log_message(self.parent.get_ui_text("clear_directories_unavailable"), "ERROR")
                except Exception as e:
                    self.parent.log_message(self.parent.get_ui_text("clear_directories_error").format(str(e)), "ERROR")
            
            def cancel_clear():
                """取消清空"""
                clear_dialog.destroy()
            
            # 创建现代化按钮
            cancel_btn = ModernButton(button_frame, text=self.parent.get_ui_text("cancel"), 
                                     command=cancel_clear, style="secondary")
            cancel_btn.pack(side=tk.RIGHT, padx=5, pady=5)
            
            confirm_btn = ModernButton(button_frame, text=self.parent.get_ui_text("clear_directories_confirm"), 
                                     command=confirm_clear, style="danger")
            confirm_btn.pack(side=tk.RIGHT, padx=5, pady=5)
            
            # 延迟显示对话框以确保正确居中
            def show_dialog():
                # 设置窗口自适应大小和居中显示
                clear_dialog.update_idletasks()
                
                # 获取窗口实际需要的尺寸
                clear_dialog.geometry("")  # 清除固定尺寸，让窗口自适应
                clear_dialog.update_idletasks()
                
                # 设置最小宽度，让高度自适应
                min_width = 420
                req_width = max(min_width, clear_dialog.winfo_reqwidth())
                req_height = clear_dialog.winfo_reqheight()
                
                # 居中显示
                x = (clear_dialog.winfo_screenwidth() // 2) - (req_width // 2)
                y = (clear_dialog.winfo_screenheight() // 2) - (req_height // 2)
                clear_dialog.geometry(f"{req_width}x{req_height}+{x}+{y}")
                
                # 显示窗口并获取焦点
                clear_dialog.deiconify()
                clear_dialog.grab_set()
                clear_dialog.lift()
                clear_dialog.focus_force()
            
            # 初始隐藏对话框
            clear_dialog.withdraw()
            # 延迟显示
            clear_dialog.after(50, show_dialog)
            
        except Exception as e:
            self.parent.log_message(self.parent.get_ui_text("clear_directories_dialog_error").format(str(e)), "ERROR")