import os
from ray.job_submission import JobSubmissionClient

# 1. Configuration
# Replace with your GKE LoadBalancer IP or local port-forward address
RAY_DASHBOARD_ADDRESS = "http://127.0.0.1:8265"

# Initialize the Client
client = JobSubmissionClient(RAY_DASHBOARD_ADDRESS)

# 2. Define the script to run on the cluster
# We use a string to represent the entrypoint script
with open("invoke_svc_test.py", "r") as fi:
    job_script = fi.read()
# job_script = """
# import ray
# import os
# import socket

# ray.init()

# @ray.remote
# def get_worker_info():
#     return {
#         "hostname": socket.gethostname(),
#         "pid": os.getpid(),
#         "ip": ray._private.services.get_node_ip_address()
#     }

# # Run multiple tasks across the GKE cluster nodes
# results = ray.get([get_worker_info.remote() for _ in range(4)])

# print("--- Job Results from GKE Cluster ---")
# for res in results:
#     print(f"Worker Node: {res['hostname']} (IP: {res['ip']})")
# """

# 3. Submit the Job
# 'runtime_env' allows you to send local files or pip packages to the cluster
job_id = client.submit_job(
    entrypoint="python -c '" + job_script + "'",
    runtime_env={
        "pip": ["requests"] # Add any extra libraries your job needs
    }
)

print(f"Job submitted successfully! Job ID: {job_id}")

# 4. (Optional) Track Status
import time
while True:
    status = client.get_job_status(job_id)
    print(f"Current Status: {status}")
    if status in ["SUCCEEDED", "FAILED", "STOPPED"]:
        break
    time.sleep(5)

# Get the logs
logs = client.get_job_logs(job_id)
print("\n--- Job Logs ---")
print(logs)
