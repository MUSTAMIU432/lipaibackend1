# WhatsApp webhook handler for phone verification
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from lipaidox_auth.models import PhoneVerification
import json
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_webhook(request):
    """
    Handle WhatsApp webhook callbacks for message delivery status
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    payload = json.loads(request.body)

    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]["value"]
        status = changes["statuses"][0]

        message_id = status["id"]
        delivery_status = status["status"]
        errors = status.get("errors", [])

        verification = PhoneVerification.objects.get(
            whatsapp_message_id=message_id
        )

        if delivery_status == "delivered":
            verification.record_whatsapp_delivered()
            logger.info(f"WhatsApp OTP delivered for {verification.phone_number}")

        elif delivery_status == "failed":
            error_code = errors[0].get("code", "unknown") if errors else "unknown"
            error_message = errors[0].get("message", "") if errors else ""
            verification.record_whatsapp_failed(
                error_code=str(error_code),
                error_message=error_message,
            )
            
            # Trigger Email fallback
            verification.trigger_email_fallback()
            
            # TODO: Resend OTP via Email here
            logger.warning(f"WhatsApp OTP failed for {verification.phone_number}, triggering Email fallback")

        return JsonResponse({"status": "ok"})

    except (KeyError, IndexError, PhoneVerification.DoesNotExist) as e:
        logger.error(f"WhatsApp webhook error: {e}")
        return JsonResponse({"status": "ok"})  # Return ok to avoid webhook retries
