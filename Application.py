import time
import argparse
from Evse import *
from Ev import *

if __name__ == "__main__":
    WHITEBBET_DEFAULT_MAC = "00:01:01:63:77:33"
    parser = argparse.ArgumentParser(description='Codico Whitebeet EVSE reference implementation.')
    parser.add_argument('interface', type=str, help='This is the name of the interface where the Whitebeet is connected to (i.e. "eth0").')
    parser.add_argument('-m', '--mac', type=str, help='This is the MAC address of the ethernet interface of the Whitebeet (i.e. "{}").'.format(WHITEBBET_DEFAULT_MAC))
    parser.add_argument('-r', '--role', type=str, help='This is the role of the Whitebeet. "EV" for EV mode and "EVSE" for EVSE mode')
    args = parser.parse_args()

    print("Welcome to Codico Whitebeet EVSE reference implementation")
    
    # If no MAC address was given set it to the default MAC address of the Whitebeet
    if args.mac == None:
        args.mac = WHITEBBET_DEFAULT_MAC

    # If no role was given set it to EVSE mode
    if args.role == None:
        args.role = "EVSE"

    if(args.role == "EV"):
        with Ev(args.interface, args.mac) as ev:

            # Start the EVSE loop
            #ev.whitebeet.networkConfigSetPortMirrorState(1)
            #ev.whitebeet.v2gSetConfiguration(ev.evid, ev.protocol_count, ev.protocols, ev.payment_method_count, ev.payment_method, ev.energy_transfer_mode_count, ev.energy_transfer_mode, ev.battery_capacity)
            ev.loop()
            print("EV loop finished")
    else:
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
