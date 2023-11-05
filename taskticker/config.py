import boto3
import json
from slack_sdk import WebClient
import os

ssm_client = boto3.client('ssm')

def fetch_config() -> dict:
    try:
        response = ssm_client.get_parameter(
            Name='taskticker-config',
            WithDecryption=True
        )
        return json.loads(response.get('Parameter').get('Value'))
    except:
        raise Exception("Unable to find config!")


app_config = fetch_config()
SLACK_CLIENT = WebClient(token=app_config.get('slack-bot-oauth-token'))
DYNAMO_DB_Table = boto3.resource('dynamodb').Table(os.environ.get('DB_TABLE_NAME'))
# slack_logs_channel = app_config.get('logs-channel-id')
