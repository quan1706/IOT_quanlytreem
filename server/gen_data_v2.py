import json
import random
import datetime

def generate_hourly_data():
    now = datetime.datetime.now()
    # Start from 7 days ago, rounded to the nearest hour
    start_date = (now - datetime.timedelta(days=7)).replace(minute=0, second=0, microsecond=0)
    
    data = []
    for i in range(169): # 7 days * 24 hours + current hour
        current_time = start_date + datetime.timedelta(hours=i)
        hour = current_time.hour
        
        # Base intensity is higher at night (22:00 to 06:00)
        if 22 <= hour or hour <= 6:
            base = random.randint(300, 600)
            # Occasional large spikes at night
            if random.random() < 0.2:
                base += random.randint(300, 500)
        else:
            base = random.randint(0, 150)
            # Rare spikes during the day
            if random.random() < 0.05:
                base += random.randint(400, 800)
                
        data.append({
            "time": current_time.strftime("%Y-%m-%d %H:%M"),
            "value": base
        })
    
    return {"hourly_data": data}

import os
target_file = "d:/GITCLONE/IOT_quanlytreem/server/data/cry_data.json"
os.makedirs(os.path.dirname(target_file), exist_ok=True)

with open(target_file, "w", encoding="utf-8") as f:
    json.dump(generate_hourly_data(), f, indent=2, ensure_ascii=False)

print(f"Generated {target_file} with 169 hourly points.")
