#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Jenkins API 解析器
负责解析从 Jenkins API 获取的 Job 信息
"""
import os
import re
import yaml
import re
from utils.logger import logger
from parsers.base_parser import BaseParser

class JenkinsApiParser(BaseParser):
    """Jenkins API 解析器类"""
    
    def __init__(self, pipeline_structure):
        """
        初始化解析器
        
        Args:
            pipeline_structure: 从 Jenkins API 获取的流水线结构
        """
        super().__init__()
        self.pipeline_structure = pipeline_structure
        self.stages = pipeline_structure.get('stages', [])
        self.parameters = pipeline_structure.get('parameters', [])
        self.script = pipeline_structure.get('script', '')
    
    ## 使用中的函数
    def parse(self):
        """
        解析流水线结构
        
        Returns:
            PipelineModel: 解析后的流水线模型
        """
        logger.info("开始解析 Jenkins API 获取的流水线结构")
        logger.info(f"初始化 JenkinsApiParser，流水线结构: {self.pipeline_structure.get('name', '未知')}")
        
        # 检查项目类型
        project_type = self.pipeline_structure.get('_class', '')
        logger.info(f"项目类型: {project_type}")
        
        # 设置流水线名称
        self.pipeline_model.name = self.pipeline_structure.get('name', '')
        
        # 提取参数 - 修改这里，传递 pipeline_structure 参数
        self._extract_parameters(self.pipeline_structure)
        
        # 根据项目类型处理
        if 'FreeStyleProject' in project_type or not project_type:  # 修改这里，当项目类型为空时也当作 Freestyle 项目处理
            # Freestyle 项目
            logger.info("检测到 Freestyle 项目，尝试提取构建步骤")
            build_steps = self._extract_freestyle_steps(self.pipeline_structure)
            
            # 添加构建步骤
            for step in build_steps:
                self.pipeline_model.add_build_step(
                    name=step.get('name', ''),
                    type=step.get('type', ''),
                    command=step.get('command', ''),
                    stage=step.get('stage', '')
                )
            if hasattr(self.pipeline_structure, 'xml_content'):
                self.pipeline_model.xml_content = self.pipeline_structure.xml_content
            self.pipeline_model.set_scm(self.pipeline_structure.get('git_url',{}), branch=self.pipeline_structure.get('main'))
            # 创建默认阶段
            stages = []
            for stage in self.pipeline_structure.get('stages', []):
                stage_name = stage.get('name', {})
                if stage_name:
                    stages.append({
                        'name': stage_name,
                        'steps': []
                    })
            
            # 添加阶段
            for stage in stages:
                self.pipeline_model.add_stage(stage)
        else:
            # 流水线项目
            logger.info(f"流水线阶段数量: {len(self.stages)}")
            
            # 提取阶段
            stages = self._extract_stages()
            
            # 添加阶段
            for stage in stages:
                self.pipeline_model.add_stage(stage)
            
            logger.info(f"转换后的阶段数量: {len(stages)}")
        
        return self.pipeline_model
    
    def _extract_environment(self):
        """
        从脚本中提取环境变量
        
        Returns:
            dict: 环境变量
        """
        environment = {}
        
        # 如果有脚本，尝试从脚本中提取环境变量
        if self.script:
            env_pattern = r'environment\s*\{([\s\S]*?)\}'
            env_match = re.search(env_pattern, self.script)
            
            if env_match:
                env_content = env_match.group(1)
                # 提取环境变量定义
                var_pattern = r'([A-Za-z0-9_]+)\s*=\s*[\'"]([^\'"]*)[\'"]'
                for var_match in re.finditer(var_pattern, env_content):
                    name = var_match.group(1)
                    value = var_match.group(2)
                    environment[name] = value
        
        # 添加默认环境变量
        default_env = {
            'projectVersion': '1.0.0',
            'deployEnv': 'dev',
            'appName': '',
            'gitBranch': 'main',
            'imageTag': '',
            'baseBranch': 'main',
            'kanikoNamespace': 'kaniko',
            'buildHistoryId': '',
            'gitCredentialId': 'gitlab-credential',
            'newbieGitCredentialId': 'newbie-git-credential',
            'kanikoKubeconfigPath': '/root/.kube/config',
            'sonarEnable': 'true',
            'isDeploy': 'true',
            'unitTest': 'true',
            'incUnitTest': 'false',
            'failureIgnore': 'false',
            'swaggerAcsEnable': 'false',
            'rolloutStatusEnable': 'true',
            'deployMethod': 'SourceCode'
        }
        
        # 合并默认环境变量和提取的环境变量
        for key, value in default_env.items():
            if key not in environment:
                environment[key] = value
        
        return environment
    
    def _convert_stages(self):
        """
        转换阶段信息
        
        Returns:
            list: 转换后的阶段信息
        """
        converted_stages = []
        
        for stage in self.stages:
            stage_name = stage.get('name', '')
            stage_steps = stage.get('steps', [])
            
            # 转换步骤信息
            steps = self._convert_steps(stage_steps)
            
            # 构建阶段信息
            stage_info = {
                'name': stage_name,
                'steps': steps,
                'environment': {},  # 默认为空
                'when': None,  # 默认为空
                'parallel': None  # 默认为空
            }
            
            converted_stages.append(stage_info)
        
        return converted_stages
    
    def _convert_steps(self, steps):
        """
        转换步骤信息
        
        Args:
            steps: 步骤信息列表
            
        Returns:
            list: 转换后的步骤信息
        """
        converted_steps = []
        
        for step in steps:
            step_name = step.get('name', '')
            step_log = step.get('log', '')
            
            # 根据步骤日志判断步骤类型
            step_type = self._determine_step_type(step_log)
            
            # 提取步骤命令
            command = self._extract_command(step_log)
            
            # 构建步骤信息
            step_info = {
                'name': step_name,
                'type': step_type,
                'command': command
            }
            
            converted_steps.append(step_info)
        
        return converted_steps
    
    def _determine_step_type(self, log):
        """
        根据日志判断步骤类型
        
        Args:
            log: 步骤日志
            
        Returns:
            str: 步骤类型
        """
        log_lower = log.lower()
        
        if 'sh ' in log_lower or 'shell' in log_lower:
            return 'sh'
        elif 'echo' in log_lower:
            return 'echo'
        elif 'git ' in log_lower or 'checkout' in log_lower:
            return 'checkout'
        elif 'mvn ' in log_lower or 'maven' in log_lower:
            return 'maven'
        elif 'gradle' in log_lower:
            return 'gradle'
        elif 'npm ' in log_lower or 'yarn ' in log_lower:
            return 'npm'
        elif 'docker ' in log_lower:
            return 'docker'
        elif 'sonar' in log_lower:
            return 'sonar'
        elif 'deploy' in log_lower or 'kubectl' in log_lower:
            return 'deploy'
        else:
            return 'sh'  # 默认为 shell 命令
    
    def _extract_command(self, action, default_type=None):
        """
        从构建步骤中提取命令
        
        Args:
            action: 构建步骤数据
            default_type: 默认步骤类型
            
        Returns:
            str: 命令
        """
        try:
            # 检查 action 是否为字典
            if not isinstance(action, dict):
                logger.warning(f"action 不是字典类型: {type(action)}")
                return str(action)
            
            # 检查常见的命令字段
            if 'command' in action:
                return action['command']
            elif 'commands' in action:
                return '\n'.join(action['commands'])
            elif 'script' in action:
                return action['script']
            elif 'targets' in action:
                return action['targets']
            elif 'properties' in action and isinstance(action['properties'], list):
                # Maven 特有的属性
                props = []
                for prop in action['properties']:
                    if isinstance(prop, dict) and 'command' in prop:
                        return prop['command']
                    elif isinstance(prop, dict):
                        for k, v in prop.items():
                            props.append(f"-D{k}={v}")
                return "mvn " + " ".join(props)
            else:
                # 尝试查找其他可能包含命令的字段
                for key, value in action.items():
                    if isinstance(value, str) and key not in ['_class'] and ('command' in key.lower() or 'script' in key.lower() or 'target' in key.lower()):
                        return value
                
                # 如果找不到明确的命令字段，返回一个默认值
                return "无法提取命令"
        except Exception as e:
            logger.error(f"提取命令时出错: {str(e)}")
            return "无法提取命令"
    
    def extract_build_steps(self):
        """
        提取构建步骤
        
        Returns:
            list: 构建步骤列表
        """
        # 加载构建映射配置
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                  "config", "build_mapping.yaml")
        
        if not os.path.exists(config_path):
            logger.error(f"构建配置文件不存在: {config_path}")
            raise FileNotFoundError(f"构建配置文件不存在: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                build_config = yaml.safe_load(f)
                logger.info(f"从 {config_path} 加载构建配置")
        except Exception as e:
            logger.error(f"加载构建配置失败: {str(e)}")
            raise
        
        build_steps = []
        
        # 遍历所有阶段，查找构建步骤
        for stage in self.stages:
            stage_name = stage.get('name', '')
            stage_steps = stage.get('steps', [])
            
            # 检查阶段名称是否匹配构建阶段
            is_build_stage = False
            step_type = None
            
            # 检查是否是 Maven 阶段
            if stage_name in build_config.get("maven_stages", []):
                is_build_stage = True
                step_type = "maven"
            # 检查是否是 Docker 阶段
            elif stage_name in build_config.get("docker_stages", []):
                is_build_stage = True
                step_type = "docker"
            # 检查是否是需要转换为 sh 的阶段
            elif stage_name in build_config.get("sh_stages", []):
                is_build_stage = True
                step_type = "sh"
            # 检查是否是需要忽略的阶段
            elif stage_name in build_config.get("ignore_stages", []):
                continue
            
            if is_build_stage:
                # 添加构建步骤
                for step in stage_steps:
                    step_name = step.get('name', '')
                    step_log = step.get('log', '')
                    
                    # 如果没有指定步骤类型，根据日志判断
                    if not step_type:
                        step_type = self._determine_step_type(step_log, build_config.get("keywords", {}))
                    
                    # 提取命令
                    command = self._extract_command(step_log, step_type)
                    
                    build_steps.append({
                        'name': step_name or stage_name,
                        'type': step_type,
                        'command': command,
                        'stage': stage_name
                    })
        
        # 如果没有找到任何构建步骤，添加一个默认的 Maven 构建步骤
        if not build_steps:
            logger.warning("未找到任何构建步骤，添加默认的 Maven 构建步骤")
            build_steps.append({
                'name': 'Maven Build',
                'type': 'maven',
                'command': 'clean package -Dmaven.test.skip=true',
                'stage': 'Build'
            })
        
        logger.info(f"提取到 {len(build_steps)} 个构建步骤")
        return build_steps
    
    def _extract_freestyle_steps(self, job_data):
        """
        从 Freestyle 项目中提取构建步骤
        
        Args:
            job_data: 作业数据
            
        Returns:
            list: 构建步骤列表
        """
        steps = []
        # 保存原始XML内容
        xml_content = job_data['xml_content']
        
        if not xml_content:
            logger.warning("未找到有效的XML内容")
            return steps
        
        self.pipeline_model.xml_content = xml_content
        
        # 使用ElementTree解析XML并转换为JSON
        try:
            from xml.etree import ElementTree as ET
            import json
            
            def xml_to_json(element):
                result = {}
                
                # 处理属性
                if element.attrib:
                    result['@attributes'] = element.attrib
                
                # 处理子元素
                children = list(element)
                if children:
                    for child in children:
                        child_data = xml_to_json(child)
                        if child.tag in result:
                            if not isinstance(result[child.tag], list):
                                result[child.tag] = [result[child.tag]]
                            result[child.tag].append(child_data)
                        else:
                            result[child.tag] = child_data
                else:
                    text = element.text
                    if text is not None:
                        text = text.strip()
                        if text:
                            result = text
                
                return result
            
            # 解析XML并转换为JSON
            root = ET.fromstring(xml_content)
            json_data = {root.tag: xml_to_json(root)}
            
            # 从JSON中提取Git信息
            if 'project' in json_data:
                scm = json_data['project'].get('scm', {})
                if isinstance(scm, dict) and scm.get('@attributes', {}).get('class') == 'hudson.plugins.git.GitSCM':
                    user_remote_configs = scm.get('userRemoteConfigs', {})
                    if isinstance(user_remote_configs, dict):
                        git_config = user_remote_configs.get('hudson.plugins.git.UserRemoteConfig', {})
                        git_url = git_config.get('url', '')
                        if git_url:
                            logger.info(f"从JSON中提取到Git URL: {git_url}")
                            
                            # 提取分支信息
                            branches = scm.get('branches', {})
                            branch_spec = branches.get('hudson.plugins.git.BranchSpec', {})
                            git_branch = branch_spec.get('name', 'master')
                            if git_branch:
                                git_branch = git_branch.replace('*/', '').replace('origin/', '')
                            
                            # 保存到pipeline_model的scm属性中
                            self.pipeline_model.scm = {
                                'url': git_url,
                                'branch': git_branch
                            }
                            
                            # 添加Git检出步骤
                            steps.append({
                                'name': 'Git Checkout',
                                'type': 'git',
                                'url': git_url,
                                'branch': git_branch,
                                'command': f"git clone -b {git_branch} {git_url}",
                                'stage': 'Checkout'
                            })
            
            # 从JSON中提取Maven构建步骤
            if 'project' in json_data:
                builders = json_data['project'].get('builders', {})
                if isinstance(builders, dict):
                    maven_builders = builders.get('hudson.tasks.Maven', [])
                    if not isinstance(maven_builders, list):
                        maven_builders = [maven_builders]
                    
                    for maven_builder in maven_builders:
                        if isinstance(maven_builder, dict):
                            maven_command = maven_builder.get('targets', '')
                            maven_properties = maven_builder.get('properties', '')
                            
                            if maven_command:
                                # 处理Maven属性
                                if maven_properties:
                                    maven_props = [f"-D{prop.strip()}" for prop in maven_properties.split('\n') if prop.strip()]
                                    if maven_props:
                                        maven_command = f"{maven_command} {' '.join(maven_props)}"
                                
                                steps.append({
                                    'name': 'Maven Build',
                                    'type': 'maven',
                                    'command': maven_command,
                                    'stage': 'Build'
                                })
            
            # 从JSON中提取Shell构建步骤
            if 'project' in json_data:
                builders = json_data['project'].get('builders', {})
                if isinstance(builders, dict):
                    shell_builders = builders.get('hudson.tasks.Shell', [])
                    if not isinstance(shell_builders, list):
                        shell_builders = [shell_builders]
                    
                    for shell_builder in shell_builders:
                        if isinstance(shell_builder, dict):
                            shell_command = shell_builder.get('command', '')
                            if shell_command:
                                steps.append({
                                    'name': 'Shell',
                                    'type': 'shell',
                                    'command': shell_command,
                                    'stage': 'Build'
                                })
            
            # 如果没有找到任何构建步骤，添加默认的Maven构建步骤
            if not any(step['type'] == 'maven' for step in steps):
                logger.warning("未找到Maven构建步骤，添加默认步骤")
                steps.append({
                    'name': 'Maven Build',
                    'type': 'maven',
                    'command': 'clean package -Dmaven.test.skip=true',
                    'stage': 'Build'
                })
        
        except ET.ParseError as e:
            logger.error(f"XML解析失败: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
        
        logger.info(f"从 Freestyle 项目中提取到 {len(steps)} 个构建步骤")
        return steps
    
    def _extract_ssh_command(self, action):
        """
        从 SSH 步骤中提取命令
        
        Args:
            action: SSH 步骤数据
            
        Returns:
            str: SSH 命令
        """
        try:
            if 'command' in action:
                return action['command']
            elif 'commands' in action:
                return '\n'.join(action['commands'])
            elif 'script' in action:
                return action['script']
            else:
                # 尝试查找其他可能包含命令的字段
                for key, value in action.items():
                    if isinstance(value, str) and ('command' in key.lower() or 'script' in key.lower()):
                        return value
            
            # 如果找不到明确的命令字段，返回整个 action 的字符串表示
            return f"SSH Action: {json.dumps(action)}"
        except Exception as e:
            logger.error(f"提取 SSH 命令时出错: {str(e)}")
            return "无法提取 SSH 命令"

    def _extract_environment_from_freestyle(self, job_data):
        """
        从自由风格项目中提取环境变量
        
        Args:
            job_data: 作业数据
            
        Returns:
            dict: 环境变量字典
        """
        environment = {}
        
        # 检查是否有环境变量注入
        if 'property' in job_data:
            for prop in job_data.get('property', []):
                # 检查是否是环境变量注入属性
                if '_class' in prop and 'EnvInjectJobProperty' in prop.get('_class', ''):
                    # 提取环境变量
                    if 'info' in prop and 'propertiesContent' in prop['info']:
                        env_content = prop['info']['propertiesContent']
                        # 解析环境变量内容
                        for line in env_content.split('\n'):
                            if '=' in line:
                                key, value = line.split('=', 1)
                                environment[key.strip()] = value.strip()
                                logger.info(f"提取到环境变量: {key}={value}")
        
        # 添加一些基本环境变量
        if 'name' in job_data:
            environment['appName'] = job_data['name']
        
        # 默认环境变量
        default_env = {
            'projectVersion': '1.0.0',
            'gitBranch': 'main'
        }
        
        # 合并默认环境变量（不覆盖已有的）
        for key, value in default_env.items():
            if key not in environment:
                environment[key] = value
        
        return environment

    def _parse_freestyle_job(self, job_data):
        """
        解析自由风格项目
        
        Args:
            job_data: 作业数据
            
        Returns:
            dict: 解析后的流水线模型
        """
        logger.info(f"解析自由风格项目: {job_data.get('name', '')}")
        
        # 创建基本模型
        pipeline_model = {
            'name': job_data.get('name', ''),
            'parameters': self._extract_parameters(job_data),
            'environment': self._extract_environment_from_freestyle(job_data),
            'agent': {'type': 'any'},
            'stages': [],
            'build_steps': []
        }
        
        # 提取构建步骤
        build_steps = self._extract_freestyle_steps(job_data)
        pipeline_model['build_steps'] = build_steps
        
        # 根据构建步骤创建阶段
        stages = []
        checkout_steps = [step for step in build_steps if step.get('stage') == 'Checkout']
        build_steps_list = [step for step in build_steps if step.get('stage') == 'Build']
        deploy_steps = [step for step in build_steps if step.get('stage') == 'Deploy']
        
        # 添加检出阶段
        if checkout_steps:
            stages.append({
                'name': 'Checkout',
                'steps': checkout_steps
            })
        
        # 添加构建阶段
        if build_steps_list:
            stages.append({
                'name': 'Build',
                'steps': build_steps_list
            })
        
        # 添加部署阶段
        if deploy_steps:
            stages.append({
                'name': 'Deploy',
                'steps': deploy_steps
            })
        
        # 添加阶段到模型
        pipeline_model['stages'] = stages
        
        logger.info(f"解析完成，共提取到 {len(stages)} 个阶段，{len(build_steps)} 个构建步骤")
        return pipeline_model
    
    def _parse_job_data(self, job_data):
        """
        解析作业数据
        
        Args:
            job_data: 作业数据
            
        Returns:
            dict: 解析后的流水线模型
        """
        # 检查作业类型
        job_class = job_data.get('_class', '')
        logger.info(f"作业类型: {job_class}")
        
        # 根据作业类型选择不同的解析方法
        if 'WorkflowJob' in job_class:
            # 流水线作业
            logger.info("检测到流水线作业")
            return self._parse_pipeline_job(job_data)
        elif 'FreeStyleProject' in job_class:
            # 自由风格项目
            logger.info("检测到自由风格项目")
            return self._parse_freestyle_job(job_data)
        else:
            # 未知类型
            logger.warning(f"未知的作业类型: {job_class}")
            return {
                'name': job_data.get('name', ''),
                'parameters': [],
                'environment': {},
                'agent': {'type': 'any'},
                'stages': []
            }

    def _extract_parameters(self, job_data):
        """
        提取项目参数
        
        Args:
            job_data: 作业数据
            
        Returns:
            list: 参数列表
        """
        parameters = []
        
        # 检查是否有 properties 字段
        if isinstance(job_data, dict) and 'properties' in job_data:
            for prop in job_data['properties']:
                if '_class' in prop and 'ParametersDefinitionProperty' in prop['_class']:
                    if 'parameterDefinitions' in prop:
                        for param in prop['parameterDefinitions']:
                            param_name = param.get('name', '')
                            param_default = param.get('defaultValue', '')
                            param_desc = param.get('description', '')
                            
                            # 添加参数到模型
                            self.pipeline_model.add_parameter(param_name, param_default, param_desc)
                            parameters.append({
                                'name': param_name,
                                'value': param_default,
                                'description': param_desc
                            })
        
        logger.info(f"获取到 {len(parameters)} 个参数")
        return parameters