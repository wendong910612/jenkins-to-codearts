#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CodeArts转换器
负责将解析后的Jenkins阶段转换为CodeArts YAML
"""

import os
import re
import yaml
from utils.logger import logger
from utils.template_loader import TemplateLoader
from models.pipeline_model import PipelineModel

class CodeArtsConverter:
    """CodeArts转换器类"""
    
    def __init__(self, pipeline_model, output_path="codearts_pipeline.yaml"):
        """
        初始化转换器
        
        Args:
            pipeline_model: 流水线模型
            output_path: 输出文件路径
        """
        # 如果 pipeline_model 是 PipelineModel 对象，则使用 to_dict 方法获取流水线阶段
        if isinstance(pipeline_model, PipelineModel):
            self.pipeline_stages = pipeline_model.to_dict()
        else:
            # 否则直接使用 pipeline_model
            self.pipeline_stages = pipeline_model
        
        self.output_path = output_path
        self.template_loader = TemplateLoader()
        
        # 加载映射配置
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "pipeline_mapping.yaml")
        with open(config_path, 'r', encoding='utf-8') as f:
            self.mapping_config = yaml.safe_load(f)
        
        # 获取需要忽略的阶段和需要转换为sh的阶段
        self.ignore_stages = self.mapping_config.get('ignore_stages', [])
        self.sh_stages = self.mapping_config.get('sh_stages', [])
        logger.info(f"需要忽略的阶段: {self.ignore_stages}")
        logger.info(f"需要转换为sh的阶段: {self.sh_stages}")

    def convert(self):
        """
        转换为CodeArts YAML
        
        Returns:
            bool: 转换是否成功
        """
        logger.info("开始转换为CodeArts YAML")
        
        # 创建基本的YAML结构
        codearts_yaml = {
            'env': {},
            'jobs': {}
        }
        
        # 添加基本环境变量
        base_env = {
            'projectVersion': '1.0.0',
            'appName': '',
            'gitBranch': 'main'
        }
        
        # 将基本环境变量添加到YAML中
        codearts_yaml['env'].update(base_env)
        
        # 将参数转换为环境变量（确保使用正确的驼峰命名）
        if 'parameters' in self.pipeline_stages:
            for param in self.pipeline_stages.get('parameters', []):
                # 确保 param 是字典类型
                if isinstance(param, dict):
                    # 获取参数名称
                    param_name = param.get('name', '')
                    if param_name:
                        # 转换为驼峰命名
                        camel_name = self._convert_to_camel_case(param_name)
                        # 获取参数值，优先使用 default 键
                        param_value = param.get('default', param.get('value', ''))
                        # 添加到环境变量
                        codearts_yaml['env'][camel_name] = param_value
        
        # 添加环境变量
        if 'environment' in self.pipeline_stages:
            for key, value in self.pipeline_stages['environment'].items():
                camel_key = self._convert_to_camel_case(key)
                codearts_yaml['env'][camel_key] = value
        
        # 动态生成任务和依赖关系
        stages = self.pipeline_stages.get('stages', [])
        previous_job_id = None
        
        # 遍历所有阶段，生成任务
        for stage in stages:
            stage_name = stage.get('name', f"Stage_{len(codearts_yaml['jobs'])}")
            
            # 检查是否在忽略列表中
            if stage_name in self.ignore_stages:
                logger.info(f"忽略阶段: {stage_name}")
                continue
            
            job_id = self._generate_camel_case_job_id(stage_name)
            
            # 确保job_id唯一
            counter = 1
            original_job_id = job_id
            while job_id in codearts_yaml['jobs']:
                job_id = f"{original_job_id}{counter}"
                counter += 1
            
            # 创建任务
            codearts_yaml['jobs'][job_id] = {
                'name': stage_name,
                'steps': []
            }
            
            # 如果有前置任务，添加依赖关系
            if previous_job_id:
                codearts_yaml['jobs'][job_id]['needs'] = [previous_job_id]
            
            # 检查是否需要转换为sh步骤
            if stage_name in self.sh_stages:
                # 添加shell步骤
                codearts_yaml['jobs'][job_id]['steps'].append({
                    'name': f"执行{stage_name}",
                    'run': f"echo \"执行{stage_name}阶段...\""
                })
            else:
                # 尝试根据阶段名称映射到模板
                template_name = self._map_stage_to_template(stage_name)
                if template_name:
                    # 加载模板
                    template = self.template_loader.load_template(template_name)
                    if template:
                        # 添加模板步骤
                        codearts_yaml['jobs'][job_id]['steps'].append(template)
                    else:
                        # 如果没有找到模板，添加默认shell步骤
                        codearts_yaml['jobs'][job_id]['steps'].append({
                            'name': f"执行{stage_name}",
                            'run': f"echo \"执行{stage_name}阶段...\""
                        })
                else:
                    # 如果没有映射到模板，添加默认shell步骤
                    codearts_yaml['jobs'][job_id]['steps'].append({
                        'name': f"执行{stage_name}",
                        'run': f"echo \"执行{stage_name}阶段...\""
                    })
            
            # 更新前置任务
            previous_job_id = job_id
        
        # 如果没有任何任务，添加一个默认任务
        if not codearts_yaml['jobs']:
            codearts_yaml['jobs']['default'] = {
                'name': 'Default',
                'steps': [{
                    'name': '默认步骤',
                    'run': 'echo "默认步骤"'
                }]
            }
        
        # 将YAML写入文件
        try:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                yaml.dump(codearts_yaml, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            logger.info(f"成功生成CodeArts YAML: {self.output_path}")
            return True
        except Exception as e:
            logger.error(f"生成CodeArts YAML失败: {str(e)}")
            return False

    def _map_stage_to_template(self, stage_name):
        """
        将阶段名称映射到模板
        
        Args:
            stage_name: 阶段名称
            
        Returns:
            str: 模板名称
        """
        # 1. 首先检查是否在 sh_stages 列表中
        if stage_name in self.sh_stages:
            logger.info(f"阶段 '{stage_name}' 将转换为 shell 步骤")
            return None  # 返回 None 表示使用默认的 shell 步骤
        
        # 2. 然后检查直接映射
        for mapping in self.mapping_config.get('stages', []):
            if mapping.get('jenkins_stage') == stage_name:
                logger.info(f"阶段 '{stage_name}' 直接映射到模板 '{mapping.get('template')}'")
                return mapping.get('template')
        
        # 3. 最后尝试关键字映射（如果没有直接映射）
        stage_name_lower = stage_name.lower()
        for key, keywords in self.mapping_config.get('keywords', {}).items():
            if any(keyword in stage_name_lower for keyword in keywords):
                logger.info(f"阶段 '{stage_name}' 通过关键字映射到模板 '{key}'")
                return key
        
        # 如果没有找到任何映射，返回 None
        logger.info(f"阶段 '{stage_name}' 没有找到映射，将使用默认 shell 步骤")
        return None
    
    def _get_step_name(self, step):
        """获取步骤的名称"""
        if step['type'] == 'code_check':
            return "代码检查"
        elif step['type'] == 'build':
            return "编译构建"
        elif step['type'] == 'deploy':
            return "部署"
        elif step['type'] == 'sh':
            # 截取命令的前20个字符作为名称
            cmd = step['command']
            if len(cmd) > 20:
                cmd = cmd[:20] + "..."
            return f"执行命令: {cmd}"
        else:
            return "未知步骤"
    
    def _convert_shell(self, command):
        """
        转换shell命令步骤
        
        Args:
            command: shell命令
            
        Returns:
            dict: CodeArts shell步骤信息
        """
        template = self.template_loader.load_template('shell.yaml')
        
        # 替换模板中的参数
        task = yaml.safe_load(template)
        task['run'] = command
        
        return task
    
    def _get_job_id(self, name):
        """根据阶段名称生成任务ID"""
        # 简化名称，移除特殊字符，转为小写
        job_id = re.sub(r'[^a-zA-Z0-9]', '_', name).lower()
        
        # 确保生成的ID不为空，且不只包含下划线
        if not job_id or all(c == '_' for c in job_id):
            # 如果名称转换后为空或只有下划线，使用默认前缀加随机字符
            if '代码检查' in name:
                return 'code_check'
            elif '编译' in name or '构建' in name:
                return 'build'
            elif '部署' in name:
                return 'deploy'
            else:
                return 'task_' + str(hash(name) % 10000)
        
        return job_id
    
    def _convert_job(self, stage):
        """
        转换Jenkins阶段为CodeArts任务
        
        Args:
            stage: Jenkins阶段信息
            
        Returns:
            dict: CodeArts任务信息
        """
        logger.debug(f"转换阶段: {stage['name']}")
        
        job = {
            'name': stage['name'],
            'steps': []
        }
        
        # 添加环境变量
        if stage['environment']:
            job['env'] = stage['environment']
        
        # 转换每个步骤
        for step in stage['steps']:
            task = self._convert_step(step)
            if task:
                job['steps'].append(task)
        
        return job
    
    def _convert_condition(self, jenkins_condition):
        """
        转换条件表达式
        
        Args:
            jenkins_condition: Jenkins条件表达式，可能是字符串或字典
            
        Returns:
            str: 转换后的条件表达式
        """
        # 如果条件是字典类型，需要特殊处理
        if isinstance(jenkins_condition, dict):
            # 处理equals条件
            if 'equals' in jenkins_condition:
                expected = jenkins_condition['equals'].get('expected', '')
                actual = jenkins_condition['equals'].get('actual', '')
                # 转换参数引用，确保使用正确的格式
                actual = actual.replace('params.', 'env.')
                return f"env.{actual.split('.')[-1]} == '{expected}'"
            
            # 处理allOf条件
            elif 'allOf' in jenkins_condition:
                conditions = []
                for condition in jenkins_condition['allOf']:
                    conditions.append(self._convert_condition(condition))
                return " && ".join(conditions)
            
            # 其他类型的条件，返回一个默认值
            else:
                logger.warning(f"未知的条件类型: {jenkins_condition}")
                return "true"
        
        # 如果条件是字符串类型，进行简单替换
        elif isinstance(jenkins_condition, str):
            condition = jenkins_condition
            condition = condition.replace('branch', 'gitBranch')
            condition = condition.replace('params.', '')
            condition = condition.replace('env.', '')
            return f"env.{condition}"
        
        # 其他类型，返回默认值
        else:
            logger.warning(f"未知的条件类型: {type(jenkins_condition)}")
            return "true"
    
    def _convert_step(self, step, stage_name=""):
        """
        转换单个步骤
        
        Args:
            step: Jenkins步骤信息
            stage_name: 阶段名称，默认为空字符串
            
        Returns:
            dict: CodeArts步骤信息
        """
        # 根据阶段名称选择合适的步骤
        stage_name_lower = stage_name.lower()
        
        # 代码检查阶段
        if '代码检查' in stage_name_lower or 'sonar' in stage_name_lower:
            return {
                'name': 'Code Check Step',
                'uses': 'CodeArtsCheck',
                'with': {
                    'jobId': '43885d46e13d4bf583d3a648e9b39d1e',
                    'checkMode': 'full',
                    'language': 'java'
                }
            }
        
        # 构建阶段
        elif '构建' in stage_name_lower or 'build' in stage_name_lower:
            return {
                'name': 'Build Image',
                'uses': 'CodeArtsBuild',
                'with': {
                    'tool': 'maven',
                    'command': 'package',
                    'artifactIdentifier': '${{ env.appName }}',
                    'skipTests': '${{ !env.unitTest }}'
                }
            }
        
        # 部署阶段
        elif '部署' in stage_name_lower or 'deploy' in stage_name_lower:
            return {
                'name': 'Deploy Application',
                'uses': 'CodeArtsDeploy',
                'with': {
                    'cluster': '${{ env.deployEnv }}',
                    'namespace': 'default',
                    'manifests': 'k8s/*.yaml'
                }
            }
        
        # 单元测试阶段
        elif '单元测试' in stage_name_lower or 'unit test' in stage_name_lower:
            return {
                'name': 'Execute Unit Test',
                'run': '|\n          echo "执行单元测试..."\n          mvn test'
            }
        
        # 准备阶段
        elif '准备' in stage_name_lower or 'preparation' in stage_name_lower:
            return {
                'name': 'Prepare Environment',
                'run': '|\n          echo "准备构建环境..."\n          echo "应用名称: ${{ env.appName }}"\n          echo "部署环境: ${{ env.deployEnv }}"'
            }
        
        # 其他阶段，使用shell步骤
        else:
            command = ""
            if isinstance(step, dict):
                if 'type' in step and step['type'] == 'sh':
                    command = step.get('command', '')
                elif 'type' in step and step['type'] == 'script':
                    command = step.get('content', '')
            
            return {
                'name': self._get_step_name(step) if isinstance(step, dict) and 'type' in step else '执行命令',
                'run': command or "echo '执行命令'"
            }
        
        # 获取步骤内容
        step_content = ""
        
        # 根据步骤类型获取内容
        if isinstance(step, dict):
            if 'type' in step and step['type'] == 'script':
                step_content = step.get('content', '')
            elif 'type' in step and step['type'] == 'sh':
                step_content = step.get('command', '')
            else:
                step_content = str(step)
        else:
            step_content = str(step)
        
        # 添加阶段名称到内容中，以便更好地匹配
        step_content += " " + stage_name
        
        # 获取映射关系
        mapping = self.template_loader.get_mapping_for_step(step_content)
        
        if not mapping:
            # 如果没有匹配到映射关系，使用shell步骤
            command = ""
            if isinstance(step, dict):
                if 'type' in step and step['type'] == 'sh':
                    command = step.get('command', '')
                elif 'type' in step and step['type'] == 'script':
                    command = step.get('content', '')
            return {
                'name': self._get_step_name(step),
                'run': command or "echo '执行命令'"
            }
        
        # 根据映射类型转换步骤
        task = None
        if mapping['type'] == 'build':
            task = self._convert_build(mapping['params'])
        elif mapping['type'] == 'code_check':
            task = self._convert_code_check(mapping['params'])
        elif mapping['type'] == 'deploy':
            task = self._convert_deploy(mapping['params'])
        else:
            # 默认使用shell步骤
            command = ""
            if isinstance(step, dict):
                if 'type' in step and step['type'] == 'sh':
                    command = step.get('command', '')
                elif 'type' in step and step['type'] == 'script':
                    command = step.get('content', '')
            return {
                'name': self._get_step_name(step),
                'run': command or "echo '执行命令'"
            }
        
        # 确保生成正确的步骤结构
        if task:
            step_info = {
                'name': task['name'],
                'uses': task['uses'],
                'with': task['with']
            } if 'uses' in task else {
                'name': task['name'],
                'run': task['run']
            }
            return step_info
        
        # 如果没有生成任何任务，返回一个默认步骤
        return {
            'name': '默认步骤',
            'run': "echo '执行默认步骤'"
        }
    
    def _convert_code_check(self, params):
        """转换代码检查步骤"""
        template = self.template_loader.load_template('code_check.yaml')
        
        # 替换模板中的参数
        task = yaml.safe_load(template)
        
        # 更新参数
        if 'language' in params:
            task['with']['language'] = params['language']
        if 'tool' in params:
            task['with']['tool'] = params['tool']
        
        return task
    
    def _convert_build(self, params):
        """转换构建步骤"""
        template = self.template_loader.load_template('build.yaml')
        
        # 替换模板中的参数
        task = yaml.safe_load(template)
        
        # 更新参数
        if 'tool' in params:
            task['with']['tool'] = params['tool']
        if 'command' in params:
            task['with']['command'] = params['command']
        
        return task
    
    def _convert_deploy(self, params):
        """转换部署步骤"""
        template = self.template_loader.load_template('deploy.yaml')
        
        # 替换模板中的参数
        task = yaml.safe_load(template)
        
        # 更新参数
        if 'cluster' in params:
            task['with']['cluster'] = params['cluster']
        if 'namespace' in params:
            task['with']['namespace'] = params['namespace']
        
        return task
    
    def _convert_shell(self, command):
        """
        转换shell命令步骤
        
        Args:
            command: shell命令
            
        Returns:
            dict: CodeArts shell步骤信息
        """
        return {
            'name': '执行Shell',
            'run': command
        }
    
    def _convert_to_camel_case(self, name):
        """
        将名称转换为驼峰命名
        
        Args:
            name: 原始名称
            
        Returns:
            str: 驼峰命名的名称
        """
        # 处理特殊情况
        if name is None:
            return ""
            
        # 如果是字典类型，可能是从 Jenkins 参数中获取的
        if isinstance(name, dict):
            # 尝试获取 name 或 default 键
            if 'name' in name:
                return self._convert_to_camel_case(name['name'])
            elif 'default' in name:
                return self._convert_to_camel_case(name['default'])
            else:
                # 如果没有找到合适的键，返回空字符串
                return ""
                
        # 确保 name 是字符串
        name = str(name)
        
        # 处理全大写情况
        if name.upper() == name:
            return name.lower()
        
        # 移除特殊字符，分割单词
        words = re.split(r'[^a-zA-Z0-9]', name)
        words = [w for w in words if w]  # 移除空字符串
        
        if not words:
            return name.lower()
        
        # 第一个单词小写，其余单词首字母大写
        result = words[0].lower()
        for word in words[1:]:
            if word:
                result += word[0].upper() + word[1:].lower()
        
        return result
    
    def _generate_camel_case_job_id(self, name):
        """
        生成驼峰命名的任务ID
        
        Args:
            name: 阶段名称
            
        Returns:
            str: 驼峰命名的任务ID
        """
        # 特殊情况处理
        name_lower = name.lower()
        if '代码检查' in name_lower or 'sonar' in name_lower:
            return "codeCheck"
        elif '编译' in name_lower or '构建' in name_lower or 'build' in name_lower:
            return "build"
        elif '部署' in name_lower or 'deploy' in name_lower:
            return "deploy"
        elif '单元测试' in name_lower or 'unit test' in name_lower:
            return "unitTest"
        elif '准备' in name_lower or 'preparation' in name_lower:
            return "preparation"
        elif '状态' in name_lower or 'status' in name_lower:
            return "checkStatus"
        elif '报告' in name_lower or 'report' in name_lower:
            if 'image' in name_lower or '镜像' in name_lower:
                return "imageReport"
            else:
                return "reportTest"
        elif '增量' in name_lower or 'inc' in name_lower:
            return "incUnitTest"
        
        # 一般情况处理
        words = re.split(r'[^a-zA-Z0-9]', name)
        words = [w for w in words if w]  # 移除空字符串
        
        if not words:
            return "job" + str(hash(name) % 1000)
        
        # 第一个单词小写，其余单词首字母大写
        result = words[0].lower()
        for word in words[1:]:
            if word:
                result += word[0].upper() + word[1:].lower()
        
        return result