import time

class Battery():

    def __init__(self):
        self._last_calc_time = 0
        self.timestep = 1000

        self.is_charging = False
        self.is_full = False
        self._capacity = 50000
        self._level = 49000 
        self.full_soc = 100
        self.bulk_soc = 80
        self._soc = 0

        self.in_voltage = 0
        self.in_current = 0
        self.max_current = 100
        self.max_power = 12000
        self.max_voltage = 300
        self.target_current = 50
        self.target_voltage = 200
        self.target_voltage_delta = 10
        self.max_current_AC = 0
        self.max_voltage_AC = 0
        self.min_current_AC = 0
        self.ernergy_transfer_mode = None 

        self.setLevel(self._level)

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
        ret += "\t.in_voltage:\t\t" + str(self.in_voltage) + "\n"
        ret += "\t.in_current:\t\t" + str(self.in_current) + "\n"
        if self.ernergy_transfer_mode in [0,1,2,3]:
            ret += "\t.max_voltage:\t\t" + str(self.max_voltage) + "\n"
            ret += "\t.max_current:\t\t" + str(self.max_current) + "\n"
            ret += "\t.max_power:\t\t" + str(self.max_power) + "\n"
            ret += "\t.target_voltage:\t" + str(self.target_voltage) + "\n"
            ret += "\t.target_current:\t" + str(self.target_current) + "\n"
        elif self.ernergy_transfer_mode in [4,5]:
            ret += "\t.max_voltage_AC:\t" + str(self.max_voltage_AC) + "\n"
            ret += "\t.max_current_AC:\t" + str(self.max_current_AC) + "\n"
            ret += "\t.min_current_AC:\t" + str(self.min_current_AC) + "\n"
        else:
            ret = "Error: No Energy Transfer Mode selected!"
            return ret
        ret += "\t._capacity:\t\t" + str(self._capacity) + "\n"
        ret += "\t.full_soc:\t\t" + str(self.full_soc) + "\n"
        ret += "\t._level:\t\t" + str(self._level) + "\n"
        ret += "\t._soc:\t\t\t" + str(self._soc) + "\n"
        ret += "\t.full:\t\t\t" + str(self.is_full) + "\n"
        ret += "\t.charging:\t\t" + str(self.is_charging) + "\n"
        ret += "*******************\n"
        return ret

    def setCapacity(self, capacity):
        self._capacity = capacity
        self.setLevel(self._level)

    def getCapacity(self):
        return self._capacity

    def setLevel(self, batteryLevel):
        self._level = batteryLevel
        self._soc = int((self._level / self._capacity) * 100)

    def getLevel(self):
        return self._level

    def setSOC(self, soc):
        self._soc = soc
        self._level = soc / 100.0 * self._capacity

    def getSOC(self):
        self._soc = int((self._level / self._capacity) * 100)
        return self._soc
    
    def setEnergyTransferMode(self, mode):
        self.ernergy_transfer_mode = mode

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
                self._level += energy
                self._soc = int((self._level / self._capacity) * 100)

                # check if battery level exceeds capacity
                if self._level > self._capacity:
                    self._level = self._capacity
                    self.is_full = True
                
                print(str(self))

        return ticked