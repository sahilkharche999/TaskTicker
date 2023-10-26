import json

# import boto3
from helper import (
    is_slack_command,
    is_from_slack,
    parse_slack_event_body,
    get_payload,
    update_slack_message,
    is_slack_submit,
    save_to_db
)
from messager import get_message


def lambda_handler(event: dict, context):

    if is_from_slack(event):
        body = parse_slack_event_body(event)
        if is_slack_command(body):

            print("Slack Command:", body)
            return {
                "statusCode": 200,
                "body": json.dumps(
                    get_message()
                ),
            }

        else:
            payload = get_payload(body)
            print("Slack Event, Payload:", payload)
            response_url = payload.get('response_url')

            if is_slack_submit(payload):
                save_to_db(payload)
                update_slack_message(response_url, {
                    'text': 'Success!!!'
                })

            else:
                print('skipping')
                return {
                    "statusCode": 204
                }
