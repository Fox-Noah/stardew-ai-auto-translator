import threading
import time
import re
import tkinter as tk
from pathlib import Path
from .mod_translation import TranslationFile

class TranslationManager:
    def __init__(self, main_app):
        self.main_app = main_app
        self.is_translating = False
        self.translation_thread = None
        self.cancel_event = threading.Event()
        self.commit_lock = threading.Lock()
    
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
        if self.translation_thread and self.translation_thread.is_alive():
            self.main_app.log_message('当前请求尚未结束，请等待后再启动', 'WARNING')
            return
        try:
            if self.main_app.file_manager.scanning:
                raise ValueError('目录扫描尚未结束，请稍后开始翻译')
            index = self.main_app.current_file_index
            files = self.main_app.available_files[index:]
            if index < 0 or not files:
                raise ValueError('请先选择 MOD 和翻译文件')
            service = self.main_app.create_translation_service()
            language = self.main_app.target_languages[self.main_app.target_language_var.get()]
            batch_size = int(self.main_app.batch_size_var.get())
            if not 1 <= batch_size <= 32:
                raise ValueError('并发数量必须在 1 到 32 之间')
            tasks = [file['task'] for file in files]
            language_code = self.main_app.language_codes[self.main_app.target_language_var.get()]
            if any(task.kind == 'i18n' and task.target.name.casefold() != f'{language_code}.json' for task in tasks):
                raise ValueError('目标语言已改变，请刷新 MOD 列表后重试')
        except (ValueError, KeyError, IndexError) as error:
            self.main_app.log_message(str(error), 'ERROR')
            return
        self.cancel_event.clear()
        self.main_app.file_manager.selection_generation = getattr(self.main_app.file_manager, 'selection_generation', 0) + 1
        self.is_translating = True
        self.main_app.translator = service
        self.main_app.translate_btn.config(text=self.main_app.get_ui_text("stop_translate"))
        self._set_selection_state('disabled')

        def translate():
            try:
                for task_index, task in enumerate(tasks):
                    if self.cancel_event.is_set():
                        return
                    document = TranslationFile(task)
                    if not document.entries:
                        self.main_app.log_message(f'未找到可安全翻译的文本，跳过：{task.source}', 'WARNING')
                        continue
                    translated = document.reusable(service.core)
                    document.completed_paths.update(translated)
                    pending = [path for path in document.entries if path not in translated]
                    preview = dict(document.entries)
                    preview.update(translated)
                    self.main_app.root.after(0, self._show_document, document, preview, index + task_index)
                    self.main_app.log_message(f'翻译：{task.source}；待处理 {len(pending)} 条')

                    def result_callback(position, original, result):
                        translated[pending[position]] = result
                        document.completed_paths.add(pending[position])
                        self.main_app.root.after(0, self.main_app.update_translation_display, pending[position], result)
                        self.main_app.root.after(0, self.main_app.update_progress_display, len(translated), len(document.entries))

                    service.translate_batch_async(
                        [document.entries[path] for path in pending], language, batch_size,
                        stop_check=self.cancel_event.is_set, result_callback=result_callback)
                    with self.commit_lock:
                        document.save(translated, service.core, self.cancel_event.is_set)
                    self.main_app.log_message(f'已安全保存：{task.target}')
                if not self.cancel_event.is_set():
                    self.main_app.log_message('所选 MOD 的翻译已完成')
            except Exception as error:
                self.main_app.log_message(f'当前文件未保存：{error}', 'ERROR')
            finally:
                self.main_app.root.after(0, self.reset_translation_state)
        
        self.translation_thread = threading.Thread(target=translate, daemon=True)
        self.translation_thread.start()
    
    def stop_translation(self):
        """停止翻译"""
        self.main_app.log_message(self.main_app.get_ui_text("stopping_translation"))
        with self.commit_lock:
            self.cancel_event.set()
        self.main_app.log_message('已请求停止；等待进行中的请求结束，当前文件不会写入')
    
    def reset_translation_state(self):
        """重置翻译状态"""
        self.is_translating = False
        self.main_app.translate_btn.config(text=self.main_app.get_ui_text("auto_translate"))
        # 清空进度显示
        self.main_app.update_progress_display(0, 0)
        self._set_selection_state('normal')

    def _set_selection_state(self, state):
        for name in ('mod_combo', 'file_combo', 'model_combo', 'language_combo', 'provider_settings_btn',
                     'select_directory_btn', 'settings_btn', 'save_translation_btn', 'import_btn',
                     'extract_btn', 'extract_i18n_btn', 'refresh_models_btn', 'clear_dirs_btn', 'restore_backup_btn',
                     'refresh_mods_btn'):
            widget = getattr(self.main_app, name, None)
            if widget is not None:
                restored = 'readonly' if name in ('mod_combo', 'file_combo', 'language_combo') else 'normal'
                widget.config(state='disabled' if state == 'disabled' else restored)

    def _show_document(self, document, preview, index):
        self.main_app.current_file_index = index
        self.main_app.file_combo.set(self.main_app.available_files[index]['name'])
        self.main_app.current_document = document
        self.main_app.current_translation_file = document.task.target
        self.display_comparison_data(preview, document.entries)
    
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
