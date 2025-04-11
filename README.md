# Jenkins 到 CodeArts 迁移工具

这个工具用于将 Jenkins 流水线转换为华为云 CodeArts 流水线，支持从 Jenkinsfile 文件或 Jenkins API 获取流水线信息。

## 功能特点

- 支持从 Jenkinsfile 文件解析流水线结构
- 支持通过 Jenkins API 获取 Job 信息
- 生成 CodeArts 流水线配置文件 (codearts_pipeline.yaml)
- 生成 CodeArts 构建任务配置文件 (codearts_build.yaml)
- 支持多种构建工具 (Maven, Gradle, NPM, Docker)

## 环境要求
- Python 3.6+

## 目录结构

```plaintext
jenkins-to-codearts/
├── README.md # 项目说明文档
├── codearts_build.yaml # 生成的 CodeArts 构建任务配置示例
├── codearts_pipeline.yaml # 生成的 CodeArts 流水线配置示例
├── example/ # 示例文件
│ ├── Jenkinsfile # 示例 Jenkinsfile
│ └── double_cloud_java_k8s_deploy.groovy # 示例 Jenkins 流水线脚本
├── jenkins_pipeline_model.json # Jenkins 流水线模型 JSON 示例
├── jenkins_pipeline_structure.json # Jenkins 流水线结构 JSON 示例
├── src/ # 源代码目录
│ ├── api/ # API 相关模块
│ │ └── jenkins_client.py # Jenkins API 客户端
│ ├── config/ # 配置文件目录
│ │ ├── build_mapping.yaml # 构建步骤映射配置
│ │ └── pipeline_mapping.yaml # 流水线步骤映射配置
│ ├── converters/ # 转换器模块
│ │ ├── init.py
│ │ ├── build_converter.py # 构建任务转换器
│ │ └── codearts_converter.py # CodeArts 流水线转换器
│ ├── main.py # 主程序入口
│ ├── models/ # 数据模型
│ │ └── pipeline_model.py # 流水线数据模型
│ ├── parsers/ # 解析器模块
│ │ ├── init.py
│ │ ├── base_parser.py # 解析器基类
│ │ ├── jenkins_api_parser.py # Jenkins API 解析器
│ │ └── jenkins_file_parser.py # Jenkinsfile 解析器
│ ├── templates/ # 模板文件目录
│ │ ├── build.yaml # 构建步骤模板
│ │ ├── build/ # 构建任务模板
│ │ │ └── codearts_build.yaml # CodeArts 构建任务模板
│ │ ├── code_check.yaml # 代码检查步骤模板
│ │ ├── deploy.yaml # 部署步骤模板
│ │ ├── shell.yaml # Shell 步骤模板
│ │ └── test_plan.yaml # 测试计划步骤模板
│ └── utils/ # 工具模块
│ ├── init.py
│ ├── config_loader.py # 配置加载工具
│ ├── logger.py # 日志工具
│ └── template_loader.py # 模板加载工具
└── tests/ # 测试目录
```

## 安装依赖

pip install -r requirements.txt

## 使用方法

### 从 Jenkinsfile 文件生成
python3 src/main.py -j example/Jenkinsfile -o codearts_pipeline.yaml -b codearts_build.yaml

### 从 Jenkins API 获取 Job 信息生成
python3 src/main.py -a -u http://127.0.0.1:8080 -n "shopping" --username jenkins --password 'jenkins' -e jenkins_pipeline_structure.json -o codearts_pipeline.yaml -b codearts_build.yaml

python3 src/main.py -a -u http://127.0.0.1:8080 -n "shopping-jenkinsfile" --username jenkins --password 'jenkins' -e jenkins_pipeline_structure.json -o codearts_pipeline.yaml -b codearts_build.yaml
