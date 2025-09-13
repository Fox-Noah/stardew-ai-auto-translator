
import json
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    
    def __init__(self, config_file_path: Path):
        self.config_file = config_file_path
        self.config_data = {}
        
        self.default_config = {
            'ui_language': '中文',
            'ollama_model': '',
            'batch_size': 5,
            'auto_save_interval': 20
        }
        
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                    
                for key, value in self.default_config.items():
                    if key not in self.config_data:
                        self.config_data[key] = value
                        
                if len(self.config_data) != len(self.default_config):
                    self.save_config()
            else:
                self.config_data = self.default_config.copy()
                self.save_config()
                
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self.config_data = self.default_config.copy()
            self.save_config()
            
        return self.config_data
    
    def save_config(self) -> bool:
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
            return True
            
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.config_data.get(key, default)
    
    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        self.config_data[key] = value
        if auto_save:
            self.save_config()
    
    def update(self, config_dict: Dict[str, Any], auto_save: bool = True) -> None:
        self.config_data.update(config_dict)
        if auto_save:
            self.save_config()
    
    def reset_to_default(self) -> None:
        self.config_data = self.default_config.copy()
        self.save_config()
    
    def get_ui_language(self) -> str:
        return self.get('ui_language', '中文')
    
    def set_ui_language(self, language: str) -> None:
        self.set('ui_language', language)
    
    def get_ollama_model(self) -> str:
        return self.get('ollama_model', '')
    
    def set_ollama_model(self, model: str) -> None:
        self.set('ollama_model', model)
    
    def get_batch_size(self) -> int:
        return self.get('batch_size', 5)
    
    def set_batch_size(self, size: int) -> None:
        self.set('batch_size', size)
    
    def get_auto_save_interval(self) -> int:
        return self.get('auto_save_interval', 20)
    
    def set_auto_save_interval(self, interval: int) -> None:
        self.set('auto_save_interval', interval)
    
    def get_all_config(self) -> Dict[str, Any]:
        return self.config_data.copy()
    
    def is_valid_config(self) -> bool:
        try:
            required_keys = ['ui_language', 'ollama_model', 'batch_size', 'auto_save_interval']
            for key in required_keys:
                if key not in self.config_data:
                    return False
            
            if not isinstance(self.config_data['batch_size'], int) or self.config_data['batch_size'] <= 0:
                return False
            
            if not isinstance(self.config_data['auto_save_interval'], int) or self.config_data['auto_save_interval'] <= 0:
                return False
            
            return True
            
        except Exception:
            return False