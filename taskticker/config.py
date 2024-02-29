import json
import os

import boto3
from slack_sdk import WebClient

LOG1_URL = os.environ.get('LOG1_URL')
ENV = os.environ.get('ENV', 'dev')
ssm_client = boto3.client('ssm')
DEFAULT_SNOOZE_DELAY = 60 * 60


def fetch_config() -> dict:
    try:
        response = ssm_client.get_parameter(
            Name=f'taskticker-config-{ENV}',
            WithDecryption=True
        )
        return json.loads(response.get('Parameter').get('Value'))
    except Exception:
        raise Exception("Unable to find config! Please check if the config is present in SSM Parameter Store.")


app_config = fetch_config()
SLACK_CLIENT = WebClient(token=app_config.get('slack-bot-oauth-token'))
ADMIN_USERS = app_config.get('admins')
DYNAMO_MAPPING_DB_Table = boto3.resource('dynamodb').Table(os.environ.get('CHANNEL_MAPPING_TABLE_NAME'))
UPDATE_LOG_Table = boto3.resource('dynamodb').Table(os.environ.get('UPDATE_LOG_TABLE_NAME'))
PROJECT_UPDATE_FUNCTION_NAME = os.environ.get('PROJECT_UPDATE_FUNCTION_NAME')
LOG1_API_KEY = app_config.get('log1-token')
# slack_logs_channel = app_config.get('logs-channel-id')
