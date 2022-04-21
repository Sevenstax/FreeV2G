     oooooooooooo                              oooooo     oooo   .oooo.     .oooooo.    
     `888'     `8                               `888.     .8'  .dP""Y88b   d8P'  `Y8b   
      888         oooo d8b  .ooooo.   .ooooo.    `888.   .8'         ]8P' 888           
      888oooo8    `888""8P d88' `88b d88' `88b    `888. .8'        .d8P'  888           
      888    "     888     888ooo888 888ooo888     `888.8'       .dP'     888     ooooo 
      888          888     888    .o 888    .o      `888'      .oP     .o `88.    .88'  
     o888o        d888b    `Y8bod8P' `Y8bod8P'       `8'       8888888888  `Y8bood8P'   

## INTRODUCTION

FreeV2G is a reference implementation in python to control the 8DEVICES WHITE beet ISO15118 EI EVSE module. For more information about the WHITE beet module please visit https://www.codico.com/de/white-beet-ei-evse-embedded-iso15118-module. An evaulation board for this module can be found here:
https://www.codico.com/en/wb-carrier-board-ei-evse-embedded-iso15118.

For **Whitebeet EVSE firmware version >= 2.0.0** please checkout the plug and charge branch:
https://github.com/Sevenstax/FreeV2G/tree/plug_and_charge

The following table has information about the relationship between Whitebeet EVSE firmware versions and FreeV2G.

| Whitebeet Version | FreeV2G Tag |
| - | - |
| V01_01_06 | [EVSE_v1.1.6_1](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v1.1.6_1) |
| V01_01_07 | [EVSE_v1.1.7_0](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v1.1.7_0) |
| V02_00_00 | [EVSE_v2.0.0_0](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v2.0.0_0) |
| V02_00_01 | [EVSE_v2.0.1_0](https://github.com/Sevenstax/FreeV2G/tree/EVSE_v2.0.1_0) |

The following table has information about the relationship between Whitebeet EV firmware and FreeV2G for EV.

| Whitebeet Version | FreeV2G Tag |
| - | - |
| V01_00_04 | [EV_v1.0.4_0](https://github.com/Sevenstax/FreeV2G/tree/EV_v1.0.4_0) |

Actual Whitebeet SW updates for EVSE abd EV are available at **CODICO PLC documentation area** https://downloads.codico.com/misc/plc under NDA.

## FEATURES

The main feature of this implementation is the parsing of the protocol used to communicate with the WHITE beet. Other features are the WHITE beet class which answers the parameter requests of the WHITE beet and the charger class which simulates the voltage and current based on the given parameters during initialization and on the parameters received by the EV during the charging process.

### Control Pilot

There is a basic control pilot implemenation which detects the EV plugin and sets the duty cycle to 5% when the module is ready to receive the SLAC request message from the EV. When the charging session is finished the oscillator shuts down automatically.

### SLAC

SLAC is performed automatically by the WHITE beet. A notification is received and the application is ready for high-level communication.

#### V2G High-Level Communication

When SLAC was succefully performed the EVSE and the EV are in same network and the high-level communication can be started. The EV will try to discover the EVSE with the SDP protocol and will then connect to the EVSE. The EVSE will choose one of the protocols the EV provided and a V2G session will be started. The service discovery, charge parameter discovery and authorization is performed and the charging loop is started. The EV will continue to charge until it decides to stop the session.

## GETTING FreeV2G

To get started first clone the repository

```console
$ git clone https://github.com/SEVENSTAX/FreeV2G
```

This will get you the newest version of the repository.
Please make sure to install scapy. The simplest way is using pip to install it.

```console
$ pip install scapy
```

## GETTING STARTED

Make sure that EVSE and EV are not physically connected on the PLC interface.

Run the Application by typing (it is necessary to provide actual STM32 ETH MAC address printed out on the label of Evaluation board)

```console
$ python3 Application.py "eth0" -m c4:93:00:22:22:22 -r EVSE
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
## EV support

Run the application in EV mode by typing

```console
$ python3 Application.py "eth0" -m c4:93:00:33:33:33 -r EV
```

## Configuration file

You can set the configuration via a configuration file in json format.

**Currently only EV mode supports a configuration file.**

Run the application with configuration file

```console
$ python3 Application.py "eth0" -m c4:93:00:33:33:33 -r EV -c $PATH_TO_CONFIG_FILE
```

If no path is given the configuration file defaults to ./ev.json. An example configuration can be found in ev.json.
