import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv()

REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = "amazon.nova-pro-v1:0"

_session = boto3.Session(region_name=REGION)
_client = _session.client("bedrock-runtime")

def chat_nova(messages, max_tokens=400, temperature=0.2, top_p=0.9) -> str:
    bedrock_messages = [{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages]

    body = {
        "messages": bedrock_messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
            "topP": top_p,
        },
    }

    resp = _client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )
    payload = json.loads(resp["body"].read())
    return payload["output"]["message"]["content"][0]["text"]
