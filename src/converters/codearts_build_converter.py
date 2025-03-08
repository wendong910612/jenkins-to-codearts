#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CodeArts构建任务转换器
负责将Jenkins流水线或Freestyle项目中的构建步骤转换为CodeArts构建任务
"""

import os
import re
import yaml
import json
from utils.logger import logger
from models.pipeline_model import PipelineModel

class CodeArtsBuildConverter:
    """CodeArts构建任务转换器类"""
    
    def __init__(self, pipeline_model, output_path="codearts_build.yaml"):
        """
        初始化转换器
        
        Args:
            pipeline_model: PipelineModel对象
            output_path: 输出文件路径
        """
        self.pipeline_model = pipeline_model
        self.output_path = output_path
        
        # 初始化构建任务YAML - 移除 env.resource 部分
        self.build_yaml = {
            "version": "2.0",
            "params": [],
            "steps": {
                "PRE_BUILD": [],
                "BUILD": []
            }
        }
        
        # 加载模板
        self.template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                         "templates", "build", "codearts_build.yaml")
        
        # 保存模板中的 PRE_BUILD 步骤
        self.template_pre_build_steps = []
        
        # 记录日志
        logger.info(f"初始化CodeArts构建任务转换器，输出路径: {output_path}")
    
    def convert(self):
        """
        转换为CodeArts构建任务
        
        Returns:
            bool: 转换是否成功
        """
        try:
            logger.info("开始转换为CodeArts构建任务")
            
            # 加载模板
            self._load_template()
            
            # 提取参数
            params = self._extract_params()
            if params:
                self.build_yaml['params'] = params
            elif 'params' in self.build_yaml:
                del self.build_yaml['params']
            
            # 提取Git URL
            git_url = self._extract_git_url_from_model()
            
            # 转换构建步骤
            build_steps = self._convert_build_steps()
            
            # 更新构建任务YAML
            self.build_yaml['steps'] = {
                'PRE_BUILD': [],
                'BUILD': build_steps
            }
            
            # 添加Git检出步骤
            self.build_yaml['steps']['PRE_BUILD'].append({
                'checkout': {
                    'name': '代码下载',
                    'inputs': {
                        'scm': 'codehub',
                        'url': git_url if git_url else "https://codehub.devcloud.cn-north-4.huaweicloud.com/your-repo.git",
                        'branch': 'master',
                        'lfs': False,
                        'submodule': False
                    
                    }
                }
            })
            
            # 保存到文件
            with open(self.output_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.build_yaml, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            logger.info(f"构建任务已保存到: {self.output_path}")
            return True
        except Exception as e:
            logger.error(f"转换为CodeArts构建任务失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _load_template(self):
        """
        加载构建任务模板
        """
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
                # 将制表符替换为空格，修复YAML解析错误
                template_content = template_content.replace('\t', '    ')
                template = yaml.safe_load(template_content)
                
                # 更新构建任务YAML
                if template:
                    # 更新 params
                    if 'params' in template:
                        self.build_yaml['params'] = template['params']
                    
                    # 保存模板中的 PRE_BUILD 步骤，以便在没有 Git 步骤时使用
                    if 'steps' in template and 'PRE_BUILD' in template['steps']:
                        self.template_pre_build_steps = template['steps']['PRE_BUILD']
            
            logger.info("成功加载构建任务模板")
        except Exception as e:
            logger.warning(f"加载构建任务模板失败: {str(e)}，使用默认模板")
            # 设置默认的 PRE_BUILD 步骤
            self.template_pre_build_steps = [{
                'checkout': {
                    'name': '代码下载',
                    'inputs': {
                        'scm': 'codehub',
                        'url': 'https://codehub.devcloud.cn/your-repo.git',
                        'branch': 'master',
                        'lfs': False,
                        'submodule': False
                    }
                }
            }]
    
    def _extract_params(self):
        """
        从pipeline_model中提取参数
        
        Returns:
            list: 参数列表
        """
        params = []
        
        # 严格校验参数有效性
        if hasattr(self.pipeline_model, 'parameters') and isinstance(self.pipeline_model.parameters, list):
            for param in self.pipeline_model.parameters:
                if isinstance(param, dict) and param.get('name'):
                    # 过滤空值参数
                    if param.get('value') or param.get('description'):
                        params.append({
                            'name': param['name'],
                            'value': param.get('value', ''),
                            'description': param.get('description', '')
                        })
        
        # 完全移除空参数
        return params if params else None
    
    def _process_build_steps(self, build_steps):
        """
        处理构建步骤
        
        Args:
            build_steps: 构建步骤列表
        """
        logger.info(f"处理 {len(build_steps)} 个构建步骤")
        
        # 清空模板中可能存在的步骤
        
        # 标记是否已添加上传构件步骤和Git检出步骤
        upload_artifact_added = False
        git_step_added = False
        
        for step in build_steps:
            # 检查步骤是否有 stage 属性，如果没有则设置默认值
            step_stage = step.get('stage', 'Build') if isinstance(step, dict) else 'Build'
            
            # 根据步骤类型处理
            if isinstance(step, dict) and 'type' in step:
                step_type = step['type']
                step_name = step.get('name', '')
                
                if step_type == 'git':
                    self._add_git_step(step)
                    git_step_added = True
                elif step_type == 'maven':
                    logger.info(f"添加 Maven 构建步骤，对应阶段: {step_stage}")
                    self._add_maven_step(step, upload_artifact_added)
                    upload_artifact_added = True  # 标记已添加上传构件步骤
                elif step_type == 'shell' or step_type == 'sh':
                    self._add_shell_step(step)
                elif step_type == 'ssh':
                    self._add_ssh_step(step)
                else:
                    logger.warning(f"未知的构建步骤类型: {step_type}")
            else:
                logger.warning(f"无效的构建步骤: {step}")
        
        # 如果没有添加Git检出步骤，添加一个默认的
        if not git_step_added:
            # 尝试从pipeline_model中提取Git URL
            git_url = self._extract_git_url_from_model()
            
            # 添加默认的Git检出步骤
            self.build_yaml['steps']['PRE_BUILD'].append({
                'checkout': {
                    'name': '代码下载',
                    'inputs': {
                        'scm': 'codehub',
                        'url': git_url,
                        'branch': 'master',
                        'lfs': False,
                        'submodule': False
                    }
                }
            })
            logger.info(f"添加默认的Git检出步骤，URL: {git_url}")
        
        # 如果没有添加过上传构件步骤，添加一个默认的
        if not upload_artifact_added and any(step.get('type') == 'maven' for step in build_steps if isinstance(step, dict)):
            self.build_yaml['steps']['BUILD'].append({
                'upload_artifact': {
                    'inputs': {
                        'path': '**/target/*.?ar'
                    }
                }
            })

    def _extract_git_url_from_model(self):
        """
        从pipeline_model中提取Git URL
        
        Returns:
            str: Git URL
        """
        git_url = None
        
        try:
            # 首先检查是否有直接保存的git_url
            if hasattr(self.pipeline_model, 'scm') and self.pipeline_model.scm:
                if isinstance(self.pipeline_model.scm, dict) and 'url' in self.pipeline_model.scm:
                    git_url = self.pipeline_model.scm['url']
                    logger.info(f"从scm属性中提取到Git URL: {git_url}")
                    return git_url
                
            # 尝试从XML内容中提取Git URL
            if hasattr(self.pipeline_model, 'xml_content') and self.pipeline_model.xml_content:
                logger.info("尝试从XML内容中提取Git URL")
                
                # 使用正则表达式提取URL
                import re
                url_match = re.search(r'<url>(.*?)</url>', self.pipeline_model.xml_content)
                if url_match:
                    git_url = url_match.group(1)
                    logger.info(f"从XML中提取到 Git URL: {git_url}")
                    return git_url
                
                # 如果上面的方法失败，尝试使用XML解析
                try:
                    from xml.etree import ElementTree as ET
                    root = ET.fromstring(self.pipeline_model.xml_content)
                    
                    # 查找所有可能包含URL的元素
                    for url_elem in root.findall('.//url'):
                        potential_url = url_elem.text
                        if potential_url and ('git' in potential_url or 'http' in potential_url):
                            git_url = potential_url
                            logger.info(f"从XML元素中提取到 Git URL: {git_url}")
                            return git_url
                except Exception as e:
                    logger.warning(f"XML解析失败: {str(e)}")
        
            # 尝试从scm属性中提取
            if hasattr(self.pipeline_model, 'scm') and self.pipeline_model.scm:
                if isinstance(self.pipeline_model.scm, dict) and 'url' in self.pipeline_model.scm:
                    git_url = self.pipeline_model.scm['url']
                    logger.info(f"从scm属性中提取到 Git URL: {git_url}")
                    return git_url
            
            # 尝试从build_steps中提取
            if hasattr(self.pipeline_model, 'build_steps'):
                for step in self.pipeline_model.build_steps:
                    if isinstance(step, dict):
                        if step.get('type') == 'git' and 'url' in step:
                            git_url = step['url']
                            logger.info(f"从build_steps中提取到 Git URL: {git_url}")
                            return git_url
                        
                        # 尝试从命令中提取
                        if 'command' in step and 'git clone' in step['command']:
                            import re
                            url_match = re.search(r'git clone\s+(?:-b\s+\S+\s+)?(\S+)', step['command'])
                            if url_match:
                                git_url = url_match.group(1)
                                logger.info(f"从命令中提取到 Git URL: {git_url}")
                                return git_url
        except Exception as e:
            logger.error(f"提取Git URL时发生错误: {str(e)}")
    
        # 如果所有方法都失败，返回一个默认值或None
        return git_url
    
    def _add_git_step(self, step):
        """
        添加 Git 检出步骤
        
        Args:
            step: Git 检出步骤
        """
        # 从命令中提取 Git URL 和分支
        command = step.get('command', '')
        
        # 直接从步骤中获取 Git URL，而不是从命令中解析
        git_url = step.get('url', '')
        branch = step.get('branch', 'master')
        
        # 如果步骤中没有 URL，尝试从命令中提取
        if not git_url:
            # 尝试从命令中提取 Git URL 和分支
            import re
            git_url_match = re.search(r'git\s+clone\s+.*?(?:-b\s+([^\s]+)\s+)?([^\s]+)', command)
            
            if git_url_match:
                if git_url_match.group(1):
                    branch = git_url_match.group(1)
                if git_url_match.group(2):
                    git_url = git_url_match.group(2)
        
        # 记录日志
        logger.info(f"Git URL: {git_url}, 分支: {branch}")
        
        # 添加 Git 检出步骤
        self.build_yaml['steps']['PRE_BUILD'].append({
            'checkout': {
                'name': step.get('name', '代码下载'),
                'inputs': {
                    'scm': 'codehub',
                    'url': git_url,
                    'branch': branch,
                    'lfs': False,
                    'submodule': False
                }
            }
        })
        
        logger.info(f"添加 Git 检出步骤: {git_url}, 分支: {branch}")
    
    def _add_maven_step(self, step, upload_artifact_added=False):
        """
        添加 Maven 构建步骤
        
        Args:
            step: Maven 构建步骤
            upload_artifact_added: 是否已添加上传构件步骤
        """
        # 获取命令，如果没有则使用默认值
        command = step.get('command', 'clean package')
        
        # 打印步骤信息，帮助调试
        logger.info(f"Maven step: {step}")
        
        # 如果命令为空，使用默认值
        if not command or command.strip() == '':
            command = 'clean package'
            logger.info("Maven命令为空，使用默认值: clean package")
        
        logger.info(f"Maven 命令: {command}")
        
        # 添加 Maven 构建步骤
        self.build_yaml['steps']['BUILD'].append({
            'maven': {
                'name': step.get('name', 'Maven 构建'),
                'inputs': {
                    'command': command
                }
            }
        })
        
        # 只有在没有添加过上传构件步骤时才添加
        if not upload_artifact_added:
            # 添加上传构件步骤
            self.build_yaml['steps']['BUILD'].append({
                'upload_artifact': {
                    'inputs': {
                        'path': '**/target/*.?ar'
                    }
                }
            })
        
        logger.info(f"添加 Maven 构建步骤: {command}")
    
    def _add_shell_step(self, step):
        """
        添加 Shell 步骤
        
        Args:
            step: Shell 步骤
        """
        # 获取命令，如果没有则使用默认值
        command = step.get('command', 'echo "执行Shell命令"')
        
        # 添加 Shell 步骤
        self.build_yaml['steps']['BUILD'].append({
            'sh': {
                'inputs': {
                    'command': command
                }
            }
        })
        
        logger.info(f"添加 Shell 步骤: {command[:50]}...")
    
    def _add_ssh_step(self, step):
        """
        添加 SSH 步骤
        
        Args:
            step: SSH 步骤
        """
        # 获取命令，如果没有则使用默认值
        command = step.get('command', 'echo "执行SSH命令"')
        
        # 添加 SSH 步骤（在 CodeArts 中通过 Shell 实现）
        self.build_yaml['steps']['BUILD'].append({
            'sh': {
                'name': step.get('name', 'SSH 部署'),
                'inputs': {
                    'command': f'echo "执行SSH部署命令:"\n{command}'
                }
            }
        })
        
        logger.info(f"添加 SSH 部署步骤: {command[:50]}...")

    def _convert_build_steps(self):
        """
        转换构建步骤
        
        Returns:
            list: 转换后的构建步骤
        """
        build_steps = []
        
        # 从XML内容中提取Maven构建步骤
        if hasattr(self.pipeline_model, 'xml_content') and self.pipeline_model.xml_content:
            logger.info("尝试从XML内容中提取Maven构建步骤")
            
            # 使用正则表达式提取Maven targets
            import re
            maven_match = re.search(r'<targets>(.*?)</targets>', self.pipeline_model.xml_content)
            if maven_match:
                maven_command = maven_match.group(1).strip()
                logger.info(f"从XML中提取到Maven命令: {maven_command}")
                
                # 添加Maven构建步骤
                maven_step = {
                            "maven": {
                                "name": "Maven构建",
                                "image": "cloudbuild@maven3.5.3-jdk8-open",
                                "inputs": {
                                    "settings": {
                                        "public_repos": [
                                            "https://mirrors.huawei.com/maven"
                                        ]
                                    },
                                    "cache": True,
                                    "command": "mvn " + maven_command,
                                    "check": {
                                        "project_dir": "./",
                                        "settings": "~/.m2/settings.xml",
                                        "param": ""
                                    }
                                }
                            }
                        }
                build_steps.append(maven_step)
                
                # 添加构件上传步骤
                build_steps.append({
                    'upload_artifact': {
                        'inputs': {
                            'path': '**/target/*.?ar'
                        }
                    }
                })
                
                return build_steps
            
            # 如果上面的方法失败，尝试使用XML解析
            try:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(self.pipeline_model.xml_content)
                
                # 查找Maven构建步骤
                maven_elements = root.findall('.//hudson.tasks.Maven')
                if maven_elements:
                    for maven_elem in maven_elements:
                        targets_elem = maven_elem.find('./targets')
                        if targets_elem is not None and targets_elem.text:
                            maven_command = targets_elem.text.strip()
                            logger.info(f"从XML元素中提取到Maven命令: {maven_command}")
                            
                            # 添加Maven构建步骤
                            build_steps.append({
                                'maven': {
                                    'name': 'Maven Build',
                                    'inputs': {
                                        'command': maven_command
                                    }
                                }
                            })
                            
                            # 添加构件上传步骤
                            build_steps.append({
                                'upload_artifact': {
                                    'inputs': {
                                        'path': '**/target/*.?ar'
                                    }
                                }
                            })
                            
                            return build_steps
            except Exception as e:
                logger.warning(f"XML解析失败: {str(e)}")
    
        # 从build_steps中提取构建步骤
        if hasattr(self.pipeline_model, 'build_steps') and self.pipeline_model.build_steps:
            for step in self.pipeline_model.build_steps:
                if isinstance(step, dict):
                    step_type = step.get('type', '')
                    step_command = step.get('command', '')
                    
                    if step_type == 'maven':
                        maven_step = {
                            "maven": {
                                "name": "Maven构建",
                                "image": "cloudbuild@maven3.5.3-jdk8-open",
                                "inputs": {
                                    "settings": {
                                        "public_repos": [
                                            "https://mirrors.huawei.com/maven"
                                        ]
                                    },
                                    "cache": True,
                                    "command": "mvn " + step_command,
                                    "check": {
                                        "project_dir": "./",
                                        "settings": "~/.m2/settings.xml",
                                        "param": ""
                                    }
                                }
                            }
                        }
                        build_steps.append(maven_step)
                        
                        # 添加构件上传步骤
                        build_steps.append({
                            'upload_artifact': {
                                'inputs': {
                                    'path': '**/target/*.?ar'
                                }
                            }
                        })
                    elif step_type == 'shell' or step_type == 'sh':
                        # 检查是否是Maven命令
                        if 'mvn' in step_command or 'maven' in step_command:
                            build_steps.append({
                                'maven': {
                                    'name': 'Maven Build',
                                    'inputs': {
                                        'command': step_command
                                    }
                                }
                            })
                            
                            # 添加构件上传步骤
                            build_steps.append({
                                'upload_artifact': {
                                    'inputs': {
                                        'path': '**/target/*.?ar'
                                    }
                                }
                            })
                        else:
                            build_steps.append({
                                'shell': {
                                    'name': step.get('name', 'Shell'),
                                    'inputs': {
                                        'command': step_command
                                    }
                                }
                            })
        
        # 如果没有找到构建步骤，添加一个默认的Maven构建步骤
        if not build_steps:
            logger.warning("未找到构建步骤，添加默认Maven构建步骤")
            build_steps.append({
                'maven': {
                    'name': 'Maven Build',
                    'inputs': {
                        'command': 'clean package'
                    }
                }
            })
            
            # 添加构件上传步骤
            build_steps.append({
                'upload_artifact': {
                    'inputs': {
                        'path': '**/target/*.?ar'
                    }
                }
            })
    
        return build_steps