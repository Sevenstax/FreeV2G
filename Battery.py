import time

class Battery():

    def __init__(self):
        print("[Battery] __init__:")
        self.lastCalcTime = 0
        self.timeStep = 100000

        self.charging = False
        self.full = False
        self.capacity = 50000
        self.fullSoC = 100
        self.batteryLevel = 0
        self.soc = 0

        self.reportedVoltageLevel = 0
        self.reportedCurrentLevel = 0
        self.maximumCurrentLimit = 100
        self.maximumPowerLimit = 5000
        self.maximumVoltageLimit = 70
        self.targetCurrent = 80
        self.targetVoltage = 60
        self.targetVoltageDelta = 10
        self.maxCurrentAC = 0
        self.maxVoltageAC = 0
        self.minCurrentAC = 0

        self.request = 0
        self.remainingTimeToBulkSoc = 0
        self.remainingTimeToFullSoc = 0
        self.resssoc = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def __del__(self):
        pass

    def _initialize(self):
        pass

    def __str__(self) -> str:
        ret = ""
        ret += "*******************\n"
        ret += "Battery\n"
        ret += "\t.lastCalcTime:\t" + str(self.lastCalcTime) + "\n"
        ret += "\t.reportedVoltageLevel:\t" + str(self.reportedVoltageLevel) + "\n"
        ret += "\t.reportedCurrentLevel:\t" + str(self.reportedCurrentLevel) + "\n"
        ret += "\t.maximumVoltageLimit:\t" + str(self.maximumVoltageLimit) + "\n"
        ret += "\t.maximumCurrentLimit:\t" + str(self.maximumCurrentLimit) + "\n"
        ret += "\t.maximumPowerLimit:\t" + str(self.maximumPowerLimit) + "\n"
        ret += "\t.targetVoltage:\t" + str(self.targetVoltage) + "\n"
        ret += "\t.targetCurrent:\t" + str(self.targetCurrent) + "\n"
        ret += "\t.capacity:\t" + str(self.capacity) + "\n"
        ret += "\t.fullSoC:\t" + str(self.fullSoC) + "\n"
        ret += "\t.batteryLevel:\t" + str(self.batteryLevel) + "\n"
        ret += "\t.soc:\t\t" + str(self.soc) + "\n"
        ret += "\t.full:\t\t" + str(self.full) + "\n"
        ret += "\t.charging:\t" + str(self.charging) + "\n"
        ret += "*******************\n"
        return ret
        
    def setCharging(self, charging):
        self.charging = charging

    def setCapacity(self, capacity):
        self.capacity = capacity

    def setFullSoC(self, soc):
        self.fullSoC = soc

    def setBatteryLevel(self, batteryLevel):
        self.batteryLevel = batteryLevel
        self.soc = int((self.batteryLevel / self.capacity) * 100)

    def setSOC(self, soc):
        self.soc = soc
        self.batteryLevel = soc / 100.0 * self.capacity

    def setReportedVoltageLevel(self, reportedVoltageLevel):
        self.reportedVoltageLevel = reportedVoltageLevel

    def setReportedCurrentLevel(self, reportedCurrentLevel):
        self.reportedCurrentLevel = reportedCurrentLevel

    def setMaximumCurrentLimit(self, maximumCurrentLimit):
        self.maximumCurrentLimit = maximumCurrentLimit

    def setMaximumVoltageLimit(self, maximumVoltageLimit):
        self.maximumVoltageLimit = maximumVoltageLimit

    def setMaximumPowerLimit(self, maximumPowerLimit):
        self.maximumPowerLimit = maximumPowerLimit

    def setTargetCurrent(self, targetCurrent):
        self.targetCurrent = targetCurrent

    def setTargetVoltage(self, targetVoltage):
        self.targetVoltage = targetVoltage
        
    def setMaxCurrentAC(self, maxCurrentAC):
        self.maxCurrentAC = maxCurrentAC

    def setMaxVoltageAC(self, maxVoltageAC):
        self.maxVoltageAC = maxVoltageAC

    def setMinCurrentAC(self, minCurrentAC):
        self.minCurrentAC = minCurrentAC

    def setRequest(self, request):
        self.request = request

    def setResssoc(self, resssoc):
        self.resssoc = resssoc

    def getCharging(self):
        return self.charging

    def getCapacity(self):
        return self.capacity

    def getFullSoC(self):
        return self.fullSoC

    def getBatteryLevel(self):
        return self.batteryLevel

    def getSoC(self):
        return self.soc

    def getReportedVoltageLevel(self):
        return self.reportedVoltageLevel

    def getReportedCurrentLevel(self):
        return self.reportedCurrentLevel

    def getMaximumCurrentLimit(self):
        return self.maximumCurrentLimit

    def getMaximumVoltageLimit(self):
        return self.maximumVoltageLimit

    def getMaximumPowerLimit(self):
        return self.maximumPowerLimit

    def getTargetCurrent(self):
        return self.targetCurrent

    def getTargetVoltage(self):
        return self.targetVoltage
        
    def getMaxCurrentAC(self):
        return self.maxCurrentAC

    def getMaxVoltageAC(self):
        return self.maxVoltageAC

    def getMinCurrentAC(self):
        return self.minCurrentAC

    def getRequest(self):
        return self.request

    def getResssoc(self):
        return self.resssoc

    def statusStartCharging(self):
        startCharging = False
        minVoltage = self.targetVoltage - self.targetVoltageDelta
        maxVoltage = self.targetVoltage + self.targetVoltageDelta
        if((self.reportedVoltageLevel > minVoltage) and (self.reportedVoltageLevel < maxVoltage)):
            startCharging = True
            self.startCharging = True
        return startCharging

    def statusStopCharging(self):
        stopCharging = False
        currentBatteryLevel = self.batteryLevel / self.capacity * 100.0
        if(currentBatteryLevel >= self.fullSoC):
            stopCharging = True
        return stopCharging

    def tickSimulation(self):
        ticked = False
        present = time.time_ns() // 1000
        if((present - self.lastCalcTime) > self.timeStep):
            ticked = True
            self.lastCalcTime = present
            if(self.charging == True and self.soc < self.fullSoC):
                energy = self.reportedVoltageLevel * self.reportedCurrentLevel
                energy *= self.timeStep / 1000.0 / 3600.0
                self.batteryLevel += energy
                self.soc = int((self.batteryLevel / self.capacity) * 100)
                if((self.full == False) and (self.batteryLevel > self.capacity)):
                    self.batteryLevel = self.capacity
                    self.full = True
                print(str(self))

        return ticked