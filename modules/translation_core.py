#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翻译核心模块
负责翻译逻辑的核心处理
"""

import re
from typing import Dict, List, Optional, Tuple


class TranslationCore:
    """翻译核心处理类"""
    
    def __init__(self):
        """初始化翻译核心"""
        self.placeholder_pattern = re.compile(r'{{[^}]+}}')
        self.special_chars = ['[', ']', '{', '}', '{{', '}}']
        
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
            
        # 跳过以特殊字符开头的文本
        if text.strip().startswith(('[', '{')):
            return False
            
        # 跳过纯数字或特殊符号
        if text.strip().isdigit() or text.strip() in ['', ' ', '\n', '\t']:
            return False
            
        # 跳过只包含占位符的文本
        placeholders = self.extract_placeholders(text)
        text_without_placeholders = text
        for placeholder in placeholders:
            text_without_placeholders = text_without_placeholders.replace(placeholder, '')
        
        if not text_without_placeholders.strip():
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
        original_placeholders = set(self.extract_placeholders(original))
        translation_placeholders = set(self.extract_placeholders(translation))
        
        if original_placeholders != translation_placeholders:
            return False
            
        # 检查翻译是否与原文相同（可能未翻译）
        if original.strip() == translation.strip():
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