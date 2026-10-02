from pathlib import Path
from setuptools import setup

ROOT = Path(__file__).parent
README = (ROOT / "README.md").read_text(encoding="utf-8")

setup(
    name="jaketts",
    version="1.0.10",
    description="Local macOS text-to-speech powered by Kokoro-82M via ONNX Runtime",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Jake",
    url="https://github.com/ofalltrades/jaketts",
    project_urls={
        "Source": "https://github.com/ofalltrades/jaketts",
    },
    license="0BSD",
    license_files=["LICENSE", "THIRD_PARTY_NOTICES.md"],
    py_modules=["jaketts"],
    install_requires=[
        "PySide6-Essentials>=6.8,<7",
        "kokoro-onnx==0.6.1",
        "misaki-fork==0.9.6",
        "fugashi>=1.4.0",
        "jaconv>=0.4.0",
        "mojimoji>=0.0.13",
        "pyopenjtalk>=0.4.1",
        "unidic-lite>=1.0.8",
        "cn2an>=0.5.23",
        "jieba>=0.42.1",
        "ordered-set>=4.1.0",
        "pypinyin>=0.55.0",
        "pypinyin-dict>=0.9.0",
        "sounddevice>=0.5.1",
        "soundfile>=0.13.0",
        "numpy>=2.0.2,<3.0.0",
        "tqdm>=4.65.0",
    ],
    entry_points={
        "console_scripts": [
            "jaketts=jaketts:main",
            "jtts=jaketts:main",
        ],
    },
    python_requires=">=3.10,<3.13",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Environment :: MacOS X",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
    ],
)
