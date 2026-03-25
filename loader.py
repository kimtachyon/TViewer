"""백그라운드 이미지 프리로더 — 속도 최적화 핵심 모듈."""
import threading
from pathlib import Path
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

SUPPORTED = {'.jpg', '.jpeg', '.png', '.heic', '.heif',
             '.tiff', '.tif', '.bmp', '.webp', '.gif'}


class ImageLoader:
    """
    디코딩된 PIL Image를 캐시하는 프리로더.
    - 현재 이미지 표시 중 앞뒤 이미지를 백그라운드에서 미리 디코딩
    - LRU 방식으로 최대 CACHE_SIZE개 유지
    """
    CACHE_SIZE = 7

    def __init__(self):
        from concurrent.futures import ThreadPoolExecutor
        self._cache: dict[str, Image.Image | None] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._futures: dict[str, object] = {}
        self._executor = ThreadPoolExecutor(max_workers=2,
                                            thread_name_prefix="tviewer")

    # ── public ──────────────────────────────────────────────

    def get(self, path: Path) -> Image.Image | None:
        """PIL Image 반환. 캐시 미스 시 동기 디코딩."""
        key = str(path)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            future = self._futures.pop(key, None)

        if future:
            img = future.result()
        else:
            img = self._decode(key)

        with self._lock:
            self._put(key, img)
        return img

    def preload(self, paths: list[Path]):
        """백그라운드에서 이미지 디코딩 예약."""
        for p in paths:
            key = str(p)
            with self._lock:
                if key in self._cache or key in self._futures:
                    continue
                self._futures[key] = self._executor.submit(self._decode, key)

    def invalidate(self, path: Path):
        """캐시에서 특정 파일 제거."""
        key = str(path)
        with self._lock:
            self._cache.pop(key, None)
            if key in self._order:
                self._order.remove(key)

    # ── private ─────────────────────────────────────────────

    @staticmethod
    def _decode(path: str) -> Image.Image | None:
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
            img.load()
            return img
        except Exception:
            return None

    def _put(self, key: str, img):
        if key in self._cache:
            return
        self._cache[key] = img
        self._order.append(key)
        while len(self._order) > self.CACHE_SIZE:
            old = self._order.pop(0)
            self._cache.pop(old, None)
