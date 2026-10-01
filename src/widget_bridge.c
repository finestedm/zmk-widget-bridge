/* SPDX-License-Identifier: MIT */

#include <errno.h>
#include <string.h>

#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>

#include <zmk/event_manager.h>

#include <zmk_widget_bridge/events/widget_bridge_state_changed.h>
#include <zmk_widget_bridge/widget_bridge.h>

LOG_MODULE_REGISTER(zmk_widget_bridge, CONFIG_ZMK_WIDGET_BRIDGE_LOG_LEVEL);

#define WIDGET_BRIDGE_UUID(value)                                                                 \
    BT_UUID_128_ENCODE(value, 0x8e3e, 0x4d9b, 0xa7a6, 0x19f65dbb0100)
#define WIDGET_BRIDGE_SERVICE_UUID WIDGET_BRIDGE_UUID(0x5a574200)
#define WIDGET_BRIDGE_WRITE_UUID WIDGET_BRIDGE_UUID(0x5a574201)

#define PACKET_SIZE 128
#define PACKET_BODY_SIZE 126
#define PACKET_VERSION 1
#define CHUNK_MARKER 0xA5

#define PACKET_FLAGS_OFFSET 6
#define PACKET_TEMPERATURE_OFFSET 7
#define PACKET_WEATHER_CODE_OFFSET 9
#define PACKET_PRECIPITATION_OFFSET 10
#define PACKET_LOCATION_OFFSET 11
#define PACKET_CONDITION_OFFSET 27
#define PACKET_EVENT_1_TIME_OFFSET 43
#define PACKET_EVENT_1_TITLE_OFFSET 49
#define PACKET_EVENT_2_TIME_OFFSET 77
#define PACKET_EVENT_2_TITLE_OFFSET 83
#define PACKET_CRC_OFFSET 126

#define PACKET_FLAG_WEATHER BIT(0)
#define PACKET_FLAG_CALENDAR BIT(1)

static struct zmk_widget_bridge_snapshot snapshot;
static K_MUTEX_DEFINE(snapshot_mutex);
static uint8_t receive_buffer[PACKET_SIZE];
static uint8_t receive_sequence;
static uint16_t receive_offset;

ZMK_EVENT_IMPL(zmk_widget_bridge_state_changed);

static uint16_t crc16_ccitt(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFF;

    for (size_t index = 0; index < length; index++) {
        crc ^= (uint16_t)data[index] << 8;
        for (uint8_t bit = 0; bit < 8; bit++) {
            crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1;
        }
    }
    return crc;
}

static void copy_text(char *destination, size_t destination_size, const uint8_t *source,
                      size_t source_size) {
    const size_t length = MIN(destination_size - 1, source_size);
    memcpy(destination, source, length);
    destination[length] = '\0';
}

static void raise_state_changed(bool active, uint8_t sequence) {
    raise_zmk_widget_bridge_state_changed((struct zmk_widget_bridge_state_changed){
        .active = active,
        .sequence = sequence,
    });
}

static void active_timeout_work_handler(struct k_work *work) {
    ARG_UNUSED(work);

    k_mutex_lock(&snapshot_mutex, K_FOREVER);
    const bool was_active = snapshot.active;
    const uint8_t sequence = snapshot.sequence;
    snapshot.active = false;
    k_mutex_unlock(&snapshot_mutex);

    if (was_active) {
        LOG_INF("Companion heartbeat expired");
        raise_state_changed(false, sequence);
    }
}

K_WORK_DELAYABLE_DEFINE(active_timeout_work, active_timeout_work_handler);

