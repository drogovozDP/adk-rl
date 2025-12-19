import gymnasium as gym
from gymnasium import spaces
import os
import asyncio
from typing import Optional
import random

from google.adk.tools import FunctionTool
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
from google.adk.runners import Runner
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv

from gcs_bucket import get_tool_updates

BUCKET_NAME = os.environ.get("BUCKET_NAME", "dimadrogovoz-tf-backend")
GCS_FILE_NAME = os.environ.get("GCS_FILE_NAME", "tool_updates.json")

load_dotenv()

# --- 1. Define Candidate Descriptions (The "Actions") ---
# CANDIDATE_DESCRIPTIONS = [
#     "stuff about places",                                      # Action 0: Vague (Bad)
#     "returns info about a country string",                     # Action 1: Technical but unclear
#     "returns the capital city of a country",                   # Action 2: Concise (Good)
#     "Retrieves the capital city name for a specific country input. Input must be a string." # Action 3: Detailed (Best)
# ]

CANDIDATE_DESCRIPTIONS = get_tool_updates(BUCKET_NAME, GCS_FILE_NAME)

# --- 2. Define Training Data (The "Observations") ---
# We use different countries to ensure the prompt works generally, not just for one input.
TRAINING_QUERIES = [
    {"country": "united states", "target": "Washington"},
    {"country": "canada", "target": "Ottawa"},
    {"country": "france", "target": "Paris"},
    {"country": "germany", "target": "Berlin"},
]

def get_capital_city(country: str) -> str:
    """Retrieves the capital city of a given country."""
    country_capitals = {
        "united states": "Washington, D.C.",
        "canada": "Ottawa",
        "france": "Paris",
        "germany": "Berlin",
    }
    return country_capitals.get(country.lower(), f"Capital not found for {country}")

class BeforeModelResponseCallback:
    def __init__(self, tool_updates):
        self.tool_updates = tool_updates

    def __call__(self, callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
        print(self.tool_updates)
        for tool in llm_request.config.tools:
            if hasattr(tool, 'function_declarations'):
                for func_decl in tool.function_declarations:
                    if func_decl.name in self.tool_updates:
                        func_decl.description = self.tool_updates[func_decl.name]
        return None

# --- 3. The Custom Gymnasium Environment ---
class ToolOptimizationEnv(gym.Env):
    """
    A custom Environment that follows the Gymnasium interface.
    This environment optimizes the description of a tool.
    """

    metadata = {"render_modes": ["human"]}
    def __init__(self):
        super(ToolOptimizationEnv, self).__init__()

        # 1. SETUP PERSISTENT EVENT LOOP
        # We create one loop that lives as long as this Environment exists
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Action/Obs spaces setup
        self.action_space = spaces.Discrete(len(CANDIDATE_DESCRIPTIONS))
        self.observation_space = spaces.Discrete(len(TRAINING_QUERIES))
        self.current_query_idx = 0

        # 2. INITIALIZE AGENT INSIDE THE CORRECT CONTEXT
        # Initialize the agent here so LiteLLM binds to self.loop
        self.before_model_response_callback = BeforeModelResponseCallback(
            tool_updates={"get_capital_city": random.choice(CANDIDATE_DESCRIPTIONS)}
        )
        self.agent = self._setup_agent()

    def _setup_agent(self):
        """Helper to set up the agent configuration"""
        api_base_url = os.getenv("LLM_BASE_URL", "http://vllm-llama3-service:8000/v1")
        model_name_at_endpoint = os.getenv("MODEL_NAME", "hosted_vllm/meta-llama/Llama-3.1-8B-Instruct")

        model = LiteLlm(
            model=model_name_at_endpoint,
            api_base=api_base_url,
        )

        capital_tool = FunctionTool(func=get_capital_city)

        return LlmAgent(
            name="GymAgent",
            model=model,
            instruction="You are a helpful assistant.",
            tools=[capital_tool],
            before_model_callback=self.before_model_response_callback
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_query_idx = self.np_random.integers(0, len(TRAINING_QUERIES))
        observation = self.current_query_idx
        info = {}
        return observation, info

    def step(self, action):
        # 1. EXECUTE ACTION
        chosen_description = CANDIDATE_DESCRIPTIONS[action]
        self.before_model_response_callback.tool_updates = {"get_capital_city": chosen_description}

        # 2. RUN SIMULATION (Using the Persistent Loop)
        current_data = TRAINING_QUERIES[self.current_query_idx]
        user_query = f"What is the capital of {current_data['country']}?"

        try:
            response_text = self.loop.run_until_complete(self._run_agent_async(user_query))
        except Exception as e:
            response_text = "Error"
            print(f"Agent failed: {e}")

        # 3. CALCULATE REWARD
        target = current_data['target']
        if target.lower() in response_text.lower():
            reward = 1.0
            print(f"✅ Success! (Act: {action}). LLM's response: {response_text.lower()}")
        else:
            reward = -1.0
            print(f"❌ Failed. (Act: {action}). LLM's response: {response_text.lower()}")
        print(f"  Q: {user_query}")
        print(f"  A: {response_text.lower()}")

        terminated = True
        truncated = False
        observation = self.current_query_idx
        info = {"description_used": chosen_description, "response": response_text}

        return observation, reward, terminated, truncated, info

    async def _run_agent_async(self, query):
        session_service = InMemorySessionService()
        session_id = f"session_{self.np_random.integers(0, 100000)}"
        session = await session_service.create_session(app_name="gym_app", user_id="gym_user", session_id=session_id)
        runner = Runner(agent=self.agent, app_name="gym_app", session_service=session_service)

        content = types.Content(role='user', parts=[types.Part(text=query)])
        events = runner.run_async(user_id="gym_user", session_id=session_id, new_message=content)

        final_text = ""
        async for event in events:
            if event.is_final_response():
                final_text = event.content.parts[0].text
        return final_text

    def close(self):
        """Cleanup the loop when the environment is closed"""
        if self.loop.is_running():
            self.loop.close()

# --- 4. Main: Run with Stable Baselines 3 ---
if __name__ == "__main__":
    from stable_baselines3 import DQN
    # from stable_baselines3.common.env_checker import check_env

    # 1. Initialize Env
    env = ToolOptimizationEnv()

    # 2. Sanity Check (Optional)
    # check_env(env)

    print("--- Starting Training with DQN ---")
    # 3. Train the Agent using Deep Q-Learning
    # We use a simple MLP policy.
    # Learning_starts=10 ensures we explore a bit before training.
    model = DQN("MlpPolicy", env, verbose=1, learning_starts=5, learning_rate=0.01)

    # Train for 40 steps (approx 10 episodes per country)
    model.learn(total_timesteps=40)

    print("\n--- Training Finished. Testing Model ---")

    # 4. Test the trained model
    obs, _ = env.reset()
    for _ in range(5):
        action, _states = model.predict(obs, deterministic=True)
        print(f"Model chose Action {action} ('{CANDIDATE_DESCRIPTIONS[action]}') for Query Index {obs}")

        obs, reward, terminated, truncated, info = env.step(action)
        if terminated:
            obs, _ = env.reset()
