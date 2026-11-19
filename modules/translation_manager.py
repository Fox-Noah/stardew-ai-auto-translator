import queue
import threading
import time
import re
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from .mod_translation import TranslationFile

class TranslationManager:
    def __init__(self, main_app):
        self.main_app = main_app
        self.is_translating = False
        self.translation_thread = None
        self.cancel_event = threading.Event()
        self.commit_lock = threading.Lock()
        self.active_files = []
        self.current_file = None
    
    def auto_translate(self):
        """自动翻译或停止翻译"""
        # 如果正在翻译，则停止翻译
        if self.is_translating:
            self.stop_translation()
            return
            
        # 开始翻译
        self.start_translation()
    
    def start_translation(self, all_mods=None):
        """开始旧式单文件翻译或批量 MOD 翻译。"""
        if self.is_translating:
            return
        if all_mods is None:
            self._start_single_translation()
            return
        if hasattr(self.main_app, 'workbench'):
            self._start_mod_translation(all_mods)
            return
        self._start_single_translation()

    def _start_worker(self, service, translate):
        cancel_event = self.cancel_event = threading.Event()
        updates = queue.SimpleQueue()

        def post(callback, *args):
            updates.put((callback, args))

        def run():
            try:
                translate(cancel_event.is_set, post)
            finally:
                post(self._finish_translation)

        def poll():
            if cancel_event is not self.cancel_event or cancel_event.is_set() or not self.is_translating:
                return
            try:
                for _ in range(64):
                    try:
                        callback, args = updates.get_nowait()
                    except queue.Empty:
                        break
                    callback(*args)
                    if not self.is_translating or cancel_event.is_set():
                        return
            finally:
                if self.is_translating and cancel_event is self.cancel_event and not cancel_event.is_set():
                    self.main_app.root.after(25, poll)

        self._set_selection_state('disabled')
        self.main_app.translate_btn.config(text=self.main_app.get_ui_text('stop_translate'))
        self.main_app.translator = service
        self.is_translating = True
        self.translation_thread = threading.Thread(target=run, daemon=True)
        self.translation_thread.start()
        self.main_app.root.after(0, poll)

    def _start_mod_translation(self, all_mods):
        try:
            if self.main_app.file_manager.scanning:
                raise ValueError('目录扫描尚未结束，请稍后开始翻译')
            service = self.main_app.create_translation_service()
            language = self.main_app.target_languages[self.main_app.target_language_var.get()]
            batch_size = int(self.main_app.batch_size_var.get())
            if not 1 <= batch_size <= 32:
                raise ValueError('并发数量必须在 1 到 32 之间')
            mods = list(self.main_app.file_manager.available_mods)
            if not all_mods:
                mods = list(self.main_app.workbench.selected_mods())
            if not mods:
                raise ValueError('请先选择要翻译的 MOD')
            approvals = {}
            if not all_mods:
                for mod in mods:
                    for file_status in mod.files:
                        task = file_status.task
                        if task is None or task.kind != 'content' or not file_status.total:
                            continue
                        approvals[id(file_status)] = messagebox.askyesno(
                            '确认原位翻译', f'{task.source}\n将直接改写 content.json，是否继续？', parent=self.main_app.root)
            active_files = [file_status for mod in mods for file_status in mod.files
                            if file_status.task is not None
                            and (file_status.task.kind != 'content' or approvals.get(id(file_status), False))]
        except (ValueError, KeyError, IndexError) as error:
            self.main_app.log_message(str(error), 'ERROR')
            return

        eligible = {id(item) for item in active_files if item.status not in ('无需翻译', '已完成', '扫描失败')}
        if not eligible:
            message = '没有待翻译的文件'
            if all_mods:
                message += '；原位翻译 content.json 请使用“翻译选中”并确认'
            self.main_app.log_message(message, 'WARNING')
            return
        self.active_files = active_files
        self.main_app.update_progress_display(sum(item.completed for item in active_files),
                                              sum(item.total for item in active_files))

        def translate(stop_check, post):
            for mod in mods:
                for file_status in mod.files:
                    if stop_check():
                        return
                    if id(file_status) not in eligible:
                        continue
                    try:
                        self._translate_file(mod, file_status, service, language, batch_size, stop_check, post)
                    except Exception as error:
                        post(self.main_app.log_message, f'{mod.name} 翻译失败：{error}', 'ERROR')
                        break

        self._start_worker(service, translate)

    def _translate_file(self, mod, file_status, service, language, batch_size, stop_check, post):
        document = TranslationFile(file_status.task)
        translatable = document.translatable_entries(service.core)
        reusable = document.reusable(service.core)
        translations = {}
        for path, original in document.entries.items():
            if path in reusable:
                translations[path] = reusable[path]
            elif path in translatable:
                continue
            elif document.task.kind == 'i18n':
                translations[path] = document.target_data.get(path[0], original)
            else:
                translations[path] = original
        pending = [path for path in translatable if path not in reusable]
        initial_completed = len(set(reusable) & set(translatable))
        total = len(translatable)
        if not pending:
            post(self._update_status, mod, file_status, total, total, '已完成' if total else '无需翻译')
            return
        completed = initial_completed
        post(self._update_status, mod, file_status, completed, total, '翻译中')
        post(self.main_app.log_message, f'翻译：{document.task.source}；待处理 {len(pending)} 条')

        def result_callback(position, original, result):
            nonlocal completed
            translations[pending[position]] = result
            completed += 1
            post(self._update_status, mod, file_status, completed, total, '翻译中')

        try:
            service.translate_batch_async(
                [translatable[path] for path in pending], language, batch_size,
                stop_check=stop_check, result_callback=result_callback)
            with self.commit_lock:
                if stop_check():
                    return
                if document.task.kind == 'content':
                    document.save_original(translations, service.core, stop_check)
                else:
                    document.save(translations, service.core, stop_check)
        except Exception:
            post(self._update_status, mod, file_status, initial_completed, total, '翻译失败')
            raise
        post(self._update_status, mod, file_status, total, total, '已完成')
        post(self.main_app.log_message, f'已安全保存：{file_status.task.target}')

    def _update_status(self, mod, file_status, completed, total, status):
        if status != '翻译中':
            self.current_file = None
        elif self.current_file is None:
            self.current_file = (mod, file_status, completed)
        file_status.completed, file_status.total, file_status.status = completed, total, status
        completed = sum(item.completed for item in mod.files)
        total = sum(item.total for item in mod.files)
        mod.completed = completed
        mod.total = total
        if status in ('翻译中', '已取消'):
            mod.status = status
        elif issue := next((issue for issue in ('翻译失败', '扫描失败', '待确认')
                           if any(item.status == issue for item in mod.files)), None):
            mod.status = issue
        elif total and completed == total:
            mod.status = '已完成'
        elif completed:
            mod.status = '部分翻译'
        elif not total:
            mod.status = '无需翻译'
        else:
            mod.status = '未翻译'
        workbench = getattr(self.main_app, 'workbench', None)
        if workbench is not None:
            workbench.update_status(mod, file_status)
        active_files = self.active_files or [file_status]
        global_completed = sum(item.completed for item in active_files)
        global_total = sum(item.total for item in active_files)
        self.main_app.update_progress_display(global_completed, global_total)

    def _start_single_translation(self):
        """兼容没有工作台的旧调用路径。"""
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
            approved_tasks = []
            for task in tasks:
                if task.kind != 'content':
                    approved_tasks.append(task)
                    continue
                document = TranslationFile(task)
                if not document.translatable_entries(service.core) or messagebox.askyesno(
                        '确认原位翻译', f'{task.source}\n将直接改写 content.json，是否继续？',
                        parent=self.main_app.root):
                    approved_tasks.append(task)
            tasks = approved_tasks
            if not tasks:
                self.main_app.log_message('未确认 content.json，未开始翻译', 'WARNING')
                return
        except (ValueError, KeyError, IndexError) as error:
            self.main_app.log_message(str(error), 'ERROR')
            return
        self.main_app.file_manager.selection_generation = getattr(self.main_app.file_manager, 'selection_generation', 0) + 1

        def translate(stop_check, post):
            try:
                for task_index, task in enumerate(tasks):
                    if stop_check():
                        return
                    document = TranslationFile(task)
                    if not document.entries:
                        post(self.main_app.log_message, f'未找到可安全翻译的文本，跳过：{task.source}', 'WARNING')
                        continue
                    translated = document.reusable(service.core)
                    document.completed_paths.update(translated)
                    pending = [path for path in document.entries if path not in translated]
                    preview = dict(document.entries)
                    preview.update(translated)
                    post(self._show_document, document, preview, index + task_index)
                    post(self.main_app.log_message, f'翻译：{task.source}；待处理 {len(pending)} 条')

                    def result_callback(position, original, result):
                        path = pending[position]
                        translated[path] = result
                        post(self.main_app.update_translation_display, path, result)
                        post(self.main_app.update_progress_display, len(translated), len(document.entries))

                    service.translate_batch_async(
                        [document.entries[path] for path in pending], language, batch_size,
                        stop_check=stop_check, result_callback=result_callback)
                    with self.commit_lock:
                        if stop_check():
                            return
                        document.save(translated, service.core, stop_check)
                    post(self.main_app.log_message, f'已安全保存：{task.target}')
                post(self.main_app.log_message, '所选 MOD 的翻译已完成')
            except Exception as error:
                post(self.main_app.log_message, f'当前文件未保存：{error}', 'ERROR')
        
        self._start_worker(service, translate)
    
    def stop_translation(self):
        """停止翻译"""
        if not self.is_translating:
            return
        self.cancel_event.set()
        self.main_app.log_message(self.main_app.get_ui_text("stopping_translation"))
        if self.current_file is not None:
            mod, file_status, completed = self.current_file
            self._update_status(mod, file_status, completed, file_status.total, '已取消')
        self._finish_translation()
        self.main_app.log_message('已停止；进行中的请求结果将丢弃，已写入的文件保留')

    def _finish_translation(self):
        self.reset_translation_state()
        file_manager = getattr(self.main_app, 'file_manager', None)
        if file_manager is not None:
            file_manager.on_file_change()
    
    def reset_translation_state(self):
        """重置翻译状态"""
        self.is_translating = False
        self.active_files = []
        self.current_file = None
        self.main_app.translate_btn.config(text=self.main_app.get_ui_text("auto_translate"))
        # 清空进度显示
        self.main_app.update_progress_display(0, 0)
        self._set_selection_state('normal')

    def _set_selection_state(self, state):
        for name in ('mod_combo', 'file_combo', 'model_combo', 'language_combo', 'provider_settings_btn',
                     'select_directory_btn', 'settings_btn', 'save_translation_btn', 'import_btn',
                     'extract_btn', 'extract_i18n_btn', 'refresh_models_btn', 'clear_dirs_btn', 'restore_backup_btn',
                     'refresh_mods_btn', 'translate_all_btn', 'translate_selected_btn'):
            widget = getattr(self.main_app, name, None)
            if widget is not None:
                restored = 'readonly' if name in ('mod_combo', 'file_combo', 'language_combo') else 'normal'
                widget.config(state='disabled' if state == 'disabled' else restored)
        tree = getattr(self.main_app, 'mod_workbench', None)
        if tree is not None:
            tree.state(('disabled' if state == 'disabled' else '!disabled',))

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
