import argparse
import importlib.metadata
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


HOST = "s3dev-gz.nie.netease.com"
ENDPOINT_URL = "https://" + HOST


def upload_file(s3_client, file_name, bucket, object_name):
    try:
        s3_client.upload_file(
            file_name, bucket, object_name, ExtraArgs={"ACL": "public-read"}
        )
    except ClientError as e:
        print(e)
        return False
    return True


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--s3-key", required=True)
    parser.add_argument("--s3-secret", required=True)
    parser.add_argument("--s3-bucket", required=True)
    parser.add_argument("path")
    parser.add_argument("key")
    return parser.parse_args()


def main():
    args = parse_args()
    s3_client = boto3.client(
        "s3",
        region_name=None,
        use_ssl=False,
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=args.s3_key,
        aws_secret_access_key=args.s3_secret,
        config=Config(
            s3={"addressing_style": "virtual"}, signature_version="s3"
        ),
    )
    if upload_file(s3_client, args.path, args.s3_bucket, args.key):
        print(f"http://{args.s3_bucket}.{HOST}/{args.key}")


if __name__ == "__main__":
    main()
