"""Trình quản lý MCP phía Server"""

import asyncio
import os
import json
from typing import Dict, Any, List

from mcp.types import LoggingMessageNotificationParams

from config.config_loader import get_project_dir
from config.logger import setup_logging
from .mcp_client import ServerMCPClient

TAG = __name__
logger = setup_logging()


class ServerMCPManager:
    """Trình quản lý tập trung các dịch vụ MCP phía Server"""

    def __init__(self, conn) -> None:
        """Khởi tạo trình quản lý MCP"""
        self.conn = conn
        self.config_path = get_project_dir() + "data/.mcp_server_settings.json"
        if not os.path.exists(self.config_path):
            self.config_path = ""
            logger.bind(tag=TAG).warning(
                f"Vui lòng kiểm tra tệp cấu hình dịch vụ MCP: data/.mcp_server_settings.json"
            )
        self.clients: Dict[str, ServerMCPClient] = {}
        self.tools = []
        self._init_lock = asyncio.Lock()

    def load_config(self) -> Dict[str, Any]:
        """Tải cấu hình dịch vụ MCP"""
        if len(self.config_path) == 0:
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("mcpServers", {})
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"Error loading MCP config from {self.config_path}: {e}"
            )
            return {}

    async def _init_server(self, name: str, srv_config: Dict[str, Any]):
        """Khởi tạo một dịch vụ MCP đơn lẻ"""
        client = None
        try:
            # 初始化服务端MCP客户端
            logger.bind(tag=TAG).info(f"Khởi tạo client MCP phía Server: {name}")
            client = ServerMCPClient(srv_config)
            # 设置超时时间10秒
            await asyncio.wait_for(client.initialize(logging_callback=self.logging_callback), timeout=10)

            # 使用锁保护共享状态的修改
            async with self._init_lock:
                self.clients[name] = client
                client_tools = client.get_available_tools()
                self.tools.extend(client_tools)

        except asyncio.TimeoutError:
            logger.bind(tag=TAG).error(
                f"Failed to initialize MCP server {name}: Timeout"
            )
            if client:
                await client.cleanup()
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"Failed to initialize MCP server {name}: {e}"
            )
            if client:
                await client.cleanup()

    async def initialize_servers(self) -> None:
        """Khởi tạo tất cả dịch vụ MCP"""
        config = self.load_config()
        tasks = []
        for name, srv_config in config.items():
            if not srv_config.get("command") and not srv_config.get("url"):
                logger.bind(tag=TAG).warning(
                    f"Skipping server {name}: neither command nor url specified"
                )
                continue
            
            tasks.append(self._init_server(name, srv_config))
        
        if tasks:
            await asyncio.gather(*tasks)

        # Tránh log trùng lặp vì UnifiedToolHandler đã in danh sách này
        pass

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Lấy định nghĩa hàm công cụ của tất cả dịch vụ"""
        return self.tools

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Kiểm tra xem có phải công cụ MCP không"""
        for tool in self.tools:
            if (
                tool.get("function") is not None
                and tool["function"].get("name") == tool_name
            ):
                return True
        return False

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Thực thi gọi công cụ, sẽ thử lại nếu thất bại"""
        logger.bind(tag=TAG).info(f"Thực thi công cụ MCP phía Server {tool_name}, tham số: {arguments}")

        max_retries = 3  # 最大重试次数
        retry_interval = 2  # 重试间隔(秒)

        # 找到对应的客户端
        client_name = None
        target_client = None
        for name, client in self.clients.items():
            if client.has_tool(tool_name):
                client_name = name
                target_client = client
                break

        if not target_client:
            raise ValueError(f"Công cụ {tool_name} không tìm thấy trong bất kỳ dịch vụ MCP nào")

        # 带重试机制的工具调用
        for attempt in range(max_retries):
            try:
                return await target_client.call_tool(tool_name, arguments, progress_callback=self.progress_callback)
            except Exception as e:
                # 最后一次尝试失败时直接抛出异常
                if attempt == max_retries - 1:
                    raise

                logger.bind(tag=TAG).warning(
                    f"执行工具 {tool_name} 失败 (尝试 {attempt+1}/{max_retries}): {e}"
                )

                # 尝试重新连接
                logger.bind(tag=TAG).info(
                    f"Thử kết nối lại client MCP {client_name} trước khi chạy lại"
                )
                try:
                    # 关闭旧的连接
                    await target_client.cleanup()

                    # 重新初始化客户端
                    config = self.load_config()
                    if client_name in config:
                        client = ServerMCPClient(config[client_name])
                        await client.initialize(logging_callback=self.logging_callback)
                        self.clients[client_name] = client
                        target_client = client
                        logger.bind(tag=TAG).info(
                            f"Kết nối lại thành công client MCP: {client_name}"
                        )
                    else:
                        logger.bind(tag=TAG).error(
                            f"Cannot reconnect MCP client {client_name}: config not found"
                        )
                except Exception as reconnect_error:
                    logger.bind(tag=TAG).error(
                        f"Failed to reconnect MCP client {client_name}: {reconnect_error}"
                    )

                # 等待一段时间再重试
                await asyncio.sleep(retry_interval)

    async def cleanup_all(self) -> None:
        """Đóng tất cả client MCP"""
        for name, client in list(self.clients.items()):
            try:
                if hasattr(client, "cleanup"):
                    await asyncio.wait_for(client.cleanup(), timeout=20)
                logger.bind(tag=TAG).info(f"Client MCP phía Server đã đóng: {name}")
            except (asyncio.TimeoutError, Exception) as e:
                logger.bind(tag=TAG).error(f"关闭服务端MCP客户端 {name} 时出错: {e}")
        self.clients.clear()

    # 可选回调方法

    async def logging_callback(self, params: LoggingMessageNotificationParams):
        logger.bind(tag=TAG).info(f"[Server Log - {params.level.upper()}] {params.data}")

    async def progress_callback(self, progress: float, total: float | None, message: str | None) -> None:
        logger.bind(tag=TAG).info(f"[Progress {progress}/{total}]: {message}")