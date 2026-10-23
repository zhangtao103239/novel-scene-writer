"""硅基流动 (SiliconFlow) 极简客户端 —— 纯标准库，零依赖。

参数与错误码依据官方文档：
https://api-docs.siliconflow.cn/docs/api/chat-completions-post

要点：
- 鉴权头 Authorization: Bearer <API Key>
- 可选追踪头 X-Trace-Id / traceparent，响应头 x-siliconcloud-trace-id
- max_tokens 不包含思维链部分；流式以 data: [DONE] 结束
- 支持 top_k / min_p(Qwen3 专用) / stop(最多4条) / n / response_format
- 429 = TPM 限流，503(code 50505) = 模型过载，均可退避重试
"""
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
ENV_KEY = "SILICONFLOW_API_KEY"
RETRY_STATUS = {429, 500, 502, 503, 504}


class ApiError(RuntimeError):
    def __init__(self, msg, status=None, code=None, trace_id=None):
        super().__init__(msg)
        self.status = status
        self.code = code
        self.trace_id = trace_id


def get_api_key() -> str:
    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        raise ApiError(
            f"环境变量 {ENV_KEY} 未设置。\n"
            f"Windows 永久设置: powershell -NoProfile -Command \"[Environment]::SetEnvironmentVariable('{ENV_KEY}','sk-xxx','User')\"\n"
            f"Linux/macOS:     export {ENV_KEY}=sk-xxx   # 建议写进 ~/.bashrc 或 ~/.zshrc\n"
            f"设置后需要重开终端才会生效。"
        )
    return key


def _explain(status, body, trace_id):
    """把官方错误码翻译成可操作的提示。"""
    code = None
    msg = body
    try:
        obj = json.loads(body)
        if isinstance(obj, dict):
            code = obj.get("code")
            msg = obj.get("message") or obj.get("error") or body
    except (json.JSONDecodeError, TypeError):
        pass

    hint = {
        400: "请求参数有误（检查 model 是否存在、参数取值范围）",
        401: "鉴权失败：API Key 无效或已失效（code 20012）",
        403: "无权限：该模型可能需实名/充值，或不在你的可用列表内",
        404: "路径或模型不存在",
        429: "触发 TPM/RPM 限流，请降低并发或稍后重试",
        503: "模型服务过载，稍后重试（code 50505）",
        504: "上游超时，可减小 max_tokens 或分批写作",
    }.get(status, "")

    parts = [f"HTTP {status}"]
    if code is not None:
        parts.append(f"code={code}")
    if msg:
        parts.append(str(msg)[:400])
    if hint:
        parts.append("→ " + hint)
    if trace_id:
        parts.append(f"trace={trace_id}")
    return " | ".join(parts), code


def _request(path, payload=None, stream=False, timeout=300, retries=3, trace_id=None):
    url = BASE_URL.rstrip("/") + path
    headers = {"Authorization": "Bearer " + get_api_key()}
    if trace_id:
        headers["X-Trace-Id"] = trace_id
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            tid = e.headers.get("x-siliconcloud-trace-id") if e.headers else None
            text, code = _explain(e.code, raw, tid)
            last = ApiError(text, e.code, code, tid)
            if e.code in RETRY_STATUS and attempt < retries:
                wait = 2 ** (attempt + 1) + random.random()
                ra = e.headers.get("Retry-After") if e.headers else None
                if ra and ra.isdigit():
                    wait = max(wait, int(ra))
                print(f"[重试 {attempt + 1}/{retries}] {text}，{wait:.1f}s 后再试", file=sys.stderr)
                time.sleep(wait)
                continue
            raise last from None
        except urllib.error.URLError as e:
            last = ApiError(f"网络错误: {e}")
            if attempt < retries:
                wait = 2 ** (attempt + 1)
                print(f"[重试 {attempt + 1}/{retries}] {last}，{wait}s 后再试", file=sys.stderr)
                time.sleep(wait)
                continue
            raise last from None
    raise last or ApiError("未知错误")


def _build_payload(messages, model, temperature, top_p, max_tokens, stream,
                   frequency_penalty, presence_penalty, stop, top_k,
                   response_format, n, seed, enable_thinking, thinking_budget):
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "frequency_penalty": frequency_penalty,
    }
    if presence_penalty:
        payload["presence_penalty"] = presence_penalty
    if stop:
        payload["stop"] = stop if isinstance(stop, list) else [stop]
        payload["stop"] = payload["stop"][:4]     # 文档：最多 4 个停止序列
    if top_k is not None:
        payload["top_k"] = top_k                    # 文档：0 < value <= 100
    if n and n > 1:
        payload["n"] = n
    if response_format:
        payload["response_format"] = response_format
    if seed is not None:
        payload["seed"] = seed
    if enable_thinking is not None:
        payload["enable_thinking"] = enable_thinking
    if thinking_budget is not None:
        payload["thinking_budget"] = max(128, min(32768, int(thinking_budget)))
    return payload


def chat(messages, model, temperature=0.85, top_p=0.9, max_tokens=4096,
         frequency_penalty=0.0, presence_penalty=0.0,
         stop=None, top_k=None, response_format=None, n=1, seed=None,
         enable_thinking=None, thinking_budget=None, trace_id=None):
    """非流式调用，返回 (text, finish_reason, usage)。"""
    payload = _build_payload(messages, model, temperature, top_p, max_tokens, False,
                             frequency_penalty, presence_penalty, stop, top_k,
                             response_format, n, seed, enable_thinking, thinking_budget)
    resp = _request("/chat/completions", payload, trace_id=trace_id)
    with resp:
        data = json.loads(resp.read().decode("utf-8"))
    choice = data["choices"][0]
    msg = choice.get("message", {})
    # 推理模型可能把内容放在 reasoning_content 里而 content 为空
    text = msg.get("content") or ""
    if not text.strip():
        text = msg.get("reasoning_content") or ""
    return text, choice.get("finish_reason"), data.get("usage", {})


def chat_stream(messages, model, temperature=0.85, top_p=0.9, max_tokens=4096,
                frequency_penalty=0.0, presence_penalty=0.0,
                stop=None, top_k=None, response_format=None, seed=None,
                enable_thinking=None, thinking_budget=None, trace_id=None):
    """流式调用（SSE），逐块 yield 正文文本增量；思维链增量被跳过。"""
    payload = _build_payload(messages, model, temperature, top_p, max_tokens, True,
                             frequency_penalty, presence_penalty, stop, top_k,
                             response_format, 1, seed, enable_thinking, thinking_budget)
    resp = _request("/chat/completions", payload, stream=True, trace_id=trace_id)
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if chunk == "[DONE]":
                break
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            for ch in obj.get("choices", []):
                delta = ch.get("delta", {})
                piece = delta.get("content")
                if piece:
                    yield piece


def list_models(sub_type="chat"):
    resp = _request(f"/models?sub_type={sub_type}")
    with resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m["id"] for m in data.get("data", [])]


def reconfigure_stdout():
    """Windows 控制台默认 GBK，强制 UTF-8 输出避免中文乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
