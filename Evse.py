import time
from Whitebeet import *
from Charger import *

class Evse():

    def __init__(self, iface, mac):
        self.whitebeet = Whitebeet(iface, mac)
        self.charger = Charger()
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
        print("Set the CP mode to EVSE")
        self.whitebeet.controlPilotSetMode(1)
        print("Set the CP duty cycle to 100%")
        self.whitebeet.controlPilotSetDutyCycle(100)
        print("Start the CP service")
        self.whitebeet.controlPilotStart()
        print("Start SLAC in EVSE mode")
        self.whitebeet.slacStart(1)
        time.sleep(2)

    def _waitEvConnected(self, timeout):
        """
        We check for the state on the CP. When there is no EV connected we have state A on CP.
        When an EV connects the state changes to state B and we can continue with further steps.
        """
        timestamp_start = time.time()
        cp_state = self.whitebeet.controlPilotGetState()
        if cp_state == 1:
            print("EV already connected")
            return True
        elif cp_state > 1:
            print("CP in wrong state: {}".format(cp_state))
            return False
        else:
            print("Wait until an EV connects")
            while True:
                cp_state = self.whitebeet.controlPilotGetState()
                if timeout != None and timestamp_start + timeout > time.time():
                    return False
                if cp_state == 0:
                    time.sleep(0.1)
                elif cp_state == 1:
                    print("EV connected")
                    return True
                else:
                    print("CP in wrong state: {}".format(cp_state))
                    return False

    def _handleEvConnected(self):
        """
        When an EV connected we start our start matching process of the SLAC which will be ready
        to answer SLAC request for the next 50s. After that we set the duty cycle on the CP to 5%
        which indicates that the EV can start with sending SLAC requests.
        """
        print("Start SLAC matching")
        self.whitebeet.slacStartMatching()
        print("Set duty cycle to 5%")
        self.whitebeet.controlPilotSetDutyCycle(5)
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
        print("Set V2G mode to EVSE")
        self.whitebeet.v2gSetMode(1)
        self.whitebeet.v2gSetSupportedProtocols([0, 2])
        self.whitebeet.v2gSetPaymentOptions([0])
        self.whitebeet.v2gSetEnergyTransferModes([0, 1, 2, 3])
        time.sleep(0.1)
        print("Start V2G")
        self.whitebeet.v2gStart()
        while True:
            id, data = self.whitebeet.v2gEvseReceiveRequest()
            if id == 0x80:
                self._handleSessionStarted(data)
            elif id == 0x81:
                self._handleSessionStopped(data)
                break
            elif id == 0x82:
                self._handleRequestEvseId(data)
            elif id == 0x83:
                self._handleRequestAuthorization(data)
            elif id == 0x84:
                self._handleRequestDiscoveryChargeParameters(data)
            elif id == 0x85:
                self._handleRequestSchedules(data)
            elif id == 0x86:
                self._handleRequestCableCheckStatus(data)
            elif id == 0x87:
                self._handleRequestCableCheckParameters(data)
            elif id == 0x88:
                self._handleRequestPreChargeParameters(data)
            elif id == 0x89:
                self._handleRequestStartCharging(data)
            elif id == 0x8A:
                self._handleRequestChargeLoopParameters(data)
            elif id == 0x8B:
                self._handleRequestStopCharging(data)
            elif id == 0x8C:
                self._handleRequestPostChargeParameters(data)
            else:
                print("Message ID not supported: {:02x}".format(id))
                break
        self.whitebeet.v2gStop()

    def _handleSessionStarted(self, data):
        """
        Handle the SessionStarted notification
        """
        print("\"Session started\" received")
        message = self.whitebeet.v2gEvseParseSessionStarted(data)
        print("Protocol: {}".format(message['protocol']))
        print("Session ID: {}".format(message['session_id'].hex()))
        print("EVCC ID: {}".format(message['evcc_id'].hex()))

    def _handleSessionStopped(self, data):
        """
        Handle the SessionStopped notification
        """
        print("\"Session stopped\" received")
        self.whitebeet.v2gEvseParseSessionStopped(data)
        self.charger.stop()

    def _handleRequestEvseId(self, data):
        """
        Handle the RequestEvseId notification
        """
        print("\"Request EVSE ID\" received")
        message = self.whitebeet.v2gEvseParseRequestEvseId(data)
        if message['format'] == 0:
            print("No EVSE ID available")
            try:
                self.whitebeet.v2gSetEvseId(None)
            except Warning as e:
                print("Warning: {}".format(e))
            except ConnectionError as e:
                print("ConnectionError: {}".format(e))
        else:
            evseid = "DE*ABC*E*00001*01"
            print("Set EVSE ID: {}".format(evseid))
            try:
                self.whitebeet.v2gSetEvseId(evseid)
            except Warning as e:
                print("Warning: {}".format(e))
            except ConnectionError as e:
                print("ConnectionError: {}".format(e))

    def _handleRequestAuthorization(self, data):
        """
        Handle the RequestAuthorization notification.
        The authorization status will be requested from the user.
        """
        print("\"Request Authorization\" received")
        message = self.whitebeet.v2gEvseParseRequestAuthorization(data)
        timeout = int(message['timeout'] / 1000) - 1
        # Promt for authorization status
        auth_str = input("Authorize the vehicle? Type \"yes\" or \"no\" in the next {}s: ".format(timeout))
        if auth_str is not None and auth_str == "yes":
            print("Vehicle was authorized by user!")
            try:
                self.whitebeet.v2gSetAuthorizationStatus(True)
            except Warning as e:
                print("Warning: {}".format(e))
            except ConnectionError as e:
                print("ConnectionError: {}".format(e))
        else:
            print("Vehicle was NOT authorized by user!")
            try:
                self.whitebeet.v2gSetAuthorizationStatus(False)
            except Warning as e:
                print("Warning: {}".format(e))
            except ConnectionError as e:
                print("ConnectionError: {}".format(e))

    def _handleRequestDiscoveryChargeParameters(self, data):
        """
        Handle the DiscoveryChargeParameters notification
        """
        print("\"Request Discovery Charge Parameters\" received")
        message = self.whitebeet.v2gEvseParseRequestDiscoveryChargeParameters(data)
        if 'dc' in message:
            print("EV maximum current: {}A".format(message['dc']['ev_max_current']))
            self.charger.setEvMaxCurrent(message['dc']['ev_max_current'])
            if 'ev_min_current' in message['dc']:
                print("EV minimum current: {}A".format(message['dc']['ev_min_current']))
                self.charger.setEvMinCurrent(message['dc']['ev_min_current'])
            if 'ev_max_power' in message['dc']:
                print("EV maximum power: {}W".format(message['dc']['ev_max_power']))
                self.charger.setEvMaxPower(message['dc']['ev_max_power'])
            if 'ev_min_power' in message['dc']:
                print("EV minimum power: {}W".format(message['dc']['ev_min_power']))
                self.charger.setEvMinPower(message['dc']['ev_min_power'])
            print("EV maximum voltage: {}V".format(message['dc']['ev_max_voltage']))
            self.charger.setEvMaxVoltage(message['dc']['ev_max_voltage'])
            if 'ev_min_voltage' in message['dc']:
                print("EV minimum voltage: {}V".format(message['dc']['ev_min_voltage']))
                self.charger.setEvMinVoltage(message['dc']['ev_min_voltage'])
            if 'full_soc' in message['dc']:
                print("Full SOC: {}%".format(message['dc']['full_soc']))
            if 'bulk_soc' in message['dc']:
                print("Bulk SOC: {}%".format(message['dc']['bulk_soc']))
            print("SOC: {}%".format(message['dc']['soc']))
        elif 'ac' in message:
            print("Energy amount: {}Wh".format(message['ac']['energy_amount']))
            self.charger.setEvMaxVoltage(message['ac']['ev_max_voltage'])
            print("EV maximum voltage: {}V".format(message['ac']['ev_max_voltage']))
            self.charger.setEvMaxCurrent(message['ac']['ev_max_current'])
            print("EV maximum current: {}A".format(message['ac']['ev_max_current']))
            self.charger.setEvMinCurrent(message['ac']['ev_min_current'])
            print("EV minimum current: {}A".format(message['ac']['ev_min_current']))

        if 'dc' in message:
            isolation_level = 0
            max_current = int(self.charger.getEvseMaxCurrent())
            min_current = int(self.charger.getEvseMinCurrent())
            max_voltage = int(self.charger.getEvseMaxVoltage())
            min_voltage = int(self.charger.getEvseMinVoltage())
            max_power = int(self.charger.getEvseMaxPower())
            current_regulation_tolerance = None
            peak_current_ripple = 2
            energy_to_be_delivered = None
            try:
                self.whitebeet.v2gSetDcDiscoveryChargeParameters(0, isolation_level, max_current, min_current, max_voltage, min_voltage, max_power, current_regulation_tolerance, peak_current_ripple, energy_to_be_delivered)
            except Warning as e:
                print("Warning: {}".format(e))
            except ConnectionError as e:
                print("ConnectionError: {}".format(e))

    def _handleRequestSchedules(self, data):
        """
        Handle the RequestSchedules notification
        """
        print("\"Request Schedules\" received")
        message = self.whitebeet.v2gEvseParseRequestSchedules(data)
        print("Max entries: {}".format(message['max_entries']))

        print("Set the schedule: {}".format(self.schedule))
        try:
            self.whitebeet.v2gSetSchedules(0, self.schedule)
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleRequestCableCheckStatus(self, data):
        """
        Handle the RequestCableCheck notification
        """
        print("\"Request Cable Check Status\" received")
        self.whitebeet.v2gEvseParseRequestCableCheckStatus(data)
        try:
            self.whitebeet.v2gSetDcCableCheckStatus(True)
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleRequestCableCheckParameters(self, data):
        """
        Handle the RequestCableCheckParameters notification
        """
        print("\"Request Cable Check Parameters\" received")
        message = self.whitebeet.v2gEvseParseRequestCableCheckParameters(data)
        if 'dc' in message:
            print("SOC: {}%".format(message['dc']['soc']))
        try:
            self.whitebeet.v2gSetDcCableCheckParameters(0, 1)
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleRequestPreChargeParameters(self, data):
        """
        Handle the RequestPreChargeParameters notification
        """
        print("\"Request Pre Charge Parameters\" received")
        message = self.whitebeet.v2gEvseParseRequestPreChargeParameters(data)
        code = 0
        if 'dc' in message:
            if not self.charger.isVoltageLimitExceeded(message['dc']['ev_target_voltage']):
                print("EV target voltage: {}V".format(message['dc']['ev_target_voltage']))
                self.charger.setEvTargetVoltage(message['dc']['ev_target_voltage'])
            else:
                print("EV target voltage of {}V exceeds charger limit of {}V".format(message['dc']['ev_target_voltage'], self.charger.getEvseMaxVoltage()))
                code = 1
            if not self.charger.isCurrentLimitExceeded(message['dc']['ev_target_current']):
                print("EV target current: {}A".format(message['dc']['ev_target_current']))
                self.charger.setEvTargetCurrent(message['dc']['ev_target_current'])
            else:
                print("EV target current of {}A exceeds charger limit of {}A".format(message['dc']['ev_target_current'], self.charger.getEvseMaxCurrent()))
                code = 1
            ev_power = message['dc']['ev_target_voltage'] * message['dc']['ev_target_current']
            if self.charger.isPowerLimitExceeded(ev_power):
                print("EV power of {}W exceeds charger limit of {}W".format(ev_power, self.charger.getEvseMaxPower()))
            print("SOC: {}%".format(message['dc']['soc']))
        try:
            self.whitebeet.v2gSetDcPreChargeParameters(code, 1, int(self.charger.getEvsePresentVoltage()))
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleRequestStartCharging(self, data):
        """
        Handle the RequestStartCharging notification
        """
        print("\"Request Start Charging\" received")
        message = self.whitebeet.v2gEvseParseRequestStartCharging(data)
        print("Schedule ID: {}".format(message['schedule_id']))
        print("EV power profile: {}".format(message['ev_power_profile']))
        if 'dc' in message:
            if 'soc' in message['dc'] != 0:
                print("SOC: {}%".format(message['dc']['soc']))
            if 'charging_complete' in message['dc']:
                print("Charging complete: {}".format(message['dc']['charging_complete']))
            if 'bulk_charging_complete' in message['dc']:
                print("Bulk charging complete: {}".format(message['dc']['bulk_charging_complete']))
        try:
            self.whitebeet.v2gSetDcStartChargingStatus(0, 1)
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleRequestChargeLoopParameters(self, data):
        """
        Handle the RequestChargeLoopParameters notification
        """
        print("\"Request Charge Loop Parameters\" received")
        message = self.whitebeet.v2gEvseParseRequestChargeLoopParameters(data)
        if 'dc' in message:
            if 'ev_max_current' in message['dc']:
                print("EV maximum current: {}A".format(message['dc']['ev_max_current']))
                self.charger.setEvMaxCurrent(message['dc']['ev_max_current'])
            if 'ev_max_voltage' in message['dc']:
                print("EV maximum voltage: {}V".format(message['dc']['ev_max_voltage']))
                self.charger.setEvMaxVoltage(message['dc']['ev_max_voltage'])
            if 'ev_max_power' in message['dc']:
                print("EV maximum power: {}W".format(message['dc']['ev_max_power']))
                self.charger.setEvMaxPower(message['dc']['ev_max_power'])
            print("EV target voltage: {}V".format(message['dc']['ev_target_voltage']))
            self.charger.setEvTargetVoltage(message['dc']['ev_target_voltage'])
            print("EV target current: {}A".format(message['dc']['ev_target_current']))
            self.charger.setEvTargetCurrent(message['dc']['ev_target_current'])
            print("SOC: {}%".format(message['dc']['soc']))
            print("Charging complete: {}".format(message['dc']['charging_complete']))
            if 'bulk_charging_complete' in message['dc']:
                print("Bulk charging complete: {}".format(message['dc']['bulk_charging_complete']))
            if 'remaining_time_to_full_soc' in message['dc']:
                print("Remaining time to full SOC: {}s".format(message['dc']['remaining_time_to_full_soc']))
            if 'remaining_time_to_bulk_soc' in message['dc']:
                print("Remaining time to bulk SOC: {}s".format(message['dc']['remaining_time_to_bulk_soc']))
        present_voltage = int(self.charger.getEvsePresentVoltage())
        present_current = int(self.charger.getEvsePresentCurrent())
        present_power = int(present_current * present_voltage)
        max_current = int(self.charger.getEvseMaxCurrent())
        max_voltage = int(self.charger.getEvseMaxVoltage())
        max_power = int(self.charger.getEvseMaxPower())
        max_current_reached = present_current >= max_current
        max_voltage_reached = present_voltage >= max_voltage
        max_power_reached = present_power >= max_power
        try:
            self.whitebeet.v2gSetDcChargeLoopParameters(0, 1, present_voltage, present_current, max_current, max_voltage, max_power, max_current_reached, max_voltage_reached, max_power_reached)
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleRequestPostChargeParameters(self, data):
        """
        Handle the RequestPostChargeParameters notification
        """
        print("\"Request Post Charge Parameters\" received")
        message = self.whitebeet.v2gEvseParseRequestPostChargeParameters(data)
        if 'dc' in message:
            print("SOC: {}%".format(message['dc']['soc']))
        try:
            self.whitebeet.v2gSetDcPostChargeParameters(0, 1, int(self.charger.getEvsePresentVoltage()))
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def _handleRequestStopCharging(self, data):
        """
        Handle the RequestStopCharging notification
        """
        print("\"Request Stop Charging\" received")
        message = self.whitebeet.v2gEvseParseRequestStopCharging(data)
        print("Schedule ID: {}".format(message['schedule_id']))
        if 'dc' in message:
            if 'soc' in message['dc']:
                print("SOC: {}%".format(message['dc']['soc']))
            if 'charging_complete' in message['dc']:
                print("Charging complete: {}".format(message['dc']['charging_complete']))
            if 'bulk_charging_complete' in message['dc']:
                print("Bulk charging complete: {}".format(message['dc']['bulk_charging_complete']))
        self.charger.stop()
        try:
            self.whitebeet.v2gSetDcStopChargingStatus(0, 1)
        except Warning as e:
            print("Warning: {}".format(e))
        except ConnectionError as e:
            print("ConnectionError: {}".format(e))

    def getCharger(self):
        """
        Returns the charger object
        """
        if hasattr(self, "charger"):
            return self.charger
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
        else:
            self.schedule = schedule
            return True

    def loop(self):
        """
        This will handle a complete charging session of the EVSE.
        """
        self._initialize()
        if self._waitEvConnected(None):
            return self._handleEvConnected()
        else:
            return False
