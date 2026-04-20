import sys
import os
import cv2
import numpy as np
import pandas as pd
from datetime import datetime
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QLabel, QTableWidget, QTableWidgetItem, QProgressBar, QMessageBox
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt
from pyzbar.pyzbar import decode as zbar_decode



def resource_path(relative_path):
    import sys, os
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
# ================= ENGINE XỬ LÝ QR =================
class CCCDScannerEngine:
    
    def __init__(self):
        self.use_wechat = False
        #base_path = os.path.dirname(os.path.abspath(__file__))
        base_path = resource_path("")
        model_dir = os.path.join(base_path, "models")
        
        files = [
            os.path.join(model_dir, "detect.prototxt"),
            os.path.join(model_dir, "detect.caffemodel"),
            os.path.join(model_dir, "sr.prototxt"),
            os.path.join(model_dir, "sr.caffemodel")
        ]

        if all(os.path.exists(f) for f in files):
            try:
                self.detector = cv2.wechat_qrcode_WeChatQRCode(files[0], files[1], files[2], files[3])
                self.use_wechat = True
            except:
                self.detector = cv2.QRCodeDetector()
        else:
            self.detector = cv2.QRCodeDetector()

    def scan_with_info(self, img):
        """Trả về (nội dung_qr, tọa_độ_vẽ)"""
        if img is None: return None, None
        
        # Thử với WeChat (ưu tiên cao nhất)
        if self.use_wechat:
            res, points = self.detector.detectAndDecode(img)
            if res and len(res[0]) > 0:
                return res[0], points[0]

        # Thử với Zbar
        zbar_res = zbar_decode(img)
        if zbar_res:
            points = np.array([[p.x, p.y] for p in zbar_res[0].polygon], dtype=np.float32)
            return zbar_res[0].data.decode('utf-8', errors='ignore'), points
            
        return None, None

