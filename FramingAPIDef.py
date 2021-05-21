import random
import string

class Frame (object):
    def __init__(self):
        self.mod_id = 0
        self.mod_name = ""
        self.sub_id = 0
        self.sub_name = 0
        self.req_id = 0
        self.payload_len = 0
        self.payload = b""
        crc = 0

    # add dict access for backwards compatibility
    def __getitem__(self, key):
        if key == "payload":
            return self.payload
        elif key == "subroutine":
            return {"id": self.sub_id, "interpretation": self.sub_name}
        elif key == "module":
            return {"id": self.mod_id, "interpretation": self.mod_name}
        elif key == "crc":
            return self.crc
        elif key == "req_id":
            return self.req_id

MODULE_IDS = {}

START_OF_FRAME      = 0xc0
END_OF_FRAME        = 0xc1
START_OF_ENCR_FRAME = 0xfe
END_OF_ENCR_FRAME   = 0xff