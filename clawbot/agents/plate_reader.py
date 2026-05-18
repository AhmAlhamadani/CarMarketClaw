import re
import cv2
import easyocr


# Load once
reader = easyocr.Reader(
    ["en"],
    gpu=False
)


# UK format: AA11AAA
UK_PLATE_REGEX = re.compile(
    r"^[A-Z]{2}[0-9]{2}[A-Z]{3}$"
)


def preprocess_image(img):

    gray = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.resize(
        gray,
        None,
        fx=2,
        fy=2
    )

    return gray


def normalize_plate(text):

    text = text.upper()

    text = re.sub(
        r"[^A-Z0-9]",
        "",
        text
    )

    if len(text) != 7:
        return None

    chars = list(text)

    # OCR → letters
    letter_corrections = {
        "0": "O",
        "1": "I",
        "2": "Z",
        "5": "S",
        "8": "B"
    }

    # OCR → numbers
    digit_corrections = {
        "O": "0",
        "Q": "0",
        "I": "1",
        "L": "1",
        "Z": "2",
        "S": "5",
        "B": "8"
    }

    # First 2 letters
    for i in [0, 1]:

        chars[i] = letter_corrections.get(
            chars[i],
            chars[i]
        )

    # Middle 2 numbers
    for i in [2, 3]:

        chars[i] = digit_corrections.get(
            chars[i],
            chars[i]
        )

    # Last 3 letters
    for i in [4, 5, 6]:

        chars[i] = letter_corrections.get(
            chars[i],
            chars[i]
        )

    candidate = "".join(chars)

    if UK_PLATE_REGEX.match(
        candidate
    ):
        return candidate

    return None


def read_plate(vision):

    detections = []

    for image in vision["raw_images"]:

        processed = preprocess_image(
            image
        )

        results = reader.readtext(
            processed
        )

        for result in results:

            _, text, confidence = result

            plate = normalize_plate(
                text
            )

            if not plate:
                continue

            print(
                f"OCR: {text}"
            )

            print(
                f"PLATE: {plate}"
            )

            detections.append(
                (
                    plate,
                    float(confidence)
                )
            )

    if not detections:

        return {
            "carplate_ai": None,
            "carplate_ai_confidence": 0.0
        }

    best_plate = max(
        detections,
        key=lambda x: x[1]
    )

    return {
        "carplate_ai": best_plate[0],
        "carplate_ai_confidence": round(
            best_plate[1],
            3
        )
    }