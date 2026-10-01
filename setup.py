from setuptools import setup

setup(
    name="jaketts",
    version="1.0.0",
    description="Jake's Local CLI Text-to-Speech tool powered by Kokoro-82M",
    author="Jake",
    py_modules=["jaketts"],
    install_requires=[
        "kokoro>=0.7.0",
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
)
