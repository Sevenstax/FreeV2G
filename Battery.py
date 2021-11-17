import time

class Battery():

    def __init__(self):
        self._last_calc_time = 0
        self.timestep = 100000

        self.is_charging = False
        self.is_full = False
        self.capacity = 50000
        self.full_soc = 100
        self.bulk_soc = 100
        self._batteryLevel = 0
        self._soc = 0

        self.in_voltage = 0
        self.in_current = 0
        self.max_current = 100
        self.max_power = 5000
        self.max_voltage = 300
        self.target_current = 80
        self.target_voltage = 200
        self.target_voltage_delta = 10
        self.max_current_AC = 0
        self.max_voltage_AC = 0
        self.min_current_AC = 0

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
        ret += "\t._last_calc_time:\t" + str(self._last_calc_time) + "\n"
        ret += "\t.in_voltage:\t" + str(self.in_voltage) + "\n"
        ret += "\t.in_current:\t" + str(self.in_current) + "\n"
        ret += "\t.max_voltage:\t" + str(self.max_voltage) + "\n"
        ret += "\t.max_current:\t" + str(self.max_current) + "\n"
        ret += "\t.max_power:\t" + str(self.max_power) + "\n"
        ret += "\t.target_voltage:\t" + str(self.target_voltage) + "\n"
        ret += "\t.target_current:\t" + str(self.target_current) + "\n"
        ret += "\t.capacity:\t" + str(self.capacity) + "\n"
        ret += "\t.full_soc:\t" + str(self.full_soc) + "\n"
        ret += "\t._batteryLevel:\t" + str(self._batteryLevel) + "\n"
        ret += "\t._soc:\t\t" + str(self._soc) + "\n"
        ret += "\t.full:\t\t" + str(self.is_full) + "\n"
        ret += "\t.charging:\t" + str(self.is_charging) + "\n"
        ret += "*******************\n"
        return ret

    def setBatteryLevel(self, batteryLevel):
        self._batteryLevel = batteryLevel
        self._soc = int((self._batteryLevel / self.capacity) * 100)

    def getBatteryLevel(self):
        return self._batteryLevel

    def setSOC(self, soc):
        self._soc = soc
        self._batteryLevel = soc / 100.0 * self.capacity

    def getSOC(self):
        return self._soc

    def tickSimulation(self):
        ticked = False
        present = time.time_ns() // 1000

        if((present - self._last_calc_time) > self.timestep):
            ticked = True
            self._last_calc_time = present

            # calculate SoC and battery level
            if(self.is_charging == True and self._soc < self.full_soc):
                energy = self.in_voltage * self.in_current
                energy *= self.timestep / 1000.0 / 3600.0
                self._batteryLevel += energy
                self._soc = int((self._batteryLevel / self.capacity) * 100)

                # check if battery level exceeds capacity
                if self._batteryLevel > self.capacity:
                    self._batteryLevel = self.capacity
                    self.is_full = True
                
                print(str(self))

        return ticked