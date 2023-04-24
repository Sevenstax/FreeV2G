import time
import sys
from multiprocessing import Process, Manager
from binascii import hexlify, unhexlify

from FramingAPIDef import *

sys.path.append("..")

def log(x): return print(x)
def debug_log(x): pass

class FramingInterface():

    def __init__(self):
        log("Initiating framing interface")
        self.encryption_configured = False
        self.encryption_initiated = False

        self.connection_mode = ""
        self.limited_host_simulation = False
        self.sut_ip = ""
        self.sut_mac = ""
        self.sut_interface = ""

        self.request_id = 0
        self.seq_nr = -1
        self.last_sent = None
        self.last_frame_fetch_time = None

        self.sut_adapter = None
        self.cmd_sut_adapter = None

        self.notification_frames = []
        self.data_frames = []
        self.frame_backlog = []

        self.verbose_tx = False
        self.verbose_rx = False
        
        self.initialized = False
        
    def isInitialized(self):
        return self.initialized

    """
    top level function for initializing the SUT adapter for framing
    """
    def initialize_framing(self, if_type, if_name, mac):
        """Top level function for initializing the SUT adapter for framing
        """
        self.connection_mode = if_type
        if self.connection_mode == "ETH":
            import EthernetAdapter
            self.sut_adapter = EthernetAdapter.EthernetAdapter()
            if mac:
                self.sut_adapter.dut_mac = mac
        elif self.connection_mode == "SPI":
            import SpiAdapter
            self.sut_adapter = SpiAdapter.SpiAdapter()
        else:
            raise AssertionError("Invalid interface!")

        self.sut_adapter.sut_interface = if_name

        self.sut_adapter.start()

        self.seq_nr = 1
        
        self.initialized = True

    def set_plain_config(self, connection_mode):
        self.connection_mode = connection_mode

    def receive_next_unencrypted_frame(self, break_on_data, break_on_notification):
        if not self.sut_adapter.holding_data():
            return None
        else:
            return self.sut_adapter.receive()

    def reload_communication_interface(self):
        if self.connection_mode == "ETH":
            self.reload_eth_interface()

    """
    reloading ethernet interface after module restart or similar
    possibly no action required
    """
    def reload_eth_interface(self):
        pass

    """
    reloading UART interface after module start or similar
    """
    def reload_serial_interface(self, baudrate):
        log("Reloading serial interface with baudrate: " + str(baudrate))
        self.sut_adapter.stop()
        self.sut_adapter.process_start(self.bin_uart_port,
                                     baudrate,
                                     self.bin_uart_timeout,
                                     self.bin_uart_stopbits,
                                     self.bin_uart_parity,
                                     self.bin_uart_bytesize,
                                     self.bin_uart_rtscts,
                                     single_byte_mode=True,
                                     lim_res_sim=False)

    def send_unencrypted_frame(self, frame):
        self.write_output(frame)

    def read_input(self, nbytes, timeout=0.3):
        data = b""
        for i in range(0, nbytes):
            end_time = time.time() + timeout
            while not self.sut_adapter.holding_data():
                if time.time() > end_time:
                    return None
            data += self.sut_adapter.receive()
        return data

    def write_output(self, data):
        """
        Logging frame
        """
        if self.verbose_tx and not self.encryption_initiated:
            debug_log("Adding the following frame to the send buffer:\n\t" +
                      self.printable_frame(self.pack_and_parse_frame(data, nocrc=True)) + "\n")
        elif self.verbose_tx and self.encryption_initiated:
            debug_log("Adding the following frame to the send buffer:\n\t" +
                      "-".join(str(hexlify(data))[i:i+2] for i in range(0, len(str(hexlify(data))), 2)))

        """
        Giving it to the SUT adapter
        """
        self.sut_adapter.send(data)

    """
    receive a frame from the sut adapters data queue
    a frame has to be received within a certain time window
    """
    def receive_next_frame(self, break_on_data=False,
                           break_on_notification=False,
                           timeout=5,
                           noisy_timeout=True,
                           filter_mod=None,
                           filter_sub=None,
                           filter_req_id=None,
                           search_backlog=True):

        frame = None
        satisfied = False

        timeout_point = time.time() + timeout
        temp_backlog = []
        if self.encryption_initiated:
            debug_log("Fetching next encrypted frame from buffer")
        else:
            debug_log("Fetching next normal frame from buffer")

        while not satisfied:
            satisfied = True

            """ make sure to get frames every x milliseconds """
            if self.limited_host_simulation and len(self.frame_backlog) == 0:
                if not self.last_frame_fetch_time:
                    self.last_frame_fetch_time = time.time()

                debug_log("Host simulation activated, delaying")
                while self.last_frame_fetch_time + 0.002 > time.time():
                    time.sleep(0.001)

            if self.encryption_initiated:
                frame = self.receive_next_encrypted_frame()
            else:
                frame = self.receive_next_unencrypted_frame(
                    break_on_data, break_on_notification)

            # check if we got a frame or no input on uart
            if frame is None:
                if self.frame_backlog and search_backlog:
                    debug_log("Retrieving frame from backlog, current size: {}".format(
                        len(self.frame_backlog)))
                    frame = self.frame_backlog.pop(0)
                    # debug_log(self.printable_frame(frame))

            if frame is not None:
                if filter_req_id is not None:
                    # Filter for request ID
                    if isinstance(filter_req_id, int):
                        filter_req_id = [filter_req_id]
                    if frame.req_id not in filter_req_id:
                        satisfied = False

                if filter_mod is not None:
                    # Filter for module ID
                    if isinstance(filter_mod, int):
                        filter_mod = [filter_mod]
                    if frame.mod_id not in filter_mod:
                        satisfied = False

                if filter_sub is not None:
                    # Filter for sub ID
                    sub_id_filter_list = None

                    if isinstance(filter_sub, dict):
                        if frame.mod_id in filter_sub:
                            sub_id_filter_list = filter_sub[frame.mod_id]
                    else:
                        sub_id_filter_list = filter_sub

                    if isinstance(sub_id_filter_list, int):
                        sub_id_filter_list = [sub_id_filter_list]

                    if not (sub_id_filter_list == None or frame.sub_id in sub_id_filter_list):
                        satisfied = False

                # for backwards compatibility
                if frame.sub_id > 127:
                    if not break_on_notification and not filter_sub and not filter_mod \
                            and not filter_req_id:
                        satisfied = False
                elif frame.sub_id == 1:
                    if break_on_data or 1 in filter_sub:
                        self.data_frames.append(frame)
                    else:
                        satisfied = False

                if not satisfied:
                    temp_backlog.append(frame)
            else:
                satisfied = False

            if timeout == 0:
                if satisfied == False:
                    frame = None

                if self.sut_adapter.holding_data():
                    continue

                if len(self.frame_backlog) == 0 or search_backlog == False:
                    break

            elif time.time() > timeout_point and not satisfied:
                self.frame_backlog = temp_backlog + self.frame_backlog
                debug_log("Im over timeout {}: timeout_point is {} and i am {}".format(
                    str(timeout), str(timeout_point), str(time.time())))

                if noisy_timeout:
                    raise AssertionError("Frame reception timed out")
                else:
                    return None

            else:
                # Timeout not exceeded, continue
                pass

        self.frame_backlog = temp_backlog + self.frame_backlog
        return frame

    def send_frame_and_get_answer(self, module_id, sub_id, payload, timeout=5,
                                  noisy_timeout=False):
        req_id = self.build_and_send_frame(module_id, sub_id, payload)
        return self.receive_next_frame(filter_req_id=req_id, timeout=timeout,
                                       noisy_timeout=noisy_timeout)

    """
    get last sent frame
    """
    def get_last_sent(self):
        return self.last_sent

    """
    send raw frame
    """
    def send_frame(self, frame):
        self.last_sent = frame
        if self.encryption_initiated:
            self.send_encrypted_frame(frame)
        else:
            self.send_unencrypted_frame(frame)

    def arg2bytes(self, hexstr, num):
        bytearr = b''
        bytearr = unhexlify(hexstr)
        if len(bytearr) != num:
            raise AssertionError(
                'Expected a {} bit hexadecimal number.'.format(8*num))
        return bytearr

    def compute_payload_checksum(self, data):
        sum = 0
        for i in range(len(data)):
            sum += data[i]
        sum = (sum & 0xFFFF) + (sum >> 16)
        sum = (sum & 0xFF) + (sum >> 8)
        sum = (sum & 0xFF) + (sum >> 8)
        if(sum != 0xFF):
            sum = (~sum & 0xFF)

        return sum.to_bytes(1, byteorder="big", signed=False)

    def printable_frame(self, frame):
        prettystring = "\n###### FRAME ######"
        for key in frame.__dict__.keys():
            if key[0] == "_":
                continue
            prettystring += "\n| " + key + ": " + \
                str(frame.__dict__[key]) + "\t\t\t"

        return prettystring + "\n"

    def build_and_send_frame(self, module_id, sub_id, payload, req_id=None):
        payload_length_and_payload = len(payload).to_bytes(
            2, "big") + payload if payload else b"\x00\x00"
        request_id_num = self.generate_next_request_id() if req_id == None else req_id
        request_id = request_id_num.to_bytes(1, "big")
        frame_without_checksum = (START_OF_FRAME.to_bytes(1, "big") + module_id.to_bytes(1, "big") +
                                  sub_id.to_bytes(1, "big") + request_id +
                                  payload_length_and_payload + b"\x00" + END_OF_FRAME.to_bytes(1,"big"))

        self.send_frame(START_OF_FRAME.to_bytes(1, "big") + module_id.to_bytes(1, "big") + sub_id.to_bytes(1, "big")
                        + request_id + payload_length_and_payload +
                        self.compute_payload_checksum(frame_without_checksum) + END_OF_FRAME.to_bytes(1, "big"))

        return request_id_num

    def generate_next_request_id(self):
        if self.request_id == 254: # Skip 0xFF as that's used for status messages
            self.request_id = 0
        else:
            self.request_id += 1

        return self.request_id

    def generate_next_seq_nr(self):
        if self.seq_nr == 200055:
            self.seq_nr = 0
        else:
            self.seq_nr += 1

        return self.seq_nr

    def holding_data(self):
        return self.sut_adapter.holding_data() or len(self.frame_backlog) > 0

    def drain_all_data_frames(self):
        time.sleep(2)
        while self.holding_data():
            self.receive_next_frame(break_on_data=True, timeout=7, search_backlog=True,
                                    noisy_timeout=False)
            time.sleep(2)

    def clear_all_data_frames(self):
        self.drain_data()
        self.data_frames.clear()
        self.frame_backlog.clear()

    def drain_data(self):
        self.sut_adapter.clear_queues()

    def clear_backlog(self):
        self.clear_all_data_frames()

    def get_backlog_frames(self):
        pass

    def get_module_name_by_id(self, id):
        for module_name, module_details in MODULE_IDS.items():
            if module_details[0] == id:
                return module_name

    def get_module_id_by_name(self, name):
        for module_name, module_details in MODULE_IDS.items():
            if module_name == name:
                return module_details[0]

    def get_sub_name_by_id(self, module_id, sub_id):
        for module_name, module_details in MODULE_IDS.items():
            if module_details[0] == module_id:
                return module_details[1][sub_id][0] if sub_id in module_details[1].keys() else "None"

    def get_sub_id_by_name(self, module_name, sub_name):
        for s_name, s_id in MODULE_IDS[module_name][1]:
            if sub_name == s_name:
                return s_id

    def shut_down_interface(self):
        self.clear_backlog()
        self.sut_adapter.clear_queues()
        self.sut_adapter.stop()
        self.initialized = False