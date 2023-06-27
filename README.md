     oooooooooooo                              oooooo     oooo   .oooo.     .oooooo.    
     `888'     `8                               `888.     .8'  .dP""Y88b   d8P'  `Y8b   
      888         oooo d8b  .ooooo.   .ooooo.    `888.   .8'         ]8P' 888           
      888oooo8    `888""8P d88' `88b d88' `88b    `888. .8'        .d8P'  888           
      888    "     888     888ooo888 888ooo888     `888.8'       .dP'     888     ooooo 
      888          888     888    .o 888    .o      `888'      .oP     .o `88.    .88'  
     o888o        d888b    `Y8bod8P' `Y8bod8P'       `8'       8888888888  `Y8bood8P'   

## IMPORTANT INFORMATION

**We are currently investigating issues with the firmware update file for EV firmware V01_00_06 and strongly advise against updating your EV module to V01_00_06 using the FWU file obtained from CODICOs download area prior to the 27th of June 2023.**

## INTRODUCTION

FreeV2G is a reference implementation in python to control the 8devices WHITE-beet-EI ISO15118 EVSE and WHITE-beet-PI ISO15118 EV modules using Ethernet host control interface (HCI).

For detailed information about the WHITE-beet modules please visit https://www.codico.com/en/white-beet-ei-evse-embedded-iso15118-module and https://www.codico.com/en/white-beet-pi-pev-embedded-iso15118-module pages. 
Evaulation boards for the modules can be found on https://www.codico.com/en/wb-carrier-board-ei-1-1-evse-embedded-iso15118-sw-stack-ev and https://www.codico.com/en/wb-carrier-board-pi-1-1-pev-embedded-iso15118-sw-stack.

Please use the correct version of the FreeV2G application for your WHITE-beet firmware.

The following table shows the relationship between WHITE-beet-EI ISO15118 EVSE firmware versions and FreeV2G.

| WB FW Version | SW Type | FreeV2G Tag |
| - | - | - |
| V01_01_06 | EIM | [EVSE_v1.1.6_1](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v1.1.6_1) |
| V01_01_07 | EIM | [EVSE_v1.1.7_1](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v1.1.7_1) |
| V02_00_00 | PNC | [EVSE_v2.0.0_0](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v2.0.0_0) |
| V02_00_01 | PNC | [EVSE_v2.0.1_4](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v2.0.1_4) |

The following table has information about the relationship between WHITE-beet-PI ISO15118 EV firmware and FreeV2G.

| WB FW Version | SW Type | FreeV2G Tag |
| - | - | - |
| V01_00_04 | EIM | [EV_v1.0.4_0](https://github.com/Sevenstax/FreeV2G/tree/EV_v1.0.4_0) |
| V01_00_05 | EIM | [EV_v1.0.5_0](https://github.com/Sevenstax/FreeV2G/tree/EV_v1.0.5_0) |
| V01_00_06 | EIM | [EV_v1.0.6_1](https://github.com/Sevenstax/FreeV2G/tree/EV_v1.0.6_1) |

Actual WHITE-beet SW updates for EVSE abd EV are available at **CODICO PLC documentation area** https://downloads.codico.com/misc/plc under NDA.

## FEATURES

The main feature of this implementation is the parsing of the protocol used to communicate with the WHITE-beet. Other features are the WHITE-beet class which answers the parameter requests of the WHITE-beet and the charger class which simulates the voltage and current based on the given parameters during initialization and on the parameters received by the EV during the charging process.

### Control Pilot

There is a basic control pilot implemenation which detects the EV plugin and sets the duty cycle to 5% when the module is ready to receive the SLAC request message from the EV. When the charging session is finished the oscillator shuts down automatically.

### SLAC

SLAC is performed automatically by the WHITE-beet. A notification is received and the application is ready for high-level communication.

#### V2G High-Level Communication

When SLAC was succefully performed the EVSE and the EV are in same network and the high-level communication can be started. The EV will try to discover the EVSE with the SDP protocol and will then connect to the EVSE. The EVSE will choose one of the protocols the EV provided and a V2G session will be started. The service discovery, charge parameter discovery and authorization is performed and the charging loop is started. The EV will continue to charge until it decides to stop the session.

## GETTING FreeV2G

To get started first clone the repository. This will get you the latest version of the repository.

```console
$ git clone https://github.com/SEVENSTAX/FreeV2G
$ cd FreeV2G
```

Create a virtual environment
```console
$ python3 -m venv .venv
$ source .venv/bin/activate
```

Install the python packages needed
```console
$ pip install --pre scapy[basic]
$ pip install Cython
$ pip install python-libpcap
```

## GETTING STARTED

Make sure that EVSE and EV are not physically connected on the PLC interface.

Find the MAC address printed on the label of the board in the form of i.e. c4:93:00:22:22:24. This is the MAC address of the PLC chip. To get the MAC address of the ethernet interface substract 2 of the last number of the MAC address. For the example above this would result in the MAC address c4:93:00:22:22:22 for the ethernet interface.

Find the ethernet interface the WHITE-beet is connected to with

```console
$ ip list
```

Run the Application in EVSE mode by typing (we need root privileges for raw socket access).

```console
$ sudo .venv/bin/python3 Application.py eth -i eth0 -m c4:93:00:22:22:22 -r EVSE
```

You should see the following output

```console
Welcome to Codico Whitebeet EVSE reference implementation
Initiating framing interface
iface: eth0, mac: c4:93:00:22:22:22
Set the CP mode to EVSE
Set the CP duty cycle to 100%
Start the CP service
Start SLAC in EVSE mode
Wait until an EV connects
```

Now, physically connect the PLC interface of the EV to the EVSE

```console
EV connected
Start SLAC matching
Set duty cycle to 5%
SLAC matching successful
Set V2G mode to EVSE
Start V2G
"Session started" received
Protocol: 2
Session ID: f3976451aedd64ce
EVCC ID: 000101637730
"Request EVSE ID" received
Set EVSE ID: DE*ABC*E*00001*01
"Request Authorization" received
Authorize the vehicle? Type "yes" or "no" in the next 59s:
```

Now you can authorize the vehicle by typing "yes", the application will continue. All the parameters that are exchanged between the vehicle and the charging station are printed to the console.

```console
Vehicle was authorized by user!
"Request Schedules" received
Max entries: 2
Set the schedule: [(0, 65535, 25000), (1, 65535, 25000)]
"Request Discovery Charge Parameters" received
EV maximum current: 20A
EV maximum power: 8000W
EV maximum voltage: 400V
Bulk SOC: 50%
SOC: 50%
"Request Cable Check Status" received
"Request Cable Check Parameters" received
SOC: 50%
"Request Pre Charge Parameters" received
EV target voltage: 380V
EV target current: 50A
SOC: 50%
"Request Start Charging" received
Schedule ID: 0
Time anchor: 0
EV power profile: [(0, 10000)]
SOC: 50%
Charging complete: False
"Request Charge Loop Parameters" received
EV maximum current: 20A
EV maximum voltage: 400V
EV maximum power: 8000W
EV target voltage: 380V
EV target current: 16A
SOC: 50%
Charging complete: False
```

... charge loop continues until EV stops charging...

```console
"Request Charge Loop Parameters" received
EV maximum current: 20A
EV maximum voltage: 400V
EV maximum power: 8000W
EV target voltage: 380V
EV target current: 16A
SOC: 50%
Charging complete: False
"Request Stop Charging" received
Schedule ID: 0
SOC: 50%
Charging complete: 1
"Request Post Charge Parameters" received
SOC: 50%
"Session stopped" received
EVSE loop finished
Goodbye!
```
## EV SUPPORT

Run the application in EV mode by typing

```console
$ sudo .venv/bin/python3 Application.py eth -i eth0 -m c4:93:00:33:33:33 -r EV
```

## CONFIGURATION

You can set the configuration via a configuration file in json format.

**Currently only EV mode supports a configuration file.**

Run the application with configuration file

```console
$ sudo .venv/bin/python3 Application.py eth -i eth0 -m c4:93:00:33:33:33 -r EV -c $PATH_TO_CONFIG_FILE
```

If no path is given the configuration file defaults to ./ev.json. An example configuration can be found in ev.json.

## RASPBERRY PI SPI

Install the python packages needed
```console
$ pip install spidev
$ pip install RPi.GPIO
```

Connect the WHITE-beet to the Raspberry Pi

The SPI pinout for the Pi can be found on https://pinout.xyz/pinout/spi#

| WB Pin | Raspberry Pi Pin |
| - | - |
| J8 MOSI | SPI0 MOSI |
| J8 MISO | SPI0 MISO |
| J8 SCK | SPI0 SCLK |
| J8 NSS | GPIO 24 |
| J8 GND | Ground |
| J1 PD4 | GPIO 22 |
| J1 PD11 | GPIO 27 |

Set up the WHITE-beet to start in SPI mode by connecting PC2 to 3.3V and PA4 to GND on J4.

Power up the WHITE-beet and run the application in SPI mode with the following command

```console
sudo .venv/bin/python3 Application.py spi -i spidev0.0 -m 00:01:01:63:77:33 -r EVSE
```
