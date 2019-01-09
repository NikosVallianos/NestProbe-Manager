#!/usr/bin/python3
#
# NestProbe TL1 temperature timeseries plotter.
#
# This program opens .TL1Data files, creates a timeseries, and creates a plot.
# Multiple data files are plotted together.
#
import sys
import os.path
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as dates
import numpy as np
import pandas as pd

temp_constant = 0.00390625
# Read file into an array.

class TL1Log:
    data_filename = None
    firmware_version = None
    data_length = None
    start_datetime = None           # Datetime logger was set to logging
    timesource = None
    deferral = None
    log_start_datetime = None       # Datetime of actual log start (after deferral passed)
    interval = None
    header_crc = None
    temperatures = None
    datetimes = None
    ts = None

    def __init__(self, rawdata_filename):
        if os.path.isfile(rawdata_filename):
            self.data_filename = rawdata_filename
            with open(rawdata_filename, 'rb') as f:
                firmware_version = int.from_bytes(f.read(1), byteorder='big')
                fv_major = firmware_version >> 4
                fv_minor = firmware_version
                self.firmware_version = "%d.%d" % (fv_major, fv_minor)
                self.data_length = int((os.path.getsize(self.data_filename)-22)/2)
                self.start_datetime = datetime.datetime.strptime(f.read(14).decode('utf-8'), "%Y%m%d%H%M%S")
                self.timesource = f.read(1).decode('utf-8')
                self.deferral = int.from_bytes(f.read(2), byteorder='big')
                self.log_start_datetime = self.start_datetime + datetime.timedelta(seconds = self.deferral*8)
                self.interval = int.from_bytes(f.read(2), byteorder='big')
                self.header_crc = f.read(2)
                self.temperatures = []
                self.datetimes = []
                previous_datetime = self.log_start_datetime
                i = 0
                while i<self.data_length:
                    i+=1
                    readbytes = f.read(2)
                    if len(readbytes) < 2:          # This has to be a bug: What if there's one byte left? (Even if there isn't supposed to be).
                        break
                    temp = int.from_bytes(readbytes, byteorder='big')
                    self.temperatures.append(temp * temp_constant)
                    dt = previous_datetime + datetime.timedelta(seconds=self.interval*8)
                    self.datetimes.append(dt)
                    previous_datetime = dt
                    self.ts = pd.Series(self.temperatures, index=self.datetimes)
            self.ts = pd.Series(self.temperatures, index=self.datetimes)

        else:
            print("Wrong filename: %s" % rawdata_filename)

if __name__ == '__main__':

    fig, ax = plt.subplots()
    if len(sys.argv) > 1:
        for datafile_name in sys.argv[1:]:
            if os.path.isfile(datafile_name):
                a = TL1Log(datafile_name)
                print(datafile_name)
                plt.plot(a.ts)

# Print a summary of the data

# Plot the data

    xax = plt.gca().get_xaxis()
    xax.set_major_formatter(dates.DateFormatter('%d/%m %H:%M')) #"%H:%M"))
#
# Add a second x-axis:
#   https://stackoverflow.com/questions/10514315/how-to-add-a-second-x-axis-in-matplotlib/10517481
#   https://preinventedwheel.com/easy-python-time-series-plots-with-matplotlib/
    fig.autofmt_xdate()
    plt.show()
