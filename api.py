from fastapi import FastAPI, UploadFile, File
from cccd_engine import process_image

app = FastAPI()

@app.post("/cccd")
async def read_cccd(file: UploadFile = File(...)):
    img_bytes = await file.read()
    result = process_image(img_bytes)
    return result
