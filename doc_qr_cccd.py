import streamlit as st
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import io
from pyzbar.pyzbar import decode as zbar_decode
from qreader import QReader
import easyocr
from datetime import datetime

st.set_page_config(page_title="CCCD Scanner PRO", layout="wide")
st.title("🔍 Đọc QR CCCD (Production - Streamlit)")

# ================= INIT =================
@st.cache_resource
def init():
    return QReader(), easyocr.Reader(['vi', 'en'], gpu=False)

qreader, ocr_reader = init()

# ================= FIX ENCODING =================
def fix_encoding(text):
    if not text:
        return ""
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

# ================= CROP QR =================
def crop_regions(img):
    h, w = img.shape[:2]
    return [
        img,
        img[0:int(h*0.4), int(w*0.6):w],  # top-right CCCD
        img[0:int(h*0.5), int(w*0.5):w],
    ]

# ================= PREPROCESS =================
def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # sharpen
    kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
    sharp = cv2.filter2D(gray, -1, kernel)

    # contrast
    clahe = cv2.createCLAHE(3.0, (8,8))
    enhanced = clahe.apply(sharp)

    # resize
    resized = cv2.resize(enhanced, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    return resized

# ================= QR DECODE =================
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

    # QReader
    decoded = qreader.detect_and_decode(image=cv_img)

    if decoded and decoded[0]:
        return fix_encoding(decoded[0])

    # multi-crop
    for crop in crop_regions(cv_img):
        data = try_decode(crop)
        if data:
            return fix_encoding(data)

    # preprocess
    for crop in crop_regions(cv_img):
        p = preprocess(crop)
        data = try_decode(p)
        if data:
            return fix_encoding(data)

    return None

# ================= OCR =================
def ocr_extract(img_bytes):
    pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = np.array(pil)

    results = ocr_reader.readtext(img)
    texts = [r[1] for r in results]

    return " ".join(texts)

# ================= PARSE =================
def parse_qr(text):
    if not text:
        return {}

    parts = [fix_encoding(p.strip()) for p in text.split('|')]

    fields = [
        "Số CCCD",
        "Số CMND cũ",
        "Họ và tên",
        "Ngày sinh",
        "Giới tính",
        "Địa chỉ",
        "Ngày cấp"
    ]

    return {f: parts[i] if i < len(parts) else "" for i, f in enumerate(fields)}

# ================= UI =================
uploaded_files = st.file_uploader(
    "📸 Upload ảnh CCCD",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if st.button("🚀 Xử lý", use_container_width=True):

    if not uploaded_files:
        st.warning("⚠️ Vui lòng chọn ảnh")
        st.stop()

    results = []
    failed = []

    progress = st.progress(0)
    status = st.empty()

    for i, file in enumerate(uploaded_files):
        status.text(f"Đang xử lý: {file.name} ({i+1}/{len(uploaded_files)})")

        img_bytes = file.getvalue()
        qr = decode_qr(img_bytes)

        row = {
            "Tên file": file.name,
            "QR Raw": qr or ""
        }

        if qr:
            row.update(parse_qr(qr))
            row["Trạng thái"] = "✅ QR OK"
        else:
            ocr_text = ocr_extract(img_bytes)
            row["OCR Text"] = ocr_text
            row["Trạng thái"] = "⚠️ OCR fallback"
            failed.append(file.name)

        results.append(row)
        progress.progress((i+1)/len(uploaded_files))

    df = pd.DataFrame(results)

    order = [
        "Tên file", "QR Raw",
        "Số CCCD", "Số CMND cũ",
        "Họ và tên", "Ngày sinh",
        "Giới tính", "Địa chỉ",
        "Ngày cấp",
        "OCR Text",
        "Trạng thái"
    ]

    df = df.reindex(columns=order)

    st.success(f"✅ Xử lý xong {len(uploaded_files)} ảnh")

    if failed:
        st.warning(f"⚠️ {len(failed)} ảnh dùng OCR fallback")

    st.dataframe(df, use_container_width=True, height=500)

    # export excel
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    st.download_button(
        "📥 Tải Excel",
        output,
        f"cccd_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        use_container_width=True
    )

st.info("💡 Mẹo: QR nằm góc trên phải, chụp rõ và không lóa để đạt kết quả tốt nhất")
