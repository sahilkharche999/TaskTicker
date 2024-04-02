import json

def create_setup_complete_message(details:dict):
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Channel setup complete!"
            }
        },
    ]
    if details['channel_type'] == 'project':
        blocks.append(
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Engineer:*\n<@{details['user_id']}>"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Scrum:*\n<@{details['scrum_id']}>"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Project ID:*\n{details['project_id']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Days:*\n{', '.join(details['days'])}"
                    }
                ]
            }
        )
    elif details['channel_type'] == 'standup':
        blocks.append(
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Scrum:*\n<@{details['scrum_id']}>"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Engineers:*\n{' '.join([f'<@{user}>' for user in details['user_ids']])}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Days:*\n{', '.join(details['days'])}"
                    }
                ]
            }
        )
    return blocks