"""
Alexa Skill Lambda handler for "Crowd Density Monitor".

Voice interactions supported:
  "Alexa, ask crowd monitor what's the density"
      -> queries the central server's HTTP API, speaks back count + tier
  "Alexa, ask crowd monitor if zone one is busy"
      -> same, phrased as a yes/no-style check

Requires:
  - ASK SDK for Python: pip install ask-sdk-core ask-sdk-model
  - Deployed as an AWS Lambda function, linked to an Alexa Skill via the
    Alexa Developer Console (see docs/ALEXA_SKILL_SETUP.md for exact steps
    — this can't be done from this sandbox; it needs your own AWS +
    Amazon developer accounts).
  - The central server's HTTP API must be reachable from the internet
    (e.g. via a tool like ngrok during development, or a proper deployment)
    since AWS Lambda can't reach a "localhost" on your home network directly.

This file is the Lambda function code — deploy it as-is to a Lambda
function once your Alexa Skill is set up.
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
# Publicly-reachable URL for your central server's HTTP API (see note above
# re: ngrok/deployment — this CANNOT be "localhost" or a private LAN IP,
# since Lambda runs in AWS's cloud, not on your home network).
API_BASE_URL = "https://scoured-pajamas-munchkin.ngrok-free.dev"
# -------------------------


def fetch_reading(zone="zone1"):
    """Call the central server's HTTP API and return the parsed JSON reading."""
    url = f"{API_BASE_URL}/reading/{zone}"
    try:
        req = urllib.request.Request(
    url,
    headers={"ngrok-skip-browser-warning": "true"}
)
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Failed to fetch reading: {e}")
        return None


def build_density_speech(reading):
    if reading is None:
        return "Sorry, I couldn't reach the crowd monitoring system right now."

    count = reading["count"]
    tier = reading["tier"]
    pct = reading["density_pct"]

    tier_phrases = {
        "normal": "It's currently at a normal density level.",
        "busy": "It's getting busy right now.",
        "critical": "It's at critical density — please be cautious.",
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
        speech = "Welcome to Crowd Density Monitor. You can ask me what the current density is."
        return handler_input.response_builder.speak(speech).ask(speech).response


class GetDensityIntentHandler(AbstractRequestHandler):
    """Handles: 'what's the crowd density', 'how busy is it', etc.
    Maps to a custom intent 'GetDensityIntent' defined in the skill's
    interaction model — see docs/ALEXA_SKILL_SETUP.md for the exact
    utterances/slots to configure in the Alexa Developer Console."""

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
        speech = "Sorry, something went wrong. Please try again."
        return handler_input.response_builder.speak(speech).ask(speech).response


sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GetDensityIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
