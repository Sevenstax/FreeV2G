import argparse
import json
from Evse import *
from Ev import *

if __name__ == "__main__":
    WHITEBBET_DEFAULT_MAC = "00:01:01:63:77:33"
    parser = argparse.ArgumentParser(description='Codico WHITE Beet reference implementation.')
    parser.add_argument('config', type=str, help='Path to configuration file. Defaults to ./config.json.', default="./config.json")
    args = parser.parse_args()

    # If no MAC address was given set it to the default MAC address of the WHITE Beet
    mac = WHITEBBET_DEFAULT_MAC
    interface = {"type": "eth", "name": "eth0"}
    portmirror = True
    role = "ev"

    # Load configuration from json
    if args.config is not None:
        try:
            with open(args.config, 'r') as configFile:
                config = json.load(configFile)

                # if a MAC adress is specified in the config file use this
                if 'mac' in config:
                    if isinstance(config['mac'], str):
                        mac = config['mac']
                    else:
                        raise ValueError("mac needs to be of type str")

                if 'interface' in config:
                    if isinstance(config['interface'], dict):
                        if 'type' in config['interface'] and 'name' in config['interface']:
                            if isinstance(interface['type'], str) and isinstance(interface['name'], str):
                                interface = config['interface']
                            else:
                                raise ValueError("interface['type'] and interface['name'] need to be of type dict")
                        else:
                            raise KeyError("Key \'type\' or \'name\' not found in config[\'interface\']")
                    else:
                        raise ValueError("interface needs to be of type dict")

                if 'portmirror' in config:
                    if isinstance(config['portmirror'], bool):
                        portmirror = config['portmirror']
                    else:
                        raise ValueError("portmirror needs to be of type bool")

                if 'ev' in config:
                    role = 'ev'
                elif 'evse' in config:
                    role = 'evse'
                else:
                    raise KeyError("Key \'ev\' or \'evse\' not found in config file")

        except FileNotFoundError as err:
            config = None
            print("Configuration file " + str(args.config) + " not found. Use default configuration.")
    else:
        config = None

    print('Welcome to Codico Whitebeet reference implementation')

    # role is EV
    if(role == "ev"):
        with Ev(interface['type'], interface['name'], mac) as ev:
            # apply config to ev
            if config is not None:
                print("EV configuration file: " + str(config))
                ev.load(config['ev'])

            # Start the EVSE loop
            ev.whitebeet.networkConfigSetPortMirrorState(portmirror)
            ev.loop()
            print("EV loop finished")

    elif(role == 'evse'):
        with Evse(interface['type'], interface['name'], mac) as evse:
            # apply config to evse
            if config is not None:
                evse.load(config['evse'])

            # Start the charger
            evse.getCharger().start()

            #set the Whitebeet time
            evse.setTime()

            cert_str = input("Inject x509 certificates to EVSE (y/N)?: ")
            if cert_str is not None and cert_str == "y":
                evse.injectCertificates()
            else:
                # Start the EVSE loop
                evse.whitebeet.networkConfigSetPortMirrorState(portmirror)
                evse.loop()
                print("EVSE loop finished")

    print("Goodbye!")
