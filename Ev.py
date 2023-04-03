import time
import traceback
from Logger import *
from scapy.automaton import Message
from Whitebeet import *
from Battery import *

class Ev():

    def __init__(self, iftype, iface, mac):
        self.logger = Logger()
        self.whitebeet = Whitebeet(iftype, iface, mac)
        print(f"WHITE-beet-PI firmware version: {self.whitebeet.version}")

        self.battery = Battery()

        self.scheduleStartTime = time.time()

        self.config = {}
        self.config["evid"] = bytes.fromhex(mac.replace(":",""))
        self.config["protocol_count"] = 2
        self.config["protocols"] = [0, 1]
        self.config["payment_method_count"] = 1
        self.config["payment_method"] = [0]
        self.config["energy_transfer_mode_count"] = 2
        self.config["energy_transfer_mode"] = [0, 4]
        self.config["battery_capacity"] = self.battery.getCapacity()

        self.DCchargingParams = {}
        self.ACchargingParams = {}

        self._updateChargingParameter()

        self.schedule = None
        self.currentSchedule = 0
        self.currentEnergyTransferMode = -1
        self.currentAcMaxCurrent = 0
        self.currentAcNominalVoltage = 0

        self.state = "init"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if hasattr(self, "whitebeet"):
            del self.whitebeet

    def __del__(self):
        if hasattr(self, "whitebeet"):
            del self.whitebeet

    def load(self, configDict):
        #TODO: change to more generic way
        # First(!) parse battery config
        if "battery" in configDict:
            for key in configDict["battery"]:
                try:
                    if key == "capacity":
                        self.battery.setCapacity(configDict["battery"][key])
                    elif key == "level":
                        self.battery.setLevel(configDict["battery"][key])
                    else:
                        setattr(self.battery, key, configDict["battery"][key])
                except:
                    print(key + " not in ev.battery")
                    continue

        if "ev" in configDict:
            for key in configDict["ev"]:
                try:
                    if key == "evid":
                        self.config[key] = bytes.fromhex(configDict["ev"][key].replace(":",""))
                    else:
                        self.config[key] = configDict["ev"][key]
                except:
                    print(key + " not in EV.config")
                    continue

        self._updateChargingParameter()


    def log_backtrace(self):
        backtrace_frames = traceback.extract_stack()

        filename, line_number, function, code = backtrace_frames[0]
        msg = "Backtrace: %s:%s: %s()\n" % (filename, line_number, function)
        detail = ""
        for frame in backtrace_frames[:-1]:
            filename, line_number, function, code = frame
            detail += "%s:%s: %s()\n" % (filename, line_number, function)
        print(msg, detail)

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
        print("Set the CP state to State B")
        self.whitebeet.controlPilotSetResistorValue(0)
        print("Set SLAC to EV mode")
        self.whitebeet.slacSetValidationConfiguration(0)
        print("Start SLAC")
        self.whitebeet.slacStart(0)
        time.sleep(2)
    
    def _updateChargingParameter(self):
        '''
        Updates the charging parameter
        '''
        # DC 
        if any((True for x in [0, 1, 2, 3] if x in self.config['energy_transfer_mode'])):
            self.DCchargingParams["min_voltage"] = 0
            self.DCchargingParams["min_current"] = 0
            self.DCchargingParams["min_power"] = self.DCchargingParams["min_voltage"] * self.DCchargingParams["min_current"]
            self.DCchargingParams["status"] = 0
            self.DCchargingParams["energy_request"] = self.battery.getCapacity() * (100 - self.battery.getSOC()) // 100
            self.DCchargingParams["departure_time"] = 100000000
            self.DCchargingParams["max_voltage"] = self.battery.max_voltage
            self.DCchargingParams["max_current"] = self.battery.max_current
            self.DCchargingParams["max_power"] = self.battery.max_power
            self.DCchargingParams["soc"] = self.battery.getSOC()
            self.DCchargingParams["target_voltage"] = self.battery.target_voltage
            self.DCchargingParams["target_current"] = self.battery.target_current
            self.DCchargingParams["full_soc"] = self.battery.full_soc
            self.DCchargingParams["bulk_soc"] = self.battery.bulk_soc

        # AC
        if any((True for x in [4, 5] if x in self.config['energy_transfer_mode'])):
            self.ACchargingParams["min_voltage"] = 220
            self.ACchargingParams["min_current"] = 1
            self.ACchargingParams["min_power"] = self.ACchargingParams["min_voltage"] * self.ACchargingParams["min_current"]
            self.ACchargingParams["energy_request"] = self.battery.getCapacity() * (100 - self.battery.getSOC()) // 100
            self.ACchargingParams["departure_time"] = 1000000
            self.ACchargingParams["max_voltage"] = self.battery.max_voltage
            self.ACchargingParams["max_current"] = self.battery.max_current
            self.ACchargingParams["max_power"] = self.battery.max_power

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
                if timeout != None and timestamp_start + timeout < time.time():
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
        self.whitebeet.v2gEvSetConfiguration(self.config)

        # DC 
        if any((True for x in [0, 1, 2, 3] if x in self.config['energy_transfer_mode'])):
            print("Set DC charging parameters")
            self.DCchargingParams["soc"] = self.battery.getSOC()
            self.whitebeet.v2gSetDCChargingParameters(self.DCchargingParams)

        # AC
        if any((True for x in [4, 5] if x in self.config['energy_transfer_mode'])):
            print("Set AC charging parameters")      
            self.whitebeet.v2gSetACChargingParameters(self.ACchargingParams)

        #print("Start V2G")
        #self.whitebeet.v2gStart()
        print("Create new charging session")
        self.whitebeet.v2gStartSession()
        self.state = "sessionStarting"

        oldVal = self.whitebeet.controlPilotGetDutyCycle()
        print("ControlPilot duty cycle: " + str(oldVal))
        while not (self.state == "end"):

            # EV state machine
            if self.state == "sessionStarting":
                pass

            elif self.state == "sessionStared":
                pass

            elif self.state == "cableCheckReady":
                try:
                    print("Change State to State C")
                    self.whitebeet.controlPilotSetResistorValue(1)
                    self.whitebeet.v2gStartCableCheck()
                    self.state = "cableCheckStarted"
                except Warning as e:
                    print("Warning: {}".format(e))
                except ConnectionError as e:
                    print("ConnectionError: {}".format(e))

            elif self.state == "cableCheckStarted":
                pass

            elif self.state == "cableCheckFinished":
                pass

            elif self.state == "preChargingReady":
                try:
                    self.state = "preChargingStarted"
                    self.whitebeet.v2gStartPreCharging()
                except Warning as e:
                    print("Warning: {}".format(e))
                except ConnectionError as e:
                    print("ConnectionError: {}".format(e))

            elif self.state == "preChargingStarted":
                pass

            elif self.state == "chargingReady" and self.schedule is not None:
                startCharging = True

                print(str(self.battery))

                # check max voltage
                if self.battery.in_voltage > self.battery.max_voltage:
                    startCharging = False
                    
                # check target voltage
                if (self.battery.in_voltage >= self.battery.target_voltage + self.battery.target_voltage_delta) \
                or (self.battery.in_voltage <= self.battery.target_voltage - self.battery.target_voltage_delta):
                    startCharging = False
                    
                # check target current
                if self.battery.in_current >= self.battery.max_current:
                    startCharging = False
                    
                # check power conditions
                if self.battery.max_power <= self.battery.in_voltage * self.battery.in_current:
                    startCharging = False

                #TODO: due to a possible bug in the whitebeet EV implementation this is commented out
                '''# check energy transfer mode
                if self.currentEnergyTransferMode in self.config['energy_transfer_mode']:
                    startCharging = True'''
                if startCharging == True and self.battery.is_charging == False:
                    self.state = "waitChargingStarted"
                    try:
                        self.battery.is_charging = True
                        self.whitebeet.v2gStartCharging()

                        # If we are charging in DC state C was already set prior to the cable check,
                        # but if we are charging in AC we need to set the state C here.
                        print("Change State to State C")
                        self.whitebeet.controlPilotSetResistorValue(1)
                    except Warning as e:
                        print("Warning: {}".format(e))
                    except ConnectionError as e:
                        print("ConnectionError: {}".format(e))

                if startCharging == False and self.battery.is_charging == True:
                    try:                        
                        self.whitebeet.v2gStopCharging(False)
                    except Warning as e:
                        print("Warning: {}".format(e))
                    except ConnectionError as e:
                        print("ConnectionError: {}".format(e))

            elif self.state == "chargingStarted" and self.schedule is not None:
                # tick battery simulation
                if self.battery.tickSimulation():

                    # check which schedule to use
                    if ({'start', 'power', 'interval'} <= set(self.schedule)):
                        if time.time() >= (self.scheduleStartTime + self.schedule['start'][self.currentSchedule]):
                            if(len(self.schedule['power']) > self.currentSchedule):
                                self.currentSchedule += 1
                            else:
                                self.whitebeet.v2gStopCharging(False)
                                print("Last profile entry finished")
                                
                        #if self.schedule['power'][self.currentSchedule] > (self.battery.target_current * self.battery.target_voltage):
                        maxPower = min(self.schedule['power'][self.currentSchedule], self.battery.max_power)
                        self.battery.target_current = maxPower // self.battery.target_voltage

                    # check SOC
                    if self.battery.getSOC() < self.battery.full_soc:
                        self.DCchargingParams["soc"] = self.battery.getSOC()
                        try:                  
                            self.whitebeet.v2gUpdateDCChargingParameters(self.DCchargingParams)
                        except Warning as e:
                            print("Warning: {}".format(e))
                        except ConnectionError as e:
                            print("ConnectionError: {}".format(e))

                    elif self.battery.getSOC() >= self.battery.full_soc and self.battery.is_charging == True:
                        self.battery.is_charging = False
                        print("charging done")
                        try:                        
                            self.whitebeet.v2gStopCharging(False)
                        except Warning as e:
                            print("Warning: {}".format(e))
                        except ConnectionError as e:
                            print("ConnectionError: {}".format(e))

            elif self.state == "chargingStopped":
                self.battery.is_charging = False
                try:
                    self.state = "waitSessionStopped"
                    self.whitebeet.v2gStopSession()
                except Warning as e:
                    print("Warning: {}".format(e))
                except ConnectionError as e:
                    print("ConnectionError: {}".format(e))

            elif self.state == "postChargingReady":
                pass

            elif self.state == "sessionStopped":
                self.battery.is_charging = False
                self.state = "end"

            # receive messages from whitebeet
            try:
                id, data = self.whitebeet.v2gEvReceiveRequest()
                #self.logger.log("Receiving 0x{:x}".format(id))
                if id == 0xC3:
                    self._handleScheduleReceived(data)
                elif id == 0xC0:
                    self._handleSessionStarted(data)
                elif id == 0xC1:
                    self._handleDCChargeParametersChanged(data)
                elif id == 0xC2:
                    self._handleACChargeParametersChanged(data)
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
            except TimeoutError:
                # In case we did not receive a request, we try again
                pass
            except Exception as e:
                print(e)
                pass
            
        self.whitebeet.controlPilotSetResistorValue(0)
        try:
            self.whitebeet.v2gStopSession()
        except Exception as e:
            # Session was already stopped
            pass

    def _handleSessionStarted(self, data):
        """
        Handle the SessionStarted notification
        """
        print("\"Session started\" received")
        message = self.whitebeet.v2gEvParseSessionStarted(data)
        self.state = "sessionStared"

        print("\tProtocol: {}".format(message['protocol']))
        print("\tSession ID: {}".format(message['session_id'].hex()))
        print("\tEVSE ID: {}".format(message['evse_id'].hex()))
        print("\tPayment method: {}".format(message['payment_method']))
        print("\tEnergy transfer mode: {}".format(message['energy_transfer_mode']))

        #TODO: message[energy_transfer_mode] is always 0
        if message['energy_transfer_mode'] in self.config['energy_transfer_mode']:
            self.currentEnergyTransferMode = message["energy_transfer_mode"]
        else:
            print("\t\twrong energy transfer mode!")

    def _handleDCChargeParametersChanged(self, data):
        """
        Handle the DCChargeParametersChanged notification
        """
        print("\"DC Charge Parameters Changed\" received")
        message = self.whitebeet.v2gEvParseDCChargeParametersChanged(data)
        print("\tEVSE min voltage: {}".format(message['evse_min_voltage']))
        print("\tEVSE min current: {}".format(message['evse_min_current']))
        print("\tEVSE min power: {}".format(message['evse_min_power']))
        print("\tEVSE max voltage: {}".format(message['evse_max_voltage']))
        print("\tEVSE max current: {}".format(message['evse_max_current']))
        print("\tEVSE max power: {}".format(message['evse_max_power']))
        print("\tEVSE present voltage: {}".format(message['evse_present_voltage']))
        print("\tEVSE present current: {}".format(message['evse_present_current']))
        print("\tEVSE status: {}".format(message['evse_status']))
        if 'evse_isolation_status' in message:
            print("\tEVSE isolation status: {}".format(message['evse_isolation_status']))
        print("\tEVSE voltage limit achieved: {}".format(message['evse_voltage_limit_achieved']))
        print("\tEVSE current limit achieved: {}".format(message['evse_current_limit_achieved']))
        print("\tEVSE power limit achieved: {}".format(message['evse_power_limit_achieved']))
        print("\tEVSE peak current ripple: {}".format(message['evse_peak_current_ripple']))
        if 'evse_current_regulation_tolerance' in message:
            print("\tEVSE current regualtion tolerance: {}".format(message['evse_current_regulation_tolerance']))
        if 'evse_energy_to_be_delivered' in message:
            print("\tEVSE energy to be delivered: {}".format(message['evse_energy_to_be_delivered']))
        
        if message["evse_status"] != 0:
            self.battery.is_charging = False

        # get evse voltage
        self.battery.in_voltage = message["evse_present_voltage"]
        self.battery.in_current = message["evse_present_current"]

    def _handleACChargeParametersChanged(self, data):
        """
        Handle the ACChargeParameterChanged notification
        """
        print("\"AC Charge Parameter changed\" received")
        message = self.whitebeet.v2gEvParseACChargeParametersChanged(data)
        print("\tNominal voltage: {}".format(message['nominal_voltage']))
        print("\tMaximal current: {}".format(message['max_current']))
        print("\tRCD: {}".format(message['rcd']))

        # check target voltage
        self.battery.in_voltage = message['nominal_voltage']
        if self.battery.in_voltage >= self.battery.max_voltage_AC:
            print("Battert voltage out of range!")
            if self.battery.is_charging == True:
                self.whitebeet.v2gStopCharging(False)
            else:
                self.whitebeet.v2gStopSession()

        # check target current
        self.currentAcMaxCurrent = message["max_current"]
        self.battery.in_current = self.schedule['power'][self.currentSchedule] / self.currentAcMaxCurrent
        if self.battery.in_current >= self.battery.max_current_AC or self.battery.in_current <= self.battery.min_current_AC:
            print("Battery current out of range!")
            if self.battery.is_charging == True:
                self.whitebeet.v2gStopCharging(False)
            else:
                self.whitebeet.v2gStopSession()

        # check power conditions
        if self.battery.max_power <= self.battery.in_voltage * self.battery.in_current:
            print("Battery power out of range!")
            if self.battery.is_charging == True:
                self.whitebeet.v2gStopCharging(False)
            else:
                self.whitebeet.v2gStopSession()
        
        if message["rcd"] == True:
            if self.battery.is_charging == True:
                self.whitebeet.v2gStopCharging(False)
            else:
                self.whitebeet.v2gStopSession()
            

    def _handleScheduleReceived(self, data):
        """
        Handle the ScheduleReceived notification.
        """
        print("\"Schedule Received\" received")
        message = self.whitebeet.v2gEvParseScheduleReceived(data)
        
        print("\tTuple count: {}".format(message['tuple_count']))
        print("\tTuple id: {}".format(message['tuple_id']))
        print("\tEntries count: {}".format(message['entries_count']))
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

        self.schedule = {}
        self.schedule["schedule_tuple_id"] = 1
        self.schedule["charging_profile_entries_count"] = message['entries_count']
        self.schedule["start"] = start
        self.schedule["interval"] = interval
        self.schedule["power"] = power

        self.schedule = {'schedule_tuple_id': 1, 'charging_profile_entries_count': 3, 'start': [0, 1800, 3600], 'interval': [1800, 1800, 82800], 'power': [25000, 18750, 12500]}

        self.scheduleStartTime = time.time()
        self.currentSchedule = 0
        
        try:
            self.whitebeet.v2gSetChargingProfile(self.schedule)
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
        self.state = "cableCheckReady"

    def _handleCableCheckFinished(self, data):
        """
        Handle the CableCheckFinished notification
        """
        print("\"Cable Check Finished\" received")
        self.whitebeet.v2gEvParseCableCheckFinished(data)
        self.state = "cableCheckFinished"

    def _handlePreChargingReady(self, data):
        """
        Handle the PreChargingReady notification
        """
        print("\"Pre Charging Ready\" received")
        self.whitebeet.v2gEvParsePreChargingReady(data)
        self.state = "preChargingReady"

    def _handleChargingReady(self, data):
        """
        Handle the ChargingReady notification
        """
        print("\"Charging Ready\" received")
        self.whitebeet.v2gEvParseChargingReady(data)
        if not self.state == "chargingStarted":
            self.state = "chargingReady"

    def _handleChargingStarted(self, data):
        """
        Handle the ChargingStarted notification
        """
        print("\"Charging Started\" received")
        self.whitebeet.v2gEvParseChargingStarted(data)
        self.state = "chargingStarted"

    def _handleChargingStopped(self, data):
        """
        Handle the ChargingStopped notification
        """
        print("\"Charging Stopped\" received")
        self.state = "chargingStopped"
        print("Change State to State B")
        self.whitebeet.controlPilotSetResistorValue(0)

    def _handlePostChargingReady(self, data):
        """
        Handle the PostChargingReady notification
        """
        print("\"Post Charging Ready\" received")
        self.whitebeet.v2gEvParsePostChargingReady(data)
        self.state = "postChargingReady"
        
    def _handleNotificationReceived(self, data):
        """
        Handle the NotificationReceived notification
        """
        print("\"Notification Received\" received")
        message = self.whitebeet.v2gEvParseNotificationReceived(data)
        if message["type"] == 0:
            self.battery.is_charging = False
        elif message["type"] == 1:
            self.DCchargingParams["soc"] = self.battery.getSOC()
            self.whitebeet.v2gSetDCChargingParameters(self.DCchargingParams)

        print("Type : {}".format(message['type']))
        print("Maximum delay : {}".format(message['max_delay']))

    def _handleSessionStopped(self, data):
        """
        Handle the SessionStopped notification
        """
        print("\"Session Stopped\" received")
        self.whitebeet.v2gEvParseSessionStopped(data)
        self.state = "sessionStopped"
        print("Change State to State B")
        self.whitebeet.controlPilotSetResistorValue(0)
    
    def _handleSessionError(self, data):
        """
        Handle the SessionError notification
        """
        print("\"Session Error\" received")
        message = self.whitebeet.v2gEvParseSessionError(data)

        errorType = message['code']
        errorString = "error code not available"

        if errorType == 1:
            errorString = "Selected payment option unavailable"
        elif errorType == 2:
            errorString = "Selected energy transfer mode unavailable"
        elif errorType == 3:
            errorString = "Wrong charge parameter"
        elif errorType == 4:
            errorString = "Power delivery not applied (EVSE is not able to deliver energy)"
        elif errorType == 5:
            errorString = "Charging profile invalid"
        elif errorType == 6:
            errorString = "Contactor error"
        elif errorType == 7:
            errorString = "EVSE present voltage to low"
        elif errorType == 8:
            errorString = "Unspecified error (No details delivered by EVSE)"

        print("Error code: {} - \"{}\"".format(errorType, errorString))
        self.battery.is_charging = False

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

    def loop(self):
        """
        This will handle a complete charging session of the EV.
        """
        self._initialize()
        if self._waitEvseConnected(None):
            return self._handleEvseConnected()
        else:
            return False
