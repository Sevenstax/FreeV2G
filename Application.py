import argparse
import json
from Evse import *
from Ev import *

if __name__ == "__main__":
    WHITEBBET_DEFAULT_MAC = "00:01:01:63:77:33"
    parser = argparse.ArgumentParser(description='Codico Whitebeet reference implementation.')
    parser.add_argument('interface_type', type=str, choices=('eth', 'spi'), help='Type of the interface through which the Whitebeet is connected. ("eth" or "spi").')
    parser.add_argument('-i', '--interface', type=str, required=True, help='This is the name of the interface where the Whitebeet is connected to (i.e. for eth "eth0" or spi "0").')
    parser.add_argument('-m', '--mac', type=str, help='This is the MAC address of the ethernet interface of the Whitebeet (i.e. "{}").'.format(WHITEBBET_DEFAULT_MAC))
    parser.add_argument('-r', '--role', type=str, help='This is the role of the Whitebeet. "EV" for EV mode and "EVSE" for EVSE mode')
    parser.add_argument('-c', '--config', type=str, help='Path to configuration file. Defaults to ./config.json.\nA MAC present in the config file will override a MAC provided with -m argument.', nargs='?', const="./config.json")
    args = parser.parse_args()

    # If no MAC address was given set it to the default MAC address of the Whitebeet
    if args.interface_type == "eth" and args.mac is None:
        args.mac = WHITEBBET_DEFAULT_MAC

    print('Welcome to Codico Whitebeet {} reference implementation'.format(args.role))

    mac = args.mac
    config = "./config.json"
    # Load configuration from json
    if args.config is not None:
        try:
            with open(args.config, 'r') as configFile:
                config = json.load(configFile)

                # if a MAC adress is specified in the config file use this
                if 'mac' in config:
                    mac = config['mac']

        except FileNotFoundError as err:
            print("Configuration file " + str(args.config) + " not found. Use default configuration.")


    # role is EV
    if(args.role == "EV"):  
        with Ev(args.interface_type, args.interface, args.mac) as ev:
            # apply config to ev
            if config is not None:
                print("EV configuration: " + str(config))
                ev.load(config)

            # Start the EVSE loop
            ev.whitebeet.networkConfigSetPortMirrorState(1)
            ev.loop()
            print("EV loop finished")

    elif(args.role == 'EVSE'):
        with Evse(args.interface_type, args.interface, args.mac) as evse:
            # apply config to evse
            if config is not None:
                evse.load(config)

            # Start the charger
            evse.getCharger().start()

            #set the Whitebeet time
            #evse.setTime()  

            cert_str = input("Inject x509 certificates to EVSE (y/N)?: ")
            if cert_str is not None and cert_str == "y":
                evse.injectCertificates()
            else:
                # Start the EVSE loop
                #evse.whitebeet.networkConfigSetPortMirrorState(1)
                evse.loop()
                print("EVSE loop finished")

    print("Goodbye!")
