import re
import cv2
import easyocr

# Load once globally
reader = easyocr.Reader(["en"], gpu=False)

# UK format: AA11AAA
UK_PLATE_REGEX = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{3}$")

def normalize_plate(text):
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]", "", text)

    if len(text) != 7:
        return None

    chars = list(text)

    # OCR mistakes -> True letters
    letter_corrections = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"}
    # OCR mistakes -> True numbers
    digit_corrections = {"O": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8"}

    # First 2 letters
    for i in [0, 1]:
        chars[i] = letter_corrections.get(chars[i], chars[i])

    # Middle 2 numbers
    for i in [2, 3]:
        chars[i] = digit_corrections.get(chars[i], chars[i])

    # Last 3 letters
    for i in [4, 5, 6]:
        chars[i] = letter_corrections.get(chars[i], chars[i])

    candidate = "".join(chars)
    return candidate if UK_PLATE_REGEX.match(candidate) else None

def read_plate(vision):
    detections = []

    # FIX: Use the cached OCR results instead of running readtext again
    for results in vision.get("ocr_results", []):
        for result in results:
            _, text, confidence = result
            plate = normalize_plate(text)

            if not plate:
                continue

            print(f"OCR Found: {text} -> Normalized: {plate} (Conf: {confidence:.2f})")
            detections.append((plate, float(confidence)))

    if not detections:
        return {"carplate_ai": None, "carplate_ai_confidence": 0.0}

    # Pick the prediction with highest confidence score
    best_plate = max(detections, key=lambda x: x[1])

    return {
        "carplate_ai": best_plate[0],
        "carplate_ai_confidence": round(best_plate[1], 3)
    }