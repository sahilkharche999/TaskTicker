import os
import boto3
import json
from slack_sdk import WebClient

ssm_client = boto3.client('ssm')
DEFAULT_SNOOZE_DELAY = 60 * 60


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
LOG1_TOKEN = app_config.get('log1-token')

LOG1_URL = os.environ.get('LOG1_URL')
# slack_logs_channel = app_config.get('logs-channel-id')
