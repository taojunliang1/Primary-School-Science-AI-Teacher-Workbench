import logging
from typing import Annotated, Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, StringConstraints, model_validator

log = logging.getLogger(__name__)

MODELS = {"science": "deepseek-flash", "general": "deepseek-v4-pro"}
SYSTEM_PROMPT = (
    "你是小学科学教师的教学助手。用中文回答，语言适合教师和小学生。"
    "可用 Markdown、表格及 LaTeX 表达，设计实验时指出必要的安全注意事项。"
    "对未经核实的数据说明局限。需要题目、学生答卷或附件内容时，请用户粘贴相关文本。"
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=24000)]


class ChatRequest(BaseModel):
    model: Literal["science", "general"] = "science"
    messages: Annotated[list[ChatMessage], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def check_context(self):
        if self.messages[-1].role != "user" or sum(len(message.content) for message in self.messages) > 48000:
            raise ValueError("需要以用户消息结束，且上下文不能超过 48000 字符")
        return self


class ChatReply(BaseModel):
    model: str
    text: str


async def complete_chat(payload: ChatRequest, key: str) -> ChatReply:
    if not key:
        raise HTTPException(503, "DeepSeek 尚未配置，请在后端设置 API 密钥")
    model = MODELS[payload.model]
    try:
        # Use a direct, certificate-verified connection to the fixed provider endpoint.
        async with httpx.AsyncClient(timeout=httpx.Timeout(70, connect=10), trust_env=False) as client:
            response = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *(message.model_dump() for message in payload.messages),
                    ],
                    "thinking": {"type": "disabled"},
                    "max_tokens": 1536,
                    "stream": False,
                },
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "DeepSeek 响应超时，请稍后重试") from exc
    except httpx.RequestError as exc:
        log.warning("DeepSeek connection failed (%s)", type(exc).__name__)
        raise HTTPException(502, "后端暂时无法连接 DeepSeek，请检查网络") from exc

    if response.is_error:
        log.warning("DeepSeek returned HTTP %s", response.status_code)
        known_errors = {
            401: (503, "DeepSeek 拒绝了后端密钥，请检查密钥是否有效"),
            402: (402, "DeepSeek 账户余额不足，请检查账户余额"),
            403: (503, "DeepSeek 拒绝访问，请检查密钥权限"),
            429: (429, "DeepSeek 请求过多，请稍后重试"),
        }
        status, detail = known_errors.get(response.status_code, (502, "DeepSeek 暂时无法完成请求，请稍后重试"))
        raise HTTPException(status, detail)

    try:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty reply")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(502, "DeepSeek 未返回可显示的回复，请重试") from exc
    return ChatReply(model=result.get("model") or model, text=content.strip())
