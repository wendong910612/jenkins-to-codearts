#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CodeArts构建任务转换器
负责将Jenkins流水线中的构建步骤转换为CodeArts构建任务
"""

import os
import re
import yaml
from utils.logger import logger
from models.pipeline_model import PipelineModel

class BuildTaskConverter:
    """CodeArts构建任务转换器类"""
    
    def __init__(self, build_steps, output_path="codearts_build.yaml", pipeline_stages=None):
        """
        初始化转换器
        
        Args:
            build_steps: 构建步骤列表或PipelineModel对象
            output_path: 输出文件路径
            pipeline_stages: 解析后的Jenkins阶段列表或PipelineModel对象，用于提取参数
        """
        self.build_steps = build_steps
        self.output_path = output_path
        self.pipeline_stages = build_steps
        
        self.template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                         "templates", "build", "codearts_build.yaml")
        self.mapping_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                        "config", "build_mapping.yaml")
        self.mapping_config = self._load_mapping_config()
        
        # 记录日志
        logger.info(f"CodeArts构建任务转换器 build_steps: {build_steps}")
        logger.info(f"CodeArts构建任务转换器 pipeline_stages: {pipeline_stages}")
        logger.info(f"初始化构建任务转换器，输出路径: {output_path}")
                # 添加详细的调试日志
        logger.info(f"pipeline_stages类型: {type(pipeline_stages)}")
        if pipeline_stages is not None:
            if hasattr(pipeline_stages, '__dict__'):
                logger.info(f"pipeline_stages属性: {pipeline_stages.__dict__}")
            elif isinstance(pipeline_stages, dict):
                logger.info(f"pipeline_stages键: {pipeline_stages.keys()}")
                if 'stages' in pipeline_stages:
                    logger.info(f"pipeline_stages['stages']类型: {type(pipeline_stages['stages'])}")
                    logger.info(f"pipeline_stages['stages']长度: {len(pipeline_stages['stages'])}")
                    if pipeline_stages['stages'] and len(pipeline_stages['stages']) > 0:
                        logger.info(f"第一个阶段: {pipeline_stages['stages'][0]}")
            elif isinstance(pipeline_stages, list):
                logger.info(f"pipeline_stages列表长度: {len(pipeline_stages)}")
                if pipeline_stages and len(pipeline_stages) > 0:
                    logger.info(f"第一个元素: {pipeline_stages[0]}")
        # 安全地获取构建步骤数量
        stages_count = 0
        if pipeline_stages is not None:
            if isinstance(pipeline_stages, PipelineModel):
                pipeline_dict = pipeline_stages.to_dict()
                logger.info(f"PipelineModel转换为字典: {pipeline_dict}")
                stages = pipeline_dict.get("stages", [])
                logger.info(f"从PipelineModel获取的stages: {stages}")
                stages_count = len(stages)
            elif isinstance(pipeline_stages, dict):
                stages = pipeline_stages.get("stages", [])
                logger.info(f"从字典获取的stages: {stages}")
                stages_count = len(stages)
            elif isinstance(pipeline_stages, list):
                stages_count = len(pipeline_stages)
                logger.info(f"列表形式的stages长度: {stages_count}")
        
        logger.info(f"流水线阶段数量: {stages_count}")
    
    def _load_mapping_config(self):
        """
        加载映射配置
        
        Returns:
            dict: 映射配置
        """
        from utils.config_loader import load_mapping_config
        return load_mapping_config("build_mapping.yaml")
    
    def convert(self):
        """
        转换为CodeArts构建任务
        
        Returns:
            bool: 转换是否成功
        """
        logger.info("开始转换为CodeArts构建任务")
        
        # 加载模板
        template = self._load_template()
        if not template:
            return False
        
        # 提取参数
        params = self._extract_params()
        
        # 添加日志，确认提取到的参数
        logger.info(f"提取到 {len(params)} 个参数")
        
        # 转换构建步骤
        build_steps = self._extract_build_steps_from_stages()
        
        # 添加日志，确认转换后的构建步骤
        logger.info(f"从阶段中提取的的构建步骤数量: {len(build_steps)}")
        
        # 更新模板
        template['params'] = params
        
        # 如果没有 steps 节点，添加一个
        if 'steps' not in template:
            template['steps'] = {}
        
        # 如果没有 BUILD 节点，添加一个
        if 'BUILD' not in template['steps']:
            template['steps']['BUILD'] = []
        
        # 添加构建步骤
        template['steps']['BUILD'].extend(build_steps)
        
        # 保存到文件
        try:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                yaml.dump(template, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            logger.info(f"构建任务已保存到: {self.output_path}")
            return True
        except Exception as e:
            logger.error(f"保存构建任务失败: {str(e)}")
            return False
    
    def _extract_git_url(self):
        """
        提取Git URL
        
        Returns:
            str: Git URL
        """
        # 如果 build_steps 是 PipelineModel 对象，尝试从阶段中提取Git URL
        if isinstance(self.build_steps, PipelineModel):
            pipeline_dict = self.build_steps.to_dict()
            stages = pipeline_dict.get("stages", [])
            
            for stage in stages:
                steps = stage.get("steps", [])
                for step in steps:
                    if isinstance(step, dict):
                        command = ""
                        if "type" in step and step["type"] == "sh":
                            command = step.get("command", "")
                        elif "type" in step and step["type"] == "script":
                            command = step.get("content", "")
                        
                        # 查找Git URL
                        git_url_match = re.search(r'git\s+clone\s+(https?://[^\s]+|git@[^\s]+)', command)
                        if git_url_match:
                            return git_url_match.group(1)
        elif isinstance(self.build_steps, list):
            # 原有的处理逻辑，适用于 build_steps 是列表的情况
            for build_step in self.build_steps:
                step = build_step.get("step", {})
                content = ""
                if isinstance(step, dict):
                    if "type" in step and step["type"] == "script":
                        content = step.get("content", "")
                    elif "type" in step and step["type"] == "sh":
                        content = step.get("command", "")
                else:
                    content = str(step)
                
                # 查找Git URL
                git_url_match = re.search(r'git\s+clone\s+(https?://[^\s]+|git@[^\s]+)', content)
                if git_url_match:
                    return git_url_match.group(1)
        else:
            # 处理其他情况，例如 build_steps 为 None
            logger.warning("build_steps 类型不支持: %s", type(self.build_steps))
        
        # 如果没有找到，返回默认值
        return "https://codehub.devcloud.cn/your-repo.git"

    def _load_template(self):
        """
        加载构建任务模板
        
        Returns:
            dict: 构建任务模板
        """
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
                # 将制表符替换为空格，修复YAML解析错误
                template_content = template_content.replace('\t', '    ')
            return yaml.safe_load(template_content)
        except Exception as e:
            logger.error(f"加载构建任务模板失败: {str(e)}")
            raise
    
    def _update_template(self, template):
        """
        更新模板内容
        
        Args:
            template: 构建任务模板
        
        Returns:
            dict: 更新后的构建任务模板
        """
        # 更新版本和元数据
        template['version'] = '2.0'
        
        # 更新参数
        template['params'] = self._extract_params()
        
        # 更新构建步骤
        if 'steps' not in template:
            template['steps'] = {}
        
        # 确保PRE_BUILD和BUILD节点存在
        if 'PRE_BUILD' not in template['steps']:
            template['steps']['PRE_BUILD'] = []
        if 'BUILD' not in template['steps']:
            template['steps']['BUILD'] = []
        
        # 更新PRE_BUILD步骤
        pre_build_steps = []
        pre_build_steps.append({
            'checkout': {
                'name': '代码下载',
                'inputs': {
                    'scm': 'codehub',
                    'url': self._extract_git_url(),
                    'branch': '${GitBranch}'
                }
            }
        })
        template['steps']['PRE_BUILD'] = pre_build_steps
        
        # 更新BUILD步骤
        build_steps = []
        build_template = self._determine_build_template()
        
        # 根据构建模板添加对应的构建步骤
        if build_template == 'maven_build':
            build_steps.append({
                'maven': {
                    'name': 'Maven构建',
                    'inputs': {
                        'command': 'clean package -Dmaven.test.skip=true'
                    }
                }
            })
        elif build_template == 'gradle_build':
            build_steps.append({
                'gradle': {
                    'name': 'Gradle构建',
                    'inputs': {
                        'command': 'clean build -x test'
                    }
                }
            })
        elif build_template == 'npm_build':
            build_steps.append({
                'npm': {
                    'name': 'NPM构建',
                    'inputs': {
                        'command': 'install && npm run build'
                    }
                }
            })
        elif build_template == 'shell_build':
            # 提取shell命令
            command = self._extract_shell_command()
            build_steps.append({
                'sh': {
                    'name': '自定义构建',
                    'inputs': {
                        'command': command or 'echo "执行自定义构建步骤"'
                    }
                }
            })
        
        # 添加上传构建产物步骤
        build_steps.append({
            'upload_artifact': {
                'inputs': {
                    'path': self._determine_artifact_path(build_template)
                }
            }
        })
        
        template['steps']['BUILD'] = build_steps
        
        return template

    def _extract_shell_command(self):
        """
        提取shell命令
        
        Returns:
            str: shell命令
        """
        # 如果 build_steps 是 PipelineModel 对象，尝试从阶段中提取shell命令
        if isinstance(self.build_steps, PipelineModel):
            pipeline_dict = self.build_steps.to_dict()
            stages = pipeline_dict.get("stages", [])
            
            for stage in stages:
                steps = stage.get("steps", [])
                for step in steps:
                    if isinstance(step, dict):
                        if "type" in step and step["type"] == "sh":
                            return step.get("command", "")
                        elif "type" in step and step["type"] == "script":
                            return step.get("content", "")
        else:
            # 原有的处理逻辑，适用于 build_steps 是列表的情况
            for build_step in self.build_steps:
                step = build_step.get("step", {})
                if isinstance(step, dict):
                    if "type" in step and step["type"] == "sh":
                        return step.get("command", "")
                    elif "type" in step and step["type"] == "script":
                        return step.get("content", "")
        
        # 如果没有找到，返回空字符串
        return ""

    def _extract_build_steps_from_stages(self):
        """
        直接从阶段名称映射到 CodeArts 构建步骤
        
        Returns:
            list: 构建步骤列表
        """
        build_steps = []
        
        # 检查 pipeline_stages 是否为空
        if self.pipeline_stages is None:
            logger.warning("pipeline_stages 为空，使用默认构建步骤")
            # 添加默认的 Maven 构建步骤
            build_steps.append({
                "maven": {
                    "name": "Maven构建",
                    "inputs": {
                        "command": "clean package -Dmaven.test.skip=true"
                    }
                }
            })
            # 添加上传构建产物步骤
            build_steps.append({
                "upload_artifact": {
                    "inputs": {
                        "path": "**/target/*.?ar"
                    }
                }
            })
            return build_steps
        
        # 获取阶段列表
        stages = []
        if isinstance(self.pipeline_stages, PipelineModel):
            pipeline_dict = self.pipeline_stages.to_dict()
            stages = pipeline_dict.get("stages", [])
        elif isinstance(self.pipeline_stages, dict):
            stages = self.pipeline_stages.get("stages", [])
        elif isinstance(self.pipeline_stages, list):
            stages = self.pipeline_stages
        logger.info("pipeline_stages:{stages}")
        
        # 加载构建映射配置
        maven_stages = self.mapping_config.get("maven_stages", [])
        gradle_stages = self.mapping_config.get("gradle_stages", [])
        npm_stages = self.mapping_config.get("npm_stages", [])
        docker_stages = self.mapping_config.get("docker_stages", [])
        sh_stages = self.mapping_config.get("sh_stages", [])
        ignore_stages = self.mapping_config.get("ignore_stages", [])
        
        # 记录已添加的构建类型，避免重复添加
        added_build_types = set()
        
        # 直接根据阶段名称映射到构建步骤
        for stage in stages:
            stage_name = ""
            if isinstance(stage, dict):
                stage_name = stage.get("name", "")
            elif hasattr(stage, "name"):
                stage_name = stage.name
            
            # 跳过空阶段名
            if not stage_name:
                continue
                
            # 跳过需要忽略的阶段
            if any(ignore_stage.lower() in stage_name.lower() for ignore_stage in ignore_stages):
                logger.info(f"忽略阶段: {stage_name}")
                continue
            
            # Maven 构建步骤
            if any(maven_stage.lower() in stage_name.lower() for maven_stage in maven_stages) and "maven" not in added_build_types:
                build_steps.append({
                    "maven": {
                        "name": "Maven构建",
                        "inputs": {
                            "command": "clean package -Dmaven.test.skip=true"
                        }
                    }
                })
                added_build_types.add("maven")
                logger.info(f"添加 Maven 构建步骤，对应阶段: {stage_name}")
            
            # Gradle 构建步骤
            elif any(gradle_stage.lower() in stage_name.lower() for gradle_stage in gradle_stages) and "gradle" not in added_build_types:
                build_steps.append({
                    "gradle": {
                        "name": "Gradle构建",
                        "inputs": {
                            "command": "clean build -x test"
                        }
                    }
                })
                added_build_types.add("gradle")
                logger.info(f"添加 Gradle 构建步骤，对应阶段: {stage_name}")
            
            # NPM 构建步骤
            elif any(npm_stage.lower() in stage_name.lower() for npm_stage in npm_stages) and "npm" not in added_build_types:
                build_steps.append({
                    "npm": {
                        "name": "NPM构建",
                        "inputs": {
                            "command": "install && npm run build"
                        }
                    }
                })
                added_build_types.add("npm")
                logger.info(f"添加 NPM 构建步骤，对应阶段: {stage_name}")
            
            # Docker 构建步骤
            elif any(docker_stage.lower() in stage_name.lower() for docker_stage in docker_stages) and "docker" not in added_build_types:
                build_steps.append({
                    "sh": {
                        "name": "Docker构建",
                        "inputs": {
                            "command": "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ."
                        }
                    }
                })
                added_build_types.add("docker")
                logger.info(f"添加 Docker 构建步骤，对应阶段: {stage_name}")
            
            # Shell 构建步骤
            elif any(sh_stage.lower() in stage_name.lower() for sh_stage in sh_stages) and "sh_" + stage_name.lower() not in added_build_types:
                build_steps.append({
                    "sh": {
                        "name": f"{stage_name}",
                        "inputs": {
                            "command": f"echo '执行 {stage_name} 阶段...'"
                        }
                    }
                })
                added_build_types.add("sh_" + stage_name.lower())
                logger.info(f"添加 Shell 构建步骤，对应阶段: {stage_name}")
        
        # 如果没有找到任何构建步骤，添加默认的 Maven 构建步骤
        if not build_steps:
            logger.warning("未找到任何构建相关阶段，添加默认的 Maven 构建步骤")
            build_steps.append({
                "maven": {
                    "name": "Maven构建",
                    "inputs": {
                        "command": "clean package -Dmaven.test.skip=true"
                    }
                }
            })
        
        # 添加上传构建产物步骤
        if "maven" in added_build_types or not added_build_types:
            artifact_path = "**/target/*.?ar"
        elif "gradle" in added_build_types:
            artifact_path = "**/build/libs/*.?ar"
        elif "npm" in added_build_types:
            artifact_path = "**/dist/**"
        else:
            artifact_path = "**/target/*.?ar,**/build/libs/*.?ar,**/dist/**"
        
        build_steps.append({
            "upload_artifact": {
                "inputs": {
                    "path": artifact_path
                }
            }
        })
        
        return build_steps

    def _extract_build_steps(self):
        """
        提取构建步骤
        
        Returns:
            list: 构建步骤列表
        """
        build_steps = []
        
        # 检查 build_steps 的类型
        if self.build_steps is None:
            logger.warning("build_steps 为空，使用默认步骤")
            build_steps.append({
                "name": "默认构建",
                "command": "echo '执行默认构建步骤'\nmvn clean package -Dmaven.test.skip=true"
            })
            return build_steps
        
        # 如果 build_steps 是 PipelineModel 对象，尝试提取阶段
        if isinstance(self.build_steps, PipelineModel):
            pipeline_dict = self.build_steps.to_dict()
            stages = pipeline_dict.get("stages", [])
            
            # 从阶段中提取构建步骤
            for stage in stages:
                stage_name = stage.get("name", "")
                steps = stage.get("steps", [])
                
                # 检查是否是构建相关阶段
                is_build_stage = "build" in stage_name.lower() or "构建" in stage_name or "编译" in stage_name
                
                for step in steps:
                    step_name = step.get("name", "")
                    
                    # 检查是否是构建相关步骤
                    is_build_step = is_build_stage or "build" in step_name.lower() or "构建" in step_name
                    
                    if is_build_step:
                        command = ""
                        if isinstance(step, dict):
                            if "type" in step and step["type"] == "sh":
                                command = step.get("command", "")
                            elif "type" in step and step["type"] == "script":
                                command = step.get("content", "")
                        
                        build_steps.append({
                            "name": step_name,
                            "command": command or f"echo '执行{step_name}步骤'"
                        })
            
            # 如果没有找到构建步骤，添加默认步骤
            if not build_steps:
                build_steps.append({
                    "name": "默认构建",
                    "command": "echo '执行默认构建步骤'\nmvn clean package -Dmaven.test.skip=true"
                })
            
            return build_steps
        
        # 原有的处理逻辑，适用于 build_steps 是列表的情况
        # 遍历所有构建步骤
        for step in self.build_steps:
            step_name = step.get("name", "构建步骤")
            step_type = ""
            command = ""
            
            # 获取步骤类型和命令
            if "step" in step:
                step_info = step["step"]
                if isinstance(step_info, dict):
                    step_type = step_info.get("type", "")
                    if step_type == "sh":
                        command = step_info.get("command", "")
                    elif step_type == "script":
                        command = step_info.get("content", "")
                    else:
                        command = str(step_info)
                else:
                    command = str(step_info)
            
            # 如果命令为空，根据步骤名称生成默认命令
            if not command:
                command = self._generate_default_command(step_name, step_type)
            
            # 添加构建步骤
            build_steps.append({
                "name": step_name,
                "command": command
            })
        
        return build_steps
    
    def _create_build_task(self):
        """
        创建构建任务
        
        Returns:
            dict: 构建任务信息
        """
        # 加载构建任务模板
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
                # 将制表符替换为空格，修复YAML解析错误
                template_content = template_content.replace('\t', '    ')
            template = yaml.safe_load(template_content)
        except Exception as e:
            logger.error(f"加载构建任务模板失败: {str(e)}")
            # 使用默认模板
            template = {
                "version": "2.0",
                "params": [],
                "env": {
                    "resource": {
                        "type": "docker",
                        "arch": "X86",
                        "class": "8U16G"
                    }
                },
                "steps": {
                    "PRE_BUILD": [],
                    "BUILD": []
                }
            }
        
        # 提取参数
        if self.pipeline_stages:
            params = self._extract_params()
            if params:
                template["params"] = params
        
        # 保留原有的PRE_BUILD步骤，确保代码下载步骤不被删除
        pre_build_steps = template["steps"].get("PRE_BUILD", [])
        
        # 如果PRE_BUILD为空，添加默认的代码下载步骤
        if not pre_build_steps:
            pre_build_steps.append({
                "checkout": {
                    "name": "代码下载",
                    "inputs": {
                        "scm": "codehub",
                        "url": self._extract_git_url(),
                        "branch": "${GitBranch}"
                    }
                }
            })
        
        # 处理BUILD步骤，保留原有的maven和upload_artifact步骤
        build_steps_converted = self._convert_build_steps()
        
        # 更新模板
        template["steps"]["PRE_BUILD"] = pre_build_steps
        template["steps"]["BUILD"] = build_steps_converted
        
        return template
    
    def _convert_build_steps(self):
        """
        转换构建步骤
        
        Returns:
            list: 转换后的构建步骤
        """
        build_steps_converted = []
        
        # 1. 首先添加固定的 maven 步骤
        build_steps_converted.append({
            "maven": {
                "name": "Maven构建",
                "inputs": {
                    "command": "clean package -Dmaven.test.skip=true"
                }
            }
        })
        
        # 2. 检查是否有需要添加的 shell 命令
        # 遍历所有非 Maven 构建步骤，提取命令并使用 sh 执行
        for build_step in self.build_steps:
            stage_name = build_step.get("name", "")
            step = build_step.get("step", {})
            
            # 跳过 Maven 相关的阶段，因为已经添加了固定的 maven 步骤
            if self._is_maven_stage(stage_name):
                continue
            
            # 提取命令
            command = ""
            step_name = f"{stage_name}步骤"
            
            if isinstance(step, dict):
                if "type" in step and step["type"] == "sh":
                    command = step.get("command", "")
                elif "type" in step and step["type"] == "script":
                    command = step.get("content", "")
                else:
                    command = step.get("command", "")
            
            # 如果没有提取到命令但有原始内容，则使用原始内容
            if not command and isinstance(step, str):
                command = step
            
            # 添加 sh 步骤
            if command:
                build_steps_converted.append({
                    "sh": {
                        "name": step_name,
                        "inputs": {
                            "command": command
                        }
                    }
                })
        
        # 3. 最后添加固定的 upload_artifact 步骤
        build_steps_converted.append({
            "upload_artifact": {
                "inputs": {
                    "path": "**/target/*.?ar"
                }
            }
        })
        
        return build_steps_converted
    
    def _is_maven_stage(self, stage_name):
        """
        判断是否为 Maven 相关阶段
        
        Args:
            stage_name: 阶段名称
            
        Returns:
            bool: 是否为 Maven 相关阶段
        """
        maven_stages = ["Maven Deploy", "Build", "Maven Build", "Compile"]
        return stage_name in maven_stages
    
    def _get_build_template(self):
        """
        获取构建模板
        
        Returns:
            str: 构建模板名称
        """
        # 加载映射配置
        mapping_config = self._load_mapping_config()
        
        # 获取 Maven 相关阶段
        maven_stages = mapping_config.get("maven_stages", [])
        
        # 获取 Docker 相关阶段
        docker_stages = mapping_config.get("docker_stages", [])
        
        # 获取需要转换为sh步骤的阶段
        sh_stages = mapping_config.get("sh_stages", [])
        
        # 检查构建步骤中是否包含特定阶段
        for build_step in self.build_steps:
            stage_name = build_step.get("name", "")
            
            # 检查是否为 Maven 阶段
            if stage_name in maven_stages:
                return "maven_build"
            
            # 检查是否为 Docker 阶段
            if stage_name in docker_stages:
                return "docker_build"
            
            # 检查是否为需要转换为sh步骤的阶段
            if stage_name in sh_stages:
                return "shell_build"
        
        # 默认使用 Maven 构建
        return "maven_build"

    def _extract_clean_command(self, build_step):
        """
        提取并清理命令内容
        
        Args:
            build_step: 构建步骤
            
        Returns:
            str: 清理后的命令
        """
        step = build_step.get("step", {})
        log = build_step.get("log", "")
        step_name = build_step.get("name", "")
        stage_name = build_step.get("stage_name", "")
        
        # 检测是否包含HTML内容
        contains_html = False
        if log and (log.startswith('<!doctype') or log.startswith('<html') or '<head' in log):
            contains_html = True
        
        # 1. 首先尝试从步骤中直接提取命令
        command = ""
        if isinstance(step, dict):
            if "type" in step and step["type"] == "sh":
                command = step.get("command", "")
            elif "type" in step and step["type"] == "script":
                command = step.get("content", "")
        
        # 2. 如果没有直接的命令，根据步骤名称和阶段名称生成合理的示例命令
        if not command:
            # 根据阶段名称推断可能的命令
            if stage_name == "Unit Test" or "Unit Test" in step_name or "Test" in stage_name:
                return 'echo "执行单元测试..."\nmvn test -Dtest=*Test'
            elif stage_name == "Deploy" or "Deploy" in step_name:
                return 'echo "执行部署..."\nkubectl apply -f deployment.yaml'
            elif "Sonar" in stage_name or "SonarQube" in step_name:
                return 'echo "执行代码扫描..."\nmvn sonar:sonar -Dsonar.projectKey=${AppName}'
            elif "Image Build" in stage_name or "Docker" in step_name:
                return 'echo "构建Docker镜像..."\ndocker build -t ${ImageTag:-latest} -f Dockerfile .'
            elif "Maven" in stage_name or "Build" in stage_name:
                return 'echo "执行Maven构建..."\nmvn clean package -Dmaven.test.skip=true'
            elif "Shell Script" in step_name:
                return f'echo "执行{stage_name}脚本..."\n# 请根据实际情况修改命令'
            else:
                # 默认示例命令
                return f'echo "执行{stage_name}步骤..."\n# 请根据实际情况修改命令'
        
        # 3. 如果命令包含HTML内容，则清理或替换
        if contains_html or ('<' in command and '>' in command):
            try:
                # 使用BeautifulSoup清理HTML标签
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(command, 'html.parser')
                clean_command = soup.get_text()
                
                # 如果清理后的命令为空或太短，则生成示例命令
                if not clean_command or len(clean_command) < 10:
                    if "Unit Test" in step_name or "Test" in stage_name:
                        clean_command = 'echo "执行单元测试..."\nmvn test'
                    elif "Deploy" in step_name:
                        clean_command = 'echo "执行部署..."\nkubectl apply -f deployment.yaml'
                    else:
                        clean_command = f'echo "执行{step_name}步骤..."\n# 请根据实际情况修改命令'
                
                command = clean_command
            except ImportError:
                # 如果没有安装BeautifulSoup，使用正则表达式清理
                import re
                clean_command = re.sub(r'<[^>]+>', '', command)
                if not clean_command or len(clean_command) < 10:
                    command = f'echo "执行{step_name}步骤..."\n# 请根据实际情况修改命令'
                else:
                    command = clean_command
        
        return command

    def _determine_artifact_path(self, build_template):
        """
        确定构建产物路径
        
        Args:
            build_template: 构建模板
            
        Returns:
            str: 构建产物路径
        """
        if build_template == "maven_build":
            return "**/target/*.?ar"
        elif build_template == "gradle_build":
            return "**/build/libs/*.?ar"
        elif build_template == "npm_build":
            return "**/dist/**"
        elif build_template == "docker_build":
            return "**/target/*.?ar"
        else:
            return "**/target/*.?ar"
    
    def _extract_params(self):
        """
        提取参数
        
        Returns:
            list: 参数列表
        """
        params = []
        
        # 检查 pipeline_stages 的类型
        if self.pipeline_stages is None:
            logger.warning("pipeline_stages 为空，添加默认参数")
            # 添加默认参数
            params.append({
                "name": "GitBranch",
                "value": "main",
                "description": "Git分支名称"
            })
            params.append({
                "name": "AppName",
                "value": "",
                "description": "应用名称"
            })
            return params
        
        # 如果是 PipelineModel 对象，使用 to_dict 方法获取字典
        if isinstance(self.pipeline_stages, PipelineModel):
            pipeline_dict = self.pipeline_stages.to_dict()
            parameters = pipeline_dict.get("parameters", [])
        else:
            # 否则直接使用 pipeline_stages
            parameters = self.pipeline_stages.get("parameters", []) if isinstance(self.pipeline_stages, dict) else []
        
        # 从参数列表中提取参数
        for param in parameters:
            if isinstance(param, dict):
                name = param.get("name", "")
                value = param.get("default", param.get("value", ""))
                description = param.get("description", "")
                
                if name:
                    params.append({
                        "name": name,
                        "value": value,
                        "description": description
                    })
        
        # 检查是否需要添加必要的默认参数
        required_params = ["GitBranch", "AppName"]
        for required_param in required_params:
            exists = False
            for p in params:
                if p["name"] == required_param:
                    exists = True
                    break
            
            # 如果必要参数不存在，则添加
            if not exists:
                if required_param == "GitBranch":
                    params.append({
                        "name": "GitBranch",
                        "value": "main",
                        "description": "Git分支名称"
                    })
                elif required_param == "AppName":
                    params.append({
                        "name": "AppName",
                        "value": "",
                        "description": "应用名称"
                    })
        
        return params
    
    def _extract_git_url(self):
        """
        提取Git URL
        
        Returns:
            str: Git URL
        """
        # 如果 build_steps 是 PipelineModel 对象，尝试从阶段中提取Git URL
        if isinstance(self.build_steps, PipelineModel):
            pipeline_dict = self.build_steps.to_dict()
            stages = pipeline_dict.get("stages", [])
            
            for stage in stages:
                steps = stage.get("steps", [])
                for step in steps:
                    if isinstance(step, dict):
                        command = ""
                        if "type" in step and step["type"] == "sh":
                            command = step.get("command", "")
                        elif "type" in step and step["type"] == "script":
                            command = step.get("content", "")
                        
                        # 查找Git URL
                        git_url_match = re.search(r'git\s+clone\s+(https?://[^\s]+|git@[^\s]+)', command)
                        if git_url_match:
                            return git_url_match.group(1)
        elif isinstance(self.build_steps, list):
            # 原有的处理逻辑，适用于 build_steps 是列表的情况
            for build_step in self.build_steps:
                step = build_step.get("step", {})
                content = ""
                if isinstance(step, dict):
                    if "type" in step and step["type"] == "script":
                        content = step.get("content", "")
                    elif "type" in step and step["type"] == "sh":
                        content = step.get("command", "")
                else:
                    content = str(step)
                
                # 查找Git URL
                git_url_match = re.search(r'git\s+clone\s+(https?://[^\s]+|git@[^\s]+)', content)
                if git_url_match:
                    return git_url_match.group(1)
        else:
            # 处理其他情况，例如 build_steps 为 None
            logger.warning("build_steps 类型不支持: %s", type(self.build_steps))
        
        # 如果没有找到，返回默认值
        return "https://codehub.devcloud.cn/your-repo.git"

    def _convert_parameters(self):
        """
        转换参数
        
        Returns:
            list: 转换后的参数
        """
        params = []
        
        # 获取自定义参数
        custom_params = []
        if hasattr(self, 'pipeline_model') and isinstance(self.pipeline_model, PipelineModel):
            custom_params = self.pipeline_model.parameters
        elif isinstance(self.pipeline_stages, dict):
            custom_params = self.pipeline_stages.get("parameters", [])
        
        # 添加从Jenkins解析出的参数
        for param in custom_params:
            name = param.get("name", "")
            value = param.get("value", "")
            description = param.get("description", "")
            
            params.append({
                "name": name,
                "value": value,
                "description": description
            })
        
        # 检查是否需要添加必要的默认参数
        required_params = ["GitBranch", "AppName"]
        for required_param in required_params:
            exists = False
            for p in params:
                if p["name"] == required_param:
                    exists = True
                    break
            
            # 如果必要参数不存在，则添加
            if not exists:
                if required_param == "GitBranch":
                    params.append({
                        "name": "GitBranch",
                        "value": "main",
                        "description": "Git分支名称"
                    })
                elif required_param == "AppName":
                    params.append({
                        "name": "AppName",
                        "value": "",
                        "description": "应用名称"
                    })
        
        return params

    def _convert_build_steps(self):
        """
        转换构建步骤
        
        Returns:
            list: 转换后的构建步骤
        """
        build_steps = []
        
        # 添加 Maven 构建步骤
        maven_step = {
            "maven": {
                "name": "Maven构建",
                "image": "xxx",
                "inputs": {
                    "command": "clean package -Dmaven.test.skip=true"
                }
            }
        }
        build_steps.append(maven_step)
        
        # 添加上传构建产物步骤
        upload_step = {
            "upload_artifact": {
                "inputs": {
                    "path": "**/target/*.?ar"
                }
            }
        }
        build_steps.append(upload_step)
        
        return build_steps

    def _determine_build_template(self):
        """
        确定构建模板类型
        
        Returns:
            str: 构建模板类型
        """
        # 加载映射配置
        mapping_config = self.mapping_config
        
        # 获取各种构建类型的阶段名称
        maven_stages = mapping_config.get("maven_stages", [])
        gradle_stages = mapping_config.get("gradle_stages", [])
        npm_stages = mapping_config.get("npm_stages", [])
        docker_stages = mapping_config.get("docker_stages", [])
        shell_stages = mapping_config.get("shell_stages", [])
        
        # 如果 build_steps 是 PipelineModel 对象，尝试从阶段中提取构建工具信息
        if isinstance(self.build_steps, PipelineModel):
            pipeline_dict = self.build_steps.to_dict()
            stages = pipeline_dict.get("stages", [])
            
            for stage in stages:
                stage_name = stage.get("name", "").lower()
                
                # 根据阶段名称判断构建工具
                if any(pattern.lower() in stage_name for pattern in gradle_stages):
                    return "gradle_build"
                elif any(pattern.lower() in stage_name for pattern in npm_stages):
                    return "npm_build"
                elif any(pattern.lower() in stage_name for pattern in docker_stages):
                    return "docker_build"
                elif any(pattern.lower() in stage_name for pattern in shell_stages):
                    return "shell_build"
                elif any(pattern.lower() in stage_name for pattern in maven_stages):
                    return "maven_build"
                
                # 遍历步骤，查找构建工具信息
                steps = stage.get("steps", [])
                for step in steps:
                    if isinstance(step, dict):
                        step_name = step.get("name", "").lower()
                        command = ""
                        
                        if "type" in step and step["type"] == "sh":
                            command = step.get("command", "").lower()
                        elif "type" in step and step["type"] == "script":
                            command = step.get("content", "").lower()
                        
                        # 根据命令内容判断构建工具
                        if "gradle" in command or "./gradlew" in command:
                            return "gradle_build"
                        elif "npm" in command or "yarn" in command or "node" in command:
                            return "npm_build"
                        elif "docker" in command or "podman" in command:
                            return "docker_build"
                        elif "mvn" in command or "maven" in command:
                            return "maven_build"
        
        # 默认返回 maven_build
        return "maven_build"

    def _generate_default_command(self, step_name, step_type):
        """
        根据步骤名称和类型生成默认命令
        
        Args:
            step_name: 步骤名称
            step_type: 步骤类型
            
        Returns:
            str: 默认命令
        """
        # 根据步骤名称和类型生成默认命令
        step_name_lower = step_name.lower()
        
        # 根据步骤名称推断可能的命令
        if "test" in step_name_lower or "单元测试" in step_name_lower:
            return 'echo "执行单元测试..."\nmvn test -Dtest=*Test'
        elif "deploy" in step_name_lower or "部署" in step_name_lower:
            return 'echo "执行部署..."\nkubectl apply -f deployment.yaml'
        elif "sonar" in step_name_lower or "代码扫描" in step_name_lower:
            return 'echo "执行代码扫描..."\nmvn sonar:sonar -Dsonar.projectKey=${AppName}'
        elif "docker" in step_name_lower or "镜像" in step_name_lower:
            return 'echo "构建Docker镜像..."\ndocker build -t ${ImageTag:-latest} -f Dockerfile .'
        elif "maven" in step_name_lower or "build" in step_name_lower or "构建" in step_name_lower or "编译" in step_name_lower:
            return 'echo "执行Maven构建..."\nmvn clean package -Dmaven.test.skip=true'
        elif "gradle" in step_name_lower:
            return 'echo "执行Gradle构建..."\n./gradlew build -x test'
        elif "npm" in step_name_lower or "node" in step_name_lower:
            return 'echo "执行NPM构建..."\nnpm install && npm run build'
        elif "shell" in step_name_lower or "脚本" in step_name_lower:
            return f'echo "执行{step_name}脚本..."\n# 请根据实际情况修改命令'
        else:
            # 默认示例命令
            return f'echo "执行{step_name}步骤..."\n# 请根据实际情况修改命令'
    
    # ... 现有代码 ...