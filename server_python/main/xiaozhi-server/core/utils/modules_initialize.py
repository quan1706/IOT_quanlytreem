from typing import Dict, Any
from config.logger import setup_logging
from core.utils import tts, llm, intent, memory, vad, asr

TAG = __name__
logger = setup_logging()


def initialize_modules(
    logger,
    config: Dict[str, Any],
    init_vad=False,
    init_asr=False,
    init_llm=False,
    init_tts=False,
    init_memory=False,
    init_intent=False,
) -> Dict[str, Any]:
    """
    Khởi tạo tất cả các module thành phần

    Args:
        config: Từ điển cấu hình

    Returns:
        Dict[str, Any]: Từ điển chứa tất cả các module đã khởi tạo
    """
    modules = {}

    # Khởi tạo module TTS (Chuyển văn bản thành giọng nói)
    if init_tts:
        select_tts_module = config["selected_module"]["TTS"]
        modules["tts"] = initialize_tts(config)
        logger.bind(tag=TAG).info(f"Khởi tạo thành phần: TTS thành công - {select_tts_module}")

    # Khởi tạo module LLM (Mô hình ngôn ngữ lớn)
    if init_llm:
        select_llm_module = config["selected_module"]["LLM"]
        llm_type = (
            select_llm_module
            if "type" not in config["LLM"][select_llm_module]
            else config["LLM"][select_llm_module]["type"]
        )
        modules["llm"] = llm.create_instance(
            llm_type,
            config["LLM"][select_llm_module],
        )
        logger.bind(tag=TAG).info(f"Khởi tạo thành phần: LLM thành công - {select_llm_module}")

    # Khởi tạo module Intent (Nhận diện ý định)
    if init_intent:
        select_intent_module = config["selected_module"]["Intent"]
        intent_type = (
            select_intent_module
            if "type" not in config["Intent"][select_intent_module]
            else config["Intent"][select_intent_module]["type"]
        )
        modules["intent"] = intent.create_instance(
            intent_type,
            config["Intent"][select_intent_module],
        )
        logger.bind(tag=TAG).info(f"Khởi tạo thành phần: Intent thành công - {select_intent_module}")

    # Khởi tạo module Memory (Bộ nhớ hội thoại)
    if init_memory:
        select_memory_module = config["selected_module"]["Memory"]
        memory_type = (
            select_memory_module
            if "type" not in config["Memory"][select_memory_module]
            else config["Memory"][select_memory_module]["type"]
        )
        modules["memory"] = memory.create_instance(
            memory_type,
            config["Memory"][select_memory_module],
            config.get("summaryMemory", None),
        )
        logger.bind(tag=TAG).info(f"Khởi tạo thành phần: Memory thành công - {select_memory_module}")

    # Khởi tạo module VAD (Phát hiện giọng nói)
    if init_vad:
        select_vad_module = config["selected_module"]["VAD"]
        vad_type = (
            select_vad_module
            if "type" not in config["VAD"][select_vad_module]
            else config["VAD"][select_vad_module]["type"]
        )
        modules["vad"] = vad.create_instance(
            vad_type,
            config["VAD"][select_vad_module],
        )
        logger.bind(tag=TAG).info(f"Khởi tạo thành phần: VAD thành công - {select_vad_module}")

    # Khởi tạo module ASR (Nhận diện giọng nói)
    if init_asr:
        select_asr_module = config["selected_module"]["ASR"]
        modules["asr"] = initialize_asr(config)
        logger.bind(tag=TAG).info(f"Khởi tạo thành phần: ASR thành công - {select_asr_module}")
    return modules


def initialize_tts(config):
    select_tts_module = config["selected_module"]["TTS"]
    tts_type = (
        select_tts_module
        if "type" not in config["TTS"][select_tts_module]
        else config["TTS"][select_tts_module]["type"]
    )
    new_tts = tts.create_instance(
        tts_type,
        config["TTS"][select_tts_module],
        str(config.get("delete_audio", True)).lower() in ("true", "1", "yes"),
    )
    return new_tts


def initialize_asr(config):
    select_asr_module = config["selected_module"]["ASR"]
    asr_type = (
        select_asr_module
        if "type" not in config["ASR"][select_asr_module]
        else config["ASR"][select_asr_module]["type"]
    )
    new_asr = asr.create_instance(
        asr_type,
        config["ASR"][select_asr_module],
        str(config.get("delete_audio", True)).lower() in ("true", "1", "yes"),
    )
    logger.bind(tag=TAG).info("Module ASR đã khởi tạo hoàn tất")
    return new_asr


def initialize_voiceprint(asr_instance, config):
    """Khởi tạo chức năng nhận diện giọng nói (Voiceprint)"""
    voiceprint_config = config.get("voiceprint")
    if not voiceprint_config:
        return False  

    # Áp dụng cấu hình
    if not voiceprint_config.get("url") or not voiceprint_config.get("speakers"):
        logger.bind(tag=TAG).warning("Cấu hình nhận diện giọng nói chưa đầy đủ")
        return False
        
    try:
        asr_instance.init_voiceprint(voiceprint_config)
        logger.bind(tag=TAG).info("Chức năng nhận diện giọng nói (Voiceprint) của ASR đã được kích hoạt")
        logger.bind(tag=TAG).info(f"Số lượng người nói đã cấu hình: {len(voiceprint_config['speakers'])}")
        return True
    except Exception as e:
        logger.bind(tag=TAG).error(f"Khởi tạo chức năng nhận diện giọng nói thất bại: {str(e)}")
        return False
