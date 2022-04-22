from multiprocessing import Value
import time
import struct
from Logger import *
from FramingInterface import *

class Whitebeet():

    def __init__(self, iface, mac):
        self.logger = Logger()

        self.connectionError = False
        self.payloadBytes = bytes()
        self.payloadBytesRead = 0
        self.payloadBytesLen = 0

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
        self.v2g_sub_set_configuration = 0xA0
        self.v2g_sub_get_configuration = 0xA1
        self.v2g_sub_set_dc_charging_parameters = 0xA2
        self.v2g_sub_update_dc_charging_parameters = 0xA3
        self.v2g_sub_get_dc_charging_parameters = 0xA4
        self.v2g_sub_set_ac_charging_parameters = 0xA5
        self.v2g_sub_update_ac_charging_parameters = 0xA6
        self.v2g_sub_get_ac_charging_parameters = 0xA7
        self.v2g_sub_set_charging_profile = 0xA8
        self.v2g_sub_start_session = 0xA9
        self.v2g_sub_start_cable_check = 0xAA
        self.v2g_sub_start_pre_charging = 0xAB
        self.v2g_sub_start_charging = 0xAC
        self.v2g_sub_stop_charging = 0xAD
        self.v2g_sub_stop_session = 0xAE
        

        # EVSE sub IDs
        self.v2g_sub_set_supported_protocols = 0x60
        self.v2g_sub_get_supported_protocols = 0x61
        self.v2g_sub_set_sdp_config = 0x62
        self.v2g_sub_get_sdp_config = 0x63
        self.v2g_sub_set_payment_options = 0x64
        self.v2g_sub_get_payment_options = 0x65
        self.v2g_sub_set_energy_transfer_modes = 0x66
        self.v2g_sub_get_energy_transfer_modes = 0x67
        self.v2g_sub_set_evseid = 0x68
        self.v2g_sub_set_authorization_status = 0x69
        self.v2g_sub_set_discovery_charge_params = 0x6A
        self.v2g_sub_set_schedules = 0x6B
        self.v2g_sub_set_cable_check_status = 0x6C
        self.v2g_sub_set_cable_check_params = 0x6D
        self.v2g_sub_set_pre_charge_params = 0x6E
        self.v2g_sub_set_start_charging_status = 0x6F
        self.v2g_sub_set_charge_loop_params = 0x70
        self.v2g_sub_set_stop_charging_status = 0x71
        self.v2g_sub_set_post_charge_params = 0x72

        # Initialization of the framing interface
        self.framing = FramingInterface()
        self.framing.sut_mac = mac
        self.framing.sut_interface = iface

        try:
            self.framing.initialize_framing()
            log("iface: {}, mac: {}".format(iface, mac))
            self.framing.clear_backlog()
            self.v2gStop()
            self.slacStop()
            self.controlPilotStop()
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
                self.v2gStop()
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
            #print(str(base) + "e" + str(exponent))
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
    def v2gSetConfiguration(self, config):
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
            
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_configuration, payload)

    def v2gGetConfiguration(self):
        """
        Get the configuration of EV mdoe
        Returns dictionary
        """
        
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_get_configuration, None)
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
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_dc_charging_parameters, payload)

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

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_update_dc_charging_parameters, payload)

    def v2gGetDCChargingParameters(self, data):
        """
        Gets the DC charging parameters
        Returns dictionary
        """
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_get_dc_charging_parameters, None)
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
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_ac_charging_parameters, payload)

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

            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_update_ac_charging_parameters, payload)

    def v2gACGetChargingParameters(self, data):
        """
        Gets the AC charging parameters
        Returns dictionary
        """
        ret = {}
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_get_dc_charging_parameters, None)
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
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_charging_profile, payload)

    def v2gStartSession(self):
        """
        Starts a new charging session
        """        
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_start_session, None)

    def v2gStartCableCheck(self):
        """
        Starts the cable check after notification Cable Check Ready has been reveived
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_start_cable_check, None)

    def v2gStartPreCharging(self):
        """
        Starts the pre charging after notification Pre Charging Ready has been reveived
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_start_pre_charging, None)

    def v2gStartCharging(self):
        """
        Starts the  charging after notification Charging Ready has been reveived
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_start_charging, None)

    def v2gStopCharging(self, renegotiation):
        """
        Stops the charging
        """
        if not isinstance(renegotiation, bool):
            raise ValueError("Parameter renegotiation has to be of type bool")
        else:
            payload = b""
            payload += renegotiation.to_bytes(1, "big")
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_stop_charging, payload)

    def v2gStopSession(self):
        """
        Stops the currently active charging session after the notification Post Charging Ready has been received.
        When Charging in AC mode the session is stopped auotamically because no post charging needs to be performed.
        """
        self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_stop_session, None)
    
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

    def v2gSetSupportedProtocols(self, prot_list):
        """
        Sets the supported protocols
        0: DIN70121-2:2012, 2: ISO15118-2:2014
        """
        prot_allowed = [0, 2]
        if not isinstance(prot_list, list):
            raise ValueError("Protocol list needs to be of type list")
        elif len(prot_list) == 0:
            raise ValueError("Protocol list is empty")
        elif len(prot_list) != len(set(prot_list)):
            raise ValueError("Protocol list needs to have unique values")
        elif any(i not in prot_allowed for i in prot_list):
            raise ValueError("Element in protocol list {} not in valid range {}".format(prot_list, prot_allowed))
        else:
            payload = len(prot_list).to_bytes(1, "big")
            for prot in prot_list:
                payload += prot.to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_supported_protocols, payload)

    def v2gGetSupportedProtocols(self):
        """
        Returns the list of supported protocols.
        0: DIN70121-2:2012, 2: ISO15118-2:2014
        """
        prot_list = []
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_get_supported_protocols, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        self.payloadReaderReadInt(1)
        for i in range(self.payloadReaderReadInt(1)):
            prot_list.append(self.payloadReaderReadInt(1))
        self.payloadReaderFinalize()
        return prot_list

    def v2gSetSdpConfig(self, unsecure_port, secure_port):
        """
        Configures the SDP server
        """
        if unsecure_port is not None and not isinstance(unsecure_port, int):
            raise ValueError("Parameter unsecure port needs to be of type int")
        elif unsecure_port is None:
            raise ValueError("Parameter unsecure port cannot be None")
        elif secure_port is not None and not isinstance(secure_port, int):
            raise ValueError("Parameter unsecure port needs to be of type int")
        elif unsecure_port is not None and unsecure_port not in range(49152, 65535):
            raise ValueError("Parameter unsecure port needs to be between 49152 and 65535")
        elif secure_port is not None and secure_port not in range(49152, 65535):
            raise ValueError("Parameter unsecure port needs to be between 49152 and 65535")
        elif unsecure_port is None and secure_port is None:
            raise ValueError("At least one of the parameters unsecure port and secure port net to be set")
        elif unsecure_port is not None and secure_port is not None and unsecure_port == secure_port:
            raise ValueError("Parameter unsecure port and secure port cannot be the same")
        else:
            payload = b""
            if unsecure_port is not None:
                payload += b"\x01"
                payload += unsecure_port.to_bytes(2, "big")
            else:
                payload += b"\x00"
            if secure_port is not None:
                payload += b"\x01"
                payload += secure_port.to_bytes(2, "big")
            else:
                payload += b"\x00"
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_sdp_config, payload)

    def v2gGetSdpConfig(self):
        """
        Returns the SDP server configuration
        """
        unsecure_port = None
        secure_port = None
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_get_sdp_config, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        self.payloadReaderReadInt(1)
        if self.payloadReaderReadInt(1) != 0:
            unsecure_port = self.payloadReaderReadInt(2)
        if self.payloadReaderReadInt(1) != 0:
            secure_port = self.payloadReaderReadInt(2)
        self.payloadReaderFinalize()
        return unsecure_port, secure_port

    def v2gSetPaymentOptions(self, payment_list):
        """
        Sets the supported payment options.
        0: External payment, 1: Contract payment
        """
        payment_allowed = [0, 1]
        if not isinstance(payment_list, list):
            raise ValueError("Payment option list needs to be of type list")
        elif len(payment_list) != len(set(payment_list)):
            raise ValueError("Payment option list needs to have unique values")
        elif any(i not in payment_allowed for i in payment_list):
            raise ValueError("Element in Payment option list {} not in valid range {}".format(payment_list, payment_allowed))
        else:
            payload = b""
            if len(payment_list) == 0:
                payload += b"\x00"
            else:
                payload += b"\x01"
                payload += len(payment_list).to_bytes(1, "big")
                for prot in payment_list:
                    payload += prot.to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_payment_options, payload)

    def v2gGetPaymentOptions(self):
        """
        Returns the list of supported payment options.
        0: External payment, 1: Contract payment
        """
        payment_list = []
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_get_payment_options, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        self.payloadReaderReadInt(1)
        if self.payloadReaderReadInt(1) != 0:
            for i in range(self.payloadReaderReadInt(1)):
                payment_list.append(self.payloadReaderReadInt(1))
        self.payloadReaderFinalize()
        return payment_list

    def v2gSetEnergyTransferModes(self, modes_list):
        """
        Sets the supported energy transfer modes.
        0: DC core, 1: DC extended 2: DC combo core 3: DC unique 4: AC single phase, 5: AC three phase
        """
        modes_allowed = [0, 1, 2, 3, 4, 5]
        if not isinstance(modes_list, list):
            raise ValueError("Protocol list needs to be of type list")
        elif len(modes_list) == 0:
            raise ValueError("Protocol list is empty")
        elif len(modes_list) != len(set(modes_list)):
            raise ValueError("Protocol list needs to have unique values")
        elif any(i not in modes_allowed for i in modes_list):
            raise ValueError("Element in protocol list {} not in valid range {}".format(modes_list, modes_allowed))
        else:
            payload = len(modes_list).to_bytes(1, "big")
            for prot in modes_list:
                payload += prot.to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_energy_transfer_modes, payload)

    def v2gGetEnergyTransferModes(self):
        """
        Returns the list of supported energy transfer modes.
        0: DC core, 1: DC extended 2: DC combo core 3: DC unique 4: AC single phase, 5: AC three phase
        """
        modes_list = []
        response = self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_get_energy_transfer_modes, None)
        self.payloadReaderInitialize(response.payload, response.payload_len)
        self.payloadReaderReadInt(1)
        for i in range(self.payloadReaderReadInt(1)):
            modes_list.append(self.payloadReaderReadInt(1))
        self.payloadReaderFinalize()
        return modes_list

    def v2gSetEvseId(self, evseid):
        """
        Sets the requested EVSEID
        """
        if evseid is not None and isinstance(evseid, str) == False:
            raise ValueError("Parameter EVSEID needs to be from type str")
        elif evseid is not None and len(evseid) > 38:
            raise ValueError("Parameter EVSEID has a maximum length of 38")
        else:
            if evseid is None or (evseid is not None and len(evseid) == 0):
                payload = b"\x01"
            else:
                payload = b"\x00" + len(evseid).to_bytes(1, "big") + bytes(evseid, 'ascii')
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_evseid, payload)

    def v2gSetAuthorizationStatus(self, authorized):
        """
        Sets the status of the authorization.
        True: succeeded, False: failed
        """
        if isinstance(authorized, bool) == False:
            raise ValueError("Parameter authorized needs to be of type bool")
        else:
            payload = b""
            if authorized:
                payload += b"\x00"
            else:
                payload += b"\x01"
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_authorization_status, payload)

    def v2gSetDcDiscoveryChargeParameters(self, code, isolation_level, max_current, min_current, max_voltage, min_voltage, max_power, current_regulation_tolerance, peak_current_ripple, energy_to_be_delivered):
        """
        Sets the discovery charge parameters.
        If code is set to 1 or 2, all other parameters can be set to None
        """
        codes_allowed = [0, 1, 2]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if isinstance(isolation_level, int) == False:
                    raise ValueError("Parameter isolation level needs to be of type int")
                elif isolation_level not in range(0, 5):
                    raise ValueError("Parameter isolation level invalid value: {}".format(isolation_level))
                elif not isinstance(max_current, int) and not (isinstance(max_current, tuple) and len(max_current) == 2):
                    raise ValueError("Parameter max current needs to be of type int or tuple with length 2")
                elif not isinstance(min_current, int) and not (isinstance(min_current, tuple) and len(min_current) == 2):
                    raise ValueError("Parameter min current needs to be of type int or tuple with length 2")
                elif not isinstance(max_voltage, int) and not (isinstance(max_voltage, tuple) and len(max_voltage) == 2):
                    raise ValueError("Parameter max voltage needs to be of type int or tuple with length 2")
                elif not isinstance(min_voltage, int) and not (isinstance(min_voltage, tuple) and len(min_voltage) == 2):
                    raise ValueError("Parameter min voltage needs to be of type int or tuple with length 2")
                elif not isinstance(max_power, int) and not (isinstance(max_power, tuple) and len(max_power) == 2):
                    raise ValueError("Parameter max power needs to be of type int or tuple with length 2")
                elif current_regulation_tolerance is not None and not isinstance(current_regulation_tolerance, int) and not (isinstance(current_regulation_tolerance, tuple) and len(current_regulation_tolerance) == 2):
                    raise ValueError("Parameter current regulation tolerance needs to be of type int or tuple with length 2")
                elif not isinstance(peak_current_ripple, int) and not (isinstance(peak_current_ripple, tuple) and len(peak_current_ripple) == 2):
                    raise ValueError("Parameter peak current ripple needs to be of type int or tuple with length 2")
                elif energy_to_be_delivered is not None and not isinstance(energy_to_be_delivered, int) and not (isinstance(energy_to_be_delivered, tuple) and len(energy_to_be_delivered) == 2):
                    raise ValueError("Parameter energy to be delivered needs to be of type int or tuple with length 2")
                else:
                    payload += b"\x00"
                    payload += isolation_level.to_bytes(1, "big")
                    if isinstance(max_current, int):
                        payload += max_current.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += max_current[0].to_bytes(2, "big")
                        payload += max_current[1].to_bytes(1, "big")
                    if isinstance(min_current, int):
                        payload += min_current.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += min_current[0].to_bytes(2, "big")
                        payload += min_current[1].to_bytes(1, "big")
                    if isinstance(max_voltage, int):
                        payload += max_voltage.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += max_voltage[0].to_bytes(2, "big")
                        payload += max_voltage[1].to_bytes(1, "big")
                    if isinstance(min_voltage, int):
                        payload += min_voltage.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += min_voltage[0].to_bytes(2, "big")
                        payload += min_voltage[1].to_bytes(1, "big")
                    if isinstance(max_power, int):
                        payload += max_power.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += max_power[0].to_bytes(2, "big")
                        payload += max_power[1].to_bytes(1, "big")
                    if current_regulation_tolerance is not None:
                        payload += b"\x01"
                        if isinstance(current_regulation_tolerance, int):
                            payload += current_regulation_tolerance.to_bytes(2, "big")
                            payload += b"\x00"
                        else:
                            payload += current_regulation_tolerance[0].to_bytes(2, "big")
                            payload += current_regulation_tolerance[1].to_bytes(1, "big")
                    else:
                        payload += b"\x00"
                    if isinstance(peak_current_ripple, int):
                        payload += peak_current_ripple.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += peak_current_ripple[0].to_bytes(2, "big")
                        payload += peak_current_ripple[1].to_bytes(1, "big")
                    if energy_to_be_delivered is not None:
                        payload += b"\x01"
                        if isinstance(energy_to_be_delivered, int):
                            payload += energy_to_be_delivered.to_bytes(2, "big")
                            payload += b"\x00"
                        else:
                            payload += energy_to_be_delivered[0].to_bytes(2, "big")
                            payload += energy_to_be_delivered[1].to_bytes(1, "big")
                    else:
                        payload += b"\x00"
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_discovery_charge_params, payload)

    def v2gSetAcDiscoveryChargeParameters(self, code, rcd_status, nominal_voltage, max_current):
        """
        Sets the discovery charge parameters.
        If code is set to 1 or 2, all other parameters can be set to None
        """
        codes_allowed = [0, 1, 2]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if isinstance(rcd_status, boolean) == False:
                    raise ValueError("Parameter RCD status needs to be of type boolean")
                elif not isinstance(nominal_voltage, int) and not (isinstance(nominal_voltage, tuple) and len(nominal_voltage) == 2):
                    raise ValueError("Parameter nominal voltage needs to be of type int or tuple with length 2")
                elif not isinstance(max_current, int) and not (isinstance(max_current, tuple) and len(max_current) == 2):
                    raise ValueError("Parameter max current needs to be of type int or tuple with length 2")
                else:
                    payload += b"\x01"
                    if rcd_status:
                        payload += b"\x01"
                    else:
                        payload += b"\x00"
                    if isinstance(nominal_voltage, int):
                        payload += nominal_voltage.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += nominal_voltage[0].to_bytes(2, "big")
                        payload += nominal_voltage[1].to_bytes(1, "big")
                    if isinstance(max_current, int):
                        payload += max_current.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += max_current[0].to_bytes(2, "big")
                        payload += max_current[1].to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_discovery_charge_params, payload)

    def v2gSetSchedules(self, code, schedule):
        """
        Sets the discovery charge parameters.
        If code is set to 1, all other parameters can be set to None
        """
        codes_allowed = [0, 1]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        elif isinstance(schedule, list) == False:
            raise ValueError("Parameter schedule needs to be of type list")
        else:
            # Check for correct schedule format
            for schedule_tuple in schedule:
                if "id" not in schedule_tuple:
                    raise ValueError("Schedule tuple needs to have key 'id'")
                if "tuple" not in schedule_tuple:
                    raise ValueError("Schedule tuple needs to have key 'tuple'")
                for entry in schedule_tuple["tuple"]:
                    if "start" not in entry:
                        raise ValueError("Schedule tuple entry needs to have key 'start'")
                    if "interval" not in entry:
                        raise ValueError("Schedule tuple entry needs to have key 'interval'")
                    if "max_power" not in entry:
                        raise ValueError("Schedule tuple entry needs to have key 'max_power'")
            # Prepare the schedule message
            payload = code.to_bytes(1, "big")
            if code == 0:
                payload += len(schedule).to_bytes(1, "big")
                for schedule_tuple in schedule:
                    payload += schedule_tuple["id"].to_bytes(2, "big")
                    payload += len(schedule_tuple["tuple"]).to_bytes(2, "big")
                    for entry in schedule_tuple["tuple"]:
                        payload += entry["start"].to_bytes(4, "big")
                        payload += entry["interval"].to_bytes(4, "big")
                        if isinstance(entry["max_power"], int):
                            payload += entry["max_power"].to_bytes(2, "big")
                            payload += b"\x00"
                        else:
                            payload += entry["max_power"][0].to_bytes(2, "big")
                            payload += entry["max_power"][1].to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_schedules, payload)

    def v2gSetDcCableCheckStatus(self, status):
        """
        Sets the status of the cable check.
        True: succeeded, False: failed
        """
        if isinstance(status, bool) == False:
            raise ValueError("Parameter status needs to be of type bool")
        else:
            payload = b""
            if status:
                payload += b"\x00"
            else:
                payload += b"\x01"
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_cable_check_status, payload)

    def v2gSetDcCableCheckParameters(self, code, isolation_level):
        """
        Sets the cable check parameters.
        If code is set to 1 or 2, all other parameters can be set to None
        """
        codes_allowed = [0, 1, 2]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if isinstance(isolation_level, int) == False:
                    raise ValueError("Parameter isolation level needs to be of type int")
                elif isolation_level not in range(0, 5):
                    raise ValueError("Parameter isolation level invalid value: {}".format(isolation_level))
                else:
                    payload += b"\x00"
                    payload += isolation_level.to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_cable_check_params, payload)

    def v2gSetDcPreChargeParameters(self, code, isolation_level, present_voltage):
        """
        Sets the pre charge parameters.
        If code is set to 1 or 2, all other parameters can be set to None
        """
        codes_allowed = [0, 1, 2]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if isinstance(isolation_level, int) == False:
                    raise ValueError("Parameter isolation level needs to be of type int")
                elif isolation_level not in range(0, 5):
                    raise ValueError("Parameter isolation level invalid value: {}".format(isolation_level))
                elif not isinstance(present_voltage, int) and not (isinstance(present_voltage, tuple) and len(present_voltage) == 2):
                    raise ValueError("Parameter present voltage needs to be of type int or tuple with length 2")
                else:
                    payload += b"\x00"
                    payload += isolation_level.to_bytes(1, "big")
                    if isinstance(present_voltage, int):
                        payload += present_voltage.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += present_voltage[0].to_bytes(2, "big")
                        payload += present_voltage[1].to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_pre_charge_params, payload)

    def v2gSetDcStartChargingStatus(self, code, isolation_level):
        """
        Sets the start charging status.
        If code is set to 1, all other parameters can be set to None
        """
        codes_allowed = [0, 1]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if isinstance(isolation_level, int) == False:
                    raise ValueError("Parameter isolation level needs to be of type int")
                elif isolation_level not in range(0, 5):
                    raise ValueError("Parameter isolation level invalid value: {}".format(isolation_level))
                else:
                    payload += b"\x00"
                    payload += isolation_level.to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_start_charging_status, payload)

    def v2gSetAcStartChargingStatus(self, code, rcd_status):
        """
        Sets the start charging status.
        If code is set to 1, all other parameters can be set to None
        """
        codes_allowed = [0, 1]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if isinstance(rcd_status, boolean) == False:
                    raise ValueError("Parameter rcd status needs to be of type boolean")
                else:
                    payload += b"\x01"
                    if rcd_status:
                        payload += b"\x01"
                    else:
                        payload += b"\x00"
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_start_charging_status, payload)

    def v2gSetDcChargeLoopParameters(self, code, isolation_level, present_voltage, present_current, max_current, max_voltage, max_power, max_current_reached, max_voltage_reached, max_power_reached):
        """
        Sets the pre charge parameters.
        If code is set to 1 or 2, all other parameters can be set to None
        """
        codes_allowed = [0, 1, 2]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if isinstance(isolation_level, int) == False:
                    raise ValueError("Parameter isolation level needs to be of type int")
                elif isolation_level not in range(0, 5):
                    raise ValueError("Parameter isolation level invalid value: {}".format(isolation_level))
                elif not isinstance(present_voltage, int) and not (isinstance(present_voltage, tuple) and len(present_voltage) == 2):
                    raise ValueError("Parameter present voltage needs to be of type int or tuple with length 2")
                else:
                    payload += b"\x00"
                    payload += isolation_level.to_bytes(1, "big")
                    if isinstance(present_voltage, int):
                        payload += present_voltage.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += present_voltage[0].to_bytes(2, "big")
                        payload += present_voltage[1].to_bytes(1, "big")
                    if isinstance(present_current, int):
                        payload += present_current.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += present_current[0].to_bytes(2, "big")
                        payload += present_current[1].to_bytes(1, "big")
                    if max_current is not None:
                        payload += b"\x01"
                        if isinstance(max_current, int):
                            payload += max_current.to_bytes(2, "big")
                            payload += b"\x00"
                        else:
                            payload += max_current[0].to_bytes(2, "big")
                            payload += max_current[1].to_bytes(1, "big")
                    else:
                        payload += b"\x00"
                    if max_voltage is not None:
                        payload += b"\x01"
                        if isinstance(max_voltage, int):
                            payload += max_voltage.to_bytes(2, "big")
                            payload += b"\x00"
                        else:
                            payload += max_voltage[0].to_bytes(2, "big")
                            payload += max_voltage[1].to_bytes(1, "big")
                    else:
                        payload += b"\x00"
                    if max_power is not None:
                        payload += b"\x01"
                        if isinstance(max_power, int):
                            payload += max_power.to_bytes(2, "big")
                            payload += b"\x00"
                        else:
                            payload += max_power[0].to_bytes(2, "big")
                            payload += max_power[1].to_bytes(1, "big")
                    else:
                        payload += b"\x00"
                    if max_current_reached:
                        payload += b"\x01"
                    else:
                        payload += b"\x00"
                    if max_voltage_reached:
                        payload += b"\x01"
                    else:
                        payload += b"\x00"
                    if max_power_reached:
                        payload += b"\x01"
                    else:
                        payload += b"\x00"
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_charge_loop_params, payload)

    def v2gSetAcChargeLoopParameters(self, code, max_current, rcd_status):
        """
        Sets the pre charge parameters.
        If code is set to 1 or 2, all other parameters can be set to None
        """
        codes_allowed = [0, 1, 2]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if not isinstance(max_current, int) and not (isinstance(max_current, tuple) and len(max_current) == 2):
                    raise ValueError("Parameter max current needs to be of type int or tuple with length 2")
                if isinstance(rcd_status, boolean) == False:
                    raise ValueError("Parameter rcd status needs to be of type boolean")
                else:
                    payload += b"\x01"
                    payload += b"\x01"
                    if isinstance(max_current, int):
                        payload += max_current.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += max_current[0].to_bytes(2, "big")
                        payload += max_current[1].to_bytes(1, "big")
                    if rcd_status:
                        payload += b"\x01"
                    else:
                        payload += b"\x00"
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_charge_loop_params, payload)

    def v2gSetDcStopChargingStatus(self, code, isolation_level):
        """
        Sets the stop charging status.
        If code is set to 1, all other parameters can be set to None
        """
        codes_allowed = [0, 1]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if isinstance(isolation_level, int) == False:
                    raise ValueError("Parameter isolation level needs to be of type int")
                elif isolation_level not in range(0, 5):
                    raise ValueError("Parameter isolation level invalid value: {}".format(isolation_level))
                else:
                    payload += b"\x00"
                    payload += isolation_level.to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_stop_charging_status, payload)

    def v2gSetDcPostChargeParameters(self, code, isolation_level, present_voltage):
        """
        Sets the post charge parameters.
        If code is set to 1 or 2, all other parameters can be set to None
        """
        codes_allowed = [0, 1, 2]
        if isinstance(code, int) == False:
            raise ValueError("Parameter code needs to be of type int")
        elif code not in codes_allowed:
            raise ValueError("Parameter code not in valid range {}".format(codes_allowed))
        else:
            payload = code.to_bytes(1, "big")
            if code == 0:
                if isinstance(isolation_level, int) == False:
                    raise ValueError("Parameter isolation level needs to be of type int")
                elif isolation_level not in range(0, 5):
                    raise ValueError("Parameter isolation level invalid value: {}".format(isolation_level))
                elif not isinstance(present_voltage, int) and not (isinstance(present_voltage, tuple) and len(present_voltage) == 2):
                    raise ValueError("Parameter present voltage needs to be of type int or tuple with length 2")
                else:
                    payload += b"\x00"
                    payload += isolation_level.to_bytes(1, "big")
                    if isinstance(present_voltage, int):
                        payload += present_voltage.to_bytes(2, "big")
                        payload += b"\x00"
                    else:
                        payload += present_voltage[0].to_bytes(2, "big")
                        payload += present_voltage[1].to_bytes(1, "big")
            self._sendReceiveAck(self.v2g_mod_id, self.v2g_sub_set_post_charge_params, payload)

    def v2gEvseParseSessionStarted(self, data):
        """
        Parse a session started message.
        Will return a dictionary with the following keys:
        keys protocol    int
        session_id       bytes
        evcc_id          bytes
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['protocol'] = self.payloadReaderReadInt(1)
        message['session_id'] = self.payloadReaderReadBytes(8)
        message['evcc_id'] = self.payloadReaderReadBytes(self.payloadReaderReadInt(1))
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseSessionStopped(self, data):
        """
        Parse a session stopped message.
        Will return an empty dictionary.
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['closure_type'] = self.payloadReaderReadInt(1)
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

    def v2gEvseParseRequestAuthorization(self, data):
        """
        Parse a session stopped message.
        Will return a dictionary with the following keys:
        timeout    int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = int(self.payloadReaderReadInt(4))
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseRequestDiscoveryChargeParameters(self, data):
        """
        Parse a request discovery charge parameters message.
        Will return a dictionary with the following keys:
        timeout    int
        type       int
        dc         dict (optional)
        ac         dict (optional)
        
        The dictionary dc has the following keys:
        ev_max_current    int or float
        ev_min_current    int or float (optional)
        ev_max_power      int or float (optional)
        ev_min_power      int or float (optional)
        ev_max_voltage    int or float
        ev_min_voltage    int or float (optional)
        full_soc          int (optional)
        bulk_soc          int (optional)
        soc               int
        
        The dictionary ac has the following keys:
        energy_amount     int or float
        ev_max_voltage    int or float
        ev_max_current    int or float
        ev_min_current    int or float
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['type'] = self.payloadReaderReadInt(1)
        if message['type'] == 0:
            # Parse DC parameters
            message['dc'] = {}
            message['dc']['ev_max_current'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['ev_min_current'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['ev_max_power'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['ev_min_power'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['dc']['ev_max_voltage'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['ev_min_voltage'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['full_soc'] = self.payloadReaderReadInt(1)
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['bulk_soc'] = self.payloadReaderReadInt(1)
            message['dc']['soc'] = self.payloadReaderReadInt(1)
        elif message['type'] == 1:
            # Parse AC parameters
            message['ac'] = {}
            message['ac']['energy_amount'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['ac']['ev_max_voltage'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['ac']['ev_max_current'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['ac']['ev_min_current'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseRequestSchedules(self, data):
        """
        Parse a request schedules message.
        Will return a dictionary with the following keys:
        timeout        int
        max_entries    int
        timestamp      int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['max_entries'] = self.payloadReaderReadInt(2)
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseRequestCableCheckStatus(self, data):
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

    def v2gEvseParseRequestCableCheckParameters(self, data):
        """
        Parse a request cable check parameters message.
        Will return a dictionary with the following keys:
        timeout    int
        type       int
        dc         dict
        
        The dictionary dc has the following keys:
        soc    int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['type'] = self.payloadReaderReadInt(1)
        if message['type'] == 0:
            message['dc'] = {}
            message['dc']['soc'] = self.payloadReaderReadInt(1)
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseRequestPreChargeParameters(self, data):
        """
        Parse a request pre charge parameters message.
        Will return a dictionary with the following keys:
        timeout    int
        type       int
        dc         dict
        
        The dictionary dc has the following keys:
        ev_target_voltage    int or float
        ev_target_current    int or float
        soc                  int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['type'] = self.payloadReaderReadInt(1)
        if message['type'] == 0:
            message['dc'] = {}
            message['dc']['ev_target_voltage'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['dc']['ev_target_current'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['dc']['soc'] = self.payloadReaderReadInt(1)
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseRequestStartCharging(self, data):
        """
        Parse a request start charging message.
        Will return a dictionary with the following keys:
        timeout             int
        schedule_id         int
        time_anchor         int
        ev_power_profile    list of tuples
        type                int
        dc                  dict
        
        The tuple entries fo the list ev_power_profile have the following entries:
        intervall    int
        power        int or float
        
        The dictionary dc has the following keys:
        soc                       int
        charging_complete         bool
        bulk_charging_complete    bool
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['schedule_id'] = self.payloadReaderReadInt(2)
        message['ev_power_profile'] = []
        for i in range(self.payloadReaderReadInt(1)):
            start = self.payloadReaderReadInt(4)
            power = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['ev_power_profile'].append((start, power))
        message['type'] = self.payloadReaderReadInt(1)
        if message['type'] == 0:
            message['dc'] = {}
            if self.payloadReaderReadInt(1) != 0:
                message['dc']['soc'] = self.payloadReaderReadInt(1)
            if self.payloadReaderReadInt(1) != 0:
                message['dc']['charging_complete'] = (self.payloadReaderReadInt(1) != 0)
            if self.payloadReaderReadInt(1) != 0:
                message['dc']['bulk_charging_complete'] = (self.payloadReaderReadInt(1) != 0)
        elif message['type'] == 1:
            message['ac'] = {}
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseRequestChargeLoopParameters(self, data):
        """
        Parse a request charge loop parameters message.
        Will return a dictionary with the following keys:
        timeout    int
        type       int
        dc         dict (optional)
        ac         dict (optional)
        
        The dictionary dc has the following keys:
        ev_max_current                int or float (optional)
        ev_max_voltage                int or float (optional)
        ev_max_power                  int or float (optional)
        ev_target_voltage             int or float
        ev_target_current             int or float
        soc                           int
        charging_complete             bool
        bulk_charging_complete        bool (optional)
        remaining_time_to_full_soc    int or float (optional)
        remaining_time_to_bulk_soc    int or float (optional)
        
        The dictionary ac is empty.
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['type'] = self.payloadReaderReadInt(1)
        if message['type'] == 0:
            # Parse DC parameters
            message['dc'] = {}
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['ev_max_current'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['ev_max_voltage'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['ev_max_power'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['dc']['ev_target_voltage'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['dc']['ev_target_current'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            message['dc']['soc'] = self.payloadReaderReadInt(1)
            message['dc']['charging_complete'] = (self.payloadReaderReadInt(1) != 0)
            if self.payloadReaderReadInt(1) != 0:
                message['dc']['bulk_charging_complete'] = (self.payloadReaderReadInt(1) != 0)
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['remaining_time_to_full_soc'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
            if self.payloadReaderReadInt(1) == 1:
                message['dc']['remaining_time_to_bulk_soc'] = self.payloadReaderReadIntSigned(2) * pow(10, self.payloadReaderReadIntSigned(1))
        if message['type'] == 1:
            # AC parameters empty
            message['ac'] = {}
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseRequestStopCharging(self, data):
        """
        Parse a request stop charging message.
        Will return a dictionary with the following keys:
        timeout        int
        schedule_id    int
        type           int
        dc             dict
        
        The dictionary dc has the following keys:
        soc                       int
        charging_complete         bool
        bulk_charging_complete    bool
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['type'] = self.payloadReaderReadInt(1)
        if message['type'] == 0:
            message['dc'] = {}
            if self.payloadReaderReadInt(1) != 0:
                message['dc']['soc'] = self.payloadReaderReadInt(1)
            if self.payloadReaderReadInt(1) != 0:
                message['dc']['charging_complete'] = self.payloadReaderReadInt(1)
            if self.payloadReaderReadInt(1) != 0:
                message['dc']['bulk_charging_complete'] = self.payloadReaderReadInt(1)
        self.payloadReaderFinalize()
        return message

    def v2gEvseParseRequestPostChargeParameters(self, data):
        """
        Parse a request post charge parameters message.
        Will return a dictionary with the following keys:
        timeout    int
        type       int
        dc         dict
        
        The dictionary dc has the following keys:
        soc    int
        """
        message = {}
        self.payloadReaderInitialize(data, len(data))
        message['timeout'] = self.payloadReaderReadInt(4)
        message['type'] = self.payloadReaderReadInt(1)
        if message['type'] == 0:
            message['dc'] = {}
            message['dc']['soc'] = self.payloadReaderReadInt(1)
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
        response = self._receive(self.v2g_mod_id, sub_id_list, 0x00, 30)
        return response.sub_id, response.payload
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
        response = self._receive(self.v2g_mod_id, sub_id_list, 0x00, 1)
        return response.sub_id, response.payload
