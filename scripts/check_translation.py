"""离线自检；输入与失败产物保留在项目的 .checks 目录。"""

import json
import os
import queue
import threading
from pathlib import Path
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.config_manager import ConfigManager
from modules.mod_translation import JsonDocument, TranslationFile, TranslationTask, discover_tasks
from modules.translation_core import TranslationCore
from modules.translation_service import TranslationService


WORK = ROOT / '.checks' / uuid.uuid4().hex


def fixture(name, text):
    path = WORK / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def rejects(action):
    try:
        action()
    except (ValueError, RuntimeError, OSError):
        return
    raise AssertionError('应当拒绝不安全操作')


def check_terms_and_tokens():
    core = TranslationCore({'Ann': '安', 'Ann Marie': '安玛丽'})
    source = 'Ann Marie, Ann and JoAnn {{Ann}} {0} $h#$b#@ [Ann] %item 2%%\nAnn'
    masked, replacements = core.protect_text(source)
    assert 'JoAnn' in masked and 'Ann Marie' not in masked
    restored = core.finish_translation(source, masked.replace(' and ', '和'), replacements)
    assert restored == '安玛丽, 安和JoAnn {{Ann}} {0} $h#$b#@ [Ann] %item 2%%\n安'
    marker = next(iter(replacements))
    rejects(lambda: core.finish_translation(source, masked.replace(marker, ''), replacements))
    rejects(lambda: core.finish_translation(source, masked + marker, replacements))
    assert not core.validate_translation('{{x}}{{x}}', '{{x}}')
    assert not core.validate_translation('$h#$b#', '$b#$h#')
    assert not core.validate_translation('Ann', '随意译名')
    assert not core.validate_translation('Ann', '安全')

    source = '{{percent}}% ({{value}} of {{max}})'
    translation = '{{percent}}%（{{max}}中的{{value}}）'
    replacements = core.protect_text(source)[1]
    response = translation
    for marker, token in replacements.items():
        response = response.replace(token, marker)
    assert core.finish_translation(source, response, replacements) == translation
    assert not core.validate_translation(source, translation.replace('{{max}}', '{{value}}'))
    assert not core.validate_translation(source, '{{value}}%（{{max}}中的{{percent}}）')
    assert not core.validate_translation('{{value}}$b{{max}}', '{{max}}$b{{value}}')


def check_protocols():
    credential = uuid.uuid4().hex
    for protocol, suffix in [('ollama', '/api/chat'), ('openai', '/v1/chat/completions'), ('anthropic', '/v1/messages')]:
        service = TranslationService({'protocol': protocol, 'base_url': 'http://localhost:1234',
                                      'model': 'offline-model', 'api_key': credential}, '使用口语', {'Ann': '安'})
        complete = TranslationService({'protocol': protocol, 'base_url': service.url,
                                       'model': 'offline-model', 'api_key': credential})
        assert complete.url == service.url

        def respond(url, *, include_end=True, **kwargs):
            assert url.endswith(suffix)
            assert kwargs['allow_redirects'] is False
            body = kwargs['json']
            text = body['messages'][-1]['content'].replace('Hello ', '你好，')
            if protocol == 'anthropic':
                assert kwargs['headers']['x-api-key'] == credential
                assert kwargs['headers']['anthropic-version'] == '2023-06-01'
                assert '使用口语' in body['system']
                payload = {'content': [{'type': 'text', 'text': text}]}
                if include_end:
                    payload['stop_reason'] = 'end_turn'
            elif protocol == 'openai':
                assert kwargs['headers']['Authorization'] == 'Bearer ' + credential
                assert '使用口语' in body['messages'][0]['content']
                choice = {'message': {'content': text}}
                if include_end:
                    choice['finish_reason'] = 'stop'
                payload = {'choices': [choice]}
            else:
                assert '使用口语' in body['messages'][0]['content']
                payload = {'message': {'content': text}}
                if include_end:
                    payload['done'] = True
            return SimpleNamespace(status_code=200, json=lambda: payload)

        with patch('modules.translation_service.requests.post', side_effect=respond):
            assert service.translate_single_text('Hello Ann {{name}}', 'Chinese') == '你好，安 {{name}}'
        with patch('modules.translation_service.requests.post',
                   side_effect=lambda url, **kwargs: respond(url, include_end=False, **kwargs)):
            assert service.translate_single_text('Hello Ann {{name}}', 'Chinese') == '你好，安 {{name}}'
        with patch('modules.translation_service.requests.post', return_value=SimpleNamespace(status_code=401)):
            try:
                service.translate_single_text('Hello', 'Chinese')
            except RuntimeError as error:
                assert credential not in str(error) and '401' in str(error)
            else:
                raise AssertionError('认证失败必须终止翻译')
        with patch('modules.translation_service.requests.post', return_value=SimpleNamespace(status_code=200, json=lambda: {
            'choices': [{'message': {'content': '截断'}, 'finish_reason': 'length'}],
            'content': [{'type': 'text', 'text': '截断'}], 'stop_reason': 'max_tokens',
            'message': {'content': '截断'}, 'done': True, 'done_reason': 'length'
        })):
            rejects(lambda: service.translate_single_text('Hello', 'Chinese'))
        with patch('modules.translation_service.requests.post',
                   side_effect=lambda url, **kwargs: SimpleNamespace(status_code=200, json=lambda: {
                       **respond(url, **kwargs).json(), 'error': {'message': credential}})):
            try:
                service.translate_single_text('Hello Ann {{name}}', 'Chinese')
            except RuntimeError as error:
                assert credential not in str(error)
            else:
                raise AssertionError('不得接受带错误的响应')


