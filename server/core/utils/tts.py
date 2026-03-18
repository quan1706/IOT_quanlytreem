import os
import re
import sys
import importlib

from config.logger import setup_logging
from core.utils.textUtils import check_emoji

logger = setup_logging()

punctuation_set = {
    "，",
    ",",  # Dấu phẩy tiếng Trung + Dấu phẩy tiếng Anh
    "。",
    ".",  # Dấu chấm tiếng Trung + Dấu chấm tiếng Anh
    "！",
    "!",  # Dấu chấm than tiếng Trung + Dấu chấm than tiếng Anh
    "“",
    "”",
    '"',  # Dấu ngoặc kép tiếng Trung + Dấu ngoặc kép tiếng Anh
    "：",
    ":",  # Dấu hai chấm tiếng Trung + Dấu hai chấm tiếng Anh
    "-",
    "－",  # Dấu gạch nối tiếng Anh + Dấu gạch ngang toàn chiều rộng tiếng Trung
    "、",  # Dấu phẩy liệt kê tiếng Trung
    "[",
    "]",  # Dấu ngoặc vuông
    "【",
    "】",  # Dấu ngoặc vuông tiếng Trung
    "~",  # Dấu ngã
}

def create_instance(class_name, *args, **kwargs):
    # Tạo phiên bản TTS
    if os.path.exists(os.path.join('core', 'providers', 'tts', f'{class_name}.py')):
        lib_name = f'core.providers.tts.{class_name}'
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(f'{lib_name}')
        return sys.modules[lib_name].TTSProvider(*args, **kwargs)

    raise ValueError(f"Loại TTS không được hỗ trợ: {class_name}, vui lòng kiểm tra xem type của cấu hình đã được thiết lập đúng chưa")


class MarkdownCleaner:
    """
    Đóng gói logic làm sạch Markdown: chỉ cần sử dụng MarkdownCleaner.clean_markdown(text)
    """
    # Ký tự công thức
    NORMAL_FORMULA_CHARS = re.compile(r'[a-zA-Z\\^_{}\+\-\(\)\[\]=]')

    @staticmethod
    def _replace_inline_dollar(m: re.Match) -> str:
        """
        Chỉ cần bắt được phần "$...$" hoàn chỉnh:
          - Nếu bên trong có các ký tự công thức điển hình => xóa dấu $ ở hai bên
          - Ngược lại (chỉ số/tiền tệ, v.v.) => giữ nguyên "$...$"
        """
        content = m.group(1)
        if MarkdownCleaner.NORMAL_FORMULA_CHARS.search(content):
            return content
        else:
            return m.group(0)

    @staticmethod
    def _replace_table_block(match: re.Match) -> str:
        """
        Gọi lại hàm này khi khớp với một khối bảng nguyên đoạn.
        """
        block_text = match.group('table_block')
        lines = block_text.strip('\n').split('\n')

        parsed_table = []
        for line in lines:
            line_stripped = line.strip()
            if re.match(r'^\|\s*[-:]+\s*(\|\s*[-:]+\s*)+\|?$', line_stripped):
                continue
            columns = [col.strip() for col in line_stripped.split('|') if col.strip() != '']
            if columns:
                parsed_table.append(columns)

        if not parsed_table:
            return ""

        headers = parsed_table[0]
        data_rows = parsed_table[1:] if len(parsed_table) > 1 else []

        lines_for_tts = []
        if len(parsed_table) == 1:
            # Chỉ có một dòng
            only_line_str = ", ".join(parsed_table[0])
            lines_for_tts.append(f"Bảng một dòng: {only_line_str}")
        else:
            lines_for_tts.append(f"Tiêu đề bảng là: {', '.join(headers)}")
            for i, row in enumerate(data_rows, start=1):
                row_str_list = []
                for col_index, cell_val in enumerate(row):
                    if col_index < len(headers):
                        row_str_list.append(f"{headers[col_index]} = {cell_val}")
                    else:
                        row_str_list.append(cell_val)
                lines_for_tts.append(f"Dòng thứ {i}: {', '.join(row_str_list)}")

        return "\n".join(lines_for_tts) + "\n"
 
    # Biên dịch trước tất cả các biểu thức chính quy (sắp xếp theo tần suất thực thi)
    # Ở đây các phương thức tĩnh replace_xxx phải được định nghĩa trước để có thể tham chiếu đúng trong danh sách.
    REGEXES = [
        (re.compile(r'```.*?```', re.DOTALL), ''),  # Khối mã
        (re.compile(r'^#+\s*', re.MULTILINE), ''),  # Tiêu đề
        (re.compile(r'(\*\*|__)(.*?)\1'), r'\2'),  # Chữ đậm
        (re.compile(r'(\*|_)(?=\S)(.*?)(?<=\S)\1'), r'\2'),  # Chữ nghiêng
        (re.compile(r'!\[.*?\]\(.*?\)'), ''),  # Hình ảnh
        (re.compile(r'\[(.*?)\]\(.*?\)'), r'\1'),  # Liên kết
        (re.compile(r'^\s*>+\s*', re.MULTILINE), ''),  # Trích dẫn
        (
            re.compile(r'(?P<table_block>(?:^[^\n]*\|[^\n]*\n)+)', re.MULTILINE),
            _replace_table_block
        ),
        (re.compile(r'^\s*[*+-]\s*', re.MULTILINE), '- '),  # Danh sách
        (re.compile(r'\$\$.*?\$\$', re.DOTALL), ''),  # Công thức cấp khối
        (
            re.compile(r'(?<![A-Za-z0-9])\$([^\n$]+)\$(?![A-Za-z0-9])'),
            _replace_inline_dollar
        ),
        (re.compile(r'\n{2,}'), '\n'),  # Dòng trống dư thừa
    ]

    @staticmethod
    def clean_markdown(text: str) -> str:
        """
        Phương thức lối vào chính: thực hiện tuần tự tất cả các biểu thức chính quy, xóa hoặc thay thế các phần tử Markdown
        """
        # Kiểm tra xem văn bản có hoàn toàn là tiếng Anh và các dấu câu cơ bản không
        if text and all((c.isascii() or c.isspace() or c in punctuation_set) for c in text):
            # Giữ nguyên khoảng trắng ban đầu, trả về trực tiếp
            return text

        for regex, replacement in MarkdownCleaner.REGEXES:
            text = regex.sub(replacement, text)

        # Xóa biểu tượng cảm xúc (emoji)
        text = check_emoji(text)

        return text.strip()

def convert_percentage_to_range(percentage, min_val, max_val, base_val=None):
    """
    Chuyển đổi phần trăm (-100~100) sang giá trị trong phạm vi chỉ định

    Args:
        percentage: Giá trị phần trăm (-100 đến 100)
        min_val: Giá trị tối thiểu của phạm vi mục tiêu
        max_val: Giá trị tối đa của phạm vi mục tiêu
        base_val: Giá trị cơ sở (tùy chọn, mặc định là trung điểm của phạm vi)

    Returns:
        Giá trị sau khi chuyển đổi
    """
    percentage, min_val, max_val = float(percentage), float(min_val), float(max_val)
    base_val = float(base_val) if base_val is not None else (min_val + max_val) / 2

    if percentage < 0:
        # Phần trăm âm: nội suy tuyến tính từ base_val đến min_val
        result = base_val + (base_val - min_val) * (percentage / 100)
    else:
        # Phần trăm dương: nội suy tuyến tính từ base_val đến max_val
        result = base_val + (max_val - base_val) * (percentage / 100)
 
    # Đảm bảo kết quả nằm trong phạm vi hợp lệ
    return max(min_val, min(max_val, result))
