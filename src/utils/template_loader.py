#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模板加载器
负责加载华为CodeArts插件模板和映射关系
"""

import os
import json
import yaml
from utils.logger import logger

class TemplateLoader:
    """模板加载器类"""
    
    def __init__(self):
        """初始化模板加载器"""
        # 基础目录
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 模板目录
        self.template_dir = os.path.join(self.base_dir, 'templates')
        # 新增流水线模板目录
        self.pipeline_template_dir = os.path.join(self.template_dir, 'pipeline')
        
        # 确保流水线模板目录存在
        if not os.path.exists(self.pipeline_template_dir):
            os.makedirs(self.pipeline_template_dir)
            
        logger.info(f"模板目录: {self.template_dir}")
        logger.info(f"流水线模板目录: {self.pipeline_template_dir}")
        
        # 映射文件路径
        self.mapping_yaml = os.path.join(self.base_dir, 'config', 'mapping.yaml')
        self.mapping_json = os.path.join(self.base_dir, 'config', 'mapping.json')
        
        # 加载映射关系
        self.mappings = self._load_mappings()
    
    def _load_mappings(self):
        """加载映射关系配置"""
        # 优先加载JSON格式的映射文件
        if os.path.exists(self.mapping_json):
            try:
                with open(self.mapping_json, 'r', encoding='utf-8') as f:
                    logger.info(f"从JSON文件加载映射关系: {self.mapping_json}")
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载JSON映射文件失败: {str(e)}")
        
        # 如果JSON文件不存在或加载失败，尝试加载YAML文件
        if os.path.exists(self.mapping_yaml):
            try:
                with open(self.mapping_yaml, 'r', encoding='utf-8') as f:
                    logger.info(f"从YAML文件加载映射关系: {self.mapping_yaml}")
                    return yaml.safe_load(f)
            except Exception as e:
                logger.error(f"加载YAML映射文件失败: {str(e)}")
        
        logger.warning("未找到有效的映射关系配置文件")
        return {}
    
    def load_template(self, template_name):
        """
        加载模板文件
        
        Args:
            template_name: 模板文件名
            
        Returns:
            str 或 dict: 模板内容
        """
        # 检查是否是流水线模板（以.yaml结尾）
        if template_name.endswith('.yaml'):
            template_path = os.path.join(self.template_dir, template_name)
        else:
            # 首先尝试从流水线模板目录加载
            pipeline_template_path = os.path.join(self.pipeline_template_dir, f"{template_name}.yaml")
            if os.path.isfile(pipeline_template_path):
                template_path = pipeline_template_path
            else:
                # 如果流水线模板目录中不存在，尝试从基础模板目录加载
                template_path = os.path.join(self.template_dir, f"{template_name}.yaml")
        
        # 检查文件是否存在
        if not os.path.exists(template_path):
            logger.error(f"模板文件不存在: {template_path}")
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        # 读取模板文件
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 如果是从流水线模板目录加载的，尝试解析YAML
        if template_path.startswith(self.pipeline_template_dir):
            try:
                return yaml.safe_load(content)
            except Exception as e:
                logger.warning(f"解析YAML模板失败，返回原始内容: {str(e)}")
        
        # 返回原始内容
        return content
    
    def get_mapping_for_step(self, step_content):
        """
        根据步骤内容获取对应的映射关系
        
        Args:
            step_content: 步骤内容
            
        Returns:
            dict: 映射关系
        """
        if not self.mappings or 'step_mappings' not in self.mappings:
            logger.warning("映射关系配置不完整或不存在")
            return None
            
        step_content = str(step_content)  # 确保步骤内容是字符串
        
        for step_type, mapping in self.mappings['step_mappings'].items():
            if 'keywords' in mapping:
                for keyword in mapping['keywords']:
                    if keyword in step_content:
                        logger.debug(f"步骤内容匹配到关键词: {keyword}")
                        return {
                            'type': mapping['type'],
                            'plugin': mapping['plugin'],
                            'template': mapping['template'],
                            'params': mapping['params']
                        }
        
        logger.debug("步骤内容未匹配到任何关键词")
        # 如果没有匹配到，返回shell类型
        return {
            'type': 'shell',
            'plugin': 'Shell',
            'template': 'shell.yaml',
            'params': {}
        }