def check_jsonc():
    raw = b'\xef\xbb\xbf{ /* keep */ "url": "https://a/b", "nested": [{"text":"Hello",}], // keep\n}'
    document = JsonDocument(raw)
    result = document.replace_strings({('nested', 0, 'text'): '你好'})
    assert result == raw.replace(b'Hello', '你好'.encode())
    assert JsonDocument(result).data['url'] == 'https://a/b'
    duplicate = JsonDocument(b'{"same":"old","same":"old"}')
    duplicate_result = duplicate.replace_strings({('same',): 'new'})
    assert duplicate_result.count(b'"same":"new"') == 2
    assert JsonDocument(b'{"same":1,"same":2}').data['same'] == 2
    unquoted_raw = (b'\xef\xbb\xbf{\r\n // keep\r\n Greeting /* keep */: "Hello", '
                    b'Nested: [{ Name: "World", },], "literal": "{ Fake: value } // keep", }\r\n')
    unquoted = JsonDocument(unquoted_raw)
    assert unquoted.data == {'Greeting': 'Hello', 'Nested': [{'Name': 'World'}],
                             'literal': '{ Fake: value } // keep'}
    replaced = unquoted.replace_strings({('Greeting',): '你好', ('Nested', 0, 'Name'): '世界'})
    assert replaced == unquoted_raw.replace(b'Hello', '你好'.encode()).replace(b'World', '世界'.encode())
    rejects(lambda: JsonDocument(b'{"bad":NaN}'))
    rejects(lambda: document.replace_strings({('url',): 12}))


def check_content_fields():
    raw = {'Format': '2.0.0', 'Changes': [
        {'Action': 'EditData', 'Target': 'Characters/Dialogue/Ann', 'When': {'Season': 'spring'},
         'Entries': {'spring': 'Hello {{name}}', 'path': 'assets/image.png'}},
        {'Action': 'EditData', 'Target': 'Data/Objects',
         'Entries': {'id': {'Name': 'InternalName', 'DisplayName': 'Berry', 'Description': 'Sweet', 'Texture': 'assets/a'}}},
        {'Action': 'Load', 'Target': 'Maps/Town', 'FromFile': 'assets/map.tmx'},
        {'Action': 'EditData', 'Target': 'Data/Events/Town', 'Entries': {'id': 'speak Ann "Hello"/end'}}]}
    source = fixture('content/content.json', json.dumps(raw))
    document = TranslationFile(TranslationTask(source, source, 'content', source.parent))
    assert set(document.entries.values()) == {'Hello {{name}}', 'Berry', 'Sweet'}
    translated = {key: value.replace('Hello', '你好').replace('Berry', '浆果').replace('Sweet', '甜')
                  for key, value in document.entries.items()}
    document.save(translated, TranslationCore())
    saved = JsonDocument(source.read_bytes()).data
    assert saved['Changes'][0]['Entries']['spring'] == '你好 {{name}}'
    assert saved['Changes'][0]['When'] == {'Season': 'spring'}
    assert saved['Changes'][1]['Entries']['id']['Name'] == 'InternalName'
    assert saved['Changes'][3] == raw['Changes'][3]


