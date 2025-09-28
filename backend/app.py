import os
import json
from flask import Flask, request, jsonify, session, send_from_directory
from dotenv import load_dotenv
from utils import save_user, load_users, check_password, save_encrypted_profiles, load_encrypted_profiles, ensure_files
from models import create_dog_profile
from cryptography.fernet import Fernet
import requests
from google import genai

load_dotenv()
app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret')

USERS_FILE = 'users.json'
BREED_DB_FILE = 'breed_db.json'

# --- Helpers -------------------------------------------------
def require_auth(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'unauthenticated'}), 401
        return fn(*args, **kwargs)
    return wrapper

def call_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Gemini API key not configured."

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",  # you can choose another Gemini model if needed
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Gemini call failed: {e}"

# --- Auth endpoints --------   ---------------------------------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    users = load_users()
    if username in users:
        return jsonify({'error': 'user exists'}), 400
    save_user(username, password)
    return jsonify({'status': 'ok'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    users = load_users()
    user = users.get(username)
    if not user:
        return jsonify({'error': 'invalid credentials'}), 401
    hashed = user['password'].encode('utf-8')
    if not check_password(password, hashed):
        return jsonify({'error': 'invalid credentials'}), 401
    session['username'] = username
    return jsonify({'status': 'ok'})

@app.route('/api/logout', methods=['POST'])
@require_auth
def logout():
    session.pop('username', None)
    return jsonify({'status': 'ok'})

@app.route('/api/profile-check', methods=['GET'])
def profile_check():
    if 'username' in session:
        return jsonify({'logged_in': True, 'username': session['username']})
    return jsonify({'logged_in': False})

# --- Profile endpoints --------------------------------------
@app.route('/api/profile', methods=['POST'])
@require_auth
def create_profile():
    payload = request.json or {}
    username = session['username']
    profile = create_dog_profile(payload, owner=username)
    # load existing profiles and append
    profiles = load_encrypted_profiles()
    profiles[profile['dog_id']] = profile
    save_encrypted_profiles(profiles)
    return jsonify({'status': 'ok', 'dog_id': profile['dog_id']})

@app.route('/api/profile/<dog_id>', methods=['GET'])
@require_auth
def get_profile(dog_id):
    profiles = load_encrypted_profiles()
    profile = profiles.get(dog_id)
    if not profile:
        return jsonify({'error': 'not found'}), 404
    if profile.get('owner') != session['username']:
        return jsonify({'error': 'forbidden'}), 403
    return jsonify({'profile': profile})

# --- Recommendation endpoint -------------------------------
@app.route('/api/recommendations', methods=['POST'])
@require_auth
def recommendations():
    data = request.json or {}
    # Accept either a profile payload or a dog_id
    profiles = load_encrypted_profiles()
    if data.get('dog_id'):
        profile = profiles.get(data['dog_id'])
        if not profile:
            return jsonify({'error': 'profile not found'}), 404
        if profile.get('owner') != session['username']:
            return jsonify({'error': 'forbidden'}), 403
    else:
        profile = data.get('profile')
    if not profile:
        return jsonify({'error': 'profile required'}), 400

    # Deterministic analysis
    breed_db = json.load(open(BREED_DB_FILE))
    breed = profile.get('breed')
    weight = float(profile.get('weight_kg', 0))
    height_cm = float(profile.get('height_cm', 0) or 0)
    age = float(profile.get('age_years', 0) or 0)
    activity = profile.get('activity_level', 'moderate')

    category = 'unknown'
    details = []

    if breed and breed in breed_db:
        b = breed_db[breed]
        if weight < b['min_kg']:
            category = 'underweight'
        elif weight > b['max_kg']:
            category = 'overweight'
        else:
            category = 'ideal'
        details.append(f"Breed ideal range: {b['min_kg']}–{b['max_kg']} kg")
    else:
        # fallback heuristic: weight-for-height ratio
        if height_cm > 0:
            ratio = weight / (height_cm / 100)
            if ratio < 5:
                category = 'underweight'
            elif ratio > 12:
                category = 'overweight'
            else:
                category = 'ideal'
            details.append(f"Fallback weight-height ratio: {ratio:.2f}")
        else:
            details.append('Insufficient data')

    # Basic calorie estimate
    import math
    cal = 70 * (weight ** 0.75) if weight > 0 else None
    calorie_recommendation = int(cal * (1.2 if activity == 'low' else 1.0 if activity == 'moderate' else 1.4)) if cal else None

    deterministic = {
        'category': category,
        'details': details,
        'calorie_estimate_kcal_per_day': calorie_recommendation,
        'exercise_minutes_per_day': 30 if activity == 'low' else 60 if activity == 'moderate' else 90
    }

    # Gemini refinement
    refine = data.get('refine_with_gemini', True)
    gemini_output = None
    if refine:
        prompt = (
            f"Dog profile: name={profile.get('name')}, breed={breed}, age={age} yrs, "
            f"weight={weight} kg, height={height_cm} cm, activity={activity}.\n"
            f"Deterministic analysis: {deterministic}.\n"
            "Provide precise, breed-specific nutrition, portion sizes, exercise plan, supplements if any, "
            "and risk evaluation. Be conservative and include references to vet care when needed. "
            "Output as JSON with keys: nutrition, exercise, risks, vet_recommendations."
        )
        raw_gemini = call_gemini(prompt)
        try:
            # Clean raw string: remove ```json if present
            cleaned = raw_gemini.strip("```json\n").strip("```")
            gemini_json = json.loads(cleaned)

            # Convert JSON to normalized text
            lines = []
            for section, content in gemini_json.items():
                lines.append(f"\n=== {section.upper()} ===")
                if isinstance(content, dict):
                    for k, v in content.items():
                        if isinstance(v, list):
                            lines.append(f"\n{k.replace('_',' ').capitalize()}:")
                            for item in v:
                                if isinstance(item, dict):
                                    item_text = ", ".join(f"{ik}: {iv}" for ik, iv in item.items())
                                    lines.append(f"  - {item_text}")
                                else:
                                    lines.append(f"  - {item}")
                        else:
                            lines.append(f"\n{k.replace('_',' ').capitalize()}:\n{v}")
                elif isinstance(content, list):
                    for item in content:
                        lines.append(f"- {item}")
                else:
                    lines.append(str(content))

            gemini_output = "\n".join(lines)
        except Exception as e:
            gemini_output = f"Failed to parse Gemini output: {e}\nRaw output:\n{raw_gemini}"

    response = {
        'deterministic': deterministic,
        'gemini_refinement': gemini_output
    }
    return jsonify(response)

# Serve frontend
@app.route('/')
def index():
    return send_from_directory(app.template_folder, 'index.html')

@app.route('/static/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)


if __name__ == '__main__':
    ensure_files()
    app.run(debug=True, port=5000)
