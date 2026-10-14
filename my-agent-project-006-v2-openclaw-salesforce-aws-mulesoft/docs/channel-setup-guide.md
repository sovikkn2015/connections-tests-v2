# Channel Setup Guide — Project 006

OpenClaw channels are optional. If a token env var is empty, OpenClaw skips that channel gracefully.

## 1. Slack

1. Create a Slack App at [api.slack.com/apps](https://api.slack.com/apps)
2. Enable **Socket Mode** → generates an App Token (`xapp-...`)
3. Add Bot Token Scopes: `chat:write`, `app_mentions:read`, `im:history`
4. Install the app to your workspace → generates Bot Token (`xoxb-...`)
5. Store both tokens:
   ```bash
   export SLACK_BOT_TOKEN="xoxb-..."
   export SLACK_APP_TOKEN="xapp-..."
   ```

Docs: [OpenClaw Slack channel](https://docs.openclaw.ai/channels/slack) · [Slack API docs](https://api.slack.com/docs)

## 2. Telegram

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot`
2. Save the bot token BotFather returns
3. Set the webhook:
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://<OPENCLAW_GATEWAY>/webhook/telegram"
   ```
4. Store the token:
   ```bash
   export TELEGRAM_BOT_TOKEN="<token>"
   ```

Docs: [OpenClaw Telegram channel](https://docs.openclaw.ai/channels/telegram) · [Telegram Bot API](https://core.telegram.org/bots/api)

## 3. WhatsApp

1. Create a [Meta Business account](https://business.facebook.com)
2. Set up WhatsApp Business API in [Meta Developer Portal](https://developers.facebook.com)
3. Create a WhatsApp Business App → get Phone Number ID and Access Token
4. Configure webhook URL pointing to `https://<OPENCLAW_GATEWAY>/webhook/whatsapp`
5. Set a verify token (any string) and match it in Meta's webhook config
6. Store credentials:
   ```bash
   export WHATSAPP_PHONE_NUMBER_ID="<id>"
   export WHATSAPP_ACCESS_TOKEN="<token>"
   export WHATSAPP_VERIFY_TOKEN="<verify-string>"
   ```

Docs: [OpenClaw WhatsApp channel](https://docs.openclaw.ai/channels/whatsapp) · [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp/cloud-api)

## Adding Tokens to AWS Secrets Manager

For production, store all channel tokens in Secrets Manager instead of env vars:

```bash
aws secretsmanager create-secret \
  --name "openclaw/006/channel-tokens" \
  --secret-string '{
    "SLACK_BOT_TOKEN": "xoxb-...",
    "SLACK_APP_TOKEN": "xapp-...",
    "TELEGRAM_BOT_TOKEN": "...",
    "WHATSAPP_PHONE_NUMBER_ID": "...",
    "WHATSAPP_ACCESS_TOKEN": "...",
    "WHATSAPP_VERIFY_TOKEN": "..."
  }'
```

The `setup-secrets.sh` script handles this automatically — see the script for details.

## Verifying Channels

After setting tokens, restart OpenClaw and check logs:

```bash
# Slack — send a DM to the bot in Slack, check logs for:
grep "slack.*connected" openclaw.log

# Telegram — send /start to the bot, check logs for:
grep "telegram.*webhook" openclaw.log

# WhatsApp — send a message to the business number, check logs for:
grep "whatsapp.*ready" openclaw.log
```

OpenClaw's gateway dashboard also shows channel status at `http://localhost:18789/status`.
