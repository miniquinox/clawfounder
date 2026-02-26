# WhatsApp — Business API Connector

Connect ClawFounder to WhatsApp using the Meta WhatsApp Cloud API (Business accounts only).

## Prerequisites

**One-time Meta Developer Setup (~10 minutes):**
1. Go to [developers.facebook.com](https://developers.facebook.com/) and log in (or create an account)
2. Click **Create App** → Choose **Business** type → Name it (e.g. "ClawFounder")
3. In your app dashboard, click **Add Product** → Find **WhatsApp** → Click **Set Up**
4. You'll land on the **WhatsApp > API Setup** page — this has everything you need:

**Get your Phone Number ID:**
5. Under "From", you'll see a test phone number and its **Phone Number ID** — copy this

**Get a permanent Access Token:**
6. Go to [Business Settings > System Users](https://business.facebook.com/settings/system-users)
7. Click **Add** → Name it (e.g. "ClawFounder Bot") → Set role to **Admin**
8. Click **Generate New Token** → Select your app → Add permissions: `whatsapp_business_messaging`, `whatsapp_business_management`
9. Copy the token — this is your **permanent** access token (the one on the API Setup page expires in 24h)

**Add test recipients:**
10. Back on API Setup, under "To", click **Manage phone number list** → Add phone numbers you want to message during development

## Important Notes

- **24-hour messaging window**: You can only send free-form messages within 24 hours of the user's last message. Outside this window, you **must** use `whatsapp_send_template` with a pre-approved template.
- **Business accounts only**: This API does not work with personal WhatsApp accounts.
- **Free tier**: 1,000 conversations/month at no cost.

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `WHATSAPP_ACCESS_TOKEN` | Permanent token from System User (step 9) | Yes |
| `WHATSAPP_PHONE_NUMBER_ID` | Phone Number ID from API Setup (step 5) | Yes |
| `WHATSAPP_DEFAULT_RECIPIENT` | Default recipient phone number, e.g. `14155551234` (no `+`) | No |

## Setup

```bash
cd connectors/whatsapp
bash install.sh
```

## Tools

### Messaging
| Tool | Description |
|------|-------------|
| `whatsapp_send_message` | Send a text message to a phone number |
| `whatsapp_send_template` | Send a pre-approved template message (required to initiate conversations) |
| `whatsapp_send_image` | Send an image by URL with optional caption |
| `whatsapp_send_document` | Send a document/file by URL with optional caption and filename |
| `whatsapp_send_location` | Send a GPS location with optional name and address |
| `whatsapp_send_contacts` | Share a contact card (name + phone) |
| `whatsapp_send_interactive` | Send reply buttons (max 3) or list menus |

### Message Management
| Tool | Description |
|------|-------------|
| `whatsapp_send_reaction` | React to a message with an emoji |
| `whatsapp_mark_read` | Mark a message as read (sends blue checkmarks) |

### Info
| Tool | Description |
|------|-------------|
| `whatsapp_get_profile` | Get WhatsApp Business profile info (about, address, email, websites) |

## Workflow Examples

- **"Send a WhatsApp to +1 415 555 1234"** → `whatsapp_send_message` with the text and phone number
- **"Start a conversation with a new contact"** → `whatsapp_send_template` (required outside 24h window) → then `whatsapp_send_message` for follow-ups
- **"Send this PDF to my client"** → `whatsapp_send_document` with the document URL and filename
- **"Share our office location"** → `whatsapp_send_location` with lat/long, name, and address
- **"Send them a menu to pick from"** → `whatsapp_send_interactive` with type `list` and sections
- **"React to that message with a thumbs up"** → `whatsapp_send_reaction` with message_id and emoji
- **"Mark those messages as read"** → `whatsapp_mark_read` with message_id

## Testing

```bash
python3 -m pytest connectors/whatsapp/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "Send a WhatsApp message to 14155551234 saying hello"
```
