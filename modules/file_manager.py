import os
import sys
import json
import shutil
import zipfile
import subprocess
import threading
import re
from pathlib import Path
from tkinter import filedialog

class FileManager:
    """文件操作管理类"""
    
    def __init__(self, app_instance):
        """初始化文件管理器
        
        Args:
            app_instance: 主应用实例，用于访问配置和日志方法
        """
        self.app = app_instance
        
        # 目录路径
        if getattr(sys, 'frozen', False):
            # 打包后的exe环境，使用exe文件所在目录
            self.work_dir = Path(os.path.dirname(sys.executable))
        else:
            # 开发环境，使用项目根目录
            self.work_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = self.work_dir / "Data"
        self.import_dir = self.data_dir / "1Import"
        self.extract_dir = self.data_dir / "2Extract"
        self.i18n_dir = self.data_dir / "3Completei18n"
        self.compress_dir = self.data_dir / "4Compress"
        
        # 创建必要的目录
        self._create_directories()
    
    def _create_directories(self):
        """创建必要的目录"""
        for directory in [self.import_dir, self.extract_dir, self.i18n_dir, self.compress_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def load_json_with_comments(self, file_path):
        """静默加载支持注释和BOM的JSON文件，容错解析但不修复原文件"""
        try:
            # 读取文件内容，自动处理BOM
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            # 移除注释（保留原始内容用于保存）
            lines = content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                # 移除单行注释 //
                if '//' in line:
                    # 检查是否在字符串内
                    in_string = False
                    escaped = False
                    comment_pos = -1
                    
                    for i, char in enumerate(line):
                        if escaped:
                            escaped = False
                            continue
                        if char == '\\' and in_string:
                            escaped = True
                            continue
                        if char == '"':
                            in_string = not in_string
                        elif char == '/' and i + 1 < len(line) and line[i + 1] == '/' and not in_string:
                            comment_pos = i
                            break
                    
                    if comment_pos >= 0:
                        line = line[:comment_pos].rstrip()
                
                # 跳过多行注释块
                line = line.strip()
                if line.startswith('/*') or line.startswith('*') or line.endswith('*/'):
                    continue
                
                if line:  # 只保留非空行
                    cleaned_lines.append(line)
            
            # 重新组合内容
            cleaned_content = '\n'.join(cleaned_lines)
            
            # 尝试直接解析JSON
            try:
                return json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                # 如果解析失败，静默尝试修复常见的JSON语法错误
                fixed_content = self._fix_json_syntax_errors(cleaned_content)
                
                try:
                    result = json.loads(fixed_content)
                    self.app.log_message(f"JSON解析成功: {file_path}")
                    return result
                    
                except json.JSONDecodeError as e2:
                    # 如果修复后仍然失败，记录错误但不弹窗
                    error_details = self._get_detailed_json_error(file_path, cleaned_content, e2)
                    self.app.log_message(f"JSON解析失败: {file_path}")
                    
                    raise Exception(f"解析JSON文件失败 {file_path}: {str(e2)}")
            
        except Exception as e:
            if "解析JSON文件失败" not in str(e):
                raise Exception(f"读取JSON文件失败 {file_path}: {str(e)}")
            else:
                raise e
    
    def save_json_with_original_format(self, data, original_file_path, target_file_path):
        """保存JSON文件并保持原始格式（包括注释）"""
        try:
            # 读取原始文件内容
            with open(original_file_path, 'r', encoding='utf-8-sig') as f:
                original_content = f.read()
            
            # 创建新内容，保持原始格式但更新翻译值
            lines = original_content.split('\n')
            new_lines = []
            
            # 获取所有键的列表，用于判断是否是最后一个键
            data_keys = list(data.keys())
            
            for i, line in enumerate(lines):
                # 检查是否是键值对行
                if ':' in line and not line.strip().startswith('//') and not line.strip().startswith('/*'):
                    # 提取键名
                    key_match = re.search(r'"([^"]+)"\s*:', line)
                    if key_match:
                        key = key_match.group(1)
                        if key in data:
                            # 替换值，保持原始格式
                            value_part = line.split(':', 1)[1]
                            # 保持缩进和格式
                            indent = line[:line.find('"')]
                            new_value = json.dumps(data[key], ensure_ascii=False)
                            new_line = f'{indent}"{key}": {new_value}'
                            
                            # 智能识别注释（避免将网址中的//误识别为注释）
                            def find_comment_start(text):
                                """查找真正的注释开始位置，避免将字符串内的//误识别"""
                                in_string = False
                                escape_next = False
                                for i, char in enumerate(text):
                                    if escape_next:
                                        escape_next = False
                                        continue
                                    if char == '\\':
                                        escape_next = True
                                        continue
                                    if char == '"' and not escape_next:
                                        in_string = not in_string
                                    elif not in_string and char == '/' and i + 1 < len(text) and text[i + 1] == '/':
                                        return i
                                return -1
                            
                            comment_start = find_comment_start(value_part)
                            
                            # 检查原始行是否有逗号（在注释之前）
                            value_before_comment = value_part[:comment_start] if comment_start >= 0 else value_part
                            has_comma_in_original = ',' in value_before_comment
                            
                            # 查找后续是否还有其他键值对（排除注释和空行）
                            has_more_keys = False
                            for j in range(i + 1, len(lines)):
                                next_line = lines[j].strip()
                                if next_line and not next_line.startswith('//') and not next_line.startswith('/*') and ':' in next_line:
                                    # 检查是否是有效的键值对
                                    next_key_match = re.search(r'"([^"]+)"\s*:', next_line)
                                    if next_key_match and next_key_match.group(1) in data:
                                        has_more_keys = True
                                        break
                                elif next_line == '}':  # 遇到结束大括号
                                    break
                            
                            # 只有当原始行有逗号且后面还有其他键值对时才添加逗号
                            if has_comma_in_original and has_more_keys:
                                new_line += ','
                            
                            # 保持注释（使用智能识别）
                            if comment_start >= 0:
                                comment_part = value_part[comment_start + 2:]  # 跳过//
                                comment_part = comment_part.strip()
                                if comment_part:
                                    new_line += ' //' + comment_part
                            
                            new_lines.append(new_line)
                            continue
                
                # 保持原始行
                new_lines.append(line)
            
            # 写入文件
            with open(target_file_path, 'w', encoding='utf-8-sig') as f:
                f.write('\n'.join(new_lines))
                
        except Exception as e:
            # 如果保持格式失败，使用标准JSON保存
            with open(target_file_path, 'w', encoding='utf-8') as f:
                 json.dump(data, f, ensure_ascii=False, indent=4)
    
    def _load_comparison_data_async(self):
        """在后台线程中加载对比数据"""
        try:
            # 获取当前选择的MOD和文件
            selected_mod = self.app.gui_manager.parent.mod_combo.get()
            selected_file = self.app.gui_manager.parent.file_combo.get()
            
            if not selected_mod or not selected_file:
                # 没有选择mod或文件时清空文本显示区域
                self.app.root.after(0, self._clear_comparison_display)
                return
            
            # 构建文件路径
            translation_file_path = self.i18n_dir / "Translation" / selected_mod / selected_file
            original_file_path = self.find_matching_original_file(translation_file_path, selected_mod)
            
            if not translation_file_path.exists():
                # 翻译文件不存在时清空文本显示区域
                self.app.root.after(0, self._clear_comparison_display)
                return
            
            # 加载翻译文件
            translation_data = self.load_json_with_comments(translation_file_path)
            
            # 设置当前翻译文件路径，用于保存功能
            self.app.current_translation_file = translation_file_path
            
            # 加载原文文件
            original_data = {}
            if original_file_path and original_file_path.exists():
                original_data = self.load_json_with_comments(original_file_path)
            
            # 在主线程中显示对比数据
            self.app.root.after(0, self.app.translation_manager.display_comparison_data, translation_data, original_data)
            
        except Exception as e:
            # 加载失败时清空文本显示区域
            self.app.root.after(0, self._clear_comparison_display)
            self.app.root.after(0, self.app.log_message, f"刷新对比数据失败: {str(e)}", "ERROR")
    
    def refresh_comparison_data(self):
        """刷新对比数据"""
        # 在后台线程中处理
        threading.Thread(target=self._load_comparison_data_async, daemon=True).start()
    
    def refresh_mod_list(self):
        """刷新MOD列表"""
        def scan_mods():
            """在后台线程中扫描MOD"""
            try:
                available_mods = []
                
                # 获取3Completei18n目录
                original_dir = self.i18n_dir / "Original"
                
                if not original_dir.exists():
                    self.app.root.after(0, self.app.log_message, "Original目录不存在，请先提取i18n文件")
                    return
                
                # 查找所有mod目录（包含JSON文件的目录）
                for mod_path in original_dir.iterdir():
                    if mod_path.is_dir():
                        # 检查是否包含JSON文件
                        json_files = list(mod_path.rglob("*.json"))
                        if json_files:
                            available_mods.append({
                                'name': mod_path.name,
                                'path': mod_path,
                                'files': json_files
                            })
                
                # 在主线程中更新UI
                self.app.root.after(0, self._update_mod_list_ui, available_mods)
                
            except Exception as e:
                self.app.root.after(0, self.app.log_message, f"刷新MOD列表失败: {str(e)}", "ERROR")
        
        # 在后台线程中执行扫描
        threading.Thread(target=scan_mods, daemon=True).start()
    
    def _update_mod_list_ui(self, available_mods):
        """在主线程中更新MOD列表UI"""
        try:
            self.available_mods = available_mods
            
            # 更新下拉框
            mod_names = [mod['name'] for mod in self.available_mods]
            self.app.gui_manager.parent.mod_combo['values'] = mod_names
            
            if mod_names:
                self.app.gui_manager.parent.mod_combo.set(mod_names[0])
                self.app.log_message(self.app.ui_text_manager.get_text("found_mods").format(len(mod_names), ', '.join(mod_names)))
                # 在后台线程中加载MOD数据
                threading.Thread(target=self._load_mod_data_async, daemon=True).start()
            else:
                self.app.gui_manager.parent.mod_combo.set('')
                # 清空文件下拉菜单和文本显示区域
                self.app.gui_manager.parent.file_combo.set('')
                self.app.gui_manager.parent.file_combo['values'] = []
                if hasattr(self.app, 'original_listbox'):
                    self.app.original_listbox.delete(0, 'end')
                if hasattr(self.app, 'translation_listbox'):
                    self.app.translation_listbox.delete(0, 'end')
                self.app.log_message(self.app.ui_text_manager.get_text("no_mods_found"))
                
        except Exception as e:
            self.app.log_message(f"更新MOD列表UI失败: {str(e)}", "ERROR")
    
    def _load_mod_data_async(self):
        """在后台线程中加载MOD数据"""
        try:
            selected_mod_name = self.app.gui_manager.parent.mod_combo.get()
            if not selected_mod_name:
                # 没有选择mod时清空界面
                self.app.root.after(0, self._clear_file_ui)
                return
                
            # 查找对应的MOD信息
            selected_mod = None
            for mod in self.available_mods:
                if mod['name'] == selected_mod_name:
                    selected_mod = mod
                    break
            
            if selected_mod:
                # 设置当前MOD路径
                self.app.current_mod_path = selected_mod['path']
                self.app.root.after(0, self.app.log_message, self.app.ui_text_manager.get_text("switch_to_mod").format(selected_mod['name']))
                
                # 在后台加载文件列表和对比数据
                self._load_file_list_async()
                self._load_comparison_data_async()
            else:
                # 找不到对应mod时清空界面
                self.app.root.after(0, self._clear_file_ui)
        except Exception as e:
            # 加载失败时清空界面
            self.app.root.after(0, self._clear_file_ui)
            self.app.root.after(0, self.app.log_message, f"MOD数据加载失败: {str(e)}", "ERROR")
    
    def on_mod_change(self, event=None):
        """MOD选择改变事件"""
        # 在后台线程中处理MOD切换
        threading.Thread(target=self._load_mod_data_async, daemon=True).start()
    
    def _load_file_list_async(self):
        """在后台线程中加载文件列表"""
        try:
            available_files = []
            
            if hasattr(self.app, 'current_mod_path') and self.app.current_mod_path:
                # 查找当前MOD的所有JSON文件
                translation_dir = self.i18n_dir / "Translation" / self.app.current_mod_path.name
                if translation_dir.exists():
                    json_files = list(translation_dir.rglob('*.json'))
                    if json_files:
                        for json_file in json_files:
                            # 获取相对于translation目录的路径
                            rel_path = json_file.relative_to(translation_dir)
                            available_files.append({
                                'name': str(rel_path),
                                'path': json_file
                            })
                        
                        # 在主线程中更新UI
                        self.app.root.after(0, self._update_file_list_ui, available_files)
                    else:
                        # 没有找到文件时清空界面
                        self.app.root.after(0, self._clear_file_ui)
                        self.app.root.after(0, self.app.log_message, self.app.get_ui_text("no_localization_files_found"))
                else:
                    # 目录不存在时清空界面
                    self.app.root.after(0, self._clear_file_ui)
                    self.app.root.after(0, self.app.log_message, self.app.get_ui_text("mod_translation_dir_not_exist"))
        except Exception as e:
            self.app.root.after(0, self.app.log_message, self.app.get_ui_text("refresh_file_list_failed").format(str(e)), "ERROR")
    
    def _update_file_list_ui(self, available_files):
        """在主线程中更新文件列表UI"""
        try:
            self.app.available_files = available_files
            
            # 更新下拉框
            file_names = [f['name'] for f in available_files]
            self.app.gui_manager.parent.file_combo['values'] = file_names
            
            # 默认选择第一个文件
            if file_names:
                self.app.gui_manager.parent.file_combo.set(file_names[0])
                self.app.current_file_index = 0
                self.app.log_message(self.app.get_ui_text("found_localization_files").format(len(file_names)))
            else:
                # 没有文件时清空文本显示区域
                if hasattr(self.app, 'original_listbox'):
                    self.app.original_listbox.delete(0, 'end')
                if hasattr(self.app, 'translation_listbox'):
                    self.app.translation_listbox.delete(0, 'end')
        except Exception as e:
            self.app.log_message(self.app.get_ui_text("refresh_file_list_failed").format(str(e)), "ERROR")
    
    def refresh_file_list(self):
        """刷新当前MOD的文件列表"""
        # 在后台线程中处理
        threading.Thread(target=self._load_file_list_async, daemon=True).start()
    
    def on_file_change(self, event=None):
        """文件选择改变事件"""
        try:
            selected_file = self.app.gui_manager.parent.file_combo.get()
            if not selected_file:
                # 没有选择文件时清空文本显示区域
                if hasattr(self.app, 'original_listbox'):
                    self.app.original_listbox.delete(0, 'end')
                if hasattr(self.app, 'translation_listbox'):
                    self.app.translation_listbox.delete(0, 'end')
                # 重置文件索引
                self.app.current_file_index = -1
                return
            
            # 更新当前文件索引以匹配用户选择
            if hasattr(self.app, 'available_files') and self.app.available_files:
                for i, file_info in enumerate(self.app.available_files):
                    if file_info['name'] == selected_file:
                        self.app.current_file_index = i
                        break
                else:
                    # 如果没找到匹配的文件，设置为-1
                    self.app.current_file_index = -1
                
            # 使用多语言文本
            switch_text = self.app.ui_text_manager.get_text("switch_to_file")
            self.app.log_message(switch_text.format(selected_file, getattr(self.app, 'current_file_index', -1)))
            # 在后台线程中重新加载对比文件
            threading.Thread(target=self._load_comparison_data_async, daemon=True).start()
            
        except Exception as e:
            self.app.log_message(f"切换文件失败: {str(e)}", "ERROR")
    
    def find_matching_original_file(self, mod_name, file_name):
        """查找匹配的原文件"""
        try:
            # 在extract目录中查找对应的原文件
            extract_mod_dir = self.extract_dir / mod_name
            if not extract_mod_dir.exists():
                return None
            
            # 递归查找匹配的文件
            for root, dirs, files in os.walk(extract_mod_dir):
                if file_name in files:
                    return Path(root) / file_name
            
            return None
            
        except Exception:
            return None
     
    def import_mods(self):
        """导入 MOD 文件"""
        file_paths = filedialog.askopenfilenames(
            title=self.app.get_ui_text("select_mod_files_title"),
            filetypes=[(self.app.get_ui_text("compressed_files_type"), "*.zip *.rar *.7z"), (self.app.get_ui_text("all_files_type"), "*.*")]
        )
        
        if not file_paths:
            return
        
        def import_files():
            try:
                for file_path in file_paths:
                    src_path = Path(file_path)
                    dst_path = self.import_dir / src_path.name
                    shutil.copy2(src_path, dst_path)
                    self.app.log_message(self.app.get_ui_text("imported_file").format(src_path.name))
                
                self.app.log_message(self.app.get_ui_text("import_success").format(len(file_paths)))
            except Exception as e:
                self.app.log_message(self.app.get_ui_text("import_failed").format(str(e)), "ERROR")
        
        threading.Thread(target=import_files, daemon=True).start()
    
    def extract_mods(self):
        """解压 MOD 文件"""
        def extract():
            try:
                # 清理解压目录
                if self.extract_dir.exists():
                    shutil.rmtree(self.extract_dir)
                self.extract_dir.mkdir(parents=True, exist_ok=True)
                
                # 查找压缩文件
                archive_files = []
                for ext in ['*.zip', '*.rar', '*.7z']:
                    archive_files.extend(self.import_dir.glob(ext))
                
                if not archive_files:
                    self.app.log_message(self.app.get_ui_text("no_archives_found"), "ERROR")
                    return
                
                for archive_file in archive_files:
                    mod_name = archive_file.stem
                    extract_path = self.extract_dir / mod_name
                    
                    self.app.log_message(self.app.get_ui_text("extracting_file").format(archive_file.name))
                    
                    try:
                        if archive_file.suffix.lower() == '.zip':
                            with zipfile.ZipFile(archive_file, 'r') as zip_ref:
                                zip_ref.extractall(extract_path)
                        else:
                            # 对于 rar 和 7z 文件，尝试使用系统命令
                            if archive_file.suffix.lower() == '.rar':
                                subprocess.run(['unrar', 'x', str(archive_file), str(extract_path)], 
                                             check=True, capture_output=True)
                            elif archive_file.suffix.lower() == '.7z':
                                subprocess.run(['7z', 'x', str(archive_file), f'-o{extract_path}'], 
                                             check=True, capture_output=True)
                        
                        self.app.log_message(self.app.get_ui_text("extract_success").format(mod_name))
                    except Exception as e:
                        self.app.log_message(self.app.get_ui_text("extract_failed").format(archive_file.name, str(e)), "ERROR")
                
                self.app.log_message(self.app.get_ui_text("extract_completed"))
            except Exception as e:
                self.app.log_message(self.app.get_ui_text("extract_error").format(str(e)), "ERROR")
        
        threading.Thread(target=extract, daemon=True).start()
    
    def extract_i18n(self):
        """提取 i18n 文件"""
        def extract():
            try:
                # 清理 i18n 目录
                if self.i18n_dir.exists():
                    shutil.rmtree(self.i18n_dir)
                self.i18n_dir.mkdir(parents=True, exist_ok=True)
                
                # 创建Original和Translation文件夹
                original_dir = self.i18n_dir / "Original"
                translation_dir = self.i18n_dir / "Translation"
                original_dir.mkdir(parents=True, exist_ok=True)
                translation_dir.mkdir(parents=True, exist_ok=True)
                
                target_lang = self.app.target_language_var.get()
                lang_prefix = self.app.language_codes.get(target_lang, "en")
                
                # 遍历解压目录中的所有 MOD
                for mod_dir in self.extract_dir.iterdir():
                    if not mod_dir.is_dir():
                        continue
                    
                    self.app.log_message(self.app.get_ui_text("processing_mod").format(mod_dir.name))
                    
                    # 查找所有 i18n 文件夹
                    i18n_folders = list(mod_dir.rglob("i18n"))
                    
                    for i18n_folder in i18n_folders:
                        if not i18n_folder.is_dir():
                            continue
                        
                        # 计算相对路径
                        rel_path = i18n_folder.relative_to(self.extract_dir)
                        
                        # 优先查找default.json，如果没有则查找其他JSON文件
                        default_json = i18n_folder / "default.json"
                        source_json = None
                        
                        if default_json.exists():
                            source_json = default_json
                        else:
                            # 如果没有default.json，查找其他JSON文件
                            json_files = list(i18n_folder.glob("*.json"))
                            if json_files:
                                source_json = json_files[0]  # 选择第一个找到的JSON文件
                        
                        if source_json:
                            # 复制原文文件到Original目录
                            target_original_dir = original_dir / rel_path
                            target_original_dir.mkdir(parents=True, exist_ok=True)
                            target_original = target_original_dir / source_json.name
                            shutil.copy2(source_json, target_original)
                            
                            # 复制文件到Translation目录
                            target_translation_dir = translation_dir / rel_path
                            target_translation_dir.mkdir(parents=True, exist_ok=True)
                            
                            # 如果是default.json，重命名为目标语言
                            if source_json.name.lower() == "default.json":
                                target_translation = target_translation_dir / f"{lang_prefix}.json"
                            else:
                                # 其他文件保持原名
                                target_translation = target_translation_dir / source_json.name
                            
                            shutil.copy2(source_json, target_translation)
                            
                            self.app.log_message(self.app.get_ui_text("extract_i18n_file").format(rel_path / source_json.name, target_translation.name))
                
                # 刷新mod列表
                self.app.refresh_mod_list()
                
                # 延迟输出完成消息，确保在所有异步操作完成后显示
                def delayed_completion_message():
                    import time
                    time.sleep(2)  # 等待异步操作完成
                    self.app.root.after(0, self.app.log_message, self.app.get_ui_text("i18n_extract_completed"))
                
                threading.Thread(target=delayed_completion_message, daemon=True).start()
                
            except Exception as e:
                self.app.log_message(self.app.get_ui_text("i18n_extract_failed").format(str(e)), "ERROR")
        
        threading.Thread(target=extract, daemon=True).start()
    

    
    def find_matching_original_file(self, translation_file_path, mod_name):
        """智能匹配原文件，优先选择default.json"""
        original_dir = self.i18n_dir / "Original"
        translation_dir = self.i18n_dir / "Translation"
        
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
    
    def save_json_with_original_format(self, data, original_file_path, target_file_path):
        """保存JSON文件并保持原始格式（包括注释）"""
        try:
            # 读取原始文件内容
            with open(original_file_path, 'r', encoding='utf-8-sig') as f:
                original_content = f.read()
            
            # 创建新内容，保持原始格式但更新翻译值
            lines = original_content.split('\n')
            new_lines = []
            
            # 获取所有键的列表，用于判断是否是最后一个键
            data_keys = list(data.keys())
            
            for i, line in enumerate(lines):
                # 检查是否是键值对行
                if ':' in line and not line.strip().startswith('//') and not line.strip().startswith('/*'):
                    # 提取键名
                    key_match = re.search(r'"([^"]+)"\s*:', line)
                    if key_match:
                        key = key_match.group(1)
                        if key in data:
                            # 替换值，保持原始格式
                            value_part = line.split(':', 1)[1]
                            # 保持缩进和格式
                            indent = line[:line.find('"')]
                            new_value = json.dumps(data[key], ensure_ascii=False)
                            new_line = f'{indent}"{key}": {new_value}'
                            
                            # 智能识别注释（避免将网址中的//误识别为注释）
                            def find_comment_start(text):
                                """查找真正的注释开始位置，避免将字符串内的//误识别"""
                                in_string = False
                                escape_next = False
                                for i, char in enumerate(text):
                                    if escape_next:
                                        escape_next = False
                                        continue
                                    if char == '\\':
                                        escape_next = True
                                        continue
                                    if char == '"' and not escape_next:
                                        in_string = not in_string
                                    elif not in_string and char == '/' and i + 1 < len(text) and text[i + 1] == '/':
                                        return i
                                return -1
                            
                            comment_start = find_comment_start(value_part)
                            
                            # 检查原始行是否有逗号（在注释之前）
                            value_before_comment = value_part[:comment_start] if comment_start >= 0 else value_part
                            has_comma_in_original = ',' in value_before_comment
                            
                            # 查找后续是否还有其他键值对（排除注释和空行）
                            has_more_keys = False
                            for j in range(i + 1, len(lines)):
                                next_line = lines[j].strip()
                                if next_line and not next_line.startswith('//') and not next_line.startswith('/*') and ':' in next_line:
                                    # 检查是否是有效的键值对
                                    next_key_match = re.search(r'"([^"]+)"\s*:', next_line)
                                    if next_key_match and next_key_match.group(1) in data:
                                        has_more_keys = True
                                        break
                                elif next_line == '}':  # 遇到结束大括号
                                    break
                            
                            # 只有当原始行有逗号且后面还有其他键值对时才添加逗号
                            if has_comma_in_original and has_more_keys:
                                new_line += ','
                            
                            # 保持注释（使用智能识别）
                            if comment_start >= 0:
                                comment_part = value_part[comment_start + 2:]  # 跳过//
                                comment_part = comment_part.strip()
                                if comment_part:
                                    new_line += ' //' + comment_part
                            
                            new_lines.append(new_line)
                            continue
                
                # 保持原始行
                new_lines.append(line)
            
            # 写入文件
            with open(target_file_path, 'w', encoding='utf-8-sig') as f:
                f.write('\n'.join(new_lines))
                
        except Exception as e:
            # 如果保持格式失败，使用标准JSON保存
            with open(target_file_path, 'w', encoding='utf-8') as f:
                 json.dump(data, f, ensure_ascii=False, indent=4)
    
    def save_translation_data(self, mod_name, file_name, data):
        """保存翻译数据到文件"""
        try:
            # 确保Translation目录存在
            translation_dir = self.i18n_dir / "Translation"
            mod_dir = translation_dir / mod_name
            
            # 创建完整的目录结构
            file_path = mod_dir / file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 查找对应的原文件以保持格式
            original_file = self.find_matching_original_file(file_path, mod_name)
            
            if original_file and original_file.exists():
                # 使用保持格式的方法保存
                self.save_json_with_original_format(data, original_file, file_path)
            else:
                # 如果找不到原文件，使用标准JSON保存
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.app.log_message(f"已保存翻译文件: {file_path}")
            
        except Exception as e:
            self.app.log_message(f"保存翻译文件失败: {str(e)}", "ERROR")
    
    def save_translation_files(self):
        """保存翻译文件"""
        try:
            translation_dir = self.i18n_dir / "Translation"
            if not translation_dir.exists():
                self.app.log_message(self.app.get_ui_text("translation_dir_not_exist"), "ERROR")
                return
            
            # 获取当前显示的数据
            if not hasattr(self.app, 'current_translation_data'):
                self.app.log_message(self.app.get_ui_text("no_translation_data_to_save"), "WARNING")
                return
            
            # 更新翻译数据
            for i in range(self.app.translation_listbox.size()):
                if i < len(self.app.current_translation_keys):
                    key = self.app.current_translation_keys[i]
                    value = self.app.translation_listbox.get(i)
                    self.app.current_translation_data[key] = value
            
            # 保存到文件
            if hasattr(self.app, 'current_translation_file'):
                # 查找对应的原文件以保持格式
                original_file = None
                if hasattr(self.app, 'current_mod_path'):
                    mod_name = self.app.current_mod_path.name
                    original_file = self.find_matching_original_file(self.app.current_translation_file, mod_name)
                
                if original_file and original_file.exists():
                    # 使用保持格式的方法保存
                    self.save_json_with_original_format(
                        self.app.current_translation_data, 
                        original_file, 
                        self.app.current_translation_file
                    )
                else:
                    # 如果找不到原文件，使用标准JSON保存
                    with open(self.app.current_translation_file, 'w', encoding='utf-8') as f:
                        json.dump(self.app.current_translation_data, f, ensure_ascii=False, indent=2)
                
                self.app.log_message(self.app.get_ui_text("translation_file_saved").format(self.app.current_translation_file.name))
            else:
                self.app.log_message(self.app.get_ui_text("cannot_determine_save_path"), "ERROR")
                
        except Exception as e:
            self.app.log_message(self.app.get_ui_text("save_translation_file_failed").format(str(e)), "ERROR")
    
    def recompress_mods(self):
        """打包MOD MOD"""
        def compress():
            try:
                # 清理压缩目录
                if self.compress_dir.exists():
                    shutil.rmtree(self.compress_dir)
                self.compress_dir.mkdir(parents=True, exist_ok=True)
                
                # 获取当前选择的翻译语言代码
                selected_language = self.app.target_language_var.get()
                language_code = self.app.language_codes.get(selected_language, "zh")
                
                # 只遍历Translation目录内的 MOD
                translation_dir = self.i18n_dir / "Translation"
                if not translation_dir.exists():
                    self.app.log_message(self.app.get_ui_text("translation_dir_not_exist"), "ERROR")
                    return
                
                for mod_dir in translation_dir.iterdir():
                    if not mod_dir.is_dir():
                        continue
                    
                    self.app.log_message(self.app.get_ui_text("compressing_mod").format(mod_dir.name))
                    
                    # 创建带语言前缀的 ZIP 文件名
                    zip_filename = f"{language_code}_{mod_dir.name}.zip"
                    zip_path = self.compress_dir / zip_filename
                    
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for file_path in mod_dir.rglob('*'):
                            if file_path.is_file():
                                arcname = file_path.relative_to(mod_dir)
                                zipf.write(file_path, arcname)
                    
                    self.app.log_message(self.app.get_ui_text("compress_success").format(zip_path.name))
                
                self.app.log_message(self.app.get_ui_text("recompress_completed"))
                
                # 压缩完成后自动打开4Compress文件夹
                try:
                    if self.compress_dir.exists():
                        subprocess.run(['explorer', str(self.compress_dir)], check=False)
                except Exception as folder_error:
                    # 打开文件夹失败不影响主要功能，只记录日志
                    print(f"打开压缩文件夹失败: {folder_error}")
            except Exception as e:
                self.app.log_message(self.app.get_ui_text("compress_error").format(str(e)), "ERROR")
        
        threading.Thread(target=compress, daemon=True).start()
    
    def clear_data_directories(self):
        """清空Data目录下的指定文件夹"""
        try:
            directories_to_clear = [
                self.import_dir,    # Data/1Import
                self.extract_dir,   # Data/2Extract
                self.i18n_dir      # Data/3Completei18n
            ]
            
            for directory in directories_to_clear:
                if directory.exists():
                    # 删除目录内所有文件和子目录
                    for item in directory.iterdir():
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    
                    self.app.log_message(self.app.get_ui_text("clear_directory_success").format(directory.name))
                else:
                    self.app.log_message(self.app.get_ui_text("directory_not_exist").format(directory.name), "WARNING")
            
            # 清空完成后重置界面组件
            self._reset_ui_components()
            # 刷新mod列表
            self.app.refresh_mod_list()
            
        except Exception as e:
            raise Exception(self.app.get_ui_text("clear_directories_error").format(str(e)))
    
    def _reset_ui_components(self):
        """重置界面组件到空状态"""
        try:
            # 清空mod下拉菜单
            self.app.gui_manager.parent.mod_combo.set("")
            self.app.gui_manager.parent.mod_combo['values'] = []
            
            # 清空文件下拉菜单
            self.app.gui_manager.parent.file_combo.set("")
            self.app.gui_manager.parent.file_combo['values'] = []
            
            # 清空原文和翻译列表框
            if hasattr(self.app, 'original_listbox'):
                self.app.original_listbox.delete(0, 'end')
            if hasattr(self.app, 'translation_listbox'):
                self.app.translation_listbox.delete(0, 'end')
            
            # 清空当前数据
            self.app.current_original_data = {}
            self.app.current_translation_data = {}
            self.app.current_translation_keys = []
            self.app.current_mod_path = None
            self.app.current_translation_file = None
            
            # 重置可用数据
            self.app.available_mods = []
            self.app.available_files = []
            
        except Exception as e:
            self.app.log_message(f"重置界面组件失败: {str(e)}", "ERROR")
    
    def _clear_file_ui(self):
        """清空文件相关的界面组件"""
        try:
            # 清空文件下拉菜单
            self.app.gui_manager.parent.file_combo.set("")
            self.app.gui_manager.parent.file_combo['values'] = []
            
            # 清空原文和翻译列表框
            if hasattr(self.app, 'original_listbox'):
                self.app.original_listbox.delete(0, 'end')
            if hasattr(self.app, 'translation_listbox'):
                self.app.translation_listbox.delete(0, 'end')
            
            # 清空文件相关数据
            self.app.current_original_data = {}
            self.app.current_translation_data = {}
            self.app.current_translation_keys = []
            self.app.current_translation_file = None
            self.app.available_files = []
            
        except Exception as e:
            self.app.log_message(f"清空文件界面失败: {str(e)}", "ERROR")
    
    def _clear_comparison_display(self):
        """清空文本对比显示区域"""
        try:
            # 清空原文和翻译列表框
            if hasattr(self.app, 'original_listbox'):
                self.app.original_listbox.delete(0, 'end')
            if hasattr(self.app, 'translation_listbox'):
                self.app.translation_listbox.delete(0, 'end')
            
            # 清空对比数据
            self.app.current_original_data = {}
            self.app.current_translation_data = {}
            self.app.current_translation_keys = []
            
        except Exception as e:
            self.app.log_message(f"清空对比显示失败: {str(e)}", "ERROR")
    
    def _fix_json_syntax_errors(self, content):
        """
        修复常见的JSON语法错误
        """
        # 修复末尾多余的逗号
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # 修复缺失的逗号（在对象属性之间）
        content = re.sub(r'"\s*\n\s*"', '",\n\t"', content)
        
        # 修复单引号为双引号
        content = re.sub(r"'([^']*)':", r'"\1":', content)
        
        # 修复未引用的属性名
        content = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        
        # 移除多余的空行
        content = re.sub(r'\n\s*\n', '\n', content)
        
        # 确保JSON结构完整
        content = content.strip()
        if not content.startswith('{') and not content.startswith('['):
            content = '{' + content
        if not content.endswith('}') and not content.endswith(']'):
            if content.startswith('{'):
                content = content + '}'
            elif content.startswith('['):
                content = content + ']'
        
        return content
    
    def _get_detailed_json_error(self, file_path, content, error):
        """
        生成详细的JSON错误信息
        """
        lines = content.split('\n')
        error_line = error.lineno - 1 if error.lineno > 0 else 0
        
        # 获取错误行周围的上下文
        start_line = max(0, error_line - 2)
        end_line = min(len(lines), error_line + 3)
        
        context_lines = []
        for i in range(start_line, end_line):
            if i < len(lines):
                marker = " -> " if i == error_line else "    "
                context_lines.append(f"{marker}第{i+1}行: {lines[i]}")
        
        error_msg = f"""
JSON解析错误详情:
文件: {file_path}
错误: {error.msg}
位置: 第{error.lineno}行，第{error.colno}列

错误上下文:
{chr(10).join(context_lines)}

建议检查:
1. 是否有多余的逗号（特别是最后一个属性后）
2. 是否缺少引号
3. 是否有未转义的特殊字符
4. 是否有未闭合的括号或大括号
"""
        return error_msg
    
    def _save_fixed_json_file(self, file_path, data):
        """
        保存修复后的JSON文件
        """
        try:
            # 创建备份
            backup_path = str(file_path) + '.backup'
            if os.path.exists(file_path):
                shutil.copy2(file_path, backup_path)
                self.app.log_message(f"已创建备份文件: {backup_path}")
            
            # 保存修复后的文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent='\t')
            
            self.app.log_message(f"已保存修复后的JSON文件: {file_path}")
            
            from tkinter import messagebox
            messagebox.showinfo("保存成功", 
                              f"修复后的文件已保存\n"
                              f"备份文件: {Path(backup_path).name}")
            
        except Exception as e:
            self.app.log_message(f"保存修复文件失败: {e}", "ERROR")
            from tkinter import messagebox
            messagebox.showerror("保存失败", f"无法保存修复后的文件: {e}")