def check_discovery():
    from modules.mod_translation import scan_mods

    root = WORK / 'discovery'
    fixture('discovery/a/manifest.json', '{}')
    source = fixture('discovery/a/I18N/Default.JSON', '\ufeff{/* keep */ a: "Hello",\n}')
    fixture('discovery/a/content.json', '{}')
    fixture('discovery/b/manifest.json', '{}')
    content = fixture('discovery/b/content.json', '{"Changes":[]}')
    tasks = discover_tasks(root)
    assert {(task.source, task.target, task.kind) for task in tasks} == {
        (source, source.parent / 'zh.json', 'i18n'), (content, content, 'content')}
    first = next(task for task in tasks if task.kind == 'i18n')
    TranslationFile(first).save({('a',): '你好'}, TranslationCore())
    assert JsonDocument((root / 'a/I18N/zh.json').read_bytes()).data == {'a': '你好'}
    assert (root / 'a/I18N/zh.json').read_bytes() == source.read_bytes().replace(b'Hello', '你好'.encode())
    assert content.read_text(encoding='utf-8') == '{"Changes":[]}'
    fixture('discovery/a/nested/manifest.json', '{"Name":"无文本子 MOD"}')
    missing = root / 'missing/I18N'
    missing.mkdir(parents=True)
    fixture('discovery/missing/content.json', '{"Changes":[]}')
    fixture('discovery/partial/i18n/en.json',
            '{"ok":"Hello","same":"Goodbye","invalid":"Thanks {{name}}","blank":"Note","absent":"Bye"}')
    fixture('discovery/partial/i18n/zh.json', '{"ok":"你好","same":"Goodbye","invalid":"谢谢","blank":" "}')
    fixture('discovery/pending/content.json',
            '{"Changes":[{"Action":"EditData","Target":"Strings/UI","Entries":{"a":"Hello"}}]}')
    fixture('discovery/pending/content.json.bak', '{}')
    fixture('discovery/broken/manifest.json', '{"Name":"损坏的 MOD"}')
    fixture('discovery/broken/i18n/default.json', '{invalid')
    fixture('discovery/untouched/i18n/default.json', '{"resource":"assets/image.png","marker":"{{name}}","number":"42"}')
    fixture('discovery/controls/content.json',
            '{"Changes":[{"Action":"EditData","Target":"Strings/UI",'
            '"Entries":{"marker":"{{name}}"}}]}')
    states = {mod.path.relative_to(root).as_posix(): mod for mod in scan_mods(root, 'zh', TranslationCore())}
    assert states['a'].status == '已完成'
    assert states['a/nested'].status == '无需翻译' and states['a/nested'].name == '无文本子 MOD'
    assert states['b'].status == '无需翻译'
    assert states['broken'].status == '扫描失败'
    assert states['missing'].status == '待确认' and '缺少' in states['missing'].files[0].detail
    assert states['pending'].status == '待确认'
    assert states['untouched'].status == '无需翻译'
    assert states['controls'].status == '无需翻译' and states['controls'].total == 0
    assert (states['partial'].status, states['partial'].completed, states['partial'].total) == ('部分翻译', 1, 5)
    english_states = {mod.path.relative_to(root).as_posix(): mod for mod in scan_mods(root, 'default', TranslationCore())}
    assert english_states['a'].status == '无需翻译' and english_states['a'].total == 0


