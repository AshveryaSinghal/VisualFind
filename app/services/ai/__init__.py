"""
AI Shopping Recommendation Engine.

Everything Gemini-related lives in this package, kept deliberately separate
from the existing (unmodified) visual-search pipeline in app/services/*.
No Gemini call happens anywhere outside this package, and no UI component
ever talks to Gemini directly - the router (app/routers/ai.py) is the only
caller.

Modules
-------
gemini_service        Thin, low-level wrapper around the Gemini REST API.
                       Nothing here knows about shopping, products, or chat.
prompt_builder         Builds the system instructions + JSON response
                       schemas used for each kind of Gemini call.
conversation_manager   Validates/normalizes the chat transcript sent by the
                       client and turns it into the format gemini_service
                       expects. This app is stateless between requests (the
                       frontend resends the transcript each turn - the same
                       pattern used by the API directly) so "memory" here
                       means "faithfully replaying prior turns", not a
                       server-side session store.
intent_parser          Turns a raw Gemini JSON reply for a chat turn into a
                       validated IntentResult.
preference_extractor   Cleans/normalizes the structured preferences Gemini
                       extracted (budget, category, brand, etc.) into a
                       concrete search string for the real product pipeline.
recommendation_engine  Given the *real* products the existing search
                       pipeline found, asks Gemini to pick and justify one
                       best product - by index into that real list only, so
                       it is structurally impossible to invent a product or
                       a purchase link that didn't come from the backend.
"""
