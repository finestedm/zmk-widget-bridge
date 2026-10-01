from __future__ import annotations

import struct
import unicodedata

from .models import DisplayData

PACKET_SIZE = 128
PROTOCOL_VERSION = 1
CHUNK_MARKER = 0xA5
CHUNK_PAYLOAD_SIZE = 17

SERVICE_UUID = "5a574200-8e3e-4d9b-a7a6-19f65dbb0100"
WRITE_CHARACTERISTIC_UUID = "5a574201-8e3e-4d9b-a7a6-19f65dbb0100"

POLISH_ASCII = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
        "Ą": "A",
        "Ć": "C",
        "Ę": "E",
        "Ł": "L",
        "Ń": "N",
        "Ó": "O",
        "Ś": "S",
        "Ź": "Z",
        "Ż": "Z",
    }
)


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _ascii(value: str, size: int) -> bytes:
    normalized = unicodedata.normalize("NFKD", value.translate(POLISH_ASCII))
    value_bytes = normalized.encode("ascii", "ignore")[:size]
    return value_bytes.ljust(size, b"\0")


def encode_packet(data: DisplayData, sequence: int) -> bytes:
    packet = bytearray(PACKET_SIZE)
    packet[0:4] = b"ZWBP"
    packet[4] = PROTOCOL_VERSION
    packet[5] = sequence & 0xFF

    flags = 0
    if data.weather is not None:
        flags |= 0x01
        weather = data.weather
        struct.pack_into("<h", packet, 7, max(-32768, min(32767, weather.temperature_tenths)))
        packet[9] = weather.weather_code & 0xFF
        packet[10] = max(0, min(100, weather.precipitation_probability))
        packet[11:27] = _ascii(weather.location, 16)
        packet[27:43] = _ascii(weather.condition, 16)

    if data.events:
        flags |= 0x02
        first = data.events[0]
        packet[43:49] = _ascii(first.time_label, 6)
        packet[49:77] = _ascii(first.title, 28)
        if len(data.events) > 1:
            second = data.events[1]
            packet[77:83] = _ascii(second.time_label, 6)
            packet[83:111] = _ascii(second.title, 28)

    packet[6] = flags
    crc = crc16_ccitt(packet[:126])
    struct.pack_into("<H", packet, 126, crc)
    return bytes(packet)


def chunk_packet(packet: bytes, sequence: int) -> list[bytes]:
    if len(packet) != PACKET_SIZE:
        raise ValueError(f"packet must contain exactly {PACKET_SIZE} bytes")
    chunks: list[bytes] = []
    for offset in range(0, PACKET_SIZE, CHUNK_PAYLOAD_SIZE):
        chunks.append(bytes((CHUNK_MARKER, sequence & 0xFF, offset)) + packet[offset : offset + CHUNK_PAYLOAD_SIZE])
    return chunks
