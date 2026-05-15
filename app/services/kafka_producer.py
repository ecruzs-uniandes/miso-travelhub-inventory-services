import json
import logging
import uuid
from datetime import UTC, datetime

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


def publish_tarifa_event(
    event_type: str,
    hotel_id: str,
    habitacion_id: str,
    tarifa_id: str,
    precio_base: float,
    moneda: str,
    descuento: float,
    precio_final: float,
    fecha_inicio: str,
    fecha_fin: str,
) -> bool:
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "hotel_id": str(hotel_id),
        "habitacion_id": str(habitacion_id),
        "tarifa_id": str(tarifa_id),
        "precio_base": precio_base,
        "moneda": moneda,
        "descuento": descuento,
        "precio_final": precio_final,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    message = json.dumps(payload)

    if not settings.kafka_enabled:
        logger.info(f"Kafka disabled — tarifa event logged: {message[:200]}")
        return True

    producer = get_producer()
    if producer is None:
        logger.warning("Kafka producer unavailable — tarifa event not published")
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
        logger.error(f"Failed to publish tarifa event: {e}")
        return False


def close_producer():
    global _producer
    if _producer:
        _producer.flush()
        _producer = None
