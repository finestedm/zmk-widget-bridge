from __future__ import annotations

import asyncio
import logging

from bleak import BleakClient, BleakScanner

from .config import BluetoothConfig
from .protocol import WRITE_CHARACTERISTIC_UUID, chunk_packet

LOG = logging.getLogger(__name__)


async def discover() -> list[tuple[str, str]]:
    devices = await BleakScanner.discover(timeout=8.0)
    return sorted((device.address, device.name or "(bez nazwy)") for device in devices)


async def resolve_device(config: BluetoothConfig):
    if config.address:
        return config.address
    device = await BleakScanner.find_device_by_name(config.device_name, timeout=10.0)
    if device is None:
        raise RuntimeError(f"Bluetooth device '{config.device_name}' was not found; configure its address")
    return device


async def write_packet(client: BleakClient, packet: bytes, sequence: int) -> None:
    characteristic = client.services.get_characteristic(WRITE_CHARACTERISTIC_UUID)
    if characteristic is None:
        raise RuntimeError("The ZMK widget bridge service is not present; flash the companion-enabled firmware")
    for chunk in chunk_packet(packet, sequence):
        await client.write_gatt_char(characteristic, chunk, response=True)
        await asyncio.sleep(0.01)
