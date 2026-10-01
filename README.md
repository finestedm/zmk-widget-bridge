# ZMK Widget Bridge

`zmk-widget-bridge` connects a Linux computer to a ZMK keyboard display. The
repository contains both sides of the link:

- a reusable Zephyr/ZMK module exposing an encrypted BLE GATT write service;
- `zmk-widget-sync`, a Linux companion that fetches Open-Meteo weather and the
  next Google Calendar events.

Only display-ready text is sent to the keyboard. Google OAuth credentials and
location configuration remain on the computer.

## Protocol and privacy

The companion sends a 128-byte, versioned packet in ordered BLE chunks. The
packet contains current temperature, WMO weather code, precipitation
probability, a location label, and at most two event time/title pairs. Each
packet has CRC-16/CCITT protection. GATT writes require an encrypted (paired)
Bluetooth connection.

A packet is also a heartbeat. Firmware considers the companion active for 75
seconds after the latest valid packet. If the app exits, Bluetooth drops, or
the computer sleeps, the display automatically returns to its offline screen.

## Linux installation

Requirements: Python 3.11+, BlueZ, and a keyboard firmware containing this
module.

```sh
python3 -m venv ~/.local/share/zmk-widget-sync/venv
~/.local/share/zmk-widget-sync/venv/bin/pip install .
mkdir -p ~/.config/zmk-widget-sync
cp example-config.toml ~/.config/zmk-widget-sync/config.toml
```

Set the keyboard address from `bluetoothctl devices` in `config.toml`. Using an
address is more reliable than discovery because an already connected HID
device may stop advertising.

## Google Calendar authorization

1. Create a Google Cloud project and enable Google Calendar API.
2. Configure the OAuth consent screen.
3. Create an OAuth client of type **Desktop app**.
4. Save its JSON as `~/.config/zmk-widget-sync/credentials.json`.
5. Run:

```sh
zmk-widget-sync auth-google
```

The app requests only `calendar.readonly`. The resulting refresh token is
stored in the configured `token_file` and is never sent to the keyboard.

## Test and run

```sh
zmk-widget-sync discover
zmk-widget-sync once --dry-run
zmk-widget-sync once
zmk-widget-sync run
```

To start automatically using the virtual environment from the installation
steps above, run:

```sh
mkdir -p ~/.config/systemd/user
cp systemd/zmk-widget-sync.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now zmk-widget-sync.service
```

## Add the module to a ZMK config

Add the project to `config/west.yml` and enable it in the central half:

```conf
CONFIG_ZMK_WIDGET_BRIDGE=y
```

Display code can read `struct zmk_widget_bridge_snapshot` with
`zmk_widget_bridge_get_snapshot()` and subscribe to
`zmk_widget_bridge_state_changed`. The API deliberately does not prescribe a
specific screen layout.
