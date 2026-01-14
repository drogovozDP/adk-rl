import os
import requests
import json

from dotenv import load_dotenv

load_dotenv()

# Configuration
APP_URL = os.environ.get("ADK_SERVICE_URL", "http://adk-agent:80")
APP_NAME = os.environ.get("APP_NAME", "capital_agent")
USER_ID = os.environ.get("USER_ID", "user_1")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "adk-gcs-test-bucket")
SESSION_ID = "session_1"

def run_adk_agent():
    # 1. Create or Update Session (Pass custom parameters here)
    # This sets the initial state/context for the session
    print(APP_URL)
    session_url = f"{APP_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions/{SESSION_ID}"

    print(f"--- Initializing Session: {SESSION_ID} ---")
    session_res = requests.post(session_url)
    session_res.raise_for_status()

    # 2. Run the Agent
    run_url = f"{APP_URL}/run_sse"

    payload = {
        "app_name": APP_NAME,
        "user_id": USER_ID,
        "session_id": SESSION_ID + "1",
        "new_message": {
            "role": "user",
            "parts": [{"text": "What is the capital of Canada?"}]
        },
        "state_delta": {
            "tool_updates": {
                "get_capital_city_info": "Retrieves the capital city name for a specific country input. Input must be a string."
            },
        },
        "streaming": False, # Set to False for a simple JSON response
    }

    print(f"--- Running Agent: {APP_NAME} ---")
    response = requests.post(run_url, json=payload)
    response.raise_for_status()

    if response.status_code == 200:
        # If streaming is False, ADK usually returns a JSON object
        # Note: If the endpoint strictly follows SSE format even for non-streaming,
        # you might need to parse the text data.
        try:
            # Navigate the response structure to get the text
            answer = json.loads(response.text.split("data: ")[-1])["content"]["parts"][0]["text"]
            print(f"Agent Response: {answer}")
        except json.JSONDecodeError:
            print("Response received, but it was not valid JSON. Response text:")
            print(response.text)
    else:
        print(f"Error {response.status_code}: {response.text}")

    session_res = requests.delete(session_url)
    session_res.raise_for_status()

if __name__ == "__main__":
    run_adk_agent()
