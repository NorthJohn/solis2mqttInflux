Introduction
============

Solis solar inverters are equipped with an RS485 interface, through which telemetry values can be read and also control 
commands can be sent. The manufacturer offers LAN and WLAN sticks in combination with a software solution to access the 
interface. Unfortunately, this is always coupled with a connection to the manufacturer's cloud and integration into a 
home automation system is only possible in a detoured manner.
This software acts as a bridge between the RS485 interface and a MQTT broker to allow easy integration into a 
home automation (with special support for Home Assistant), and furthermore without cloud constraints.


Hardware
========

* The inverter uses a proprietary(?) RS485 plug, with the following pin-out:
```
  /-----\
  | 2 3 |
  | 1 4 |
  \--^--/
```
  
1. +5V
2. GND
3. DATA+
4. DATA-

* Any RS485 adapter should do. I use one of [these](https://www.amazon.com/DSD-TECH-SH-U14-Built-Terminal/dp/B083169369)
(with FTDI chip), but have also tested [this](https://www.amazon.com/-/en/dp/B07TB5WVF4) simple (and cheaper) one.
* I highly recommend using a proper connector, which can be found on 
[ebay](https://www.ebay.com/itm/234026066127?hash=item367d0a60cf:g:6uYAAOSwFKVgrqlf) (search for "RS485 Solis" or 
"Exceedconn EC04681-2014-BF") and solder the wires to it.
* I run the software on a RaspberryPi Zero W, but any Linux box should do.

Installation
============

TODO

Basic Configuration
===================

Configuration is read from `config.yaml`, that has to contain at least these entries:

```yaml
device: /dev/ttyUSB0
mqtt:
  url: hassio.local
  user: whoami
  passwd: secret
```

This is a complete config example:

```yaml
device: /dev/ttyUSB0
slave_address: 1
poll_interval: 60
poll_interval_if_off: 600
inverter:
    name: solis2mqtt
    manufacturer: Ginlong Technologies
    model: solis2mqtt
mqtt:
    url: hassio.local
    port: 8883
    use_ssl: true
    validate_cert: true
    user: whoami
    passwd: secret
```

* `device`: [Required] The path to your RS485 adapter
* `slave_address`: [Optional] The modbus slave address, default is _1_
* `poll_interval`: [Optional] Inverter poll interval in seconds, default is _60_
* `poll_interval_if_off`: [Optional] Poll interval during night in seconds, default is _600_
* `interter`:
  * `name`: [Optional] Used as a base path in MQTT, default is _solis2mqtt_
  * `manufaturer`: [Optional] Used for device info in Home Assistant, default is _incub_
  * `model`: [Optional] Used for device info in Home Assistant, default is _solis2mqtt_
* `mqtt`:
  * `url`: [Required] URL to your MQTT broker
  * `port`: [Optional] Port of your MQTT broker, default is _8883_
  * `use_ssl`: [Optional] Use SSL for MQTT traffic encryption, default is _true_
  * `validate_cert` [Optional] Validate certificate for SSL encryption, default is _true_
  * `user`: [Required] User for MQTT broker login
  * `passwd`: [Required] Password for MQTT broker login

Inverter configuration
======================

The file `solis_modbus.yaml` contains a list of entries, that describe the values to read from 
(and write to) the inverter.\
You can add your own entries if you want to read other metrics from the inverter. 
Especially if it comes to writing to the inverter - use at your own risk :-)\
Each entry can be configured with the following options:
```yaml
- name: inverter_temp
  description: Inverter temperature
  unit: "°C"
  active: true
  modbus:
    register: 3041
    read_type: register
    function_code: 4
    number_of_decimals: 1
    signed: false
  homeassistant:
    device: sensor
    state_class: measurement
    device_class: temperature
```

* `name`: [Required] Has to be unique. Used in MQTT path and together inverter name (from config.yaml) as part of 
Home Assistant unique_id
* `description`: [Required] Used for generating log messages and as name in Home Assistant
* `unit`: [Optional] Added to log messages and used for Home Assistant
* `active` [Required] Set to `false` if the entry should be ignored
* `modbus`: [Required]
  * `register`: [Required] The modbus register address to read/write
  * `read_type`: [Required] The [modbus data type](https://minimalmodbus.readthedocs.io/en/stable/modbusdetails.html). 
Currently `register` and `long` are supported. Additionally `composed_datetime` can also be used here (see TODO)
  * `function_code`: [Required] The 
[modbus function code](https://minimalmodbus.readthedocs.io/en/stable/modbusdetails.html#implemented-functions) to use
  * `number_of_decimals`: [Optional] Can only be used in combination with `ready_type: register`. Used for automatic 
content conversion, e.g. 101 with `number_of_decimals: 1` is read as 10.1
  * `signed`: [Required] Whether the data should be interpreted as signed or unsigned
* `homeassistant`: [Optional]
  * `device`: [Required] Used for [Home Assistant MQTT discovery](https://www.home-assistant.io/docs/mqtt/discovery/). 
Can either be `sensor`, `number` or `switch`
  * `state_class`: [Optional] 
[State class](https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes) for Home Assistant 
sensors 
  * `device_class`: [Optional] [Device class](https://www.home-assistant.io/integrations/sensor/#device-class) for 
Home Assistant sensors






