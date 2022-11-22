import time

class Charger():

    def __init__(self):
        self.timestamp_last_calc_u = time.time_ns() / 1000000
        self.timestamp_last_calc_i = time.time_ns() / 1000000
        self.present_voltage = 0
        self.present_current = 0
        self.delta_u = 0
        self.delta_i = 0
        self.max_current = 0
        self.min_current = 0
        self.max_voltage = 0
        self.min_voltage = 0
        self.max_power = 0
        self.ev_max_current = 0
        self.ev_min_current = 0
        self.ev_max_power = 0
        self.ev_min_power = 0
        self.ev_max_voltage = 0
        self.ev_min_voltage = 0
        self.ev_target_voltage = 0
        self.ev_target_current = 0
        self.stopped = True

    def _calcEvsePresentVoltage(self):
        """
        Calculates the present voltage at the current point in time, based on the given delta_u and
        the minimum and maximum values of the EVSE and EV.
        """
        delta_t = (time.time_ns() / 1000000) - self.timestamp_last_calc_u
        self.timestamp_last_calc_u = time.time_ns() / 1000000
        if self.stopped:
            self.present_voltage -= self.delta_u * delta_t
            self.present_voltage = max(self.present_voltage, 0)
        elif self.ev_target_voltage > self.present_voltage:
            self.present_voltage += self.delta_u * delta_t
            self.present_voltage = min(self.present_voltage, self.max_voltage, self.ev_target_voltage)
        elif self.ev_target_voltage < self.present_voltage:
            self.present_voltage -= self.delta_u * delta_t
            self.present_voltage = max(self.present_voltage, self.min_voltage, self.ev_target_voltage)
        else:
            # Target voltage already reached
            pass

    def _calcEvsePresentCurrent(self):
        """
        Calculates the present current at the current point in time, based on the given delta_i and
        the minimum and maximum values of the EVSE and EV.
        """
        delta_t = (time.time_ns() / 1000000) - self.timestamp_last_calc_i
        self.timestamp_last_calc_i = time.time_ns() / 1000000
        if self.stopped:
            self.present_current -= self.delta_i * delta_t
            self.present_current = max(self.present_current, 0)
        elif self.ev_target_current > self.present_current:
            self.present_current += self.delta_i * delta_t
            self.present_current = min(self.present_current, self.max_current, self.ev_target_current)
        elif self.ev_target_current < self.present_current:
            self.present_current -= self.delta_i * delta_t
            self.present_current = max(self.present_current, self.min_current, self.ev_target_current)
        else:
            # Target current already reached
            pass

    def start(self):
        """
        Starts the charger.
        """
        self.stopped = False

    def stop(self):
        """
        Stops the charger by setting target voltage and current to 0.
        """
        self.ev_target_voltage = 0
        self.ev_target_current = 0
        self.stopped = True

    def setEvseMaxCurrent(self, value):
        self.max_current = value

    def setEvseMinCurrent(self, value):
        self.min_current = value

    def setEvseMaxVoltage(self, value):
        self.max_voltage = value

    def setEvseMinVoltage(self, value):
        self.min_voltage = value

    def setEvseMaxPower(self, value):
        self.max_power = value

    def setEvseDeltaVoltage(self, value):
        self.delta_u = value

    def setEvseDeltaCurrent(self, value):
        self.delta_i = value

    def setEvMaxCurrent(self, value):
        self.ev_max_current = value

    def setEvMinCurrent(self, value):
        self.ev_min_current = value

    def setEvMaxVoltage(self, value):
        self.ev_max_voltage = value

    def setEvMinVoltage(self, value):
        self.ev_min_voltage = value

    def setEvMinPower(self, value):
        self.ev_min_power = value

    def setEvMaxPower(self, value):
        self.ev_max_power = value

    def setEvTargetVoltage(self, voltage):
        if voltage > self.max_voltage:
            return False
        else:
            self._calcEvsePresentVoltage()
            self.ev_target_voltage = voltage
            return True

    def setEvTargetCurrent(self, current):
        if current > self.max_current:
            return False
        else:
            self._calcEvsePresentCurrent()
            self.ev_target_current = current
            return True

    def getEvseMaxCurrent(self):
        return self.max_current

    def getEvseMinCurrent(self):
        return self.min_current

    def getEvseMaxVoltage(self):
        return self.max_voltage

    def getEvseMinVoltage(self):
        return self.min_voltage

    def getEvseMaxPower(self):
        return self.max_power

    def getEvseDeltaVoltage(self):
        return self.delta_u

    def getEvseDeltaCurrent(self):
        return self.delta_i

    def getEvMaxCurrent(self):
        return self.ev_max_current

    def getEvMinCurrent(self):
        return self.ev_min_current

    def getEvMaxVoltage(self):
        return self.ev_max_voltage

    def getEvMinVoltage(self):
        return self.ev_min_voltage

    def getEvMinPower(self):
        return self.ev_min_power

    def getEvMaxPower(self):
        return self.ev_max_power

    def getEvsePresentVoltage(self):
        self._calcEvsePresentVoltage()
        return self.present_voltage

    def getEvsePresentCurrent(self):
        self._calcEvsePresentCurrent()
        return self.present_current

    def isVoltageLimitExceeded(self, voltage):
        if voltage > self.max_voltage:
            return True
        elif voltage < self.min_voltage:
            return True
        else:
            return False

    def isCurrentLimitExceeded(self, current):
        if current > self.max_current:
            return True
        elif current < self.min_current:
            return True
        else:
            return False

    def isPowerLimitExceeded(self, power):
        if power > self.max_power:
            return True
        else:
            return False