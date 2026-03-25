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
    Tạo dữ liệu tiếng khóc giả lập hoặc thực tế tùy theo mock_mode.
    Trả về: labels, values
    """
    # Nếu mock mode ON, sinh dữ liệu ngẫu nhiên
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

    # Nếu mock mode OFF, đọc từ file cry_data.json
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
                if days > 1:
                    label = item_time.strftime("%d/%m %Hh")
                else:
                    label = item_time.strftime("%H:%M")
                
                filtered_labels.append(label)
                filtered_values.append(item["value"])
        except Exception:
            continue
            
    # Fallback nếu không có dữ liệu trong khoảng thời gian yêu cầu
    if not filtered_labels and all_data:
        last_n = all_data[-24:]
        for item in last_n:
            try:
                item_time = datetime.datetime.strptime(item["time"], "%Y-%m-%d %H:%M")
                label = item_time.strftime("%d/%m %H:%M")
                filtered_labels.append(label)
                filtered_values.append(item["value"])
            except Exception:
                continue

    return filtered_labels, filtered_values

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
