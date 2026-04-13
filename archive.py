"""압축 파일(zip, tar, gz, bz2) 내부 이미지 읽기 모듈."""
import io
import tarfile
import zipfile
from pathlib import PurePosixPath
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

from loader import SUPPORTED

ARCHIVE_EXTS = {'.zip', '.tar', '.gz', '.tgz', '.bz2', '.tbz2', '.xz', '.txz'}


def is_archive(path) -> bool:
    """경로가 지원되는 압축 파일인지 확인."""
    from pathlib import Path
    p = Path(path)
    # .tar.gz, .tar.bz2, .tar.xz 등 이중 확장자 처리
    if p.suffixes[-2:] in (['.tar', '.gz'], ['.tar', '.bz2'], ['.tar', '.xz']):
        return True
    return p.suffix.lower() in ARCHIVE_EXTS


class ArchiveReader:
    """압축 파일을 폴더처럼 읽어 이미지 목록과 PIL Image를 제공."""

    def __init__(self, archive_path):
        from pathlib import Path
        self.path = Path(archive_path).resolve()
        self._entries: list[str] = []
        self._handle = None
        self._kind: str = ""  # "zip" or "tar"
        self._open()

    def _open(self):
        name = self.path.name.lower()
        if zipfile.is_zipfile(self.path):
            self._kind = "zip"
            self._handle = zipfile.ZipFile(self.path, 'r')
            all_names = self._handle.namelist()
        elif tarfile.is_tarfile(self.path):
            self._kind = "tar"
            self._handle = tarfile.open(self.path, 'r:*')
            all_names = [m.name for m in self._handle.getmembers() if m.isfile()]
        else:
            raise ValueError(f"지원하지 않는 압축 형식: {self.path.name}")

        # 이미지 파일만 필터링, 숨김 파일(__MACOSX 등) 제외
        self._entries = sorted(
            [n for n in all_names
             if PurePosixPath(n).suffix.lower() in SUPPORTED
             and not any(part.startswith(('.', '__')) for part in PurePosixPath(n).parts)],
            key=lambda n: PurePosixPath(n).name.lower()
        )

    @property
    def entries(self) -> list[str]:
        return self._entries

    def get_image(self, entry_name: str) -> Image.Image | None:
        """압축 파일 내 항목을 PIL Image로 디코딩."""
        try:
            if self._kind == "zip":
                data = self._handle.read(entry_name)
            else:
                member = self._handle.getmember(entry_name)
                f = self._handle.extractfile(member)
                if f is None:
                    return None
                data = f.read()
            img = Image.open(io.BytesIO(data))
            img = ImageOps.exif_transpose(img)
            img.load()
            return img
        except Exception:
            return None

    def get_entry_size(self, entry_name: str) -> int | None:
        """압축 파일 내 항목의 원본 크기(bytes)."""
        try:
            if self._kind == "zip":
                info = self._handle.getinfo(entry_name)
                return info.file_size
            else:
                return self._handle.getmember(entry_name).size
        except Exception:
            return None

    def close(self):
        if self._handle:
            self._handle.close()
            self._handle = None

    def __del__(self):
        self.close()
