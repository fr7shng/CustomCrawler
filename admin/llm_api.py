"""LLM API helper with retry logic."""

import time

import requests


def _call_llm_api(url, headers, payload=None, timeout=180, json=None, max_retries=3):
    """Make an LLM API request with friendly error messages and retry logic."""
    body = json if json is not None else payload
    retryable_statuses = {429, 502, 503, 504}

    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=body, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            last_error = Exception(
                f"LLM API 请求超时 ({timeout}s)，请检查网络或更换更快的 API"
            )
        except requests.exceptions.ConnectionError:
            last_error = Exception(
                f"无法连接到 LLM API ({url})，请检查 Base URL 是否正确、网络是否通畅"
            )
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status == 401:
                raise Exception("API Key 无效或已过期，请在设置页面更新 API Key")
            elif status == 402:
                raise Exception("API Key 余额不足，请充值或更换 Key")
            elif status in retryable_statuses:
                last_error = Exception(
                    f"LLM API 返回 {status} 错误（第{attempt + 1}次尝试），"
                    f"将自动重试..."
                )
            else:
                raise Exception(
                    f"LLM API 返回错误 (HTTP {status}): "
                    f"{e.response.text[:500] if e.response else '无响应'}"
                )
        except requests.exceptions.RequestException as e:
            last_error = Exception(
                f"LLM API 请求失败 ({type(e).__name__}): {str(e)[:300]}"
            )
        except OSError as e:
            last_error = Exception(
                f"LLM API 系统错误 ({url[:80]}): {str(e)}。"
                f"Windows 常见原因: 代理配置问题、防火墙阻止、Base URL 格式错误"
            )

        if attempt < max_retries - 1:
            wait = 2**attempt
            time.sleep(wait)

    raise last_error or Exception("LLM API 请求失败（未知原因）")
