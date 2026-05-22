"""LLM code generation utilities for admin server."""

import logging
import os

from admin.llm_api import _call_llm_api
from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


def _validate_generated_scraper(name: str, code: str) -> tuple:
    """验证生成的爬虫代码：编译 → 安全 → 加载 → 执行 → 结果检查.

    Returns:
        (success: bool, error_msg: str, project_count: int)
    """
    # Step 1: Syntax check
    try:
        compile(code, f"<validate_{name}>", "exec")
    except SyntaxError as e:
        return False, f"语法错误: {e}", 0

    # Step 2: Security check
    from admin.security import _validate_source_code

    is_valid, error_msg = _validate_source_code(code)
    if not is_valid:
        return False, f"安全校验失败: {error_msg}", 0

    # Step 3: Load and register
    from admin.security import load_custom_source

    success, msg = load_custom_source(name, code)
    if not success:
        return False, f"加载失败: {msg}", 0

    # Step 4: Instantiate and scrape (capture HTTP response for debugging)
    from scraper.sources import SOURCE_REGISTRY

    source_class = SOURCE_REGISTRY.get(name)
    if not source_class:
        return False, "注册后未找到 Source 类", 0

    captured_responses = []

    import requests as _requests

    _original_get = _requests.get

    def _capture_get(url, *args, **kwargs):
        resp = _original_get(url, *args, **kwargs)
        captured_responses.append((url, resp.status_code, resp.text[:5000]))
        return resp

    _requests.get = _capture_get
    try:
        instance = source_class(priority=10)
        projects = instance.scrape()
    except Exception as e:
        _requests.get = _original_get
        return False, f"执行 scrape() 异常: {e}", 0
    finally:
        _requests.get = _original_get

    # Step 5: Check results
    if not projects or len(projects) == 0:
        page_info = ""
        if captured_responses:
            url, status, body = captured_responses[0]
            page_info = (
                f"\n请求 URL: {url}\nHTTP 状态码: {status}\n"
                f"页面 HTML 片段 (前 5000 字符):\n{body}"
            )
        return (
            False,
            f"scrape() 返回空列表（HTTP 请求成功但 XPath 未匹配到元素）{page_info}",
            0,
        )

    return True, "", len(projects)


