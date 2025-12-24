Go to the `../terraform` directory, specify `<PROJECT_ID>`, `<PROJECT_NUMBER>`, and `<CLUSTER_NAME>`. Then run:
```bash
terraform init
terraform apply -var-file=example_vars.tfvars
```

Upload the `tool_updates.json` to your bucket:

```bash
gcloud storage cp tool_updates.json  gs://<BUCKET_NAME>/tool_updates.json
```

Get the access to the cluster:
```bash
gcloud container clusters get-credentials <CLUSTER_NAME> --project=<PROJECT_ID> --zone=us-east4
```

Create a secret:
```bash
GOOGLE_API_KEY=<aistudio_api_key>
kubectl create secret generic google-api-key \
    --from-literal=api-key=${GOOGLE_API_KEY} \
    --dry-run=client -o yaml | kubectl apply -f -
```

Create a ray cluster
```bash
kubectl apply -f ray-cluster-option1.yaml
```

Create a Docker image with an ADK agent:
```bash
cd adk-example
gcloud build submit .
```

Change `<PROJECT_ID>` to your project ID and `<BUCKET_NAME>` to your bucket name in the `deployment.yaml` file and apply it:
```bash
kubectl apply -f deployment.yaml
```

## Set up and simple invokation

Go to the previous directory, create a venv, install `requirements.txt`, port-forward the ray cluster and submit a testing job.
```bash
cd ..
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
kubectl port-forward svc/ray-cluster-example-head-svc 8265
python ray_invoke_svc_test.py
```

In the `http://127.0.0.1:8265` you will see the job.

## Trainig and verification

Run this command to submit the trainnig job:
```bash
python ray_dummy_training.py
```

Once the training is done, you can check the graphs by running tensorboard with gcsfuse. Open the `tensorboard.yaml` file and replace `<BUCKET_NAME>` with your bucket name. Apply and port-forward it:

```bash
kubectl apply -f tensorboard.yaml
kubectl port-forward svc/tensorboard-service 8000:80
```

The reward graph should increase over time.
