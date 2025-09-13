import threading
import time
import re
import tkinter as tk
from pathlib import Path

class TranslationManager:
    def __init__(self, main_app):
        self.main_app = main_app
        self.is_translating = False
        self.translation_thread = None
    
    def auto_translate(self):
        if self.is_translating:
            self.stop_translation()
            return
            
        self.start_translation()
    
    def start_translation(self):
        self.is_translating = True
        self.main_app.translate_btn.config(text=self.main_app.get_ui_text("stop_translate"))
        
        def translate():
            try:
                if not self.main_app.available_models:
                    self.main_app.log_message(self.main_app.get_ui_text("ollama_model_required"), "ERROR")
                    return
                
                target_lang = self.main_app.target_language_var.get()
                target_lang_en = self.main_app.language_codes[target_lang]
                
                self.main_app.log_message(self.main_app.get_ui_text("start_auto_translate").format(target_lang))
                
                if not self.main_app.current_mod_path:
                    self.main_app.log_message(self.main_app.get_ui_text("select_mod_first"), "ERROR")
                    return
                
                if not hasattr(self.main_app, 'current_file_index') or self.main_app.current_file_index < 0:
                    self.main_app.log_message(self.main_app.get_ui_text("select_file_first"), "ERROR")
                    return
                
                if not hasattr(self.main_app, 'available_files') or not self.main_app.available_files:
                    self.main_app.log_message(self.main_app.get_ui_text("no_available_translation_files"), "ERROR")
                    return
                
                selected_file = self.main_app.available_files[self.main_app.current_file_index]
                json_files = [selected_file['path']]
                
                self.main_app.log_message(self.main_app.get_ui_text("start_translate_selected_file").format(selected_file['name']))
                
                self.main_app.log_message(self.main_app.get_ui_text("start_translate_mod").format(self.main_app.current_mod_path.name))
                
                self.main_app.current_translating_file_index = self.main_app.current_file_index
                
                total_entries = 0
                for json_file in json_files:
                    try:
                        data = self.main_app.file_manager.load_json_with_comments(json_file)
                        total_entries += sum(1 for value in data.values() if isinstance(value, str))
                    except:
                        continue
                
                current_entry = 0
                auto_save_counter = 0
                auto_save_interval = getattr(self.main_app, 'auto_save_interval', 10)
                batch_size = getattr(self.main_app, 'batch_size', 5)
                self.main_app.update_progress_display(current_entry, total_entries)
                
                for json_file in json_files:
                    if not self.is_translating:
                        self.main_app.log_message("翻译已停止")
                        return
                        
                    self.main_app.log_message(self.main_app.get_ui_text("translating_file").format(json_file.relative_to(self.main_app.file_manager.i18n_dir)))
                    
                    try:
                        data = self.main_app.file_manager.load_json_with_comments(json_file)
                        
                        items_to_translate = []
                        keys_to_translate = []
                        translated_data = data.copy()
                        
                        original_data = None
                        try:
                            mod_name = self.main_app.current_mod_path.name
                            original_file = self.main_app.find_matching_original_file(json_file, mod_name)
                            
                            if original_file and original_file.exists():
                                original_data = self.main_app.file_manager.load_json_with_comments(original_file)
                                self.main_app.log_message(self.main_app.get_ui_text("loaded_original_file").format(original_file.name))
                        except Exception as e:
                            self.main_app.log_message(f"加载原文文件失败，将翻译所有条目: {str(e)}")
                        
                        total_text_entries = 0
                        skipped_entries = 0
                        
                        for key, value in data.items():
                            if isinstance(value, str) and value.strip() and not value.startswith("["):
                                total_text_entries += 1
                                needs_translation = self._should_translate_text(key, value, original_data)
                                if needs_translation:
                                    items_to_translate.append(value)
                                    keys_to_translate.append(key)
                                else:
                                    skipped_entries += 1
                        
                        if original_data:
                            self.main_app.log_message(self.main_app.get_ui_text("smart_comparison_complete").format(total_text_entries, len(items_to_translate), skipped_entries))
                        else:
                            self.main_app.log_message(self.main_app.get_ui_text("found_entries_no_comparison").format(len(items_to_translate)))
                        
                        if not items_to_translate:
                            self.main_app.log_message(self.main_app.get_ui_text("file_no_translation_needed").format(json_file.name))
                            continue
                        
                        def result_callback(index, original_text, translated_text):
                            if not self.is_translating:
                                return
                            
                            key = keys_to_translate[index]
                            translated_data[key] = translated_text
                            self.main_app.log_message(self.main_app.get_ui_text("translate_entry").format(key, original_text, translated_text))
                            
                            if hasattr(self.main_app, 'current_translation_file') and json_file == self.main_app.current_translation_file:
                                if hasattr(self.main_app, 'update_translation_display'):
                                    self.main_app.root.after(0, lambda k=key, t=translated_text: self.main_app.update_translation_display(k, t))
                            
                            nonlocal current_entry, auto_save_counter
                            current_entry += 1
                            auto_save_counter += 1
                            self.main_app.update_progress_display(current_entry, total_entries)
                            
                            if auto_save_counter >= auto_save_interval:
                                self.main_app.file_manager.save_json_with_original_format(translated_data, json_file, json_file)
                                self.main_app.log_message(self.main_app.get_ui_text("auto_saved_translations").format(auto_save_interval))
                                auto_save_counter = 0
                        
                        def stop_check():
                            return not self.is_translating
                        
                        try:
                            batch_size = int(self.main_app.batch_size_var.get())
                            self.main_app.translator.translate_batch_async(
                                items_to_translate,
                                target_lang_en,
                                batch_size,
                                None,
                                stop_check,
                                result_callback
                            )
                        except Exception as e:
                            self.main_app.log_message(f"批量翻译失败: {str(e)}", "ERROR")
                            for i, (key, value) in enumerate(zip(keys_to_translate, items_to_translate)):
                                if not self.is_translating:
                                    break
                                translated_text = self.main_app.translator.translate_single_text(value, target_lang_en)
                                result_callback(i, value, translated_text)
                        
                        if not self.is_translating:
                            return
                        
                        self.main_app.file_manager.save_json_with_original_format(translated_data, json_file, json_file)
                        self.main_app.log_message(f"已保存翻译文件: {json_file.name}")
                        
                    except Exception as e:
                        self.main_app.log_message(self.main_app.get_ui_text("translate_file_failed").format(json_file.name, str(e)), "ERROR")
                
                if not self.is_translating:
                    return
                
                self.main_app.log_message(self.main_app.get_ui_text("auto_translate_completed"))
                
                self.auto_switch_to_next_file()
                
            except Exception as e:
                self.main_app.log_message(self.main_app.get_ui_text("auto_translate_error").format(str(e)), "ERROR")
            finally:
                self.reset_translation_state()
        
        self.translation_thread = threading.Thread(target=translate, daemon=True)
        self.translation_thread.start()
    
    def stop_translation(self):
        self.main_app.log_message(self.main_app.get_ui_text("stopping_translation"))
        self.reset_translation_state()
        self.main_app.log_message(self.main_app.get_ui_text("translation_stopped"))
    
    def reset_translation_state(self):
        self.is_translating = False
        self.main_app.translate_btn.config(text=self.main_app.get_ui_text("auto_translate"))
        self.main_app.update_progress_display(0, 0)
        self.translation_thread = None
    
    def auto_switch_to_next_file(self):
        try:
            if not hasattr(self.main_app, 'available_files') or not self.main_app.available_files:
                self.main_app.log_message("没有可用的文件列表")
                return
            
            if not hasattr(self.main_app, 'current_file_index'):
                self.main_app.current_file_index = 0
            
            next_index = self.main_app.current_file_index + 1
            
            if next_index < len(self.main_app.available_files):
                self.main_app.current_file_index = next_index
                
                next_file = self.main_app.available_files[next_index]
                
                self.main_app.gui_manager.parent.file_combo.set(next_file['name'])
                
                self.main_app.log_message(f"自动切换到下一个文件: {next_file['name']}")
                
                self.main_app.file_manager.on_file_change()
                
                def delayed_auto_translate():
                    if not self.is_translating:
                        self.main_app.log_message(f"开始自动翻译下一个文件: {next_file['name']}")
                        self.start_translation()
                
                self.main_app.root.after(2000, delayed_auto_translate)
                
            else:
                self.main_app.log_message("所有文件翻译完成！")
                
        except Exception as e:
            self.main_app.log_message(f"自动切换文件失败: {str(e)}", "ERROR")
    
    def update_translation_display(self, key, translated_text):
        try:
            if hasattr(self.main_app, 'current_translation_keys') and key in self.main_app.current_translation_keys:
                index = self.main_app.current_translation_keys.index(key)
                if index < self.main_app.translation_listbox.size():
                    self.main_app.translation_listbox.delete(index)
                    self.main_app.translation_listbox.insert(index, translated_text)
                    if hasattr(self.main_app, 'current_translation_data'):
                        self.main_app.current_translation_data[key] = translated_text
        except Exception as e:
            self.main_app.log_message(self.main_app.get_ui_text("update_translation_display_failed").format(str(e)), "ERROR")
    
    def _should_translate_text(self, key, translation_text, original_data=None):
        if not translation_text or not translation_text.strip():
            return True
        
        if original_data and key in original_data:
            original_text = original_data[key]
            
            if translation_text == original_text:
                return True
            
            if self._is_mainly_english(translation_text) and translation_text != original_text:
                return True
        else:
            if self._is_mainly_english(translation_text):
                return True
        
        return False
    
    def _is_mainly_english(self, text):
        if not text or not text.strip():
            return False
        
        clean_text = re.sub(r'[\s\W]', '', text)
        if not clean_text:
            return False
        
        english_chars = sum(1 for c in clean_text if ord(c) < 128 and c.isalpha())
        total_chars = len(clean_text)
        
        return english_chars / total_chars > 0.7
    
    def display_comparison_data(self, translation_data, original_data):
        try:
            self.main_app.original_listbox.delete(0, tk.END)
            self.main_app.translation_listbox.delete(0, tk.END)
            
            self.main_app.current_original_data = original_data.copy()
            self.main_app.current_translation_data = translation_data.copy()
            self.main_app.current_translation_keys = list(original_data.keys()) if original_data else list(translation_data.keys())
            
            data_to_iterate = original_data if original_data else translation_data
            for key in self.main_app.current_translation_keys:
                original_value = original_data.get(key, self.main_app.get_ui_text("untranslated_text")) if original_data else self.main_app.get_ui_text("untranslated_text")
                translation_value = translation_data.get(key, self.main_app.get_ui_text("untranslated_text"))
                
                original_text = original_value
                translation_text = translation_value
                
                self.main_app.original_listbox.insert(tk.END, original_text)
                self.main_app.translation_listbox.insert(tk.END, translation_text)
            
            self.main_app.log_message(self.main_app.get_ui_text("comparison_data_displayed").format(len(self.main_app.current_translation_keys)))
             
        except Exception as e:
             self.main_app.log_message(self.main_app.get_ui_text("display_comparison_failed").format(str(e)), "ERROR")