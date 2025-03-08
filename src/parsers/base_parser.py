#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
解析器基类
定义解析器的通用接口和方法
"""

from models.pipeline_model import PipelineModel

class BaseParser:
    """解析器基类"""
    
    def __init__(self):
        """初始化解析器"""
        self.pipeline_model = PipelineModel()
    
    def parse(self):
        """
        解析流水线
        
        Returns:
            PipelineModel: 解析后的流水线模型
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def extract_build_steps(self):
        """
        提取构建步骤
        
        Returns:
            list: 构建步骤列表
        """
        build_steps = []
        
        # 遍历所有阶段，提取构建相关的步骤
        for stage in self.pipeline_model.stages:
            stage_name = stage.get("name", "")
            
            # 跳过一些非构建相关的阶段
            if stage_name in ["Preparation", "Checkout", "Checkout Code"]:
                continue
            
            # 提取步骤
            steps = stage.get("steps", [])
            for step in steps:
                # 为步骤添加所属阶段信息
                step["stage_name"] = stage_name
                build_steps.append(step)
        
        return build_steps