static int process_packet(void) {
    if (memcmp(receive_buffer, "ZWBP", 4) != 0 || receive_buffer[4] != PACKET_VERSION ||
        receive_buffer[5] != receive_sequence) {
        LOG_WRN("Rejected widget packet header");
        return -EINVAL;
    }

    const uint16_t expected_crc = sys_get_le16(&receive_buffer[PACKET_CRC_OFFSET]);
    const uint16_t actual_crc = crc16_ccitt(receive_buffer, PACKET_BODY_SIZE);
    if (expected_crc != actual_crc) {
        LOG_WRN("Rejected widget packet CRC: expected %04x, calculated %04x", expected_crc,
                actual_crc);
        return -EBADMSG;
    }

    const uint8_t flags = receive_buffer[PACKET_FLAGS_OFFSET];
    k_mutex_lock(&snapshot_mutex, K_FOREVER);
    snapshot.active = true;
    snapshot.sequence = receive_sequence;
    snapshot.weather.valid = (flags & PACKET_FLAG_WEATHER) != 0;
    snapshot.calendar_valid = (flags & PACKET_FLAG_CALENDAR) != 0;
    snapshot.weather.temperature_tenths =
        (int16_t)sys_get_le16(&receive_buffer[PACKET_TEMPERATURE_OFFSET]);
    snapshot.weather.weather_code = receive_buffer[PACKET_WEATHER_CODE_OFFSET];
    snapshot.weather.precipitation_probability = receive_buffer[PACKET_PRECIPITATION_OFFSET];
    copy_text(snapshot.weather.location, sizeof(snapshot.weather.location),
              &receive_buffer[PACKET_LOCATION_OFFSET], ZMK_WIDGET_BRIDGE_LOCATION_LENGTH);
    copy_text(snapshot.weather.condition, sizeof(snapshot.weather.condition),
              &receive_buffer[PACKET_CONDITION_OFFSET], ZMK_WIDGET_BRIDGE_CONDITION_LENGTH);
    copy_text(snapshot.events[0].time, sizeof(snapshot.events[0].time),
              &receive_buffer[PACKET_EVENT_1_TIME_OFFSET], ZMK_WIDGET_BRIDGE_EVENT_TIME_LENGTH);
    copy_text(snapshot.events[0].title, sizeof(snapshot.events[0].title),
              &receive_buffer[PACKET_EVENT_1_TITLE_OFFSET], ZMK_WIDGET_BRIDGE_EVENT_TITLE_LENGTH);
    copy_text(snapshot.events[1].time, sizeof(snapshot.events[1].time),
              &receive_buffer[PACKET_EVENT_2_TIME_OFFSET], ZMK_WIDGET_BRIDGE_EVENT_TIME_LENGTH);
    copy_text(snapshot.events[1].title, sizeof(snapshot.events[1].title),
              &receive_buffer[PACKET_EVENT_2_TITLE_OFFSET], ZMK_WIDGET_BRIDGE_EVENT_TITLE_LENGTH);
    k_mutex_unlock(&snapshot_mutex);

    k_work_reschedule(&active_timeout_work,
                      K_SECONDS(CONFIG_ZMK_WIDGET_BRIDGE_ACTIVE_TIMEOUT_SECONDS));
    raise_state_changed(true, receive_sequence);
    LOG_DBG("Accepted widget packet %u", receive_sequence);
    return 0;
}

static ssize_t write_widget_data(struct bt_conn *connection, const struct bt_gatt_attr *attribute,
                                 const void *data, uint16_t length, uint16_t offset,
                                 uint8_t flags) {
    ARG_UNUSED(connection);
    ARG_UNUSED(attribute);
    ARG_UNUSED(offset);
    ARG_UNUSED(flags);

    const uint8_t *chunk = data;
    if (length < 4 || chunk[0] != CHUNK_MARKER) {
        return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
    }

    const uint8_t sequence = chunk[1];
    const uint16_t chunk_offset = chunk[2];
    const uint16_t payload_length = length - 3;

    if (chunk_offset == 0) {
        receive_sequence = sequence;
        receive_offset = 0;
    }
    if (sequence != receive_sequence || chunk_offset != receive_offset ||
        receive_offset + payload_length > PACKET_SIZE) {
        receive_offset = 0;
        return BT_GATT_ERR(BT_ATT_ERR_INVALID_OFFSET);
    }

    memcpy(&receive_buffer[receive_offset], &chunk[3], payload_length);
    receive_offset += payload_length;

    if (receive_offset == PACKET_SIZE) {
        receive_offset = 0;
        if (process_packet() < 0) {
            return BT_GATT_ERR(BT_ATT_ERR_VALUE_NOT_ALLOWED);
        }
    }

    return length;
}

BT_GATT_SERVICE_DEFINE(
    widget_bridge_service,
    BT_GATT_PRIMARY_SERVICE(BT_UUID_DECLARE_128(WIDGET_BRIDGE_SERVICE_UUID)),
    BT_GATT_CHARACTERISTIC(BT_UUID_DECLARE_128(WIDGET_BRIDGE_WRITE_UUID), BT_GATT_CHRC_WRITE,
                           BT_GATT_PERM_WRITE_ENCRYPT, NULL, write_widget_data, NULL));

bool zmk_widget_bridge_is_active(void) {
    k_mutex_lock(&snapshot_mutex, K_FOREVER);
    const bool active = snapshot.active;
    k_mutex_unlock(&snapshot_mutex);
    return active;
}

void zmk_widget_bridge_get_snapshot(struct zmk_widget_bridge_snapshot *destination) {
    if (destination == NULL) {
        return;
    }

    k_mutex_lock(&snapshot_mutex, K_FOREVER);
    memcpy(destination, &snapshot, sizeof(*destination));
    k_mutex_unlock(&snapshot_mutex);
}
