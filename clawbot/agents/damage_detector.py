import re
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

# Load models once
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# Specific UK terms for previous damage / insurance write-offs
PREVIOUS_DAMAGE_TERMS = [
    r"CAT N", r"CAT S", r"CAT C", r"CAT D",
    r"CATEGORY N", r"CATEGORY S", r"CATEGORY C", r"CATEGORY D",
    r"WRITE OFF", r"WRITEOFF", r"CAT-N", r"CAT-S",
    r"PREVIOUSLY REPAIRED", r"INSURANCE CLAIM"
]

def detect_from_text(vehicle):
    text = (
        f"{vehicle.get('title') or ''} "
        f"{vehicle.get('description') or ''}"
    ).upper()

    hits = 0
    matched_terms = []

    # Use regex to find specific category phrases
    for term in PREVIOUS_DAMAGE_TERMS:
        if re.search(term, text):
            hits += 1
            matched_terms.append(term)

    if hits == 0:
        return (False, 0.5, "No history of damage found in text")

    confidence = min(0.98, 0.7 + (hits * 0.1))
    return (True, confidence, f"Previous damage mentioned: {', '.join(matched_terms)}")

def detect_from_images(vision):
    votes = []
    prompts = ["a badly damaged car", "a clean undamaged car"]

    for img_array in vision.get("images", []):
        image = Image.fromarray(img_array)

        inputs = processor(
            text=prompts,
            images=image,
            return_tensors="pt",
            padding=True
        )

        outputs = model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1).detach().numpy()[0]
        
        damaged_prob = float(probs[0])
        votes.append(damaged_prob)

    if not votes:
        return (False, 0.0, "No images to scan")

    avg_damage = sum(votes) / len(votes)

    if avg_damage > 0.65:
        return (True, avg_damage, "Visually damaged in current photos")

    return (False, 1 - avg_damage, "Looks visually clean")

def detect_damage(vehicle, vision):
    text_result = detect_from_text(vehicle)
    image_result = detect_from_images(vision)

    # We prioritize text because "previous" damage is usually invisible (repaired)
    final_is_damaged = text_result[0] or image_result[0]

    if text_result[0]:
        explanation = text_result[2]
        confidence = text_result[1]
    elif image_result[0]:
        explanation = image_result[2]
        confidence = image_result[1]
    else:
        explanation = "No previous or current damage detected"
        confidence = max(text_result[1], image_result[1])

    # Ensure types match your database schema
    return {
        "damage_ai": bool(final_is_damaged),
        "damage_explanation_ai": str(explanation),
        "damage_ai_confidence": float(round(confidence, 3))
    }