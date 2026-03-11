import os
import re
import queue
import asyncio
import subprocess
import threading
import time
import traceback
from yt_dlp import YoutubeDL

from core.handle.sendAudioHandle import send_stt_message
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

TAG = __name__

play_youtube_function_desc = {
    "type": "function",
    "function": {
        "name": "play_youtube",
        "description": "Tìm kiếm và phát nhạc, kể chuyện, tiếng ồn trắng (white noise) trực tiếp từ YouTube. Chỉ sử dụng chức năng này khi người dùng yêu cầu nghe nhạc hoặc nội dung âm thanh.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Từ khóa tìm kiếm trên YouTube, ví dụ: 'nhạc ru ngủ cho bé', 'tiếng ồn trắng sleep', 'sơn tùng mtp'.",
                }
            },
            "required": ["query"],
        },
    },
}

@register_function("play_youtube", play_youtube_function_desc, ToolType.SYSTEM_CTL)
def play_youtube(conn, query: str):
    try:
        # Kiểm tra event loop
        if not getattr(conn, "loop", None) or not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("Event loop chưa chạy, không thể phát nhạc.")
            return ActionResponse(action=Action.RESPONSE, result="Hệ thống bận", response="Xin vui lòng thử lại sau.")
        
        task = conn.loop.create_task(handle_youtube_command(conn, query))
        
        def handle_done(f):
            try:
                f.result()
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"YouTube Playback Failed: {e}")
        
        task.add_done_callback(handle_done)
        
        # Trả về để chặn LLM sinh thêm phản hồi
        return ActionResponse(action=Action.NONE, result="Command Received", response="Đang tìm kiếm YouTube")
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"play_youtube error: {e}")
        return ActionResponse(action=Action.RESPONSE, result=str(e), response="Đã xảy ra lỗi khi cố gắng phát nhạc.")

async def handle_youtube_command(conn, query):
    try:
        wait_text = f"Đang tìm kiếm {query} trên kênh YouTube..."
        await send_stt_message(conn, wait_text)
        if hasattr(conn, "dialogue"):
            conn.dialogue.put(Message(role="assistant", content=wait_text))
            
        def search_yt():
            ydl_opts = {
                'format': 'bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'simulate': True,
                'skip_download': True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if 'entries' in info and len(info['entries']) > 0:
                    entry = info['entries'][0]
                    return entry['url'], entry.get('title', 'YouTube Audio')
                return None, None
                
        stream_url, title = await asyncio.to_thread(search_yt)
        
        if not stream_url:
            await send_stt_message(conn, "Xin lỗi, không tìm thấy kết quả phù hợp trên YouTube.")
            if hasattr(conn, "dialogue"):
                conn.dialogue.put(Message(role="assistant", content="Không tìm thấy bài hát trên YouTube."))
            return
            
        play_text = f"Đang phát: {title}"
        await send_stt_message(conn, play_text)
        if hasattr(conn, "dialogue"):
            conn.dialogue.put(Message(role="assistant", content=play_text))
            
        # Thêm câu nói giới thiệu bài hát lên hàng đợi TTS
        if conn.tts and hasattr(conn.tts, "tts_text_queue"):
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id if hasattr(conn, "sentence_id") else None,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=play_text,
                )
            )

        # Trích xuất sample rate
        sample_rate = getattr(conn, "sample_rate", 16000)
        
        def stream_ffmpeg():
            proc = None
            try:
                cmd = [
                    "ffmpeg", 
                    "-nostdin",
                    "-i", stream_url,
                    "-f", "s16le",
                    "-ac", "1",
                    "-ar", str(sample_rate),
                    "-"
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                
                # Tính frame size: 60ms = sample_rate * 60 / 1000 samples, 2 bytes/sample (16bit)
                frame_duration_ms = 60
                frame_size = int(sample_rate * frame_duration_ms / 1000 * 2) 
                
                is_opus = getattr(conn, "audio_format", "opus") == "opus"
                encoder = getattr(conn.tts, "opus_encoder", None) if hasattr(conn, "tts") else None
                
                while not getattr(conn, "stop_event", threading.Event()).is_set():
                    # Nếu có tín hiệu ngắt (Bấm nút / Gọi VAD mới), dọn dẹp và thoát
                    if getattr(conn, "client_abort", False):
                        conn.logger.bind(tag=TAG).info("YouTube stream aborted (client_abort=True)")
                        break
                        
                    # Điều tiết nghẽn queue (giới hạn 50 chunks ~ 3s đệm) để không OOM RAM
                    if hasattr(conn, "tts") and hasattr(conn.tts, "tts_audio_queue"):
                        if conn.tts.tts_audio_queue.qsize() > 50:
                            time.sleep(0.5)
                            continue
                    
                    chunk = proc.stdout.read(frame_size)
                    if not chunk: # Hết file nhạc
                        break
                        
                    if len(chunk) < frame_size: # Đệm null bytes cho đủ size (quan trọng cho Opus)
                        chunk = chunk + b'\0' * (frame_size - len(chunk))
                        
                    if is_opus and encoder:
                        encoded = encoder.encode(chunk)
                        if hasattr(conn, "tts"):
                            conn.tts.tts_audio_queue.put((SentenceType.MIDDLE, encoded, None))
                    else:
                        if hasattr(conn, "tts"):
                            conn.tts.tts_audio_queue.put((SentenceType.MIDDLE, chunk, None))
                            
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"FFmpeg stream error: {e}")
            finally:
                if proc:
                    proc.terminate()
                if hasattr(conn, "tts") and hasattr(conn.tts, "tts_audio_queue"):
                    # Gửi cờ kết thúc để TTS không bị kẹt đợi
                    conn.tts.tts_audio_queue.put((SentenceType.LAST, [], None))
                    
        # Thời gian nhỏ chờ TTS đọc xong tiêu đề bài hát rồi mới bật ffmpeg
        await asyncio.sleep(2.0)
        threading.Thread(target=stream_ffmpeg, daemon=True).start()

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"handle_youtube_command error: {e}")
