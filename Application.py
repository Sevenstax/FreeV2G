from binascii import Error
import time
import argparse
import json
from Evse import *
from Ev import *

if __name__ == "__main__":
    WHITEBBET_DEFAULT_MAC = "00:01:01:63:77:33"
    parser = argparse.ArgumentParser(description='Codico Whitebeet reference implementation.')
    parser.add_argument('interface_type', type=str, help='Type of the interface through which the Whitebeet is connected. ("eth" or "spi").')
    parser.add_argument('-i', '--interface', type=str, required=True, help='This is the name of the interface where the Whitebeet is connected to (i.e. for eth "eth0" or spi "0").')
    parser.add_argument('-m', '--mac', type=str, help='This is the MAC address of the ethernet interface of the Whitebeet (i.e. "{}").'.format(WHITEBBET_DEFAULT_MAC))
    parser.add_argument('-r', '--role', type=str, help='This is the role of the Whitebeet. "EV" for EV mode and "EVSE" for EVSE mode')
    parser.add_argument('-c', '--config', type=str, help='Path to configuration file. Defaults to ./ev.json.\nA MAC present in the config file will override a MAC provided with -m argument.', nargs='?', const="./ev.json")
    args = parser.parse_args()

    if (args.interface_type != "spi") and (args.interface_type != "eth"):
        print("Error: Unsupported type of interface!")
    elif args.interface != None:
        # If no MAC address was given set it to the default MAC address of the Whitebeet
        if args.mac == None:
            args.mac = WHITEBBET_DEFAULT_MAC

    # If no role was given set it to EVSE mode
    if args.role not in ['EVSE', 'EV'] or args.role == None:
        print("Please specify the role EVSE or EV")
        exit(0)

    print('Welcome to Codico Whitebeet {} reference implementation'.format(args.role))

    # role is EV
    if(args.role == "EV"):
        mac = args.mac
        config = None
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
            # Set regulation parameters of the charger
            evse.getCharger().setEvseDeltaVoltage(0.5)
            evse.getCharger().setEvseDeltaCurrent(0.05)

            # Set limitations of the charger
            evse.getCharger().setEvseMaxVoltage(400)
            evse.getCharger().setEvseMaxCurrent(100)
            evse.getCharger().setEvseMaxPower(25000)

            # Start the charger
            evse.getCharger().start()

            # Set the schedule
            digest_value = range(31)
            signature_value = range(63)
            schedule = {
                "code": 0,
                "schedule_tuples": [{
                    'schedule_tuple_id': 1,
                    'schedules':[
                        {
                            "start": 0,
                            "interval": 1800,
                            "power": evse.getCharger().getEvseMaxPower()
                        },
                        {
                            "start": 1800,
                            "interval": 1800,
                            "power": int(evse.getCharger().getEvseMaxPower() * 0.75)
                        },
                        {
                            "start": 3600,
                            "interval": 82800,
                            "power": int(evse.getCharger().getEvseMaxPower() * 0.5)
                        }
                    ]
                }]
            }
            evse.setSchedule(schedule)

            # Start the EVSE loop
            evse.loop()
            print("EVSE loop finished")

    print("Goodbye!")
