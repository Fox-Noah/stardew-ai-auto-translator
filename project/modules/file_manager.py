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
    
    def __init__(self, app_instance):
        self.app = app_instance
        
        if getattr(sys, 'frozen', False):
            self.work_dir = Path(os.path.dirname(sys.executable))
        else:
            self.work_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = self.work_dir / "Data"
        self.import_dir = self.data_dir / "1Import"
        self.extract_dir = self.data_dir / "2Extract"
        self.i18n_dir = self.data_dir / "3Completei18n"
        self.compress_dir = self.data_dir / "4Compress"
        
        self._create_directories()
    
    def _create_directories(self):
        for directory in [self.import_dir, self.extract_dir, self.i18n_dir, self.compress_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def load_json_with_comments(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            lines = content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                if '//' in line:
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
                
                line = line.strip()
                if line.startswith('/*') or line.startswith('*') or line.endswith('*/'):
                    continue
                
                if line:
                    cleaned_lines.append(line)
            
            cleaned_content = '\n'.join(cleaned_lines)
            
            return json.loads(cleaned_content)
            
        except Exception as e:
            raise Exception(f"解析JSON文件失败 {file_path}: {str(e)}")
    
    def save_json_with_original_format(self, data, original_file_path, target_file_path):
        try:
            with open(original_file_path, 'r', encoding='utf-8-sig') as f:
                original_content = f.read()
            
            lines = original_content.split('\n')
            new_lines = []
            
            data_keys = list(data.keys())
            
            for i, line in enumerate(lines):
                if ':' in line and not line.strip().startswith('//') and not line.strip().startswith('/*'):
                    key_match = re.search(r'"([^"]+)"\s*:', line)
                    if key_match:
                        key = key_match.group(1)
                        if key in data:
                            value_part = line.split(':', 1)[1]
                            indent = line[:line.find('"')]
                            new_value = json.dumps(data[key], ensure_ascii=False)
                            new_line = f'{indent}"{key}": {new_value}'
                            
                            def find_comment_start(text):
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
                            
                            value_before_comment = value_part[:comment_start] if comment_start >= 0 else value_part
                            has_comma_in_original = ',' in value_before_comment
                            
                            has_more_keys = False
                            for j in range(i + 1, len(lines)):
                                next_line = lines[j].strip()
                                if next_line and not next_line.startswith('//') and not next_line.startswith('/*') and ':' in next_line:
                                    next_key_match = re.search(r'"([^"]+)"\s*:', next_line)
                                    if next_key_match and next_key_match.group(1) in data:
                                        has_more_keys = True
                                        break
                                elif next_line == '}':
                                    break
                            
                            if has_comma_in_original and has_more_keys:
                                new_line += ','
                            
                            if comment_start >= 0:
                                comment_part = value_part[comment_start + 2:]
                                comment_part = comment_part.strip()
                                if comment_part:
                                    new_line += ' //' + comment_part
                            
                            new_lines.append(new_line)
                            continue
                
                new_lines.append(line)
            
            with open(target_file_path, 'w', encoding='utf-8-sig') as f:
                f.write('\n'.join(new_lines))
                
        except Exception as e:
            with open(target_file_path, 'w', encoding='utf-8') as f:
                 json.dump(data, f, ensure_ascii=False, indent=4)
    
    def _load_comparison_data_async(self):
        try:
            selected_mod = self.app.gui_manager.parent.mod_combo.get()
            selected_file = self.app.gui_manager.parent.file_combo.get()
            
            if not selected_mod or not selected_file:
                return
            
            translation_file_path = self.i18n_dir / "Translation" / selected_mod / selected_file
            original_file_path = self.find_matching_original_file(translation_file_path, selected_mod)
            
            if not translation_file_path.exists():
                return
            
            translation_data = self.load_json_with_comments(translation_file_path)
            
            self.app.current_translation_file = translation_file_path
            
            original_data = {}
            if original_file_path and original_file_path.exists():
                original_data = self.load_json_with_comments(original_file_path)
            
            self.app.root.after(0, self.app.translation_manager.display_comparison_data, translation_data, original_data)
            
        except Exception as e:
            self.app.root.after(0, self.app.log_message, f"刷新对比数据失败: {str(e)}", "ERROR")
    
    def refresh_comparison_data(self):
        threading.Thread(target=self._load_comparison_data_async, daemon=True).start()
    
    def refresh_mod_list(self):
        def scan_mods():
            try:
                available_mods = []
                
                original_dir = self.i18n_dir / "Original"
                
                if not original_dir.exists():
                    self.app.root.after(0, self.app.log_message, "Original目录不存在，请先提取i18n文件")
                    return
                
                for mod_path in original_dir.iterdir():
                    if mod_path.is_dir():
                        json_files = list(mod_path.rglob("*.json"))
                        if json_files:
                            available_mods.append({
                                'name': mod_path.name,
                                'path': mod_path,
                                'files': json_files
                            })
                
                self.app.root.after(0, self._update_mod_list_ui, available_mods)
                
            except Exception as e:
                self.app.root.after(0, self.app.log_message, f"刷新MOD列表失败: {str(e)}", "ERROR")
        
        threading.Thread(target=scan_mods, daemon=True).start()
    
    def _update_mod_list_ui(self, available_mods):
        try:
            self.available_mods = available_mods
            
            mod_names = [mod['name'] for mod in self.available_mods]
            self.app.gui_manager.parent.mod_combo['values'] = mod_names
            
            if mod_names:
                self.app.gui_manager.parent.mod_combo.set(mod_names[0])
                self.app.log_message(self.app.ui_text_manager.get_text("found_mods").format(len(mod_names), ', '.join(mod_names)))
                threading.Thread(target=self._load_mod_data_async, daemon=True).start()
            else:
                self.app.gui_manager.parent.mod_combo.set('')
                self.app.log_message(self.app.ui_text_manager.get_text("no_mods_found"))
                
        except Exception as e:
            self.app.log_message(f"更新MOD列表UI失败: {str(e)}", "ERROR")
    
    def _load_mod_data_async(self):
        try:
            selected_mod_name = self.app.gui_manager.parent.mod_combo.get()
            if not selected_mod_name:
                return
                
            selected_mod = None
            for mod in self.available_mods:
                if mod['name'] == selected_mod_name:
                    selected_mod = mod
                    break
            
            if selected_mod:
                self.app.current_mod_path = selected_mod['path']
                self.app.root.after(0, self.app.log_message, self.app.ui_text_manager.get_text("switch_to_mod").format(selected_mod['name']))
                
                self._load_file_list_async()
                self._load_comparison_data_async()
        except Exception as e:
            self.app.root.after(0, self.app.log_message, f"MOD数据加载失败: {str(e)}", "ERROR")
    
    def on_mod_change(self, event=None):
        threading.Thread(target=self._load_mod_data_async, daemon=True).start()
    
    def _load_file_list_async(self):
        try:
            available_files = []
            
            if hasattr(self.app, 'current_mod_path') and self.app.current_mod_path:
                translation_dir = self.i18n_dir / "Translation" / self.app.current_mod_path.name
                if translation_dir.exists():
                    json_files = list(translation_dir.rglob('*.json'))
                    if json_files:
                        for json_file in json_files:
                            rel_path = json_file.relative_to(translation_dir)
                            available_files.append({
                                'name': str(rel_path),
                                'path': json_file
                            })
                        
                        self.app.root.after(0, self._update_file_list_ui, available_files)
                    else:
                        self.app.root.after(0, self.app.log_message, self.app.get_ui_text("no_localization_files_found"))
                else:
                    self.app.root.after(0, self.app.log_message, self.app.get_ui_text("mod_translation_dir_not_exist"))
        except Exception as e:
            self.app.root.after(0, self.app.log_message, self.app.get_ui_text("refresh_file_list_failed").format(str(e)), "ERROR")
    
    def _update_file_list_ui(self, available_files):
        try:
            self.app.available_files = available_files
            
            file_names = [f['name'] for f in available_files]
            self.app.gui_manager.parent.file_combo['values'] = file_names
            
            if file_names:
                self.app.gui_manager.parent.file_combo.set(file_names[0])
                self.app.current_file_index = 0
                
            self.app.log_message(self.app.get_ui_text("found_localization_files").format(len(file_names)))
        except Exception as e:
            self.app.log_message(self.app.get_ui_text("refresh_file_list_failed").format(str(e)), "ERROR")
    
    def refresh_file_list(self):
        threading.Thread(target=self._load_file_list_async, daemon=True).start()
    
    def on_file_change(self, event=None):
        try:
            selected_file = self.app.gui_manager.parent.file_combo.get()
            if not selected_file:
                return
                
            self.app.log_message(f"切换到文件: {selected_file}")
            threading.Thread(target=self._load_comparison_data_async, daemon=True).start()
            
        except Exception as e:
            self.app.log_message(f"切换文件失败: {str(e)}", "ERROR")
    
    def find_matching_original_file(self, mod_name, file_name):
        try:
            extract_mod_dir = self.extract_dir / mod_name
            if not extract_mod_dir.exists():
                return None
            
            for root, dirs, files in os.walk(extract_mod_dir):
                if file_name in files:
                    return Path(root) / file_name
            
            return None
            
        except Exception:
            return None
     
    def import_mods(self):
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
        def extract():
            try:
                if self.extract_dir.exists():
                    shutil.rmtree(self.extract_dir)
                self.extract_dir.mkdir(parents=True, exist_ok=True)
                
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
        def extract():
            try:
                if self.i18n_dir.exists():
                    shutil.rmtree(self.i18n_dir)
                self.i18n_dir.mkdir(parents=True, exist_ok=True)
                
                original_dir = self.i18n_dir / "Original"
                translation_dir = self.i18n_dir / "Translation"
                original_dir.mkdir(parents=True, exist_ok=True)
                translation_dir.mkdir(parents=True, exist_ok=True)
                
                target_lang = self.app.target_language_var.get()
                lang_prefix = self.app.language_codes.get(target_lang, "en")
                
                for mod_dir in self.extract_dir.iterdir():
                    if not mod_dir.is_dir():
                        continue
                    
                    self.app.log_message(self.app.get_ui_text("processing_mod").format(mod_dir.name))
                    
                    i18n_folders = list(mod_dir.rglob("i18n"))
                    
                    for i18n_folder in i18n_folders:
                        if not i18n_folder.is_dir():
                            continue
                        
                        rel_path = i18n_folder.relative_to(self.extract_dir)
                        
                        default_json = i18n_folder / "default.json"
                        source_json = None
                        
                        if default_json.exists():
                            source_json = default_json
                        else:
                            json_files = list(i18n_folder.glob("*.json"))
                            if json_files:
                                source_json = json_files[0]
                        
                        if source_json:
                            target_original_dir = original_dir / rel_path
                            target_original_dir.mkdir(parents=True, exist_ok=True)
                            target_original = target_original_dir / source_json.name
                            shutil.copy2(source_json, target_original)
                            
                            target_translation_dir = translation_dir / rel_path
                            target_translation_dir.mkdir(parents=True, exist_ok=True)
                            
                            if source_json.name.lower() == "default.json":
                                target_translation = target_translation_dir / f"{lang_prefix}.json"
                            else:
                                target_translation = target_translation_dir / source_json.name
                            
                            shutil.copy2(source_json, target_translation)
                            
                            self.app.log_message(self.app.get_ui_text("extract_i18n_file").format(rel_path / source_json.name, target_translation.name))
                
                self.app.refresh_mod_list()
                
                def delayed_completion_message():
                    import time
                    time.sleep(2)
                    self.app.root.after(0, self.app.log_message, self.app.get_ui_text("i18n_extract_completed"))
                
                threading.Thread(target=delayed_completion_message, daemon=True).start()
                
            except Exception as e:
                self.app.log_message(self.app.get_ui_text("i18n_extract_failed").format(str(e)), "ERROR")
        
        threading.Thread(target=extract, daemon=True).start()
    

    
    def find_matching_original_file(self, translation_file_path, mod_name):
        original_dir = self.i18n_dir / "Original"
        translation_dir = self.i18n_dir / "Translation"
        
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
    
    def load_json_with_comments(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            lines = content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                if '//' in line:
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
                
                line = line.strip()
                if line.startswith('/*') or line.startswith('*') or line.endswith('*/'):
                    continue
                
                if line:
                    cleaned_lines.append(line)
            
            cleaned_content = '\n'.join(cleaned_lines)
            
            return json.loads(cleaned_content)
            
        except Exception as e:
            raise Exception(f"解析JSON文件失败 {file_path}: {str(e)}")
    
    def save_json_with_original_format(self, data, original_file_path, target_file_path):
        try:
            with open(original_file_path, 'r', encoding='utf-8-sig') as f:
                original_content = f.read()
            
            lines = original_content.split('\n')
            new_lines = []
            
            data_keys = list(data.keys())
            
            for i, line in enumerate(lines):
                if ':' in line and not line.strip().startswith('//') and not line.strip().startswith('/*'):
                    key_match = re.search(r'"([^"]+)"\s*:', line)
                    if key_match:
                        key = key_match.group(1)
                        if key in data:
                            value_part = line.split(':', 1)[1]
                            indent = line[:line.find('"')]
                            new_value = json.dumps(data[key], ensure_ascii=False)
                            new_line = f'{indent}"{key}": {new_value}'
                            
                            def find_comment_start(text):
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
                            
                            value_before_comment = value_part[:comment_start] if comment_start >= 0 else value_part
                            has_comma_in_original = ',' in value_before_comment
                            
                            has_more_keys = False
                            for j in range(i + 1, len(lines)):
                                next_line = lines[j].strip()
                                if next_line and not next_line.startswith('//') and not next_line.startswith('/*') and ':' in next_line:
                                    next_key_match = re.search(r'"([^"]+)"\s*:', next_line)
                                    if next_key_match and next_key_match.group(1) in data:
                                        has_more_keys = True
                                        break
                                elif next_line == '}':
                                    break
                            
                            if has_comma_in_original and has_more_keys:
                                new_line += ','
                            
                            if comment_start >= 0:
                                comment_part = value_part[comment_start + 2:]
                                comment_part = comment_part.strip()
                                if comment_part:
                                    new_line += ' //' + comment_part
                            
                            new_lines.append(new_line)
                            continue
                
                new_lines.append(line)
            
            with open(target_file_path, 'w', encoding='utf-8-sig') as f:
                f.write('\n'.join(new_lines))
                
        except Exception as e:
            with open(target_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
    
    def save_translation_data(self, mod_name, file_name, data):
        try:
            translation_dir = self.i18n_dir / "Translation"
            mod_dir = translation_dir / mod_name
            
            file_path = mod_dir / file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            original_file = self.find_matching_original_file(file_path, mod_name)
            
            if original_file and original_file.exists():
                self.save_json_with_original_format(data, original_file, file_path)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.app.log_message(f"已保存翻译文件: {file_path}")
            
        except Exception as e:
            self.app.log_message(f"保存翻译文件失败: {str(e)}", "ERROR")
    
    def save_translation_files(self):
        try:
            translation_dir = self.i18n_dir / "Translation"
            if not translation_dir.exists():
                self.app.log_message(self.app.get_ui_text("translation_dir_not_exist"), "ERROR")
                return
            
            if not hasattr(self.app, 'current_translation_data'):
                self.app.log_message(self.app.get_ui_text("no_translation_data_to_save"), "WARNING")
                return
            
            for i in range(self.app.translation_listbox.size()):
                if i < len(self.app.current_translation_keys):
                    key = self.app.current_translation_keys[i]
                    value = self.app.translation_listbox.get(i)
                    self.app.current_translation_data[key] = value
            
            if hasattr(self.app, 'current_translation_file'):
                original_file = None
                if hasattr(self.app, 'current_mod_path'):
                    mod_name = self.app.current_mod_path.name
                    original_file = self.find_matching_original_file(self.app.current_translation_file, mod_name)
                
                if original_file and original_file.exists():
                    self.save_json_with_original_format(
                        self.app.current_translation_data, 
                        original_file, 
                        self.app.current_translation_file
                    )
                else:
                    with open(self.app.current_translation_file, 'w', encoding='utf-8') as f:
                        json.dump(self.app.current_translation_data, f, ensure_ascii=False, indent=2)
                
                self.app.log_message(self.app.get_ui_text("translation_file_saved").format(self.app.current_translation_file.name))
            else:
                self.app.log_message(self.app.get_ui_text("cannot_determine_save_path"), "ERROR")
                
        except Exception as e:
            self.app.log_message(self.app.get_ui_text("save_translation_file_failed").format(str(e)), "ERROR")
    
    def recompress_mods(self):
        def compress():
            try:
                if self.compress_dir.exists():
                    shutil.rmtree(self.compress_dir)
                self.compress_dir.mkdir(parents=True, exist_ok=True)
                
                selected_language = self.app.target_language_var.get()
                language_code = self.app.language_codes.get(selected_language, "zh")
                
                translation_dir = self.i18n_dir / "Translation"
                if not translation_dir.exists():
                    self.app.log_message(self.app.get_ui_text("translation_dir_not_exist"), "ERROR")
                    return
                
                for mod_dir in translation_dir.iterdir():
                    if not mod_dir.is_dir():
                        continue
                    
                    self.app.log_message(self.app.get_ui_text("compressing_mod").format(mod_dir.name))
                    
                    zip_filename = f"{language_code}_{mod_dir.name}.zip"
                    zip_path = self.compress_dir / zip_filename
                    
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for file_path in mod_dir.rglob('*'):
                            if file_path.is_file():
                                arcname = file_path.relative_to(mod_dir)
                                zipf.write(file_path, arcname)
                    
                    self.app.log_message(self.app.get_ui_text("compress_success").format(zip_path.name))
                
                self.app.log_message(self.app.get_ui_text("recompress_completed"))
                
                try:
                    if self.compress_dir.exists():
                        subprocess.run(['explorer', str(self.compress_dir)], check=False)
                except Exception as folder_error:
                    print(f"打开压缩文件夹失败: {folder_error}")
            except Exception as e:
                self.app.log_message(self.app.get_ui_text("compress_error").format(str(e)), "ERROR")
        
        threading.Thread(target=compress, daemon=True).start()
    
    def clear_data_directories(self):
        try:
            directories_to_clear = [
                self.import_dir,
                self.extract_dir,
                self.i18n_dir
            ]
            
            for directory in directories_to_clear:
                if directory.exists():
                    for item in directory.iterdir():
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    
                    self.app.log_message(self.app.get_ui_text("clear_directory_success").format(directory.name))
                else:
                    self.app.log_message(self.app.get_ui_text("directory_not_exist").format(directory.name), "WARNING")
            
            self.app.refresh_mod_list()
            
        except Exception as e:
            raise Exception(self.app.get_ui_text("clear_directories_error").format(str(e)))