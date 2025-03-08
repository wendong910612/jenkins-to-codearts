#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Jenkinsfile解析器
负责解析Jenkinsfile并提取各个阶段和步骤
"""

import re
import os
from utils.logger import logger
from parsers.base_parser import BaseParser

class JenkinsfileParser(BaseParser):
    """Jenkinsfile解析器类"""
    
    def __init__(self, jenkinsfile_path):
        """
        初始化解析器
        
        Args:
            jenkinsfile_path: Jenkinsfile的路径
        """
        super().__init__()
        self.jenkinsfile_path = jenkinsfile_path
        self.content = None
        self._load_jenkinsfile()
    
    def _load_jenkinsfile(self):
        """加载Jenkinsfile内容"""
        if not os.path.exists(self.jenkinsfile_path):
            raise FileNotFoundError(f"Jenkinsfile不存在: {self.jenkinsfile_path}")
        
        with open(self.jenkinsfile_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
    
    def parse(self):
        """
        解析Jenkinsfile
        
        Returns:
            PipelineModel: 解析后的流水线模型
        """
        logger.info(f"开始解析Jenkinsfile: {self.jenkinsfile_path}")
        
        # 解析pipeline块
        pipeline_pattern = r'pipeline\s*\{([\s\S]*)\}'
        pipeline_match = re.search(pipeline_pattern, self.content)
        
        if not pipeline_match:
            logger.error("未找到pipeline块")
            return self.pipeline_model
        
        pipeline_content = pipeline_match.group(1)
        logger.info("成功匹配到pipeline块")
        
        # 解析agent
        logger.info("开始解析agent")
        self.pipeline_model.agent = self._parse_agent(pipeline_content)
        logger.info(f"解析agent完成: {self.pipeline_model.agent}")
        
        # 解析环境变量
        logger.info("开始解析环境变量")
        environment = self._parse_environment()
        for name, value in environment.items():
            self.pipeline_model.add_environment(name, value)
        logger.info(f"解析环境变量完成，共 {len(environment)} 个")
        
        # 解析参数
        logger.info("开始解析参数")
        parameters = self._parse_parameters(pipeline_content)
        for param in parameters:
            self.pipeline_model.add_parameter(
                param.get("name", ""),
                param.get("default", ""),
                param.get("description", "")
            )
        logger.info(f"解析参数完成，共 {len(parameters)} 个")
        
        # 解析stages
        logger.info("开始解析stages")
        stages = self._parse_stages()
        for stage in stages:
            self.pipeline_model.add_stage(stage)
        logger.info(f"解析stages完成，共 {len(stages)} 个")
        
        # 提取构建步骤
        logger.info("开始提取构建步骤")
        build_steps = self.extract_build_steps()
        for step in build_steps:
            logger.info(f"添加构建步骤: {step}")
            self.pipeline_model.add_build_step(
                name=step['name'],
                type=step['type'],
                command=step.get('command', ''),
                stage=step.get('stage', '')
            )
        logger.info(f"提取构建步骤完成，共 {len(build_steps)} 个")
        
        logger.info("Jenkinsfile解析完成")
        return self.pipeline_model

    # 保留原有的解析方法，但修改返回格式以符合统一模型
    def _parse_parameters(self, pipeline_content):
        """
        解析Jenkinsfile中的参数
        
        Args:
            pipeline_content: pipeline内容
        
        Returns:
            list: 参数列表
        """
        parameters = []
        # 匹配parameters块
        params_pattern = r'parameters\s*\{([\s\S]*?)\}'
        params_match = re.search(params_pattern, pipeline_content)
        if not params_match:
            return parameters
        params_content = params_match.group(1)
        
        # 解析各种类型的参数
        # 字符串参数
        string_pattern = r'string\s*\(\s*name\s*:\s*[\'"]([^\'"]+)[\'"](?:.*?defaultValue\s*:\s*[\'"]([^\'"]*)[\'"])?(?:.*?description\s*:\s*[\'"]([^\'"]*)[\'"])?\s*\)'
        for param_match in re.finditer(string_pattern, params_content):
            name = param_match.group(1)
            default_value = param_match.group(2) or ""
            description = param_match.group(3) or ""
            
            parameters.append({
                'name': name,
                'type': 'string',
                'default': default_value,
                'description': description
            })
        
        # 布尔参数
        bool_pattern = r'booleanParam\s*\(\s*name\s*:\s*[\'"]([^\'"]+)[\'"](?:.*?defaultValue\s*:\s*(true|false))?(?:.*?description\s*:\s*[\'"]([^\'"]*)[\'"])?\s*\)'
        for param_match in re.finditer(bool_pattern, params_content):
            name = param_match.group(1)
            default_value = param_match.group(2) == 'true' if param_match.group(2) else False
            description = param_match.group(3) or ""
            
            parameters.append({
                'name': name,
                'type': 'boolean',
                'default': default_value,
                'description': description
            })
        
        # 选择参数
        choice_pattern = r'choice\s*\(\s*name\s*:\s*[\'"]([^\'"]+)[\'"](?:.*?choices\s*:\s*\[(.*?)\])?(?:.*?description\s*:\s*[\'"]([^\'"]*)[\'"])?\s*\)'
        for param_match in re.finditer(choice_pattern, params_content):
            name = param_match.group(1)
            choices_str = param_match.group(2) or ""
            description = param_match.group(3) or ""
            
            # 解析选项列表
            choices = []
            if choices_str:
                choices = [choice.strip().strip('\'"') for choice in choices_str.split(',')]
            
            parameters.append({
                'name': name,
                'type': 'choice',
                'choices': choices,
                'default': choices[0] if choices else "",
                'description': description
            })
        
        return parameters
    
        # 修改正则表达式，使用贪婪匹配来获取整个stages块
        # 注意：这里使用了贪婪匹配 [\s\S]* 而不是非贪婪匹配 [\s\S]*?
        stages_pattern = r'stages\s*\{([\s\S]*)\}'
        stages_match = re.search(stages_pattern, self.content, re.DOTALL)
        
        if not stages_match:
            # 输出文件内容以便调试
            logger.debug(f"Jenkinsfile内容: {self.content}")
            raise ValueError("未找到stages定义")
        
        stages_content = stages_match.group(1)
        logger.debug(f"找到stages内容: {stages_content}")
        
        # 使用新的方法来匹配stage块
        stages = []
        # 使用更精确的正则表达式来匹配每个stage块
        stage_pattern = r'stage\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)\s*\{([\s\S]*?)(?=\s*stage\s*\(|\s*\}\s*$)'
        
        for stage_match in re.finditer(stage_pattern, stages_content):
            name = stage_match.group(1)
            stage_content = stage_match.group(2)
            logger.debug(f"找到阶段 '{name}' 的内容")
            
            # 解析steps部分
            steps = []
            steps_match = re.search(r'steps\s*\{([\s\S]*?)\}', stage_content)
            if steps_match:
                steps_content = steps_match.group(1)
                steps = self._parse_steps(steps_content)
            
            # 解析when条件
            when_condition = None
            when_match = re.search(r'when\s*\{([\s\S]*?)\}', stage_content)
            if when_match:
                when_condition = when_match.group(1).strip()
            
            # 解析环境变量
            environment = {}
            env_match = re.search(r'environment\s*\{([\s\S]*?)\}', stage_content)
            if env_match:
                env_content = env_match.group(1)
                for env_var in re.finditer(r'(\w+)\s*=\s*[\'"]?([^\'"]+)[\'"]?', env_content):
                    environment[env_var.group(1)] = env_var.group(2)
            
            stages.append({
                'name': name,
                'steps': steps,
                'when': when_condition,
                'environment': environment
            })
        
        # 如果没有找到任何阶段，尝试使用备用方法
        if not stages:
            logger.warning("使用主要正则表达式未找到任何阶段，尝试使用备用方法")
            # 备用方法：先找出所有stage名称，然后手动分割内容
            stage_names = re.findall(r'stage\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', stages_content)
            
            # 手动分割stages内容
            stage_sections = []
            start_indices = [m.start() for m in re.finditer(r'stage\s*\(', stages_content)]
            
            for i in range(len(start_indices)):
                start = start_indices[i]
                end = start_indices[i+1] if i+1 < len(start_indices) else len(stages_content)
                stage_sections.append(stages_content[start:end])
            
            for i, section in enumerate(stage_sections):
                if i < len(stage_names):
                    name = stage_names[i]
                    logger.debug(f"备用方法找到阶段: {name}")
                    
                    # 解析steps部分
                    steps = []
                    steps_match = re.search(r'steps\s*\{([\s\S]*?)\}', section)
                    if steps_match:
                        steps_content = steps_match.group(1)
                        steps = self._parse_steps(steps_content)
                    
                    # 解析when条件
                    when_condition = None
                    when_match = re.search(r'when\s*\{([\s\S]*?)\}', section)
                    if when_match:
                        when_condition = when_match.group(1).strip()
                    
                    # 解析环境变量
                    environment = {}
                    env_match = re.search(r'environment\s*\{([\s\S]*?)\}', section)
                    if env_match:
                        env_content = env_match.group(1)
                        for env_var in re.finditer(r'(\w+)\s*=\s*[\'"]?([^\'"]+)[\'"]?', env_content):
                            environment[env_var.group(1)] = env_var.group(2)
                    
                    stages.append({
                        'name': name,
                        'steps': steps,
                        'when': when_condition,
                        'environment': environment
                    })
        
        logger.info(f"解析完成，共找到 {len(stages)} 个阶段")
        return stages
    
    # 修改 _parse_stages 方法，使用字典而不是自定义类
    def _parse_stages(self):
        """
        解析stages块
        
        Returns:
            list: 阶段列表
        """
        logger.info("进入_parse_stages方法")
        stages = []
        
        # 查找stages块 - 修改正则表达式，使用更精确的匹配方式
        # 使用平衡组匹配来处理嵌套的大括号
        # 先尝试使用贪婪匹配获取整个stages块
        stages_pattern = r'stages\s*\{([\s\S]*)\}'
        stages_match = re.search(stages_pattern, self.content)
        
        if not stages_match:
            logger.warning("未找到stages块，尝试使用备用正则表达式")
            # 备用正则表达式，尝试匹配从stages开始到pipeline结束的内容
            stages_pattern = r'stages\s*\{([\s\S]*?)(?=\}\s*\})'
            stages_match = re.search(stages_pattern, self.content)
            
            if not stages_match:
                logger.error("使用备用正则表达式仍未找到stages块")
                # 输出文件内容的一部分用于调试
                logger.debug(f"Jenkinsfile内容片段: {self.content[:500]}...")
                return stages
        
        stages_content = stages_match.group(1)
        logger.info(f"找到stages块，长度: {len(stages_content)}")
        logger.debug(f"stages块内容前100个字符: {stages_content[:100]}...")
        
        # 使用非递归方式查找所有stage块
        # 修改stage匹配模式，使用更精确的正则表达式
        stage_pattern = r'stage\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)\s*\{([\s\S]*?)(?=\s*stage\s*\(|\s*\}\s*$)'
        stage_matches = list(re.finditer(stage_pattern, stages_content))
        
        if not stage_matches:
            logger.warning("未找到任何stage块，尝试使用备用stage匹配模式")
            # 备用stage匹配模式
            stage_pattern = r'stage\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
            stage_names = re.findall(stage_pattern, stages_content)
            logger.info(f"使用备用模式找到 {len(stage_names)} 个stage名称")
            
            if stage_names:
                # 手动分割stages内容
                stage_sections = []
                start_indices = [m.start() for m in re.finditer(r'stage\s*\(', stages_content)]
                
                for i in range(len(start_indices)):
                    start = start_indices[i]
                    end = start_indices[i+1] if i+1 < len(start_indices) else len(stages_content)
                    stage_sections.append(stages_content[start:end])
                
                for i, section in enumerate(stage_sections):
                    if i < len(stage_names):
                        stage_name = stage_names[i]
                        logger.info(f"处理阶段: {stage_name}")
                        
                        # 创建阶段字典而不是对象
                        stage = {
                            'name': stage_name,
                            'steps': []
                        }
                        
                        # 尝试提取steps部分
                        steps_match = re.search(r'steps\s*\{([\s\S]*?)\}', section)
                        if steps_match:
                            steps_content = steps_match.group(1)
                            steps = self._parse_steps(steps_content)
                            stage['steps'] = steps
                            logger.info(f"阶段 {stage_name} 包含 {len(steps)} 个步骤")
                        else:
                            # 如果没有明确的steps块，尝试直接解析整个section
                            steps = self._parse_steps(section)
                            stage['steps'] = steps
                            logger.info(f"阶段 {stage_name} 直接解析得到 {len(steps)} 个步骤")
                        
                        stages.append(stage)
        else:
            logger.info(f"找到 {len(stage_matches)} 个stage块")
            
            for match in stage_matches:
                stage_name = match.group(1)
                stage_content = match.group(2)
                logger.info(f"解析阶段: {stage_name}")
                
                # 创建阶段字典而不是对象
                stage = {
                    'name': stage_name,
                    'steps': []
                }
                
                # 解析阶段中的步骤
                logger.info(f"开始解析阶段 {stage_name} 的步骤")
                steps = self._parse_steps(stage_content)
                stage['steps'] = steps
                logger.info(f"阶段 {stage_name} 包含 {len(steps)} 个步骤")
                
                stages.append(stage)
        
        logger.info(f"_parse_stages方法完成，共解析 {len(stages)} 个阶段")
        return stages

    # 修改 _parse_steps 方法，使用字典而不是自定义类
    def _parse_steps(self, stage_content):
        """
        解析阶段中的步骤
        
        Args:
            stage_content: 阶段内容
            
        Returns:
            list: 步骤列表
        """
        logger.info("进入_parse_steps方法")
        steps = []
        
        # 查找steps块
        steps_pattern = r'steps\s*\{([\s\S]*?)\}'
        steps_match = re.search(steps_pattern, stage_content)
        
        if not steps_match:
            logger.warning("未找到steps块")
            return steps
        
        steps_content = steps_match.group(1)
        logger.info(f"找到steps块，长度: {len(steps_content)}")
        
        # 查找sh步骤 - 修改正则表达式以匹配多行字符串
        # 匹配 sh '...'、sh "..."、sh '''...'''、sh """...""" 四种格式
        sh_pattern = r'sh\s*(?:\'\'\'([\s\S]*?)\'\'\'|"""([\s\S]*?)"""|\'([^\']*)\'|"([^"]*)")'
        sh_matches = list(re.finditer(sh_pattern, steps_content))
        logger.info(f"找到 {len(sh_matches)} 个sh步骤")
        
        for match in sh_matches:
            # 获取匹配到的命令内容（可能在四个捕获组中的任意一个）
            command = next((group for group in match.groups() if group is not None), "")
            step = {
                'name': "Shell Command",
                'type': "sh",
                'command': command.strip()
            }
            steps.append(step)
        
        # 查找echo步骤 - 同样修改以匹配多行字符串
        echo_pattern = r'echo\s*(?:\'\'\'([\s\S]*?)\'\'\'|"""([\s\S]*?)"""|\'([^\']*)\'|"([^"]*)")'
        echo_matches = list(re.finditer(echo_pattern, steps_content))
        logger.info(f"找到 {len(echo_matches)} 个echo步骤")
        
        for match in echo_matches:
            message = next((group for group in match.groups() if group is not None), "")
            step = {
                'name': "Echo Message",
                'type': "echo",
                'command': message.strip()
            }
            steps.append(step)
        
        # 查找checkout步骤
        checkout_pattern = r'checkout\s+scm'
        checkout_matches = list(re.finditer(checkout_pattern, steps_content))
        logger.info(f"找到 {len(checkout_matches)} 个checkout步骤")
        
        for _ in checkout_matches:
            step = {
                'name': "Checkout",
                'type': "git",
                'command': "checkout scm"
            }
            steps.append(step)
        
        # 查找sshagent步骤
        sshagent_pattern = r'sshagent\s*\(\s*\[\'([^\']+)\'\]\s*\)\s*\{([\s\S]*?)\}'
        sshagent_matches = list(re.finditer(sshagent_pattern, steps_content))
        logger.info(f"找到 {len(sshagent_matches)} 个sshagent步骤")
        
        for match in sshagent_matches:
            credentials = match.group(1)
            ssh_content = match.group(2)
            step = {
                'name': "SSH Agent",
                'type': "ssh",
                'credentials': credentials,
                'command': ssh_content.strip()
            }
            steps.append(step)
        
        # 查找script步骤
        script_pattern = r'script\s*\{([\s\S]*?)\}'
        script_matches = list(re.finditer(script_pattern, steps_content))
        logger.info(f"找到 {len(script_matches)} 个script步骤")
        
        for match in script_matches:
            script_content = match.group(1)
            step = {
                'name': "Script",
                'type': "script",
                'content': script_content
            }
            steps.append(step)
        
        logger.info(f"_parse_steps方法完成，共解析 {len(steps)} 个步骤")
        return steps
    def _extract_code_check_params(self, content):
        """提取代码检查参数"""
        params = {
            'tool': 'sonarqube',  # 默认使用sonarqube
            'language': 'java',   # 默认语言为java
        }
        
        # 尝试提取更多参数
        if re.search(r'python|py', content, re.IGNORECASE):
            params['language'] = 'python'
        elif re.search(r'javascript|js|node', content, re.IGNORECASE):
            params['language'] = 'javascript'
        
        return params
    
    def _extract_build_params(self, content):
        """提取构建参数"""
        params = {
            'tool': 'maven',  # 默认使用maven
            'command': 'package',  # 默认命令
        }
        
        # 尝试提取更多参数
        if re.search(r'gradle', content, re.IGNORECASE):
            params['tool'] = 'gradle'
            params['command'] = 'build'
        elif re.search(r'npm|yarn', content, re.IGNORECASE):
            params['tool'] = 'npm'
            params['command'] = 'build'
        
        return params
    
    def _extract_deploy_params(self, content):
        """提取部署参数"""
        params = {
            'type': 'cce',  # 默认使用CCE
            'cluster': 'default',  # 默认集群
            'namespace': 'default',  # 默认命名空间
        }
        
        # 尝试提取更多参数
        namespace_match = re.search(r'-n\s+(\w+)', content)
        if namespace_match:
            params['namespace'] = namespace_match.group(1)
        
        return params
    
    def _parse_environment(self):
        """
        解析Jenkinsfile中的环境变量
        
        Returns:
            dict: 环境变量字典
        """
        environment = {}
        
        # 匹配environment块
        env_pattern = r'environment\s*\{([\s\S]*?)\}'
        env_match = re.search(env_pattern, self.content)
        
        if not env_match:
            return environment
        
        env_content = env_match.group(1)
        
        # 匹配环境变量定义
        env_var_pattern = r'([A-Za-z0-9_]+)\s*=\s*(?:credentials\([\'"]([^\'"]+)[\'"]\)|[\'"]([^\'"]+)[\'"])'
        for env_match in re.finditer(env_var_pattern, env_content):
            name = env_match.group(1)
            credential = env_match.group(2)
            value = env_match.group(3) or ""
            
            if credential:
                environment[name] = f"${{credentials.{credential}}}"
            else:
                environment[name] = value
        
        return environment
    
    def extract_build_steps(self):
        """
        提取构建步骤
        
        Returns:
            list: 构建步骤列表
        """
        logger.info("进入extract_build_steps方法")
        build_steps = []
        
        # 查找构建相关的阶段
        build_keywords = ["构建"]
        
        # 如果pipeline_model中已有stages，直接使用
        if hasattr(self, 'pipeline_model') and hasattr(self.pipeline_model, 'stages'):
            stages = self.pipeline_model.stages
            logger.info(f"从pipeline_model获取到 {len(stages)} 个阶段")
        else:
            # 否则重新解析stages
            logger.info("pipeline_model中没有stages，重新解析")
            stages = self._parse_stages()
        
        # 遍历所有阶段，查找构建步骤
        for stage in stages:
            # 使用字典访问方式获取阶段名称
            stage_name = stage['name'].lower()
            logger.info(f"检查阶段 {stage['name']} 是否包含构建步骤")
            
            # 检查阶段名称是否包含构建关键字
            if any(keyword in stage_name for keyword in build_keywords):
                logger.info(f"阶段 {stage['name']} 名称包含构建关键字")
                
                # 遍历阶段中的所有步骤
                for step in stage['steps']:
                    # 使用字典访问方式获取步骤类型和命令
                    if step.get('type') == "sh":
                        # 确定构建类型
                        build_type = self._determine_build_type(step.get('command', ''), build_keywords)
                        logger.info(f"从步骤中确定构建类型: {build_type}")
                        
                        # 根据构建类型添加构建步骤
                        if build_type == "maven":
                            build_steps.append({
                                    "name": "Maven构建",
                                    "type": build_type,
                                    "stage": stage_name,
                                    "command": step.get('command', ''),
                                
                            })
                        elif build_type == "gradle":
                            build_steps.append({
                                "gradle": {
                                    "name": "Gradle构建",
                                    "inputs": {
                                        "command": "clean build -x test"
                                    }
                                }
                            })
                        elif build_type == "npm":
                            build_steps.append({
                                "npm": {
                                    "name": "NPM构建",
                                    "inputs": {
                                        "command": "install && npm run build"
                                    }
                                }
                            })
                        elif build_type == "docker":
                            build_steps.append({
                                "sh": {
                                    "name": "Docker构建",
                                    "inputs": {
                                        "command": "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ."
                                    }
                                }
                            })
                        else:
                            build_steps.append({
                                "sh": {
                                    "name": "Shell构建",
                                    "inputs": {
                                        "command": step.get('command', '')
                                    }
                                }
                            })
        
        # 如果没有找到任何构建步骤，添加默认的Maven构建步骤
        if not build_steps:
            logger.info("未找到任何构建步骤，添加默认的Maven构建步骤")
            build_steps.append({
                "maven": {
                    "name": "Maven构建",
                    "inputs": {
                        "command": "clean package -Dmaven.test.skip=true"
                    }
                }
            })
        
        logger.info(f"extract_build_steps方法完成，共提取 {len(build_steps)} 个构建步骤")
        return build_steps

    def _determine_build_type(self, content, build_keywords):
        """
        确定构建类型
        
        Args:
            content: 步骤内容
            build_keywords: 构建关键字列表
            
        Returns:
            str: 构建类型
        """
        content_lower = content.lower()
        
        if "mvn" in content_lower or "maven" in content_lower:
            return "maven"
        elif "gradle" in content_lower:
            return "gradle"
        elif "npm" in content_lower or "yarn" in content_lower:
            return "npm"
        elif "docker build" in content_lower or "kaniko" in content_lower:
            return "docker"
        
        # 默认返回shell
        return "shell"
    
    def _parse_agent(self, pipeline_content):
        """
        解析agent部分
        
        Args:
            pipeline_content: pipeline内容
        
        Returns:
            dict: agent信息
        """
        agent = {
            'type': 'any'  # 默认agent类型
        }
        
        # 匹配agent块
        agent_pattern = r'agent\s*\{([\s\S]*?)\}'
        agent_match = re.search(agent_pattern, pipeline_content)
        
        if not agent_match:
            # 检查简单agent声明
            simple_agent = re.search(r'agent\s+(\w+)', pipeline_content)
            if simple_agent:
                agent['type'] = simple_agent.group(1)
            return agent
        
        agent_content = agent_match.group(1)
        
        # 检查agent类型
        if 'kubernetes' in agent_content:
            agent['type'] = 'kubernetes'
            
            # 尝试提取kubernetes配置
            yaml_pattern = r'yaml\s*[\'"]([^\'"]+)[\'"]'
            yaml_match = re.search(yaml_pattern, agent_content)
            if yaml_match:
                agent['yaml'] = yaml_match.group(1)
            
            # 尝试提取label
            label_pattern = r'label\s*[\'"]([^\'"]+)[\'"]'
            label_match = re.search(label_pattern, agent_content)
            if label_match:
                agent['label'] = label_match.group(1)
        elif 'docker' in agent_content:
            agent['type'] = 'docker'
            
            # 尝试提取镜像
            image_pattern = r'image\s*[\'"]([^\'"]+)[\'"]'
            image_match = re.search(image_pattern, agent_content)
            if image_match:
                agent['image'] = image_match.group(1)
        elif 'label' in agent_content:
            agent['type'] = 'node'
            
            # 提取label
            label_pattern = r'label\s*[\'"]([^\'"]+)[\'"]'
            label_match = re.search(label_pattern, agent_content)
            if label_match:
                agent['label'] = label_match.group(1)
        
        return agent
