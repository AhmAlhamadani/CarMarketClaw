import cv2
import requests
import numpy as np
from clawbot.agents.plate_reader import reader # Re-use the global reader instance

def download_image(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        img_array = np.frombuffer(r.content, np.uint8)
        return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception:
        return None

def preprocess(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return gray

def build_vision_context(image_urls):
    images = []
    grayscale = []
    ocr_results = [] # Cache results to prevent running EasyOCR multiple times

    for url in image_urls:
        img = download_image(url)
        if img is None:
            continue
        images.append(img)
        
        gray = preprocess(img)
        grayscale.append(gray)
        
        # Run OCR once here and store the results
        ocr_results.append(reader.readtext(gray))

    return {
        "urls": image_urls,
        "images": images,
        "grayscale": grayscale,
        "ocr": reader,
        "ocr_results": ocr_results
    }