def check_save_and_history():
    source = fixture('save/i18n/default.json', '{"one":"Hello {{name}}","two":"Goodbye"}')
    target = fixture('save/i18n/zh.json', '{"one":"你好 {{name}}","custom":"用户自有"}')
    original = target.read_bytes()
    document = TranslationFile(TranslationTask(source, target, 'i18n', source.parent.parent))
    assert document.reusable(TranslationCore()) == {('one',): '你好 {{name}}'}
    document.save({('one',): '你好 {{name}}', ('two',): '再见'}, TranslationCore())
    assert JsonDocument(target.read_bytes()).data == {'one': '你好 {{name}}', 'two': '再见', 'custom': '用户自有'}
    assert target.with_name('zh.json.bak').read_bytes() == original
    document.save({('one',): '您好 {{name}}', ('two',): '再见'}, TranslationCore())
    assert target.with_name('zh.json.bak').read_bytes() == original
    assert target.with_name('zh.json.bak.1').exists()
    from modules.mod_translation import atomic_write
    atomic_write(target, original, target.read_bytes())
    assert target.read_bytes() == original
    assert target.with_name('zh.json.bak.2').exists()

    control_source = fixture('save-controls/i18n/default.json',
                              '{"conditions-summary":"[conditions: {{conditions}}]","text":"Hello"}')
    control_target = fixture('save-controls/i18n/zh.json',
                              '{"conditions-summary":"[条件: {{conditions}}]"}')
    control_document = TranslationFile(TranslationTask(control_source, control_target, 'i18n', control_source.parent.parent))
    control_document.save({('conditions-summary',): '[条件: {{conditions}}]', ('text',): '你好'}, TranslationCore())
    assert JsonDocument(control_target.read_bytes()).data == {
        'conditions-summary': '[条件: {{conditions}}]', 'text': '你好'}

    control_content = fixture('save-controls/content.json',
                              '{"Changes":[{"Action":"EditData","Target":"Strings/UI",'
                              '"Entries":{"conditions":"[conditions: {{conditions}}]",'
                              '"text":"Hello"}}]}')
    content_document = TranslationFile(TranslationTask(control_content, control_content, 'content', control_content.parent))
    content_document.save_original({
        ('Changes', 0, 'Entries', 'conditions'): '[条件: {{conditions}}]',
        ('Changes', 0, 'Entries', 'text'): '你好'}, TranslationCore())
    assert JsonDocument(control_content.read_bytes()).data['Changes'][0]['Entries'] == {
        'conditions': '[条件: {{conditions}}]', 'text': '你好'}


def check_failed_writes():
    source = fixture('fail/i18n/default.json', '{"a":"Hello {{name}}"}')
    target = fixture('fail/i18n/zh.json', '{"a":"原有 {{name}}"}')
    document = TranslationFile(TranslationTask(source, target, 'i18n', source.parent.parent))
    before = target.read_bytes()
    good = {('a',): '你好 {{name}}'}
    rejects(lambda: document.save({}, TranslationCore()))
    rejects(lambda: document.save({('a',): '缺少标记'}, TranslationCore()))
    rejects(lambda: document.save(good, TranslationCore(), lambda: True))
    assert target.read_bytes() == before
    with patch('modules.mod_translation.create_backup', side_effect=OSError('备份失败')):
        rejects(lambda: document.save(good, TranslationCore()))
    assert target.read_bytes() == before
    with patch('modules.mod_translation.os.replace', side_effect=OSError('写入中断')):
        rejects(lambda: document.save(good, TranslationCore()))
    assert target.read_bytes() == before
    target.write_text('{"a":"外部修改 {{name}}"}', encoding='utf-8')
    rejects(lambda: document.save(good, TranslationCore()))
    assert '外部修改' in target.read_text(encoding='utf-8')
    rejects(lambda: document.save_original({('a',): 'Hello'}, TranslationCore()))
    content = fixture('fail/content.json',
                      '{"Changes":[{"Action":"EditData","Target":"Strings/UI",'
                      '"Entries":{"a":"Hello {{name}}"}}]}')
    content_document = TranslationFile(TranslationTask(content, content, 'content', content.parent))
    content_path = next(iter(content_document.entries))
    with patch('modules.mod_translation.create_backup', side_effect=OSError('备份失败')):
        rejects(lambda: content_document.save_original({content_path: 'Welcome {{name}}'}, TranslationCore()))
    assert JsonDocument(content.read_bytes()).data['Changes'][0]['Entries']['a'] == 'Hello {{name}}'
    content_document.save_original({content_path: 'Welcome {{name}}'}, TranslationCore())
    assert JsonDocument(content.read_bytes()).data['Changes'][0]['Entries']['a'] == 'Welcome {{name}}'
    assert JsonDocument(content.with_name('content.json.bak').read_bytes()).data['Changes'][0]['Entries']['a'] == 'Hello {{name}}'
    assert JsonDocument(target.read_bytes()).data == {'a': '外部修改 {{name}}'}


