#!/usr/bin/python3

import minimalmodbus
import yaml
import daemon
import logging
import time
import math
import signal
from logging.handlers import RotatingFileHandler
import argparse
from time import sleep
from datetime import datetime
from mqtt_discovery import DiscoverMsgSensor, DiscoverMsgNumber, DiscoverMsgSwitch
from inverter import Inverter
from mqtt import Mqtt
from influx import Influx
from config import Config


VERSION = "0.9"

class Solis2Mqtt:
    def __init__(self, logging, args):
        self.cfg = Config('config.yaml')
        self.register_cfg = ...
        self.load_register_cfg(args.modbus)
        self.inverters = None ;
        self.topicPath = self.cfg['mqtt']['topic']
        self.mqtt = Mqtt(self.topicPath, self.cfg['mqtt'],logging)

    def load_register_cfg(self, register_data_file):
        logging.info(f"Loading {args.modbus}")
        with open(args.modbus) as smfile:
            self.register_cfg = yaml.load(smfile, yaml.Loader)

    def generate_ha_discovery_topics(self, retain=False):
        for entry in self.register_cfg:
            if entry['active'] and 'homeassistant' in entry:
                discoveryTopic = f"homeassistant/{entry['homeassistant']['device']}/{self.topicPath}/{entry['name']}/config";
                logging.debug("Generating discovery topic for " + discoveryTopic)
                if entry['homeassistant']['device'] == 'sensor':
                    self.mqtt.publish(discoveryTopic,
                                      str(DiscoverMsgSensor(entry['description'],
                                                            entry['name'],
                                                            entry['unit'],
                                                            entry['homeassistant']['device_class'],
                                                            entry['homeassistant']['state_class'],
                                                            self.cfg['inverter']['name'],
                                                            self.cfg['inverter']['model'],
                                                            self.cfg['inverter']['manufacturer'],
                                                            VERSION)),
                                      retain=retain)
                elif entry['homeassistant']['device'] == 'number':
                    self.mqtt.publish(discoveryTopic,
                                      str(DiscoverMsgNumber(entry['description'],
                                                            entry['name'],
                                                            entry['homeassistant']['min'],
                                                            entry['homeassistant']['max'],
                                                            entry['homeassistant']['step'],
                                                            self.cfg['inverter']['name'],
                                                            self.cfg['inverter']['model'],
                                                            self.cfg['inverter']['manufacturer'],
                                                            VERSION)),
                                      retain=retain)
                elif entry['homeassistant']['device'] == "switch":
                    self.mqtt.publish(discoveryTopic,
                                      str(DiscoverMsgSwitch(entry['description'],
                                                            entry['name'],
                                                            entry['homeassistant']['payload_on'],
                                                            entry['homeassistant']['payload_off'],
                                                            self.cfg['inverter']['name'],
                                                            self.cfg['inverter']['model'],
                                                            self.cfg['inverter']['manufacturer'],
                                                            VERSION)),
                                      retain=retain)
                else:
                    logging.error("Unknown homeassistant device type: "+entry['homeassistant']['device'])

    def subscribe(self):
        for entry in self.register_cfg:
            if 'write_function_code' in entry['modbus']:
                if not self.mqtt.on_message:
                    self.mqtt.on_message = self.on_mqtt_message
                    subscription = "{}/{}/set".format(self.cfg['mqtt']['topic'], entry['name']);
                    logging.info("Subscribing to: " + subscription)
                self.mqtt.persistent_subscribe(subscription)

    def on_mqtt_message(self, client, userdata, msg):
        for el in self.register_cfg:
            if el['name'] == msg.topic.split('/')[-2]:
                register_cfg = el['modbus']
                break

        str_value = msg.payload.decode('utf-8')
        if 'number_of_decimals' in register_cfg and register_cfg['number_of_decimals'] > 0:
            value = float(str_value)
        else:
            try :
                value = int(str_value);
            except ValueError as ve:
                logging.info("{} Expected {} digits but have {} :{}".format(el['name'],str_value, register_cfg['number_of_decimals'], ve));
                value = 0 ;

        with self.inverter_lock:
            try:
                self.inverter.write_register(register_cfg['register'],
                                             value,
                                             register_cfg['number_of_decimals'],
                                             register_cfg['write_function_code'],
                                             register_cfg['signed'])
                logging.debug(f"Inverter write register: reg {register_cfg['register']} dec:{register_cfg['number_of_decimals']} fc:{register_cfg['write_function_code']} signed:{register_cfg['signed']}")
            except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError):
                if not self.inverter_offline:
                    logging.exception(f"Error while writing message to inverter. Topic: '{msg.topic}, "
                                      f"Value: '{str_value}', Register: '{register_cfg['register']}'.")

    def scanRegister(self, entry, inverter):
        success = False
        value = None
        try:
            if entry['modbus']['read_type'] == "register":
                with inverter.lock:
                    value = inverter.read_register(entry['modbus']['register'],
                                                        number_of_decimals=entry['modbus']['number_of_decimals'],
                                                        functioncode=entry['modbus']['function_code'],
                                                        signed=entry['modbus']['signed'])

            elif entry['modbus']['read_type'] == "long":
                with inverter.lock:
                    value = inverter.read_long(entry['modbus']['register'],
                                                    functioncode=entry['modbus']['function_code'],
                                                    signed=entry['modbus']['signed'])
            elif entry['modbus']['read_type'] == "composed_datetime":
                with inverter.lock:
                    value = inverter.read_composed_date(entry['modbus']['register'],
                                                    functioncode=entry['modbus']['function_code'])
            success = True
        # NoResponseError occurs if inverter is off,
        # InvalidResponseError might happen when inverter is starting up or shutting down during a request
        except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError):
            # in case we didn't have a exception before
            if not inverter.offline:
                logging.info(f"{inverter.name} not reachable, going offline")
                inverter_offline = True

            if 'homeassistant' in entry and entry['homeassistant']['state_class'] == "measurement":
                value = 0

        return success,value



    def main(self, influx):

        self.inverters = [ Inverter('InverterA', 1, self.cfg['device']),
                           Inverter('InverterB', 2, self.cfg['device']) ]

        self.generate_ha_discovery_topics()
        self.subscribe()

        while True:
            timestamp = (math.floor(time.time()/60)) * 60 ; # round up to 1 minute
