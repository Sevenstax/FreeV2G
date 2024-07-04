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

FreeV2G is a reference application written in python to control the 8devices WHITE Beet-EI ISO15118 EVSE and WHITE Beet-PI ISO15118 EV modules using host control interface (HCI).

For detailed information about the WHITE Beet modules please visit the Codico website:

[WHITE Beet-EI](https://www.codico.com/en/WHITE Beet-ei-evse-embedded-iso15118-module)

[WHITE Beet-PI](https://www.codico.com/en/WHITE Beet-pi-pev-embedded-iso15118-module)

Evaulation boards for easy access of the modules are also available:

[WHITE Beet-EI evaluation board](https://www.codico.com/en/wb-carrier-board-ei-1-1-evse-embedded-iso15118-sw-stack-ev)

[WHITE Beet-PI evaluation board](https://www.codico.com/en/wb-carrier-board-pi-1-1-pev-embedded-iso15118-sw-stack)

**NOTE:** Please make sure to use matching WHITE Beet firmware version and FreeV2G tag.

The following table shows the relationship between WHITE Beet-EI ISO15118 EVSE firmware versions and FreeV2G.

| WB FW Version | Payment Methods | FreeV2G Tag                                                              |
| ------------- | --------------- | ------------------------------------------------------------------------ |
| V01_01_06     | EIM             | [EVSE_v1.1.6_1](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v1.1.6_1) |
| V01_01_07     | EIM             | [EVSE_v1.1.7_1](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v1.1.7_1) |
| V02_00_00     | EIM + PNC       | [EVSE_v2.0.0_0](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v2.0.0_0) |
| V02_00_01     | EIM + PNC       | [EVSE_v2.0.1_4](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v2.0.1_4) |
| V02_01_00     | EIM + PNC       | [EVSE_v2.1.0_0](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v2.1.0_0) |

The following table shows the relationship between WHITE Beet-PI ISO15118 EV firmware and FreeV2G.

| WB FW Version | SW Type | FreeV2G Tag                                                          |
| ------------- | ------- | -------------------------------------------------------------------- |
| V01_00_04     | EIM     | [EV_v1.0.4_0](https://github.com/Sevenstax/FreeV2G/tree/EV_v1.0.4_0) |
| V01_00_05     | EIM     | [EV_v1.0.5_0](https://github.com/Sevenstax/FreeV2G/tree/EV_v1.0.5_0) |
| V01_00_06     | EIM     | [EV_v1.0.6_1](https://github.com/Sevenstax/FreeV2G/tree/EV_v1.0.6_1) |

Actual WHITE Beet SW updates for EVSE abd EV are available at [**CODICO PLC documentation area**](https://downloads.codico.com/misc/plc) under NDA.

## FEATURES

The main feature of this implementation is the parsing of the protocol used to communicate with the WHITE Beet. Other features are the WHITE Beet class which answers the parameter requests of the WHITE Beet and the charger class which simulates the voltage and current based on the given parameters during initialization and on the parameters received by the EV during the charging process.

### Control Pilot

There is a basic control pilot implemenation which detects the EV plugin and sets the duty cycle to 5% when the module is ready to receive the SLAC request message from the EV. When the charging session is finished the oscillator shuts down automatically.

### SLAC

SLAC is performed automatically by the WHITE Beet. A notification is received and the application is ready for high-level communication.

#### V2G High-Level Communication

When SLAC was succefully performed the EVSE and the EV are in same network and the high-level communication can be started. The EV will try to discover the EVSE with the SDP protocol and will then connect to the EVSE. The EVSE will choose one of the protocols the EV provided and a V2G session will be started. The service discovery, charge parameter discovery and authorization is performed and the charging loop is started. The EV will continue to charge until it decides to stop the session.

## Get started

### Installation

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
$ pip install -r requirements_eth.txt
```

### Usage

```console
usage: Application.py [-h] config

Codico WHITE Beet reference implementation.

positional arguments:
  config      Path to configuration file. Defaults to ./config.json.

options:
  -h, --help  show this help message and exit
```

### Configuration

Configuration is done via a configuration file. If no path is given the configuration file defaults to `./config.json`. Example configurations can be found in `config_ev.json` and `config_evse.json`.

### Ethernet setup

Find the ethernet interface the WHITE Beet is connected to with:

```console
$ ip list
```
Here the WHITE Beet is connected to `eth0`, therefore in the config file the `interface` key is set to:

```json
    "interface": {
        "type": "eth",
        "name": "eth0"
    }
```

Run the Application in EVSE mode by typing (the application needs root privileges for raw socket access).

```console
$ sudo .venv/bin/python3 Application.py config_evse.json
```

### SPI setup (RaspberryPi)

The example application can be used with SPI as host controller interface. This is tested on a RaspberryPi 4, but should work with any other Linux system that has access to a spidev in userspace.

Set up the WHITE Beet to start in SPI mode by connecting PC2 to 3.3V and PA4 to GND.

Connect the WHITE Beet to the Raspberry Pi:

| Whietbeet Pin | RaspberryPi Name | wPi | BCM |
| ------------- | ---------------- | --- | --- |
| J8 MOSI       | SPI0 MOSI        | 12  | 10  |
| J8 MISO       | SPI0 MISO        | 13  | 9   |
| J8 SCK        | SPI0 SCLK        | 14  | 11  |
| J8 NSS        | GPIO.5           | 5   | 24  |
| J8 GND        | Ground           |     |     |
| J1 PD4        | GPIO.3           | 3   | 22  |
| J1 PD11       | GPIO.2           | 2   | 27  |

An overview over the SPI pinout for the Pi can be found [here](https://pinout.xyz/pinout/spi#).

In the config file the `interface` keyword is set to:

```json
    "interface": {
        "type": "spi",
        "name": "spidev0.0"
    }
```

Power up the WHITE Beet and run the application with the following command

```console
.venv/bin/python3 Application.py config_evse.json
```

### Running the application

Make sure that EVSE and EV are not physically connected on the PLC interface.

Find the MAC address printed on the label of the board in the form of i.e. c4:93:00:22:22:24. This is the MAC address of the PLC chip. To get the MAC address of the ethernet interface substract 2 of the last number of the MAC address. For the example above this would result in the MAC address c4:93:00:22:22:22 for the ethernet interface.

Update the config file accordingly (for example `config_evse.json`):

```json
  {
    "mac": "c4:93:00:22:22:22",
    "interface": {
        "type": "eth",
        "name": "eth-wb1-evse"
    },
    "portmirror": true,
    "evse": {
      ...
      ...
      ...
    }
  }
```

Now run the application, e.g.:

```console
$ sudo .venv/bin/python3 config_evse.json
```

You should see a output similar to this:

```console
Welcome to Codico WHITE Beet EVSE reference implementation
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

Now you can authorize the vehicle by typing "yes", or by just pressing `Enter`. All the parameters that are exchanged between the vehicle and the charging station are printed to the console.

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