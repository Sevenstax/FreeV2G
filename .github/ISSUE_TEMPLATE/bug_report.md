---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

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
