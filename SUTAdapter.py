from binascii import hexlify, unhexlify

from FramingAPIDef import *

class SUTAdapter:
    def __init__(self):
        pass

    def receive(self):
        pass

    def send(self, data):
        pass

    def clear_queues(self):
        pass

    def stop(self):
        pass

    def holding_data(self):
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

    def printable_frame(self, frame):
        prettystring = "\n###### FRAME ######"
        for key in frame.__dict__.keys():
            if key[0] == "_":
                continue
            prettystring += "\n| " + key + ": " + \
                str(frame.__dict__[key]) + "\t\t\t"

        return prettystring + "\n"

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

    def pack_and_parse_frame(self, binary_string, nocrc=False):
        frame = Frame()
        frame.mod_id = binary_string[1]
        frame.mod_name = self.get_module_name_by_id(binary_string[1])
        frame.sub_id = binary_string[2]
        frame.sub_name = self.get_sub_name_by_id(
            binary_string[1], binary_string[2])
        frame.req_id = binary_string[3]
        frame.payload_len = int.from_bytes(binary_string[4:6], 'big')
        frame.payload = binary_string[6:5+frame.payload_len+1]
        frame.crc = binary_string[-2]
        hex_byte_string = str(hexlify(binary_string))
        frame.raw_hex = "_".join(
            hex_byte_string[i:i+2] for i in range(2, len(hex_byte_string) - 1, 2))

        # check for correct checksum
        if not nocrc and self.compute_payload_checksum(binary_string[:-2] + b"\x00"
                                                       + binary_string[-1:]) != frame.crc.to_bytes(1, "big") and frame.crc != 0:
            raise AssertionError(
                "CRC of received frame not correct!\n" + frame.raw_hex)

        # log out mod_name if error
        if frame.mod_name == "error":
            print("Warning: Binuart \"Error\" frame responded")

        # '-'.join(hex_byte_string[i:i+2] for i in range(0, len(hex_byte_string) , 2))
        return frame


