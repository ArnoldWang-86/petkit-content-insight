# -*- coding: utf-8 -*-
"""analysis 包的入口：把中文文件名映射成可 import 的模块名

Python 无法直接 import 以数字开头的模块名（如 01_产品线），
所以这里用 importlib 按文件路径加载，对外暴露简洁的名字。
"""
import importlib.util
import os

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load(filename):
    path = os.path.join(_DIR, filename)
    spec = importlib.util.spec_from_file_location(filename[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


产品线模块 = _load("01_产品线.py")
品牌模块 = _load("02_品牌声量.py")
痛点模块 = _load("03_用户痛点.py")
内容策略模块 = _load("04_内容策略.py")
场景模块 = _load("05_场景与内容.py")
