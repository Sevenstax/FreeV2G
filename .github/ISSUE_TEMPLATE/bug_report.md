---
name: Problems / Bugs
about: Create an issue if you are experience a problem with FreeV2G / Whitebeet or think you may encountered a bug.
title: ''
labels: ''
assignees: ''
---

**Before you post**
- [ ] I confirm that I've read the [guide on how to post issues](https://github.com/Sevenstax/FreeV2G/issues/304)
- [ ] I confirm that I've consulted the [wiki](https://github.com/Sevenstax/FreeV2G/wiki) about my issue

**Your Setup**
Platform: PEV / EVSE
Firmware Version: i.e. V01_00_05
Host Controller Interface: Ethernet / SPI
Host: FreeV2G (EV_v1.0.4_0) / Own Implementation

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior.

**Expected behavior**
A clear and concise description of what you expected to happen.

**Logs**
- If using the ethernet port enable the port mirror (see Whitebeet manual chapter *13.3.10 Set Port Mirror State*) and create a Wireshark log of the ethernet traffic between the host and the Whitebeet. Connect your host directly to your Whitebeet!
- If using SPI create a log file of the SPI traffic between host and Whitebeet. Currently Saleae Logic2 (preferred) and KingstVIS recordings are supported.
- Create a log of the debug port (J11 UART) of the Whitebeet.
- Attach the log files to this issue

**Additional context**
Add any other context about the problem here.
