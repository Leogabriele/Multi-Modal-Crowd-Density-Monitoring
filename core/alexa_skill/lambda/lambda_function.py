"""
Alexa Skill Lambda handler for "Crowd Density Monitor".

Voice interactions supported:
  "Alexa, ask crowd monitor what's the density"
      -> queries the central server's HTTP API, speaks back count + tier
  "Alexa, ask crowd monitor if zone one is busy"
      -> same, phrased as a yes/no-style check
"""

import logging
import urllib.request
import json

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---- CONFIGURE THIS ----
# Publicly-reachable URL for your central server's HTTP API via ngrok
API_BASE_URL = "https://scoured-pajamas-munchkin.ngrok-free.dev"
# -------------------------


def fetch_reading(zone="zone1"):
    """Call the central server's HTTP API and return the parsed JSON reading."""
    url = f"{API_BASE_URL}/reading/{zone}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "ngrok-skip-browser-warning": "true",
                "User-Agent": "Mozilla/5.0 (compatible; AlexaSkill/1.0)"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        logger.error(f"Failed to fetch reading from {url}: {e}")
        return None


def build_density_speech(reading):
    if reading is None:
        return "Sorry, I couldn't reach the crowd monitoring server right now. Please make sure your server and ngrok tunnel are running."

    count = reading.get("count", 0.0)
    tier = reading.get("tier", "normal")
    pct = reading.get("density_pct", 0.0)

    tier_phrases = {
        "normal": "It is currently at a normal density level.",
        "busy": "It is getting busy right now.",
        "critical": "It is at critical density — please be cautious.",
    }
    tier_phrase = tier_phrases.get(tier, "")

    return (
        f"There are approximately {round(count)} people in the monitored area, "
        f"which is about {round(pct)} percent of capacity. {tier_phrase}"
    )


# ---------------------------------------------------------------------------
# Alexa Skill request handlers
# ---------------------------------------------------------------------------
class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        speech = "Welcome to Crowd Density Monitor. You can ask me what the current density is, or ask if zone one is busy."
        return handler_input.response_builder.speak(speech).ask(speech).response


class GetDensityIntentHandler(AbstractRequestHandler):
    """Handles: 'what's the crowd density', 'how busy is it', etc."""
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return is_intent_name("GetDensityIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        reading = fetch_reading("zone1")
        speech = build_density_speech(reading)
        return handler_input.response_builder.speak(speech).response


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        speech = "You can ask me things like: what's the current crowd density?"
        return handler_input.response_builder.speak(speech).ask(speech).response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input: HandlerInput) -> Response:
        return handler_input.response_builder.speak("Goodbye!").response


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception) -> bool:
        return True

    def handle(self, handler_input: HandlerInput, exception) -> Response:
        logger.error(exception, exc_info=True)
        speech = "Sorry, something went wrong while processing your request. Please try again."
        return handler_input.response_builder.speak(speech).response


sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GetDensityIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
