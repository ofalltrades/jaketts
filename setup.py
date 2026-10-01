from pathlib import Path
from setuptools import setup

ROOT = Path(__file__).parent
README = (ROOT / "README.md").read_text(encoding="utf-8")

setup(
    name="jaketts",
    version="1.0.7",
    description="Jake's local CLI text-to-speech tool powered by Kokoro-82M",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Jake",
    url="https://github.com/ofalltrades/jaketts",
    project_urls={
        "Source": "https://github.com/ofalltrades/jaketts",
        "Issues": "https://github.com/ofalltrades/jaketts/issues",
    },
    license="MIT",
    license_files=["LICENSE"],
    py_modules=["jaketts"],
    install_requires=[
        "kokoro>=0.7.0",
        "misaki[ja,zh]>=0.9.4",
        "sounddevice>=0.4.0",
        "soundfile>=0.4.0",
        "numpy>=1.20.0,<2.0.0",
        "torch>=2.0.0",
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
        "Development Status :: 4 - Beta",
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
