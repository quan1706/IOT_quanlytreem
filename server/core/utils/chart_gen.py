import datetime
import random
import json
import os
import urllib.parse
from core.serverToClients.dashboard_updater import DASHBOARD_STATE

def load_cry_data():
    """Load dữ liệu tiếng khóc từ file JSON."""
    try:
        file_path = "data/cry_data.json"
        if not os.path.exists(file_path):
            return []
            
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Hỗ trợ cả định dạng list trực tiếp hoặc dict {hourly_data: []}
            if isinstance(data, dict):
                return data.get("hourly_data", [])
            return data
    except Exception:
        return []

def generate_mock_cry_data(days=1):
    """
    Tạo dữ liệu tiếng khóc: Ưu tiên lấy từ chart_history.json (Web Dashboard),
    sau đó đến cry_data.json, và cuối cùng là mock nếu không có dữ liệu.
    """
    # 1. Ưu tiên đọc từ chart_history.json (đã được DashboardUpdater cập nhật live)
    try:
        hist_path = "data/chart_history.json"
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                hist = json.load(f)
            # chart_history.json lưu điểm mỗi 10p, n_points = 144 cho 24h
            n = 144 if days == 1 else days * 48
            labels = hist.get("labels", [])[-n:]
            values = hist.get("cry", [])[-n:]
            if labels and any(v > 0 for v in values):
                return labels, values
    except Exception:
        pass

    # 2. Fallback sang mock mode nếu ON
    if DASHBOARD_STATE.get("mock_mode", False):
        labels = []
        values = []
        now = datetime.datetime.now()
        points = 24 if days == 1 else days * 4  # 1h/điểm hoặc 6h/điểm
        
        for i in range(points):
            delta = datetime.timedelta(hours=i if days == 1 else i*6)
            t = now - delta
            labels.insert(0, t.strftime("%H:%M") if days == 1 else t.strftime("%d/%m %Hh"))
            values.insert(0, random.randint(0, 1000))
        return labels, values

    # 3. Fallback sang cry_data.json (legacy)
    all_data = load_cry_data()
    if not all_data:
        return ["00:00"], [0]
        
    now = datetime.datetime.now()
    start_time = now - datetime.timedelta(days=days)
    
    filtered_labels = []
    filtered_values = []
    
    for item in all_data:
        try:
            item_time = datetime.datetime.strptime(item["time"], "%Y-%m-%d %H:%M")
            if item_time >= start_time:
                label = item_time.strftime("%d/%m %Hh") if days > 1 else item_time.strftime("%H:%M")
                filtered_labels.append(label)
                filtered_values.append(item["value"])
        except Exception:
            continue
            
    if not filtered_labels and all_data:
        for item in all_data[-24:]:
            try:
                item_time = datetime.datetime.strptime(item["time"], "%Y-%m-%d %H:%M")
                filtered_labels.append(item_time.strftime("%d/%m %H:%M"))
                filtered_values.append(item["value"])
            except Exception:
                continue

    return filtered_labels, filtered_values


