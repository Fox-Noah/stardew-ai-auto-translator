
import re
from typing import Dict, List, Optional, Tuple


class TranslationCore:
    
    def __init__(self):
        self.placeholder_pattern = re.compile(r'{{[^}]+}}')
        self.special_chars = ['[', ']', '{', '}', '{{', '}}']
        
    def extract_placeholders(self, text: str) -> List[str]:
        return self.placeholder_pattern.findall(text)
    
    def preserve_placeholders(self, text: str) -> Tuple[str, Dict[str, str]]:
        placeholders = self.extract_placeholders(text)
        placeholder_map = {}
        processed_text = text
        
        for i, placeholder in enumerate(placeholders):
            temp_marker = f"__PLACEHOLDER_{i}__"
            placeholder_map[temp_marker] = placeholder
            processed_text = processed_text.replace(placeholder, temp_marker, 1)
            
        return processed_text, placeholder_map
    
    def restore_placeholders(self, text: str, placeholder_map: Dict[str, str]) -> str:
        restored_text = text
        for temp_marker, original_placeholder in placeholder_map.items():
            restored_text = restored_text.replace(temp_marker, original_placeholder)
        return restored_text
    
    def is_translatable_text(self, text: str) -> bool:
        if not text or not text.strip():
            return False
            
        if text.strip().startswith(('[', '{')):
            return False
            
        if text.strip().isdigit() or text.strip() in ['', ' ', '\n', '\t']:
            return False
            
        placeholders = self.extract_placeholders(text)
        text_without_placeholders = text
        for placeholder in placeholders:
            text_without_placeholders = text_without_placeholders.replace(placeholder, '')
        
        if not text_without_placeholders.strip():
            return False
            
        return True
    
    def clean_translation_text(self, text: str) -> str:
        if not text:
            return text
            
        cleaned = text.strip()
        
        cleaned = re.sub(r'\n+', '\n', cleaned)
        
        cleaned = re.sub(r' +', ' ', cleaned)
        
        return cleaned
    
    def validate_translation(self, original: str, translation: str) -> bool:
        if not translation or not translation.strip():
            return False
            
        original_placeholders = set(self.extract_placeholders(original))
        translation_placeholders = set(self.extract_placeholders(translation))
        
        if original_placeholders != translation_placeholders:
            return False
            
        if original.strip() == translation.strip():
            return False
            
        return True
    
    def format_translation_prompt(self, text: str, target_lang: str, examples: List[Tuple[str, str]] = None) -> str:
        prompt_parts = [
            f"请将以下文本翻译成{target_lang}，保持原有的格式和占位符不变："
        ]
        
        if examples:
            prompt_parts.append("\n翻译示例：")
            for original, translated in examples[:3]:
                prompt_parts.append(f"原文：{original}")
                prompt_parts.append(f"译文：{translated}")
        
        prompt_parts.extend([
            "\n请翻译以下文本：",
            f"原文：{text}",
            "译文："
        ])
        
        return "\n".join(prompt_parts)
    
    def extract_translation_from_response(self, response: str) -> str:
        if not response:
            return ""
            
        translation_match = re.search(r'译文[：:](.*?)(?:\n|$)', response, re.DOTALL)
        if translation_match:
            return translation_match.group(1).strip()
            
        return self.clean_translation_text(response)
    
    def batch_process_texts(self, texts: List[str], processor_func) -> List[str]:
        results = []
        for text in texts:
            try:
                result = processor_func(text)
                results.append(result if result else text)
            except Exception:
                results.append(text)
                
        return results
    
    def calculate_translation_progress(self, completed: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return min(100.0, (completed / total) * 100.0)
    
    def estimate_translation_time(self, text_count: int, avg_time_per_text: float = 2.0) -> int:
        return int(text_count * avg_time_per_text)