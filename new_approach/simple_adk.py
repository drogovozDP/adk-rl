import os
import json
from google.cloud import storage
import requests
import numpy as np

import gymnasium as gym
from ray.rllib.env.multi_agent_env import MultiAgentEnv

import ray
from ray import tune
from ray.rllib.algorithms.ppo import PPOConfig

from dotenv import load_dotenv

load_dotenv()


APP_URL = os.environ.get("ADK_SERVICE_URL", "http://adk-agent:80")
APP_NAME = os.environ.get("APP_NAME", "capital_agent")
USER_ID = os.environ.get("USER_ID", "user_1")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "adk-gcs-test-bucket")


class SimpleMultiAgentEnv(MultiAgentEnv):
    def __init__(self, config):
        super().__init__()
        self._agent_ids = {"agent_1", "agent_2"}

        self.candidate_description = config["candidate_description"]

        self.training_queries = [
            {"country": "united states", "target": "Washington"},
            {"country": "canada", "target": "Ottawa"},
            {"country": "france", "target": "Paris"},
            {"country": "germany", "target": "Berlin"},
        ]
        self.action_space = gym.spaces.Discrete(len(self.candidate_description))
        self.observation_space = gym.spaces.Discrete(len(self.training_queries))
        self.current_query_idx = 0

    def reset(self, *, seed=None, options=None):
        """Resets the environment and returns initial observations."""
        self.current_query_idx = self.np_random.integers(0, len(self.training_queries))

        observations = {
            aid: int(self.current_query_idx)
            for aid in self._agent_ids
        }
        return observations, {}

    def step(self, action_dict):
        obs, rewards, terminateds, truncateds, infos = {}, {}, {}, {}, {}

        for aid, action in action_dict.items():
            # Map the discrete action to the tool/description
            act_idx = int(action)
            chosen_tool = self.candidate_description[act_idx]

            # Get current query data
            current_data = self.training_queries[self.current_query_idx]
            user_query = "What is the capital of " + current_data["country"] + "?"
            target_city = current_data["target"]

            response_text = self._invoke_adk_agent(user_query, chosen_tool)
            reward = 1.0 if target_city in response_text else -0.5

            # response_text = "mocked"
            # reward = 1.0 if chosen_tool != "error" else -0.5

            print(f"reward={reward}, act_idx={act_idx}, chosen_tool={chosen_tool}, response_text={response_text}")

            rewards[aid] = reward

            obs[aid] = int(self.current_query_idx)

            terminateds[aid] = True

            infos[aid] = {"correct": reward > 0, "tool_used": chosen_tool}

        # Global state
        terminateds["__all__"] = True # End episode after each agent acts
        truncateds["__all__"] = False

        return obs, rewards, terminateds, truncateds, infos

    def _invoke_adk_agent(self, input_text: str, custom_tool_description: str):
        answer = "Error"
        session_id = f"session_{np.random.randint(1e6)}"
        session_url = f"{APP_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions/{session_id}"
        print(session_url, "!!!")

        session_data = {
            "tool_updates": {
                "get_capital_city_info": custom_tool_description
            },
        }

        session_res = requests.post(session_url, json=session_data)
        run_url = f"{APP_URL}/run_sse"

        payload = {
            "app_name": APP_NAME,
            "user_id": USER_ID,
            "session_id": session_id,
            "new_message": {
                "role": "user",
                "parts": [{"text": input_text}]
            },
            "streaming": False, # Set to False for a simple JSON response
            "metadata": "test"
        }

        response = requests.post(run_url, json=payload)

        if response.status_code == 200:
            try:
                answer = json.loads(response.text.split("data: ")[-1])["content"]["parts"][0]["text"]
            except json.JSONDecodeError:
                print("Response received, but it was not valid JSON. Response text:")
                print(response.text)

        session_res = requests.delete(session_url, json=session_data)
        session_res.raise_for_status()

        return answer

def get_external_data():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("tool_updates.json")
    print("[DRIVER] Downloading data once...")
    json_content = blob.download_as_text()
    print(f"[DRIVER] json_content={json_content}")

    prefix = "ray_results/"
    blobs = list(bucket.list_blobs(prefix=prefix, max_results=1))

    if not blobs:
        print(f"[DRIVER] Creating virtual folder: {prefix}")
        # Create a placeholder zero-byte blob to make the folder show up in UI
        placeholder = bucket.blob(prefix)
        placeholder.upload_from_string("")
    else:
        print(f"[DRIVER] Folder {prefix} already exists.")

    return json.loads(json_content)


if __name__ == "__main__":
    # Initialize Ray
    ray.init(ignore_reinit_error=True)

    # Fetch data on driver
    tool_data = get_external_data()

    # Configure the algorithm
    config = (
        PPOConfig()
        .environment(
            SimpleMultiAgentEnv,
            env_config={
                "candidate_description": tool_data,
            }
        )
        .framework("torch")
        .multi_agent(
            policies={"p1", "p2"},
            # Map agent_1 to policy p1, agent_2 to policy p2
            policy_mapping_fn=lambda aid, episode, worker, **kw: "p1" if aid == "agent_1" else "p2",
        )
        .training(
            train_batch_size=16,
            sgd_minibatch_size=4,
            num_sgd_iter=5,
            entropy_coeff=0.01,
        )
        .resources(num_gpus=0)
        .rollouts(num_rollout_workers=2)
    )

    # Run training
    import time
    start = time.time()
    stop_criteria = {"training_iteration": 5}
    results = tune.Tuner(
        "PPO",
        param_space=config.to_dict(),
        run_config=ray.train.RunConfig(
            storage_path=f"gs://{BUCKET_NAME}/ray_results",
            stop=stop_criteria, verbose=1
        ),
    ).fit()

    print(f"Training finished! It took: {time.time() - start} seconds.")
