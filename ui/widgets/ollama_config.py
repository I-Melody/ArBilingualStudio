# -*- coding: utf-8 -*-
import json
import urllib.request
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from core import config as app_config


class OllamaConfigWidget(QWidget):
    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.setObjectName("ConfigFrame")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        layout.addWidget(QLabel("🤖 本地 Ollama 模型:", self, objectName="ConfigLabel"))
        self.combo_ollama_model = QComboBox(self)
        self.combo_ollama_model.setObjectName("ConfigCombo")
        self.combo_ollama_model.setMinimumWidth(180)
        self.combo_ollama_model.currentTextChanged.connect(self._on_config_changed)
        layout.addWidget(self.combo_ollama_model)

        self.btn_refresh = QPushButton("🔄 扫描可用模型", self)
        self.btn_refresh.setObjectName("ConfigBtn")
        self.btn_refresh.clicked.connect(self.scan_local_ollama_tags)
        layout.addWidget(self.btn_refresh)

        layout.addSpacing(15)

        layout.addWidget(QLabel("🌡️ 创造力温度 (Temp):", self, objectName="ConfigLabel"))
        self.combo_ollama_temp = QComboBox(self)
        self.combo_ollama_temp.setObjectName("ConfigCombo")
        self.combo_ollama_temp.addItems(["0.0 (严谨/推荐)", "0.1", "0.2", "0.5 (温和)", "0.8 (发散)", "1.0 (高创意)"])
        self.combo_ollama_temp.currentTextChanged.connect(self._on_config_changed)
        layout.addWidget(self.combo_ollama_temp)

        layout.addStretch()

    def load_saved_settings(self):
        saved_model = app_config.get_ollama_model()
        saved_temp = str(app_config.get_ollama_temp())
        for i in range(self.combo_ollama_temp.count()):
            if saved_temp in self.combo_ollama_temp.itemText(i):
                self.combo_ollama_temp.setCurrentIndex(i)
                break

    def scan_local_ollama_tags(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳ 扫描中...")
        QTimer.singleShot(100, self._exec_ollama_scan)

    def _exec_ollama_scan(self):
        models_found = []
        try:
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with opener.open(req, timeout=1.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    models = data.get("models", [])
                    for m in models:
                        name = m.get("name")
                        if name:
                            models_found.append(name)
        except Exception:
            pass

        self.combo_ollama_model.blockSignals(True)
        self.combo_ollama_model.clear()
        if models_found:
            self.combo_ollama_model.addItems(models_found)
            saved_model = app_config.get_ollama_model()
            idx = self.combo_ollama_model.findText(saved_model)
            if idx != -1:
                self.combo_ollama_model.setCurrentIndex(idx)
        else:
            self.combo_ollama_model.addItem("⚠️ 未检测到运行中的Ollama服务")
        self.combo_ollama_model.blockSignals(False)

        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("🔄 扫描可用模型")

    def _on_config_changed(self):
        current_model = self.combo_ollama_model.currentText()
        if "未检测到" in current_model or not current_model:
            return
        temp_text = self.combo_ollama_temp.currentText()
        temp_val = "0.1"
        try:
            temp_val = temp_text.split(" ")[0]
        except Exception:
            pass
        app_config.set_ollama_model(current_model)
        app_config.set_ollama_temp(float(temp_val))
