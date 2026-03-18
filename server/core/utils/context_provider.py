import httpx
from typing import Dict, Any, List
from config.logger import setup_logging

TAG = __name__

class ContextDataProvider:
    """Điền dữ liệu ngữ cảnh, chịu trách nhiệm lấy dữ liệu từ các API đã cấu hình"""
    
    def __init__(self, config: Dict[str, Any], logger=None):
        self.config = config
        self.logger = logger or setup_logging()
        self.context_data = ""

    def fetch_all(self, device_id: str) -> str:
        """Lấy tất cả các dữ liệu ngữ cảnh đã cấu hình"""
        context_providers = self.config.get("context_providers", [])
        if not context_providers:
            return ""

        formatted_lines = []
        for provider in context_providers:
            url = provider.get("url")
            headers = provider.get("headers", {})

            if not url:
                continue

            try:
                headers = headers.copy() if isinstance(headers, dict) else {}
                # Thêm device_id vào tiêu đề (headers) yêu cầu
                headers["device-id"] = device_id
                
                # Gửi yêu cầu
                response = httpx.get(url, headers=headers, timeout=3)
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, dict):
                        if result.get("code") == 0:
                            data = result.get("data")
                            # Định dạng dữ liệu
                            if isinstance(data, dict):
                                for k, v in data.items():
                                    formatted_lines.append(f"- **{k}:** {v}")
                            elif isinstance(data, list):
                                for item in data:
                                    formatted_lines.append(f"- {item}")
                            else:
                                formatted_lines.append(f"- {data}")
                        else:
                            self.logger.bind(tag=TAG).warning(f"API {url} trả về mã lỗi: {result.get('msg')}")
                    else:
                        self.logger.bind(tag=TAG).warning(f"API {url} không trả về một từ điển JSON")
                else:
                    self.logger.bind(tag=TAG).warning(f"Yêu cầu API {url} thất bại: {response.status_code}")
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"Lấy dữ liệu ngữ cảnh {url} thất bại: {e}")
        
        # Nối tất cả các dòng đã định dạng thành một chuỗi
        self.context_data = "\n".join(formatted_lines)
        if self.context_data:
            self.logger.bind(tag=TAG).debug(f"Đã chèn dữ liệu ngữ cảnh động:\n{self.context_data}")
        return self.context_data
