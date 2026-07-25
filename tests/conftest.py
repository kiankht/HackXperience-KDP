import os


# Automated tests must never consume paid live-model quota or depend on secrets.
os.environ["AI_MODE"] = "fallback"
