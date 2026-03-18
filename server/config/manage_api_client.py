import os
import base64
from typing import Optional, Dict

import httpx

TAG = __name__


class DeviceNotFoundException(Exception):
    pass


class DeviceBindException(Exception):
    def __init__(self, bind_code):
        self.bind_code = bind_code
        super().__init__(f"Lỗi ràng buộc thiết bị, mã ràng buộc: {bind_code}")


class ManageApiClient:
    _instance = None
    _async_clients = {}  # Lưu trữ máy khách độc lập cho mỗi vòng lặp sự kiện
    _secret = None

    def __new__(cls, config):
        """Chế độ Singleton đảm bảo một phiên bản duy nhất toàn cục và hỗ trợ truyền các tham số cấu hình"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._init_client(config)
        return cls._instance

    @classmethod
    def _init_client(cls, config):
        """Khởi tạo cấu hình (trì hoãn việc tạo máy khách)"""
        cls.config = config.get("manager-api")

        if not cls.config:
            raise Exception("Lỗi cấu hình manager-api")

        if not cls.config.get("url") or not cls.config.get("secret"):
            raise Exception("Lỗi cấu hình url hoặc secret của manager-api")

        if "Bạn" in cls.config.get("secret") or "你" in cls.config.get("secret"):
            raise Exception("Vui lòng cấu hình secret của manager-api trước")

        cls._secret = cls.config.get("secret")
        cls.max_retries = cls.config.get("max_retries", 6)  # Số lần thử lại tối đa
        cls.retry_delay = cls.config.get("retry_delay", 10)  # Độ trễ thử lại ban đầu (giây)
        # Không tạo AsyncClient ở đây, trì hoãn việc tạo cho đến khi thực tế sử dụng
        cls._async_clients = {}

    @classmethod
    async def _ensure_async_client(cls):
        """Đảm bảo máy khách không đồng bộ đã được tạo (tạo máy khách độc lập cho mỗi vòng lặp sự kiện)"""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)

            # Cho mỗi vòng lặp sự kiện tạo máy khách độc lập
            if loop_id not in cls._async_clients:
                # Máy chủ có thể chủ động đóng kết nối, nhóm kết nối httpx không thể phát hiện và dọn dẹp chính xác
                limits = httpx.Limits(
                    max_keepalive_connections=0,  # Tắt keep-alive, luôn tạo kết nối mới mỗi lần
                )
                cls._async_clients[loop_id] = httpx.AsyncClient(
                    base_url=cls.config.get("url"),
                    headers={
                        "User-Agent": f"PythonClient/2.0 (PID:{os.getpid()})",
                        "Accept": "application/json",
                        "Authorization": "Bearer " + cls._secret,
                    },
                    timeout=cls.config.get("timeout", 30),
                    limits=limits,  # Sử dụng các giới hạn
                )
            return cls._async_clients[loop_id]
        except RuntimeError:
            # Nếu không có vòng lặp sự kiện đang chạy, hãy tạo một vòng lặp tạm thời
            raise Exception("Phải được gọi trong ngữ cảnh không đồng bộ")

    @classmethod
    async def _async_request(cls, method: str, endpoint: str, **kwargs) -> Dict:
        """Gửi một yêu cầu HTTP không đồng bộ duy nhất và xử lý phản hồi"""
        # Đảm bảo máy khách đã được tạo
        client = await cls._ensure_async_client()
        endpoint = endpoint.lstrip("/")
        response = None
        try:
            response = await client.request(method, endpoint, **kwargs)
            response.raise_for_status()

            result = response.json()

            # Xử lý các lỗi nghiệp vụ do API trả về
            if result.get("code") == 10041:
                raise DeviceNotFoundException(result.get("msg"))
            elif result.get("code") == 10042:
                raise DeviceBindException(result.get("msg"))
            elif result.get("code") != 0:
                raise Exception(f"API trả về lỗi: {result.get('msg', 'Lỗi không xác định')}")

            # Trả về dữ liệu thành công
            return result.get("data") if result.get("code") == 0 else None
        finally:
            # Đảm bảo phản hồi đã được đóng (ngay cả khi xảy ra ngoại lệ)
            if response is not None:
                await response.aclose()

    @classmethod
    def _should_retry(cls, exception: Exception) -> bool:
        """Xác định xem ngoại lệ có nên được thử lại hay không"""
        # Các lỗi liên quan đến kết nối mạng
        if isinstance(
            exception, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)
        ):
            return True

        # Lỗi mã trạng thái HTTP
        if isinstance(exception, httpx.HTTPStatusError):
            status_code = exception.response.status_code
            return status_code in [408, 429, 500, 502, 503, 504]

        return False

    @classmethod
    async def _execute_async_request(cls, method: str, endpoint: str, **kwargs) -> Dict:
        """Bộ thực thi yêu cầu không đồng bộ với cơ chế thử lại"""
        import asyncio

        retry_count = 0

        while retry_count <= cls.max_retries:
            try:
                # Thực hiện yêu cầu không đồng bộ
                return await cls._async_request(method, endpoint, **kwargs)
            except Exception as e:
                # Xác định xem có nên thử lại không
                if retry_count < cls.max_retries and cls._should_retry(e):
                    retry_count += 1
                    print(
                        f"{method} {endpoint} yêu cầu không đồng bộ thất bại, sẽ thực hiện thử lại lần thứ {retry_count} sau {cls.retry_delay:.1f} giây"
                    )
                    await asyncio.sleep(cls.retry_delay)
                    continue
                else:
                    # Không thử lại, trực tiếp ném ra ngoại lệ
                    raise

    @classmethod
    def safe_close(cls):
        """Đóng an toàn tất cả các nhóm kết nối không đồng bộ"""
        import asyncio

        for client in list(cls._async_clients.values()):
            try:
                asyncio.run(client.aclose())
            except Exception:
                pass
        cls._async_clients.clear()
        cls._instance = None


async def get_server_config() -> Optional[Dict]:
    """Lấy cấu hình cơ bản của máy chủ"""
    return await ManageApiClient._instance._execute_async_request(
        "POST", "/config/server-base"
    )


async def get_agent_models(
    mac_address: str, client_id: str, selected_module: Dict
) -> Optional[Dict]:
    """Lấy cấu hình mô hình tác nhân (agent models)"""
    return await ManageApiClient._instance._execute_async_request(
        "POST",
        "/config/agent-models",
        json={
            "macAddress": mac_address,
            "clientId": client_id,
            "selectedModule": selected_module,
        },
    )


async def generate_and_save_chat_summary(session_id: str) -> Optional[Dict]:
    """Tạo và lưu bản tóm tắt lịch sử trò chuyện"""
    try:
        return await ManageApiClient._instance._execute_async_request(
            "POST",
            f"/agent/chat-summary/{session_id}/save",
        )
    except Exception as e:
        print(f"Tạo và lưu bản tóm tắt lịch sử trò chuyện thất bại: {e}")
        return None


async def report(
    mac_address: str, session_id: str, chat_type: int, content: str, audio, report_time
) -> Optional[Dict]:
    """Báo cáo lịch sử trò chuyện không đồng bộ"""
    if not content or not ManageApiClient._instance:
        return None
    try:
        return await ManageApiClient._instance._execute_async_request(
            "POST",
            f"/agent/chat-history/report",
            json={
                "macAddress": mac_address,
                "sessionId": session_id,
                "chatType": chat_type,
                "content": content,
                "reportTime": report_time,
                "audioBase64": (
                    base64.b64encode(audio).decode("utf-8") if audio else None
                ),
            },
        )
    except Exception as e:
        print(f"Báo cáo TTS thất bại: {e}")
        return None


def init_service(config):
    ManageApiClient(config)


def manage_api_http_safe_close():
    ManageApiClient.safe_close()
