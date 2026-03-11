import aiohttp
import json
import asyncio
from config.logger import setup_logging

TAG = "AIProvider"

class AIProvider:
    """
    Cung cấp giao diện chung để gọi các mô hình LLM (Groq, OpenAI, etc.).
    Tránh việc hardcode endpoint và logic gọi API ở nhiều nơi.
    """
    
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    DEFAULT_URL = "https://api.groq.com/openai/v1/chat/completions"

    @staticmethod
    async def call_llm(api_key, messages, model=None, response_format=None, max_tokens=500, timeout=15):
        """
        Thực hiện gọi LLM API.
        messages: list[dict] - Danh sách tin nhắn.
        response_format: dict - {"type": "json_object"} hoặc None.
        """
        if not api_key:
            return None, "Missing API Key"

        url = AIProvider.DEFAULT_URL
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model or AIProvider.DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": max_tokens
        }
        
        if response_format:
            payload["response_format"] = response_format

        logger = setup_logging()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"].strip()
                        return content, None
                    else:
                        error_text = await response.text()
                        logger.bind(tag=TAG).error(f"API Error: {response.status} - {error_text}")
                        return None, f"API Error {response.status}"
        except asyncio.TimeoutError:
            logger.bind(tag=TAG).error("Request timed out")
            return None, "Timeout"
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi khi gọi AI: {e}")
            return None, str(e)
