"""AI API 调用处理"""
import httpx
import json
import time
from typing import Optional, Dict, Any, AsyncGenerator
from datetime import datetime
from models import ModelConfig, APIType


class APIHandler:
    def __init__(self):
        self.timeout = 60.0

    async def test_connection(self, config: ModelConfig) -> Dict[str, Any]:
        """测试API连接"""
        try:
            if config.api_type == APIType.OPENAI:
                return await self._test_openai(config)
            elif config.api_type == APIType.CLAUDE:
                return await self._test_claude(config)
            elif config.api_type == APIType.OLLAMA:
                return await self._test_ollama(config)
            elif config.api_type == APIType.QWEN:
                return await self._test_qwen(config)
            else:
                return await self._test_openai(config)
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_openai(self, config: ModelConfig) -> Dict[str, Any]:
        """测试OpenAI API"""
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": config.model_name,
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 5
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                return {"success": True, "message": "连接成功"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

    async def _test_claude(self, config: ModelConfig) -> Dict[str, Any]:
        """测试Claude API"""
        headers = {
            "x-api-key": config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": config.model_name,
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 5
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/messages",
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                return {"success": True, "message": "连接成功"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

    async def _test_ollama(self, config: ModelConfig) -> Dict[str, Any]:
        """测试Ollama API"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{config.base_url.rstrip('/')}/api/tags")

            if response.status_code == 200:
                return {"success": True, "message": "连接成功"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

    async def _test_qwen(self, config: ModelConfig) -> Dict[str, Any]:
        """测试Qwen API"""
        return await self._test_openai(config)

    async def chat(
        self,
        config: ModelConfig,
        messages: list,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送聊天请求"""
        try:
            if config.api_type == APIType.OPENAI:
                return await self._chat_openai(config, messages, system_prompt)
            elif config.api_type == APIType.CLAUDE:
                return await self._chat_claude(config, messages, system_prompt)
            elif config.api_type == APIType.OLLAMA:
                return await self._chat_ollama(config, messages, system_prompt)
            elif config.api_type == APIType.QWEN:
                return await self._chat_qwen(config, messages, system_prompt)
            else:
                return await self._chat_openai(config, messages, system_prompt)
        except Exception as e:
            return {"success": False, "error": str(e), "content": "", "tokens": 0}

    async def _chat_openai(
        self,
        config: ModelConfig,
        messages: list,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """OpenAI Chat API"""
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": config.model_name,
            "messages": full_messages,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                return {"success": True, "content": content, "tokens": tokens}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}", "content": "", "tokens": 0}

    async def _chat_claude(
        self,
        config: ModelConfig,
        messages: list,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Claude API"""
        headers = {
            "x-api-key": config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": config.model_name,
            "messages": full_messages,
            "max_tokens": 4096
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/messages",
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                content = data["content"][0]["text"]
                tokens = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
                return {"success": True, "content": content, "tokens": tokens}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}", "content": "", "tokens": 0}

    async def _chat_ollama(
        self,
        config: ModelConfig,
        messages: list,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ollama API"""
        full_messages = messages
        if system_prompt:
            full_messages = [{"role": "system", "content": system_prompt}] + messages

        payload = {
            "model": config.model_name,
            "messages": full_messages,
            "stream": False
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/api/chat",
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                content = data["message"]["content"]
                tokens = data.get("eval_count", 0)
                return {"success": True, "content": content, "tokens": tokens}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}", "content": "", "tokens": 0}

    async def _chat_qwen(
        self,
        config: ModelConfig,
        messages: list,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Qwen API (兼容OpenAI格式)"""
        return await self._chat_openai(config, messages, system_prompt)


api_handler = APIHandler()
