import datetime
import logging

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

_INPUT_RATE = 0.075 / 1_000_000  # Gemini 2.5 Pro: $0.075 / 1M input tokens
_OUTPUT_RATE = 0.30 / 1_000_000  # Gemini 2.5 Pro: $0.30  / 1M output tokens


class CostTracker:
    """Tracks LLM API costs per request and accumulates daily/monthly stats in Redis."""

    def __init__(
        self, input_rate: float = _INPUT_RATE, output_rate: float = _OUTPUT_RATE
    ):
        self.input_rate = input_rate
        self.output_rate = output_rate

    def add(self, input_tokens: int, output_tokens: int) -> float:
        """Records token usage in Redis and returns the cost for this call."""
        cost = (input_tokens * self.input_rate) + (output_tokens * self.output_rate)
        try:
            r = get_redis_client()
            today = datetime.date.today().isoformat()
            month = today[:7]
            for key, ttl in [
                (f"cost:daily:{today}", 30 * 86400),
                (f"cost:monthly:{month}", 365 * 86400),
            ]:
                r.hincrby(key, "input", input_tokens)
                r.hincrby(key, "output", output_tokens)
                r.hincrbyfloat(key, "cost", cost)
                r.expire(key, ttl)
        except Exception as e:
            logger.warning("CostTracker: Redis write failed: %s", e)
        return cost

    def get_stats(self) -> dict:
        """Returns today's and the current month's accumulated stats from Redis."""
        r = get_redis_client()
        today = datetime.date.today().isoformat()
        month = today[:7]
        d = r.hgetall(f"cost:daily:{today}") or {}
        m = r.hgetall(f"cost:monthly:{month}") or {}
        return {
            "today": {
                "date": today,
                "input_tokens": int(d.get("input", 0)),
                "output_tokens": int(d.get("output", 0)),
                "cost_usd": round(float(d.get("cost", 0.0)), 6),
            },
            "month": {
                "month": month,
                "input_tokens": int(m.get("input", 0)),
                "output_tokens": int(m.get("output", 0)),
                "cost_usd": round(float(m.get("cost", 0.0)), 6),
            },
        }
