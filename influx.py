import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, WriteOptions
from influxdb_client.client.write_api import ASYNCHRONOUS
import yaml
import re
import time
import math
from os import wait


def load_config(fileName):
    with open(fileName, "r") as yaml_file:
        config = yaml.safe_load(yaml_file)
    return config

class Influx :

    def __init__(self, logger, batch_size=1000, flush_interval=30000):
        self.clientInflux = None
        self.config = None
        self.mapper = None
        self.logger = logger
        self.numPoints = 0
        self.config = config = load_config("config.yaml");
        self.mapper = mapper = load_config("solis_modbus.yaml");
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self.clientInflux = InfluxDBClient(url=config['influx']['url'], token=config['influx']['token'], org=config['influx']['org'])

        self.blackList = ['solar/system_datetime']

    def __enter__(self):
        self.clientInfluxWrite = self.clientInflux.write_api( write_options=WriteOptions(batch_size=self.batch_size, flush_interval=self.flush_interval))
        self.logger.debug("influxDB instantiated");
        return self


    def writeFieldSet(self, inverterName, timestamp, fieldSet):

        self.logger.debug(f"Influx write fieldset");
        tags = {}
        tags['inverter'] = inverterName

        point = {   'measurement' : 'sensor',
                    'fields' :      fieldSet,
                    'tags'   :      tags,
                    'timestamp' :   timestamp
        };
        try:
            #self.logger.info(f"Trying write :{topic}, value:{value}, point:{str(point)}");
            self.clientInfluxWrite.write(self.config['influx']['bucket'], record=point)
            self.logger.debug(f"looks OK {str(point)}");
            self.numPoints = self.numPoints + 1
            pointLogged = True
        except ValueError as er:
            #self.logger.warning(er);
            self.logger.info(f"{str(er)} write failed. Point:{str(point)}");



    def write(self,topic,value,timestamp,inverterName):

        # lose the leading topic name
        topicID = re.search(r'\/(.+)', topic).group(1);

        if topicID in self.blackList :
            self.logger.info(f"Blacklisted:{topic}, value:{value}, point:{str(point)}");
            return ;

        self.logger.debug(f"influx write {topicID} : {value}");

        measurement = None ;
        fields = {} ;
        tags = {} ;
        point = None

        # find matching field
        # could really search for param or get passed it.
        # would be nice to group all measurements in a block before writing

        for param in self.mapper:

            pointLogged = False
            if param['name'].lower() == topicID.lower():
                point = None
                ha = param['homeassistant']
                if ha["device_class"] == 'string' : # need to re check
                    break ;    #  breaks influx

                measurement = ha['device'] ;  # e.g. sensor | number

                useFloat = ('number of decimals' in param["modbus"] and param["modbus"]['number_of_decimals']) or ha["device_class"] in ['energy','voltage','current','temperature','frequency']

                value = float(value) if useFloat else value

                fields[topicID] = value ;
                fields["register"] = param['modbus']['register'];

                tags['inverter'] = inverterName

                point = {   'measurement' : measurement,
                            'fields' : fields,
                            'tags'   : tags,
                            'timestamp' : timestamp
                    };
                break;

        # we've got a measurement, save save it
        if measurement :
            try:
                #self.logger.info(f"Trying write :{topic}, value:{value}, point:{str(point)}");
                self.clientInfluxWrite.write(self.config['influx']['bucket'], record=point)
                self.logger.debug(f"looks OK {str(point)}");
                self.numPoints = self.numPoints + 1
                pointLogged = True
            except ValueError as er:
                #self.logger.warning(er);
                self.logger.info(f"{str(er)} write failed :{topic}, value:{value}, point:{str(point)}");

        if not pointLogged :
            self.logger.info(f"Not logging this topic:{topic}, value:{value}");

    def __exit__(self, *args):
        self.logger.info(f"Closing influx");
        self.clientInfluxWrite.close()



    def writeOld(self,topic,value):

        # lose the leading topic name
        topicID = re.search(r'\/(.+)', topic).group(1);
#       val = msg.payload.decode("utf-8")
#       print(topicID + " " + str(msg.qos) + " " + str(val))
        if topicID in self.blackList :
            self.logger.info(f"Blacklisted:{topic}, value:{value}, point:{str(point)}");
            return ;

        self.logger.debug(f"influx write {topicID} : {value}");

        measurement = None ;
        fields = {} ;
        tags = {} ;
        timestamp = (math.floor(time.time()/60)) * 60 ; # round up to 1 minute
        point = None
        # find matching fields
        for param in self.mapper:
            pointLogged = False
            if param['name'].lower() == topicID.lower():
                point = None
                ha = param['homeassistant']
                if ha["device_class"] == 'string' : # need an re check
                    break ;    #  breaks influx
                measurement = ha['device'] ;  # sensor | number

                useFloat = ('number of decimals' in param["modbus"] and param["modbus"]['number_of_decimals']) or ha["device_class"] in ['energy','voltage','current','temperature','frequency']

                value = float(value) if useFloat else value

                fields[ha["device_class"]] =  value ;
                fields["topic"] = topicID ;
                #if param['modbus']['register'].isnumeric() :
                fields["register"] = param['modbus']['register'];

                tags['inverter'] = 0 ;
                if 'location' in self.config['inverter']:
                    tags['location'] = self.config['inverter']['location']

                if 'group' in ha :
                    tags['group'] = ha['group'] ;

                if 'index' in ha :
                    tags['index'] = ha['index'] ;

                point = {   'measurement' : measurement,
                            'fields' : fields,
                            'tags'   : tags,
                            'timestamp' : timestamp
                    };
                break;

        # we've got a measurement, save save it

        if measurement :
            try:
                #self.logger.info(f"Trying write :{topic}, value:{value}, point:{str(point)}");
                self.clientInfluxWrite.write(self.config['influx']['bucket'], record=point)
                self.logger.debug(f"looks OK {str(point)}");
                self.numPoints = self.numPoints + 1
                pointLogged = True
            except ValueError as er:
                #self.logger.warning(er);
                self.logger.info(f"{str(er)} write failed :{topic}, value:{value}, point:{str(point)}");


        if not pointLogged :
            self.logger.info(f"Not logging this topic:{topic}, value:{value}");

    def __exit__(self, *args):
        self.logger.info(f"closing influx");
        self.clientInfluxWrite.close()
