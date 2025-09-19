#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
负责应用程序配置的加载、保存和管理
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file_path: Path):
        """初始化配置管理器
        
        Args:
            config_file_path: 配置文件路径
        """
        self.config_file = config_file_path
        self.config_data = {}
        
        # 默认配置
        self.default_config = {
            'ui_language': '中文',
            'ollama_model': '',  # 不再硬编码，由程序自动获取
            'batch_size': 5,
            'auto_save_interval': 20
        }
        
        # 加载配置
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件
        
        Returns:
            配置数据字典
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                    
                # 确保所有默认配置项都存在
                for key, value in self.default_config.items():
                    if key not in self.config_data:
                        self.config_data[key] = value
                        
                # 如果有新增的默认配置项，保存配置
                if len(self.config_data) != len(self.default_config):
                    self.save_config()
            else:
                # 配置文件不存在，使用默认配置
                self.config_data = self.default_config.copy()
                self.save_config()
                
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            # 配置文件损坏时使用默认配置
            self.config_data = self.default_config.copy()
            self.save_config()
            
        return self.config_data
    
    def save_config(self) -> bool:
        """保存配置文件
        
        Returns:
            保存是否成功
        """
        try:
            # 确保配置目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
            return True
            
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项
        
        Args:
            key: 配置项键名
            default: 默认值
            
        Returns:
            配置项值
        """
        return self.config_data.get(key, default)
    
    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        """设置配置项
        
        Args:
            key: 配置项键名
            value: 配置项值
            auto_save: 是否自动保存
        """
        self.config_data[key] = value
        if auto_save:
            self.save_config()
    
    def update(self, config_dict: Dict[str, Any], auto_save: bool = True) -> None:
        """批量更新配置项
        
        Args:
            config_dict: 配置字典
            auto_save: 是否自动保存
        """
        self.config_data.update(config_dict)
        if auto_save:
            self.save_config()
    
    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self.config_data = self.default_config.copy()
        self.save_config()
    
    def get_ui_language(self) -> str:
        """获取界面语言"""
        return self.get('ui_language', '中文')
    
    def set_ui_language(self, language: str) -> None:
        """设置界面语言"""
        self.set('ui_language', language)
    
    def get_ollama_model(self) -> str:
        """获取Ollama模型"""
        return self.get('ollama_model', '')
    
    def set_ollama_model(self, model: str) -> None:
        """设置Ollama模型"""
        self.set('ollama_model', model)
    
    def get_batch_size(self) -> int:
        """获取批处理大小"""
        return self.get('batch_size', 5)
    
    def set_batch_size(self, size: int) -> None:
        """设置批处理大小"""
        self.set('batch_size', size)
    
    def get_auto_save_interval(self) -> int:
        """获取自动保存间隔"""
        return self.get('auto_save_interval', 20)
    
    def set_auto_save_interval(self, interval: int) -> None:
        """设置自动保存间隔"""
        self.set('auto_save_interval', interval)
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config_data.copy()
    
    def is_valid_config(self) -> bool:
        """检查配置是否有效"""
        try:
            # 检查必要的配置项是否存在
            required_keys = ['ui_language', 'ollama_model', 'batch_size', 'auto_save_interval']
            for key in required_keys:
                if key not in self.config_data:
                    return False
            
            # 检查数值类型配置的有效性
            if not isinstance(self.config_data['batch_size'], int) or self.config_data['batch_size'] <= 0:
                return False
            
            if not isinstance(self.config_data['auto_save_interval'], int) or self.config_data['auto_save_interval'] <= 0:
                return False
            
            return True
            
        except Exception:
            return False