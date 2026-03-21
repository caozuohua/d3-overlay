"""
D3OA — 构建脚本

编译 C 扩展模块: python setup.py build_ext --inplace
打包 EXE: pyinstaller --onefile --windowed src/main.py
"""

from setuptools import setup, Extension
import os

# C 扩展: overlay_core
overlay_core = Extension(
    'overlay_core',
    sources=[os.path.join('src', 'overlay_core.c')],
    libraries=['user32', 'gdi32', 'kernel32'],
    define_macros=[('UNICODE', None), ('_UNICODE', None)],
)

setup(
    name='d3-overlay',
    version='1.0.0',
    description='Diablo 3 Overlay Assistant — 透明叠加增强助手',
    author='D3OA Community',
    license='MIT',
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
)
