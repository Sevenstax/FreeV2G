import time

from scapy.automaton import Message
from Whitebeet import *
from Battery import *

class Ev():

    def __init__(self, iface, mac):
        self.whitebeet = Whitebeet(iface, mac)
        self.battery = Battery()

        self.evid = list(bytes.fromhex(mac.replace(":","")))
        self.protocol_count = 2
        self.protocols = [0, 1]
        self.payment_method_count = 1
        self.payment_method = [0]
        self.energy_transfer_mode_count = 1
        self.energy_transfer_mode = [1]
        self.battery_capacity = list(int(50000).to_bytes(2, "big"))
        self.battery_capacity.append(0)

        self.min_voltage = 50
        self.min_current = 1
        self.min_power = self.min_voltage * self.min_current
        self.max_voltage = 70
        self.max_current = 100
        self.max_power = self.max_voltage * self.max_current
        self.soc = self.battery.getBatteryLevel()
        self.status = 0
        self.target_voltage = 60
        self.target_current = 80
        self.full_soc = 100
        self.bulk_soc = 80
        self.energy_request = self.battery.getCapacity() * (100 - self.soc)
        self.departure_time = 1000000


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
        print("Set SLAC to EV mode")
        self.whitebeet.slacSetValidationConfiguration(0)
        print("Start SLAC")
        self.whitebeet.slacStart(0)
        time.sleep(2)
    
    def _int2exp(self, value):
        ret = list(int(value).to_bytes(2, "big"))
        ret.append(0)
        return ret

    def _waitEvseConnected(self, timeout):
        """
        We check for the state on the CP. When there is no EVSE connected we have state A on CP.
        When an EVSE connects the state changes to state B and we can continue with further steps.
        """
        timestamp_start = time.time()
        cp_dc = self.whitebeet.controlPilotGetDutyCycle()
        if cp_dc < 10.0 and cp_dc > 0.1:
            print("EVSE connected")
            return True
        else:
            print("Wait until an EVSE connects")
            while True:
                cp_dc = self.whitebeet.controlPilotGetDutyCycle()
                if timeout != None and timestamp_start + timeout > time.time():
                    return False
                if cp_dc < 10.0 and cp_dc > 0.1:
                    print("EVSE connected")
                    return True
                else:
                    time.sleep(0.1)

    def _handleEvseConnected(self):
        """
        When an EVSE connected we start our start matching process of the SLAC which will be ready
        to answer SLAC request for the next 50s. After that we set the duty cycle on the CP to 5%
        which indicates that the EVSE can start with sending SLAC requests.
        """

        print("Start SLAC matching")
        time.sleep(5.0)
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
        print("Set V2G configuration")
        self.whitebeet.v2gSetConfiguration(self.evid, self.protocol_count, self.protocols, self.payment_method_count, self.payment_method, self.energy_transfer_mode_count, self.energy_transfer_mode, self.battery_capacity)
        print("Set DC charging parameters")
        self.whitebeet.v2SetDCChargingParameters(self.min_voltage, self.min_current, self.min_power, self.max_voltage, self.max_current, self.max_power, self.soc, self.status, self.target_voltage, self.target_current, self.full_soc, self.bulk_soc, self.energy_request, self.departure_time)
        print("Start V2G")
        self.whitebeet.v2gStart()
        print("Change State to State C")
        self.whitebeet.controlPilotSetResistorValue(1)
        print("Create new charging session")
        self.whitebeet.v2gStartSession()

        oldVal = self.whitebeet.controlPilotGetDutyCycle()
        print("controlpilot dutycycle: " + str(oldVal))
        while True:
            newVal = self.whitebeet.controlPilotGetDutyCycle()
            if newVal != oldVal:
                oldVal = newVal
                print("controlpilot dutycycle: " + str(oldVal))
            id, data = self.whitebeet.v2gEvReceiveRequest()
            if id == 0xC0:
                self._handleSessionStarted(data)
            elif id == 0xC1:
                self._handleDCChargeParametersChanged(data)
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
        self.whitebeet.controlPilotSetResistorValue(1)
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
        print("Payment method: {}".format(message['payment_method']))
        print("Energy transfer mode: {}".format(message['energy_transfer_method']))

    def _handleDCChargeParametersChanged(self, data):
        """
        Handle the DCChargeParametersChanged notification
        """
        print("\"DC Charge Parameters Changed\" received")
        message = self.whitebeet.v2gEvParseDCChargeParametersChanged(data)
        print("EVSE min voltage: {}".format(message['evse_min_voltage']))
        print("EVSE min current: {}".format(message['evse_min_current']))
        print("EVSE min power: {}".format(message['evse_min_power']))
        print("EVSE max voltage: {}".format(message['evse_max_voltage']))
        print("EVSE max current: {}".format(message['evse_max_current']))
        print("EVSE max power: {}".format(message['evse_max_power']))
        print("EVSE present voltage: {}".format(message['evse_present_voltage']))
        print("EVSE present current: {}".format(message['evse_present_current']))
        print("EVSE status: {}".format(message['evse_status']))

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
            
            print("Entry " + str(i) + ":")
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
        self.battery.setCharging(True)
        '''try:
            self.whitebeet.v2gStartCharging() #TODO: stimmt das so?
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))'''

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