def generate_source_code(name: str, description: str, extra_prompt: str = "") -> str:
    """Generate Python source code for a scraper using LLM."""
    try:
        logger.info(f"Starting code generation for {name}")
    except OSError:
        pass

    try:
        store = SQLiteStore()
    except OSError as e:
        raise Exception(f"无法打开数据库: {str(e)}")

    provider = store.get_setting("llm_provider", "openai").strip()
    api_key = (store.get_setting("llm_api_key") or "").strip()
    base_url = (store.get_setting("llm_base_url", "") or "").strip()
    model = (store.get_setting("llm_model", "") or "").strip()

    _gen_timeout_str = store.get_setting("llm_generate_timeout", "")
    GENERATE_TIMEOUT = int(_gen_timeout_str) if _gen_timeout_str else 600

    _mt_str = store.get_setting("llm_max_tokens", "")
    MAX_TOKENS = int(_mt_str) if _mt_str else None

    _is_reasoning = model and any(
        kw in model.lower() for kw in ["deepseek-r", "deepseek-v4", "o1", "o3", "o4"]
    )

    api_timeout = GENERATE_TIMEOUT if _is_reasoning else min(GENERATE_TIMEOUT, 300)

    if MAX_TOKENS:
        gen_max_tokens = MAX_TOKENS
    elif _is_reasoning:
        gen_max_tokens = 8000
    else:
        gen_max_tokens = 4000

    if not api_key:
        api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
        )

    if not api_key:
        raise Exception("未配置 LLM API Key")

    system_prompt = """你是爬虫代码生成专家。你必须在生成的代码中严格遵守以下项目框架规范。

## 项目框架规范

### 1. 数据模型 UnifiedProject（必须使用）
所有采集到的新项目必须构建为 UnifiedProject 实例，字段如下：
```python
@dataclass
class UnifiedProject:
    source: str          # 数据源标识（使用数据源名称）
    project_name: str    # 项目名称/标题
    project_url: str     # 项目链接 URL
    description: str     # 项目描述
    author: str          # 作者/发布者
    stars: int           # 热度/点赞数（非负整数）
    forks: int           # 派生/评论数（非负整数）
    language: str        # 编程语言或文档语言
    category: str        # 分类标签（如 "trending", "hot", "new", "article" 等）
    scraped_at: datetime  # 采集时间（使用 datetime.now()）
```

### 2. 基类 BaseSource（必须继承并实现 scrape 方法）
```python
class BaseSource(ABC):
    def __init__(self, name: str, priority: int = 10):
        self.name = name
        self.priority = priority

    @abstractmethod
    def scrape(self) -> List[UnifiedProject]:
        pass
```

### 3. 注册装饰器 @register_source（必须使用）
```python
@register_source("数据源名称")
class YourSource(BaseSource):
    ...
```

### 4. 必须的导入语句
```python
from typing import List
from datetime import datetime
import requests
from lxml import html
from scraper.sources.base import BaseSource
from scraper.sources.models import UnifiedProject
from scraper.sources import register_source
```
禁止使用 re 模块解析 HTML，必须使用 lxml.html + XPath。

### 5. 代码结构模板（必须使用 XPath 解析）
```python
@register_source("{name}")
class {ClassName}Source(BaseSource):
    def __init__(self, priority: int = 10):
        super().__init__("{name}", priority)

    def scrape(self) -> List[UnifiedProject]:
        projects = []
        resp = requests.get("目标URL", timeout=30)
        resp.raise_for_status()
        tree = html.fromstring(resp.content)

        # 使用 XPath 选取列表项
        items = tree.xpath('//div[@class="item"]')
        for item in items[:30]:
            # 提取标题: text() 获取元素文本
            title_el = item.xpath('.//h2/a')
            title = title_el[0].text_content().strip() if title_el else ""

            # 提取链接: @href 获取属性
            link_el = item.xpath('.//h2/a/@href')
            link = link_el[0] if link_el else ""

            # 提取数字: text() 后 int() 转换
            stars_el = item.xpath('.//span[@class="stars"]/text()')
            stars = int(stars_el[0].replace(",", "")) if stars_el else 0

            # 提取作者/描述等其他字段同理
            author_el = item.xpath('.//span[@class="author"]/text()')
            author = author_el[0].strip() if author_el else ""

            desc_el = item.xpath('.//p[@class="desc"]/text()')
            description = desc_el[0].strip() if desc_el else ""

            projects.append(UnifiedProject(
                source=self.name,
                project_name=title,
                project_url=link,
                description=description,
                author=author,
                stars=stars,
                forks=0,
                language="",
                category="article",
                scraped_at=datetime.now(),
            ))
        return projects
```

### 6. XPath 解析规则（强制）
- HTML 解析必须使用 lxml.html.fromstring() + XPath，严禁使用 re 正则解析 HTML
- 获取元素文本: xpath('.//tag/text()') 或 xpath('.//tag')[0].text_content()
- 获取属性值: xpath('.//tag/@attr')
- 获取所有匹配元素: xpath('//div[@class="item"]') 返回列表
- 条件过滤: xpath('//div[contains(@class, "item")]')
- 检查元素是否存在后再访问，缺失时使用空字符串 "" 或 0
- 数字字段 (stars, forks) 必须先 replace(",", "") 再 int() 转换

### 7. 重要规则
- 必须使用 @register_source 装饰器注册数据源
- 类名必须以 "Source" 结尾
- scrape() 方法必须返回 List[UnifiedProject]
- 每个 UnifiedProject 都必须设置 source 字段为数据源名称
- 所有数字字段 (stars, forks) 必须是整数，缺失时填 0
- 所有字符串字段缺失时填空字符串 ""
- 不要包含 markdown 代码块标记（```）
- 只输出纯 Python 代码"""

    base_user_prompt = f"""请生成数据源爬虫代码。

数据源名称: {name}
功能描述: {description}
{extra_prompt}

按照上述框架规范生成完整的 Python 爬虫代码。关键要素：
1. 使用 @register_source("{name}") 注册
2. 继承 BaseSource 并实现 scrape() 方法
3. 必须使用 lxml.html + XPath 解析 HTML，禁止使用 re 正则
4. 将页面列表中的每项内容映射到 UnifiedProject 对应字段
5. 确保 stars/forks 字段为整数，缺失填 0
6. 只输出纯 Python 代码，不要包含 ``` 标记"""

    max_attempts = 5
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Generation attempt {attempt}/{max_attempts} for {name}")

        if attempt == 1:
            current_prompt = base_user_prompt
        else:
            if "空列表" in last_error or "未采集到" in last_error:
                fix_hint = """XPath 选择器未匹配到任何元素。请根据上方错误信息中附带的「页面 HTML 片段」分析实际页面结构，修正 XPath：
1. 对照 HTML 片段中的实际标签和 class 名称重写选择器
2. class 名称不精确 → 使用 contains(@class, '关键词') 模糊匹配
3. 层级路径不对 → 先用 //div 宽泛选取再逐步筛选
4. 目标元素的 class 中有空格（如 "item active"），用 contains 匹配"""
            else:
                fix_hint = "请根据错误信息修复代码中的问题。"

            current_prompt = f"""上一版生成的代码验证失败，错误信息：
{last_error}

{fix_hint}

请修复以上问题，重新生成完整的 Python 爬虫代码。严格遵循框架规范，确保代码可以正常执行并采集到数据。

{base_user_prompt}"""

        # --- LLM call (same for both providers) ---
        if provider == "anthropic":
            endpoint = (base_url or "https://api.anthropic.com") + "/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            payload = {
                "model": model or "claude-sonnet-4-20250514",
                "max_tokens": gen_max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": current_prompt}],
            }
            response = _call_llm_api(endpoint, headers, payload, timeout=api_timeout)
            result = response.json()
            code = ""
            for block in result.get("content", []):
                if block.get("type") == "text":
                    code = block.get("text", "")
                    break

        else:
            endpoint = (base_url or "https://api.openai.com/v1") + "/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            payload = {
                "model": model or "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": gen_max_tokens,
            }
            response = _call_llm_api(endpoint, headers, payload, timeout=api_timeout)
            result = response.json()
            code = result["choices"][0]["message"].get("content", "")

        # Extract code from markdown
        if "```python" in code:
            start = code.find("```python") + 8
            end = code.find("```", start)
            code = code[start:end].strip()
        elif "```" in code:
            start = code.find("```") + 3
            end = code.find("```", start)
            code = code[start:end].strip()

        # --- Validate generated code ---
        success, error_msg, count = _validate_generated_scraper(name, code)

        # Clean up registry after validation
        from scraper.sources import SOURCE_REGISTRY

        if name in SOURCE_REGISTRY:
            del SOURCE_REGISTRY[name]

        if success:
            logger.info(f"Validation passed on attempt {attempt}: {count} projects")
            return code

        last_error = error_msg
        logger.warning(
            f"Validation failed (attempt {attempt}/{max_attempts}): {error_msg}"
        )

    logger.error(f"All {max_attempts} attempts failed for {name}: {last_error}")
    raise Exception(
        f"代码生成验证失败（{max_attempts} 次重试后仍未通过）: {last_error}"
    )
