import struct

def decode_opus_from_file(input_file):
    """
    Giải mã dữ liệu Opus từ tệp p3 và trả về danh sách các gói dữ liệu Opus kèm theo tổng thời lượng.
    """
    opus_datas = []
    total_frames = 0
    sample_rate = 16000  # Tỷ lệ lấy mẫu tệp
    frame_duration_ms = 60  # Thời lượng khung hình
    frame_size = int(sample_rate * frame_duration_ms / 1000)

    with open(input_file, 'rb') as f:
        while True:
            # Đọc phần đầu (4 byte): [1 byte loại, 1 byte dự phòng, 2 byte độ dài]
            header = f.read(4)
            if not header:
                break

            # Giải nén thông tin phần đầu
            _, _, data_len = struct.unpack('>BBH', header)

            # Đọc dữ liệu Opus dựa trên độ dài được chỉ định trong phần đầu
            opus_data = f.read(data_len)
            if len(opus_data) != data_len:
                raise ValueError(f"Data length({len(opus_data)}) mismatch({data_len}) in the file.")

            opus_datas.append(opus_data)
            total_frames += 1

    # Tính tổng thời lượng
    total_duration = (total_frames * frame_duration_ms) / 1000.0
    return opus_datas, total_duration

def decode_opus_from_bytes(input_bytes):
    """
    Giải mã dữ liệu Opus từ dữ liệu nhị phân p3 và trả về danh sách các gói dữ liệu Opus kèm theo tổng thời lượng.
    """
    import io
    opus_datas = []
    total_frames = 0
    sample_rate = 16000  # 文件采样率
    frame_duration_ms = 60  # 帧时长
    frame_size = int(sample_rate * frame_duration_ms / 1000)

    f = io.BytesIO(input_bytes)
    while True:
        header = f.read(4)
        if not header:
            break
        _, _, data_len = struct.unpack('>BBH', header)
        opus_data = f.read(data_len)
        if len(opus_data) != data_len:
            raise ValueError(f"Khối lượng dữ liệu({len(opus_data)}) không khớp({data_len}) trong byte.")
        opus_datas.append(opus_data)
        total_frames += 1
 
    total_duration = (total_frames * frame_duration_ms) / 1000.0
    return opus_datas, total_duration