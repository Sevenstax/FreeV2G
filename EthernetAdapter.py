import multiprocessing
import time
import sys
from platform import system as system_type
from scapy.all import *
from scapy.layers.l2 import Ether, getmacbyip, sendp

from SUTAdapter import *
from FramingAPIDef import *

if system_type() == "Linux":
    from pylibpcap.base import Sniff

class EthernetAdapter(SUTAdapter):
    def __init__(self):
        self.recv_process = None
        self.queue_rx = multiprocessing.Manager().Queue()
        self.queue_tx = multiprocessing.Manager().Queue()

        self.sut_ip = ""
        self.sut_interface = ""
        self.dut_mac = None
        self.packet = None
        self.socket = None
        conf.use_pcap=True


    """
    send data
    """
    def send(self, data):
        if len(data) > 1450:
            print("Alert: Sending large frame")

        if system_type() == "Linux":
            self.socket.send(self.packet/(b"\x00\x04" + len(data).to_bytes(2, "big") + data))
        else:
            global socket
            socket.send(self.packet/(b"\x00\x04" + len(data).to_bytes(2, "big") + data))


    """
    receive data
    """
    def receive(self):
        if not self.queue_rx.empty():
            frame = self.queue_rx.get_nowait()
            print("Received frame from queue")
            return frame
        else:
            return None

    """
    packet callback for our custom ethernet type
    """
    def pkt_callback(self, packet):
        print("Got packet")
        if system_type() == "Linux":
            payload = Ether(packet)[Ether].load[4:]
        else:
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

            print("Putting frame into receive queue")
            self.queue_rx.put_nowait(frame)
        else:
            print("Could not catch end of frame")
            print(str(payload))

    """
    filter packets with custom ethernet type
    """
    def process_receive(self):
        print("Receive process started")
        if system_type() == "Linux":
            print("Starting sniff process (unix)...")
            sniffobj = Sniff(self.sut_interface, filters="ether proto 0x6003 and ether src " + self.dut_mac, promisc=1)
            for plen, t, buf in sniffobj.capture():
                self.pkt_callback(buf)
        else:
            print("Starting sniff process (win)...")
            sniff(filter='ether proto 0x6003 and ether src ' + self.dut_mac, iface=self.sut_interface,
                prn=self.pkt_callback)

    """
    start process waiting for mac frames of specific ethernet type
    """
    def start(self):
        print("Starting Ethernet Adapter...")

        self.recv_process = multiprocessing.Process(target=self.process_receive)

        end_time = time.time() + 10

        while self.dut_mac == None and time.time() < end_time:
            self.dut_mac = getmacbyip(self.sut_ip)

        if self.dut_mac == None:
            raise AssertionError("[]!] Could not determine target MAC address from IP")

        if system_type() == "Linux":
            self.socket = conf.L2socket(iface=self.sut_interface)
            self.packet = Ether(src=get_if_hwaddr(self.sut_interface), dst=self.dut_mac, type=0x6003)
        else:
            global socket
            socket = conf.L2socket(iface=self.sut_interface)
            self.packet = Ether(dst=self.dut_mac, type=0x6003)

        print("Starting receive process...")
        self.recv_process.start()

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
