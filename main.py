import sys
import tkinter as tk
from app import TViewerApp


def main():
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    app = TViewerApp(root, initial_path=initial)

    # macOS: 파인더에서 파일 더블클릭 시 Apple Event로 경로가 전달됨
    # argv_emulation 없이도 Tk의 OpenDocument 핸들러로 처리 가능
    def _open_doc(*paths):
        if paths:
            app._open_path(paths[0])

    try:
        root.createcommand("::tk::mac::OpenDocument", _open_doc)
    except Exception:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()
