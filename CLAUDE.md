# TViewer

Python Tkinter 기반 macOS 이미지 뷰어. 폴더/압축파일 내 이미지 탐색, EXIF 정보 패널, 다크 테마.

## 실행 / 빌드

```bash
# 개발 실행
/opt/homebrew/bin/python3.12 main.py

# 배포 빌드 (dist/TViewer.app 생성)
/opt/homebrew/bin/python3.12 -m PyInstaller TViewer_mac.spec --clean --noconfirm

# 테스트
/opt/homebrew/bin/python3.12 -u test_tviewer.py
```

**빌드 시 반드시 Homebrew Python 3.12 사용.** 시스템 `python3`(3.9/Tk 8.5)로 빌드하면 Aqua 백엔드가 커스텀 bg/fg를 무시하여 화면이 비어보임.

## 핵심 규칙

- **UI 색상**: `theme.py`의 팔레트 상수 사용 (`BG`, `BG2`, `ACCENT` 등 하드코딩 금지)
- **EXIF 방향 보정**: 이미지 로딩 시 `ImageOps.exif_transpose` 적용 (loader.py)
- **캔버스 가드**: `winfo_width()` < 10이면 렌더링/클릭 처리 건너뛰기 (매핑 전 1px 반환 문제 방지)
- **툴바**: 캔버스 아래 별도 영역으로 `pack(side=BOTTOM)` — 이미지 위에 오버레이하지 않음
- **클릭 네비게이션**: 캔버스 좌 1/3 클릭 → 이전, 우 1/3 → 다음, 중앙 → 무동작. 드래그와 구분

## 파일 구조

```
main.py          # 엔트리포인트, macOS OpenDocument 핸들러
app.py           # TViewerApp — UI, 네비게이션, 줌, EXIF 패널
loader.py        # ImageLoader — 백그라운드 프리로드, LRU 캐시
archive.py       # ArchiveReader — zip/tar 내부 이미지 읽기
theme.py         # 다크 테마 색상/폰트 상수
test_tviewer.py  # 유닛 테스트 (33개)
TViewer_mac.spec # PyInstaller 빌드 설정
```

## 지원 포맷

이미지: `.jpg .jpeg .png .heic .heif .tiff .tif .bmp .webp .gif`
압축: `.zip .tar .gz .tgz .bz2 .tbz2 .xz .txz`
