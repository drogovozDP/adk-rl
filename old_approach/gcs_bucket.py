import json
from google.cloud import storage


def get_tool_updates(bucket_name, gcs_file_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(gcs_file_name)

    print("[GCS] Downloading tool updates")

    json_content = blob.download_as_text()
    tool_updates = json.loads(json_content)

    print(f"[GCS] Tool updates: {tool_updates}")
    return tool_updates
