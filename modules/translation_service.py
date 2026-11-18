"""按所选协议发送翻译请求；错误直接交给任务层，避免回写原文冒充成功。"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import threading
from urllib.parse import urlsplit

import requests

from .translation_core import TranslationCore


DEFAULT_PROVIDER = {
    'name': '本地 Ollama', 'protocol': 'ollama',
    'base_url': 'http://localhost:11434', 'model': '', 'api_key': ''
}


def ollama_server_url(base_url):
    base_url = base_url.strip().rstrip('/')
    for suffix in ('/api/chat', '/api'):
        if base_url.endswith(suffix):
            return base_url[:-len(suffix)]
    return base_url


class TranslationService:
    def __init__(self, provider, prompt='', glossary=None):
        self.provider = dict(provider)
        self.core = TranslationCore(glossary)
        self.prompt = prompt
        self.protocol = provider.get('protocol', '')
        if self.protocol not in ('ollama', 'openai', 'anthropic'):
            raise ValueError('请选择 Ollama、OpenAI 或 Anthropic 协议')
        base_url = provider.get('base_url', '').strip().rstrip('/')
        parsed = urlsplit(base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('接口地址必须是无内嵌认证、查询参数的 HTTP(S) 地址')
        if not isinstance(prompt, str):
            raise ValueError('提示词必须是文本')
        self.model = provider.get('model', '').strip()
        self.api_key = provider.get('api_key', '').strip()
        if not self.model:
            raise ValueError('请设置翻译模型')
        if self.protocol != 'ollama' and not self.api_key:
            raise ValueError('请设置 API 密钥')
        suffix = {'ollama': '/api/chat', 'openai': '/chat/completions', 'anthropic': '/messages'}[self.protocol]
        if self.protocol == 'ollama':
            base_url = ollama_server_url(base_url)
        if self.protocol != 'ollama' and not parsed.path.strip('/'):
            base_url += '/v1'
        self.url = base_url if base_url.endswith(suffix) else base_url + suffix

    def translate_single_text(self, text, target_lang):
        masked, replacements = self.core.protect_text(text)
        plain = masked
        for marker in replacements:
            plain = plain.replace(marker, '')
        if not re.search(r'[^\W\d_]', plain):
            return self.core.finish_translation(text, masked, replacements) if text.strip() else text
        system = (
            f'将用户文本翻译成 {target_lang}，只返回译文，不加引号、解释或代码围栏。\n'
            f'用户风格要求：\n{self.prompt}\n'
            '最高优先级：原样保留每一个 __SDV_ 开头的标记，次数与顺序不变。'
            '标记代表游戏语法或指定译法，任何风格要求均不得覆盖此约束。'
        )
        messages = [{'role': 'user', 'content': masked}]
        body = {'model': self.model, 'messages': messages, 'stream': False}
        headers = {'Content-Type': 'application/json'}
        if self.protocol == 'anthropic':
            body.update(system=system, max_tokens=4096)
            headers.update({'x-api-key': self.api_key, 'anthropic-version': '2023-06-01'})
        else:
            messages.insert(0, {'role': 'system', 'content': system})
            if self.protocol == 'openai':
                headers['Authorization'] = 'Bearer ' + self.api_key
        try:
            response = requests.post(self.url, headers=headers, json=body, timeout=(10, 120), allow_redirects=False)
        except requests.RequestException:
            raise RuntimeError('供应商请求失败，请检查网络、接口地址及超时设置') from None
        if response.status_code != 200:
            reason = {401: '认证失败', 403: '访问被拒绝', 429: '请求限流或额度不足'}.get(response.status_code, '供应商请求失败')
            raise RuntimeError(f'{reason}（HTTP {response.status_code}）')
        try:
            payload = response.json()
            if self.protocol == 'anthropic':
                if payload.get('stop_reason') != 'end_turn':
                    raise ValueError('响应未完整结束')
                translated = ''.join(block['text'] for block in payload['content'] if block.get('type') == 'text')
            elif self.protocol == 'openai':
                choice = payload['choices'][0]
                if choice.get('finish_reason') != 'stop':
                    raise ValueError('响应未完整结束')
                translated = choice['message']['content']
            else:
                if payload.get('done') is not True or payload.get('done_reason') == 'length':
                    raise ValueError('响应未完整结束')
                translated = payload['message']['content']
            if not isinstance(translated, str) or not translated.strip():
                raise ValueError('缺少译文')
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise RuntimeError('供应商返回了不完整或无法识别的译文') from None
        return self.core.finish_translation(text, translated, replacements)

    def translate_batch_async(self, texts, target_lang, batch_size=5, progress_callback=None,
                              stop_check=None, result_callback=None):
        if not 1 <= batch_size <= 32:
            raise ValueError('并发数量必须在 1 到 32 之间')
        if not texts:
            return []
        aborted = threading.Event()
        results = [None] * len(texts)

        def translate(text):
            if aborted.is_set() or (stop_check and stop_check()):
                raise RuntimeError('翻译已取消，未保存当前文件')
            return self.translate_single_text(text, target_lang)

        with ThreadPoolExecutor(max_workers=min(batch_size, len(texts))) as executor:
            futures = {executor.submit(translate, text): index for index, text in enumerate(texts)}
            try:
                for completed, future in enumerate(as_completed(futures), 1):
                    if stop_check and stop_check():
                        raise RuntimeError('翻译已取消，未保存当前文件')
                    index = futures[future]
                    results[index] = future.result()
                    if result_callback:
                        result_callback(index, texts[index], results[index])
                    if progress_callback:
                        progress_callback(completed, len(texts), '')
            except Exception:
                aborted.set()
                for future in futures:
                    future.cancel()
                raise
        return results