def check_batch_failure():
    service = TranslationService({'protocol': 'openai', 'base_url': 'http://localhost:1234/v1',
                                  'model': 'offline-model', 'api_key': uuid.uuid4().hex})
    with patch('modules.translation_service.requests.post', return_value=SimpleNamespace(status_code=503)):
        rejects(lambda: service.translate_batch_async(['Hello', 'Goodbye'], 'Chinese', 1))
    assert service.translate_batch_async([], 'Chinese', 1) == []
    rejects(lambda: service.translate_batch_async(['Hello'], 'Chinese', 0))


def check_batch_cancel_does_not_wait():
    service = TranslationService({'protocol': 'openai', 'base_url': 'http://localhost:1234/v1',
                                  'model': 'offline-model', 'api_key': uuid.uuid4().hex})
    started = threading.Event()
    release = threading.Event()
    cancelled = threading.Event()

    def response(url, **kwargs):
        started.set()
        assert release.wait(5), '取消测试请求未释放'
        return SimpleNamespace(status_code=200, json=lambda: {
            'choices': [{'message': {'content': '你好'}, 'finish_reason': 'stop'}]})

    def translate():
        try:
            service.translate_batch_async(['Hello'], 'Chinese', 1, stop_check=cancelled.is_set)
        except RuntimeError:
            pass

    with patch('modules.translation_service.requests.post', side_effect=response):
        worker = threading.Thread(target=translate)
        worker.start()
        assert started.wait(5), '取消测试请求未启动'
        cancelled.set()
        worker.join(0.2)
        returned_while_blocked = not worker.is_alive()
        release.set()
        worker.join(5)
    assert returned_while_blocked, '停止翻译不得等待阻塞中的供应商请求'


def check_connection_test_timeout():
    service = TranslationService({'protocol': 'openai', 'base_url': 'http://localhost:1234/v1',
                                  'model': 'offline-model', 'api_key': uuid.uuid4().hex})
    response = SimpleNamespace(status_code=200, json=lambda: {
        'choices': [{'message': {'content': '连接成功'}, 'finish_reason': 'stop'}]})
    with patch('modules.translation_service.requests.post', return_value=response) as request:
        service.translate_single_text('connection test', 'Chinese', timeout=(1, 2))
    assert request.call_args.kwargs['timeout'] == (1, 2)


def check_cancel_updates_ui_immediately():
    from tkinter import TclError
    from modules.translation_manager import TranslationManager

    class Widget:
        def __init__(self):
            self.configured = {}

        def config(self, **kwargs):
            self.configured.update(kwargs)

    class Tree(Widget):
        def config(self, **kwargs):
            if 'state' in kwargs:
                raise TclError('unknown option "-state"')
            super().config(**kwargs)

        def state(self, states):
            self.configured['state'] = states[0]

    widgets = {name: Widget() for name in ('translate_btn', 'mod_combo', 'file_combo', 'model_combo',
                                            'language_combo', 'provider_settings_btn', 'select_directory_btn',
                                            'settings_btn', 'save_translation_btn', 'import_btn', 'extract_btn',
                                            'extract_i18n_btn', 'refresh_models_btn', 'clear_dirs_btn',
                                            'restore_backup_btn', 'refresh_mods_btn', 'translate_all_btn',
                                            'translate_selected_btn')}
    tree = Tree()
    app = SimpleNamespace(**widgets, update_progress_display=lambda *args: None,
                          log_message=lambda *args: None, mod_workbench=tree,
                          get_ui_text=lambda key: {'stopping_translation': '停止中',
                                                   'auto_translate': '自动翻译'}[key])
    manager = TranslationManager(app)
    manager._set_selection_state('disabled')
    manager.is_translating = True
    manager.stop_translation()
    assert manager.cancel_event.is_set()
    assert not manager.is_translating
    assert app.translate_btn.configured['text'] == '自动翻译'
    assert all(widget.configured.get('state') != 'disabled' for widget in widgets.values())
    assert tree.configured['state'] == '!disabled'


