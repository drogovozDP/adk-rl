# adk-rl

## How to run

### Set up a GKE cluster

You need to create a GKE cluster and deploy an LLM to invoke. Go to `/terraform` folder. Here you need to hange `<PROJET_ID>` and `<CLUSTER_NAME>` to your values. Then run these commands:

```bash
terraform init
terraform apply -var-file=example_vars.tfvars
```

Then get the access to your cluster by running this:

```bash
gcloud container clusters get-credentials <CLUSTER_NAME> --project=<PROJECT_ID> --zone=us-east4
```

Now you can deploy an LLM and port-forward it so the agent can access it.

```bash
kubectl apply -f deploy-llm.yaml
# once it is deployed, port-forward its service
kubectl port-forward svc/vllm-llama3-service 8000
```

### Set up a GCS bucket

You need to go to the root of this project. Here you can find `tool_updates.json` file. This file contains multiple descriptions for a single tool `capital_tool` from the `main.py` file. You need to upload this to a `GCS` bucket as it is. Then copy the `.env.example` to `.env` and replace the values inside accordingly. Now you can create a Python environment.

```bash
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
python main.py
```

### What is happening inside the `/main.py`

We define a function `get_capital_city`, which is converted to a tool `capital_tool`. We want to find the best description for this tool. To do so, we created a custom gymnasium `ToolOptimizationEnv` environment. Inside this environment we, accordingly to standardized environment definition, created appropriate methods, like `step`, `reset`, `init`. These methods interpret our ADK agent as an environment, and the instructions as possible actions. In the `__main__` we create a `DQN` network that tries to learn which tool description is the best to solve our environment. In our case, the model should come to only one description, because other are not so good.

## Clean up

Go to the `/terraform` folder and run this command:

```bash
terraform destroy -var-file=example_vars.tfvars
```
