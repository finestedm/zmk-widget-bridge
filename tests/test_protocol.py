import struct
import unittest

from zmk_widget_sync.models import CalendarEvent, DisplayData, WeatherData
from zmk_widget_sync.protocol import PACKET_SIZE, chunk_packet, crc16_ccitt, encode_packet


class ProtocolTests(unittest.TestCase):
    def test_packet_layout_and_crc(self):
        data = DisplayData(
            weather=WeatherData(123, 61, 42, "Lodz", "Deszcz"),
            events=[CalendarEvent("14:30", "Spotkanie"), CalendarEvent("CALY", "Urlop")],
        )
        packet = encode_packet(data, 7)
        self.assertEqual(len(packet), PACKET_SIZE)
        self.assertEqual(packet[:7], b"ZWBP\x01\x07\x03")
        self.assertEqual(struct.unpack_from("<h", packet, 7)[0], 123)
        self.assertEqual(packet[10], 42)
        self.assertEqual(packet[43:49].rstrip(b"\0"), b"14:30")
        self.assertEqual(struct.unpack_from("<H", packet, 126)[0], crc16_ccitt(packet[:126]))

    def test_chunks_reassemble_packet(self):
        packet = encode_packet(DisplayData(), 255)
        chunks = chunk_packet(packet, 255)
        rebuilt = bytearray(PACKET_SIZE)
        for chunk in chunks:
            self.assertEqual(chunk[0:2], b"\xa5\xff")
            offset = chunk[2]
            rebuilt[offset : offset + len(chunk) - 3] = chunk[3:]
        self.assertEqual(bytes(rebuilt), packet)

    def test_polish_text_is_normalized_for_display_font(self):
        data = DisplayData(events=[CalendarEvent("12:00", "Zażółć gęślą")])
        packet = encode_packet(data, 0)
        self.assertIn(b"Zazolc gesla", packet)


if __name__ == "__main__":
    unittest.main()