def check_workbench_double_click_selects_mod():
    from modules.file_manager import FileManager
    from modules.gui_manager import GUIManager

    class Tree:
        def __init__(self):
            self.calls = []

        def identify_region(self, x, y):
            return 'tree' if y == 10 else 'heading'

        def identify_row(self, y):
            return '1' if y == 10 else ''

        def selection_set(self, item):
            self.calls.append(('selection_set', item))

        def focus(self, item):
            self.calls.append(('focus', item))

        def see(self, item):
            self.calls.append(('see', item))

    class Combo(dict):
        index = 0
        value = ''

        def current(self, index=None):
            if index is not None:
                self.index = index
            return self.index

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    tree = Tree()
    combo = Combo()
    comparisons = []
    source = fixture('workbench/second/i18n/default.json', '{"label":"Second"}')
    target = fixture('workbench/second/i18n/zh.json', '{"label":"第二个"}')
    task = TranslationTask(source, target, 'i18n', source.parent.parent)
    mods = [SimpleNamespace(name='Example Mod', path=task.root.with_name('first'), tasks=[]),
            SimpleNamespace(name='Example Mod', path=task.root, tasks=[task])]
    gui = GUIManager.__new__(GUIManager)
    manager = FileManager.__new__(FileManager)
    gui.parent = manager.app = SimpleNamespace(
        mod_workbench=tree, mod_combo=combo, file_combo=Combo(), gui_manager=gui,
        on_mod_change=manager.on_mod_change, log_message=lambda *args: None, get_ui_text=lambda key: key,
        config_manager=SimpleNamespace(get=lambda key, default: default),
        translation_manager=SimpleNamespace(is_translating=False,
                                            display_comparison_data=lambda *args: comparisons.append(args)),
        ui_text_manager=SimpleNamespace(get_text=lambda key: key),
        root=SimpleNamespace(after=lambda delay, callback, *args: callback(*args)))
    gui.mod_items = dict(zip(('0', '1'), mods))
    gui.root = gui.parent.root
    gui.comboboxes = []
    manager.available_mods = mods
    manager.selection_generation = 0
    with patch.object(gui.root, 'after') as schedule:
        gui._on_global_click(SimpleNamespace(widget=tree))
        schedule.assert_not_called()
    with patch('modules.file_manager.threading.Thread', side_effect=lambda target, args, daemon:
               SimpleNamespace(start=lambda: target(*args))):
        assert gui._on_mod_workbench_double_click(SimpleNamespace(x=5, y=0)) is None
        assert gui._on_mod_workbench_double_click(SimpleNamespace(x=150, y=10)) == 'break'
    assert tree.calls == [('selection_set', '1'), ('focus', '1'), ('see', '1')]
    assert combo.current() == 1 and gui.parent.current_translation_file == target
    filename = str(target.relative_to(task.root))
    assert gui.parent.file_combo['values'] == [filename] and gui.parent.file_combo.get() == filename
    assert comparisons == [({('label',): '第二个'}, {('label',): 'Second'})]


