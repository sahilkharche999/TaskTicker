from helper import (
    get_payload,
    is_from_slack,
    is_slack_command,
    post_project_update,
    slack_command_handler,
    parse_slack_event_body,
    is_from_aws_event_bridge,
    slack_view_submit_handler,
    slack_block_actions_handler
)
from scheduler_worker import send_notifications


def update_handler(event: dict, context):
    """
    Handler for the update event
    :param event: payload from the event
    :param context: lambda context
    :return: None
    """
    print("Update Event:", event)
    post_project_update(event)


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
            return slack_command_handler(body)

        # If the event is a Slack Event
        else:
            payload = get_payload(body)
            print("Slack Event, Payload:", payload)

            action = payload.get('type')

            actions = {
                'view_submission': slack_view_submit_handler,
                'block_actions': slack_block_actions_handler,
            }
            return actions.get(action, lambda x: {"statusCode": 400})(payload)

    return {"statusCode": 400}
