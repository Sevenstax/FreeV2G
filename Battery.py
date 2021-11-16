import time


BATTERY_TIME_STEP = 1000
BATTERY_ENERGY_CAPACITY = 50000
BATTERY_TARGET_VOLTAGE = 100
BATTERY_TARGET_VOLTAGE_DELTA = 10
BATTERY_END_VALUE = 100

class Battery():


    def __init__(self):
        print("[Battery] __init__:")
        self.lastCalcTime = 0
        self.charging = False
        self.full = False
        self.batteryLevel = 0
        self.reportedVoltageLevel = 0
        self.reportedCurrentLevel = 0
        self.maximumCurrentLimit = 0
        self.maximumPowerLimit = 0
        self.maximumVoltageLimit = 0
        self.targetCurrent = 0
        self.targetVoltage = 0
        self.maxCurrentAC = 0
        self.maxVoltageAC = 0
        self.minCurrentAC = 0
        self.capacity = 0
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
        ret += "\t.voltageIn:\t" + str(self.voltageIn) + "\n"
        ret += "\t.currentIn:\t" + str(self.currentIn) + "\n"
        ret += "\t.batterylevel:\t" + str(self.batterylevel) + "\n"
        ret += "\t.voltageMaxIn:\t" + str(self.voltageMaxIn) + "\n"
        ret += "\t.currentMaxIn:\t" + str(self.currentMaxIn) + "\n"
        ret += "\t.targetVoltage:\t" + str(self.targetVoltage) + "\n"
        ret += "\t.targetPower:\t" + str(self.targetPower) + "\n"
        ret += "\t.timestep:\t" + str(self.timestep) + "\n"
        ret += "\t.full:\t\t" + str(self.full) + "\n"
        ret += "\t.charging:\t" + str(self.charging) + "\n"
        ret += "*******************\n"
        return ret
        
    def setCharging(self, charging):
        self.charging = charging

    def setBatteryLevel(self, batteryLevel):
        self.batteryLevel = batteryLevel

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

    def setCapacity(self, capacity):
        self.capacity = capacity

    def setRequest(self, request):
        self.request = request

    def setResssoc(self, resssoc):
        self.resssoc = resssoc

    def getCharging(self):
        return self.charging

    def getBatteryLevel(self):
        return self.batteryLevel

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

    def getCapacity(self):
        return self.capacity

    def getRequest(self):
        return self.request

    def getResssoc(self):
        return self.resssoc

    def statusStartCharging(self):
        startCharging = False
        minVoltage = BATTERY_TARGET_VOLTAGE - BATTERY_TARGET_VOLTAGE_DELTA
        maxVoltage = BATTERY_TARGET_VOLTAGE + BATTERY_TARGET_VOLTAGE_DELTA
        if((self.reportedVoltageLevel > minVoltage) and (self.reportedVoltageLevel < maxVoltage)):
            startCharging = True
            self.startCharging = True
        return startCharging

    def statusStopCharging(self):
        stopCharging = False
        currentBatteryLevel = self.batteryLevel / self.capacity * 100.0
        if(currentBatteryLevel >= BATTERY_END_VALUE):
            stopCharging = True
        return stopCharging

    def tickSimulation(self):
        present = time.time_ns() // 1000
        if((present - self.lastCalcTime) > BATTERY_TIME_STEP):
            self.lastCalcTime = present
            if(self.charging == True):
                energy = self.reportedVoltageLevel * self.reportedCurrentLevel
                energy *= BATTERY_TIME_STEP / 1000.0 / 3600.0
                self.batteryLevel += energy
                if((self.full == False) and (self.batteryLevel > self.capacity)):
                    self.batteryLevel = self.capacity
                    self.full = True