def check_coordinator():
    from modules.mod_translation import scan_mods

    messagebox = SimpleNamespace()
    with patch.dict(sys.modules, {'tkinter': SimpleNamespace(END='end', filedialog=SimpleNamespace(), messagebox=messagebox)}):
        import modules.translation_manager as translation_manager
        translation_manager.messagebox = messagebox
        TranslationManager = translation_manager.TranslationManager

    app = SimpleNamespace(workbench=object(), log_message=lambda *args: None)
    manager = TranslationManager(app)
    calls = []
    manager._start_single_translation = lambda: calls.append('single')
    manager._start_mod_translation = lambda all_mods: calls.append(('batch', all_mods))
    manager.start_translation()
    manager.start_translation(all_mods=True)
    assert calls == ['single', ('batch', True)]

    owner = threading.get_ident()

    class Widget:
        def __init__(self, value=''):
            self.value = value
            self.items = []

        def config(self, **kwargs):
            assert threading.get_ident() == owner

        def get(self, index=None):
            assert threading.get_ident() == owner
            return self.value if index is None else self.items[index]

        def set(self, value):
            assert threading.get_ident() == owner
            self.value = value

        def delete(self, start, end=None):
            assert threading.get_ident() == owner
            if end is not None:
                self.items.clear()
            else:
                self.items.pop(start)

        def insert(self, index, value):
            assert threading.get_ident() == owner
            if index == 'end':
                self.items.append(value)
            else:
                self.items.insert(index, value)

    class Root:
        def __init__(self):
            self.callbacks = queue.Queue()

        def after(self, delay, callback, *args):
            assert threading.get_ident() == owner, '后台线程不得调用 Tk'
            self.callbacks.put((callback, args))

        def drain(self):
            for _ in range(self.callbacks.qsize()):
                callback, args = self.callbacks.get_nowait()
                callback(*args)

    legacy_content = fixture(
        'coordinator/legacy/content.json',
        '{"Changes":[{"Action":"EditData","Target":"Strings/UI",'
        '"Entries":{"a":"Hello"}}]}')
    legacy_task = TranslationTask(legacy_content, legacy_content, 'content', legacy_content.parent)
    legacy_service = TranslationService({'protocol': 'ollama', 'model': 'offline-model',
                                         'base_url': 'http://localhost:1234'})
    legacy_app = SimpleNamespace(
        root=Root(), file_manager=SimpleNamespace(scanning=False, selection_generation=0),
        available_files=[{'name': 'content.json', 'task': legacy_task}], current_file_index=0,
        target_languages={'中文': 'Chinese'}, target_language_var=Widget('中文'),
        language_codes={'中文': 'zh'},
        batch_size_var=Widget('1'), create_translation_service=lambda: legacy_service,
        get_ui_text=lambda key: key, log_message=lambda *args: None,
        update_progress_display=lambda *args: None, translate_btn=Widget(), file_combo=Widget(),
        original_listbox=Widget(), translation_listbox=Widget())
    legacy_manager = TranslationManager(legacy_app)
    confirmations = []
    messagebox.askyesno = lambda *args, **kwargs: confirmations.append(args[1]) or False
    with patch('modules.translation_service.requests.post', side_effect=AssertionError('拒绝后不得请求')):
        legacy_manager.start_translation()
        if legacy_manager.translation_thread:
            legacy_manager.translation_thread.join(5)
    assert len(confirmations) == 1
    assert legacy_content.read_text(encoding='utf-8').count('Hello') == 1

    for outcome in ('batch', 'selected', 'cancel'):
        base = f'coordinator/{outcome}'
        source = fixture(f'{base}/a/i18n/default.json', '{"a":"Hello {{name}}","b":"Fail here"}')
        target = fixture(f'{base}/a/i18n/zh.json', source.read_text(encoding='utf-8'))
        good = fixture(f'{base}/b/i18n/default.json', '{"a":"Goodbye"}')
        complete = fixture(f'{base}/c/i18n/default.json', '{"a":"No request"}')
        fixture(f'{base}/c/i18n/zh.json', '{"a":"已保存"}')
        content = fixture(f'{base}/d/content.json',
                          '{"Changes":[{"Action":"EditData","Target":"Strings/UI","Entries":{"a":"Hello"}}]}')
        declined = fixture(f'{base}/e/content.json', content.read_text(encoding='utf-8'))
        before = target.read_bytes()
        content_before = content.read_bytes()
        service = TranslationService({
            'protocol': 'openai' if outcome == 'batch' else 'ollama',
            'model': 'configured-model' if outcome == 'batch' else 'offline-model',
            'api_key': 'offline-key' if outcome == 'batch' else '',
            'base_url': 'http://localhost:1234/v1' if outcome == 'batch' else 'http://localhost:1234'})
        logs = []
        progress = []
        global_progress = []
        mods = scan_mods(WORK / base, 'zh', service.core)
        assert [mod.path.name for mod in mods] == ['a', 'b', 'c', 'd', 'e']
        workbench = SimpleNamespace(selected_mods=lambda: mods[1:2] if outcome == 'cancel' else mods[-2:],
                                    update_status=lambda mod, file: progress.append(
                                        (mod.path.name, mod.status, mod.completed, mod.total)))
        app = SimpleNamespace(root=Root(), file_manager=SimpleNamespace(scanning=False, available_mods=mods,
                              on_file_change=lambda: None), workbench=workbench,
                              batch_size_var=Widget('1'), target_language_var=Widget('中文'),
                              target_languages={'中文': 'Chinese'}, language_codes={'中文': 'zh'},
                              create_translation_service=lambda: service, get_ui_text=lambda key: key,
                              log_message=lambda text, level='INFO': logs.append(text),
                              update_progress_display=lambda *args: global_progress.append(args),
                              translate_btn=Widget(), file_combo=Widget(),
                              original_listbox=Widget(), translation_listbox=Widget())
        manager = TranslationManager(app)
        app.translation_manager = manager
        started = threading.Event()
        release = threading.Event()
        confirmations = []

        def confirm(title, prompt, **kwargs):
            confirmations.append(prompt)
            return str(content) in prompt

        messagebox.askyesno = confirm

        def response(url, **kwargs):
            text = kwargs['json']['messages'][-1]['content']
            if outcome == 'batch':
                assert kwargs['json']['model'] == 'configured-model'
                assert kwargs['headers']['Authorization'] == 'Bearer offline-key'
            if outcome == 'cancel' and text.startswith('Hello'):
                started.set()
                assert release.wait(5), '取消测试未释放请求'
            assert text != 'No request', '已完成 MOD 不应发送请求'
            if text == 'Fail here':
                return SimpleNamespace(status_code=503)
            translated = text.replace('Hello', '你好').replace('Goodbye', '再见')
            payload = ({'choices': [{'message': {'content': translated}, 'finish_reason': 'stop'}]}
                       if service.protocol == 'openai'
                       else {'message': {'content': translated}, 'done': True})
            return SimpleNamespace(status_code=200, json=lambda: payload)

        with patch('modules.translation_service.requests.post', side_effect=response):
            manager.start_translation(all_mods=outcome != 'selected')
            if outcome == 'cancel':
                assert started.wait(5), '取消测试未启动请求'
                app.root.drain()
                old_cancel = manager.cancel_event
                old_thread = manager.translation_thread
                try:
                    manager.stop_translation()
                    assert not manager.is_translating and old_cancel.is_set()
                    manager.start_translation(all_mods=False)
                    assert old_cancel.is_set() and manager.cancel_event is not old_cancel
                    assert manager.translation_thread is not old_thread
                    manager.translation_thread.join(1)
                    assert good.with_name('zh.json').exists() and not release.is_set()
                finally:
                    release.set()
                old_thread.join(5)
            manager.translation_thread.join(5)
            assert not manager.translation_thread.is_alive()
        app.root.drain()
        assert not manager.is_translating
        assert target.read_bytes() == before and declined.read_bytes() == content_before
        if outcome == 'batch':
            assert not confirmations and content.read_bytes() == content_before
            assert JsonDocument(good.with_name('zh.json').read_bytes()).data == {'a': '再见'}
            assert ('a', '翻译失败', 0, 2) in progress and ('b', '已完成', 1, 1) in progress
            assert max(total for _, total in global_progress) == 4
        elif outcome == 'selected':
            assert len(confirmations) == 2 and str(declined) in confirmations[1]
            assert content.with_name('content.json.bak').read_bytes() == content_before
            assert '你好' in content.read_text(encoding='utf-8') and not good.with_name('zh.json').exists()
            assert ('d', '已完成', 1, 1) in progress
            assert max(total for _, total in global_progress) == 1
            rescanned = {mod.path.name: mod.status for mod in scan_mods(WORK / base, 'zh', service.core)}
            assert rescanned['d'] == '待确认'
        else:
            assert not target.with_name('zh.json.bak').exists()
            assert ('a', '已取消', 0, 2) in progress and ('b', '已完成', 1, 1) in progress


