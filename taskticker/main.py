from datetime import date

from helper import *
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
            if body['command'][0] == '/setup':
                if is_from_admin(body):
                    SLACK_CLIENT.views_open(
                        trigger_id=body['trigger_id'][0],
                        view=get_setup_modal(body['channel_id'][0])
                    )
                else:
                    return {
                        "statusCode": 200,
                        "body": "You are not authorized to use this command. Please contact admin."
                    }
            elif body['command'][0] == '/update':
                res = SLACK_CLIENT.views_open(
                    trigger_id=body['trigger_id'][0],
                    view=get_update_modal(body['channel_id'][0])
                )
                print('saving update response', res)
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
                    update = retrieve_update_details(payload)
                    details = DYNAMO_MAPPING_DB_Table.get_item(
                        Key={
                            'channel_id': payload['view']['blocks'][1]['text']['text']
                        }
                    ).get('Item', {})
                    print('details', details)
                    res = post_updates_to_log1(
                        project_id=details['project_id'],
                        update=update['update'],
                        sprint_start=date.today(),
                        sprint_end=date.today(),
                        blocker=update['blocker']
                    )
                    print('log1 response', res)

                    res = post_updates_to_slack(
                        channel_id=payload['view']['blocks'][1]['text']['text'],
                        update=update['update'],
                        blocker=update['blocker']
                    )
                    print('slack response', res)

            if is_button_pressed(payload):
                action_id = get_action_id(payload)
                print('action id:', action_id)
                if action_id == 'update_now_action':
                    channel_id = get_channel_from_action_button(payload)
                    print('update now action')
                    SLACK_CLIENT.views_open(
                        trigger_id=payload['trigger_id'],
                        view=get_update_modal(channel_id=channel_id)
                    )
                    update_slack_message(payload['response_url'], {'text': 'Thanks for updating!'})
                if action_id == 'snooze_action':
                    print('update later action')
                    channel_id = get_channel_from_action_button(payload)
                    schedule_notification(
                        user=payload['user']['id'],
                        channel_id=channel_id,
                        post_at=int(payload['actions'][0]['action_ts'].split('.')[0]) + DEFAULT_SNOOZE_DELAY
                    )
                    update_slack_message(
                        response_url=payload['response_url'],
                        message={
                            "text": "Okay will remind you in an hour.",
                            "blocks": [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": "Okay will remind you in an hour.\n"
                                                "Or you can post update anytime with `/update` command"
                                    }
                                }
                            ]
                        })

            if is_checkboxes_action(payload):
                action_id = get_action_id(payload)
                if action_id == 'blocker-checkbox-action':
                    print('blocker checkbox action')
                    is_blocker = bool(payload['actions'][0]['selected_options'])
                    res = SLACK_CLIENT.views_update(
                        view_id=payload['view']['id'],
                        hash=payload['view']['hash'],
                        view=get_update_modal(
                            channel_id=payload['view']['blocks'][1]['text']['text'],
                            is_blocker=is_blocker
                        )
                    )
                    print('update view response', res)

            return {
                "statusCode": 204
            }
