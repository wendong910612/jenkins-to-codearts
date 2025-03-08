#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Jenkins迁移工具主程序
将Jenkins流水线转换为华为CodeArts流水线
支持从Jenkinsfile文件或Jenkins API获取流水线信息
"""

import os
import sys
import argparse
import json
from parsers.jenkins_file_parser import JenkinsfileParser
from parsers.jenkins_api_parser import JenkinsApiParser
from converters.codearts_converter import CodeArtsConverter
from converters.build_converter import BuildTaskConverter
from api.jenkins_client import JenkinsClient
from utils.logger import logger
from models.pipeline_model import PipelineModel  # 添加导入PipelineModel
from converters.codearts_build_converter import CodeArtsBuildConverter

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Jenkins迁移到华为CodeArts工具')
    
    # 创建互斥组，用户必须选择其中一种方式
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--jenkinsfile', '-j', help='Jenkinsfile路径')
    source_group.add_argument('--jenkins-api', '-a', action='store_true', help='使用Jenkins API获取Job信息')
    
    # Jenkins API相关参数
    parser.add_argument('--jenkins-url', '-u', help='Jenkins服务器URL')
    parser.add_argument('--job-name', '-n', help='Jenkins Job名称')
    parser.add_argument('--username', help='Jenkins用户名')
    parser.add_argument('--password', help='Jenkins密码')
    parser.add_argument('--api-token', help='Jenkins API Token (可选，优先使用)')
    
    # 输出相关参数
    parser.add_argument('--output', '-o', default='codearts_pipeline.yaml', help='输出的CodeArts YAML文件路径')
    parser.add_argument('--build-output', '-b', default='codearts_build.yaml', help='输出的CodeArts构建任务YAML文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细日志')
    parser.add_argument('--build-only', action='store_true', help='仅生成构建任务')
    # 添加导出流水线结构参数
    parser.add_argument('--export-structure', '-e', help='导出Jenkins流水线结构到指定文件')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel('DEBUG')
    
    # 检查参数
    if args.jenkins_api and not (args.jenkins_url and args.job_name):
        logger.error("使用Jenkins API时必须指定Jenkins服务器URL和Job名称")
        parser.print_help()
        sys.exit(1)
    
    try:
        pipeline_model = None
        
        # 根据参数选择解析方式
        if args.jenkinsfile:
            from converters.codearts_build_converter import CodeArtsBuildConverter
            # 解析Jenkinsfile
            logger.info(f"开始解析Jenkinsfile: {args.jenkinsfile}")
            jenkinsfile_parser = JenkinsfileParser(args.jenkinsfile)
            
            pipeline_model = jenkinsfile_parser.parse()
            logger.info("Jenkinsfile解析完成")
            
            # 导出解析后的流水线模型，便于调试
            with open("jenkins_pipeline_model.json", 'w', encoding='utf-8') as f:
                json.dump(pipeline_model.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info("解析后的流水线模型已导出到: jenkins_pipeline_model.json")
            
            # 生成构建任务
            # logger.info(f"开始生成构建任务: {args.build_output}")
            # build_converter = BuildTaskConverter(build_steps=pipeline_model, output_path=args.build_output, pipeline_stages=pipeline_model)
            # if build_converter.convert():
            #     logger.info(f"成功生成CodeArts构建任务: {args.build_output}")
            # else:
            #     logger.error("生成CodeArts构建任务失败")
            
            # # 生成构建任务
            # build_converter = BuildTaskConverter(build_steps=None, output_path=args.build_output, pipeline_stages=pipeline_model)
            # if build_converter.convert():
            #     logger.info(f"成功生成CodeArts构建任务: {args.build_output}")
            # else:
            #     logger.error("生成CodeArts构建任务失败")
            # 转换为CodeArts YAML
            converter = CodeArtsConverter(pipeline_model, args.output)
            if converter.convert():
                logger.info(f"成功生成CodeArts YAML: {args.output}")
            else:
                logger.error("生成CodeArts YAML失败")
            
                # 如果指定了构建任务输出路径，转换为CodeArts构建任务YAML
                if args.build_output:
                    build_converter = CodeArtsBuildConverter(pipeline_model, args.build_output)
                    build_success = build_converter.convert()
                    if build_success:
                        logger.info(f"成功生成CodeArts构建任务YAML: {args.build_output}")
                    else:
                        logger.error("生成CodeArts构建任务YAML失败")
        else:
            # 在 main.py 中找到处理 Jenkins API 的部分，大约在第 65 行左右
            # 在导入部分添加
            from converters.codearts_build_converter import CodeArtsBuildConverter
            
            # 在处理 Jenkins API 的部分修改为
            if args.jenkins_api:
                logger.info(f"从Jenkins API解析: {args.jenkins_url}/job/{args.job_name}")
                jenkins_client = JenkinsClient(args.jenkins_url, args.username, args.password, args.api_token)
                pipeline_structure = jenkins_client.get_pipeline_structure(args.job_name)
                logger.info(f"解析完成: {args.jenkins_url}/job/{args.job_name}")
                
                # 导出流水线结构
                if args.export_structure:
                    with open(args.export_structure, 'w', encoding='utf-8') as f:
                        json.dump(pipeline_structure, f, indent=2, ensure_ascii=False)
                    logger.info(f"流水线结构已导出到: {args.export_structure}")
                
                # 解析流水线结构
                logger.info("开始解析 Jenkins API 获取的流水线结构")
                jenkins_api_parser = JenkinsApiParser(pipeline_structure)
                pipeline_model = jenkins_api_parser.parse()
                
                # 导出解析后的流水线模型
                with open("jenkins_pipeline_model.json", 'w', encoding='utf-8') as f:
                    json.dump(pipeline_model.to_dict(), f, indent=2, ensure_ascii=False)
                logger.info("解析后的流水线模型已导出到: jenkins_pipeline_model.json")
                
                # 转换为CodeArts YAML
                converter = CodeArtsConverter(pipeline_model, args.output)
                if converter.convert():
                    logger.info(f"成功生成CodeArts YAML: {args.output}")
                else:
                    logger.error("生成CodeArts YAML失败")
                
                # 如果指定了构建任务输出路径，转换为CodeArts构建任务YAML
                if args.build_output:
                    build_converter = CodeArtsBuildConverter(pipeline_model, args.build_output)
                    build_success = build_converter.convert()
                    if build_success:
                        logger.info(f"成功生成CodeArts构建任务YAML: {args.build_output}")
                    else:
                        logger.error("生成CodeArts构建任务YAML失败")
                
                # 不要再调用 BuildTaskConverter
                return
        
        # 导出解析后的流水线模型，便于调试
        with open("jenkins_pipeline_model.json", 'w', encoding='utf-8') as f:
            json.dump(pipeline_model.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("解析后的流水线模型已导出到: jenkins_pipeline_model.json")
        
        # 生成构建任务
        build_converter = BuildTaskConverter(pipeline_model, args.build_output)
        build_result = build_converter.convert()
        
        if build_result:
            logger.info(f"构建任务已生成: {args.build_output}")
        else:
            logger.error("生成构建任务失败")
            sys.exit(1)
        
        # 如果只需要生成构建任务，则退出
        if args.build_only:
            logger.info("仅生成构建任务，任务完成")
            sys.exit(0)
        
        # 生成完整流水线
        # 转换为CodeArts YAML
        converter = CodeArtsConverter(pipeline_model, args.output)
        success = converter.convert()
        
        # 如果指定了构建任务输出路径，转换为CodeArts构建任务YAML
        if args.build_output:
            build_converter = CodeArtsBuildConverter(pipeline_model, args.build_output)
            build_success = build_converter.convert()
            if build_success:
                logger.info(f"成功生成CodeArts构建任务YAML: {args.build_output}")
            else:
                logger.error("生成CodeArts构建任务YAML失败")
        
        # 找到最后一行包含 pipeline_result 的代码，修改为：
        try:
            # 这里应该使用 success 变量而不是 pipeline_result
            if success:
                logger.info(f"CodeArts流水线已生成: {args.output}")
                sys.exit(0)
            else:
                logger.error("生成CodeArts流水线失败")
                sys.exit(1)
        except Exception as e:
            logger.error(f"发生错误: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()