def check_config():
    path = fixture('config/config.json', '{"ollama_model":"local","custom":"保留"}')
    config = ConfigManager(path)
    config.update({'glossary': {'Ann': '安'}, 'translation_prompt': '口语'}, auto_save=False)
    assert config.save_config()
    restored = ConfigManager(path)
    assert restored.get('custom') == '保留' and restored.get('glossary') == {'Ann': '安'}
    assert restored.get('translation_prompt') == '口语'
    if os.name == 'posix':
        assert path.stat().st_mode & 0o077 == 0
    corrupt = fixture('config/corrupt.json', '{invalid')
    ConfigManager(corrupt)
    assert corrupt.read_text(encoding='utf-8') == '{invalid'


if __name__ == '__main__':
    WORK.mkdir(parents=True)
    checks = [check_terms_and_tokens, check_protocols, check_jsonc, check_content_fields,
              check_discovery, check_save_and_history, check_failed_writes, check_batch_failure,
              check_batch_cancel_does_not_wait, check_connection_test_timeout,
              check_cancel_updates_ui_immediately, check_workbench_double_click_selects_mod,
              check_config, check_coordinator]
    for check in checks:
        check()
        print('通过:', check.__name__)
    print(f'{len(checks)} 组自检通过；产物：{WORK.relative_to(ROOT)}')
