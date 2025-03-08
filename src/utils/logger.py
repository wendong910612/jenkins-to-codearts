#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志工具模块
"""

import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('jenkins-to-codearts')

def setLevel(level):
    """设置日志级别"""
    logger.setLevel(getattr(logging, level))