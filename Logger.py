import datetime
import re

class Logger():
    def __init__(self):
        self.fileName = re.sub('[- :.]', '_', str(datetime.datetime.now()))[:-7]

    def log(self, logString):
        print(logString)
        filename = "log_{}".format(self.fileName)
        file = open(filename, "a")
        file.writelines(logString + "\n")
        file.close()

