from collections import Counter
from clawbot.agents.plate_reader import read_plate



SERVICE_TERMS = [
    "SERVICE",
    "DETAILING",
    "VALETING",
    "REPAIR",
    "MECHANIC",
    "BREAKING",
    "PARTS",
    "WANTED",
    "FINANCE",
    "RECOVERY",
    "TOWING",
    "ALLOY",
    "MATS"
]


CAR_TERMS = [
    "BMW",
    "AUDI",
    "MERCEDES",
    "FORD",
    "FIAT",
    "VOLKSWAGEN",
    "VAUXHALL",
    "TOYOTA",
    "HONDA",
    "MILES",
    "MOT",
    "PETROL",
    "DIESEL"
]


def detect_from_text(
    title,
    description
):

    text = (
        f"{title} {description}"
    ).upper()


    service_hits = sum(
        term in text
        for term in SERVICE_TERMS
    )


    car_hits = sum(
        term in text
        for term in CAR_TERMS
    )


    if service_hits > car_hits:

        return (
            False,
            0.9
        )


    if car_hits > 0:

        confidence = min(
            0.95,
            0.5 + (
                car_hits * 0.1
            )
        )

        return (
            True,
            confidence
        )


    return (
        True,
        0.5
    )


def detect_from_images(
    vision
):

    ocr_hits = 0


    for image in vision[
        "grayscale"
    ]:

        results = vision[
            "ocr"
        ].readtext(
            image
        )


        for result in results:

            _, text, _ = result

            text = text.upper()


            if any(
                term in text
                for term in CAR_TERMS
            ):

                ocr_hits += 1
                break


    if ocr_hits == 0:

        return (
            False,
            0.7
        )


    confidence = min(
        0.95,
        0.5 + (
            ocr_hits * 0.1
        )
    )


    return (
        True,
        confidence
    )


def detect_vehicle(
    vehicle,
    vision
):

    text_result = (
        detect_from_text(
            vehicle["title"],
            vehicle.get(
                "description"
            ) or ""
        )
    )


    image_result = (
        detect_from_images(
            vision
        )
    )


    plate_result = (
        read_plate(
            vision
        )
    )


    plate_found = (
        plate_result[
            "carplate_ai"
        ] is not None
    )


    votes = [
        text_result[0],
        image_result[0],
        plate_found
    ]


    final = Counter(
        votes
    ).most_common(1)[0][0]


    confidence = max(
        text_result[1],
        image_result[1],
        plate_result[
            "carplate_ai_confidence"
        ]
    )


    if plate_found:

        confidence = max(
            confidence,
            0.98
        )


    return {
        "is_car_ai": final,
        "is_car_ai_confidence": round(
            confidence,
            3
        )
    }