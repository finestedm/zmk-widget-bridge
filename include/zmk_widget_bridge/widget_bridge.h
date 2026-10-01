/* SPDX-License-Identifier: MIT */

#pragma once

#include <stdbool.h>
#include <stdint.h>

#define ZMK_WIDGET_BRIDGE_LOCATION_LENGTH 16
#define ZMK_WIDGET_BRIDGE_CONDITION_LENGTH 16
#define ZMK_WIDGET_BRIDGE_EVENT_TIME_LENGTH 6
#define ZMK_WIDGET_BRIDGE_EVENT_TITLE_LENGTH 28
#define ZMK_WIDGET_BRIDGE_EVENT_COUNT 2

struct zmk_widget_bridge_weather {
    bool valid;
    int16_t temperature_tenths;
    uint8_t weather_code;
    uint8_t precipitation_probability;
    char location[ZMK_WIDGET_BRIDGE_LOCATION_LENGTH + 1];
    char condition[ZMK_WIDGET_BRIDGE_CONDITION_LENGTH + 1];
};

struct zmk_widget_bridge_event {
    char time[ZMK_WIDGET_BRIDGE_EVENT_TIME_LENGTH + 1];
    char title[ZMK_WIDGET_BRIDGE_EVENT_TITLE_LENGTH + 1];
};

struct zmk_widget_bridge_snapshot {
    bool active;
    uint8_t sequence;
    bool calendar_valid;
    struct zmk_widget_bridge_weather weather;
    struct zmk_widget_bridge_event events[ZMK_WIDGET_BRIDGE_EVENT_COUNT];
};

bool zmk_widget_bridge_is_active(void);
void zmk_widget_bridge_get_snapshot(struct zmk_widget_bridge_snapshot *destination);
