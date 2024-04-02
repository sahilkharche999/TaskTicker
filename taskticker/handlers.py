from helper import (
    get_payload,
    is_from_slack,
    is_slack_command,
    post_project_update,
    slack_command_handler,
    parse_slack_event_body,
    is_from_aws_event_bridge,
    slack_view_submit_handler,
    slack_block_actions_handler, initiate_project_update
)
from scheduler_worker import send_notifications
import time


def update_handler(event: dict, context):
    """
    Handler for the update event
    :param event: payload from the event
    :param context: lambda context
    :return: None
    """
    print("Update Event:", event)
    start_time = time.time()
    post_project_update(event)
    print("Time taken to post update:", time.time() - start_time)


def lambda_handler(event: dict, context):
    """
    Lambda handler for the taskticker app
    :param event:
    :param context:
    :return:
    """
    start_time = time.time()

    # If the event is from AWS Event Bridge, then it is a scheduled event
    if is_from_aws_event_bridge(event):
        print("AWS Event Bridge Event:", event)
        send_notifications()
        print("Time taken :: Notifications:", time.time() - start_time)
        return

    # If the event is from Slack
    if is_from_slack(event):
        body = parse_slack_event_body(event)

        # If the event is a Slack Command
        if is_slack_command(body):
            print("Slack Command:", body)
            res = slack_command_handler(body)
            print("Time taken :: Slack command:", time.time() - start_time)
            return res


        # If the event is a Slack Event
        else:
            payload = get_payload(body)
            print("Slack Event payload: ", payload)
            action = payload.get('type')

            actions = {
                'view_submission': slack_view_submit_handler,
                'block_actions': slack_block_actions_handler,
            }
            res = actions.get(action, lambda x: {"statusCode": 400})(payload)
            print("Time taken :: Slack event:", time.time() - start_time)
            return res

    return {"statusCode": 400}

