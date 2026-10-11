"""Redis is a wakeup hint. Committed Postgres jobs are authoritative."""
import logging
import os


def client():
    import redis
    return redis.Redis.from_url(os.environ['APP_REDIS_URL'], socket_connect_timeout=3,
                                socket_timeout=7, decode_responses=True)


def notify():
    if not os.getenv('APP_REDIS_URL'):
        return
    try:
        with client() as connection:
            pipe = connection.pipeline()
            pipe.lpush('metaflow:monitor:wakeup', '1')
            pipe.ltrim('metaflow:monitor:wakeup', 0, 99)
            pipe.expire('metaflow:monitor:wakeup', 60)
            pipe.execute()
    except Exception:
        # No payload or credentials in queue messages or logs.
        logging.getLogger(__name__).warning('Redis wakeup unavailable; worker will scan durable jobs.')


def wait():
    if not os.getenv('APP_REDIS_URL'):
        return False
    try:
        with client() as connection:
            connection.blpop('metaflow:monitor:wakeup', timeout=5)
        return True
    except Exception:
        logging.getLogger(__name__).warning('Redis unavailable; falling back to timed job scans.')
        return False
