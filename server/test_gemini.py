import asyncio
from google import generativeai as genai
from google.generativeai import GenerationConfig

api_key = "AIzaSyDNl8_Bttc3i6XHnz_OELu7y8fSWj-xBWQ"
genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-1.5-flash")
prompt = """
Bạn là Tiểu Bảo AI - Cố vấn Nhi khoa Cao cấp, chuyên phân tích dữ liệu IoT phòng trẻ sơ sinh.

Dữ liệu cảm biến phòng bé trong 24 giờ qua:
Nhiệt độ: 25C

**Nhiệm vụ:** Viết báo cáo phân tích chi tiết, ít nhất 4 đoạn văn, gồm đủ 4 mục sau:
1. Nhận định tổng quan
2. Phân tích xu hướng
3. Khuyến nghị thiết bị
4. Lời khuyên chăm sóc
"""
gen_cfg = GenerationConfig(
    max_output_tokens=1200,
    temperature=0.75,
)

async def run():
    try:
        resp = model.generate_content(prompt, generation_config=gen_cfg)
        print("RESPONSE:", resp.text)
    except Exception as e:
        print("ERROR:", e)

asyncio.run(run())
