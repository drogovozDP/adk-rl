import requests
import json

# Configuration
# APP_URL = "http://localhost:8000" # Change to your actual URL/Port
APP_URL = "http://127.0.0.1:8000" # Change to your actual URL/Port
APP_NAME = "capital_agent"
USER_ID = "user_123"
SESSION_ID = "session_3"

def run_adk_agent():
    # 1. Create or Update Session (Pass custom parameters here)
    # This sets the initial state/context for the session
    session_url = f"{APP_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions/{SESSION_ID}"

    # These are your custom parameters/state
    session_data = {
        "tool_updates": {
            "get_capital_city_info": "Retrieves the capital city name for a specific country input. Input must be a string."
        },
    }

    print(f"--- Initializing Session: {SESSION_ID} ---")
    session_res = requests.post(session_url, json=session_data)
    session_res.raise_for_status()

    # 2. Run the Agent
    run_url = f"{APP_URL}/run_sse"

    payload = {
        "app_name": APP_NAME,
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "new_message": {
            "role": "user",
            "parts": [{"text": "What is the capital of Canada?"}]
        },
        "streaming": False, # Set to False for a simple JSON response
        "metadata": "test"
    }

    print(f"--- Running Agent: {APP_NAME} ---")
    response = requests.post(run_url, json=payload)

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

    session_res = requests.delete(session_url, json=session_data)
    session_res.raise_for_status()

if __name__ == "__main__":
    run_adk_agent()
