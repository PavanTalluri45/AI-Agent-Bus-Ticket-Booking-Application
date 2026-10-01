from dotenv import load_dotenv
from upstash_redis import Redis

load_dotenv()

try:
    redis = Redis.from_env()
    redis.set("foo", "bar")
    print("Connection successful" if redis.get("foo") == "bar" else "Connection failed")
except Exception as e:
    print(f"Connection failed: {e}")