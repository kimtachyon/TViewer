# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('icon_tviewer.icns', '.')],
    hiddenimports=[
        'PIL._imagingtk', 'PIL.Image', 'PIL.ImageTk',
        'PIL.JpegImagePlugin', 'PIL.PngImagePlugin',
        'PIL.BmpImagePlugin', 'PIL.WebPImagePlugin',
        'PIL.TiffImagePlugin', 'PIL.GifImagePlugin',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon_tviewer.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TViewer',
)

app = BUNDLE(
    coll,
    name='TViewer.app',
    icon='icon_tviewer.icns',
    bundle_identifier='com.tachyon.tviewer',
    info_plist={
        'CFBundleShortVersionString': '1.0.4',
        'CFBundleName': 'TViewer',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        # 이미지 파일 연결 등록
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Image',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Default',
                'LSItemContentTypes': [
                    'public.jpeg',
                    'public.png',
                    'public.tiff',
                    'public.bmp',
                    'public.gif',
                    'public.heic',
                    'public.heif',
                    'org.webmproject.webp',
                ],
            },
            {
                'CFBundleTypeName': 'Archive',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Default',
                'LSItemContentTypes': [
                    'public.zip-archive',
                    'public.tar-archive',
                    'org.gnu.gnu-zip-archive',
                    'public.bzip2-archive',
                    'org.tukaani.xz-archive',
                ],
            }
        ],
        'UTImportedTypeDeclarations': [],
    },
)
