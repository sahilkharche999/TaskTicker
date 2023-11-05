from helper import (
    is_from_aws_event_bridge,
    is_slack_command,
    is_from_slack,
    parse_slack_event_body,
    get_payload,
    update_slack_message,
    is_slack_submit,
    save_to_db
)
from config import SLACK_CLIENT
from helper import get_message
from scheduler_worker import send_notifications


def lambda_handler(event: dict, context):

    # If the event is from AWS Event Bridge, then it is a scheduled event
    if is_from_aws_event_bridge(event):
        print("AWS Event Bridge Event:", event)
        send_notifications()
        return

    # If the event is from Slack
    if is_from_slack(event):
        body = parse_slack_event_body(event)

        # If the event is a Slack Command
        if is_slack_command(body):
            print("Slack Command:", body)
            SLACK_CLIENT.views_open(
                trigger_id=body['trigger_id'][0],
                view=get_message(body['channel_id'][0])
            )
            return {
                "statusCode": 204,
            }

        # If the event is a Slack Event
        else:
            payload = get_payload(body)
            print("Slack Event, Payload:", payload)

            if is_slack_submit(payload):
                save_to_db(payload)
                return {
                    "statusCode": 204
                }
            else:
                print('skipping: ', payload)
                return {
                    "statusCode": 204
                }
