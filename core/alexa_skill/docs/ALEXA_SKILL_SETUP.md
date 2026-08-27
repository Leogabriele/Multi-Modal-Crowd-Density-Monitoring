# Alexa Skill Setup

This can't be fully set up from this sandbox — it needs your own Amazon
Developer account and AWS account. Here's the exact path.

## 1. Make your central server reachable from the internet

AWS Lambda (where the skill code runs) cannot reach `localhost` or a
private home-network IP. For development/testing, the simplest option:

```bash
# Install ngrok (free tier is enough): https://ngrok.com/download
ngrok http 8000
```
This gives you a public URL (e.g. `https://abc123.ngrok-free.app`) that
forwards to your local server's port 8000. Use this as `API_BASE_URL` in
`lambda/lambda_function.py`.

(For a real deployment beyond testing, host the server properly — e.g. a
small cloud VM — rather than relying on ngrok long-term.)

## 2. Create the Alexa Skill

1. Go to https://developer.amazon.com/alexa/console/ask, sign in, "Create Skill"
2. Name it "Crowd Density Monitor", choose "Custom" model, "Provision your own" for hosting
3. In the **Interaction Model** (JSON Editor), use:

```json
{
  "interactionModel": {
    "languageModel": {
      "invocationName": "crowd monitor",
      "intents": [
        {
          "name": "AMAZON.HelpIntent",
          "samples": []
        },
        {
          "name": "AMAZON.CancelIntent",
          "samples": []
        },
        {
          "name": "AMAZON.StopIntent",
          "samples": []
        },
        {
          "name": "GetDensityIntent",
          "samples": [
            "what's the crowd density",
            "how busy is it",
            "what's the current density",
            "is it busy",
            "how many people are there",
            "what's the crowd level"
          ]
        }
      ]
    }
  }
}
```

## 3. Deploy the Lambda function

1. AWS Console -> Lambda -> Create function -> Python 3.12 runtime
2. Package `lambda_function.py` with its dependencies:
   ```bash
   pip install ask-sdk-core ask-sdk-model -t package/ --break-system-packages
   cp lambda_function.py package/
   cd package && zip -r ../lambda_deploy.zip . && cd ..
   ```
3. Upload `lambda_deploy.zip` to the Lambda function.
4. Set the Lambda function's handler to `lambda_function.lambda_handler`.
5. Back in the Alexa Developer Console -> Endpoint -> paste your Lambda
   function's ARN.
6. Add the Alexa Skill's Skill ID as an allowed trigger in your Lambda
   function's permissions (the console usually prompts you to do this).

## 4. Test

In the Alexa Developer Console's "Test" tab (enable testing for
"Development"), type or say:
> "ask crowd monitor what's the density"

Or on a real Echo Dot registered to the same developer account:
> "Alexa, ask crowd monitor what's the density"

## What's already verified (in this sandbox, without a real Alexa account)

- `build_density_speech()` — tested for all three tiers plus the
  server-unreachable case — all produce correct, natural speech text.
- The skill builds successfully with all 5 handlers registered
  (Launch, GetDensity, Help, Cancel/Stop, SessionEnded + exception handler).
- **Not verified here** (needs your real accounts): the actual voice
  recognition/interaction model matching, and the live network call from
  AWS Lambda to your server.
