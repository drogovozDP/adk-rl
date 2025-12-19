import os
import json
import datetime
from google.adk.agents import LlmAgent
from google.adk.models import LlmResponse, LlmRequest
from google.adk.tools import FunctionTool
from google.adk.agents.callback_context import CallbackContext
from google.cloud import storage
from typing import Optional

BUCKET_NAME = os.environ.get("BUCKET_NAME", "dimadrogovoz-tf-backend")
GCS_FILE_NAME = os.environ.get("GCS_FILE_NAME", "tool_updates.json")

# Define a tool function
def get_capital_city(country: str) -> str:
    """Retrieves the capital city of a given country."""
    print(f"--- Tool 'get_capital_city' executing with country: {country} ---")
    country_capitals = {
        "united states": "Washington, D.C.",
        "canada": "Ottawa",
        "france": "Paris",
        "germany": "Berlin",
    }
    return country_capitals.get(country.lower(), f"Capital not found for {country}")

capital_tool = FunctionTool(func=get_capital_city)

# --- Define the Callback Function ---
class BeforeModelResponseCallback:
    def __init__(self, bucket_name, gcs_file_name):
        self.bucket_name = bucket_name
        self.gcs_file_name = gcs_file_name
        self.tool_updates = {"get_capital_city": self._get_tool_updates()}
        self.timestamp = datetime.datetime.now()

    def _get_tool_updates(self):
        storage_client = storage.Client()
        bucket = storage_client.bucket(self.bucket_name)
        blob = bucket.blob(self.gcs_file_name)

        print("[GCS] Downloading tool updates")

        json_content = blob.download_as_text()
        tool_updates = json.loads(json_content)

        print(f"[GCS] Tool updates: {tool_updates}")
        return tool_updates[-1]

    def __call__(self, callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
        state = callback_context.session.state if callback_context.session else {}
        print(f"!!!state={state}!!!")

        if datetime.datetime.now() - self.timestamp > datetime.timedelta(seconds=7):
            self.tool_updates = self._get_tool_updates()
            self.timestamp = datetime.datetime.now()
        for tool in llm_request.config.tools:
            if hasattr(tool, 'function_declarations'):
                for func_decl in tool.function_declarations:
                    if func_decl.name in self.tool_updates:
                        func_decl.description = self.tool_updates[func_decl.name]
        return None

# Add the tool to the agent
capital_agent = LlmAgent(
    model="gemini-2.0-flash",
    name="capital_agent", #name of your agent
    description="Answers user questions about the capital city of a given country.",
    instruction="""You are an agent that provides the capital city of a country... (previous instruction text)""",
    tools=[capital_tool], # Provide the function directly
    before_model_callback=BeforeModelResponseCallback(BUCKET_NAME, GCS_FILE_NAME)
)

# ADK will discover the root_agent instance
root_agent = capital_agent
