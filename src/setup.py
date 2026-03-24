"""
D3OA — 构建脚本

编译 C 扩展模块:
    cd src && python setup.py build_ext --inplace

打包 EXE (PyInstaller):
    pyinstaller --onefile --windowed --manifest d3oa.manifest src/main.py

嵌入 Manifest 到 EXE (需要 Windows SDK mt.exe):
    mt.exe -manifest d3oa.manifest -outputresource:dist/d3oa.exe;#1
"""

from setuptools import setup, Extension
import os
import sys

# C 扩展: overlay_core
# 链接 user32/gdi32/kernel32，这些都是标准 Windows 系统库
# 不需要额外权限，普通用户即可使用
extra_compile_args = []
extra_link_args = []

if sys.platform == 'win32':
    # MSVC 编译选项
    extra_compile_args = ['/W3', '/DUNICODE', '/D_UNICODE']
    # manifest 资源文件（用于嵌入 UAC 清单）
    # 需要在项目根目录创建 d3oa.rc 文件引用 manifest

overlay_core = Extension(
    'overlay_core',
    sources=[os.path.join('src', 'overlay_core.c')],
    libraries=['user32', 'gdi32', 'kernel32', 'dwmapi'],
    define_macros=[
        ('UNICODE', None),
        ('_UNICODE', None),
        ('WINVER', '0x0A00'),          # Windows 10
        ('_WIN32_WINNT', '0x0A00'),    # Windows 10
    ],
    extra_compile_args=extra_compile_args,
    extra_link_args=extra_link_args,
)

setup(
    name='d3-overlay',
    version='1.0.0',
    description='Diablo 3 Overlay Assistant — 透明叠加增强助手',
    long_description=open(os.path.join(os.path.dirname(__file__), '..', 'README.md'), encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    author='D3OA Community',
    license='MIT',
    url='https://github.com/caozuohua/d3-overlay',
    ext_modules=[overlay_core],
    python_requires='>=3.10',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 3',
        'Programming Language :: C',
        'Topic :: Games/Entertainment',
    ],
    # 包含 manifest 文件到分发包
    data_files=[
        ('', ['../d3oa.manifest']),
    ],
    package_dir={'': 'src'},
    py_modules=[
        'main', 'config', 'overlay', 'game_monitor',
        'data_provider', 'renderer', 'plugin_manager', 'hotkey',
    ],
)
