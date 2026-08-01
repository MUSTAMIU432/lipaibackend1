import requests
from django.conf import settings
from lipaidox_auth.models import PhoneVerification


def send_otp_via_whatsapp(verification: PhoneVerification) -> bool:
    """
    Sends OTP to user via WhatsApp Business API.
    Returns True on success, False on failure.
    """
    url = (
        f"https://graph.facebook.com/v18.0/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": verification.e164_phone_number,
        "type": "template",
        "template": {
            "name": "otp_verification",
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": verification.otp_code,
                        }
                    ],
                }
            ],
        },
    }

    response = requests.post(url, json=payload, headers=headers, timeout=10)

    if response.status_code == 200:
        data = response.json()
        message_id = data["messages"][0]["id"]
        verification.record_whatsapp_sent(message_id=message_id)
        return True

    verification.record_whatsapp_failed(
        error_code=str(response.status_code),
        error_message=response.text,
    )
    return False
