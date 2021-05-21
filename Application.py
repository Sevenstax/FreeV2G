import time
import argparse
from Evse import *

if __name__ == "__main__":
    WHITEBBET_DEFAULT_MAC = "00:01:01:63:77:33"
    parser = argparse.ArgumentParser(description='Codico Whitebeet EVSE reference implementation.')
    parser.add_argument('interface', type=str, help='This is the name of the interface where the Whitebeet is connected to (i.e. "eth0").')
    parser.add_argument('-m', '--mac', type=str, help='This is the MAC address of the ethernet interface of the Whitebeet (i.e. "{}").'.format(WHITEBBET_DEFAULT_MAC))
    args = parser.parse_args()

    print("Welcome to Codico Whitebeet EVSE reference implementation")
    
    # If no MAC address was given set it to the default MAC address of the Whitebeet
    if args.mac == None:
        args.mac = WHITEBBET_DEFAULT_MAC
    
    with Evse(args.interface, args.mac) as evse:
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
        schedule = [{
            "valid_until": time.time() + (48 * 60 * 60),
            "max_power": evse.getCharger().getEvseMaxPower()
        }]
        evse.setSchedule(schedule)

        # Start the EVSE loop
        evse.loop()
        print("EVSE loop finished")

    print("Goodbye!")
