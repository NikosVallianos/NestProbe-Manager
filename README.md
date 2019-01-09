# NestProbe-Manager
Desktop application to configure and download data from NestProbe devices.

This application is eventually intended to become a GUI desktop program.
At the moment, it is only available as a small set of python scripts:

 * nestrpobe-manager.py
 * plotter.py

## Installation
To install this program just copy either of the executable files to a
directory in your system. You will need to have python 3 installed, with
the following libraries available: pytz, serial, crc16, intelhex, ntplib, matplotlib, numpy, pandas.

## Devices
NestProbe-Manager currently works with NestProbe TL1, a 0.3℃  accuracy
temperature logger that can operate for at least six months on a CR2032
coin-cell battery. The TL1 is also an open-source project. The NestProbe TL2 is
a similar device with a 0.13℃ accuracy under development, which will also work
with NestProbe-Manager.

## Use
NestProb


Temporary text transferred from old README:
>The WSTL18 is a low cost/power/size temperature logger. Its only interface for
>setup and data acquisition is through the UART interface. It is meant to connect
>to a host computer or portable field device for initial setup and to download
>temperature log data at the end of deployment.

>While I intend to fully open-source release a GUI program to manage WSTL18
>loggers, current deadlines mean I have to resort to a quick and functional
>program to do the job. For now, this is a python (3.5+) script that will do the
>job as long as you have a python installation with the serial library installed.

