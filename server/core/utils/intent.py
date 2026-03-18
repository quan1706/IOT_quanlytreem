import os
import sys
from config.logger import setup_logging
import importlib

logger = setup_logging()


def create_instance(class_name, *args, **kwargs):
    # Tạo phiên bản intent
    if os.path.exists(os.path.join('core', 'providers', 'intent', class_name, f'{class_name}.py')):
        lib_name = f'core.providers.intent.{class_name}.{class_name}'
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(f'{lib_name}')
        return sys.modules[lib_name].IntentProvider(*args, **kwargs)

    raise ValueError(f"Loại intent không được hỗ trợ: {class_name}, vui lòng kiểm tra xem type của cấu hình đã được thiết lập đúng chưa")