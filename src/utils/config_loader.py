#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置加载工具
负责加载和处理配置文件
"""

import os
import yaml
from utils.logger import logger

def load_mapping_config(config_name="build_mapping.yaml"):
    """
    加载映射配置
    
    Args:
        config_name: 配置文件名称
        
    Returns:
        dict: 映射配置
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                              "config", config_name)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            mapping_config = yaml.safe_load(f)
        return mapping_config or {}
    except Exception as e:
        logger.error(f"加载映射配置失败: {str(e)}")
        return {}