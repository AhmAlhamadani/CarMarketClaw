import requests
import numpy as np
import cv2


def download_images(image_urls):

    images = []

    for url in image_urls:

        try:

            response = requests.get(
                url,
                timeout=10
            )

            image_array = np.frombuffer(
                response.content,
                np.uint8
            )

            image = cv2.imdecode(
                image_array,
                cv2.IMREAD_COLOR
            )

            if image is not None:
                images.append(image)

        except:
            continue

    return images


def build_vision_context(vehicle):

    images = download_images(
        vehicle["image_urls"]
    )

    return {
        "raw_images": images,
        "image_count": len(images)
    }