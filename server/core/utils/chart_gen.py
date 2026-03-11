import urllib.parse
import json

def load_cry_data():
    """Load dữ liệu tiếng khóc từ file JSON."""
    import os
    from config.config_loader import get_project_dir
    
    file_path = os.path.join(get_project_dir(), "data", "cry_data.json")
    if not os.path.exists(file_path):
        return []
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("hourly_data", [])
    except Exception:
        return []

def generate_mock_cry_data(days=1):
    """Lấy dữ liệu tiếng khóc từ file JSON và lọc theo số ngày."""
    import datetime
    all_data = load_cry_data()
    if not all_data:
        # Fallback nếu không có file
        return ["00:00"], [0]

    now = datetime.datetime.now()
    start_time = now - datetime.timedelta(days=days)
    
    filtered_labels = []
    filtered_values = []
    
    for item in all_data:
        try:
            item_time = datetime.datetime.strptime(item["time"], "%Y-%m-%d %H:%M")
            if item_time >= start_time:
                # Nếu hiển thị nhiều ngày, label nên bao gồm ngày
                if days > 1:
                    label = item_time.strftime("%d/%m %Hh")
                else:
                    label = item_time.strftime("%H:%M")
                
                filtered_labels.append(label)
                filtered_values.append(item["value"])
        except Exception:
            continue
            
    return filtered_labels, filtered_values

def get_cry_chart_url(labels, values, title="Thống kê tiếng khóc"):
    """Tạo URL QuickChart.io cho biểu đồ tiếng khóc."""
    # Giới hạn số lượng nhãn hiển thị nếu quá nhiều (để chart không bị rối)
    step = 1
    if len(labels) > 24:
        step = len(labels) // 12 # Hiển thị khoảng 12 nhãn trục X
        
    display_labels = [label if i % step == 0 else "" for i, label in enumerate(labels)]

    chart_config = {
        "type": "line",
        "data": {
            "labels": display_labels, # Chỉ hiển thị một số nhãn để tránh rối
            "datasets": [
                {
                    "label": "Cường độ tiếng khóc (RMS)",
                    "data": values, # Vẫn giữ toàn bộ điểm dữ liệu
                    "fill": True,
                    "backgroundColor": "rgba(255, 99, 132, 0.2)",
                    "borderColor": "rgb(255, 99, 132)",
                    "tension": 0.4,
                    "pointRadius": 0 if len(values) > 50 else 3 # Ẩn point nếu quá nhiều điểm
                }
            ]
        },
        "options": {
            "title": {
                "display": True,
                "text": title
            },
            "scales": {
                "yAxes": [{"ticks": {"beginAtZero": True}}],
                "xAxes": [{
                    "ticks": {
                        "autoSkip": True,
                        "maxRotation": 45,
                        "minRotation": 45
                    }
                }]
            }
        }
    }
    
    config_str = json.dumps(chart_config)
    encoded_config = urllib.parse.quote(config_str)
    return f"https://quickchart.io/chart?c={encoded_config}"
