"""
Shared test setup.

app/config.py's Settings() has no defaults for serpapi_key / cloudinary_*
(by design -- the app should fail loudly at startup if real credentials are
missing, not silently degrade). That's correct for production, but it means
importing anything that transitively touches app.config (most of the
pipeline does) will raise a pydantic ValidationError unless *some* value is
present.

These are dummy, non-functional placeholders used only so imports succeed
in a test/CI environment with no real credentials configured. No test in
this suite makes a real network call to SerpApi/Cloudinary -- every test
below is a pure-function or fake-strategy test.
"""

import os

os.environ.setdefault("SERPAPI_KEY", "test-serpapi-key")
os.environ.setdefault("CLOUDINARY_CLOUD_NAME", "test-cloud")
os.environ.setdefault("CLOUDINARY_API_KEY", "test-cloud-key")
os.environ.setdefault("CLOUDINARY_API_SECRET", "test-cloud-secret")
