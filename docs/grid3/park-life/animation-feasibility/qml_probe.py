import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtCore import QByteArray, QUrl
app = QGuiApplication(sys.argv)
eng = QQmlEngine()
for src in ["import QtQuick\nimport Qt.labs.lottieqt\nItem { LottieAnimation {} }",
            "import QtQuick\nimport QtQuick.VectorImage\nItem { VectorImage {} }"]:
    c = QQmlComponent(eng); c.setData(QByteArray(src.encode()), QUrl())
    print(src.splitlines()[1], "->", "OK" if c.isReady() else [e.toString() for e in c.errors()])
