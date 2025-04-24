import paho.mqtt.client as mqtt_client

class Mqtt(mqtt_client.Client):
    def __init__(self, client_id, cfg, logging):
        super().__init__(client_id=client_id, clean_session=True)
        self.subscriptions = []
        self.enable_logger()
        self.logging = logging
        self.username_pw_set(cfg['username'], cfg['password'])
        if cfg['use_ssl']:
            self.tls_set()
        if cfg['use_ssl'] and not cfg['validate_cert']:
            self.tls_insecure_set(True)
        self.on_publish = self._on_publish_callback
        self.logging.info(f"Connecting to MQTT...{cfg['host']}")
        self.connect(cfg['host'], cfg['port'])
        self.logging.info("Connected  to MQTT")
        if len(self.subscriptions):
            self.subscribe(self.subscriptions)

    def __del__(self):
        self.logging.info("Disconnecting from MQTT (if connected)...")
        self.disconnect()

    def _on_publish_callback(self,client, userdata, mid):
        #logging.debug("on_publish, mid {}".format(mid))
        pass

    def persistent_subscribe(self, topic):
        self.subscriptions.append((topic, 0))
        self.subscribe(topic)
