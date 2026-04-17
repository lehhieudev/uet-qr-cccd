import sys
import os
import cv2
import numpy as np
import pandas as pd
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QLabel, QTableWidget, QTableWidgetItem, QProgressBar, QMessageBox
)
from pyzbar.pyzbar import decode as zbar_decode

# ================= ENGINE XỬ LÝ QR =================
class CCCDScannerEngine:
    def __init__(self):
        self.use_wechat = False
        # Đường dẫn tới thư mục models (để cùng cấp với file code)
        base_path = os.path.dirname(os.path.abspath(__file__))
        model_dir = os.path.join(base_path, "models")
        
        # Danh sách các file model cần thiết
        files = [
            os.path.join(model_dir, "detect.prototxt"),
            os.path.join(model_dir, "detect.caffemodel"),
            os.path.join(model_dir, "sr.prototxt"),
            os.path.join(model_dir, "sr.caffemodel")
        ]

        # Kiểm tra sự tồn tại của model
        if all(os.path.exists(f) for f in files):
            try:
                self.detector = cv2.wechat_qrcode_WeChatQRCode(files[0], files[1], files[2], files[3])
                self.use_wechat = True
                print("--- Đã kích hoạt WeChatQRCode Model thành công ---")
            except Exception as e:
                print(f"Lỗi khởi tạo WeChatQRCode: {e}")
                self.detector = cv2.QRCodeDetector()
        else:
            print("--- CẢNH BÁO: Không tìm thấy model WeChat, dùng OpenCV mặc định ---")
            self.detector = cv2.QRCodeDetector()

    def preprocess(self, img):
        """Các biến thể xử lý ảnh để tối ưu khả năng đọc"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Biến thể 1: Ảnh gốc xám
        yield gray
        
        # Biến thể 2: Tăng tương phản mạnh (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        yield clahe.apply(gray)
        
        # Biến thể 3: Làm sắc nét (Sharpen)
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        yield cv2.filter2D(gray, -1, kernel)

    def scan(self, img_path):
        try:
            # Đọc ảnh hỗ trợ unicode path (phòng hờ tên folder tiếng Việt)
            img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None: return None

            h, w = img.shape[:2]
            
            # Các vùng cần quét: Toàn bộ ảnh -> 1/2 trên (ảnh ghép) -> Góc trên phải (vị trí QR)
            crops = [
                img,
                img[0:int(h/2), :],
                img[0:int(h*0.4), int(w*0.5):w]
            ]

            for crop in crops:
                if crop.size == 0: continue
                
                for processed in self.preprocess(crop):
                    # Thử ở kích thước gốc và phóng to 2 lần (QR CCCD thường rất bé)
                    for scale in [1, 2]:
                        target = processed
                        if scale > 1:
                            target = cv2.resize(processed, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                        
                        # 1. Ưu tiên WeChat
                        if self.use_wechat:
                            res, _ = self.detector.detectAndDecode(target)
                            if res and len(res[0]) > 0:
                                return res[0]
                        
                        # 2. Fallback sang Zbar (Rất mạnh với QR bị méo)
                        zbar_res = zbar_decode(target)
                        if zbar_res:
                            return zbar_res[0].data.decode('utf-8', errors='ignore')
            
            return None
        except Exception as e:
            print(f"Lỗi khi quét file {img_path}: {e}")
            return None

def parse_qr_data(text):
    if not text: return {}
    # Format CCCD: Số ID|Số cũ|Họ tên|Ngày sinh|Giới tính|Địa chỉ|Ngày cấp
    parts = [p.strip() for p in text.split('|')]
    fields = ["Số CCCD", "Số CMND cũ", "Họ và tên", "Ngày sinh", "Giới tính", "Địa chỉ thường trú", "Ngày cấp"]
    return {fields[i]: parts[i] if i < len(parts) else "" for i, f in enumerate(fields)}

# ================= GIAO DIỆN PHẦN MỀM =================
class BIDVScannerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.engine = CCCDScannerEngine()
        self.files = []
        self.results = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle("BIDV - Hệ thống Quét QR CCCD Offline")
        self.resize(1100, 700)
        
        layout = QVBoxLayout()
        
        self.info_label = QLabel("Vui lòng chọn các file ảnh CCCD (Scan hoặc Chụp)")
        self.info_label.setStyleSheet("font-size: 14px; color: #555;")
        layout.addWidget(self.info_label)

        self.btn_select = QPushButton("📂 Chọn danh sách ảnh")
        self.btn_select.setMinimumHeight(50)
        self.btn_select.clicked.connect(self.select_files)
        layout.addWidget(self.btn_select)

        self.btn_run = QPushButton("🚀 Bắt đầu nhận diện QR")
        self.btn_run.setMinimumHeight(50)
        self.btn_run.setStyleSheet("background-color: #00732E; color: white; font-weight: bold; font-size: 16px;")
        self.btn_run.clicked.connect(self.run_process)
        layout.addWidget(self.btn_run)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.table = QTableWidget()
        layout.addWidget(self.table)

        self.btn_export = QPushButton("📥 Xuất kết quả ra Excel")
        self.btn_export.clicked.connect(self.export_to_excel)
        layout.addWidget(self.btn_export)

        self.setLayout(layout)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn ảnh", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if files:
            self.files = files
            self.info_label.setText(f"Đã chọn: {len(files)} ảnh")

    def run_process(self):
        if not self.files:
            QMessageBox.warning(self, "Lỗi", "Chưa có ảnh nào được chọn!")
            return

        self.results = []
        self.progress.setValue(0)

        for i, file_path in enumerate(self.files):
            raw_data = self.engine.scan(file_path)
            
            row = {"Tên file": os.path.basename(file_path)}
            if raw_data:
                row.update(parse_qr_data(raw_data))
                row["Kết quả"] = "Thành công"
            else:
                row["Kết quả"] = "Không tìm thấy mã QR"
            
            self.results.append(row)
            self.progress.setValue(int((i + 1) / len(self.files) * 100))
            QApplication.processEvents()

        self.update_table()

    def update_table(self):
        if not self.results: return
        df = pd.DataFrame(self.results)
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)

        for i in range(len(df)):
            for j in range(len(df.columns)):
                val = str(df.iat[i, j]) if pd.notna(df.iat[i, j]) else ""
                self.table.setItem(i, j, QTableWidgetItem(val))
        self.table.resizeColumnsToContents()

    def export_to_excel(self):
        if not self.results: return
        output_name = f"KetQua_CCCD_{datetime.now().strftime('%H%M%S')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Lưu file Excel", output_name, "Excel (*.xlsx)")
        if path:
            pd.DataFrame(self.results).to_excel(path, index=False)
            QMessageBox.information(self, "Thông báo", f"Đã xuất file thành công tại:\n{path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Cài đặt style cho hiện đại hơn
    app.setStyle('Fusion')
    window = BIDVScannerApp()
    window.show()
    sys.exit(app.exec_())