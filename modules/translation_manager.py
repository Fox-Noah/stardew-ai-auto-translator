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
        """自动翻译或停止翻译"""
        # 如果正在翻译，则停止翻译
        if self.is_translating:
            self.stop_translation()
            return
            
        # 开始翻译
        self.start_translation()
    
    def start_translation(self):
        """开始翻译"""
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
                
                # 检查是否选择了MOD
                if not self.main_app.current_mod_path:
                    self.main_app.log_message(self.main_app.get_ui_text("select_mod_first"), "ERROR")
                    return
                
                # 检查是否选择了文件
                if not hasattr(self.main_app, 'current_file_index') or self.main_app.current_file_index < 0:
                    self.main_app.log_message(self.main_app.get_ui_text("select_file_first"), "ERROR")
                    return
                
                # 检查是否有可用文件
                if not hasattr(self.main_app, 'available_files') or not self.main_app.available_files:
                    self.main_app.log_message(self.main_app.get_ui_text("no_available_translation_files"), "ERROR")
                    return
                
                # 获取用户选择的文件
                selected_file = self.main_app.available_files[self.main_app.current_file_index]
                json_files = [selected_file['path']]
                
                self.main_app.log_message(self.main_app.get_ui_text("start_translate_selected_file").format(selected_file['name']))
                
                self.main_app.log_message(self.main_app.get_ui_text("start_translate_mod").format(self.main_app.current_mod_path.name))
                
                # 记录当前翻译的文件，用于后续自动跳转
                self.main_app.current_translating_file_index = self.main_app.current_file_index
                
                # 计算总的翻译条目数
                total_entries = 0
                for json_file in json_files:
                    try:
                        data = self.main_app.file_manager.load_json_with_comments(json_file)
                        total_entries += sum(1 for value in data.values() if isinstance(value, str))
                    except:
                        continue
                
                # 初始化进度和自动保存计数器
                current_entry = 0
                auto_save_counter = 0
                auto_save_interval = getattr(self.main_app, 'auto_save_interval', 10)
                batch_size = getattr(self.main_app, 'batch_size', 5)
                self.main_app.update_progress_display(current_entry, total_entries)
                
                for json_file in json_files:
                    # 检查是否需要停止翻译
                    if not self.is_translating:
                        self.main_app.log_message("翻译已停止")
                        return
                        
                    self.main_app.log_message(self.main_app.get_ui_text("translating_file").format(json_file.relative_to(self.main_app.file_manager.i18n_dir)))
                    
                    try:
                        # 读取 JSON 文件（支持注释和BOM）
                        data = self.main_app.file_manager.load_json_with_comments(json_file)
                        
                        # 收集需要翻译的条目 - 智能对比原文和译文
                        items_to_translate = []
                        keys_to_translate = []
                        translated_data = data.copy()  # 保留原有数据
                        
                        # 尝试加载对应的原文文件进行对比
                        original_data = None
                        try:
                            # 智能匹配原文件
                            mod_name = self.main_app.current_mod_path.name
                            original_file = self.main_app.find_matching_original_file(json_file, mod_name)
                            
                            if original_file and original_file.exists():
                                original_data = self.main_app.file_manager.load_json_with_comments(original_file)
                                self.main_app.log_message(self.main_app.get_ui_text("loaded_original_file").format(original_file.name))
                        except Exception as e:
                            self.main_app.log_message(f"加载原文文件失败，将翻译所有条目: {str(e)}")
                        
                        # 智能判断哪些条目需要翻译
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
                        
                        # 详细的日志信息
                        if original_data:
                            self.main_app.log_message(self.main_app.get_ui_text("smart_comparison_complete").format(total_text_entries, len(items_to_translate), skipped_entries))
                        else:
                            self.main_app.log_message(self.main_app.get_ui_text("found_entries_no_comparison").format(len(items_to_translate)))
                        
                        # 如果没有需要翻译的条目，跳过这个文件
                        if not items_to_translate:
                            self.main_app.log_message(self.main_app.get_ui_text("file_no_translation_needed").format(json_file.name))
                            continue
                        
                        # 定义结果回调函数
                        def result_callback(index, original_text, translated_text):
                            if not self.is_translating:
                                return
                            
                            key = keys_to_translate[index]
                            translated_data[key] = translated_text
                            self.main_app.log_message(self.main_app.get_ui_text("translate_entry").format(key, original_text, translated_text))
                            
                            # 如果当前文件是显示的文件，实时更新界面
                            if hasattr(self.main_app, 'current_translation_file') and json_file == self.main_app.current_translation_file:
                                if hasattr(self.main_app, 'update_translation_display'):
                                    self.main_app.root.after(0, lambda k=key, t=translated_text: self.main_app.update_translation_display(k, t))
                            
                            # 更新进度
                            nonlocal current_entry, auto_save_counter
                            current_entry += 1
                            auto_save_counter += 1
                            self.main_app.update_progress_display(current_entry, total_entries)
                            
                            # 自动保存检查
                            if auto_save_counter >= auto_save_interval:
                                self.main_app.file_manager.save_json_with_original_format(translated_data, json_file, json_file)
                                self.main_app.log_message(self.main_app.get_ui_text("auto_saved_translations").format(auto_save_interval))
                                auto_save_counter = 0
                        
                        # 定义停止检查函数
                        def stop_check():
                            return not self.is_translating
                        
                        # 使用批量翻译
                        try:
                            batch_size = int(self.main_app.batch_size_var.get())
                            self.main_app.translator.translate_batch_async(
                                items_to_translate,
                                target_lang_en,
                                batch_size,
                                None,  # progress_callback
                                stop_check,
                                result_callback
                            )
                        except Exception as e:
                            self.main_app.log_message(f"批量翻译失败: {str(e)}", "ERROR")
                            # 回退到逐条翻译
                            for i, (key, value) in enumerate(zip(keys_to_translate, items_to_translate)):
                                if not self.is_translating:
                                    break
                                translated_text = self.main_app.translator.translate_single_text(value, target_lang_en)
                                result_callback(i, value, translated_text)
                        
                        # 检查是否被停止
                        if not self.is_translating:
                            return
                        
                        # 最终保存文件（保持原始格式）
                        self.main_app.file_manager.save_json_with_original_format(translated_data, json_file, json_file)
                        self.main_app.log_message(f"已保存翻译文件: {json_file.name}")
                        
                    except Exception as e:
                        self.main_app.log_message(self.main_app.get_ui_text("translate_file_failed").format(json_file.name, str(e)), "ERROR")
                
                # 再次检查是否被停止
                if not self.is_translating:
                    return
                
                self.main_app.log_message(self.main_app.get_ui_text("auto_translate_completed"))
                
                # 翻译正常完成后自动跳转到下一个文件
                self.auto_switch_to_next_file()
                
            except Exception as e:
                self.main_app.log_message(self.main_app.get_ui_text("auto_translate_error").format(str(e)), "ERROR")
            finally:
                # 重置翻译状态和按钮文本
                self.reset_translation_state()
        
        self.translation_thread = threading.Thread(target=translate, daemon=True)
        self.translation_thread.start()
    
    def stop_translation(self):
        """停止翻译"""
        self.main_app.log_message(self.main_app.get_ui_text("stopping_translation"))
        self.reset_translation_state()
        self.main_app.log_message(self.main_app.get_ui_text("translation_stopped"))
    
    def reset_translation_state(self):
        """重置翻译状态"""
        self.is_translating = False
        self.main_app.translate_btn.config(text=self.main_app.get_ui_text("auto_translate"))
        # 清空进度显示
        self.main_app.update_progress_display(0, 0)
        self.translation_thread = None
    
    def auto_switch_to_next_file(self):
        """自动切换到下一个文件"""
        try:
            # 检查是否有可用文件列表
            if not hasattr(self.main_app, 'available_files') or not self.main_app.available_files:
                self.main_app.log_message("没有可用的文件列表")
                return
            
            # 检查当前文件索引
            if not hasattr(self.main_app, 'current_file_index'):
                self.main_app.current_file_index = 0
            
            # 计算下一个文件的索引
            next_index = self.main_app.current_file_index + 1
            
            # 检查是否还有下一个文件
            if next_index < len(self.main_app.available_files):
                # 切换到下一个文件
                self.main_app.current_file_index = next_index
                
                # 获取下一个文件信息
                next_file = self.main_app.available_files[next_index]
                
                # 更新下拉菜单选中项
                self.main_app.gui_manager.parent.file_combo.set(next_file['name'])
                
                self.main_app.log_message(f"自动切换到下一个文件: {next_file['name']}")
                
                # 手动触发文件切换事件，更新界面显示
                self.main_app.file_manager.on_file_change()
                
                # 延迟一段时间后自动开始翻译下一个文件
                def delayed_auto_translate():
                    if not self.is_translating:  # 确保当前没有在翻译
                        self.main_app.log_message(f"开始自动翻译下一个文件: {next_file['name']}")
                        self.start_translation()
                
                # 延迟2秒后开始翻译，确保界面更新完成
                self.main_app.root.after(2000, delayed_auto_translate)
                
            else:
                self.main_app.log_message("所有文件翻译完成！")
                
        except Exception as e:
            self.main_app.log_message(f"自动切换文件失败: {str(e)}", "ERROR")
    
    def update_translation_display(self, key, translated_text):
        """实时更新翻译显示"""
        try:
            if hasattr(self.main_app, 'current_translation_keys') and key in self.main_app.current_translation_keys:
                index = self.main_app.current_translation_keys.index(key)
                if index < self.main_app.translation_listbox.size():
                    self.main_app.translation_listbox.delete(index)
                    self.main_app.translation_listbox.insert(index, translated_text)
                    # 更新当前翻译数据
                    if hasattr(self.main_app, 'current_translation_data'):
                        self.main_app.current_translation_data[key] = translated_text
        except Exception as e:
            self.main_app.log_message(self.main_app.get_ui_text("update_translation_display_failed").format(str(e)), "ERROR")
    
    def _should_translate_text(self, key, translation_text, original_data=None):
        """智能判断文本是否需要翻译
        
        Args:
            key: 文本的键
            translation_text: 当前的翻译文本
            original_data: 原文数据字典，可选
        
        Returns:
            bool: 是否需要翻译
        """
        # 如果翻译文本为空，需要翻译
        if not translation_text or not translation_text.strip():
            return True
        
        # 如果有原文数据，进行对比
        if original_data and key in original_data:
            original_text = original_data[key]
            
            # 如果翻译文本与原文相同，需要翻译
            if translation_text == original_text:
                return True
            
            # 如果翻译文本主要是英文且与原文不同，可能需要重新翻译
            if self._is_mainly_english(translation_text) and translation_text != original_text:
                return True
        else:
            # 没有原文数据时，如果翻译文本主要是英文，需要翻译
            if self._is_mainly_english(translation_text):
                return True
        
        # 其他情况不需要翻译
        return False
    
    def _is_mainly_english(self, text):
        """判断文本是否主要是英文
        
        Args:
            text: 要检查的文本
        
        Returns:
            bool: 是否主要是英文
        """
        if not text or not text.strip():
            return False
        
        # 移除空格和标点符号
        clean_text = re.sub(r'[\s\W]', '', text)
        if not clean_text:
            return False
        
        # 计算英文字符比例
        english_chars = sum(1 for c in clean_text if ord(c) < 128 and c.isalpha())
        total_chars = len(clean_text)
        
        # 如果英文字符占比超过70%，认为主要是英文
        return english_chars / total_chars > 0.7
    
    def display_comparison_data(self, translation_data, original_data):
        """显示对比数据"""
        try:
            # 清空列表框
            self.main_app.original_listbox.delete(0, tk.END)
            self.main_app.translation_listbox.delete(0, tk.END)
            
            # 保存当前原文和翻译数据，用于编辑和保存功能
            self.main_app.current_original_data = original_data.copy()
            self.main_app.current_translation_data = translation_data.copy()
            self.main_app.current_translation_keys = list(original_data.keys()) if original_data else list(translation_data.keys())
            
            # 遍历数据（优先使用原文数据，如果没有则使用翻译数据）
            data_to_iterate = original_data if original_data else translation_data
            for key in self.main_app.current_translation_keys:
                # 获取原文和译文
                original_value = original_data.get(key, self.main_app.get_ui_text("untranslated_text")) if original_data else self.main_app.get_ui_text("untranslated_text")
                translation_value = translation_data.get(key, self.main_app.get_ui_text("untranslated_text"))
                
                # 格式化显示文本 - 只显示值，不显示键
                original_text = original_value
                translation_text = translation_value
                
                # 添加到列表框
                self.main_app.original_listbox.insert(tk.END, original_text)
                self.main_app.translation_listbox.insert(tk.END, translation_text)
            
            self.main_app.log_message(self.main_app.get_ui_text("comparison_data_displayed").format(len(self.main_app.current_translation_keys)))
             
        except Exception as e:
             self.main_app.log_message(self.main_app.get_ui_text("display_comparison_failed").format(str(e)), "ERROR")