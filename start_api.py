from candy_nsfw_plus_api import app
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
print("="*60)
print("CANDY.NSFW+ ENHANCED API")
print("="*60)
uvicorn.run(app, host="127.0.0.1", port=9500, log_level="info")
