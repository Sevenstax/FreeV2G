"""
*        COMPANY:      SEVENSTAX GmbH
*                      Guenther-Wagner-Allee 19
*                      30177 Hannover
*                      GERMANY
*
*        CONTACT:      www.sevenstax.de
*                      info@sevenstax.de
*
"""
import multiprocessing
import time
import sys
import spidev
import RPi.GPIO as GPIO
import re


from SUTAdapter import *
from FramingAPIDef import *

#def log(x): return print(x)
def log(x): return
#def packet_dump(x): return print(x)
def packet_dump(x): return
def debug_log(x): pass

class SpiAdapter(SUTAdapter):
    def __init__(self):
        log("SpiAdapter->__init__()")
        self.started = False
        self.spiadapter_process = None
        self.queue_rx = multiprocessing.Manager().Queue()
        self.queue_tx = multiprocessing.Manager().Queue()

        self.sut_interface = ""
        self.packet = None
        self.spi = None
        self.gpioRxReady = 22
        self.gpioTxPending = 27
        self.gpioAltCS = 24
        self.DefectPacket = 0
        self.PacketCount = 0
        
        # Prepare GPIOS for Rx Ready and Tx Pending detection
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpioRxReady, GPIO.IN)
        GPIO.setup(self.gpioTxPending, GPIO.IN)
        
        # Optional CS (needed due to problems with default CS)
        GPIO.setup(self.gpioAltCS, GPIO.OUT, initial=GPIO.HIGH)

    """
    send data
    """
    def send(self, data):
        log("SpiAdapter->send()")
        self.queue_tx.put_nowait(data)
        packet_dump(bytes(data).hex())

    """
    receive data
    """
    def receive(self):
        log("SpiAdapter->receive()")
        if not self.queue_rx.empty():
            frame = self.queue_rx.get_nowait()
            return frame
        else:
            return None
        return None

    """
    packet callback for our custom ethernet type
    """
    def pkt_callback(self, packet):
        log("SpiAdapter->pkt_callback()")
        payload = packet[4:]

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
    def process_spi_transfers(self):
        while 1:
            # check if slave is ready for receiving frames
            if GPIO.input(self.gpioRxReady) == 1:
                # check if TX data is available or TX pending is set
                if not self.queue_tx.empty() or GPIO.input(self.gpioTxPending) == 1:
                    log("SpiAdapter->process_spi_transfers()")
                    spi_slave_trans_size = 0
                    spi_master_trans_size = 0
                    TxFrame = None

                    # Read out frame from TX queue
                    if not self.queue_tx.empty():
                        TxFrame = self.queue_tx.get_nowait()
                        spi_master_trans_size = len(TxFrame)
                   
                    # Create and send SPI size header
                    Transfer = self.__AddSizeHeader(spi_master_trans_size)
                    packet_dump(bytes(Transfer).hex())
                    reply = self.__TransferData(Transfer)
                    packet_dump(bytes(reply).hex())

                    # check if valid data was received from SLAVE
                    if reply[0] == 0xAA and reply[1] == 0xAA:
                        count = 0
                        next_transfer_data = self.__GenerateDataFrame(TxFrame)
                        # calculate rx data size from slave
                        spi_slave_trans_size = reply[2] * 255 + reply[3]
                    
                        # append data to data for next SPI transfer if SPI slave wants to send more data than master
                        if spi_slave_trans_size > spi_master_trans_size:
                            count = spi_slave_trans_size - spi_master_trans_size
                            
                        while count > 0:
                            next_transfer_data.append(0x00)
                            count -= 1

                        # start SPI transfer
                        packet_dump(bytes(next_transfer_data).hex())
                        while 1:
                            if GPIO.input(self.gpioRxReady) == 1:
                                break;

                        reply = self.__TransferData(next_transfer_data)
                        reply = bytearray(reply)
                        packet_dump(bytes(reply).hex())

                        if len(reply) > 4:
                            if reply[0] == 0x55 and reply[1] == 0x55 and reply[2] == 0x00 and reply[3] == 0x00:
                                self.pkt_callback(reply)
                            else:
                                print("Warning: Received invalid data-frame header!")
                                print (reply)
                        else:
                            print("Warning: Too few data received!")
                    else:
                        print("Warning: Received invalid size-frame header!")
                        print(reply)

    """
    start process waiting for mac frames of specific ethernet type
    """
    def start(self):
        log("SpiAdapter->start()")
        # get SPI bus and device from given interface string
        temp = re.match(r'^spidev(\d+)\.(\d+)$', self.sut_interface)
        bus = int(temp.group(1))
        device = int(temp.group(2))
        
        # start SPI device
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = 12000000
        self.spi.mode = 0b00
        
        print ("Start SPI on bus " + str(bus) + " device " + str(device) + " with " + str(self.spi.max_speed_hz) + " MHz")
        
        # initialize and start SPI transfer process
        self.spiadapter_process = multiprocessing.Process(target=self.process_spi_transfers)
        self.spiadapter_process.start()

        self.started = True

        """
        sleep - letting sniffing process initialize
        """
        time.sleep(1)

    """
    stop listening for specific ethernet type
    """
    def stop(self):
        log("SpiAdapter->stop()")
        self.spiadapter_process.terminate()
        time.sleep(1)

    """
    returns true if data is available
    """
    def holding_data(self):
        return not self.queue_rx.empty()

    """
    clearing queues
    """
    def clear_queues(self):
        log("SpiAdapter->clear_queues()")
        while not self.queue_rx.empty():
            msg = self.queue_rx.get_nowait()

    def __AddSizeHeader(self, size):
        log("SpiAdapter->__AddSizeHeader()")
        data = b"\xAA\xAA"
        data += size.to_bytes(2, "big")
        return data

    def __TransferData(self, txData):
        #log("SpiAdapter->__TransferData()")
        GPIO.output(self.gpioAltCS, False)
        #time.sleep(0.00002)
        #self.PacketCount += 1
        end_time_toggle = time.time_ns() + 10 * 1000
        while time.time_ns() < end_time_toggle:
            continue
        
        #if (self.PacketCount == self.DefectPacket):
        #    txData = txData[:3]
        reply = self.spi.xfer(txData)
        GPIO.output(self.gpioAltCS, True)
        return reply

    def __GenerateDataFrame(self, data):
        frame = bytearray(b"\x55\x55\x00\x00")
        if data != None:
            frame += bytearray(data)
        return frame