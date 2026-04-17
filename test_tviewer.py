"""TViewer unit tests."""
from __future__ import annotations
import io
import os
import sys
import signal
import tempfile
import shutil
import unittest
import zipfile
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
os.environ['TK_SILENCE_DEPRECATION'] = '1'
signal.alarm(30)

from app import TViewerApp, _make_icon_btn
from loader import ImageLoader, SUPPORTED
from archive import ArchiveReader, is_archive, ARCHIVE_EXTS
from theme import BG, BG2, BG3, TEXT, TEXT2, ACCENT

_root = None

def get_root():
    global _root
    if _root is None:
        _root = tk.Tk()
        _root.geometry('1280x800+0+0')
        _root.update_idletasks()
    return _root


def make_test_image(path: Path, size=(100, 80), color='red'):
    img = Image.new('RGB', size, color)
    img.save(str(path))
    return path


class TestTheme(unittest.TestCase):
    def test_colors_are_hex(self):
        for name, val in [('BG', BG), ('BG2', BG2), ('BG3', BG3),
                          ('TEXT', TEXT), ('TEXT2', TEXT2), ('ACCENT', ACCENT)]:
            self.assertTrue(val.startswith('#'), f'{name}={val} is not hex')


class TestImageLoader(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.loader = ImageLoader()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_supported_extensions(self):
        for ext in ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.tiff'):
            self.assertIn(ext, SUPPORTED)

    def test_load_valid_image(self):
        p = make_test_image(self.tmpdir / 'test.png')
        img = self.loader.get(p)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (100, 80))

    def test_load_invalid_file(self):
        p = self.tmpdir / 'bad.png'
        p.write_text('not an image')
        self.assertIsNone(self.loader.get(p))

    def test_cache_hit(self):
        p = make_test_image(self.tmpdir / 'cached.png')
        img1 = self.loader.get(p)
        img2 = self.loader.get(p)
        self.assertIs(img1, img2)

    def test_invalidate(self):
        p = make_test_image(self.tmpdir / 'inv.png')
        self.loader.get(p)
        self.loader.invalidate(p)
        self.assertNotIn(str(p), self.loader._cache)

    def test_cache_eviction(self):
        paths = []
        for i in range(ImageLoader.CACHE_SIZE + 3):
            p = make_test_image(self.tmpdir / f'img{i}.png', color=(i, i, i))
            paths.append(p)
            self.loader.get(p)
        self.assertLessEqual(len(self.loader._cache), ImageLoader.CACHE_SIZE)
        self.assertNotIn(str(paths[0]), self.loader._cache)

    def test_preload(self):
        p = make_test_image(self.tmpdir / 'pre.png')
        self.loader.preload([p])
        import time; time.sleep(0.3)
        self.assertIsNotNone(self.loader.get(p))


