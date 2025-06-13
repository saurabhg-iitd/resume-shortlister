import boto3
import os
from urllib.parse import urlparse
from uuid import uuid4

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION")

if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_S3_BUCKET and AWS_REGION):
    raise Exception("AWS S3 credentials/bucket/region are not set in environment variables.")

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

def upload_file_to_s3(file_path, filename):
    s3_key = f"resumes/{uuid4()}_{filename}"
    s3.upload_file(file_path, AWS_S3_BUCKET, s3_key)
    return f"s3://{AWS_S3_BUCKET}/{s3_key}"

def download_file_from_s3(s3_path):
    # Parse the S3 path to extract bucket and key
    parsed_url = urlparse(s3_path)
    bucket = parsed_url.netloc
    key = parsed_url.path.lstrip('/')
    
    # If no bucket in the path, use the default bucket
    if not bucket:
        bucket = AWS_S3_BUCKET
        key = s3_path
    
    # Download the file
    response = s3.get_object(Bucket=bucket, Key=key)
    return response['Body'].read() 