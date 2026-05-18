from collections import Counter

import torch
from PIL import Image

from transformers import (
    CLIPProcessor,
    CLIPModel
)


model = CLIPModel.from_pretrained(
    "openai/clip-vit-base-patch32"
)

processor = CLIPProcessor.from_pretrained(
    "openai/clip-vit-base-patch32"
)


DAMAGE_TERMS = [
    "CAT",
    "DAMAGE",
    "DENT",
    "SCRATCH",
    "SPARES",
    "REPAIR",
    "CRACKED",
    "BROKEN"
]


def detect_from_text(
    vehicle
):

    text = (
        f"{vehicle['title']} "
        f"{vehicle.get('description') or ''}"
    ).upper()


    hits = sum(
        term in text
        for term in DAMAGE_TERMS
    )


    if hits == 0:

        return (
            False,
            0.5,
            "No damage terms found"
        )


    confidence = min(
        0.95,
        0.5 + (
            hits * 0.1
        )
    )


    return (
        True,
        confidence,
        "Damage terms found"
    )


def detect_from_images(
    vision
):

    votes = []


    prompts = [
        "a damaged car",
        "a clean car"
    ]


    for image in vision[
        "images"
    ]:

        image = Image.fromarray(
            image
        )


        inputs = processor(
            text=prompts,
            images=image,
            return_tensors="pt",
            padding=True
        )


        outputs = model(
            **inputs
        )


        probs = (
            outputs.logits_per_image
            .softmax(dim=1)
            .detach()
            .numpy()[0]
        )


        damaged_prob = float(
            probs[0]
        )


        votes.append(
            damaged_prob
        )


    avg_damage = sum(
        votes
    ) / len(votes)


    if avg_damage > 0.6:

        return (
            True,
            avg_damage,
            "Visual damage detected"
        )


    return (
        False,
        1 - avg_damage,
        "No visible damage"
    )


def detect_damage(
    vehicle,
    vision
):

    text_result = (
        detect_from_text(
            vehicle
        )
    )


    image_result = (
        detect_from_images(
            vision
        )
    )


    final = any([
        text_result[0],
        image_result[0]
    ])


    confidence = max(
        text_result[1],
        image_result[1]
    )


    explanation = (
        image_result[2]
        if image_result[0]
        else text_result[2]
    )


    return {
        "damage_ai": final,
        "damage_explanation_ai": explanation,
        "damage_ai_confidence": round(
            confidence,
            3
        )
    }