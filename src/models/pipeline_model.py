#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Jenkins 流水线数据模型
定义统一的数据结构，用于存储从不同来源解析的 Jenkins 流水线信息
"""

from utils.logger import logger

class PipelineModel:
    """Jenkins 流水线数据模型"""
    
    def __init__(self):
        """初始化流水线数据模型"""
        self.name = ""
        self.type = ""
        self.parameters = []
        self.environment = {}
        self.agent = {"type": "any"}
        self.stages = []
        self.build_steps = []
        self.scm = {}  # 添加 SCM 属性
        self.xml_content = ""  # 添加原始XML内容
    
    def add_parameter(self, name, value="", description=""):
        """添加参数"""
        self.parameters.append({
            "name": name,
            "value": value,
            "description": description
        })
    
    def add_environment(self, name, value):
        """添加环境变量"""
        self.environment[name] = value
    
    def add_stage(self, stage):
        """添加阶段"""
        self.stages.append(stage)
        logger.info(f"添加阶段: {stage.get('name', '未命名')}")
    
    def add_build_step(self, name, type, command="", stage=""):
        """
        添加构建步骤
        
        Args:
            name: 步骤名称
            type: 步骤类型
            command: 步骤命令
            stage: 所属阶段
        """
        self.build_steps.append({
            "name": name,
            "type": type,
            "command": command,
            "stage": stage
        })
    
    def set_scm(self, url, branch="master"):
        """
        设置 SCM 信息
        
        Args:
            url: Git 仓库 URL
            branch: Git 分支
        """
        self.scm = {
            "url": url,
            "branch": branch
        }
        logger.info(f"设置 SCM 信息: URL={url}, branch={branch}")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "name": self.name,
            "parameters": self.parameters,
            "environment": self.environment,
            "agent": self.agent,
            "stages": self.stages,
            "build_steps": self.build_steps,
            "scm": self.scm
        }