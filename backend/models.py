from typing import Dict, Any
import uuid

def create_dog_profile(payload: Dict[str, Any], owner: str) -> Dict[str, Any]:
    # Validate and normalize payload
    dog_id = str(uuid.uuid4())
    profile = {
        'dog_id': dog_id,
        'owner': owner,
        'name': payload.get('name'),
        'breed': payload.get('breed'),
        'age_years': float(payload.get('age_years', 0)),
        'gender': payload.get('gender'),
        'weight_kg': float(payload.get('weight_kg', 0)),
        'height_cm': float(payload.get('height_cm', 0)),
        'activity_level': payload.get('activity_level'),
        'current_diet': payload.get('current_diet'),
        'exercise_routine': payload.get('exercise_routine'),
        'health_history': payload.get('health_history'),
    }
    return profile
