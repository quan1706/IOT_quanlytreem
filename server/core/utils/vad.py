import importlib
import os
import sys
from core.providers.vad.base import VADProviderBase
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


def create_instance(class_name: str, *args, **kwargs) -> VADProviderBase:
    """Phương thức nhà máy để tạo phiên bản VAD (Factory Method)"""
    if os.path.exists(os.path.join("core", "providers", "vad", f"{class_name}.py")):
        lib_name = f"core.providers.vad.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(f"{lib_name}")
        return sys.modules[lib_name].VADProvider(*args, **kwargs)

    raise ValueError(f"Loại VAD không được hỗ trợ: {class_name}, vui lòng kiểm tra xem type của cấu hình đã được thiết lập đúng chưa")
