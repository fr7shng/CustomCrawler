"""Security utilities for custom source validation and loading."""

import ast
import builtins
import sys
import types

from scraper.sources import SOURCE_REGISTRY, register_source
from scraper.sources.base import BaseSource

# Dangerous modules/builtins that will be blocked
BLOCKED_BUILTINS = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "file",
    "input",
    "print",
    "reload",
    "zipimport",
    "__builtins__",
}

BLOCKED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "requests.exceptions",
    "ctypes",
    "cffi",
    "pickle",
    "marshal",
    "importlib",
    "pkgutil",
    "zipfile",
    "pathlib",
    "tempfile",
    "shutil",
    "threading",
    "multiprocessing",
    "concurrent",
    "gc",
    "builtins",
}


def _validate_source_code(source_code: str) -> tuple:
    """
    Validate source code using AST to ensure safety.
    Returns (is_valid, error_message)
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return False, f"语法错误: {e}"

    dangerous_found = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in BLOCKED_MODULES or any(
                    alias.name.startswith(f"{m}.") for m in BLOCKED_MODULES
                ):
                    dangerous_found.append(f"禁止的模块导入: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            if node.module and (
                node.module in BLOCKED_MODULES
                or any(node.module.startswith(f"{m}.") for m in BLOCKED_MODULES)
            ):
                dangerous_found.append(f"禁止的模块导入: {node.module}")

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "__import__"}:
                    dangerous_found.append(f"禁止的函数调用: {node.func.id}")
                elif node.func.id == "compile":
                    dangerous_found.append("禁止的函数调用: compile")

        elif isinstance(node, ast.Attribute):
            if node.attr in {
                "__dict__",
                "__class__",
                "__globals__",
                "__code__",
                "__closure__",
                "__globals__",
                "__import__",
            }:
                dangerous_found.append(f"禁止的属性访问: {node.attr}")

    if dangerous_found:
        return False, "; ".join(dangerous_found[:3])

    return True, ""


def _create_safe_globals(module_name: str) -> dict:
    """Create a safe globals dictionary for restricted execution."""
    import datetime
    import json
    import re
    from typing import List

    from scraper.sources.models import UnifiedProject

    safe_base = types.ModuleType("scraper.sources.base")
    safe_base.BaseSource = BaseSource

    safe_models = types.ModuleType("scraper.sources.models")
    safe_models.UnifiedProject = UnifiedProject

    safe_sources = types.ModuleType("scraper.sources")
    safe_sources.BaseSource = BaseSource
    safe_sources.UnifiedProject = UnifiedProject
    safe_sources.register_source = register_source
    safe_sources.SOURCE_REGISTRY = SOURCE_REGISTRY

    safe_scraper = types.ModuleType("scraper")
    safe_scraper.sources = safe_sources

    safe_builtins = {
        k: v
        for k, v in builtins.__dict__.items()
        if k
        not in {
            "eval",
            "exec",
            "compile",
            "open",
            "input",
            "__import__",
            "exit",
            "quit",
            "help",
            "credits",
            "copyright",
            "license",
        }
    }
    # Allow __import__ for from...import statements
    safe_builtins["__import__"] = __import__
    # Inject extra non-builtin items needed by scraper code
    safe_builtins.update(
        {
            "datetime": datetime,
            "json": json,
            "re": re,
            "List": List,
        }
    )

    safe_globals = {
        "__name__": module_name,
        "__builtins__": safe_builtins,
        "types": types,
        "requests": __import__("requests"),
        "datetime": datetime,
        "json": json,
        "re": re,
        "lxml": __import__("lxml"),
        "lxml.html": __import__("lxml.html"),
        "typing": __import__("typing"),
        "scraper": safe_scraper,
        "scraper.sources": safe_sources,
        "scraper.sources.base": safe_base,
        "scraper.sources.models": safe_models,
        "BaseSource": BaseSource,
        "UnifiedProject": UnifiedProject,
        "register_source": register_source,
    }

    return safe_globals


def load_custom_source(name: str, source_code: str) -> tuple:
    """
    Safely load a custom source into SOURCE_REGISTRY with AST validation.
    """
    is_valid, error_msg = _validate_source_code(source_code)
    if not is_valid:
        return False, f"代码安全验证失败: {error_msg}"

    try:
        module = types.ModuleType(f"custom_{name}")
        safe_globals = _create_safe_globals(f"custom_{name}")
        safe_globals["__name__"] = f"custom_{name}"

        import lxml as _lxml_mod
        import lxml.html as _lxml_html_mod

        mock_modules = {
            "scraper": safe_globals["scraper"],
            "scraper.sources": safe_globals["scraper.sources"],
            "scraper.sources.base": safe_globals["scraper.sources.base"],
            "scraper.sources.models": safe_globals["scraper.sources.models"],
            "lxml": _lxml_mod,
            "lxml.html": _lxml_html_mod,
        }
        original_modules = {}
        for mod_name, mod_obj in mock_modules.items():
            original_modules[mod_name] = sys.modules.get(mod_name)
            sys.modules[mod_name] = mod_obj

        try:
            compiled = compile(source_code, f"<custom_source_{name}>", "exec")
            exec(compiled, safe_globals)
        finally:
            for mod_name in mock_modules:
                if original_modules[mod_name] is not None:
                    sys.modules[mod_name] = original_modules[mod_name]
                else:
                    sys.modules.pop(mod_name, None)

        module.__dict__.update(safe_globals)
        module.__dict__["__builtins__"] = safe_globals["__builtins__"]

        for item_name in dir(module):
            item = getattr(module, item_name)
            if (
                isinstance(item, type)
                and issubclass(item, BaseSource)
                and item is not BaseSource
            ):
                SOURCE_REGISTRY[name] = item
                return True, f"已注册为 {name}"

        return False, "未找到继承 BaseSource 的类"
    except SyntaxError as e:
        return False, f"语法错误: {e}"
    except Exception as e:
        return False, str(e)
