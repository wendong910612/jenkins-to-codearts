#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Jenkins API 客户端
负责连接 Jenkins 服务器并获取 Job 信息
"""

import requests
import json
import re
from utils.logger import logger

class JenkinsClient:
    """Jenkins API 客户端"""
    
    def __init__(self, jenkins_url, username=None, password=None, api_token=None):
        """
        初始化 Jenkins API 客户端
        
        Args:
            jenkins_url: Jenkins 服务器 URL
            username: Jenkins 用户名
            password: Jenkins 密码
            api_token: Jenkins API Token (不再使用)
        """
        self.jenkins_url = jenkins_url.rstrip('/')
        self.username = username
        self.password = password
        
        # 只使用用户名和密码进行认证
        self.auth = (username, password) if username and password else None
    
    def get_job_config(self, job_name):
        """
        获取 Job 配置
        
        Args:
            job_name: Job 名称
            
        Returns:
            str: Job 配置 XML
        """
        url = f"{self.jenkins_url}/job/{job_name}/config.xml"
        logger.info(f"获取 Job 配置: {url}")
        
        try:
            response = requests.get(url, auth=self.auth)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取 Job 配置失败: {str(e)}")
            return None
    
    def get_last_build_info(self, job_name):
        """
        获取最后一次构建信息
        
        Args:
            job_name: Job 名称
            
        Returns:
            dict: 构建信息
        """
        url = f"{self.jenkins_url}/job/{job_name}/lastBuild/api/json?pretty=true"
        logger.info(f"获取最后一次构建信息: {url}")
        
        try:
            response = requests.get(url, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取最后一次构建信息失败: {str(e)}")
            return None
    
    def get_pipeline_script(self, job_name):
        """
        获取流水线脚本
        
        Args:
            job_name: Job 名称
            
        Returns:
            str: 流水线脚本
        """
        # 首先获取 Job 配置
        config_xml = self.get_job_config(job_name)
        if not config_xml:
            return None
        
        # 从配置中提取流水线脚本
        script_pattern = r'<script>(.*?)</script>'
        script_match = re.search(script_pattern, config_xml, re.DOTALL)
        
        if script_match:
            return script_match.group(1)
        
        # 如果没有找到内联脚本，尝试查找 SCM 中的 Jenkinsfile 路径
        scm_pattern = r'<scriptPath>(.*?)</scriptPath>'
        scm_match = re.search(scm_pattern, config_xml, re.DOTALL)
        
        if scm_match:
            jenkinsfile_path = scm_match.group(1)
            logger.info(f"流水线脚本存储在 SCM 中: {jenkinsfile_path}")
            return f"// Jenkinsfile 存储在 SCM 中: {jenkinsfile_path}\n// 请从 SCM 获取具体内容"
        
        logger.warning("未找到流水线脚本")
        return None
    
    def get_pipeline_stages(self, job_name):
        """
        获取流水线阶段信息
        
        Args:
            job_name: Job 名称
            
        Returns:
            list: 阶段信息列表
        """
        # 获取最后一次构建信息
        build_info = self.get_last_build_info(job_name)
        if not build_info:
            return []
        
        # 获取流水线阶段信息
        url = f"{self.jenkins_url}/job/{job_name}/lastBuild/wfapi/describe"
        logger.info(f"获取流水线阶段信息: {url}")
        
        try:
            response = requests.get(url, auth=self.auth)
            response.raise_for_status()
            stages_info = response.json()
            
            # 提取阶段信息
            stages = []
            for stage in stages_info.get('stages', []):
                stage_name = stage.get('name')
                stage_status = stage.get('status')
                stage_id = stage.get('id')
                
                # 获取阶段详细信息
                stage_url = f"{self.jenkins_url}/job/{job_name}/lastBuild/execution/node/{stage_id}/wfapi/describe"
                try:
                    stage_response = requests.get(stage_url, auth=self.auth)
                    stage_response.raise_for_status()
                    stage_detail = stage_response.json()
                    
                    # 提取步骤信息
                    steps = []
                    for step in stage_detail.get('stageFlowNodes', []):
                        step_name = step.get('name')
                        step_status = step.get('status')
                        
                        # 获取步骤日志
                        step_log = self._get_step_log(job_name, step.get('id'))
                        
                        steps.append({
                            'name': step_name,
                            'status': step_status,
                            'log': step_log
                        })
                    
                    stages.append({
                        'name': stage_name,
                        'status': stage_status,
                        'steps': steps
                    })
                except Exception as e:
                    logger.error(f"获取阶段详细信息失败: {str(e)}")
            
            return stages
        except Exception as e:
            logger.error(f"获取流水线阶段信息失败: {str(e)}")
            return []
    
    def _get_step_log(self, job_name, node_id):
        """
        获取步骤日志
        
        Args:
            job_name: Job 名称
            node_id: 节点 ID
            
        Returns:
            str: 步骤日志
        """
        url = f"{self.jenkins_url}/job/{job_name}/lastBuild/execution/node/{node_id}/log"
        logger.info(f"获取步骤日志: {url}")
        
        try:
            response = requests.get(url, auth=self.auth)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取步骤日志失败: {str(e)}")
            return ""
    
    def extract_pipeline_structure(self, job_name):
        """
        提取流水线结构
        
        Args:
            job_name: Job 名称
            
        Returns:
            dict: 流水线结构
        """
        # 获取流水线脚本
        pipeline_script = self.get_pipeline_script(job_name)
        
        # 获取流水线阶段信息
        stages = self.get_pipeline_stages(job_name)
        
        # 获取 Job 信息
        job_info = self.get_job_info(job_name)
        
        # 提取参数
        parameters = []
        if job_info and 'property' in job_info:
            for prop in job_info.get('property', []):
                if 'parameterDefinitions' in prop:
                    for param in prop.get('parameterDefinitions', []):
                        param_name = param.get('name')
                        param_default = param.get('defaultValue', '')
                        param_description = param.get('description', '')
                        param_type = param.get('type', 'string')
                        
                        parameters.append({
                            'name': param_name,
                            'default': param_default,
                            'description': param_description,
                            'type': param_type
                        })
        
        # 构建流水线结构
        pipeline_structure = {
            'name': job_name,
            'script': pipeline_script,
            'parameters': parameters,
            'stages': stages
        }
        
        return pipeline_structure
    
    def export_pipeline_structure(self, job_name, output_file='jenkins_pipeline_structure.json'):
        """
        导出流水线结构到文件
        
        Args:
            job_name: Job 名称
            output_file: 输出文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            # 提取流水线结构
            pipeline_structure = self.extract_pipeline_structure(job_name)
            
            if not pipeline_structure:
                logger.error(f"获取流水线结构失败: {job_name}")
                return False
            
            # 清理日志内容，移除HTML
            cleaned_structure = self._clean_pipeline_structure(pipeline_structure)
            
            # 将结构写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(cleaned_structure, f, indent=2, ensure_ascii=False)
            
            logger.info(f"流水线结构已导出到: {output_file}")
            return True
        except Exception as e:
            logger.error(f"导出流水线结构失败: {str(e)}")
            import traceback
            logger.info(traceback.format_exc())
            return False
    
    def _clean_pipeline_structure(self, pipeline_structure):
        """
        清理流水线结构中的日志内容
        
        Args:
            pipeline_structure: 流水线结构
            
        Returns:
            dict: 清理后的流水线结构
        """
        import re
        import copy
        
        # 深拷贝避免修改原始数据
        cleaned = copy.deepcopy(pipeline_structure)
        
        # 清理阶段和步骤的日志
        if 'stages' in cleaned:
            for stage in cleaned['stages']:
                if 'steps' in stage:
                    for step in stage['steps']:
                        if 'log' in step:
                            # 提取日志中的实际命令和输出
                            log = step['log']
                            
                            # 移除HTML标签
                            clean_log = re.sub(r'<!DOCTYPE.*?</html>', '', log, flags=re.DOTALL)
                            
                            # 提取时间戳行
                            timestamp_lines = re.findall(r'<span class="timestamp"><b>.*?</b> </span>(.*?)(?=<span class="timestamp"|$)', clean_log, re.DOTALL)
                            
                            # 合并提取的行
                            if timestamp_lines:
                                clean_log = '\n'.join([line.strip() for line in timestamp_lines])
                            
                            # 移除剩余的HTML标签
                            clean_log = re.sub(r'<.*?>', '', clean_log)
                            
                            # 移除多余的空行
                            clean_log = re.sub(r'\n\s*\n', '\n', clean_log)
                            
                            # 限制日志长度
                            if len(clean_log) > 1000:
                                clean_log = clean_log[:1000] + "... (日志已截断)"
                            
                            step['log'] = clean_log.strip()
        
        return cleaned
    
    def _determine_step_type(self, log):
        """
        根据日志判断步骤类型
        
        Args:
            log: 步骤日志
            
        Returns:
            str: 步骤类型
        """
        log_lower = log.lower()
        
        if 'mvn ' in log_lower or 'maven' in log_lower:
            return 'maven'
        elif 'gradle' in log_lower:
            return 'gradle'
        elif 'npm ' in log_lower or 'yarn ' in log_lower:
            return 'npm'
        elif 'docker ' in log_lower or 'build -t' in log_lower:
            return 'docker'
        elif 'sonar' in log_lower:
            return 'sonar'
        elif 'deploy' in log_lower or 'kubectl' in log_lower:
            return 'deploy'
        elif 'git ' in log_lower or 'checkout' in log_lower:
            return 'checkout'
        elif 'sh ' in log_lower or 'shell' in log_lower:
            return 'sh'
        elif 'echo' in log_lower:
            return 'echo'
        else:
            return 'sh'  # 默认为 shell 命令
        
    def _extract_command(self, log):
        """
        从日志中提取命令
        
        Args:
            log: 步骤日志
            
        Returns:
            str: 命令
        """
        # 尝试提取 sh 命令
        sh_pattern = r'sh\s+[\'"](.*?)[\'"]'
        sh_match = re.search(sh_pattern, log)
        if sh_match:
            return sh_match.group(1)
        
        # 尝试提取 echo 命令
        echo_pattern = r'echo\s+[\'"](.*?)[\'"]'
        echo_match = re.search(echo_pattern, log)
        if echo_match:
            return f"echo '{echo_match.group(1)}'"
        
        # 尝试提取 Maven 命令
        mvn_pattern = r'mvn\s+(.*?)[\r\n]'
        mvn_match = re.search(mvn_pattern, log)
        if mvn_match:
            return f"mvn {mvn_match.group(1)}"
        
        # 尝试提取其他命令行
        cmd_pattern = r'(\$\s+.*?)[\r\n]'
        cmd_match = re.search(cmd_pattern, log)
        if cmd_match:
            return cmd_match.group(1).strip('$ ')
        
        # 如果没有找到明确的命令，返回日志的第一行作为命令
        lines = log.strip().split('\n')
        if lines:
            return lines[0]
        
        return ""
        
    def get_pipeline_structure(self, job_name):
        """
        获取流水线结构
        
        Args:
            job_name: Job 名称
            
        Returns:
            dict: 流水线结构
        """
        logger.info(f"获取流水线结构: {job_name}")
        
        # 规范化 job_name
        job_path = self._normalize_job_path(job_name)
        
        # 尝试多种方式获取流水线结构
        pipeline_structure = {}
        
        # 方法1: 使用 wfapi/describe 端点
        try:
            api_url = f"{self.jenkins_url}/job/{job_path}/wfapi/describe"
            logger.info(f"尝试从 wfapi/describe 获取流水线结构: {api_url}")
            response = requests.get(api_url, auth=self.auth, verify=False)
            if response.status_code == 200:
                pipeline_structure = response.json()
                if 'stages' in pipeline_structure:
                    logger.info(f"从 wfapi/describe 获取到 {len(pipeline_structure.get('stages', []))} 个阶段")
        except Exception as e:
            logger.warning(f"从 wfapi/describe 获取流水线结构失败: {str(e)}")
        
        # 方法2: 如果没有获取到阶段信息，尝试从最后一次构建中获取
        if not pipeline_structure.get('stages'):
            try:
                api_url = f"{self.jenkins_url}/job/{job_path}/lastBuild/wfapi/describe"
                logger.info(f"尝试从最后一次构建中获取流水线结构: {api_url}")
                response = requests.get(api_url, auth=self.auth, verify=False)
                if response.status_code == 200:
                    pipeline_structure = response.json()
                    if 'stages' in pipeline_structure:
                        logger.info(f"从最后一次构建中获取到 {len(pipeline_structure.get('stages', []))} 个阶段")
            except Exception as e:
                logger.warning(f"从最后一次构建中获取流水线结构失败: {str(e)}")
        
        # 方法3: 如果仍然没有获取到阶段信息，尝试从 Blue Ocean API 获取
        if not pipeline_structure.get('stages'):
            try:
                # 获取最后一次构建编号
                job_info_url = f"{self.jenkins_url}/job/{job_path}/api/json"
                job_info_response = requests.get(job_info_url, auth=self.auth, verify=False)
                job_info = job_info_response.json() if job_info_response.status_code == 200 else {}
                last_build_number = job_info.get('lastBuild', {}).get('number', 1)
                
                # 使用 Blue Ocean API
                blue_ocean_url = f"{self.jenkins_url}/blue/rest/organizations/jenkins/pipelines/{job_path.replace('/job/', '/')}/runs/{last_build_number}"
                logger.info(f"尝试从 Blue Ocean API 获取流水线结构: {blue_ocean_url}")
                blue_ocean_response = requests.get(blue_ocean_url, auth=self.auth, verify=False)
                
                if blue_ocean_response.status_code == 200:
                    blue_ocean_data = blue_ocean_response.json()
                    # 转换 Blue Ocean 数据为流水线结构
                    pipeline_structure = {
                        'name': blue_ocean_data.get('name', ''),
                        'stages': []
                    }
                    
                    # 获取节点信息
                    nodes_url = f"{blue_ocean_url}/nodes"
                    nodes_response = requests.get(nodes_url, auth=self.auth, verify=False)
                    
                    if nodes_response.status_code == 200:
                        nodes = nodes_response.json()
                        for node in nodes:
                            if node.get('type') == 'STAGE':
                                stage = {
                                    'name': node.get('displayName', ''),
                                    'steps': []
                                }
                                
                                # 获取阶段步骤
                                steps_url = f"{blue_ocean_url}/nodes/{node.get('id')}/steps"
                                steps_response = requests.get(steps_url, auth=self.auth, verify=False)
                                
                                if steps_response.status_code == 200:
                                    steps = steps_response.json()
                                    for step in steps:
                                        stage['steps'].append({
                                            'name': step.get('displayName', ''),
                                            'log': self._get_step_log(blue_ocean_url, node.get('id'), step.get('id'))
                                        })
                                
                                pipeline_structure['stages'].append(stage)
                        
                        logger.info(f"从 Blue Ocean API 获取到 {len(pipeline_structure.get('stages', []))} 个阶段")
            except Exception as e:
                logger.warning(f"从 Blue Ocean API 获取流水线结构失败: {str(e)}")
        
        # 方法4: 如果仍然没有获取到阶段信息，尝试从 config.xml 中获取 Jenkinsfile
        if not pipeline_structure.get('stages'):
            try:
                config_url = f"{self.jenkins_url}/job/{job_path}/config.xml"
                logger.info(f"尝试从 config.xml 获取 Jenkinsfile: {config_url}")
                config_response = requests.get(config_url, auth=self.auth, verify=False)
                
                if config_response.status_code == 200:
                    import xml.etree.ElementTree as ET
                    import tempfile
                    import os
                    
                    # 解析 XML
                    root = ET.fromstring(config_response.content)
                    
                    # 查找 definition 元素
                    definition = root.find(".//definition")
                    if definition is not None:
                        # 查找 script 元素
                        script = definition.find(".//script")
                        if script is not None and script.text:
                            logger.info("从 config.xml 中提取到 Jenkinsfile 内容")
                            
                            # 将 Jenkinsfile 内容保存到临时文件
                            with tempfile.NamedTemporaryFile(suffix='.jenkinsfile', delete=False) as temp:
                                temp.write(script.text.encode('utf-8'))
                                temp_path = temp.name
                            
                            # 使用 Jenkinsfile 解析器解析流水线结构
                            from parsers.jenkins_file_parser import JenkinsfileParser
                            jenkinsfile_parser = JenkinsfileParser(temp_path)
                            jenkinsfile_model = jenkinsfile_parser.parse()
                            
                            # 将 Jenkinsfile 解析结果转换为流水线结构
                            jenkinsfile_dict = jenkinsfile_model.to_dict()
                            pipeline_structure['stages'] = jenkinsfile_dict.get('stages', [])
                            pipeline_structure['script'] = script.text
                            
                            # 删除临时文件
                            os.unlink(temp_path)
                            
                            logger.info(f"从 Jenkinsfile 中获取到 {len(pipeline_structure.get('stages', []))} 个阶段")
            except Exception as e:
                logger.warning(f"从 config.xml 获取 Jenkinsfile 失败: {str(e)}")
        
        # 方法5: 如果是 Freestyle 项目，尝试从构建步骤中提取信息
        if not pipeline_structure.get('stages'):
            try:
                job_config_url = f"{self.jenkins_url}/job/{job_path}/config.xml"
                job_config_response = requests.get(job_config_url, auth=self.auth, verify=False)
                logger.info(f"请求 {job_config_url} ")
                if job_config_response.status_code == 200:
                    import xml.etree.ElementTree as ET
                    
                    # 解析 XML
                    root = ET.fromstring(job_config_response.content)
                    logger.info(f"请求结果 {job_config_response} ")
                    # 检查是否是 Freestyle 项目
                    project_class = root.tag
                    if project_class == 'project':
                        logger.info("检测到 Freestyle 项目，尝试提取构建步骤")
                        
                        # 提取构建步骤
                        builders = root.find(".//builders")
                        if builders is not None:
                            # 创建一个模拟的流水线结构
                            pipeline_structure = {
                                'name': job_path.split('/')[-1],
                                'stages': [{
                                    'name': 'Build',
                                    'steps': []
                                }]
                            }
                            
                            # 提取 shell 步骤
                            for shell in builders.findall(".//hudson.tasks.Shell"):
                                command = shell.find("./command")
                                if command is not None and command.text:
                                    pipeline_structure['stages'][0]['steps'].append({
                                        'name': 'Shell',
                                        'type': 'sh',
                                        'command': command.text
                                    })
                            
                            # 提取 Maven 步骤
                            for maven in builders.findall(".//hudson.tasks.Maven"):
                                targets = maven.find("./targets")
                                if targets is not None and targets.text:
                                    pipeline_structure['stages'][0]['steps'].append({
                                        'name': 'Maven',
                                        'type': 'maven',
                                        'command': targets.text
                                    })
                            
                            logger.info(f"从 Freestyle 项目中提取到 {len(pipeline_structure['stages'][0]['steps'])} 个构建步骤")
            except Exception as e:
                logger.warning(f"从 Freestyle 项目提取构建步骤失败: {str(e)}")
        
        # 如果仍然没有获取到阶段信息，添加一个空的阶段结构
        if not pipeline_structure:
            pipeline_structure = {
                'name': job_path.split('/')[-1],
                'stages': []
            }
        
        # 获取参数信息
        try:
            job_info_url = f"{self.jenkins_url}/job/{job_path}/api/json?tree=property[parameterDefinitions[name,defaultValue,description]]"
            job_info = self._make_request("GET", job_info_url)
            
            if job_info and 'property' in job_info:
                parameters = []
                for prop in job_info['property']:
                    if 'parameterDefinitions' in prop:
                        for param in prop['parameterDefinitions']:
                            parameters.append({
                                'name': param.get('name', ''),
                                'default': param.get('defaultValue', ''),
                                'description': param.get('description', '')
                            })
                
                pipeline_structure['parameters'] = parameters
                logger.info(f"获取到 {len(parameters)} 个参数")
        except Exception as e:
            logger.warning(f"获取参数信息失败: {str(e)}")
        
        return pipeline_structure

    def _normalize_job_path(self, job_name):
        """
        规范化任务路径
        
        Args:
            job_name: Jenkins 任务名称
            
        Returns:
            str: 规范化后的任务路径
        """
        # 移除开头的斜杠
        if job_name.startswith('/'):
            job_name = job_name[1:]
        
        # 处理嵌套任务路径
        if '/job/' not in job_name:
            parts = job_name.split('/')
            job_path = '/job/'.join(parts)
        else:
            job_path = job_name
        
        return job_path

    def _get_step_log(self, base_url, node_id, step_id):
        """
        获取步骤日志
        
        Args:
            base_url: 基础 URL
            node_id: 节点 ID
            step_id: 步骤 ID
            
        Returns:
            str: 步骤日志
        """
        log_url = f"{base_url}/nodes/{node_id}/steps/{step_id}/log"
        
        try:
            response = requests.get(log_url, auth=self.auth, verify=False)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取步骤日志失败: {str(e)}")
            return ""
    
    def extract_pipeline_structure(self, job_name):
        """
        提取流水线结构
        
        Args:
            job_name: Job 名称
            
        Returns:
            dict: 流水线结构
        """
        # 获取流水线脚本
        pipeline_script = self.get_pipeline_script(job_name)
        
        # 获取流水线阶段信息
        stages = self.get_pipeline_stages(job_name)
        
        # 获取 Job 信息
        job_info = self.get_job_info(job_name)
        
        # 提取参数
        parameters = []
        if job_info and 'property' in job_info:
            for prop in job_info.get('property', []):
                if 'parameterDefinitions' in prop:
                    for param in prop.get('parameterDefinitions', []):
                        param_name = param.get('name')
                        param_default = param.get('defaultValue', '')
                        param_description = param.get('description', '')
                        param_type = param.get('type', 'string')
                        
                        parameters.append({
                            'name': param_name,
                            'default': param_default,
                            'description': param_description,
                            'type': param_type
                        })
        
        # 构建流水线结构
        pipeline_structure = {
            'name': job_name,
            'script': pipeline_script,
            'parameters': parameters,
            'stages': stages
        }
        
        return pipeline_structure
    
    def export_pipeline_structure(self, job_name, output_file='jenkins_pipeline_structure.json'):
        """
        导出流水线结构到文件
        
        Args:
            job_name: Job 名称
            output_file: 输出文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            # 提取流水线结构
            pipeline_structure = self.extract_pipeline_structure(job_name)
            
            if not pipeline_structure:
                logger.error(f"获取流水线结构失败: {job_name}")
                return False
            
            # 清理日志内容，移除HTML
            cleaned_structure = self._clean_pipeline_structure(pipeline_structure)
            
            # 将结构写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(cleaned_structure, f, indent=2, ensure_ascii=False)
            
            logger.info(f"流水线结构已导出到: {output_file}")
            return True
        except Exception as e:
            logger.error(f"导出流水线结构失败: {str(e)}")
            import traceback
            logger.info(traceback.format_exc())
            return False
    
    def _clean_pipeline_structure(self, pipeline_structure):
        """
        清理流水线结构中的日志内容
        
        Args:
            pipeline_structure: 流水线结构
            
        Returns:
            dict: 清理后的流水线结构
        """
        import re
        import copy
        
        # 深拷贝避免修改原始数据
        cleaned = copy.deepcopy(pipeline_structure)
        
        # 清理阶段和步骤的日志
        if 'stages' in cleaned:
            for stage in cleaned['stages']:
                if 'steps' in stage:
                    for step in stage['steps']:
                        if 'log' in step:
                            # 提取日志中的实际命令和输出
                            log = step['log']
                            
                            # 移除HTML标签
                            clean_log = re.sub(r'<!DOCTYPE.*?</html>', '', log, flags=re.DOTALL)
                            
                            # 提取时间戳行
                            timestamp_lines = re.findall(r'<span class="timestamp"><b>.*?</b> </span>(.*?)(?=<span class="timestamp"|$)', clean_log, re.DOTALL)
                            
                            # 合并提取的行
                            if timestamp_lines:
                                clean_log = '\n'.join([line.strip() for line in timestamp_lines])
                            
                            # 移除剩余的HTML标签
                            clean_log = re.sub(r'<.*?>', '', clean_log)
                            
                            # 移除多余的空行
                            clean_log = re.sub(r'\n\s*\n', '\n', clean_log)
                            
                            # 限制日志长度
                            if len(clean_log) > 1000:
                                clean_log = clean_log[:1000] + "... (日志已截断)"
                            
                            step['log'] = clean_log.strip()
        
        return cleaned
    
    def _determine_step_type(self, log):
        """
        根据日志判断步骤类型
        
        Args:
            log: 步骤日志
            
        Returns:
            str: 步骤类型
        """
        log_lower = log.lower()
        
        if 'mvn ' in log_lower or 'maven' in log_lower:
            return 'maven'
        elif 'gradle' in log_lower:
            return 'gradle'
        elif 'npm ' in log_lower or 'yarn ' in log_lower:
            return 'npm'
        elif 'docker ' in log_lower or 'build -t' in log_lower:
            return 'docker'
        elif 'sonar' in log_lower:
            return 'sonar'
        elif 'deploy' in log_lower or 'kubectl' in log_lower:
            return 'deploy'
        elif 'git ' in log_lower or 'checkout' in log_lower:
            return 'checkout'
        elif 'sh ' in log_lower or 'shell' in log_lower:
            return 'sh'
        elif 'echo' in log_lower:
            return 'echo'
        else:
            return 'sh'  # 默认为 shell 命令
        
    def _extract_command(self, log):
        """
        从日志中提取命令
        
        Args:
            log: 步骤日志
            
        Returns:
            str: 命令
        """
        # 尝试提取 sh 命令
        sh_pattern = r'sh\s+[\'"](.*?)[\'"]'
        sh_match = re.search(sh_pattern, log)
        if sh_match:
            return sh_match.group(1)
        
        # 尝试提取 echo 命令
        echo_pattern = r'echo\s+[\'"](.*?)[\'"]'
        echo_match = re.search(echo_pattern, log)
        if echo_match:
            return f"echo '{echo_match.group(1)}'"
        
        # 尝试提取 Maven 命令
        mvn_pattern = r'mvn\s+(.*?)[\r\n]'
        mvn_match = re.search(mvn_pattern, log)
        if mvn_match:
            return f"mvn {mvn_match.group(1)}"
        
        # 尝试提取其他命令行
        cmd_pattern = r'(\$\s+.*?)[\r\n]'
        cmd_match = re.search(cmd_pattern, log)
        if cmd_match:
            return cmd_match.group(1).strip('$ ')
        
        # 如果没有找到明确的命令，返回日志的第一行作为命令
        lines = log.strip().split('\n')
        if lines:
            return lines[0]
        
        return ""
        
    def get_pipeline_structure(self, job_name):
        """
        获取流水线结构
        
        Args:
            job_name: Job 名称
            
        Returns:
            dict: 流水线结构
        """
        logger.info(f"获取流水线结构: {job_name}")
        
        # 规范化 job_name
        job_path = self._normalize_job_path(job_name)
        
        # 尝试多种方式获取流水线结构
        pipeline_structure = {}
        
        # 方法1: 使用 wfapi/describe 端点
        try:
            api_url = f"{self.jenkins_url}/job/{job_path}/wfapi/describe"
            logger.info(f"尝试从 wfapi/describe 获取流水线结构: {api_url}")
            response = self._make_request("GET", api_url)
            if response and 'stages' in response:
                pipeline_structure = response
                logger.info(f"从 wfapi/describe 获取到 {len(response.get('stages', []))} 个阶段")
        except Exception as e:
            logger.warning(f"从 wfapi/describe 获取流水线结构失败: {str(e)}")
        
        # 方法2: 如果没有获取到阶段信息，尝试从最后一次构建中获取
        if not pipeline_structure.get('stages'):
            try:
                api_url = f"{self.jenkins_url}/job/{job_path}/lastBuild/wfapi/describe"
                logger.info(f"尝试从最后一次构建中获取流水线结构: {api_url}")
                response = self._make_request("GET", api_url)
                if response and 'stages' in response:
                    pipeline_structure = response
                    logger.info(f"从最后一次构建中获取到阶段信息: {pipeline_structure}")
                    logger.info(f"从最后一次构建中获取到 {len(response.get('stages', []))} 个阶段")
            except Exception as e:
                logger.warning(f"从最后一次构建中获取流水线结构失败: {str(e)}")
        
        # 方法3: 如果仍然没有获取到阶段信息，尝试从 Blue Ocean API 获取
        if not pipeline_structure.get('stages'):
            try:
                # 获取最后一次构建编号
                job_info_url = f"{self.jenkins_url}/job/{job_path}/api/json"
                logger.info(f"尝试从 Blue Ocean API 获取流水线结构: {job_info_url}")
                job_info = self._make_request("GET", job_info_url)
                last_build_number = job_info.get('lastBuild', {}).get('number', 1)
                
                # 使用 Blue Ocean API
                blue_ocean_url = f"{self.jenkins_url}/blue/rest/organizations/jenkins/pipelines/{job_path.replace('job/', '')}/runs/{last_build_number}"
                blue_ocean_data = self._make_request("GET", blue_ocean_url)
                
                if blue_ocean_data:
                    # 转换 Blue Ocean 数据为流水线结构
                    pipeline_structure = {
                        'name': blue_ocean_data.get('name', ''),
                        'stages': []
                    }
                    
                    # 获取节点信息
                    nodes_url = f"{blue_ocean_url}/nodes"
                    nodes = self._make_request("GET", nodes_url)
                    
                    if nodes:
                        for node in nodes:
                            if node.get('type') == 'STAGE':
                                stage = {
                                    'name': node.get('displayName', ''),
                                    'steps': []
                                }
                                
                                # 获取阶段步骤
                                steps_url = f"{blue_ocean_url}/nodes/{node.get('id')}/steps"
                                steps_response = requests.get(steps_url, auth=self.auth, verify=False)
                                
                                if steps_response.status_code == 200:
                                    steps = steps_response.json()
                                    for step in steps:
                                        # 修改这一行，传递正确的参数
                                        log = self._get_step_log(blue_ocean_url, node.get('id'), step.get('id'))
                                        stage['steps'].append({
                                            'name': step.get('displayName', ''),
                                            'log': log
                                        })
                                
                                pipeline_structure['stages'].append(stage)
                        
                        logger.info(f"从 Blue Ocean API 获取到 {len(pipeline_structure.get('stages', []))} 个阶段")
            except Exception as e:
                logger.warning(f"从 Blue Ocean API 获取流水线结构失败: {str(e)}")
        
        # 方法4: 如果仍然没有获取到阶段信息，尝试从 config.xml 中获取 Jenkinsfile
        if not pipeline_structure.get('stages'):
            try:
                config_url = f"{self.jenkins_url}/job/{job_path}/config.xml"
                logger.info(f"尝试从 config.xml 获取 Jenkinsfile: {config_url}")
                config_xml = self._make_request("GET", config_url, as_json=False)
                
                if config_xml:
                    import xml.etree.ElementTree as ET
                    import tempfile
                    import os
                    
                    # 解析 XML
                    root = ET.fromstring(config_xml)
                    
                    # 查找 definition 元素
                    definition = root.find(".//definition")
                    if definition is not None:
                        # 查找 script 元素
                        script = definition.find(".//script")
                        if script is not None and script.text:
                            logger.info("从 config.xml 中提取到 Jenkinsfile 内容")
                            
                            # 将 Jenkinsfile 内容保存到临时文件
                            with tempfile.NamedTemporaryFile(suffix='.jenkinsfile', delete=False) as temp:
                                temp.write(script.text.encode('utf-8'))
                                temp_path = temp.name
                            
                            # 使用 Jenkinsfile 解析器解析流水线结构
                            from parsers.jenkins_file_parser import JenkinsfileParser
                            jenkinsfile_parser = JenkinsfileParser(temp_path)
                            jenkinsfile_model = jenkinsfile_parser.parse()
                            
                            # 将 Jenkinsfile 解析结果转换为流水线结构
                            jenkinsfile_dict = jenkinsfile_model.to_dict()
                            pipeline_structure['stages'] = jenkinsfile_dict.get('stages', [])
                            pipeline_structure['script'] = script.text
                            
                            # 删除临时文件
                            os.unlink(temp_path)
                            
                            logger.info(f"从 Jenkinsfile 中获取到 {len(pipeline_structure.get('stages', []))} 个阶段")
            except Exception as e:
                logger.warning(f"从 config.xml 获取 Jenkinsfile 失败: {str(e)}")
        
        # 方法5: 如果是 Freestyle 项目，尝试从构建步骤中提取信息
        if not pipeline_structure.get('stages'):
            try:
                job_config_url = f"{self.jenkins_url}/job/{job_path}/config.xml"
                job_config_response = requests.get(job_config_url, auth=self.auth, verify=False)
                
                if job_config_response.status_code == 200:
                    import xml.etree.ElementTree as ET
                    
                    # 解析 XML
                    root = ET.fromstring(job_config_response.content)
                    logger.info(f"检测到 Freestyle 项目,内容： {job_config_response.content} ")
                    # 检查是否是 Freestyle 项目
                    project_class = root.tag
                    if project_class == 'project':
                        logger.info("检测到 Freestyle 项目，尝试提取构建步骤")
                        pipeline_structure = {
                            'name': job_name,
                            '_class': 'FreeStyleProject',
                            'xml_content': '',
                            'git_url': '',
                            'stages': [{
                                'name': 'Build',
                                'steps': []
                            }]
                        }
                        # 提取Git URL
                        scm = root.find(".//scm[@class='hudson.plugins.git.GitSCM']")
                        if scm is not None:
                            url_element = scm.find(".//url")
                            if url_element is not None and url_element.text:
                                git_url = url_element.text
                                logger.info(f"从 Freestyle 项目中提取到 Git URL: {git_url}")
                                # 保存到pipeline_structure中
                                pipeline_structure['xml_content'] = job_config_response.content.decode('utf-8')
                                pipeline_structure['git_url'] = git_url
                        deploy = root.find(".//publishers")
                        logger.info(f"从 Freestyle 项目中提取到 Deploy: {deploy} ")
                        if deploy is not None:
                            # 创建部署阶段
                            deploy_stage = {
                                'name': 'Deploy',
                                'steps': []
                            }
                            # 提取 ssh 步骤
                            execCommands = deploy.findall(".//execCommand")
                            logger.info(f"从 Freestyle 项目中提取到 Deploy execCommands: {execCommands} ")
                            for execCommand in execCommands:
                                logger.info(f"从 Freestyle 项目中提取到 Deploy execCommand: {execCommand.text} ")
                                if execCommand is not None and execCommand.text:
                                    deploy_stage['steps'].append({
                                        'name': 'Deploy',
                                        'type': 'Deploy',
                                        'command': execCommand.text
                                    })
                        if deploy_stage['steps']:
                            pipeline_structure['stages'].append(deploy_stage)
                            logger.info(f"添加了 {len(deploy_stage['steps'])} 个部署步骤到 Deploy 阶段")
                        # 提取构建步骤
                        builders = root.find(".//builders")
                        if builders is not None:
                            # 提取 shell 步骤
                            for shell in builders.findall(".//hudson.tasks.Shell"):
                                command = shell.find("./command")
                                if command is not None and command.text:
                                    pipeline_structure['stages'][0]['steps'].append({
                                        'name': 'Shell',
                                        'type': 'sh',
                                        'command': command.text
                                    })
                            
                            # 提取 Maven 步骤
                            for maven in builders.findall(".//hudson.tasks.Maven"):
                                targets = maven.find("./targets")
                                if targets is not None and targets.text:
                                    pipeline_structure['stages'][0]['steps'].append({
                                        'name': 'Maven',
                                        'type': 'maven',
                                        'command': targets.text
                                    })
                            
                            logger.info(f"从 Freestyle 项目中提取到 {len(pipeline_structure['stages'][0]['steps'])} 个构建步骤")
            except Exception as e:
                logger.warning(f"从 Freestyle 项目提取构建步骤失败: {str(e)}")
        
        # 如果仍然没有获取到阶段信息，添加一个空的阶段结构
        if not pipeline_structure.get('stages'):
            pipeline_structure = {
                'name': job_path.split('/')[-1],
                'stages': []
            }
        
        # 获取参数信息
        try:
            job_info_url = f"{self.jenkins_url}/job/{job_path}/api/json?tree=property[parameterDefinitions[name,defaultValue,description]]"
            job_info = self._make_request("GET", job_info_url)
            logger.info(f"获取参数信息: {job_info}")
            if job_info and 'property' in job_info:
                parameters = []
                for prop in job_info['property']:
                    if 'parameterDefinitions' in prop:
                        for param in prop['parameterDefinitions']:
                            parameters.append({
                                'name': param.get('name', ''),
                                'default': param.get('defaultValue', ''),
                                'description': param.get('description', '')
                            })
                
                pipeline_structure['parameters'] = parameters
                logger.info(f"获取到 {len(parameters)} 个参数")
        except Exception as e:
            logger.warning(f"获取参数信息失败: {str(e)}")
        
        return pipeline_structure

    def _normalize_job_path(self, job_name):
        """
        规范化任务路径
        
        Args:
            job_name: Jenkins 任务名称
            
        Returns:
            str: 规范化后的任务路径
        """
        # 移除开头的斜杠
        if job_name.startswith('/'):
            job_name = job_name[1:]
        
        # 处理嵌套任务路径
        if '/job/' not in job_name:
            parts = job_name.split('/')
            job_path = '/job/'.join(parts)
        else:
            job_path = job_name
        
        return job_path

    def _make_request(self, method, url, data=None, as_json=True):
        """
        发送 HTTP 请求
        
        Args:
            method: HTTP 方法
            url: 请求 URL
            data: 请求数据
            as_json: 是否将响应解析为 JSON
            
        Returns:
            dict 或 str: 响应内容
        """
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        headers = {'Content-Type': 'application/json'}
        
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                auth=self.auth,  # 使用用户名和密码认证
                data=data,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            
            if as_json:
                return response.json()
            else:
                return response.text
        except Exception as e:
            logger.error(f"请求失败: {url}, 错误: {str(e)}")
            return None
    
    def _determine_step_type(self, step_name, step_log):
        """
        根据步骤名称和日志推断步骤类型
        
        Args:
            step_name: 步骤名称
            step_log: 步骤日志
            
        Returns:
            dict: 步骤类型信息
        """
        step_type = {"type": "unknown"}
        
        # 根据步骤名称推断类型
        if "Shell Script" in step_name:
            step_type = {
                "type": "sh",
                "command": self._extract_shell_command(step_log)
            }
        elif "Print Message" in step_name or "echo" in step_name.lower():
            step_type = {
                "type": "echo",
                "message": self._extract_echo_message(step_log)
            }
        elif "Check out" in step_name:
            step_type = {"type": "checkout"}
        elif "Maven" in step_name:
            step_type = {
                "type": "maven",
                "command": self._extract_maven_command(step_log)
            }
        
        return step_type
    
    def _extract_shell_command(self, log):
        """
        从日志中提取shell命令
        
        Args:
            log: 日志内容
            
        Returns:
            str: shell命令
        """
        # 如果日志包含HTML内容，则返回示例命令
        if log and (log.startswith('<!doctype') or log.startswith('<html') or '<head' in log):
            return "echo '执行Shell脚本...'\n# 请根据实际情况修改命令"
        
        # 尝试从日志中提取命令
        if log:
            # 简单处理：取日志的前几行作为命令
            lines = log.split('\n')
            command_lines = []
            for line in lines[:5]:  # 最多取前5行
                line = line.strip()
                if line and not line.startswith('+') and not line.startswith('#'):
                    command_lines.append(line)
            
            if command_lines:
                return '\n'.join(command_lines)
        
        return "echo '执行Shell脚本...'\n# 请根据实际情况修改命令"
    
    def _extract_echo_message(self, log):
        """
        从日志中提取echo消息
        
        Args:
            log: 日志内容
            
        Returns:
            str: echo消息
        """
        if log:
            # 简单处理：取日志的第一行作为消息
            return log.split('\n')[0].strip()
        
        return "构建信息"
    
    def _extract_maven_command(self, log):
        """
        从日志中提取Maven命令
        
        Args:
            log: 日志内容
            
        Returns:
            str: Maven命令
        """
        if log:
            # 尝试从日志中提取Maven命令
            import re
            maven_cmd = re.search(r'mvn\s+([^"\'\n]+)', log)
            if maven_cmd:
                return maven_cmd.group(1)
        
        return "clean package -Dmaven.test.skip=true"
    
    def get_job_parameters(self, job_path):
        """
        获取 Job 参数
        
        Args:
            job_path: Job 路径
            
        Returns:
            list: 参数列表
        """
        parameters = []
        
        try:
            # 构建 API URL
            api_url = f"{self.jenkins_url}/job/{job_path}/api/json?tree=property[parameterDefinitions[name,defaultParameterValue[value],description,type]]"
            
            # 发送请求
            response = requests.get(api_url, auth=self.auth)
            
            # 检查响应状态
            if response.status_code != 200:
                logger.error(f"获取 Job 参数失败: {response.status_code} - {response.text}")
                return parameters
            
            # 解析响应
            job_data = response.json()
            
            # 提取参数
            for prop in job_data.get('property', []):
                if 'parameterDefinitions' in prop:
                    for param in prop['parameterDefinitions']:
                        param_info = {
                            'name': param.get('name', ''),
                            'default': param.get('defaultParameterValue', {}).get('value', ''),
                            'description': param.get('description', ''),
                            'type': param.get('type', '')
                        }
                        parameters.append(param_info)
            
            return parameters
        
        except Exception as e:
            logger.error(f"获取 Job 参数时发生错误: {str(e)}")
            return parameters
            
    def get_job_info(self, job_name):
        """
        获取 Job 信息
        
        Args:
            job_name: Job 名称
            
        Returns:
            dict: Job 信息
        """
        url = f"{self.jenkins_url}/job/{job_name}/api/json?pretty=true&depth=1"
        logger.info(f"获取 Job 信息: {url}")
        
        try:
            response = requests.get(url, auth=self.auth)
            response.raise_for_status()
            job_info = response.json()
            
            # 检查作业类型
            job_class = job_info.get('_class', '')
            logger.info(f"作业类型: {job_class}")
            
            # 如果是 Freestyle 项目，获取更多信息
            if 'FreeStyleProject' in job_class:
                logger.info("检测到 Freestyle 项目，获取更多信息")
                # 获取构建步骤信息
                if 'builds' in job_info and job_info['builds']:
                    last_build = job_info['builds'][0]
                    if 'number' in last_build:
                        build_number = last_build['number']
                        build_info = self.get_build_info(job_name, build_number)
                        if build_info:
                            # 合并构建信息
                            job_info['lastBuildInfo'] = build_info
            
            return job_info
        except Exception as e:
            logger.error(f"获取 Job 信息失败: {str(e)}")
            return None