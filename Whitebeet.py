from distutils.command.config import config
from encodings import utf_8
from multiprocessing import Value
import time
import struct
from Logger import *
from FramingInterface import *

class Whitebeet():

    def __init__(self, iftype, iface, mac):
        self.logger = Logger()

        self.connectionError = False
        self.payloadBytes = bytes()
        self.payloadBytesRead = 0
        self.payloadBytesLen = 0

        # System sub IDs
        self.sys_mod_id = 0x10
        self.sys_sub_get_firmware_version = 0x41

        # Network configuration IDs
        self.netconf_sub_id = 0x05
        self.netconf_set_port_mirror_state = 0x55

        # SLAC module IDs
        self.slac_mod_id = 0x28
        self.slac_sub_start = 0x42
        self.slac_sub_stop = 0x43
        self.slac_sub_match = 0x44
        self.slac_sub_start_match = 0x44
        self.slac_sub_set_validation_configuration = 0x4B
        self.slac_sub_join = 0x4D
        self.slac_sub_success = 0x80
        self.slac_sub_failed = 0x81
        self.slac_sub_join_status = 0x84

        # CP module IDs
        self.cp_mod_id = 0x29
        self.cp_sub_set_mode = 0x40
        self.cp_sub_get_mode = 0x41
        self.cp_sub_start = 0x42
        self.cp_sub_stop = 0x43
        self.cp_sub_set_dc = 0x44
        self.cp_sub_get_dc = 0x45
        self.cp_sub_set_res = 0x46
        self.cp_sub_get_res = 0x47
        self.cp_sub_get_state = 0x48
        self.cp_sub_nc_state = 0x81

        # V2G module IDs
        self.v2g_mod_id = 0x27
        self.v2g_sub_set_mode = 0x40
        self.v2g_sub_get_mode = 0x41
        self.v2g_sub_start = 0x42
        self.v2g_sub_stop = 0x43

        # EV sub IDs
        self.v2g_sub_ev_set_configuration = 0xA0
        self.v2g_sub_ev_get_configuration = 0xA1
        self.v2g_sub_ev_set_dc_charging_parameters = 0xA2
        self.v2g_sub_ev_update_dc_charging_parameters = 0xA3
        self.v2g_sub_ev_get_dc_charging_parameters = 0xA4
        self.v2g_sub_ev_set_ac_charging_parameters = 0xA5
        self.v2g_sub_ev_update_ac_charging_parameters = 0xA6
        self.v2g_sub_ev_get_ac_charging_parameters = 0xA7
        self.v2g_sub_ev_set_charging_profile = 0xA8
        self.v2g_sub_ev_start_session = 0xA9
        self.v2g_sub_ev_start_cable_check = 0xAA
        self.v2g_sub_ev_start_pre_charging = 0xAB
        self.v2g_sub_ev_start_charging = 0xAC
        self.v2g_sub_ev_stop_charging = 0xAD
        self.v2g_sub_ev_stop_session = 0xAE
       

        # EVSE sub IDs
        self.v2g_sub_evse_set_configuration = 0x60
        self.v2g_sub_evse_get_configuration = 0x61
        self.v2g_sub_evse_set_dc_charging_parameters = 0x62
        self.v2g_sub_evse_update_dc_charging_parameters = 0x63
        self.v2g_sub_evse_get_dc_charging_parameters = 0x64
        self.v2g_sub_evse_set_ac_charging_parameters = 0x65
        self.v2g_sub_evse_update_ac_charging_parameters = 0x66
        self.v2g_sub_evse_get_ac_charging_parameters = 0x67
        self.v2g_sub_evse_set_sdp_config = 0x68
        self.v2g_sub_evse_get_sdp_config = 0x69
        self.v2g_sub_evse_start_listen = 0x6A
        self.v2g_sub_evse_set_authorization_status = 0x6B
        self.v2g_sub_evse_set_schedules = 0x6C
        self.v2g_sub_evse_set_cable_check_finished = 0x6D
        self.v2g_sub_evse_start_charging = 0x6E
        self.v2g_sub_evse_stop_charging = 0x6F
        self.v2g_sub_evse_stop_listen = 0x70
        self.v2g_sub_evse_set_cable_certificate_installation_and_update_response = 0x73
        self.v2g_sub_evse_set_meter_receipt = 0x74
        self.v2g_sub_evse_send_notification = 0x75
        self.v2g_sub_evse_set_session_parameter_timeout = 0x76

        # Initialization of the framing interface
        self.framing = FramingInterface()
        iftype =  iftype.upper()

        try:
            if iftype == 'ETH':
                self.framing.initialize_framing(iftype, iface, mac)
                log("iface: {}, name: {}, mac: {}".format(iftype, iface, mac))
            else:
                self.framing.initialize_framing(iftype, iface, None)
                log("iface: {}, name: {}".format(iftype, iface))

            self.framing.clear_backlog()
            self.version = self.systemGetVersion()
            self.slacStop()
            self.controlPilotStop()
            if self.v2gGetMode() == 1:
                self.v2gEvseStopListen()
        except:
            self.connectionError = True
            raise ConnectionError("Failed to initialize the framing interface on \"{}\"".format(self.framing.sut_interface))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._shutdown()

    def __del__(self):
        self._shutdown()

    def _shutdown(self):
        if self.framing.isInitialized() == True:
            if self.connectionError == False:
                if self.v2gGetMode() == 1:
                    self.v2gEvseStopListen()
                self.slacStop()
                self.controlPilotStop()
            self.framing.shut_down_interface()

    def _valueToExponential(self, value):
        retValue = b""
        if isinstance(value, int):
            base = value
            exponent = 0
            while(not (base == 0) and (base % 10) == 0 and exponent < 3):
                exponent += 1
                base = base // 10
            retValue += base.to_bytes(2, "big")
            retValue += exponent.to_bytes(1, "big")
        else:
            retValue += value[0].to_bytes(2, "big")
            retValue += value[1].to_bytes(1, "big")
        
        return retValue

    def _sendReceive(self, mod_id, sub_id, payload):
        """
        Sends a message and receives the response. When the whitebeet returns busy the message will
        be repeated until it is accepted to the timeout runs out.
        """
        try:
            time_now = time.time()
            time_start = time_now
            time_end = time_start + 5
            loop = True
            response = None
            while loop == True:
                req_id = self.framing.build_and_send_frame(mod_id, sub_id, payload)
                response = self.framing.receive_next_frame(filter_mod=[mod_id, 0xFF], filter_req_id=req_id, timeout=time_end - time_start)
                if response is None:
                    self.connectionError = True
                    raise ConnectionError("Problem with send/receive - Please check your connection!")
                elif response.mod_id == 0xFF:
                    raise Warning("Framing protocol error: {:02X}".format(response.sub_id))
                elif response.sub_id != sub_id:
                    raise Warning("Response from mod ID {:02X} with unexpected sub ID {:02X} received".format(response.mod_id, response.sub_id))
                elif response.payload_len == 1 and response.payload[0] == 1:
                    loop = True
                else:
                    loop = False
            return response
        except:
            self.connectionError = True
            raise ConnectionError("Problem with send/receive - Please check your connection!")

    def _sendReceiveAck(self, mod_id, sub_id, payload):
        """
        Sends a message and expects and ACK as response. Additional payload is returned.
        """
        response = self._sendReceive(mod_id, sub_id, payload)
        if response.payload_len == 0:
            raise Warning("Module did not accept command with no return code")
        elif response.payload[0] != 0:
            raise Warning("Module did not accept command {:x}:{:x}, return code: {}".format(mod_id, sub_id, response.payload[0]))
        else:
            return response

    def _receive(self, mod_id, sub_id, req_id, timeout):
        """
        Try to receive a message with the given parameters until the timeout is reached.
        """
        try:
            response = self.framing.receive_next_frame(filter_mod=mod_id, filter_sub=sub_id, filter_req_id=req_id, timeout=timeout)
            if response == None:
                raise TimeoutError("We did not receive a frame before the timeout of {}s".format(timeout))
            else:
                return response
        except AssertionError as error:
            raise TimeoutError("We did not receive a frame before the timeout of {}s".format(timeout))

    def _receiveSilent(self, mod_id, sub_id, req_id, timeout):
        """
        Try to receive a message with the given parameters until the timeout is reached.
        Does not raise an assertion if no frame is received within timeout.
        """
        response = self.framing.receive_next_frame(filter_mod=mod_id, filter_sub=sub_id, filter_req_id=req_id, noisy_timeout=False, timeout=timeout)
        return response

    def _printPayload(self, payload):
            print("Length of payload: " + str(len(payload)))
            print("Payload:")
            print(" ".join(hex(n) for n in payload))

    def stop(self):
        self.__exit__()

    def payloadReaderInitialize(self, data, length):
        """
        Helper function for parsing payload. Need to be called before payloadReaderReadInt and
        payloadReaderReadBytes.
        """
        self.payloadBytesRead = 0
        self.payloadBytes = data
        self.payloadBytesLen = length

    def payloadReaderReadInt(self, num):
        """
        Helper function for parsing payload. Reads an integer from the payload.
        """
        value = 0
        if self.payloadBytesRead + num <= self.payloadBytesLen:
            i = self.payloadBytesRead
            if num == 1:
                value = self.payloadBytes[i]
            else:
                value = int.from_bytes(self.payloadBytes[i:i+num], 'big')
            self.payloadBytesRead = self.payloadBytesRead + num
        else:
            raise Warning("Less payload than expected!")
        return value

    def payloadReaderReadExponential(self):
        """
        Helper function for parsing payload. Reads an exponential from the payload.
        """
        value = 0
        if self.payloadBytesRead + 3 <= self.payloadBytesLen:
            i = self.payloadBytesRead
            number, exp = struct.unpack("!hb", self.payloadBytes[i: i+3])
            value = number * 10 ** exp
            self.payloadBytesRead = self.payloadBytesRead + 3
        else:
            raise Warning("Less payload than expected!")
        return value

    def payloadReaderReadIntSigned(self, num):
        """
        Helper function for parsing payload. Reads an signed integer from the payload.
        """
        value = 0
        if self.payloadBytesRead + num <= self.payloadBytesLen:
            i = self.payloadBytesRead
            value = int.from_bytes(self.payloadBytes[i:i+num], 'big', signed=True)
            self.payloadBytesRead = self.payloadBytesRead + num
        else:
            raise Warning("Less payload than expected!")
        return value

    def payloadReaderReadBytes(self, num):
        """
        Helper function for parsing payload. Reads a number of bytes from the payload.
        """
        bytes = None
        if self.payloadBytesRead + num <= self.payloadBytesLen:
            i = self.payloadBytesRead
            if num == 1:
                bytes = bytearray(self.payloadBytes[i])
            else:
                bytes = self.payloadBytes[i:i+num]
            self.payloadBytesRead = self.payloadBytesRead + num
        else:
            raise Warning("Less payload than expected!")
        return bytes

    def payloadReaderFinalize(self):
        """
        Helper function for parsing payload. Finalizes the reading. Checks if payload was read
        completely. Raises a ValueError otherwise.
        """
        if self.payloadBytesRead != self.payloadBytesLen:
            raise Warning("More payload than expected! (read: {}, length: {})".format(self.payloadBytesRead, self.payloadBytesLen))

    def systemGetVersion(self):
        """
        Retrives the firmware version in the form x.x.x
        """
        response = self._sendReceiveAck(self.sys_mod_id, self.sys_sub_get_firmware_version, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        version_length = self.payloadReaderReadInt(2)
        return self.payloadReaderReadBytes(version_length).decode("utf-8")

    def controlPilotSetMode(self, mode):
        """
        Sets the mode of the control pilot service.
        0: EV, 1: EVSE
        """
        if isinstance(mode, int) == False:
            raise ValueError("CP mode needs to be from type int")
        elif mode != 0 and mode != 1:
            raise ValueError("CP mode can be either 0 or 1")
        else:
            self._sendReceiveAck(self.cp_mod_id, self.cp_sub_set_mode, mode.to_bytes(1, "big"))

    def networkConfigSetPortMirrorState(self, value):
        if not isinstance(value, int) or value not in [0,1]:
            raise ValueError("Value needs to be of type int with value 0 or 1")
        else:
            self._sendReceiveAck(self.netconf_sub_id, self.netconf_set_port_mirror_state, value.to_bytes(1, "big"))

    def controlPilotGetMode(self):
        """
        Sets the mode of the control pilot service.
        Returns: 0: EV, 1: EVSE, 255: Mode was not yet set
        """
        response = self._sendReceiveAck(self.cp_mod_id, self.cp_sub_get_mode, None)
        if response.payload_len != 2:
            raise Warning("Module returned malformed message with length {}".format(response.payload_len))
        elif response.payload[1] not in [0, 1, 255]:
            raise Warning("Module returned invalid mode {}".format(response.payload[1]))
        else:
            return response.payload[1]

    def controlPilotStart(self):
        """
        Starts the control pilot service.
        """
        self._sendReceiveAck(self.cp_mod_id, self.cp_sub_start, None)

    def controlPilotStop(self):
        """
        Stops the control pilot service.
        """
        response = self._sendReceive(self.cp_mod_id, self.cp_sub_stop, None)
        if response.payload[0] not in [0, 5]:
            raise Warning("CP module did not accept our stop command")

    def controlPilotSetDutyCycle(self, duty_cycle_in):
        if not isinstance(duty_cycle_in, int) and not isinstance(duty_cycle_in, float):
            raise ValueError("Duty cycle parameter needs to be int or float")
        elif duty_cycle_in < 0 or duty_cycle_in > 100:
            raise ValueError("Duty cycle parameter needs to be between 0 and 100")
        else:
            duty_cycle_permill = int(duty_cycle_in * 10)
            # Convert given duty cycle to permill
            payload = duty_cycle_permill.to_bytes(2, "big")
            self._sendReceiveAck(self.cp_mod_id, self.cp_sub_set_dc, payload)

    def controlPilotGetDutyCycle(self):
        """
        Returns the currently configured duty cycle
        """
        response = self._sendReceiveAck(self.cp_mod_id, self.cp_sub_get_dc, None)
        if response.payload_len != 3:
            raise Warning("Module returned malformed message with length {}".format(response.payload_len))
        else:
            duty_cycle = int.from_bytes(response.payload[1:3], 'big') / 10
            if duty_cycle < 0 or duty_cycle > 100:
                raise Warning("Module returned invalid duty cycle {}".format(duty_cycle))
            else:
                return duty_cycle

    def controlPilotGetResistorValue(self):
        """
        Returns the state of the resistor value
        """
        response = self._sendReceiveAck(self.cp_mod_id, self.cp_sub_get_res, None)
        if response.payload_len != 1:
            raise Warning("Module returned malformed message with length {}".format(response.payload_len))
        elif response.payload[0] not in range(0, 5):
            raise Warning("Module returned invalid state {}".format(response.payload[1]))
        else:
            return response.payload[0]

    def controlPilotSetResistorValue(self, value):
        """
        Returns the state of the resistor value
        """
        if not isinstance(value, int) or value not in range(0, 2):
            print("Resistor value needs to be of type int with range 0..2")
            return None
        response = self._sendReceiveAck(self.cp_mod_id, self.cp_sub_set_res, value.to_bytes(1, "big"))
        if response.payload_len != 1:
            raise Warning("Module returned malformed message with length {}".format(response.payload_len))
        elif response.payload[0] not in range(0, 5):
            raise Warning("Module returned invalid state {}".format(response.payload[1]))
        else:
            return response.payload[0]

    def controlPilotGetState(self):
        """
        Returns the state on the CP
        0: state A, 1: state B, 2: state C, 3: state D, 4: state E, 5: state F, 6: Unknown
        """
        response = self._sendReceiveAck(self.cp_mod_id, self.cp_sub_get_state, None)
        if response.payload_len != 2:
            raise Warning("Module returned malformed message with length {}".format(response.payload_len))
        elif response.payload[1] not in range(0, 7):
            raise Warning("Module returned invalid state {}".format(response.payload[1]))
        else:
            return response.payload[1]

    def slacStart(self, mode_in):
        """
        Starts the SLAC service.
        """
        if not isinstance(mode_in, int):
            raise ValueError("Mode parameter needs to be int")
        elif mode_in not in [0, 1]:
            raise ValueError("Mode parameter needs to be 0 (EV) or 1 (EVSE)")
        else:
            self._sendReceiveAck(self.slac_mod_id, self.slac_sub_start, mode_in.to_bytes(1, "big"))

    def slacStop(self):
        """
        Stops the SLAC service.
        """
        response = self._sendReceive(self.slac_mod_id, self.slac_sub_stop, None)
        if response.payload[0] not in [0, 0x10]:
            raise Warning("SLAC module did not accept our stop command")

    def slacStartMatching(self):
        """
        Starts the SLAC matching process on EV side
        """
        self._sendReceiveAck(self.slac_mod_id, self.slac_sub_match, None)

    def slacMatched(self):
        """
        Waits for SLAC success or failed message for matching process
        """
        time_start = time.time()
        response = self._receive(self.slac_mod_id, [self.slac_sub_success, self.slac_sub_failed], 0xFF, 60)
        if response.payload_len != 0:
            raise Warning("Module returned malformed message with length {}".format(response.payload_len))
        elif response.sub_id == self.slac_sub_success:
            return True
        else:
            if time.time() - time_start > 49:
                raise TimeoutError("SLAC matching timed out")
            return False

    def slacJoinNetwork(self, nid, nmk):
        """
        Joins a network
        """
        if not isinstance(nid, bytearray):
            raise ValueError("NID parameter needs to be bytes")
        elif len(nid) != 7:
            raise ValueError("NID parameter needs to be of length 7 (is {})".format(len(nid)))
        elif not isinstance(nmk, bytearray):
            raise ValueError("NMK parameter needs to be bytes")
        elif len(nmk) != 16:
            raise ValueError("NMK parameter needs to be of length 16 (is {})".format(len(nmk)))
        else:
            self._sendReceiveAck(self.slac_mod_id, self.slac_sub_join, nid + nmk)

    def slacJoined(self):
        """
        Waits for SLAC success or failed message for joining process
        """
        response = self._receive(self.slac_mod_id, self.slac_sub_join_status, 0xFF, 30)
        if response.payload_len != 1:
            raise Warning("Module sent malformed message with length {}".format(response.payload_len))
        elif response.payload[0] not in [0, 1]:
            raise Warning("Module sent invalid status {}".format(response.payload[0]))
        elif response.payload[0] == 0:
            return False
        else:
            return True

    def slacSetValidationConfiguration(self, configuration):
        """
        Enables or disables validation
        """
        if not isinstance(configuration, int) or configuration not in [0,1]:
            print("Parameter configuration needs to be of type int with value 0 or 1")
        else:
            self._sendReceiveAck(self.slac_mod_id, self.slac_sub_set_validation_configuration, configuration.to_bytes(1, "big"))


    def v2gSetMode(self, mode):
        """
        Sets the mode of the V2G service.
        0: EV, 1: EVSE
        """
        if isinstance(mode, int) == False:
            raise ValueError("V2G mode needs to be from type int")
        elif mode not in [0, 1]:
            raise ValueError("V2G mode can be either 0 or 1")
        else:
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_mode, mode.to_bytes(1, "big"))

    def v2gGetMode(self):
        """
        Returns the mode of the V2G service.
        Returns: 0: EV, 1: EVSE, 2: Mode was not yet set
        """
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_get_mode, None)
        if response.payload_len != 2:
            raise Warning("Module returned malformed message with length {}".format(response.payload_len))
        elif response.payload[1] not in [0, 1, 2]:
            raise Warning("Module returned invalid mode {}".format(response.payload[1]))
        else:
            return response.payload[1]

    def v2gStart(self):
        """
        Starts the v2g service.
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_start, None)

    def v2gStop(self):
        """
        Stops the v2g service.
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_stop, None)

    # EV 
    def v2gEvSetConfiguration(self, config):
        """
        Sets the configuration for EV mode
        """
        if not ({"evid", "protocol_count", "protocols", "payment_method_count", "payment_method", "energy_transfer_mode_count", "energy_transfer_mode", "battery_capacity", "battery_capacity"} <= set(config)):
            raise ValueError("Missing keys in config dict")

        if config["evid"] is not None and (not isinstance(config["evid"], bytes) or len(config["evid"]) != 6):
            raise ValueError("evid needs to be of type byte with length 6")
        elif not isinstance(config["protocol_count"], int) or not (1 <= config["protocol_count"] <= 2):
            raise ValueError("protocol_count needs to be of type int with value 1 or 2")
        elif config["protocols"] is not None and (not isinstance(config["protocols"], list) or len(config["protocols"]) != config["protocol_count"]):
            raise ValueError("protocol needs to be of type int with value 0 or 1")
        elif not isinstance(config["payment_method_count"], int):
            raise ValueError("payment_method_count needs to be of type int")
        elif not isinstance(config["payment_method"], list):
            raise ValueError("payment_method needs to be of type list")
        elif not isinstance(config["energy_transfer_mode_count"], int) or not (1 <= config["energy_transfer_mode_count"] <= 6):
            raise ValueError("energy_transfer_mode_count needs to be of type int with value between 1 and 6")
        elif config["energy_transfer_mode"] is not None and (not isinstance(config["energy_transfer_mode"], list) or len(config["energy_transfer_mode"]) != config["energy_transfer_mode_count"]):
            raise ValueError("energy_transfer_mode needs to be of type list with length of energy_transfer_mode_count")
        elif not isinstance(config["battery_capacity"], int) and not (isinstance(config["battery_capacity"], tuple) and len(config["battery_capacity"]) == 2):
            raise ValueError("config battery_capacity needs to be of type int or tuple with length 2")
        else:
            payload = b""
            payload += config["evid"]
            payload += config["protocol_count"].to_bytes(1, "big")
            for protocol in config["protocols"]:
                payload += protocol.to_bytes(1, "big")

            payload += config["payment_method_count"].to_bytes(1, "big")
            for method in config["payment_method"]:
                payload += method.to_bytes(1, "big")

            payload += config["energy_transfer_mode_count"].to_bytes(1, "big")
            for mode in config["energy_transfer_mode"]:
                if mode not in range(0, 6):
                    raise ValueError("values of energy_transfer_mode out of range")
                else:
                    payload += mode.to_bytes(1, "big")

            payload += self._valueToExponential(config["battery_capacity"])
            
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_set_configuration, payload)

    def v2gEvGetConfiguration(self):
        """
        Get the configuration of EV mdoe
        Returns dictionary
        """
        
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_get_configuration, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        self.payloadReaderReadInt(1)

        ret["evid"] = self.payloadReaderReadBytes(6)

        ret["protocol_count"] = self.payloadReaderReadInt(1)
        prot_list = []
        for i in range(ret["protocol_count"]):
            prot_list.append(self.payloadReaderReadInt(1))
        ret["protocol"] = prot_list
        
        ret["payment_method_count"] = self.payloadReaderReadInt(1)
        met_list = []
        for i in range(ret["payment_method_count"]):
            met_list.append(self.payloadReaderReadInt(1))
        ret["payment_method"] = met_list

        ret["energy_transfer_mode_count"] = self.payloadReaderReadInt(1)
        met_list = []
        for i in range(ret["energy_transfer_mode_count"]):
            met_list.append(self.payloadReaderReadInt(1))

        ret["energy_transfer_mode"] = met_list
        
        #TODO: wrong battery capacity
        ret["battery_capacity"] = self.payloadReaderReadExponential()
        #TODO: payload to short
        #ret["departure_time"] = self.payloadReaderReadInt(4)
        self.payloadReaderFinalize()
        return ret

    def v2gSetDCChargingParameters(self, parameter):
        """
        Sets the DC charging parameters of the EV
        """
        if not ({"min_current", "min_voltage", "min_power", "min_voltage", "min_current", "min_power", "status", "energy_request", "departure_time", "max_voltage", "max_current", "max_power", "soc", "target_voltage", "target_current", "full_soc", "bulk_soc"} <= set(parameter)):
            raise ValueError("Missing keys in parameter dict")
        elif not isinstance(parameter["min_voltage"], int) and not (isinstance(parameter["min_voltage"], tuple) and len(parameter["min_voltage"]) == 2):
            raise ValueError("Parameter min_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["min_current"], int) and not (isinstance(parameter["min_current"], tuple) and len(parameter["min_current"]) == 2):
            raise ValueError("Parameter min_current needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["min_power"], int) and not (isinstance(parameter["min_power"], tuple) and len(parameter["min_power"]) == 2):
            raise ValueError("Parameter min_power needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_voltage"], int) and not (isinstance(parameter["max_voltage"], tuple) and len(parameter["max_voltage"]) == 2):
            raise ValueError("Parameter max_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_current"], int) and not (isinstance(parameter["max_current"], tuple) and len(parameter["max_current"]) == 2):
            raise ValueError("Parameter max_current needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_power"], int) and not (isinstance(parameter["max_power"], tuple) and len(parameter["max_power"]) == 2):
            raise ValueError("Parameter max_power needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["soc"], int) or parameter["soc"] not in range(0, 101):
            raise ValueError("Parameter soc needs to be of type int with a vlaue range from 0 to 100")
        elif not isinstance(parameter["status"], int) or parameter["status"] not in range(0, 8):
            raise ValueError("Parameter status needs to be of type int with a vlaue range from 0 to 7")
        elif not isinstance(parameter["target_voltage"], int) and not (isinstance(parameter["target_voltage"], tuple) and len(parameter["target_voltage"]) == 2):
            raise ValueError("Parameter target_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["target_current"], int) and not (isinstance(parameter["target_current"], tuple) and len(parameter["target_current"]) == 2):
            raise ValueError("Parameter target_current needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["full_soc"], int) or parameter["full_soc"] not in range(0, 101):
            raise ValueError("Parameter full_soc needs to be of type int with a value range from 0 to 100")
        elif not isinstance(parameter["bulk_soc"], int) or parameter["bulk_soc"] not in range(0, 101):
            raise ValueError("Parameter bulk_soc needs to be of type int with a value range from 0 to 100")
        elif not isinstance(parameter["energy_request"], int) and not (isinstance(parameter["energy_request"], tuple) and len(parameter["energy_request"]) == 2):
            raise ValueError("Parameter energy_request needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["departure_time"], int) or parameter["departure_time"] not in range(0, 2**32 + 1):
            raise ValueError("Parameter departure_time needs to be of type int with a value range from 0 to 2**32")
        else:
            payload = b""

            payload += self._valueToExponential(parameter["min_voltage"])
            payload += self._valueToExponential(parameter["min_current"])
            payload += self._valueToExponential(parameter["min_power"])

            payload += self._valueToExponential(parameter["max_voltage"])
            payload += self._valueToExponential(parameter["max_current"])
            payload += self._valueToExponential(parameter["max_power"])

            payload += parameter["soc"].to_bytes(1, "big")
            payload += parameter["status"].to_bytes(1, "big")

            payload += self._valueToExponential(parameter["target_voltage"])
            payload += self._valueToExponential(parameter["target_current"])

            payload += parameter["full_soc"].to_bytes(1, "big")
            payload += parameter["bulk_soc"].to_bytes(1, "big")
            
            payload += self._valueToExponential(parameter["energy_request"])

            payload += parameter["departure_time"].to_bytes(4, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_set_dc_charging_parameters, payload)

    def v2gUpdateDCChargingParameters(self, parameter):
        """
        Updates the DC charging parameters of the EV
        """
        if not ({"min_current", "min_voltage", "min_power", "min_voltage", "min_current", "min_power", "status","max_voltage", "max_current", "max_power", "soc", "target_voltage", "target_current"} <= set(parameter)):
            raise ValueError("Missing keys in parameter dict")
        elif not isinstance(parameter["min_voltage"], int) and not (isinstance(parameter["min_voltage"], tuple) and len(parameter["min_voltage"]) == 2):
            raise ValueError("Parameter min_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["min_current"], int) and not (isinstance(parameter["min_current"], tuple) and len(parameter["min_current"]) == 2):
            raise ValueError("Parameter min_current needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["min_power"], int) and not (isinstance(parameter["min_power"], tuple) and len(parameter["min_power"]) == 2):
            raise ValueError("Parameter min_power needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_voltage"], int) and not (isinstance(parameter["max_voltage"], tuple) and len(parameter["max_voltage"]) == 2):
            raise ValueError("Parameter max_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_current"], int) and not (isinstance(parameter["max_current"], tuple) and len(parameter["max_current"]) == 2):
            raise ValueError("Parameter max_current needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_power"], int) and not (isinstance(parameter["max_power"], tuple) and len(parameter["max_power"]) == 2):
            raise ValueError("Parameter max_power needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["soc"], int) or parameter["soc"] not in range(0, 101):
            raise ValueError("Parameter soc needs to be of type int with a vlaue range from 0 to 100")
        elif not isinstance(parameter["status"], int) or parameter["status"] not in range(0, 8):
            raise ValueError("Parameter status needs to be of type int with a vlaue range from 0 to 7")
        elif not isinstance(parameter["target_voltage"], int) and not (isinstance(parameter["target_voltage"], tuple) and len(parameter["target_voltage"]) == 2):
            raise ValueError("Parameter target_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["target_current"], int) and not (isinstance(parameter["target_current"], tuple) and len(parameter["target_current"]) == 2):
            raise ValueError("Parameter target_current needs to be of type int or tuple with length 2")
        else:
            payload = b""

            payload += self._valueToExponential(parameter["min_voltage"])
            payload += self._valueToExponential(parameter["min_current"])
            payload += self._valueToExponential(parameter["min_power"])

            payload += self._valueToExponential(parameter["max_voltage"])
            payload += self._valueToExponential(parameter["max_current"])
            payload += self._valueToExponential(parameter["max_power"])

            payload += parameter["soc"].to_bytes(1, "big")
            payload += parameter["status"].to_bytes(1, "big")

            payload += self._valueToExponential(parameter["target_voltage"])
            payload += self._valueToExponential(parameter["target_current"])

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_update_dc_charging_parameters, payload)

    def v2gGetDCChargingParameters(self, data):
        """
        Gets the DC charging parameters
        Returns dictionary
        """
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_get_dc_charging_parameters, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        self.payloadReaderReadInt(1)
        ret["min_voltage"] = self.payloadReaderReadBytes(3)
        ret["min_current"] = self.payloadReaderReadBytes(3)
        ret["min_power"] = self.payloadReaderReadBytes(3)
        ret["max_voltage"] = self.payloadReaderReadBytes(3)
        ret["max_current"] = self.payloadReaderReadBytes(3)
        ret["max_power"] = self.payloadReaderReadBytes(3)
        ret["soc"] = self.payloadReaderReadInt(1)
        ret["status"] = self.payloadReaderReadInt(1)
        ret["full_soc"] = self.payloadReaderReadInt(1)
        ret["bulk_soc"] = self.payloadReaderReadInt(1)
        ret["energy_request"] = self.payloadReaderReadBytes(3)
        ret["departure_time"] = self.payloadReaderReadInt(4)
        self.payloadReaderFinalize()
        return ret

    def v2gSetACChargingParameters(self, parameter):
        """
        Sets the AC charging parameters of the EV
        """
        if not ({"min_current", "min_voltage", "min_power", "min_voltage", "min_current", "min_power", "energy_request", "departure_time", "max_voltage", "max_current", "max_power"} <= set(parameter)):
            raise ValueError("Missing keys in parameter dict")
        elif not isinstance(parameter["min_voltage"], int) and not (isinstance(parameter["min_voltage"], tuple) and len(parameter["min_voltage"]) == 2):
            raise ValueError("Parameter min_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["min_current"], int) and not (isinstance(parameter["min_current"], tuple) and len(parameter["min_current"]) == 2):
            raise ValueError("Parameter min_current needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["min_power"], int) and not (isinstance(parameter["min_power"], tuple) and len(parameter["min_power"]) == 2):
            raise ValueError("Parameter min_power needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_voltage"], int) and not (isinstance(parameter["max_voltage"], tuple) and len(parameter["max_voltage"]) == 2):
            raise ValueError("Parameter max_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_current"], int) and not (isinstance(parameter["max_current"], tuple) and len(parameter["max_current"]) == 2):
            raise ValueError("Parameter max_current needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_power"], int) and not (isinstance(parameter["max_power"], tuple) and len(parameter["max_power"]) == 2):
            raise ValueError("Parameter max_power needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["energy_request"], int) and not (isinstance(parameter["energy_request"], tuple) and len(parameter["energy_request"]) == 2):
            raise ValueError("Parameter energy_request needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["departure_time"], int) or parameter["departure_time"] not in range(0, 2**32 + 1):
            raise ValueError("Parameter departure_time needs to be of type int with a value range from 0 to 2**32")
        else:
            payload = b""

            payload += self._valueToExponential(parameter["min_voltage"])
            payload += self._valueToExponential(parameter["min_current"])
            payload += self._valueToExponential(parameter["min_power"])

            payload += self._valueToExponential(parameter["max_voltage"])
            payload += self._valueToExponential(parameter["max_current"])
            payload += self._valueToExponential(parameter["max_power"])

            payload += self._valueToExponential(parameter["energy_request"])

            payload += parameter["departure_time"].to_bytes(4, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_set_ac_charging_parameters, payload)

    def v2gUpdateACChargingParameters(self, parameter):
        """
        Updates the AC charging parameters of the EV
        """
        if not ({"min_current", "min_voltage", "min_power", "min_voltage", "min_current", "min_power", "energy_request", "departure_time", "max_voltage", "max_current", "max_power", "soc"} <= set(parameter)):
            raise ValueError("Missing keys in parameter dict")
        elif not isinstance(parameter["min_voltage"], int) and not (isinstance(parameter["min_voltage"], tuple) and len(parameter["min_voltage"]) == 2):
            raise ValueError("Parameter min_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["min_current"], int) and not (isinstance(parameter["min_current"], tuple) and len(parameter["min_current"]) == 2):
            raise ValueError("Parameter min_current needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["min_power"], int) and not (isinstance(parameter["min_power"], tuple) and len(parameter["min_power"]) == 2):
            raise ValueError("Parameter min_power needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_voltage"], int) and not (isinstance(parameter["max_voltage"], tuple) and len(parameter["max_voltage"]) == 2):
            raise ValueError("Parameter max_voltage needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_current"], int) and not (isinstance(parameter["max_current"], tuple) and len(parameter["max_current"]) == 2):
            raise ValueError("Parameter max_current needs to be of type int or tuple with length 2")
        elif not isinstance(parameter["max_power"], int) and not (isinstance(parameter["max_power"], tuple) and len(parameter["max_power"]) == 2):
            raise ValueError("Parameter max_power needs to be of type int or tuple with length 2")
        else:
            payload = b""

            payload += self._valueToExponential(parameter["min_voltage"])
            payload += self._valueToExponential(parameter["min_current"])
            payload += self._valueToExponential(parameter["min_power"])

            payload += self._valueToExponential(parameter["max_voltage"])
            payload += self._valueToExponential(parameter["max_current"])
            payload += self._valueToExponential(parameter["max_power"])

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_update_dc_charging_parameters, payload)

    def v2gACGetChargingParameters(self, data):
        """
        Gets the AC charging parameters
        Returns dictionary
        """
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_get_dc_charging_parameters, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        self.payloadReaderReadInt(1)
        ret["min_voltage"] = self.payloadReaderReadBytes(3)
        ret["min_current"] = self.payloadReaderReadBytes(3)
        ret["min_power"] = self.payloadReaderReadBytes(3)
        ret["max_voltage"] = self.payloadReaderReadBytes(3)
        ret["max_current"] = self.payloadReaderReadBytes(3)
        ret["max_power"] = self.payloadReaderReadBytes(3)
        ret["energy_request"] = self.payloadReaderReadBytes(3)
        ret["departure_time"] = self.payloadReaderReadInt(4)
        self.payloadReaderFinalize()
        return ret

    def v2gSetChargingProfile(self, schedule):
        """
        Sets the charging profile
        """
        if not isinstance(schedule['schedule_tuple_id'], int) or schedule['schedule_tuple_id'] not in range(2**16):
            raise ValueError("Parameter schedule_tuple_id needs to be of type int with range 0 - 65536")
        if not isinstance(schedule['charging_profile_entries_count'], int) or schedule['charging_profile_entries_count'] not in range(1, 24):
            raise ValueError("Parameter chargin_profile_entries_count needs to be of type int with range 1 - 24")
        if schedule['start'] is not None and (not isinstance(schedule['start'], list)):
            raise ValueError("Parameter start needs to be of type list")
        if schedule['interval'] is not None and (not isinstance(schedule['interval'], list)):
            raise ValueError("Parameter interval needs to be of type list")
        elif schedule['power'] is not None and (not isinstance(schedule['power'], list)):
            raise ValueError("Parameter power needs to be of type list")
        else:
            payload = b""
            payload += schedule['schedule_tuple_id'].to_bytes(2, "big")
            payload += schedule['charging_profile_entries_count'].to_bytes(1, "big")
            for i in range(schedule['charging_profile_entries_count']):
                payload += int(schedule['start'][i]).to_bytes(4, "big")
                payload += int(schedule['interval'][i]).to_bytes(4, "big")
                payload += int(schedule['power'][i]).to_bytes(2, "big")
                payload += b"\x00"
        print(schedule)
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_set_charging_profile, payload)

    def v2gStartSession(self):
        """
        Starts a new charging session
        """        
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_start_session, None)

    def v2gStartCableCheck(self):
        """
        Starts the cable check after notification Cable Check Ready has been reveived
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_start_cable_check, None)

    def v2gStartPreCharging(self):
        """
        Starts the pre charging after notification Pre Charging Ready has been reveived
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_start_pre_charging, None)

    def v2gStartCharging(self):
        """
        Starts the  charging after notification Charging Ready has been reveived
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_start_charging, None)

    def v2gStopCharging(self, renegotiation):
        """
        Stops the charging
        """
        if not isinstance(renegotiation, bool):
            raise ValueError("Parameter renegotiation has to be of type bool")
        else:
            payload = b""
            payload += renegotiation.to_bytes(1, "big")
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_stop_charging, payload)

    def v2gStopSession(self):
        """
        Stops the currently active charging session after the notification Post Charging Ready has been received.
        When Charging in AC mode the session is stopped auotamically because no post charging needs to be performed.
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_ev_stop_session, None)
    
    def v2gEvParseSessionStarted(self, data):
        """
        Parse a session started message.
        Will return a dictionary with the following keys:
        keys protocol           int
        session_id              bytes
        evse_id                 bytes
        payment_method          int
        energy_transfer_method  int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['protocol'] = self.payloadReaderReadInt(1)
        message['session_id'] = self.payloadReaderReadBytes(8)
        message['evse_id'] = self.payloadReaderReadBytes(self.payloadReaderReadInt(1))
        message['payment_method'] = self.payloadReaderReadInt(1)
        message['energy_transfer_mode'] = self.payloadReaderReadInt(1)
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseDCChargeParametersChanged(self, data):
        """
        Parse a DC charge parameters changed message.
        Will return a dictionary with the following keys:
        keys evse_min_voltage   int or float
        evse_min_current        int or float
        evse_min_power          int or float
        evse_max_voltage        int or float
        evse_max_current        int or float
        evse_max_power          int or float
        evse_present_voltage    int or float
        evse_present_current    int or float
        evse_status             int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['evse_min_voltage'] = self.payloadReaderReadExponential()
        message['evse_min_current'] = self.payloadReaderReadExponential()
        message['evse_min_power'] = self.payloadReaderReadExponential()
        message['evse_max_voltage'] = self.payloadReaderReadExponential()
        message['evse_max_current'] = self.payloadReaderReadExponential()
        message['evse_max_power'] = self.payloadReaderReadExponential()
        message['evse_present_voltage'] = self.payloadReaderReadExponential()
        message['evse_present_current'] = self.payloadReaderReadExponential()
        message['evse_status'] = self.payloadReaderReadInt(1)
        if self.payloadReaderReadInt(1) != 0:
            message['evse_isolation_status'] = self.payloadReaderReadInt(1)
        message['evse_voltage_limit_achieved'] = self.payloadReaderReadInt(1)
        message['evse_current_limit_achieved'] = self.payloadReaderReadInt(1)
        message['evse_power_limit_achieved'] = self.payloadReaderReadInt(1)
        message['evse_peak_current_ripple'] = self.payloadReaderReadExponential()
        if self.payloadReaderReadInt(1) != 0:
            message['evse_current_regulation_tolerance'] = self.payloadReaderReadExponential()
        if self.payloadReaderReadInt(1) != 0:
            message['evse_energy_to_be_delivered'] = self.payloadReaderReadExponential()
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseACChargeParametersChanged(self, data):
        """
        Parse a AC charge parameters changed message.
        Will return a dictionary with the following keys:
        keys nominal_voltage    int or float
        max_current             int or float
        rcd                     boolean
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        message['nominal_voltage'] = self.payloadReaderReadExponential()
        message['max_current'] = self.payloadReaderReadExponential()
        message['rcd'] = True if self.payloadReaderReadInt(1) == 1 else False
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseScheduleReceived(self, data):
        """
        Parse a schedule received message.
        Will return a dictionary with the following keys:
        keys tuple_count    int
        tuple_id            int
        entries_count       int
        entries             list of dict

        The list elements of entries have the following keys:

        start               int
        interval            int
        power               int or float
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        message['tuple_count'] = self.payloadReaderReadInt(1)
        message['tuple_id'] = self.payloadReaderReadInt(2)
        message['entries_count'] = self.payloadReaderReadInt(2)
        message['entries'] = []
        for i in range(message["entries_count"]):
            start = self.payloadReaderReadInt(4)
            interval = self.payloadReaderReadInt(4)
            power = self.payloadReaderReadExponential()
            message['entries'].append({'start': start,'interval': interval,'power': power})
        self.payloadReaderFinalize()

        return message
    
    def v2gEvParseCableCheckReady(self, data):
        """
        Parse a cable check ready message.
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseCableCheckFinished(self, data):
        """
        Parse a cable check finished message.
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParsePreChargingReady(self, data):
        """
        Parse a pre charging ready message.
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseChargingReady(self, data):
        """
        Parse a charging ready message.
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseChargingStarted(self, data):
        """
        Parse a charging started message.
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseChargingStopped(self, data):
        """
        Parse a charging stopped message.
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParsePostChargingReady(self, data):
        """
        Parse a post charging method ready message.
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseSessionStopped(self, data):
        """
        Parse a session stopped message.
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseNotificationReceived(self, data):
        """
        Parse a notification received message.
        Will return a dictionary with the following keys:
        keys type   int
        max_delay   int
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        message['type'] = self.payloadReaderReadInt(1)
        message['max_delay'] = self.payloadReaderReadInt(2)
        self.payloadReaderFinalize()
        return message
    
    def v2gEvParseSessionError(self, data):
        """
        Parse a session error message.
        Will return a dictionary with the following keys:
        keys code    int
        """
        message = {}        
        self.payloadReaderInitialize(data, len(data))
        message['code'] = self.payloadReaderReadInt(1)
        self.payloadReaderFinalize()
        return message

    # EV

    def v2gEvseSetConfiguration(self, configuration):
        """
        Sets the configuration
        """
        if not ({"evse_id_DIN", "evse_id_ISO", "protocol", "payment_method", "payment_method", "certificate_installation_support", "certificate_update_support", "energy_transfer_mode"} <= set(configuration)):
            raise ValueError("Missing keys in config dict")

        if not ('evse_id_DIN' in configuration or isinstance(configuration['evse_id_DIN'],str) or len(configuration['evse_id_DIN']) <= 32):
            raise ValueError("evse_id_DIN needs to be of type str with maximum length 32")
        elif not ('evse_id_ISO' in configuration or isinstance(configuration['evse_id_ISO'],str) or len(configuration['evse_id_ISO']) <= 38):
            raise ValueError("evse_id_ISO needs to be of type str with maximum length 38")
        elif not ('protocol' in configuration  or isinstance(configuration['protocol'],list) or len(configuration['protocol']) in [1,2]):
            raise ValueError("protocol needs to be of type list with length between 1 and 2")
        elif not ('payment_method' in configuration or isinstance(configuration['payment_method'],list) or len(configuration['payment_method']) in [1,2]):
            raise ValueError("payment_method needs to be of type list with length between 1 and 2")
        elif not ('energy_transfer_mode' in configuration or isinstance(configuration['energy_transfer_mode'],list) or len(configuration['energy_transfer_mode']) in range(6)):
            raise ValueError("energy_transfer_mode needs to be of type list with length between 1 and 6")
        elif 'certificate_installation_support' in configuration and not isinstance(configuration['certificate_installation_support'], bool):
            raise ValueError("certificate_installation_support needs to be of type bool")
        elif 'certificate_update_support' in configuration and not isinstance(configuration['certificate_update_support'], bool):
            raise ValueError("certificate_update_support needs to be of type bool")
        else:
            
            payload = b''
            
            payload += len(configuration['evse_id_DIN']).to_bytes(1, 'big')
            payload += bytes(configuration['evse_id_DIN'], "utf-8")
            payload += len(configuration['evse_id_ISO']).to_bytes(1, 'big')
            payload += bytes(configuration['evse_id_ISO'], "utf-8")

            payload += len(configuration['protocol']).to_bytes(1, 'big')
            for val in configuration['protocol']:
                payload += val.to_bytes(1, "big")

            payload += len(configuration['payment_method']).to_bytes(1, 'big')
            for val in configuration['payment_method']:
                payload += val.to_bytes(1, "big")

            payload += len(configuration['energy_transfer_mode']).to_bytes(1, 'big')
            for val in configuration['energy_transfer_mode']:
                payload += val.to_bytes(1, "big")

            if 'certificate_installation_support' in configuration:
                payload += b'\x01' if configuration['certificate_installation_support'] == True else b'\x00'
            else:
                payload += b'\x00'

            if 'certificate_update_support' in configuration:
                payload += b'\x01' if configuration['certificate_update_support'] == True else b'\x00'
            else:
                payload += b'\x00'

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_configuration, payload)

    def v2gEvseGetConfiguration(self):
        """
        Sets the configuration
        """
        
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_get_configuration, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        
        code = self.payloadReaderReadBytes(1)
        ret['code'] = code
        ret['evse_id_din'] = None
        ret['evse_id_iso'] = None
        ret['evse_protocols'] = None
        ret['evse_payment_method'] = None
        ret['evse_certification_installation_support'] = None
        ret['evse_certification_update_support'] = None
        ret['evse_energy_transfer_mode'] = None

        if code == b'\x00':
            lenEvseIdDin = self.payloadReaderReadBytes(1)
            evseIdDin = self.payloadReaderReadBytes(lenEvseIdDin)

            lenEvseIdIso = self.payloadReaderReadBytes(1)
            evseIdIso = self.payloadReaderReadBytes(lenEvseIdDin)

            lenProtocols = self.payloadReaderReadBytes(1)
            protocols = self.payloadReaderReadBytes(lenProtocols)

            lenPaymentMethod = self.payloadReaderReadBytes(1)
            paymentMethod = self.payloadReaderReadBytes(lenPaymentMethod)

            if 1 in paymentMethod:
                certificateInstallationSupported = True if self.payloadReaderReadBytes(1) == b'\x00' else False
                certificateUpdateSupported = True if self.payloadReaderReadBytes(1) == b'\x00' else False
            
            lenEnergyTransferMode = self.payloadReaderReadBytes(1)
            energyTransferMode = self.payloadReaderReadBytes(lenEnergyTransferMode)

            ret['evse_id_din'] = evseIdDin.decode('utf-8')
            ret['evse_id_iso'] = evseIdIso.decode('utf-8')
            ret['evse_protocols'] = protocols
            ret['evse_payment_method'] = paymentMethod
            ret['evse_certification_installation_support'] = certificateInstallationSupported
            ret['evse_certification_update_support'] = certificateUpdateSupported
            ret['evse_energy_transfer_mode'] = energyTransferMode

        return ret

    def v2gEvseSetDcChargingParameters(self, parameters):
        """
        Set DC Charging Parameter
        """
        
        if not ('isolation_level' in parameters or isinstance(parameters['isolation_level'],int) or parameters['isolation_level'] in range(4)):
            raise ValueError("isolation_level needs to be of type int with range 4")
        elif not ('min_voltage' in parameters or isinstance(parameters['min_voltage'],(int, tuple))):
            raise ValueError("min_voltage needs to be of type int or tuple")
        elif not ('min_current' in parameters or isinstance(parameters['min_current'],(int, tuple))):
            raise ValueError("min_current needs to be of type int or tuple")
        elif not ('max_voltage' in parameters or isinstance(parameters['max_voltage'],(int, tuple))):
            raise ValueError("max_voltage needs to be of type int or tuple")
        elif not ('max_current' in parameters or isinstance(parameters['max_current'],(int, tuple))):
            raise ValueError("max_current needs to be of type int or tuple")
        elif not ('max_power' in parameters or isinstance(parameters['max_power'],(int, tuple))):
            raise ValueError("max_power needs to be of type int or tuple")
        elif not isinstance(parameters['current_regulation_tolerance'],(int, tuple)) if 'current_regulation_tolerance' in parameters else False:
            raise ValueError("current_regulation_tolerance needs to be of type int or tuple")
        elif not ('peak_current_ripple' in parameters or isinstance(parameters['peak_current_ripple'],(int, tuple))):
            raise ValueError("peak_current_ripple needs to be of type int or tuple")
        elif not ('status' in parameters or isinstance(parameters['status'],int) or parameters['status'] in range(6)):
            raise ValueError("status needs to be of type int with range 6")
        else:
            payload = b''
            payload += parameters['isolation_level'].to_bytes(1, "big")
            payload += self._valueToExponential(parameters['min_voltage'])
            payload += self._valueToExponential(parameters['min_current'])
            payload += self._valueToExponential(parameters['max_voltage'])
            payload += self._valueToExponential(parameters['max_current'])
            payload += self._valueToExponential(parameters['max_power'])

            if 'current_regulation_tolerance' in parameters:
                payload += b'\x01'
                payload += self._valueToExponential(parameters['current_regulation_tolerance'])
            else:
                payload += b'\x00'
            
            payload += self._valueToExponential(parameters['peak_current_ripple'])
            payload += parameters['status'].to_bytes(1, "big")

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_dc_charging_parameters, payload)

    def v2gEvseUpdateDcChargingParameters(self, parameters):
            """
            Update DC Charging Parameter
            """

            if not ('isolation_level' in parameters or isinstance(parameters['isolation_level'],int) or parameters['isolation_level'] in range(4)):
                raise ValueError("isolation_level needs to be of type int with range 4")
            elif not ('present_voltage' in parameters or isinstance(parameters['present_voltage'],(int, tuple))):
                raise ValueError("present_voltage needs to be of type int or tuple")
            elif not ('present_current' in parameters or isinstance(parameters['present_current'],(int, tuple))):
                raise ValueError("present_current needs to be of type int or tuple")
            elif not ('max_voltage' in parameters or isinstance(parameters['max_voltage'],(int, tuple))):
                raise ValueError("max_voltage needs to be of type int or tuple")
            elif not ('max_current' in parameters or isinstance(parameters['max_current'],(int, tuple))):
                raise ValueError("max_current needs to be of type int or tuple")
            elif not ('max_power' in parameters or isinstance(parameters['max_power'],(int, tuple))):
                raise ValueError("max_power needs to be of type int or tuple")
            elif not ('status' in parameters or isinstance(parameters['status'],int) or parameters['status'] in range(6)):
                raise ValueError("status needs to be of type int with range 6")
            else:
                payload = b''
                payload += parameters['isolation_level'].to_bytes(1, "big")
                payload += self._valueToExponential(parameters['present_voltage'])
                payload += self._valueToExponential(parameters['present_current'])
                
                if 'max_voltage' in parameters:
                    payload += b'\x01'
                    payload += self._valueToExponential(parameters['max_voltage'])
                else:
                    payload += b'\x00'

                if 'max_current' in parameters:
                    payload += b'\x01'
                    payload += self._valueToExponential(parameters['max_current'])
                else:
                    payload += b'\x00'

                if 'max_power' in parameters:
                    payload += b'\x01'
                    payload += self._valueToExponential(parameters['max_power'])
                else:
                    payload += b'\x00'
                
                payload += parameters['status'].to_bytes(1, "big")

                self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_update_dc_charging_parameters, payload)

    def v2gEvseGetDCChargingParameters(self):
        """

        """
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_get_dc_charging_parameters, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        code = self.payloadReaderReadInt(1)
        ret['code'] = code
        
        if code > b'\x00':

            isolationLevel = self.payloadReaderReadInt(1)

            minVoltage = self.payloadReaderReadExponential()
            minCurrent = self.payloadReaderReadExponential()
            maxVoltage = self.payloadReaderReadExponential()
            maxCurrent = self.payloadReaderReadExponential()
            maxPower = self.payloadReaderReadExponential()

            currentRegulationTolerancePresent = self.payloadReaderReadInt(1)
            if currentRegulationTolerancePresent == 1:
                currentRegulationTolerance = self.payloadReaderReadExponential()
            
            peakCurrentRipple = self.payloadReaderReadExponential()
            
            lenPresentVoltage = self.payloadReaderReadInt(1)
            if lenPresentVoltage == 1:
                presentVoltage = self.payloadReaderReadExponential()

            lenPresentCurrent = self.payloadReaderReadInt(1)
            if lenPresentCurrent == 1:
                presentCurrent = self.payloadReaderReadExponential()

            status = self.payloadReaderReadInt(1)

            ret['isolation_level'] = isolationLevel
            ret['min_voltage'] = minVoltage
            ret['min_current'] = minCurrent
            ret['max_voltage'] = maxVoltage
            ret['max_current'] = maxCurrent
            ret['max_power'] = maxPower
            
            if currentRegulationTolerancePresent == 1:
                ret['current_regulation_tolerance'] = currentRegulationTolerance

            ret['peak_current_ripple'] = peakCurrentRipple

            if lenPresentVoltage == 1:
                ret['present_voltage'] = presentVoltage
            if lenPresentCurrent == 1:
                ret['present_current'] = presentCurrent

            ret['status'] = status

        return ret   

    def v2gEvseSetAcChargingParameters(self, parameters):
        """
        Set AC Charging Parameter
        """
        
        if not ('rcd_status' in parameters or isinstance(parameters['rcd_status'], bool)):
            raise ValueError("rcd_status needs to be of type bool")
        elif not ('nominal_voltage' in parameters or isinstance(parameters['nominal_voltage'],(int, tuple))):
            raise ValueError("nominal_voltage needs to be of type int or tuple")
        elif not ('max_current' in parameters or isinstance(parameters['max_current'],(int, tuple))):
            raise ValueError("max_current needs to be of type int or tuple")
        else:
            payload = b''
            payload += parameters['rcd_status'].to_bytes(1, "big")
            payload += self._valueToExponential(parameters['nominal_voltage'])
            payload += self._valueToExponential(parameters['max_current'])

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_ac_charging_parameters, payload)

    def v2gEvseUpdateAcChargingParameters(self, parameters):
        """
        Set DC Charging Parameter
        """
        
        if not ('rcd_status' in parameters or isinstance(parameters['rcd_status'], bool)):
            raise ValueError("rcd_status needs to be of type bool")
        elif not isinstance(parameters['max_current'],(int, tuple)) if 'max_current' in parameters else False:
            raise ValueError("max_current needs to be of type int or tuple")
        else:
            payload = b''
            payload += b'\x01' if parameters['rcd_status'] == True else b'\x00'

            if 'max_current' in parameters:
                payload += int(1).to_bytes(1, "big")
                payload += self._valueToExponential(parameters['max_current'])
            else:
                payload += int(0).to_bytes(1, "big")

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_update_ac_charging_parameters, payload)

    def v2gEvseGetAcChargingParameters(self):
        """

        """
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_get_ac_charging_parameters, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        code = self.payloadReaderReadInt(1)
        ret['code'] = code
        
        if code > b'\x00':

            rcdStatus = self.payloadReaderReadInt(1)

            nominalVoltage = self.payloadReaderReadExponential()
            maxCurrent = self.payloadReaderReadExponential()

            ret['rcd_status'] = True if rcdStatus == 0 else False
            ret['nominal_voltage'] = nominalVoltage
            ret['max_current'] = maxCurrent

        return ret 

    def v2gEvseSetSdpConfig(self, sdp_config):
        """
        Configures the SDP server
        """
        if not ('allow_unsecure' in sdp_config or isinstance(sdp_config['allow_unsecure'], bool)):
            raise ValueError("allow_unsecure needs to be of type bool")
        elif not (isinstance(sdp_config['unsecure_port'], int) and (sdp_config['unsecure_port'] in range(49152, 65535))) if (('unsecure_port' in sdp_config) and (sdp_config['allow_unsecure'] == True)) else True:
            raise ValueError("unsecure_port needs to be of type int with range 49152 to 65535")
        if not ('allow_secure' in sdp_config or isinstance(sdp_config['allow_secure'], bool)):
            raise ValueError("allow_secure needs to be of type bool")
        elif not (isinstance(sdp_config['secure_port'], int) and (sdp_config['secure_port'] in range(49152, 65535))) if (('secure_port' in sdp_config) and (sdp_config['allow_secure'] == True)) else True:
            raise ValueError("secure_port needs to be of type int with range 49152 to 65535")
        elif (sdp_config['unsecure_port'] == sdp_config['secure_port']):
            raise ValueError("unsecure_port and secure_port can not be the same")
        else:
            payload = b""

            if sdp_config['allow_unsecure'] == True:
                payload += b'\x01'
                payload += sdp_config['unsecure_port'].to_bytes(2, "big")
            else:
                payload += b'\x00'

            if sdp_config['allow_secure'] == True:
                payload += b'\x01'
                payload += sdp_config['allow_secure'].to_bytes(2, "big")
            else:
                payload += b'\x00'

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_sdp_config, payload)

    def v2gEvseGetSdpConfig(self):
        """
        Returns the SDP server configuration
        """
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_get_sdp_config, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        code = self.payloadReaderReadInt(1)
        ret['code'] = code
        
        if code > b'\x00':

            allowUnsecure = self.payloadReaderReadInt(1)
            if allowUnsecure == 1:
                unsecurePort = self.payloadReaderReadInt(2)

            allowSecure = self.payloadReaderReadInt(1)
            if allowSecure == 1:
                securePort = self.payloadReaderReadInt(2)

            if allowUnsecure == 1:
                ret['allow_unsecure'] = True
                ret['unsecure_port'] = unsecurePort
            else:
                 ret['allow_unsecure'] = False

            if allowSecure == 1:
                ret['allow_secure'] = True
                ret['secure_port'] = securePort
            else:
                 ret['allow_secure'] = False

        return ret

    def v2gEvseStartListen(self):
        payload = b''
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_start_listen, payload)

    def v2gEvseSetAuthorizationStatus(self, status):
        if not isinstance(status, bool):
            raise ValueError('status needs to be of type bool')
        else:
            payload = b'\x00' if status == True else b'\x01'
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_authorization_status, payload)

    def v2gEvseSetSchedules(self, schedules):
        if not ('code' in schedules or isinstance(schedules['code'], int) or schedules['code'] in [0,1]):
            raise ValueError('code needs to be of type int and in range 0 to 1')
        elif not ('schedule_tuples' in schedules or isinstance(schedules['schedule_tuples'], list)):
            raise ValueError('schedule_tuples needs to be of type list')
        elif not isinstance(schedules['energy_to_be_delivered'], (int, tuple)) if 'energy_to_be_delivered' in schedules else False:
            raise ValueError('energy_to_be_delivered needs to be of type int or tuple')
        else:
            payload = b''

            payload += schedules['code'].to_bytes(1, 'big')
            payload += len(schedules['schedule_tuples']).to_bytes(1, 'big')

            for schedule_tuple in schedules['schedule_tuples']:
                if not ('schedule_tuple_id' in schedule_tuple or isinstance(schedule_tuple['schedule_tuple_id'], int) or (-32768 < schedule_tuple['schedule_tuple_id'] < 32768)):
                    raise ValueError('schedule_tuple_id needs to be of type int with range -32768 to 32768')
                elif not ('schedules' in schedule_tuple or isinstance(schedule_tuple['schedules'], list)):
                    raise ValueError('schedules needs to be of type list')
                else:

                    payload += schedule_tuple['schedule_tuple_id'].to_bytes(2, 'big')
                    payload += len(schedule_tuple['schedules']).to_bytes(2, 'big')

                    for schedule in schedule_tuple['schedules']:
                        if not ('start' in schedule or isinstance(schedule['start'], int) or (0 < schedule['start'] < 2**32)):
                            raise ValueError('start needs to be of type int with range 0 to {}'.format(2**32))
                        elif not ('interval' in schedule or isinstance(schedule['interval'], int) or (0 < schedule['interval'] < 2*32)):
                            raise ValueError('interval needs to be of type int with range 0 to {}'.format(2**32))
                        elif not ('power' in schedule or isinstance(schedule['power'], (int, tuple))):
                            raise ValueError('power needs to be of type tuple or int')
                        else:
                            payload += schedule['start'].to_bytes(4, 'big')
                            payload += schedule['interval'].to_bytes(4, 'big')
                            payload += self._valueToExponential(schedule['power'])

            if 'energy_to_be_delivered' in schedules:
                payload += b'\x01'
                payload += self._valueToExponential(schedules['energy_to_be_delivered'])
            else:
                payload += b'\x00'

            if 'sales_tariff_tuples' not in schedules or len(schedules['sales_tariff_tuples']) == 0:
                payload += b'\x00'
            else:
                if not (isinstance(schedules['sales_tariff_tuples'], list)):
                    raise ValueError('sales_tariff_tuples needs to be of type list')
                elif not ('signature_value' in schedules or isinstance(schedules['signature_value'], list) or len(schedules['signature_value']) == 64):
                    raise ValueError('signature_value needs to be of type list with length 64')

                payload += len(schedules['sales_tariff_tuples']).to_bytes(1, 'big')

                for sales_tariff in schedules['sales_tariff_tuples']:
                    if not ('sales_tariff_id' in sales_tariff or isinstance(sales_tariff['sales_tariff_id'], int) or (0 < sales_tariff['sales_tariff_id'] < 256)):
                        raise ValueError('schedule_tuple_id needs to be of type int with range -32768 to 32768')
                    elif not (isinstance(sales_tariff['sales_tariff_description'], str) or len(sales_tariff['sales_tariff_description']) <= 32) if 'sales_tariff_description' in sales_tariff else False:
                        raise ValueError('sales_tariff_description needs to be of type str with length <= 32')
                    elif not ('number_of_price_levels' in sales_tariff or isinstance(sales_tariff['number_of_price_levels'], int) or 0 <= sales_tariff['number_of_price_levels'] < 256):
                        raise ValueError('number_of_price_levels needs to be of type int with range 0 to 255')
                    elif not ('sales_tariff_entries' in sales_tariff or isinstance(sales_tariff['sales_tariff_entries'], list) or 1 <= len(sales_tariff['sales_tariff_entries']) <= 10):
                        raise ValueError('sales_tariff_entries needs to be of type list with length between 1 or 10')
                    elif not ('signature_id' in sales_tariff or isinstance(sales_tariff['signature_id'], str) or 1 <= len(sales_tariff['signature_id']) <= 254):
                        raise ValueError('signature_id needs to be of type str with length between 1 and 254')
                    elif not ('digest_value' in sales_tariff or isinstance(sales_tariff['digest_value'], list) or len(sales_tariff['digest_value']) == 32):
                        raise ValueError('digest_value needs to be of type list with length 32')
                    else:
                        payload += sales_tariff['sales_tariff_id'].to_bytes(1, 'big')
                        payload += len(sales_tariff['sales_tariff_description']).to_bytes(1, 'big')
                        payload += sales_tariff['sales_tariff_description'].encode('utf-8')
                        payload += sales_tariff['number_of_price_levels'].to_bytes(1, 'big')

                        payload += len(sales_tariff['sales_tariff_entries']).to_bytes(2, 'big')
                        for entry in sales_tariff['sales_tariff_entries']:
                            if not ('time_interval_start' in entry or isinstance(entry['time_interval_duration'], int) or (0 < entry['time_interval_duration'] < 16777214)):
                                raise ValueError('time_interval_start needs to be of type int with range 0 to 16777214')
                            elif not ('time_interval_duration' in entry or isinstance(entry['time_interval_duration'], int) or (0 < entry['time_interval_duration'] < 86400)):
                                raise ValueError('time_interval_duration needs to be of type int with range 0 to 86400')
                            elif not ('price_level' in schedule or isinstance(entry['price_level'], int) or (0 <= entry['price_level'] <= 255)):
                                raise ValueError('price_level needs to be of type int with range 0 to 255')
                            elif not ('consumption_costs' in schedule or isinstance(entry['consumption_costs'], list) or (1 <= len(entry['consumption_costs']) <= 3)):
                                raise ValueError('consumption_costs needs to be of type list with length between 1 and 3')
                            else:

                                payload += entry['time_interval_start'].to_bytes(4, 'big')
                                payload += entry['time_interval_duration'].to_bytes(4, 'big')
                                payload += entry['price_level'].to_bytes(1, 'big')
                                
                                payload += len(entry['consumption_costs']).to_bytes(1, 'big')
                                for consumption in entry['consumption_costs']:
                                    if not ('start_value' in consumption or isinstance(consumption['start_value'], (int, tuple))):
                                        raise ValueError('start_value needs to be of type int or tuple')
                                    elif not ('costs' in consumption or isinstance(consumption['costs'], list) or (1 <= len(consumption['costs']) <= 3)):
                                        raise ValueError('costs needs to be of type list with length between 1 and 3')
                                    else:
                                
                                        payload += self._valueToExponential(consumption['start_value'])
                                        
                                        payload += len(consumption['costs']).to_bytes(1, 'big')
                                        for cost in consumption['costs']:
                                            if not ('kind' in cost or isinstance(cost['kind'], int) or cost['kind'] in [0,1,2]):
                                                raise ValueError('kind needs to be of type int with range 0 to 2')
                                            elif not ('amount' in cost or isinstance(cost['amount'], int) or 0 <= cost['amount'] < 2**32):
                                                raise ValueError('amount needs to be of type int with range 0 to {}'.format(2**32))
                                            elif not ('amount_multiplier' in cost or isinstance(cost['amount_multiplier'], int) or cost['amount_multiplier'] in range(-3, 4)):
                                                raise ValueError('amount_multiplier needs to be of type int with range -3 to 3')
                                            else:
                                                
                                                payload += cost['kind'].to_bytes(1, 'big')
                                                payload += cost['amount'].to_bytes(4, 'big')
                                                payload += cost['amount_multiplier'].to_bytes(1, 'big')

                        payload += len(sales_tariff['signature_id']).to_bytes(1, 'big')
                        payload += sales_tariff['signature_id'].encode('utf-8')
                        
                        payload += len(sales_tariff['digest_value']).to_bytes(1, 'big')
                        for val in sales_tariff['digest_value']:
                            payload += val.to_bytes(1, 'big')

                payload += len(schedules['signature_value']).to_bytes(1, 'big')
                for val in schedules['signature_value']:
                    payload += val.to_bytes(1, 'big')

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_schedules, payload)

    def v2gEvseSetCableCheckFinished(self, code):
        if not (isinstance(code, bool)):
            raise ValueError('code needs to be of type bool')
        else:
            payload = b'\x00' if code == True else b'\x01'
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_cable_check_finished, payload)

    def v2gEvseStartCharging(self):
        payload = b''
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_start_charging, payload)

    def v2gEvseStopCharging(self):
        payload = b''
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_stop_charging, payload)

    def v2gEvseStopListen(self):
        payload = b''
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_stop_listen, payload)

    def v2gEvseSetCertificateInstallationAndUpdateResponse(self, response):
        if not ('status' in response or isinstance(response['status'], int) or response['status'] in [0,1,2]):
            raise ValueError('status needs to be of type int with range 0 to 2')
        elif not ('exi_response' in response or isinstance(response['exi_response'], list) or len(response['exi_response']) <= 6000):
            raise ValueError('exi_response needs to be of type list with length <= 6000')
        else:
            payload = b''
            payload += response['status'].to_bytes(1, 'big')
            payload += response['exi_response'].to_bytes(len(response['exi_response']), 'big')
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_cable_certificate_installation_and_update_response, payload)

    def v2gEvseSetMeterReceiptRequest(self, receipt):
        if not ('meter_id' in receipt or isinstance(receipt['meter_id'], str) or len(receipt['meter_id']) < 33):
            raise ValueError('meter_id needs to be of type str with length <= 32')
        elif not (isinstance(receipt['meter_reading'], int) or (0 < receipt['meter_reading'] < 2**64)) if 'meter_reading' in receipt else False:
            raise ValueError('meter_reading needs to be of type int with range 0 to {}'.format(2**64))
        elif not (isinstance(receipt['meter_reading_signature'], list) or len(receipt['meter_reading_signature']) <= 64) if 'meter_reading_signature' in receipt else False:
            raise ValueError('meter_reading_signature needs to be of type list with length <= 64')
        elif not (isinstance(receipt['meter_status'], int) or (0 < receipt['meter_status'] < 2**16)) if 'meter_status' in receipt else False:
            raise ValueError('meter_status needs to be of type list with length <= {}'.format(2**16))
        elif not (isinstance(receipt['meter_timestamp'], int) or (0 < receipt['meter_timestamp'] < 2**64)) if 'meter_timestamp' in receipt else False:
            raise ValueError('meter_timestamp needs to be of type list with length <= {}'.format(2**64))
        else:
            payload = b''
            payload += receipt['meter_id'].encode('utf-8')
            
            if 'meter_reading' in receipt:
                payload += b'\x01'
                payload += receipt['meter_reading'].to_bytes(8, 'big')
            else:
                payload += b'\x00'

            if 'meter_reading_signature' in receipt:
                payload += len(receipt['meter_reading_signature'])
                for val in receipt['meter_reading_signature']:
                    payload += val.to_bytes(1, 'big')
            else:
                payload += b'\x00'
            
            if 'meter_status' in receipt:
                payload += len(receipt['meter_status'])
                for val in receipt['meter_status']:
                    payload += val.to_bytes(2, 'big')
            else:
                payload += b'\x00'

            if 'meter_timestamp' in receipt:
                payload += b'\x01'
                payload += receipt['meter_timestamp'].to_bytes(8, 'big')
            else:
                payload += b'\x00'

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_meter_receipt, payload)

    def v2gEvseSendNotification(self, renegotiation, timeout):
        payload = struct.pack("!?", renegotiation)
        payload += struct.pack("!H", timeout)
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_send_notification, payload)

    def v2gEvseSetSessionParameterTimeout(self, timeoutMs):
        payload = struct.pack("!H", timeoutMs)
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_evse_set_session_parameter_timeout, payload)

    def v2gEvseParseSessionStarted(self, data):
        """
        Parse a session started message.
        Will return a dictionary with the following keys:
        protocol    int
        session_id  bytes
        evcc_id     bytes
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['protocol'] = self.payloadReaderReadInt(1)
        message['session_id'] = self.payloadReaderReadBytes(8)
        message['evcc_id'] = self.payloadReaderReadBytes(self.payloadReaderReadInt(1))
        self.payloadReaderFinalize()
        return message

    def v2gEvseParsePaymentSelected(self, data):
        """
        Parse a payment selected message.
        Will return a dictionary with the following keys:
        selected_payment_method     int
        contract_certificate        bytes[0-800]
        mo_sub_ca1                  bytes[0-800]
        mo_sub_ca2                  bytes[0-800]
        emaid                       string
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['selected_payment_method'] = self.payloadReaderReadInt(1)
        if message['selected_payment_method'] == 1:
            message['contract_certificate'] = self.payloadReaderReadBytes(self.payloadReaderReadInt(1))
            message['mo_sub_ca1'] = self.payloadReaderReadBytes(self.payloadReaderReadInt(1))
            message['mo_sub_ca2'] = self.payloadReaderReadBytes(self.payloadReaderReadInt(1))
            message['emaid'] = self.payloadReaderReadBytes(self.payloadReaderReadInt(1)).decode('utf-8')
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseAuthorizationStatusRequested(self, data):
        """
        Parse a authorization status requested message.
        Will return a dictionary with the following keys:
        timeout    int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseSessionStopped(self, data):
        """
        Parse a session stopped message.
        Will return an empty dictionary.
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseRequestEvseId(self, data):
        """
        Parse a session stopped message.
        Will return a dictionary with the following keys:
        timeout    int
        format     int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['format'] = self.payloadReaderReadInt(1)
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseEnergyTransferModeSelected(self, data):
        """
        Parse a energy transfer mode selected message.
        Will return a dictionary with the following keys:
        departure_time                  int (optional)
        energy_request                  int or float (optional)
        max_voltage                     int or float
        min_current                     int or float (optional)
        max_current                     int or float
        max_power                       int or float (optional)
        selected_energy_transfer_mode   int or float (optional)
        energy_capacity                 int or float
        full_soc                        int (optional)
        bulk_soc                        int (optional)
        ready                           bool
        error_code                      int
        soc                             int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))

        if self.payloadReaderReadInt(1) == 1:
            message['departure_time'] = self.payloadReaderReadInt(4)

        if self.payloadReaderReadInt(1) == 1:
            message['energy_request'] = self.payloadReaderReadExponential()

        message['max_voltage'] = self.payloadReaderReadExponential()

        if self.payloadReaderReadInt(1) == 1:
            message['min_current'] = self.payloadReaderReadExponential()

        message['max_current'] = self.payloadReaderReadExponential()

        if self.payloadReaderReadInt(1) == 1:
            message['max_power'] = self.payloadReaderReadExponential()

        message['selected_energy_transfer_mode'] = self.payloadReaderReadInt(1)
        message['energy_capacity'] = self.payloadReaderReadExponential()

        if self.payloadReaderReadInt(1) == 1:
            message['full_soc'] = self.payloadReaderReadInt(1)

        if self.payloadReaderReadInt(1) == 1:   
            message['bulk_soc'] = self.payloadReaderReadInt(1)

        message['ready'] = True if self.payloadReaderReadInt(1) == 1 else False
        message['error_code'] = self.payloadReaderReadInt(1)
        message['soc'] = self.payloadReaderReadInt(1)

        self.payloadReaderFinalize()
        return message

    def v2gEvseParseSchedulesRequested(self, data):
        """
        Parse a request schedules message.
        Will return a dictionary with the following keys:
        timeout        int
        max_entries    int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['max_entries'] = self.payloadReaderReadInt(2)
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseDCChargeParametersChanged(self, data):
        """
        Parse a dc charge parameteres changed message.
        Will return a dictionary with the following keys:
        max_voltage                     int or float
        max_current                     int or float
        max_power                       int or float
        ready                           bool
        error_code                      int
        soc                             int
        target_voltage                  int or float (optional)
        target_current                  int or float (optional)
        full_soc                        int (optional)
        bulk_soc                        int (optional)
        charging_complete               bool (optional)
        bulk_charging_complete          bool (optional)
        remaining_time_to_full_soc      int or float (optional)
        remaining_time_to_bulk_soc      int or float (optional)
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['max_voltage'] = self.payloadReaderReadExponential()
        message['max_current'] = self.payloadReaderReadExponential()

        if self.payloadReaderReadInt(1) == 1:
            message['max_power'] = self.payloadReaderReadExponential()

        message['ready'] = True if self.payloadReaderReadInt(1) == 1 else False
        message['error_code'] = self.payloadReaderReadInt(1)
        message['soc'] = self.payloadReaderReadInt(1)
        
        message['target_voltage'] = self.payloadReaderReadExponential()
        message['target_current'] = self.payloadReaderReadExponential()
        
        if self.payloadReaderReadInt(1) == 1:
            message['full_soc'] = self.payloadReaderReadInt(1)
        
        if self.payloadReaderReadInt(1) == 1:
            message['bulk_soc'] = self.payloadReaderReadInt(1)

        message['charging_complete'] = self.payloadReaderReadInt(1)

        if self.payloadReaderReadInt(1) == 1:
            message['bulk_charging_complete'] = True if self.payloadReaderReadInt(1) == 1 else False
        
        if self.payloadReaderReadInt(1) == 1:
            message['remaining_time_to_full_soc'] = self.payloadReaderReadExponential()

        if self.payloadReaderReadInt(1) == 1:
            message['remaining_time_to_bulk_soc'] = self.payloadReaderReadExponential()

        self.payloadReaderFinalize()
        return message

    def v2gEvseParseACChargeParametersChanged(self, data):
        """
        Parse a dc charge parameteres changed message.
        Will return a dictionary with the following keys:
        max_voltage                  int or float
        min_current                  int or float
        max_current                  int or float
        energy_amount                int or float
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        
        message['max_voltage'] = self.payloadReaderReadExponential()
        message['min_current'] = self.payloadReaderReadExponential()
        message['max_current'] = self.payloadReaderReadExponential()
        message['energy_amount'] = self.payloadReaderReadExponential()

        self.payloadReaderFinalize()
        return message

    def v2gEvseParseCableCheckRequested(self, data):
        """
        Parse a request cable check status message.
        Will return a dictionary with the following keys:
        timeout        int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        self.payloadReaderFinalize()
        return message

    def v2gEvseParsePreChargeStarted(self, data):
        """
        nothing to do
        """
        pass

    def v2gEvseParseStartChargingRequested(self, data):
        """
        Parse a start charging requested message.
        Will return a dictionary with the following keys:
        timeout             int
        schedule_tuple_id   int
        charging_profiles   list
        
        The dict entries fo the list charging_profiles have the following entries:
        start        int
        power        int or float
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['schedule_tuple_id'] = self.payloadReaderReadInt(2)

        message['charging_profiles'] = []
        for i in range(self.payloadReaderReadInt(1)):
            start = self.payloadReaderReadInt(4)
            power = self.payloadReaderReadExponential()
            message['charging_profiles'].append({'start': start, 'power': power})

        self.payloadReaderFinalize()
        return message

    def v2gEvseParseStopChargingRequested(self, data):
        """
        Parse a stop charging requested message.
        Will return a dictionary with the following keys:
        timeout             int
        renegotiation      bool
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['renegotiation'] = True if self.payloadReaderReadInt(1) == 1 else False

        self.payloadReaderFinalize()
        return message

    def v2gEvseParseWeldingDetectionStarted(self, data):
        """
        nothing to do
        """
        pass

    def v2gEvseParseSessionStopped(self, data):
        """
        Parse a session stopped message.
        Will return a dictionary with the following keys:
        closure_type    int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['closure_type'] = self.payloadReaderReadInt(1)

        self.payloadReaderFinalize()
        return message

    def v2gEvseParseSessionError(self, data):
        """
        Parse a session error message.
        Will return a dictionary with the following keys:
        error_code  int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['error_code'] = self.payloadReaderReadInt(1)

        self.payloadReaderFinalize()
        return message

    def v2gEvseParseCertificateInstallationRequested(self, data):
        """
        Parse a session error message.
        Will return a dictionary with the following keys:
        timeout     int
        exi_request list
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(1)
        message['exi_request'] = self.payloadReaderReadBytes(self.payloadReaderReadInt(2))

        self.payloadReaderFinalize()
        return message

    def v2gEvseParseCertificateUpdateRequested(self, data):
        """
        Parse a session error message.
        Will return a dictionary with the following keys:
        timeout     int
        exi_request list
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(1)
        message['exi_request'] = self.payloadReaderReadBytes(self.payloadReaderReadInt(2))

        self.payloadReaderFinalize()
        return message

    def v2gEvseParseMeteringReceiptStatus(self, data):
        """
        Parse a metering receipt status message.
        Will return a dictionary with the following keys:
        status  bool
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['status'] = True if self.payloadReaderReadInt(1) == 1 else False

        self.payloadReaderFinalize()
        return message

    def v2gEvseReceiveRequest(self):
        """
        Receives a V2G request status message.
        """
        sub_id_list = []
        sub_id_list.append(0x80)
        sub_id_list.append(0x81)
        sub_id_list.append(0x82)
        sub_id_list.append(0x83)
        sub_id_list.append(0x84)
        sub_id_list.append(0x85)
        sub_id_list.append(0x86)
        sub_id_list.append(0x87)
        sub_id_list.append(0x88)
        sub_id_list.append(0x89)
        sub_id_list.append(0x8A)
        sub_id_list.append(0x8B)
        sub_id_list.append(0x8C)
        sub_id_list.append(0x8E)
        sub_id_list.append(0x8F)
        sub_id_list.append(0x90)
        sub_id_list.append(0x91)
        response = self._receive(self.v2g_mod_id, sub_id_list, [0x00, 0xFF], 30)
        return response.sub_id, response.payload

    def v2gEvseReceiveRequestSilent(self):
        """
        Receives a V2G request status message.
        """
        sub_id_list = []
        sub_id_list.append(0x80)
        sub_id_list.append(0x81)
        sub_id_list.append(0x82)
        sub_id_list.append(0x83)
        sub_id_list.append(0x84)
        sub_id_list.append(0x85)
        sub_id_list.append(0x86)
        sub_id_list.append(0x87)
        sub_id_list.append(0x88)
        sub_id_list.append(0x89)
        sub_id_list.append(0x8A)
        sub_id_list.append(0x8B)
        sub_id_list.append(0x8C)
        sub_id_list.append(0x8E)
        sub_id_list.append(0x8F)
        sub_id_list.append(0x90)
        sub_id_list.append(0x91)
        response = self._receiveSilent(self.v2g_mod_id, sub_id_list, [0x00, 0xFF], 0.1)
        if response is not None:
            return response.sub_id, response.payload
        else:
            return None, None

    def v2gEvReceiveRequest(self):
        """
        Receives a V2G request status message.
        """
        sub_id_list = []
        sub_id_list.append(0xC0)
        sub_id_list.append(0xC1)
        sub_id_list.append(0xC2)
        sub_id_list.append(0xC3)
        sub_id_list.append(0xC4)
        sub_id_list.append(0xC5)
        sub_id_list.append(0xC6)
        sub_id_list.append(0xC7)
        sub_id_list.append(0xC8)
        sub_id_list.append(0xC9)
        sub_id_list.append(0xCA)
        sub_id_list.append(0xCB)
        sub_id_list.append(0xCC)
        sub_id_list.append(0xCD)
        response = self._receive(self.v2g_mod_id, sub_id_list, [0x00, 0xFF], 1)
        return response.sub_id, response.payload
