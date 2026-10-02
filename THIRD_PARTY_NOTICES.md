# Third-party licensing notes

JakeTTS's own source code is licensed under 0BSD. That license does **not** apply to third-party software, native libraries, dictionaries, or model assets used by JakeTTS. Those components retain their own licenses.

This document highlights the licensing points most relevant to redistribution and downstream development. It is a practical project note, not legal advice and not a substitute for reading the authoritative upstream license files.

## Model and inference runtime

| Component | License / licensing note | Upstream |
| --- | --- | --- |
| Kokoro-82M model weights and voice assets | Apache-2.0 according to the Kokoro-82M model repository | https://huggingface.co/hexgrad/Kokoro-82M |
| `kokoro-onnx` | MIT | https://github.com/thewh1teagle/kokoro-onnx |
| ONNX Runtime | MIT (with its own third-party notices) | https://github.com/microsoft/onnxruntime |
| `misaki-fork` | Apache-2.0 | https://pypi.org/project/misaki-fork/ |

## Components that require special attention for redistribution

### `phonemizer` and eSpeak NG

`kokoro-onnx` depends on `phonemizer`, which is licensed GPL-3.0-or-later. The eSpeak NG library used by that phonemization path is also GPLv3-or-later. `espeakng-loader` packages/loads an eSpeak NG shared library for supported platforms.

This is the most important licensing consideration for anyone building a proprietary or closed-source product from JakeTTS. Do **not** assume that JakeTTS's 0BSD license permits a proprietary redistribution of the complete current runtime stack. Evaluate the GPL components and your distribution/linking architecture separately, replace them with suitably licensed alternatives, or obtain qualified legal advice before distributing a proprietary product.

Upstream references:

- https://pypi.org/project/phonemizer/
- https://github.com/espeak-ng/espeak-ng
- https://github.com/thewh1teagle/espeakng-loader

### PySide6 / Qt

`PySide6-Essentials` is distributed under LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only, with Qt commercial licensing also available. Proprietary applications can have obligations under the LGPL route; a Qt commercial license is a separate option. Follow Qt's current licensing guidance for the way you distribute your application.

Upstream references:

- https://doc.qt.io/qtforpython-6/
- https://pypi.org/project/PySide6-Essentials/

### libsndfile

The Python `soundfile` package is BSD-3-Clause, but it uses libsndfile, which is LGPL-licensed. Redistribution of a bundled libsndfile binary therefore has separate LGPL obligations.

Upstream reference:

- https://pypi.org/project/soundfile/

## Other notable components

The current runtime also includes permissively licensed components such as fugashi (MIT; bundled MeCab under BSD terms), UniDic Lite code (MIT/WTFPL) and UniDic data (BSD terms), pyopenjtalk (MIT with Modified-BSD/Open-JTalk components), NumPy (BSD/MIT/other permissive notices), sounddevice (MIT), jieba (MIT), ordered-set (MIT), pypinyin/pypinyin-dict (MIT), and other transitive packages with their own notices.

Authoritative upstream license files and the license metadata included with the exact packages you distribute control. When redistributing a binary bundle or Homebrew bottle, preserve required copyright/license notices and satisfy any source, relinking, or other obligations imposed by the licenses of the components actually included.
