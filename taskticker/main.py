from helper import (
    is_from_aws_event_bridge,
    is_slack_command,
    is_slack_submit,
    is_from_slack,
    parse_slack_event_body,
    get_payload,
    save_to_db,
    get_setup_modal,
    is_button_pressed,
    get_button_action_id,
    update_slack_message,
    get_submission,
    get_update_modal
)
from config import SLACK_CLIENT, DEFAULT_SNOOZE_DELAY
from scheduler_worker import send_notifications, schedule_notification


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
                view=get_setup_modal(body['channel_id'][0])
            )
            return {
                "statusCode": 204,
            }

        # If the event is a Slack Event
        else:
            payload = get_payload(body)
            print("Slack Event, Payload:", payload)

            if is_slack_submit(payload):
                submission = get_submission(payload)
                if submission == 'project_setup_view':
                    save_to_db(payload)
                    return {
                        "statusCode": 204
                    }
                if submission == 'project_update_view':
                    print('project update view')

            if is_button_pressed(payload):
                action_id = get_button_action_id(payload)
                if action_id == 'update_now_action':
                    print('update now action')
                    SLACK_CLIENT.views_open(
                        trigger_id=payload['trigger_id'],
                        view=get_update_modal(payload['channel']['id'])
                    )
                    update_slack_message(payload['response_url'], {'text': 'Okay will remind you in an hour'})
                if action_id == 'snooze_action':
                    print('update later action')
                    schedule_notification(
                        user=payload['user']['id'],
                        channel=payload['channel']['id'],
                        post_at=int(payload['actions'][0]['action_ts'].split('.')[0]) + DEFAULT_SNOOZE_DELAY
                    )
                    update_slack_message(payload['response_url'], {'text': 'Okay will remind you in an hour'})

            return {
                "statusCode": 204
            }