# ================= GIAO DIỆN PHẦN MỀM =================
class BIDVScannerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.engine = CCCDScannerEngine()
        self.files = []
        self.results = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Căn cước QR Scanner - CN Bà Rịa | hieulh2 | Desktop v1.0")
        self.resize(1200, 850)
        # Layout chính (Dọc)
        main_layout = QVBoxLayout()
        
        # Layout nội dung (Ngang: Trái là Ảnh, Phải là Bảng)
        content_layout = QHBoxLayout()

        # --- CỘT TRÁI: HIỂN THỊ ẢNH ---
        left_panel = QVBoxLayout()
        self.image_label = QLabel("Hình ảnh xem trước")
        self.image_label.setFixedSize(450, 450)
        self.image_label.setStyleSheet("border: 2px dashed #00732E; background-color: #f0f0f0;")
        self.image_label.setAlignment(Qt.AlignCenter)
        left_panel.addWidget(self.image_label)
        
        self.info_label = QLabel("Sẵn sàng quét...")
        self.info_label.setStyleSheet("font-weight: bold; color: #00732E;")
        left_panel.addWidget(self.info_label)
        left_panel.addStretch()

        # --- CỘT PHẢI: BẢNG DỮ LIỆU ---
        self.table = QTableWidget()
        
        content_layout.addLayout(left_panel, 1)
        content_layout.addWidget(self.table, 2)

        # --- ĐIỀU KHIỂN ---
        self.btn_select = QPushButton("📂 Chọn danh sách ảnh")
        self.btn_select.setMinimumHeight(40)
        self.btn_select.clicked.connect(self.select_files)

        self.btn_run = QPushButton("🚀 Bắt đầu nhận diện QR")
        self.btn_run.setMinimumHeight(50)
        self.btn_run.setStyleSheet("background-color: #00732E; color: white; font-weight: bold;")
        self.btn_run.clicked.connect(self.run_process)

        self.progress = QProgressBar()

        self.btn_export = QPushButton("📥 Xuất Excel")
        self.btn_export.clicked.connect(self.export_to_excel)

        # Add các phần vào main layout
        main_layout.addWidget(self.btn_select)
        main_layout.addLayout(content_layout)
        main_layout.addWidget(self.progress)
        main_layout.addWidget(self.btn_run)
        main_layout.addWidget(self.btn_export)

        self.setLayout(main_layout)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn ảnh", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if files:
            self.files = files
            self.info_label.setText(f"Đã chọn: {len(files)} ảnh")

    def display_image(self, img):
        """Chuyển đổi OpenCV image sang QPixmap để hiện lên giao diện"""
        qformat = QImage.Format_RGB888
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = img_rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(img_rgb.data, w, h, bytes_per_line, qformat)
        pixmap = QPixmap.fromImage(q_img)
        # Scale ảnh cho vừa khung hiển thị mà không méo
        self.image_label.setPixmap(pixmap.scaled(self.image_label.width(), self.image_label.height(), Qt.KeepAspectRatio))
    def run_process(self):
        if not self.files:
            QMessageBox.warning(self, "Lỗi", "Chưa có ảnh nào được chọn!")
            return

        # --- BƯỚC 1: CLEAR DỮ LIỆU CŨ ---
        self.results = []           # Xóa danh sách kết quả cũ
        self.table.setRowCount(0)   # Xóa toàn bộ các dòng trên lưới hiển thị
        self.progress.setValue(0)   # Reset thanh tiến trình
        
        # Cập nhật giao diện ngay lập tức để người dùng thấy lưới đã trống
        QApplication.processEvents()

        for i, file_path in enumerate(self.files):
            # 1. Đọc ảnh
            img = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None: continue

            # 2. Quét QR
            raw_data, points = self.engine.scan_with_info(img)
            
            # 3. Vẽ khung (Giữ nguyên logic cũ của anh)
            display_img = img.copy()
            if points is not None:
                pts = points.astype(int)
                for j in range(len(pts)):
                    cv2.line(display_img, tuple(pts[j]), tuple(pts[(j+1)%len(pts)]), (0, 115, 46), 5)
                cv2.putText(display_img, "QR DETECTED", (pts[0][0], pts[0][1] - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 115, 46), 3)

            # 4. Hiển thị ảnh và thông tin file đang xử lý
            self.display_image(display_img)
            self.info_label.setText(f"Đang xử lý ({i+1}/{len(self.files)}): {os.path.basename(file_path)}")
            
            # 5. Lưu kết quả
            row = {"Tên file": os.path.basename(file_path)}
            if raw_data:
                row.update(self.parse_qr_data(raw_data))
                row["Kết quả"] = "Thành công"
            else:
                row["Kết quả"] = "Thất bại"
            
            self.results.append(row)
            self.progress.setValue(int((i + 1) / len(self.files) * 100))
            
            # Đẩy cập nhật lên màn hình và tạm dừng 2 giây để quan sát
            QApplication.processEvents()
            #time.sleep(0.5)  # Giảm thời gian chờ để tăng tốc quá trình

        # --- BƯỚC cuối: HIỆN LẠI DỮ LIỆU MỚI LÊN LƯỚI ---
        self.update_table()
        self.info_label.setText("✅ Hoàn thành quét danh sách!")

    def parse_qr_data(self, text):
        parts = [p.strip() for p in text.split('|')]
        fields = ["Số CCCD", "Số CMND cũ", "Họ và tên", "Ngày sinh", "Giới tính", "Địa chỉ", "Ngày cấp"]
        return {fields[i]: parts[i] if i < len(parts) else "" for i, f in enumerate(fields)}

    def update_table(self):
        if not self.results: return
        df = pd.DataFrame(self.results)
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)
        for i in range(len(df)):
            for j in range(len(df.columns)):
                self.table.setItem(i, j, QTableWidgetItem(str(df.iat[i, j])))
        self.table.resizeColumnsToContents()

    def export_to_excel(self):
        if not self.results: return
        path, _ = QFileDialog.getSaveFileName(self, "Lưu file", f"KetQua_{datetime.now().strftime('%H%M%S')}.xlsx", "Excel (*.xlsx)")
        if path:
            pd.DataFrame(self.results).to_excel(path, index=False)
            QMessageBox.information(self, "OK", "Đã lưu file!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = BIDVScannerApp()
    window.show()
    sys.exit(app.exec_())