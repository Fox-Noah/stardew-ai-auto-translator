#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翻译核心模块
负责翻译逻辑的核心处理
"""

import re
import uuid
from collections import Counter
from typing import Dict, List, Optional, Tuple


NAMED_PLACEHOLDER = re.compile(r'\{\{[A-Za-z_][A-Za-z0-9_]*\}\}(?:%(?![A-Za-z0-9_%]))?')


class TranslationCore:
    """翻译核心处理类"""
    
    def __init__(self, glossary=None):
        """初始化翻译核心"""
        self.placeholder_pattern = re.compile(r'{{[^}]+}}')
        self.special_chars = ['[', ']', '{', '}', '{{', '}}']
        self.glossary = {} if glossary is None else glossary
        if not isinstance(self.glossary, dict) or any(
            not isinstance(source, str) or not source.strip()
            or not isinstance(target, str) or not target.strip()
            for source, target in self.glossary.items()
        ):
            raise ValueError('术语必须是非空的“原词 → 指定译法”字典')
        self.control_pattern = re.compile(
            f'{NAMED_PLACEHOLDER.pattern}|'
            r'\{\{[^{}]*\}\}|\{[^{}]*\}|\[[^\]\r\n]*\]|https?://[^\s]+|'
            r'%item\b[^\r\n]*?%%|%(?:\d+\$)?[sdif]|%[A-Za-z_][A-Za-z0-9_]*|'
            r'#\$[qrcedy][^#\r\n]*#|\$[A-Za-z0-9_]+(?:[ \t]+\d+(?:[./]\d+)*)*|[#^@|~%]|\r\n|\r|\n'
        )
        for source, target in self.glossary.items():
            if self.control_pattern.search(source) or self.control_pattern.search(target):
                raise ValueError('术语不能包含占位符或游戏控制符')
        patterns = []
        for source in sorted(self.glossary, key=len, reverse=True):
            left = r'(?<!\w)' if re.match(r'\w', source[0]) else ''
            right = r'(?!\w)' if re.match(r'\w', source[-1]) else ''
            patterns.append(left + re.escape(source) + right)
        self.term_pattern = re.compile('|'.join(patterns)) if patterns else None

    def protect_text(self, text):
        """先保护游戏语法，再以最长匹配保护术语。"""
        prefix = '__SDV_' + uuid.uuid4().hex + '_'
        replacements = {}

        def protect(value):
            marker = f'{prefix}{len(replacements)}__'
            replacements[marker] = value
            return marker

        parts = []
        offset = 0
        for match in self.control_pattern.finditer(text):
            plain = text[offset:match.start()]
            if self.term_pattern:
                plain = self.term_pattern.sub(lambda term: protect(self.glossary[term.group()]), plain)
            parts.extend((plain, protect(match.group())))
            offset = match.end()
        plain = text[offset:]
        if self.term_pattern:
            plain = self.term_pattern.sub(lambda term: protect(self.glossary[term.group()]), plain)
        parts.append(plain)
        return ''.join(parts), replacements

    @staticmethod
    def _token_order(tokens, replacements=None):
        """只允许同一语段内的命名占位符换位。"""
        replacements = replacements or {}
        order = []
        named = []
        for token in tokens:
            if NAMED_PLACEHOLDER.fullmatch(replacements.get(token, token)):
                named.append(token)
            else:
                order.extend(sorted(named))
                named.clear()
                order.append(token)
        return order + sorted(named)

    def finish_translation(self, original, translated, replacements):
        """拒绝缺失、重复或非法换位的标记。"""
        if any(translated.count(marker) != 1 for marker in replacements):
            raise ValueError('翻译丢失或重复了受保护标记')
        if replacements:
            pattern = re.compile('|'.join(map(re.escape, replacements)))
            markers = pattern.findall(translated)
            if self._token_order(markers, replacements) != self._token_order(replacements, replacements):
                raise ValueError('翻译改变了受保护标记的顺序')
            translated = pattern.sub(lambda match: replacements[match.group()], translated)
        if '__SDV_' in translated and '__SDV_' not in original:
            raise ValueError('翻译包含无法识别的临时标记')
        if not self.validate_translation(original, translated):
            raise ValueError('翻译未通过占位符、控制符或指定译法校验')
        return translated

    def _plain_text(self, text):
        return self.control_pattern.sub(' ', text)
        
    def extract_placeholders(self, text: str) -> List[str]:
        """提取文本中的占位符
        
        Args:
            text: 输入文本
            
        Returns:
            占位符列表
        """
        return self.placeholder_pattern.findall(text)
    
    def preserve_placeholders(self, text: str) -> Tuple[str, Dict[str, str]]:
        """保护占位符，替换为临时标记
        
        Args:
            text: 原始文本
            
        Returns:
            (处理后的文本, 占位符映射)
        """
        placeholders = self.extract_placeholders(text)
        placeholder_map = {}
        processed_text = text
        
        for i, placeholder in enumerate(placeholders):
            temp_marker = f"__PLACEHOLDER_{i}__"
            placeholder_map[temp_marker] = placeholder
            processed_text = processed_text.replace(placeholder, temp_marker, 1)
            
        return processed_text, placeholder_map
    
    def restore_placeholders(self, text: str, placeholder_map: Dict[str, str]) -> str:
        """恢复占位符
        
        Args:
            text: 处理后的文本
            placeholder_map: 占位符映射
            
        Returns:
            恢复占位符后的文本
        """
        restored_text = text
        for temp_marker, original_placeholder in placeholder_map.items():
            restored_text = restored_text.replace(temp_marker, original_placeholder)
        return restored_text
    
    def is_translatable_text(self, text: str) -> bool:
        """判断文本是否需要翻译
        
        Args:
            text: 待检查的文本
            
        Returns:
            是否需要翻译
        """
        if not text or not text.strip():
            return False
            
        plain = self._plain_text(text).strip()
        if not plain or not any(character.isalpha() for character in plain):
            return False
        if re.search(r'(?i)(?:^|[\s/])assets/|\.(?:png|tmx|tbin|xnb|json)(?:$|\s)', plain):
            return False
        return True
    
    def clean_translation_text(self, text: str) -> str:
        """清理翻译文本
        
        Args:
            text: 原始翻译文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return text
            
        # 移除首尾空白
        cleaned = text.strip()
        
        # 移除多余的换行符
        cleaned = re.sub(r'\n+', '\n', cleaned)
        
        # 移除多余的空格
        cleaned = re.sub(r' +', ' ', cleaned)
        
        return cleaned
    
    def validate_translation(self, original: str, translation: str) -> bool:
        """验证翻译质量
        
        Args:
            original: 原文
            translation: 译文
            
        Returns:
            翻译是否有效
        """
        if not translation or not translation.strip():
            return False
            
        # 检查占位符是否保持一致
        original_placeholders = self.control_pattern.findall(original)
        translation_placeholders = self.control_pattern.findall(translation)
        
        if self._token_order(original_placeholders) != self._token_order(translation_placeholders):
            return False
            
        # 指定译法按最长项计数，避免长译名掩盖短译名缺失
        if self.term_pattern:
            required = Counter(self.glossary[match.group()] for match in self.term_pattern.finditer(self._plain_text(original)))
            plain_translation = self._plain_text(translation)
            source_remainder = self.term_pattern.sub('', self._plain_text(original))
            allow_embedded_cjk = any(character.isalpha() for character in source_remainder) or sum(required.values()) > 1
            target_patterns = []
            for target in sorted(set(self.glossary.values()), key=len, reverse=True):
                cjk = r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]'
                left = r'(?<!\w)' if target[0].isascii() and target[0].isalnum() else ''
                right = r'(?!\w)' if target[-1].isascii() and target[-1].isalnum() else ''
                if not allow_embedded_cjk and re.match(cjk, target[0]):
                    left = rf'(?<!{cjk})'
                if not allow_embedded_cjk and re.match(cjk, target[-1]):
                    right = rf'(?!{cjk})'
                target_patterns.append(left + re.escape(target) + right)
            targets = re.compile('|'.join(target_patterns))
            actual = Counter(targets.findall(plain_translation))
            if any(actual[target] < count for target, count in required.items()):
                return False
            
        return True
    
    def format_translation_prompt(self, text: str, target_lang: str, examples: List[Tuple[str, str]] = None) -> str:
        """格式化翻译提示词
        
        Args:
            text: 待翻译文本
            target_lang: 目标语言
            examples: 翻译示例
            
        Returns:
            格式化的提示词
        """
        prompt_parts = [
            f"请将以下文本翻译成{target_lang}，保持原有的格式和占位符不变："
        ]
        
        if examples:
            prompt_parts.append("\n翻译示例：")
            for original, translated in examples[:3]:  # 最多使用3个示例
                prompt_parts.append(f"原文：{original}")
                prompt_parts.append(f"译文：{translated}")
        
        prompt_parts.extend([
            "\n请翻译以下文本：",
            f"原文：{text}",
            "译文："
        ])
        
        return "\n".join(prompt_parts)
    
    def extract_translation_from_response(self, response: str) -> str:
        """从响应中提取翻译结果
        
        Args:
            response: AI响应文本
            
        Returns:
            提取的翻译文本
        """
        if not response:
            return ""
            
        # 尝试提取"译文："后的内容
        translation_match = re.search(r'译文[：:](.*?)(?:\n|$)', response, re.DOTALL)
        if translation_match:
            return translation_match.group(1).strip()
            
        # 如果没有找到标记，返回整个响应的清理版本
        return self.clean_translation_text(response)
    
    def batch_process_texts(self, texts: List[str], processor_func) -> List[str]:
        """批量处理文本
        
        Args:
            texts: 文本列表
            processor_func: 处理函数
            
        Returns:
            处理后的文本列表
        """
        results = []
        for text in texts:
            try:
                result = processor_func(text)
                results.append(result if result else text)
            except Exception:
                results.append(text)  # 处理失败时保持原文
                
        return results
    
    def calculate_translation_progress(self, completed: int, total: int) -> float:
        """计算翻译进度
        
        Args:
            completed: 已完成数量
            total: 总数量
            
        Returns:
            进度百分比 (0-100)
        """
        if total <= 0:
            return 0.0
        return min(100.0, (completed / total) * 100.0)
    
    def estimate_translation_time(self, text_count: int, avg_time_per_text: float = 2.0) -> int:
        """估算翻译时间
        
        Args:
            text_count: 文本数量
            avg_time_per_text: 每个文本的平均翻译时间（秒）
            
        Returns:
            估算时间（秒）
        """
        return int(text_count * avg_time_per_text)