def build_chart_summary(labels, cry=None, temp=None, hum=None, top_n=10):
    """
    Xây dựng chuỗi tóm tắt dữ liệu chart để AI dễ đọc và phân tích.
    Áp dụng logic chọn điểm đỉnh (peak points) + điểm gần nhất.
    Đây là hàm dùng chung cho cả Telegram và Web Dashboard.

    Args:
        labels: list[str] - Các mốc thời gian.
        cry: list[float|int] - Cường độ tiếng khóc (0-1000).
        temp: list[float] - Nhiệt độ (°C).
        hum: list[float] - Độ ẩm (%).
        top_n: Số điểm đỉnh chọn để tóm tắt.

    Returns:
        str - Đoạn text mô tả dữ liệu chart.
    """
    if not labels:
        return "Chưa có dữ liệu lịch sử."

    n = len(labels)
    has_cry = cry and len(cry) == n
    has_temp = temp and len(temp) == n
    has_hum = hum and len(hum) == n

    # Tính thống kê tổng quan
    stats_lines = ["**Thống kê tổng quan:**"]
    if has_temp:
        t_avg = round(sum(temp) / n, 1)
        t_max = max(temp)
        t_min = min(temp)
        stats_lines.append(f"- Nhiệt độ: TB {t_avg}°C, Max {t_max}°C, Min {t_min}°C")
    if has_hum:
        h_avg = round(sum(hum) / n, 1)
        stats_lines.append(f"- Độ ẩm: TB {h_avg}%")
    if has_cry:
        crying_count = sum(1 for v in cry if v > 200)
        stats_lines.append(f"- Bé khóc: {crying_count}/{n} điểm (ngưỡng RMS > 200)")

    # Chọn các điểm đáng chú ý: đỉnh cry + 2 điểm gần nhất
    if has_cry:
        indexed = list(enumerate(cry))
        peak_idx = sorted([i for i, v in sorted(indexed, key=lambda x: x[1], reverse=True)[:top_n]])
        selected_idx = sorted(set(peak_idx + [n - 2, n - 1]) & set(range(n)))
    else:
        # Nếu không có cry, chọn đều từ toàn bộ dữ liệu
        step = max(1, n // top_n)
        selected_idx = list(range(0, n, step)) + [n - 1]
        selected_idx = sorted(set(selected_idx))

    # Tạo bảng dữ liệu từng điểm
    detail_lines = ["\n**Chi tiết các điểm đáng chú ý:**"]
    for i in selected_idx:
        parts = [f"  [{labels[i]}]"]
        if has_cry:
            parts.append(f"Bé khóc: {cry[i]} RMS")
        if has_temp:
            parts.append(f"Nhiệt độ: {temp[i]}°C")
        if has_hum:
            parts.append(f"Độ ẩm: {hum[i]}%")
        detail_lines.append(", ".join(parts))

    return "\n".join(stats_lines + detail_lines)

def generate_combined_mock_data(days=1):
    """
    Sinh dữ liệu kết hợp Khóc + Nhiệt độ cho Dashboard hoặc Chart.
    """
    labels = []
    cry_values = []
    temp_values = []
    
    now = datetime.datetime.now()
    points = 24 if days == 1 else 20
    base_temp = 28.0
    
    for i in range(points):
        delta = datetime.timedelta(hours=i if days == 1 else i*(days*24//20))
        t = now - delta
        labels.insert(0, t.strftime("%H:%M") if days == 1 else t.strftime("%d/%m"))
        
        cry = random.randint(0, 1000)
        temp = base_temp + random.uniform(-1, 3) + (2 if cry > 700 else 0) # Giả lập correlation
        
        cry_values.insert(0, cry)
        temp_values.insert(0, round(temp, 1))
        
    return labels, cry_values, temp_values

def get_cry_chart_url(labels, values, title="Thống kê tiếng khóc"):
    """Tạo URL QuickChart cho biểu đồ tiếng khóc đơn."""
    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Cường độ tiếng khóc (RMS)",
                "data": values,
                "fill": True,
                "backgroundColor": "rgba(255, 99, 132, 0.2)",
                "borderColor": "rgb(255, 99, 132)",
                "tension": 0.4
            }]
        },
        "options": {
            "title": { "display": True, "text": title },
            "scales": { "yAxes": [{"ticks": {"beginAtZero": True}}] }
        }
    }
    return f"https://quickchart.io/chart?c={urllib.parse.quote(json.dumps(chart_config))}"

def get_dual_chart_url(labels, cry_values, temp_values, title="Thống kê Tổng hợp (Khóc & Nhiệt độ)"):
    """
    Tạo URL QuickChart với 2 trục Y: Khóc (trái) và Nhiệt độ (phải)
    """
    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Tiếng khóc (RMS)",
                    "data": cry_values,
                    "borderColor": "rgb(255, 99, 132)",
                    "backgroundColor": "rgba(255, 99, 132, 0.2)",
                    "fill": True,
                    "yAxisID": "y"
                },
                {
                    "label": "Nhiệt độ (°C)",
                    "data": temp_values,
                    "borderColor": "rgb(54, 162, 235)",
                    "fill": False,
                    "yAxisID": "y1"
                }
            ]
        },
        "options": {
            "title": { "display": True, "text": title, "fontSize": 18 },
            "scales": {
                "yAxes": [
                    {
                        "id": "y",
                        "type": "linear",
                        "position": "left",
                        "scaleLabel": { "display": True, "labelString": "Tiếng khóc (RMS)" },
                        "ticks": { "beginAtZero": True }
                    },
                    {
                        "id": "y1",
                        "type": "linear",
                        "position": "right",
                        "gridLines": { "drawOnChartArea": False },
                        "scaleLabel": { "display": True, "labelString": "Nhiệt độ (°C)" },
                        "ticks": { "min": 20, "max": 45 }
                    }
                ]
            }
        }
    }
    return f"https://quickchart.io/chart?c={urllib.parse.quote(json.dumps(chart_config))}"
