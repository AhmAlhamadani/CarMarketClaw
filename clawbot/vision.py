import cv2
import requests
import numpy as np
import easyocr


reader = easyocr.Reader(
    ["en"],
    gpu=False
)


def download_image(url):

    try:

        response = requests.get(
            url,
            timeout=10
        )

        image_array = np.frombuffer(
            response.content,
            np.uint8
        )

        return cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

    except:

        return None


def preprocess_gray(image):

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.resize(
        gray,
        None,
        fx=2,
        fy=2
    )

    return gray


def build_vision_context(image_urls):

    images = []
    grayscale = []

    for url in image_urls:

        image = download_image(
            url
        )

        if image is None:
            continue

        images.append(
            image
        )

        grayscale.append(
            preprocess_gray(
                image
            )
        )

    return {
        "images": images,
        "grayscale": grayscale,
        "ocr": reader
    }