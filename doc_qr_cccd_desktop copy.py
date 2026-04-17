import sys
import os
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import io
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QLabel, QTableWidget, QTableWidgetItem, QProgressBar, QMessageBox
)

from pyzbar.pyzbar import decode as zbar_decode

# ================= FUNCTIONS =================
def fix_encoding(text):
    if not text:
        return ""
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text


def crop_regions(img):
    h, w = img.shape[:2]
    return [
        img,
        img[0:int(h*0.4), int(w*0.6):w],
        img[0:int(h*0.5), int(w*0.5):w],
    ]


def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
    sharp = cv2.filter2D(gray, -1, kernel)
    clahe = cv2.createCLAHE(3.0, (8,8))
    enhanced = clahe.apply(sharp)
    resized = cv2.resize(enhanced, None, fx=3, fy=3)
    return resized


def try_decode(img):
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(img)
    if data:
        return data

    barcodes = zbar_decode(img)
    for b in barcodes:
        return b.data.decode('utf-8', errors='ignore')

    return None


def decode_qr(img_bytes):
    pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    cv_img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    for crop in crop_regions(cv_img):
        data = try_decode(crop)
        if data:
            return fix_encoding(data)

    for crop in crop_regions(cv_img):
        p = preprocess(crop)
        data = try_decode(p)
        if data:
            return fix_encoding(data)

    return None


def parse_qr(text):
    if not text:
        return {}

    parts = [fix_encoding(p.strip()) for p in text.split('|')]

    fields = [
        "Số CCCD", "Số CMND cũ", "Họ và tên",
        "Ngày sinh", "Giới tính", "Địa chỉ", "Ngày cấp"
    ]

    return {f: parts[i] if i < len(parts) else "" for i, f in enumerate(fields)}


# ================= UI =================
class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CCCD Scanner Desktop")
        self.resize(1000, 600)

        self.layout = QVBoxLayout()

        self.label = QLabel("Chưa chọn file")
        self.layout.addWidget(self.label)

        self.btn_select = QPushButton("📸 Chọn ảnh")
        self.btn_select.clicked.connect(self.select_files)
        self.layout.addWidget(self.btn_select)

        self.btn_process = QPushButton("🚀 Xử lý")
        self.btn_process.clicked.connect(self.process)
        self.layout.addWidget(self.btn_process)

        self.progress = QProgressBar()
        self.layout.addWidget(self.progress)

        self.table = QTableWidget()
        self.layout.addWidget(self.table)

        self.btn_export = QPushButton("📥 Xuất Excel")
        self.btn_export.clicked.connect(self.export_excel)
        self.layout.addWidget(self.btn_export)

        self.setLayout(self.layout)

        self.files = []
        self.results = []

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn ảnh", "", "Images (*.png *.jpg *.jpeg)")
        if files:
            self.files = files
            self.label.setText(f"Đã chọn {len(files)} file")

    def process(self):
        if not self.files:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn file")
            return

        self.results = []

        for i, file in enumerate(self.files):
            with open(file, 'rb') as f:
                img_bytes = f.read()

            qr = decode_qr(img_bytes)

            row = {
                "Tên file": os.path.basename(file),
                "QR Raw": qr or ""
            }

            if qr:
                row.update(parse_qr(qr))
                row["Trạng thái"] = "QR OK"
            else:
                row["Trạng thái"] = "❌ Không đọc được QR"

            self.results.append(row)

            self.progress.setValue(int((i+1)/len(self.files)*100))
            QApplication.processEvents()

        self.show_table()

    def show_table(self):
        df = pd.DataFrame(self.results)
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)

        for i in range(len(df)):
            for j in range(len(df.columns)):
                self.table.setItem(i, j, QTableWidgetItem(str(df.iat[i, j])))

    def export_excel(self):
        if not self.results:
            return

        path, _ = QFileDialog.getSaveFileName(self, "Lưu file", "cccd.xlsx", "Excel (*.xlsx)")
        if path:
            pd.DataFrame(self.results).to_excel(path, index=False)
            QMessageBox.information(self, "OK", "Đã lưu file")


# ================= RUN =================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec_())