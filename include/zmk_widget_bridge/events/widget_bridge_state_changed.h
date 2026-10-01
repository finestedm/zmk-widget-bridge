/* SPDX-License-Identifier: MIT */

#pragma once

#include <stdbool.h>
#include <stdint.h>

#include <zmk/event_manager.h>

struct zmk_widget_bridge_state_changed {
    bool active;
    uint8_t sequence;
};

ZMK_EVENT_DECLARE(zmk_widget_bridge_state_changed);
