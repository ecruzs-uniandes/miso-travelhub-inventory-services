import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.config import settings

logger = logging.getLogger(__name__)

_producer = None


def get_producer():
    global _producer
    if not settings.kafka_enabled:
        return None
    if _producer is None:
        try:
            from confluent_kafka import Producer
            _producer = Producer({
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "client.id": settings.service_name,
                "acks": "all",
                "retries": 3,
                "linger.ms": 10,
            })
            logger.info("Kafka producer initialized")
        except Exception as e:
            logger.error(f"Failed to create Kafka producer: {e}")
            return None
    return _producer


def _delivery_callback(err, msg):
    if err:
        logger.error(f"Kafka delivery failed: {err}")
    else:
        logger.info(f"Event delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")


def publish_rate_event(
    event_type: str,
    hotel_id: UUID,
    room_id: UUID,
    rate_id: UUID,
    base_price: Decimal,
    currency: str,
    discount: Decimal,
    final_price: Decimal,
    valid_from: str,
    valid_to: str,
    status: str,
) -> bool:
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "hotel_id": str(hotel_id),
        "room_id": str(room_id),
        "rate_id": str(rate_id),
        "base_price": str(base_price),
        "currency": currency,
        "discount": str(discount),
        "final_price": str(final_price),
        "valid_from": valid_from,
        "valid_to": valid_to,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    message = json.dumps(payload)

    if not settings.kafka_enabled:
        logger.info(f"Kafka disabled — rate event logged: {message[:200]}")
        return True

    producer = get_producer()
    if producer is None:
        logger.warning("Kafka producer unavailable — rate event not published")
        return False

    try:
        producer.produce(
            topic=settings.kafka_topic_inventory_rates,
            key=str(hotel_id).encode("utf-8"),
            value=message.encode("utf-8"),
            callback=_delivery_callback,
        )
        producer.poll(0)
        return True
    except Exception as e:
        logger.error(f"Failed to publish rate event: {e}")
        return False


def close_producer():
    global _producer
    if _producer:
        _producer.flush()
        _producer = None
