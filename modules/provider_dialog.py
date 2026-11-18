"""供应商、提示词和术语库编辑窗口。"""

import copy
import json
import tkinter as tk
from tkinter import messagebox, ttk

from .mod_translation import JsonDocument
from .translation_service import DEFAULT_PROVIDER, TranslationService


def show_provider_dialog(app):
    if app.translation_manager.is_translating:
        app.log_message('请先停止当前翻译，再修改供应商设置', 'WARNING')
        return
    dialog = tk.Toplevel(app.root)
    dialog.title('供应商、提示词与术语库')
    dialog.transient(app.root)
    dialog.geometry('680x590')
    notebook = ttk.Notebook(dialog)
    notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    providers = copy.deepcopy(app.config_manager.get('providers', [DEFAULT_PROVIDER.copy()]))
    active = tk.StringVar(value=app.config_manager.get('selected_provider', DEFAULT_PROVIDER['name']))
    fields = {name: tk.StringVar() for name in ('name', 'protocol', 'base_url', 'model', 'api_key')}
    provider_tab = ttk.Frame(notebook, padding=12)
    notebook.add(provider_tab, text='供应商')
    provider_tab.columnconfigure(1, weight=1)
    ttk.Label(provider_tab, text='当前供应商').grid(row=0, column=0, sticky='w', pady=5)
    selector = ttk.Combobox(provider_tab, textvariable=active, values=[provider['name'] for provider in providers], state='readonly')
    selector.grid(row=0, column=1, sticky='ew')
    labels = {'name': '名称', 'protocol': '协议', 'base_url': '接口地址', 'model': '模型', 'api_key': 'API 密钥'}
    for row, (name, label) in enumerate(labels.items(), 1):
        ttk.Label(provider_tab, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=8)
        if name == 'protocol':
            entry = ttk.Combobox(provider_tab, textvariable=fields[name], values=['ollama', 'openai', 'anthropic'], state='readonly')
        else:
            entry = ttk.Entry(provider_tab, textvariable=fields[name], show='*' if name == 'api_key' else '')
        entry.grid(row=row, column=1, sticky='ew')
    ttk.Label(provider_tab, text='API 地址可填协议根地址、/v1 或完整请求地址。\n'
              '密钥保存在本机 Data/config.json；请仅向可信地址发送请求。\n'
              '点击“保存全部设置”后，当前供应商用于后续翻译。', wraplength=570).grid(row=7, columnspan=2, sticky='w', pady=15)
    loaded_name = [active.get()]

    def load_profile(event=None):
        provider = next((item for item in providers if item['name'] == active.get()), DEFAULT_PROVIDER)
        loaded_name[0] = active.get()
        for name, variable in fields.items():
            variable.set(provider.get(name, ''))

    def store_profile():
        provider = {name: variable.get().strip() for name, variable in fields.items()}
        if not provider['name']:
            raise ValueError('请输入供应商名称')
        if provider['name'] != loaded_name[0] and any(item['name'] == provider['name'] for item in providers):
            raise ValueError('供应商名称已存在')
        TranslationService(provider)
        position = next((index for index, item in enumerate(providers) if item['name'] == loaded_name[0]), None)
        if position is None:
            providers.append(provider)
        else:
            providers[position] = provider
        loaded_name[0] = provider['name']
        active.set(provider['name'])
        selector['values'] = [item['name'] for item in providers]

    def select_profile(event=None):
        load_profile()

    def new_profile():
        active.set('')
        loaded_name[0] = ''
        for name, variable in fields.items():
            variable.set('openai' if name == 'protocol' else '')

    selector.bind('<<ComboboxSelected>>', select_profile)
    ttk.Button(provider_tab, text='新增供应商', command=new_profile).grid(row=8, column=0, sticky='w')

    def keep_profile():
        try:
            store_profile()
        except ValueError as error:
            messagebox.showerror('设置无效', str(error), parent=dialog)

    ttk.Button(provider_tab, text='暂存当前供应商', command=keep_profile).grid(row=8, column=1, sticky='w')
    prompt_tab = ttk.Frame(notebook, padding=12)
    notebook.add(prompt_tab, text='翻译提示词')
    ttk.Label(prompt_tab, text='指定译法与游戏标记约束优先于下列提示词。').pack(anchor='w')
    prompt = tk.Text(prompt_tab, wrap=tk.WORD, height=15, undo=True)
    prompt.pack(fill=tk.BOTH, expand=True, pady=8)
    prompt.insert('1.0', app.config_manager.get('translation_prompt', ''))
    glossary_tab = ttk.Frame(notebook, padding=12)
    notebook.add(glossary_tab, text='术语库')
    ttk.Label(glossary_tab, text='填写 JSON 字典，例如 {"Abigail": "阿比盖尔"}。\n'
              '区分大小写；完整词匹配；重叠术语优先匹配最长项。\n'
              '术语不得包含占位符、游戏控制符或换行。', wraplength=580).pack(anchor='w')
    glossary = tk.Text(glossary_tab, wrap=tk.WORD, height=15, undo=True)
    glossary.pack(fill=tk.BOTH, expand=True, pady=8)
    glossary.insert('1.0', json.dumps(app.config_manager.get('glossary', {}), ensure_ascii=False, indent=2))

    def save():
        try:
            store_profile()
            terms = JsonDocument(glossary.get('1.0', 'end-1c').encode('utf-8')).data
            TranslationService(next(item for item in providers if item['name'] == active.get()),
                               prompt.get('1.0', 'end-1c'), terms)
            original = copy.deepcopy(app.config_manager.config_data)
            app.config_manager.update({'providers': providers, 'selected_provider': active.get(),
                                       'translation_prompt': prompt.get('1.0', 'end-1c'), 'glossary': terms}, auto_save=False)
            if not app.config_manager.save_config():
                app.config_manager.config_data = original
                raise ValueError('配置保存失败，原配置已保留')
            app.ollama_model_var.set(fields['model'].get().strip())
            app.model_combo['values'] = [fields['model'].get().strip()]
            app.log_message(f'已保存供应商、提示词与术语库：{active.get()}')
            dialog.destroy()
        except (ValueError, TypeError, KeyError) as error:
            messagebox.showerror('设置无效', str(error), parent=dialog)

    buttons = ttk.Frame(dialog, padding=(12, 0, 12, 12))
    buttons.pack(fill=tk.X)
    ttk.Button(buttons, text='取消', command=dialog.destroy).pack(side=tk.RIGHT)
    ttk.Button(buttons, text='保存全部设置', command=save).pack(side=tk.RIGHT, padx=8)
    load_profile()
    dialog.grab_set()