#23456789010
            for inverter in self.inverters :
                fieldSet = {}
                logging.debug(f"{inverter.name} scan start. Number of points written {influx.numPoints}")
                for entry in self.register_cfg:

                    # print('register', entry['modbus']['register'], entry['name']);
                    if not entry['active'] or 'function_code' not in entry['modbus'] :
                        continue

                    isStatistic = 'measurement' in entry and entry['measurement'] == 'statistic'

                    topicShortName = entry['name']
                    topicQualified = f"{self.cfg['mqtt']['topic']}/{entry['name']}"
                    mqttTopicQualified = f"{self.cfg['mqtt']['topic']}/{inverter.name}/{entry['name']}"

                    success,value = self.scanRegister(entry, inverter)

                    if not success:

                        logging.debug(f"Read {inverter.name}:{entry['name']}\{entry['description']} - {value}")
                        break ;

                    if value or inverter.loopCount == 0 :  # skip zero values
                        ha = entry['homeassistant']
                        useFloat = ('number of decimals' in entry["modbus"] and entry["modbus"]['number_of_decimals']) or ha["device_class"] in ['energy','voltage','current','temperature','frequency']

                        value = float(value) if useFloat else value

                        if not isStatistic:
                            fieldSet[topicShortName] = value ;

                        self.mqtt.publish(f"{mqttTopicQualified}", value, retain=False)

                if influx and fieldSet :
                    influx.writeFieldSet(inverter.name, timestamp, fieldSet);

                logging.info(f"{inverter.name} scan ended. Number of points written {influx.numPoints}")
                self.mqtt.publish(f"sys/influx/num_points_written", influx.numPoints, retain=False)
                inverter.loopCount = inverter.loopCount + 1

            #end for inverters
#23456789010
            # wait with next poll configured interval, or if inverters are not responding longer

            sleep_duration = self.cfg['poll_interval'] if True else self.cfg['poll_interval_if_off']
            logging.debug(f"Inverter scanning paused for {sleep_duration} seconds")
            sleep(sleep_duration)



def poll(is_daemon, args):
    log_level = logging.DEBUG if args.verbose else logging.INFO
    handler = RotatingFileHandler("solis.log", maxBytes=1024 * 1024 * 10,
                                  backupCount=1) if is_daemon else logging.StreamHandler()
    logging.basicConfig(level=log_level, format="%(asctime)s %(message)s", handlers=[handler])
    logging.info("Starting up...")
    with Influx(logging) as influx :   # instantiating logger
        sol = Solis2Mqtt(logging, args)
        sol.main(influx)
        del sol


def signal_term_handler(sigNum, frame):
    # on receiving a signal initiate a normal exit
    logging.info(f"Got signal {sigNum} to shut down")
    exit(0);


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Solis inverter to mqtt/influx bridge.')
    parser.add_argument('-d', '--daemon', action='store_true', help='start as daemon')
    parser.add_argument('-v', '--verbose', action='store_true', help="verbose logging")
    parser.add_argument('-r', '--modbus', default='solis_modbus.yaml', help="modbus reguister mappings")
    args = parser.parse_args()

    # register the signal handler
    signal.signal(signal.SIGTERM, signal_term_handler)
    signal.signal(signal.SIGHUP, signal_term_handler)

    if args.daemon:
        try:
            poll(args.daemon, args)
        except Exception as ex:
            logging.exception(ex)   # direct exception log to file?
    else:
        poll(args.daemon, args)
    exit(0);
