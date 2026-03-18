import os
import sys

# Thêm thư mục gốc của dự án vào đường dẫn Python
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
sys.path.insert(0, project_root)

from config.logger import setup_logging
import importlib

logger = setup_logging()


def create_instance(class_name, *args, **kwargs):
    # Tạo phiên bản LLM
    if os.path.exists(os.path.join('core', 'providers', 'llm', class_name, f'{class_name}.py')):
        lib_name = f'core.providers.llm.{class_name}.{class_name}'
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(f'{lib_name}')
        return sys.modules[lib_name].LLMProvider(*args, **kwargs)

    raise ValueError(f"Loại LLM không được hỗ trợ: {class_name}, vui lòng kiểm tra xem type của cấu hình đã được thiết lập đúng chưa")
