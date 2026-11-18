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


def check_protocols():
    credential = uuid.uuid4().hex
    for protocol, suffix in [('ollama', '/api/chat'), ('openai', '/v1/chat/completions'), ('anthropic', '/v1/messages')]:
        service = TranslationService({'protocol': protocol, 'base_url': 'http://localhost:1234',
                                      'model': 'offline-model', 'api_key': credential}, '使用口语', {'Ann': '安'})
        complete = TranslationService({'protocol': protocol, 'base_url': service.url,
                                       'model': 'offline-model', 'api_key': credential})
        assert complete.url == service.url

        def respond(url, **kwargs):
            assert url.endswith(suffix)
            assert kwargs['allow_redirects'] is False
            body = kwargs['json']
            text = body['messages'][-1]['content'].replace('Hello ', '你好，')
            if protocol == 'anthropic':
                assert kwargs['headers']['x-api-key'] == credential
                assert kwargs['headers']['anthropic-version'] == '2023-06-01'
                assert '使用口语' in body['system']
                payload = {'content': [{'type': 'text', 'text': text}], 'stop_reason': 'end_turn'}
            elif protocol == 'openai':
                assert kwargs['headers']['Authorization'] == 'Bearer ' + credential
                payload = {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}]}
            else:
                payload = {'message': {'content': text}, 'done': True}
            return SimpleNamespace(status_code=200, json=lambda: payload)

        with patch('modules.translation_service.requests.post', side_effect=respond):
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
    fixture('discovery/a/I18N/default.json', '{}')
    rejects(lambda: discover_tasks(root))


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


def check_batch_failure():
    service = TranslationService({'protocol': 'openai', 'base_url': 'http://localhost:1234/v1',
                                  'model': 'offline-model', 'api_key': uuid.uuid4().hex})
    with patch('modules.translation_service.requests.post', return_value=SimpleNamespace(status_code=503)):
        rejects(lambda: service.translate_batch_async(['Hello', 'Goodbye'], 'Chinese', 1))
    assert service.translate_batch_async([], 'Chinese', 1) == []
    rejects(lambda: service.translate_batch_async(['Hello'], 'Chinese', 0))


def check_coordinator():
    with patch.dict(sys.modules, {'tkinter': SimpleNamespace(END='end', filedialog=SimpleNamespace(), messagebox=SimpleNamespace())}):
        from modules.translation_manager import TranslationManager
        from modules.file_manager import FileManager
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
            self.callbacks.put((callback, args))

        def drain(self):
            while not self.callbacks.empty():
                callback, args = self.callbacks.get_nowait()
                callback(*args)

    for outcome in ('success', 'failure', 'cancel'):
        source = fixture(f'coordinator/{outcome}/i18n/default.json', '{"a":"Hello {{name}}","b":"Goodbye"}')
        target = fixture(f'coordinator/{outcome}/i18n/zh.json', source.read_text(encoding='utf-8'))
        task = TranslationTask(source, target, 'i18n', source.parent.parent)
        before = target.read_bytes()
        service = TranslationService({'protocol': 'ollama', 'model': 'offline-model', 'base_url': 'http://localhost:1234'})
        logs = []
        app = SimpleNamespace(root=Root(), file_manager=SimpleNamespace(scanning=False),
                              available_files=[{'name': 'i18n/zh.json', 'task': task}], current_file_index=0,
                              batch_size_var=Widget('1'), target_language_var=Widget('中文'),
                              target_languages={'中文': 'Chinese'}, language_codes={'中文': 'zh'},
                              create_translation_service=lambda: service, get_ui_text=lambda key: key,
                              log_message=lambda text, level='INFO': logs.append(text),
                              update_progress_display=lambda *args: None, translate_btn=Widget(), file_combo=Widget(),
                              original_listbox=Widget(), translation_listbox=Widget())
        manager = TranslationManager(app)
        app.translation_manager = manager
        app.update_translation_display = manager.update_translation_display
        started = threading.Event()
        release = threading.Event()

        def response(url, **kwargs):
            text = kwargs['json']['messages'][-1]['content']
            if outcome == 'cancel':
                started.set()
                assert release.wait(5), '取消测试未释放请求'
            if outcome == 'failure' and text == 'Goodbye':
                return SimpleNamespace(status_code=503)
            payload = {'message': {'content': text.replace('Hello', '你好').replace('Goodbye', '再见')}, 'done': True}
            return SimpleNamespace(status_code=200, json=lambda: payload)

        with patch('modules.translation_service.requests.post', side_effect=response):
            manager.start_translation()
            if outcome == 'cancel':
                assert started.wait(5), '取消测试未启动请求'
                manager.stop_translation()
                manager.start_translation()
                release.set()
            manager.translation_thread.join(5)
            assert not manager.translation_thread.is_alive()
        app.root.drain()
        assert not manager.is_translating
        if outcome == 'success':
            assert JsonDocument(target.read_bytes()).data == {'a': '你好 {{name}}', 'b': '再见'}
        else:
            assert target.read_bytes() == before
            if outcome == 'failure':
                file_manager = FileManager.__new__(FileManager)
                file_manager.app = app
                file_manager.save_translation_files()
                assert target.read_bytes() == before
                assert app.current_document.completed_paths != app.current_document.entries.keys()


def check_config():
    path = fixture('config/config.json', '{"ollama_model":"local","custom":"保留"}')
    config = ConfigManager(path)
    config.update({'glossary': {'Ann': '安'}, 'translation_prompt': '口语'}, auto_save=False)
    assert config.save_config()
    restored = ConfigManager(path)
    assert restored.get('custom') == '保留' and restored.get('glossary') == {'Ann': '安'}
    if os.name == 'posix':
        assert path.stat().st_mode & 0o077 == 0
    corrupt = fixture('config/corrupt.json', '{invalid')
    ConfigManager(corrupt)
    assert corrupt.read_text(encoding='utf-8') == '{invalid'


if __name__ == '__main__':
    WORK.mkdir(parents=True)
    checks = [check_terms_and_tokens, check_protocols, check_jsonc, check_content_fields,
              check_discovery, check_save_and_history, check_failed_writes, check_batch_failure, check_config,
              check_coordinator]
    for check in checks:
        check()
        print('通过:', check.__name__)
    print(f'{len(checks)} 组自检通过；产物：{WORK.relative_to(ROOT)}')
