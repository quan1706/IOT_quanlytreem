"""
Module quản lý GC (Garbage Collection) toàn cục
Thực hiện dọn rác bộ nhớ định kỳ, tránh GC kích hoạt quá thường xuyên gây khóa GIL
"""

import gc
import asyncio
import threading
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class GlobalGCManager:
    """Bộ quản lý dọn rác bộ nhớ toàn cục"""

    def __init__(self, interval_seconds=300):
        """
        Khởi tạo bộ quản lý GC

        Args:
            interval_seconds: Khoảng cách giữa các lần dọn rác (giây), mặc định 300 giây (5 phút)
        """
        self.interval_seconds = interval_seconds
        self._task = None
        self._stop_event = asyncio.Event()
        self._lock = threading.Lock()

    async def start(self):
        """Khởi động tác vụ dọn rác định kỳ"""
        if self._task is not None:
            logger.bind(tag=TAG).warning("Bộ quản lý GC đã đang chạy")
            return

        logger.bind(tag=TAG).info(f"Khởi động bộ quản lý GC toàn cục, chu kỳ {self.interval_seconds} giây")
        self._stop_event.clear()
        self._task = asyncio.create_task(self._gc_loop())

    async def stop(self):
        """Dừng tác vụ dọn rác định kỳ"""
        if self._task is None:
            return

        logger.bind(tag=TAG).info("Dừng bộ quản lý GC toàn cục")
        self._stop_event.set()

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._task = None

    async def _gc_loop(self):
        """Vòng lặp dọn rác"""
        try:
            while not self._stop_event.is_set():
                # Chờ đúng khoảng thời gian đã đặt
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.interval_seconds
                    )
                    # Nếu stop_event được kích hoạt, thoát vòng lặp
                    break
                except asyncio.TimeoutError:
                    # Hết thời gian chờ = đã đến lúc dọn rác
                    pass

                # Thực hiện dọn rác
                await self._run_gc()

        except asyncio.CancelledError:
            logger.bind(tag=TAG).info("Tác vụ dọn rác đã bị hủy")
            raise
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi trong vòng lặp dọn rác: {e}")
        finally:
            logger.bind(tag=TAG).info("Tác vụ dọn rác đã thoát")

    async def _run_gc(self):
        """Thực hiện dọn rác bộ nhớ"""
        try:
            # Chạy GC trong thread pool để không chặn event loop
            loop = asyncio.get_running_loop()

            def do_gc():
                with self._lock:
                    before = len(gc.get_objects())
                    collected = gc.collect()
                    after = len(gc.get_objects())
                    return before, collected, after

            before, collected, after = await loop.run_in_executor(None, do_gc)
            logger.bind(tag=TAG).debug(
                f"Dọn rác hoàn tất - Đã thu hồi: {collected} đối tượng, "
                f"Số lượng đối tượng: {before} -> {after}"
            )
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi khi dọn rác bộ nhớ: {e}")


# Đối tượng đơn nhất (Singleton) toàn cục
_gc_manager_instance = None


def get_gc_manager(interval_seconds=300):
    """
    Lấy đối tượng quản lý GC toàn cục (Singleton)

    Args:
        interval_seconds: Khoảng cách giữa các lần dọn rác (giây), mặc định 300 giây (5 phút)

    Returns:
        Đối tượng GlobalGCManager
    """
    global _gc_manager_instance
    if _gc_manager_instance is None:
        _gc_manager_instance = GlobalGCManager(interval_seconds)
    return _gc_manager_instance
