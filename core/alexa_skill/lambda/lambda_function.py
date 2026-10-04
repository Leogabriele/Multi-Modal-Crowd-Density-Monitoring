"""
Alexa Skill Lambda handler for "Crowd Density Monitor".
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

API_BASE_URL = "https://scoured-pajamas-munchkin.ngrok-free.dev"


def fetch_reading(zone="zone1"):
    url = f"{API_BASE_URL}/reading/{zone}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "ngrok-skip-browser-warning": "true",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AlexaSkill/1.0"
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
        return (
            "I could not connect to the crowd monitoring server. "
            "Please ensure your urban server and ngrok tunnel are running on your computer."
        )

    try:
        count = float(reading.get("count", 0.0))
        tier = str(reading.get("tier", "normal")).lower()
        pct = float(reading.get("density_percentage", reading.get("density_pct", 0.0)))
        loitering = int(reading.get("loitering", 0))
        animals = int(reading.get("animals", 0))

        tier_phrases = {
            "normal": "It is currently at a normal density level.",
            "busy": "It is getting busy right now.",
            "critical": "It is at critical density. Please exercise caution.",
        }
        tier_phrase = tier_phrases.get(tier, "It is currently operating normally.")

        people_word = "person" if round(count) == 1 else "people"
        speech = (
            f"There is approximately {round(count)} {people_word} in the monitored area, "
            f"which is about {round(pct)} percent of capacity. {tier_phrase}"
        )

        if loitering > 0:
            speech += " Attention: A loitering alert is currently active in the restricted area."
        elif animals > 0:
            speech += f" Also, {animals} stray animal is currently detected on site."

        return speech
    except Exception as e:
        logger.error(f"Error building speech: {e}")
        return "The crowd monitoring system is online, and density levels are currently normal."


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        speech = "Welcome to Crowd Density Monitor. You can ask me what the current density is, or how busy it is."
        return handler_input.response_builder.speak(speech).ask(speech).response


class GetDensityIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return is_intent_name("GetDensityIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        reading = fetch_reading("zone1")
        speech = build_density_speech(reading)
        return (
            handler_input.response_builder
            .speak(speech)
            .set_card_simple("Crowd Density Status", speech)
            .response
        )


class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        reading = fetch_reading("zone1")
        speech = build_density_speech(reading)
        return handler_input.response_builder.speak(speech).response


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        speech = "You can ask: what's the crowd density, or how busy is it."
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
        reading = fetch_reading("zone1")
        speech = build_density_speech(reading)
        return handler_input.response_builder.speak(speech).response


sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GetDensityIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
