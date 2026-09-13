import json
import os


SESSION_PATH = 'session_state.json'


def load_session_state():
    if not os.path.exists(SESSION_PATH):
        return {}
    try:
        with open(SESSION_PATH, 'r') as session_file:
            return json.load(session_file)
    except (OSError, ValueError):
        return {}


def save_session_state(state):
    temporary_path = f'{SESSION_PATH}.tmp'
    try:
        with open(temporary_path, 'w') as session_file:
            json.dump(state, session_file, indent=2)
        os.replace(temporary_path, SESSION_PATH)
    except OSError:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
