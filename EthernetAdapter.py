import multiprocessing
import time
import sys
from scapy.all import *
from scapy.layers.l2 import Ether, getmacbyip, sendp

from SUTAdapter import *
from FramingAPIDef import *

socket = None

class EthernetAdapter(SUTAdapter):
    def __init__(self):
        self.recv_process = None
        self.queue_rx = multiprocessing.Manager().Queue()
        self.queue_tx = multiprocessing.Manager().Queue()

        self.sut_ip = ""
        self.sut_interface = ""
        self.dut_mac = None
        self.packet = None
        conf.use_pcap=True

        self.holy_buffer = []


    """
    send data
    """
    def send(self, data):
        global socket
        if len(data) > 1492:
            print("Alert: Sending large frame")

        socket.send(self.packet/(b"\x00\x04" + len(data).to_bytes(2, "big") + data))


    """
    receive data
    """
    def receive(self):
        if not self.queue_rx.empty():
            frame = self.queue_rx.get_nowait()
            return frame
        else:
            return None

    """
    packet callback for our custom ethernet type
    """
    def pkt_callback(self, packet):
        payload = packet[Ether].load[4:]
        seqno = 0

        # check for input on uart
        marker = payload[0]

        # if nothing there, return to receive control
        if not marker or marker != START_OF_FRAME:
            return None

        pheader = payload[1:6]
        pbytes = int.from_bytes(pheader[3:5], 'big')

        pbytedata = 2
        if pbytes > 0:
            pbytedata = payload[6:6+pbytes]

        if not pbytedata:
            print("Had to cancel data reception mid frame")
            return None

        pdata = (pheader + pbytedata) if pbytes > 0 else pheader
        pbytes += 5

        crc = int.from_bytes(payload[pbytes+1:pbytes+2], "big")
        marker = int.from_bytes(payload[pbytes+2:pbytes+3], "big")

        if marker == END_OF_FRAME:
            frame = self.pack_and_parse_frame(
                b"\xc0" + pdata + crc.to_bytes(1, "big") + b"\xc1")

            self.queue_rx.put_nowait(frame)
        else:
            print("Could not catch end of frame")
            print(str(payload))

    """
    filter packets with custom ethernet type
    """
    def process_receive(self):
        sniff(filter='ether proto 0x6003 and ether src ' + self.dut_mac, iface=self.sut_interface,
                prn=self.pkt_callback)

    """
    start process waiting for mac frames of specific ethernet type
    """
    def start(self):
        global socket

        self.recv_process = multiprocessing.Process(target=self.process_receive)

        end_time = time.time() + 10

        while self.dut_mac == None and time.time() < end_time:
            self.dut_mac = getmacbyip(self.sut_ip)

        socket = conf.L2socket(iface=self.sut_interface)
        self.packet = Ether(dst=self.dut_mac, type=0x6003)

        if self.dut_mac == None:
            print("[!] Could not determine target MAC address from IP")
            sys.exit(1)

        self.recv_process.start()
        #self.process_receive()

        """
        sleep - letting sniffing process initialize
        """
        time.sleep(3)

    """
    stop listening for specific ethernet type
    """
    def stop(self):
        self.recv_process.terminate()

    """
    returns true if data is available
    """
    def holding_data(self):
        return not self.queue_rx.empty()

    """
    clearing queues
    """
    def clear_queues(self):
        while not self.queue_rx.empty():
            msg = self.queue_rx.get_nowait()

