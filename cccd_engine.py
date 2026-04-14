    import cv2
import numpy as np
from PIL import Image
import io
from pyzbar.pyzbar import decode as zbar_decode
from qreader import QReader
from paddleocr import PaddleOCR

# init
qreader = QReader()
ocr = PaddleOCR(use_angle_cls=True, lang='vi')

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
        img[0:int(h*0.4), int(w*0.6):w],  # top-right
        img[0:int(h*0.5), int(w*0.5):w],
    ]

# ================= PREPROCESS =================
def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
    sharp = cv2.filter2D(gray, -1, kernel)

    clahe = cv2.createCLAHE(3.0, (8,8))
    enhanced = clahe.apply(sharp)

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
    decoded = qreader.detect_and_decode(image=pil)
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

# ================= OCR FALLBACK =================
def ocr_extract(img_bytes):
    pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = np.array(pil)

    result = ocr.ocr(img, cls=True)

    texts = []
    for line in result:
        for word in line:
            texts.append(word[1][0])

    return " ".join(texts)

# ================= PARSE =================
def parse_qr(text):
    if not text:
        return {}

    parts = [fix_encoding(p.strip()) for p in text.split('|')]

    fields = [
        "cccd", "cmnd_cu", "name",
        "dob", "gender", "address", "issue_date"
    ]

    return {f: parts[i] if i < len(parts) else "" for i, f in enumerate(fields)}

# ================= MAIN PIPELINE =================
def process_image(img_bytes):
    qr = decode_qr(img_bytes)

    if qr:
        return {
            "type": "QR",
            "raw": qr,
            "data": parse_qr(qr)
        }

    # fallback OCR
    text = ocr_extract(img_bytes)

    return {
        "type": "OCR",
        "raw": text,
        "data": {}  # bạn có thể parse thêm nếu cần
    }