class TestArchive(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_is_archive_zip(self):
        self.assertTrue(is_archive(Path('test.zip')))

    def test_is_archive_tar_gz(self):
        self.assertTrue(is_archive(Path('test.tar.gz')))

    def test_is_archive_image(self):
        self.assertFalse(is_archive(Path('photo.jpg')))

    def test_read_zip_images(self):
        zpath = self.tmpdir / 'test.zip'
        img = Image.new('RGB', (50, 50), 'blue')
        with zipfile.ZipFile(zpath, 'w') as zf:
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            zf.writestr('a/photo.png', buf.getvalue())
            zf.writestr('__MACOSX/junk.png', buf.getvalue())
            zf.writestr('readme.txt', 'hello')
        ar = ArchiveReader(zpath)
        self.assertEqual(len(ar.entries), 1)
        pil = ar.get_image('a/photo.png')
        self.assertIsNotNone(pil)
        self.assertEqual(pil.size, (50, 50))
        self.assertGreater(ar.get_entry_size('a/photo.png'), 0)
        ar.close()


class TestAppLayout(unittest.TestCase):
    def setUp(self):
        self.root = get_root()
        self.app = TViewerApp(self.root)
        self.root.update_idletasks()

    def test_toolbar_parent_is_canvas_wrap(self):
        self.assertEqual(self.app._toolbar.master, self.app._canvas_wrap)

    def test_toolbar_packed_at_bottom(self):
        info = self.app._toolbar.pack_info()
        self.assertEqual(info['side'], 'bottom')

    def test_toolbar_not_placed_floating(self):
        """Toolbar must NOT use place (old bug: overlay on canvas)."""
        self.assertEqual(self.app._toolbar.winfo_manager(), 'pack')

    def test_canvas_packed_with_expand(self):
        info = self.app._canvas.pack_info()
        self.assertTrue(info['expand'])
        self.assertEqual(info['fill'], 'both')

    def test_panel_visible_default(self):
        self.assertTrue(self.app._panel_visible)
        info = self.app._panel.pack_info()
        self.assertEqual(info['side'], 'right')

    def test_panel_toggle(self):
        self.app._toggle_panel()
        self.assertFalse(self.app._panel_visible)
        self.app._toggle_panel()
        self.assertTrue(self.app._panel_visible)

    def test_empty_state_placeholder(self):
        """Empty state must show placeholder text and open button."""
        self.app._images = []
        self.app._show_image()
        items = self.app._canvas.find_all()
        types = [self.app._canvas.type(i) for i in items]
        self.assertIn('text', types)
        self.assertIn('window', types)


class TestAppNavigation(unittest.TestCase):
    def setUp(self):
        self.root = get_root()
        self.tmpdir = Path(tempfile.mkdtemp())
        self.paths = []
        for i in range(5):
            p = make_test_image(self.tmpdir / f'img{i:02d}.png', color=(i*50, 0, 0))
            self.paths.append(p)
        self.app = TViewerApp(self.root)
        self.app._open_path(str(self.paths[0]))
        self.root.update_idletasks()

    def tearDown(self):
        self.app._canvas.delete('all')
        self.app._images = []
        shutil.rmtree(self.tmpdir)

    def test_images_loaded(self):
        self.assertEqual(len(self.app._images), 5)
        self.assertEqual(self.app._index, 0)

    def test_next(self):
        self.app._next()
        self.assertEqual(self.app._index, 1)

    def test_prev_wraps(self):
        self.app._prev()
        self.assertEqual(self.app._index, 4)

    def test_next_wraps(self):
        self.app._index = 4
        self.app._next()
        self.assertEqual(self.app._index, 0)

    def _simulate_click(self, x, y):
        press = MagicMock(); press.x = x; press.y = y
        self.app._on_canvas_click(press)
        release = MagicMock(); release.x = x; release.y = y
        self.app._on_canvas_release(release)

    def _ensure_canvas_width(self):
        """Force a usable canvas width for click zone tests."""
        self.app._canvas.config(width=900, height=600)
        self.root.update_idletasks()
        cw = self.app._canvas.winfo_width()
        if cw < 10:
            self.app._canvas._winfo_width_override = 900
            orig = self.app._canvas.winfo_width
            self.app._canvas.winfo_width = lambda: 900
            self.addCleanup(lambda: setattr(self.app._canvas, 'winfo_width', orig))
            cw = 900
        return cw

    def test_click_left_third_prev(self):
        self.app._index = 2
        cw = self._ensure_canvas_width()
        self._simulate_click(cw // 6, 100)
        self.assertEqual(self.app._index, 1)

    def test_click_right_third_next(self):
        self.app._index = 2
        cw = self._ensure_canvas_width()
        self._simulate_click(cw - cw // 6, 100)
        self.assertEqual(self.app._index, 3)

    def test_click_center_no_nav(self):
        self.app._index = 2
        cw = self._ensure_canvas_width()
        self._simulate_click(cw // 2, 100)
        self.assertEqual(self.app._index, 2)

    def test_drag_no_nav(self):
        self.app._index = 2
        cw = self._ensure_canvas_width()
        press = MagicMock(); press.x = cw // 6; press.y = 100
        self.app._on_canvas_click(press)
        drag = MagicMock(); drag.x = cw // 6 + 50; drag.y = 120
        self.app._drag_move(drag)
        release = MagicMock(); release.x = drag.x; release.y = drag.y
        self.app._on_canvas_release(release)
        self.assertEqual(self.app._index, 2)


class TestAppZoom(unittest.TestCase):
    def setUp(self):
        self.root = get_root()
        self.tmpdir = Path(tempfile.mkdtemp())
        p = make_test_image(self.tmpdir / 'z.png', size=(200, 150))
        self.app = TViewerApp(self.root)
        self.app._open_path(str(p))

    def tearDown(self):
        self.app._canvas.delete('all')
        self.app._images = []
        shutil.rmtree(self.tmpdir)

    def test_default_fit(self):
        self.assertTrue(self.app._fit_mode)

    def test_zoom_100(self):
        self.app._zoom_100()
        self.assertFalse(self.app._fit_mode)

    def test_zoom_fit_back(self):
        self.app._zoom_100()
        self.app._zoom_fit()
        self.assertTrue(self.app._fit_mode)

    def test_toggle(self):
        self.app._toggle_fit()
        self.assertFalse(self.app._fit_mode)
        self.app._toggle_fit()
        self.assertTrue(self.app._fit_mode)


class TestIconButton(unittest.TestCase):
    def test_creates_label(self):
        root = get_root()
        btn = _make_icon_btn(root, "Test", lambda: None)
        self.assertIsInstance(btn, tk.Label)
        self.assertEqual(btn.cget('text'), 'Test')

    def test_hover_colors(self):
        root = get_root()
        btn = _make_icon_btn(root, "X", lambda: None, bg='#111', hover_bg='#222')
        self.assertEqual(btn._base_bg, '#111')
        self.assertEqual(btn._hover_bg, '#222')


if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        if _root:
            _root.destroy()
