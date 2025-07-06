import os
import boto3

def download_model_from_s3(bucket_name, object_key, local_path):
    if not os.path.exists(local_path):
        print(f"Downloading model from s3://{bucket_name}/{object_key} ...")
        s3 = boto3.client("s3")
        s3.download_file(bucket_name, object_key, local_path)
        print("Download complete.")
    else:
        print("Model file already exists. Skipping download.")