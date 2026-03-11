import json
import datetime
import os
import sys

# Mock get_project_dir to match our environment
def get_project_dir():
    return "d:/GITCLONE/IOT_quanlytreem/server/"

# Copy of load_cry_data
def load_cry_data():
    file_path = os.path.join(get_project_dir(), "data", "cry_data.json")
    print(f"Checking path: {file_path}")
    if not os.path.exists(file_path):
        print("File does not exist!")
        return []
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("hourly_data", [])
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return []

# Copy of generate_mock_cry_data
def generate_mock_cry_data(days=1):
    all_data = load_cry_data()
    if not all_data:
        return ["00:00"], [0]

    # Use a fixed "now" or datetime.datetime.now()
    now = datetime.datetime.now()
    start_time = now - datetime.timedelta(days=days)
    print(f"Filtering from {start_time} to {now}")
    
    filtered_labels = []
    filtered_values = []
    
    count = 0
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
            else:
                count += 1
        except Exception as e:
            continue
            
    print(f"Skipped {count} old points. Found {len(filtered_labels)} matching points.")
    return filtered_labels, filtered_values

labels, values = generate_mock_cry_data(1)
print(f"Labels: {labels}")
print(f"Values: {values}")
