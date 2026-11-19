"""MOD 文本定位、JSONC 保真修改与带历史备份的安全保存。"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import uuid


JSON_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/')
TRAILING_COMMAS = re.compile(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])')
UNQUOTED_KEY = re.compile(r'[A-Za-z_$][A-Za-z0-9_$-]*')
UNQUOTED_KEY_PAIR = re.compile(r'([{,])(\s*)([A-Za-z_$][A-Za-z0-9_$-]*)(?=\s*:)')


def _quote_unquoted_keys(text):
    parts = []
    cursor = 0
    for token in JSON_TOKENS.finditer(text):
        parts.append(UNQUOTED_KEY_PAIR.sub(
            lambda match: f'{match.group(1)}{match.group(2)}"{match.group(3)}"',
            text[cursor:token.start()]))
        parts.append(token.group())
        cursor = token.end()
    parts.append(UNQUOTED_KEY_PAIR.sub(
        lambda match: f'{match.group(1)}{match.group(2)}"{match.group(3)}"',
        text[cursor:]))
    return ''.join(parts)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'JSON 不支持数值：{value}')


class JsonDocument:
    def __init__(self, raw):
        self.raw = raw
        self.bom = raw.startswith(b'\xef\xbb\xbf')
        self.text = raw.decode('utf-8-sig')
        cleaned = JSON_TOKENS.sub(
            lambda match: match.group() if match.group().startswith('"') else re.sub(r'[^\r\n]', ' ', match.group()), self.text)
        self.cleaned = TRAILING_COMMAS.sub(lambda match: ' ' if match.group() == ',' else match.group(), cleaned)
        self.data = json.loads(_quote_unquoted_keys(self.cleaned), object_pairs_hook=_unique_object,
                               parse_constant=_reject_constant)
        self.spans = {}
        self._walk(0, ())

    def _space(self, index):
        while index < len(self.cleaned) and self.cleaned[index].isspace():
            index += 1
        return index

    def _walk(self, index, path):
        index = self._space(index)
        token = self.cleaned[index]
        decoder = json.JSONDecoder()
        if token in '{[':
            closing = '}' if token == '{' else ']'
            index = self._space(index + 1)
            count = 0
            while self.cleaned[index] != closing:
                if token == '{':
                    if self.cleaned[index] == '"':
                        key, index = decoder.raw_decode(self.cleaned, index)
                    else:
                        match = UNQUOTED_KEY.match(self.cleaned, index)
                        if not match:
                            raise ValueError('对象键名必须是字符串或未加引号的标识符')
                        key, index = match.group(), match.end()
                    index = self._space(index)
                    if index >= len(self.cleaned) or self.cleaned[index] != ':':
                        raise ValueError('对象键名后缺少冒号')
                    index = self._space(index + 1)
                else:
                    key = count
                index = self._space(self._walk(index, path + (key,)))
                count += 1
                if self.cleaned[index] == ',':
                    index = self._space(index + 1)
            return index + 1
        value, end = decoder.raw_decode(self.cleaned, index)
        if isinstance(value, str):
            self.spans.setdefault(path, []).append((index, end))
        return end

    def replace_strings(self, replacements):
        edits = []
        for path, value in replacements.items():
            if path not in self.spans or not isinstance(value, str):
                raise ValueError('只能修改已有的 JSON 文本值')
            replacement = json.dumps(value, ensure_ascii=False)
            edits.extend((start, end, replacement) for start, end in self.spans[path])
        text = self.text
        for start, end, value in sorted(edits, reverse=True):
            text = text[:start] + value + text[end:]
        raw = (b'\xef\xbb\xbf' if self.bom else b'') + text.encode('utf-8')
        JsonDocument(raw)
        return raw


def read_optional(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def has_symlink(path):
    return any(component.is_symlink() for component in (path, *path.parents))


def create_backup(path, raw):
    number = 0
    while True:
        backup = path.with_name(path.name + '.bak' + (f'.{number}' if number else ''))
        try:
            descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            number += 1
            continue
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return backup


def atomic_write(path, raw, expected, backup=True, stop_check=None, mode=None):
    path = Path(path)
    JsonDocument(raw)
    if has_symlink(path) or read_optional(path) != expected:
        raise ValueError('目标文件已变动或是符号链接，请重新加载后保存')
    if stop_check and stop_check():
        raise RuntimeError('翻译已取消，未保存当前文件')
    pending = path.with_name(path.name + '.pending.' + uuid.uuid4().hex)
    permissions = mode if mode is not None else (path.stat().st_mode & 0o777 if expected is not None else 0o644)
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, permissions)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if backup and expected is not None:
        create_backup(path, expected)
    if has_symlink(path) or read_optional(path) != expected:
        raise ValueError('保存期间目标文件发生变动，已保留原文件和待写入文件')
    if stop_check and stop_check():
        raise RuntimeError('翻译已取消，未保存当前文件')
    os.replace(pending, path)


@dataclass(frozen=True)
class TranslationTask:
    source: Path
    target: Path
    kind: str
    root: Path


@dataclass
class ModFileStatus:
    path: Path
    task: TranslationTask = None
    status: str = '扫描失败'
    completed: int = 0
    total: int = 0
    detail: str = ''


@dataclass
class ModStatus:
    path: Path
    name: str
    files: list
    status: str
    completed: int = 0
    total: int = 0
    detail: str = ''

    @property
    def tasks(self):
        return [item.task for item in self.files if item.task is not None]


def _status_from_counts(completed, total):
    if total == 0:
        return '无需翻译'
    if completed == total:
        return '已完成'
    if completed:
        return '部分翻译'
    return '未翻译'


def _relative_mod_path(root, path):
    try:
        relative = path.relative_to(root)
    except ValueError:
        return path.name
    return str(relative) if str(relative) != '.' else path.name


def scan_mods(root, language_code='zh', core=None):
    """从磁盘扫描 MOD，并按当前目标语言计算可恢复状态。"""
    from .translation_core import TranslationCore

    root = Path(root).resolve()
    core = core or TranslationCore()
    try:
        files = [path for path in root.rglob('*') if path.is_file() and not path.is_symlink()
                 and not any(parent.is_symlink() for parent in path.parents)]
    except OSError as error:
        return [ModStatus(root, root.name, [], '扫描失败', detail=str(error))]
    manifests = {path.parent for path in files if path.name.casefold() == 'manifest.json'}

    def manifest_owner(path):
        return next((parent for parent in path.parents if parent in manifests), None)

    def fallback_owner(path):
        relative = path.relative_to(root)
        return root if len(relative.parts) <= 1 else root / relative.parts[0]

    def owner(path):
        return manifest_owner(path) or fallback_owner(path)

    i18n_folders = {path for path in root.rglob('*')
                    if path.is_dir() and not path.is_symlink()
                    and not any(parent.is_symlink() for parent in path.parents)
                    and path.name.casefold() == 'i18n'}
    candidates = set(manifests)
    candidates.update(owner(folder) for folder in i18n_folders)
    candidates.update(owner(path) for path in files if path.name.casefold() == 'content.json')
    candidates = {path for path in candidates if path == root or root in path.parents}
    manifest_files = {path.parent: path for path in files if path.name.casefold() == 'manifest.json'}
    results = []

    for mod_path in sorted(candidates):
        file_statuses = []
        errors = []
        manifest = manifest_files.get(mod_path)
        name = _relative_mod_path(root, mod_path)
        if manifest:
            try:
                manifest_data = JsonDocument(manifest.read_bytes()).data
                if isinstance(manifest_data, dict) and isinstance(manifest_data.get('Name'), str):
                    name = manifest_data['Name'].strip() or name
            except Exception as error:
                errors.append(f'{manifest}: {error}')

        mod_i18n = sorted(folder for folder in i18n_folders if owner(folder) == mod_path)
        has_i18n = bool(mod_i18n)
        for folder in mod_i18n:
            try:
                siblings = [path for path in files if path.parent == folder]
                children = {path.name.casefold(): path for path in siblings}
                if len(children) != len(siblings):
                    raise ValueError('i18n 存在仅大小写不同的重名文件')
                source = children.get('default.json') or children.get('en.json')
                if source is None:
                    file_statuses.append(ModFileStatus(folder, status='待确认',
                                                       detail='i18n 缺少 default.json 或 en.json'))
                    continue
                target = children.get(f'{language_code}.json') or folder / f'{language_code}.json'
                if source == target:
                    file_statuses.append(ModFileStatus(source, status='无需翻译', detail='源文件就是目标语言'))
                    continue
                task = TranslationTask(source, target, 'i18n', mod_path)
                document = TranslationFile(task)
                translatable = {path: value for path, value in document.entries.items()
                                if core.is_translatable_text(value)}
                reusable = document.reusable(core)
                completed = len(set(reusable) & set(translatable))
                file_statuses.append(ModFileStatus(target, task, _status_from_counts(completed, len(translatable)),
                                                   completed, len(translatable)))
            except Exception as error:
                errors.append(f'{folder}: {error}')
                file_statuses.append(ModFileStatus(folder, status='扫描失败', detail=str(error)))

        if not has_i18n:
            content_paths = sorted(path for path in files if path.name.casefold() == 'content.json'
                                   and owner(path) == mod_path)
            for path in content_paths:
                try:
                    task = TranslationTask(path, path, 'content', mod_path)
                    document = TranslationFile(task)
                    translatable = document.translatable_entries(core)
                    status = '待确认' if translatable else '无需翻译'
                    detail = '原位写回前需要逐个确认' if translatable else '没有可安全翻译的文本'
                    file_statuses.append(ModFileStatus(path, task, status, 0, len(translatable), detail))
                except Exception as error:
                    errors.append(f'{path}: {error}')
                    file_statuses.append(ModFileStatus(path, status='扫描失败', detail=str(error)))

        total = sum(item.total for item in file_statuses)
        completed = sum(item.completed for item in file_statuses)
        if errors or any(item.status == '扫描失败' for item in file_statuses):
            status = '扫描失败'
        elif any(item.status == '待确认' for item in file_statuses):
            status = '待确认'
        elif all(item.status == '无需翻译' for item in file_statuses):
            status = '无需翻译'
        else:
            status = _status_from_counts(completed, total)
        results.append(ModStatus(mod_path, name, file_statuses, status, completed, total,
                                 '; '.join(errors)))
    return results


def discover_tasks(root, language_code='zh'):
    root = Path(root).resolve()
    files = [path for path in root.rglob('*') if path.is_file() and not path.is_symlink()
             and not any(parent.is_symlink() for parent in path.parents)]
    manifests = {path.parent for path in files if path.name.casefold() == 'manifest.json'}

    def owner(path):
        return next((parent for parent in path.parents if parent in manifests), path.parent)

    folders = {path.parent for path in files if path.parent.name.casefold() == 'i18n'}
    if root.name.casefold() == 'i18n':
        folders.add(root)
    owners = {owner(folder) if any(parent in manifests for parent in folder.parents) else folder.parent for folder in folders}
    tasks = []
    for folder in sorted(folders):
        siblings = [path for path in files if path.parent == folder]
        children = {path.name.casefold(): path for path in siblings}
        if len(children) != len(siblings):
            raise ValueError(f'i18n 存在仅大小写不同的重名文件，请先确认：{folder}')
        source = children.get('default.json') or children.get('en.json')
        if source:
            target = children.get(f'{language_code}.json') or folder / f'{language_code}.json'
            if source != target:
                mod_root = owner(folder) if any(parent in manifests for parent in folder.parents) else folder.parent
                tasks.append(TranslationTask(source, target, 'i18n', mod_root))
    for path in sorted(files):
        if path.name.casefold() == 'content.json' and owner(path) not in owners:
            tasks.append(TranslationTask(path, path, 'content', owner(path)))
    return tasks


def content_entries(data):
    entries = {}
    if not isinstance(data, dict) or not isinstance(data.get('Changes'), list):
        return entries
    for index, change in enumerate(data['Changes']):
        if not isinstance(change, dict) or change.get('Action') != 'EditData':
            continue
        target = change.get('Target', '')
        values = change.get('Entries')
        if not isinstance(target, str) or not isinstance(values, dict):
            continue
        if any(symbol in target for symbol in ('{', '}', ',')):
            continue
        plain = (target.startswith(('Characters/Dialogue/', 'Strings/'))
                 or target in ('Data/ExtraDialogue', 'Data/mail'))
        structured = target in ('Data/Objects', 'Data/BigCraftables', 'Data/Characters')
        for key, value in values.items():
            path = ('Changes', index, 'Entries', key)
            if plain and isinstance(value, str) and value.strip() and not re.search(
                r'(?i)(?:^|[\s/])assets/|\.(?:png|tmx|tbin|xnb|json)(?:$|\s)|^(?:[\w.-]+/)+[\w.-]+$', value
            ):
                entries[path] = value
            elif structured and isinstance(value, dict):
                for field in ('DisplayName', 'Description') if target != 'Data/Characters' else ('DisplayName',):
                    if isinstance(value.get(field), str) and value[field].strip():
                        entries[path + (field,)] = value[field]
    return entries


class TranslationFile:
    def __init__(self, task):
        self.task = task
        if has_symlink(task.source) or has_symlink(task.target):
            raise ValueError('不处理符号链接文件')
        self.source_bytes = task.source.read_bytes()
        self.document = JsonDocument(self.source_bytes)
        self.target_bytes = read_optional(task.target)
        self.target_data = JsonDocument(self.target_bytes).data if self.target_bytes is not None else {}
        self.completed_paths = set()
        if task.kind == 'i18n':
            if not isinstance(self.document.data, dict) or not isinstance(self.target_data, dict):
                raise ValueError('i18n 文件必须是 JSON 对象')
            self.entries = {(key,): value for key, value in self.document.data.items() if isinstance(value, str)}
        else:
            self.entries = content_entries(self.document.data)

    def reusable(self, core):
        if self.task.kind != 'i18n':
            return {}
        return {path: self.target_data[path[0]] for path, original in self.entries.items()
                if isinstance(self.target_data.get(path[0]), str) and self.target_data[path[0]] != original
                and core.validate_translation(original, self.target_data[path[0]])}

    def translatable_entries(self, core):
        return {path: value for path, value in self.entries.items()
                if core.is_translatable_text(value)}

    def save(self, translations, core, stop_check=None):
        if translations.keys() != self.entries.keys():
            raise ValueError('译文不完整，未保存当前文件')
        translatable = self.translatable_entries(core)
        for path, original in self.entries.items():
            translated = translations[path]
            if not isinstance(translated, str) or (
                    path in translatable and original.strip() and not core.validate_translation(original, translated)):
                raise ValueError(f'译文校验失败：{path}')
        def check_source():
            if has_symlink(self.task.source) or self.task.source.read_bytes() != self.source_bytes:
                raise ValueError('原文已变动，请重新加载后翻译')
            return stop_check() if stop_check else False

        check_source()
        if self.task.kind == 'content':
            raw = self.document.replace_strings(translations)
        elif self.target_bytes is None:
            # 新目标沿用原文结构，保留重复键、注释和 BOM。
            raw = self.document.replace_strings(translations)
        else:
            merged = dict(self.target_data)
            merged.update(self.document.data)
            merged.update({path[0]: value for path, value in translations.items()})
            if merged == self.target_data:
                raw = self.target_bytes
            elif self.target_bytes is not None and merged.keys() == self.target_data.keys():
                raw = JsonDocument(self.target_bytes).replace_strings(translations)
            else:
                raw = (json.dumps(merged, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if raw == self.target_bytes:
            if has_symlink(self.task.target) or read_optional(self.task.target) != self.target_bytes:
                raise ValueError('目标文件已变动，请重新加载后保存')
            if check_source():
                raise RuntimeError('翻译已取消，未保存当前文件')
            return self.task.target
        atomic_write(self.task.target, raw, self.target_bytes, stop_check=check_source)
        self.target_bytes = raw
        self.target_data = JsonDocument(raw).data
        if self.task.source == self.task.target:
            self.source_bytes = raw
            self.document = JsonDocument(raw)
        return self.task.target

    def save_original(self, translations, core, stop_check=None):
        """确认后原位保存 content.json，并保留历史备份。"""
        if self.task.kind != 'content' or self.task.source != self.task.target:
            raise ValueError('只有 content.json 支持原位保存')
        if translations.keys() != self.entries.keys():
            raise ValueError('译文不完整，未保存当前文件')
        translatable = self.translatable_entries(core)
        for path, original in self.entries.items():
            translated = translations[path]
            if not isinstance(translated, str) or (
                    path in translatable and original.strip() and not core.validate_translation(original, translated)):
                raise ValueError(f'译文校验失败：{path}')
        if has_symlink(self.task.source) or self.task.source.read_bytes() != self.source_bytes:
            raise ValueError('原文已变动，请重新加载后保存')
        if stop_check and stop_check():
            raise RuntimeError('翻译已取消，未保存当前文件')
        raw = self.document.replace_strings(translations)
        if raw == self.source_bytes:
            return self.task.source
        atomic_write(self.task.source, raw, self.source_bytes, stop_check=stop_check)
        self.source_bytes = raw
        self.document = JsonDocument(raw)
        return self.task.source
