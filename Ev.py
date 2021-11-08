import time

from scapy.automaton import Message
from Whitebeet import *
from Battery import *

class Evse():

    def __init__(self, iface, mac):
        self.whitebeet = Whitebeet(iface, mac)
        self.battery = Battery()
        self.schedule = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if hasattr(self, "whitebeet"):
            del self.whitebeet

    def __del__(self):
        if hasattr(self, "whitebeet"):
            del self.whitebeet

    def _initialize(self):
        """
        Initializes the whitebeet by setting the control pilot mode and setting the duty cycle
        to 100%. The SLAC module is also started. This one needs ~1s to 2s to be ready.
        Therefore we delay the initialization by 2s.
        """
        print("Set the CP mode to EV")
        self.whitebeet.controlPilotSetMode(0)
        print("Start the CP service")
        self.whitebeet.controlPilotStart()
        print("Start SLAC in EV mode")
        self.whitebeet.slacStart(0)
        time.sleep(2)

    def _waitEvseConnected(self, timeout):
        """
        We check for the state on the CP. When there is no EVSE connected we have state A on CP.
        When an EVSE connects the state changes to state B and we can continue with further steps.
        """
        timestamp_start = time.time()
        cp_state = self.whitebeet.controlPilotGetState()
        if cp_state == 1:
            print("EVSE already connected")
            return True
        elif cp_state > 1:
            print("CP in wrong state: {}".format(cp_state))
            return False
        else:
            print("Wait until an EVSE connects")
            while True:
                cp_state = self.whitebeet.controlPilotGetState()
                if timeout != None and timestamp_start + timeout > time.time():
                    return False
                if cp_state == 0:
                    time.sleep(0.1)
                elif cp_state == 1:
                    print("EVSE connected")
                    return True
                else:
                    print("CP in wrong state: {}".format(cp_state))
                    return False

    def _handleEvseConnected(self):
        """
        When an EVSE connected we start our start matching process of the SLAC which will be ready
        to answer SLAC request for the next 50s. After that we set the duty cycle on the CP to 5%
        which indicates that the EVSE can start with sending SLAC requests.
        """
        print("Start SLAC matching")
        self.whitebeet.slacStartMatching()
        try:
            if self.whitebeet.slacMatched() == True:
                print("SLAC matching successful")
                self._handleNetworkEstablished()
                return True
            else:
                print("SLAC matching failed")
                return False
        except TimeoutError as e:
            print(e)
            return False

    def _handleNetworkEstablished(self):
        """
        When SLAC was successful we can start the V2G module. Set our supported protocols,
        available payment options and energy transfer modes. Then we start waiting for
        notifications for requested parameters.
        """
        print("Set V2G mode to EV")
        self.whitebeet.v2gSetMode(0)
        self.whitebeet.v2gSetConfigruation()
        time.sleep(0.1)
        print("Start V2G")
        self.whitebeet.v2gStart()
        while True:
            id, data = self.whitebeet.v2gReceiveRequest()
            if id == 0xC0:
                self._handleSessionStarted(data)
            elif id == 0xC1:
                self._handleDCChargeParametersChanged(data)
                break
            elif id == 0xC2:
                self._handleACChargeParametersChanged(data)
            elif id == 0xC3:
                self._handleScheduleReceived(data)
            elif id == 0xC4:
                self._handleCableCheckReady(data)
            elif id == 0xC5:
                self._handleCableCheckFinished(data)
            elif id == 0xC6:
                self._handlePreChargingReady(data)
            elif id == 0xC7:
                self._handleChargingReady(data)
            elif id == 0xC8:
                self._handleChargingStarted(data)
            elif id == 0xC9:
                self._handleChargingStopped(data)
            elif id == 0xCA:
                self._handlePostChargingReady(data)
            elif id == 0xCB:
                self._handleSessionStopped(data)
            elif id == 0xCC:
                self._handleNotificationReceived(data)
            elif id == 0xCD:
                self._handleSessionError(data)
            else:
                print("Message ID not supported: {:02x}".format(id))
                break
        self.whitebeet.v2gStop()

    def _handleSessionStarted(self, data):
        """
        Handle the SessionStarted notification
        """
        print("\"Session started\" received")
        message = self.whitebeet.v2gEvParseSessionStarted(data)
        print("Protocol: {}".format(message['protocol']))
        print("Session ID: {}".format(message['session_id'].hex()))
        print("EVSE ID: {}".format(message['evse_id'].hex()))
        print("Payment method: {}".format(message['payment_method'].hex()))
        print("Energy transfer mode: {}".format(message['energy_transfer_method'].hex()))

    def _handleDCChargeParametersChanged(self, data):
        """
        Handle the SessionStopped notification
        """
        print("\"Session stopped\" received")
        message = self.whitebeet.v2gEvParseDCChargeParametersChanged(data)
        print("EVSE min voltage: {}".format(message['evse_min_voltage']))
        print("EVSE min current: {}".format(message['evse_min_current']))
        print("EVSE min power: {}".format(message['evse_min_power']))
        print("EVSE max voltage: {}".format(message['evse_max_voltage']))
        print("EVSE max current: {}".format(message['evse_max_current']))
        print("EVSE max power: {}".format(message['evse_max_power']))
        print("EVSE present voltage: {}".format(message['evse_present_voltage']))
        print("EVSE present current: {}".format(message['evse_present_current']))
        print("EVSE status: {}".format(message['evse_status'].hex()))

    def _handleACChargeParametersChanged(self, data):
        """
        Handle the ACChargeParameterChanged notification
        """
        print("\"AC Charge Parameter changed\" received")
        message = self.whitebeet.v2gEvParseACChargeParametersChanged(data)
        print("Nominal voltage: {}".format(message['nominal_voltage']))
        print("Maximal current: {}".format(message['max_current']))
        print("RCD: {}".format(message['rcd']))

    def _handleScheduleReceived(self, data):
        """
        Handle the ScheduleReceived notification.
        """
        print("\"Schedule Received\" received")
        message = self.whitebeet.v2gEvParseScheduleReceived(data)
        print("Tuple count: {}".format(message['tuple_count']))
        print("Tuple id: {}".format(message['tuple_id']))
        print("Entries count: {}".format(message['entries_count']))
        start = []
        interval = []
        power = []
        i = 0
        for entry in message['entries']:
            start.append(entry['start'])
            interval.append(entry['interval'])
            power.append(entry['power'])
            
            print("Entry " + i + ":")
            print("\tStart: {}".format(entry['start']))
            print("\tInterval: {}".format(entry['interval']))
            print("\tPower: {}".format(entry['power']))
            i += 1
        try:
            self.whitebeet.v2gSetChargingProfile(message['tuple_count'], message['entries_count'], start, interval, power)
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleCableCheckReady(self, data):
        """
        Handle the CableCheckReady notification
        """
        print("\"Cable Check Ready\" received")
        self.whitebeet.v2gEvParseCableCheckReady(data)
        try:
            self.whitebeet.v2gStartCableCheck()
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleCableCheckFinished(self, data):
        """
        Handle the CableCheckFinished notification
        """
        print("\"Cable Check Finished\" received")
        self.whitebeet.v2gEvParseCableCheckFinished(data)

    def _handlePreChargingReady(self, data):
        """
        Handle the PreChargingReady notification
        """
        print("\"Pre Charging Ready\" received")
        self.whitebeet.v2gEvParsePreChargingReady(data)
        try:
            self.whitebeet.v2gStartPreCharging()
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleChargingReady(self, data):
        """
        Handle the ChargingReady notification
        """
        print("\"Charging Ready\" received")
        self.whitebeet.v2gEvParseChargingReady(data)
        try:
            self.whitebeet.v2gStartCharging()
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleChargingStarted(self, data):
        """
        Handle the ChargingStarted notification
        """
        print("\"Charging Started\" received")
        self.whitebeet.v2gEvParseChargingStarted(data)

    def _handleChargingStopped(self, data):
        """
        Handle the ChargingStopped notification
        """
        print("\"Charging Stopped\" received")
        self.whitebeet.v2gEvParseChargingStopped(data)
        try:
            self.whitebeet.v2gStopCharging() #TODO: stimmt das so?
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handlePostChargingReady(self, data):
        """
        Handle the PostChargingReady notification
        """
        print("\"Post Charging Ready\" received")
        self.whitebeet.v2gEvParsePostChargingReady(data)
        
    def _handleNotificationReceived(self, data):
        """
        Handle the NotificationReceived notification
        """
        print("\"Notification Received\" received")
        message = self.whitebeet.v2gEvParseNotificationReceived(data)
        print("Type : {}".format(message['type'].hex()))
        print("Maximum delay : {}".format(message['max_delay']))

    def _handleSessionStopped(self, data):
        """
        Handle the SessionStopped notification
        """
        print("\"Session Stopped\" received")
        self.whitebeet.v2gEvParseSessionStopped(data)
    
    def _handleSessionError(self, data):
        """
        Handle the SessionError notification
        """
        print("\"Session Error\" received")
        message = self.whitebeet.v2gEvParseSessionError(data)
        print("Error code: {}".format(message['error'].hex()))

    def getBattery(self):
        """
        Returns the battery object
        """
        if hasattr(self, "battery"):
            return self.battery
        else:
            return None

    def getWhitebeet(self):
        """
        Returns the whitebeet object
        """
        if hasattr(self, "whitebeet"):
            return self.whitebeet
        else:
            return None

    def setSchedule(self, schedule):
        """
        Sets the schedule. This schedule will be used when the whitebeet requests this data
        """
        if isinstance(schedule, list) == False:
            print("Schedule needs to be of type list")
            return False
        elif len(schedule) != 0 and any(isinstance(entry, dict) == False for entry in schedule):
            print("Entries in schedule need to be of type dict")
            return False
        else:
            self.schedule = schedule
            return True

    def loop(self):
        """
        This will handle a complete charging session of the EV.
        """
        self._initialize()
        if self._waitEvseConnected(None):
            return self._handleEvseConnected()
        else:
            return False
