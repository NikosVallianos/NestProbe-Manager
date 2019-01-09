#!/usr/bin/python3
#
    This file is part of NestProbe-Manager.

    NestProbe-Manager is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    NestProbe-Manager is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Foobar.  If not, see <https://www.gnu.org/licenses/>.
#
# Nice example for pyserial logging into a file:
# https://github.com/gskielian/Arduino-DataLogging/blob/master/PySerial/README.md
#
# You will need to do the following to use the serial port:
#    sudo usermod -a -G tty <username>
#
import sys
import struct
import math
import time
import pytz
import re
import serial
from serial.tools import list_ports
import signal
import datetime
import calendar
import pytz
import crc16            # Install with 'sudo pip3 install crc16'
import intelhex         # Install with 'sudo pip3 install intelhex'
import ntplib           # Install with 'sudo pip3 install ntplib'

# ih = intelhex.IntelHex("Readout.hex")
# ih[0]    # ... is first byte, given as an integer. Must convert to b'' before writing via serial.

dt_utc = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp())
dt_local =  datetime.datetime.fromtimestamp(datetime.datetime.now().timestamp())
local_timezone = time.tzname[0]
local_dst = time.localtime().tm_isdst
local_pytz = pytz.timezone(local_timezone)

#connected_devices = list()                  # List containing mcu ids of connected devices. Used to check re-connect within session.
# Use NTP to calculate computer clock offset to UTC.
c = ntplib.NTPClient()
try:
    ntp_object = c.request('europe.pool.ntp.org', version=4)
except:
    time_offset = 0.0
    time_method = "L"                       # 'L' stands for local.
else:
    time_offset = ntp_object.offset
    time_method = "N"                       # 'N' stands for network.
del(c, ntp_object)                          # Don't need these any more.

logging_interval_eightseconds = {   1:15,                   # 2 minutes
                                    2:75,                   # 10 minutes
                                    3:225,                  # 30 minutes
                                    4:450,                  #  1 hour
                                    5:1350,                 #  3 hours
                                    6:2700,                 #  6 hours
                                    7:5400,                 # 12 hours
                                    8:10800 }               # 24 hours

def log_event(description):
    if type(description) == type('string'):
        f = open('logfile', 'a')
        f.write( datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S: ") + description + "\n")
        f.close()

def interval_text(eightseconds):
    intext = ""
    seconds = eightseconds*8%60
    minutes = int(eightseconds*8/60) % 60
    hours = int(eightseconds*8/60/60)
    if(hours):
        intext = intext + "%d hour%s" % (hours, "s" if hours>1 else "")
    if(hours and minutes):
        intext += " "
    if(minutes):
        intext = intext + "%d minute%s" % (minutes, "s" if minutes>1 else "")
    if(minutes and seconds):
        intext += " "
    if(seconds):
        intext = intext + "%d second%s" % (seconds, "s" if seconds>1 else "")
    return(intext)

def get_ntp_time():
    c = ntplib.NTPClient()
    try:
        ltime = c.request('europe.pool.ntp.org', version=4).tx_time
    except ntplib.NTPException:
        return(0)
    return(ltime)




# Set up a handler for Ctrl+c
def control_c_handler(sig_number, frame):
    print("\n\nGoodbye and thanks for all the fish!")
    quit()

def exit_program(message="Bye bye!"):
    print(message)
    raise SystemExit

def month_name(month_number):
    if month_number >= 1 and month_number <= 12:
        return( datetime.datetime(1, month_number, 1).strftime("%B") )
    else:
        return(None)

# is_dst: Takes an abbreviated or extended time zone name (see pytz.common_timezones and pytz.all_timezones)
# and a timezone-unaware datetime, and returns whether
# ????? Is the naive_datetime here assumed to be UTC????????? Should check this!!!!!
def is_dst(zonename, naive_datetime):
    local_pytz = pytz.timezone(zonename)
    future_datetime = pytz.utc.localize(naive_datetime)
    return future_datetime.astimezone(local_pytz).dst() != datetime.timedelta(0)

# Convert a 'naive' datetime from 'zonename' to 'utc'. Returned datetime is timezone-aware.
# https://stackoverflow.com/questions/79797/how-do-i-convert-local-time-to-utc-in-python/79877#79877
def localToUtc(naive_datetime, zonename):
    local_pytz = pytz.timezone(zonename)
    local_dt = local_pytz.localize(naive_datetime)
    return(local_dt.astimezone(pytz.utc))

def utcToLocal(naive_utc_datetime, zonename):
    utc_pytz = pytz.timezone("UTC")
    local_pytz = pytz.timezone(zonename)
    utc_dt = utc_pytz.localize(naive_utc_datetime)
    return(utc_dt.astimezone(local_pytz))

# get_logging_start: As the user a series of questions about when they want to start logging in local time.
# Returns a UTC datetime to be sent to the logger.
def get_logging_start():
    while(1):
        print("\nPlease enter local date and time you would like logging to begin at.")
        print("This can be up to six days and one hour from now.")
        ltime = time.localtime()
        datetime_min = datetime.datetime.now()
        datetime_max = datetime_min + datetime.timedelta(days=6, hours=1)

        # Get the year
        if datetime_min.year == datetime_max.year:
            f_year = int(datetime_min.year)
        else:
            f_year = input("Year? (%d or %d) " % (datetime_min.year, datetime_max.year))
            if f_year.isdigit():
                f_year = int(f_year)
            else:
                continue

        # Get the month
        if datetime_min.month == datetime_max.month:
            f_mon = datetime_min.month
        else:
            f_mon = input("%s or %s? (type %d or %d) " % (month_name(datetime_min.month),
                                                            month_name(datetime_max.month),
                                                            datetime_min.month,
                                                            datetime_max.month))
            if f_mon.isdigit():
                f_mon = int(f_mon)
            else:
                continue

        # Get the day of month
        if f_mon == datetime_min.month:
            minday = datetime_min.day

            maxday = (datetime.date(f_year, f_mon+1, 1) - datetime.timedelta(days=1)).day
        else:
            minday = 1
            maxday = datetime_max.day
        f_mday = input("Day of month? (%d to %d) " % (minday, maxday))
        if f_mday.isdigit():
            f_mday = int(f_mday)
            if f_mday < minday or f_mday > maxday:
                print("\nLet's try again")
                continue
        else:
            continue

        # Get the hour (24h format)
        if f_mday == datetime_min.day and f_mon == datetime_min.month:
            minhour = datetime_min.hour
        else:
            minhour = 0

        if f_mday == datetime_max.day and f_mon == datetime_max.month:
            maxhour = datetime_max.hour
        else:
            maxhour = 23

        f_hour =    input("Hour? (%d to %d) " % (minhour, maxhour))
        if f_hour.isdigit():
            f_hour = int(f_hour)
        else:
            continue

        # Get the minute
        if f_year == datetime_min.year and f_mon == datetime_min.month and f_mday == datetime_min.day and f_hour == datetime_min.hour:
            minmin = datetime_min.minute
            maxmin = 59
        elif f_year == datetime_max.year and f_mon == datetime_max.month and f_mday == datetime_max.day and f_hour == datetime_max.hour:
            minmin = 0
            maxmin = datetime_max.minute
        else:
            minmin = 0
            maxmin = 59

        f_minute =  input("Minute? (%d to %d) " % (minmin, maxmin))
        if f_minute.isdigit():
            f_minute = int(f_minute)
        else:
            continue
        return(datetime.datetime(f_year, f_mon, f_mday, f_hour, f_minute))
#################################################### Work below here ##########################

        # Is there a daylight saving time change between now and start of logging? If so, inform user and
        # ask them if they want to proceed. If not, repeat start datetime setting.

# Get the logging interval in eightseconds from the user
def get_logging_interval():
    firstint = min(logging_interval_eightseconds.keys())
    lastint = max(logging_interval_eightseconds.keys())
    while(1):
        print("\nPlease select the temperature logging interval.")
        for i in range(firstint, lastint+1):
            print("%d:\t%s" % (i, interval_text(logging_interval_eightseconds[i])))
        print("%d:\tOther" % int(lastint+1))

        interval = input("Interval? (%d to %d) " % (firstint, lastint+1))
        if interval.isdigit():
            interval = int(interval)
            if firstint <= interval <= lastint:
                return(logging_interval_eightseconds[interval])
            elif interval == lastint+1:
                print("You can set an arbitrary interval as an integer multiplier of 8 second counts.")
                print("For example, type 900 for a 2 hour interval (900 * 8 seconds = 7200 seconds = 120 minutes = 2 hours).")
                print("Plese note that intervals under 10 minutes will lead to reduced battery lifetime.")
                interval = input("8-second multiplier (1 to 65535): ")
                if interval.isdigit():
                    interval = int(interval)
                    if 1 <= interval <= 65535:
                        return(interval)
                continue


#!/usr/bin/python3
# Instead of the host sending a 'U' to the NestProbe, this is how this should work:
# 1. While NestProbe is still in firmware, NestProbe sends a 'here's my status & ready for command' signal.
# 2. The host sends a command to update and waits for NestProbe to signal it's ready
# (provided NestProbe is not logging & has no resident data).
# 3. The NestProbe resets itself and enters bootloader section.
# 4. Bootloader notices the data cable is connected and signals host it's ready for update.
# 5. Host & NestProbe complete update.
# 6. NestProbe loads new firmware.
# 7. Host should connect to a new NestProbe and wait for a 'here's my status & ready for command' signal ...
def firmwareUpdate(filename):
    update_hex    = intelhex.IntelHex(filename)  # SuperBlinker.hex
    hexfile_size  = len(update_hex)
    hexfile_pages = math.ceil(hexfile_size/128)
    hexfile_crc   = crc16.crc16xmodem(update_hex.tobinstr(update_hex.minaddr(), update_hex.maxaddr()))
    print("Hex file %s loaded: %d bytes CRC:%s" % (filename, hexfile_size, hex(hexfile_crc)))
    # Send a string consisting of character 'U', two bytes of update size, and two bytes of update CRC16 Xmodem.
    update_info = 'U'.encode('utf-8') + hexfile_size.to_bytes(2, byteorder='big') + hexfile_crc.to_bytes(2, byteorder='big')

    ser = serial.Serial('/dev/ttyUSB0', 1000000, stopbits=2)#, timeout=4)
    x = ser.read(13)

    signature = x[0:3].hex().upper()
    serialnum = x[3:13].hex().upper()
    firmwareend = int.from_bytes(x[13:15], byteorder='big')
    mcu_crc = x[15:17].hex().upper()

    print("ID: %s Serial: %s Firmware size: %db Firmware CRC: %s" % (signature, serialnum, firmwareend, mcu_crc))
    ser.write(update_info)
    print(update_info)
    while(1):
        y = ser.read()
        requested_page = int.from_bytes(y, byteorder='big')
        if requested_page < hexfile_pages:
            ser.write(update_hex.tobinstr(requested_page*128, ((requested_page+1)*128)-1))
            print("Sent page number: %d" % requested_page)
            print(update_hex.tobinstr(requested_page*128, ((requested_page+1)*128)-1))
        elif requested_page == 0xFF:     # Termination signal; A 328PB with a bootloader cannot flash page 0xFF.
            break;
        else:
            print("Danger: Bootloader requested page out of range.")
    print("\nUpdate completed!")



#
# Running program
#
if __name__ == "__main__":
    signal.signal(signal.SIGINT, control_c_handler)        # Set handler for ctrl+c.
    version = "0.2"
    print("NestProbe TL1 Manager, version %s" % version)
    print("Copyright (C) 2017-2018 Nikos Vallianos/Wildlife Sense")
    print("This is free software under the terms of GPL v3.0. See COPYING for details.")
    print("Press Ctrl+c to exit program.")
    print("")

    #
    # Quit if there's no serial device connected.
    #
    if not list_ports.comports():
        print("No serial devices found. Please connect a serial device and try again.")
        exit_program()


    # Ask user to verify that date, time, and timezone are correct.
	# This is important as data logger users often realize log times
	# are off, especially if they've travelled to another country
	# to conduct their research or the laptop's time was off and
	# they didn't think it was important until after they looked
	# at their logger data.
	#
	#print("This program and the WSTL18 use UTC time to prevent problems with timezone")
	#print("or daylight saving time changes.")
	# Move the two lines above to the manual.
	#print("")
    # or show if timezone/dst settings are not specified
    while (1):
        #print("UTC:        %s" %time.strftime("%A %B %d %Y, %H:%M:%S", time.gmtime()) )
        print("\nYour time zone is %s. Local time is %d hours %s UTC." % (
                            time.strftime("%Z", time.localtime()),
                            int(-time.timezone/3600),
                            "ahead of" if time.timezone<0 else "behind"))
        print("You are currently %s daylight saving time." % ("in" if time.localtime().tm_isdst else "not in"))
        print("Local date: %s" % time.strftime("%B %0d %Y", time.localtime()) )
        print("Local time: %s" % time.strftime("%H:%M", time.localtime()) )
        timeok = input("\nAre these correct? (Yes/No/Repeat): " )
        if not timeok:
            continue
        if timeok[0].lower() == 'y':
            break
        elif timeok[0].lower() == 'n':
            print("Please fix your computer's time and try again.")
            exit_program()

	#
	# Show all serial ports found on this computer (that the serial library can use).
	#
	#
	# Prepare list of available actions
	#
    actions_help = [    'I: Read and show device information',
                        'D: Download data from logger',

                        'B: Begin logging immediately',
                        'F: Begin logging at a future time, up to six days and one hour from now',

                        'E: End logging',
                        'C: Clear logger (only possible after data downloaded)',
                        'X: Clear logger flags',

                        "A: Add logger(s) to this manager's collection",
                        "R: Remove logger(s) from this manager's collection",
                        'S: Write local serial number to this/these device/s',]
                        #'T: End logging, download data, and clear logger']
                        #'U: Update firmware.']

    # Create a string with all command characters listed in actions_help
    allinitials = ""
    for item in actions_help:
        allinitials += item[0]


    #
    # Show available actions to user
    #
    print("\nAvailable actions:")
    for item in actions_help:
        print(item)
    print("\nSelected action will be repeated for all loggers connected in this session.")


	#
	# User selects action
	#
    while(1):
        desired_action = input("Please select desired action [%s]: " % ''.join([i+'/' if i!=allinitials[-1] else i for i in allinitials]))
        if desired_action:
            desired_action = desired_action[0].upper()
            if desired_action in allinitials:
                break


    #
    # These actions need more user input
    #
    #
    # I,D,E,C, and T don't need any other input.
    # F needs the time to start logging
    # B and F need a logging interval
    if desired_action in "BF":
        if desired_action == "F":
            future_local_dt_naive = get_logging_start()
            future_utc_dt = localToUtc(future_local_dt_naive, local_timezone)
            print(future_local_dt_naive.strftime("\nLogging will begin at %H:%M on %B %d, %Y (+/- 8 seconds)."))
        logging_interval = get_logging_interval()

    elif desired_action == "D":
        pass
    elif desired_action == 'S':
        new_label = input("Starting label (number): ")
        if new_label.isdigit():
            new_label = int(new_label)
        # Need to ask user if the program (if it has internet access?) should upload data to nestprobe.com.
        # This will only work if the user is registered there?? Or the logger is registered?


#"""
    #if desired_action == 'B':
        #command_string = "B%s-" % time.strftime("%Y%m%d%H%M%S%Z", time.localtime())
    #elif desired_action == 'I':
        #command_string = "I-"
    #quit()
#"""
    # Show list of serial devices
    serial_devices = list_ports.comports()
    while not serial_devices:
        input("\nNo serial devices found. Please connect a serial device and press Enter.")
        serial_devices = list_ports.comports()
    if len(serial_devices) > 1:
        iternum = 1
        print("Serial devices: \n")
        for device in serial_devices:
            print(str(iternum) + ": " + device.device + "\n")
            iternum += 1
        while(1):
            device_selected = input("Please select device to use: ")
            if device_selected.strip().isdigit(): # Also check number is in available range of devices!!!!!! !!!####!!!!
                print("Selected %d" % int(device_selected))
                print(serial_devices[int(device_selected)-1])
                device_selected = serial_devices[int(device_selected)-1].device
                break
    elif len(serial_devices) == 1:
        device_selected = serial_devices[0].device


###############################################################################################
#                                                                                             #
# Ok we've got everything. Let's start connecting to the loggers.                             #
#                                                                                             #
###############################################################################################


    print("Please connect and hold cable to a WSTL18 logger.")
    # 1Mbits with 2 stopbits as set on WSTL18.
    ser = serial.Serial(device_selected, 1000000, stopbits=2)
    print("Opened " + ser.name)
    while(1):
        ser.timeout = None
        x = ser.read(34)
        model         = x[0:4].decode('utf-8')
        mcu_serial    = x[4:14].hex().upper()
        local_label   = int.from_bytes(x[14:16], byteorder='big')
        firmware_version = x[16:17].hex().upper()                   # Needs a little work.
        firmware_crc  = x[17:19].hex().upper()
        battery_level = round(1.1 * 1024 / int.from_bytes(x[19:21], byteorder='big'), 2)
        logger_flags  = int.from_bytes(x[21:23], byteorder='big')
        logger_status = x[25:26].decode('utf-8')

        if logger_status == 'L':
            data_length = int.from_bytes(x[26:28], byteorder='big')
            countdown   = int.from_bytes(x[28:30], byteorder='big')
            counter     = int.from_bytes(x[30:32], byteorder='big')
            interval    = int.from_bytes(x[32:34], byteorder='big')
        elif logger_status == 'I':
            pass
        elif logger_status == 'H':
            data_length = int.from_bytes(x[26:28], byteorder='big')
        elif logger_status == 'D':
            pass
        else:
            pass

        #if mcu_serial in connected_devices:
            #print("\nThis device was already connected in this session. Please connect another device to continue or exit.")
            #continue
        #else:
            #connected_devices.append(mcu_serial)


        if desired_action == 'I':
            print("\n")
            print("Model: "                 + model             )
            print("Serial number: "         + mcu_serial        )
            print("Local label: %05d"        % local_label       )
            print("Firmware version: "      + firmware_version  )
            print("Firmware CRC: "          + firmware_crc      )
            print("Battery voltage: %1.2fV" % battery_level     )
            print("Flags: "                 + bin(logger_flags) )
            print("Status: "                + logger_status     )

            if logger_status == 'L':
                print("Data length: %d"     % data_length       )
                print("Countdown: %d"       % countdown         )
                print("Counter: %d"         % counter           )
                print("Interval: %d"        % interval          )

        elif desired_action == 'D' and logger_status in 'LHD':
            #           01234567890123456789
            # TODO: Why did the following line reset the device?
            #ser.write('D\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0')
            ser.write('D\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0'.encode('utf-8'))
            ser.timeout = 2
            filedata = ser.read(data_length)
            print("Read %d bytes" % len(filedata))
            datetime_utc_now = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
            if local_label != 0x0000 and local_label != 0xFFFF:
                data_filename = "%05d-" % local_label + mcu_serial + datetime_utc_now + ".TL1Data"
            else:
                data_filename = mcu_serial + datetime_utc_now + ".TL1Data"
            with open(data_filename, 'wb') as mydatafile:
                mydatafile.write(filedata)
                mydatafile.close()
                print("Dumped data in file %s" % data_filename)

        elif desired_action == 'E':
            if logger_status == 'L':
                last_log_datetime = datetime.datetime.utcnow() - datetime.timedelta(seconds=counter*8)  # Datetime (UTC) at last log
                command_string =  desired_action.encode('utf-8') +                      \
                                  last_log_datetime.strftime("%Y%m%d%H%M%S").encode('utf-8') +                        \
                                  'L'.encode('utf-8') +                                     \
                                  (0).to_bytes(length=2, byteorder='big') +          \
                                  (0).to_bytes(length=2, byteorder='big')      # 2 bytes, total = 20
                ser.write(command_string)
                log_event("Logger %s (%05d) end logging." % (mcu_serial, local_label))
                print(command_string)
            else:
                print("Cannot stop a device that isn't logging.")

        elif desired_action == 'X':
            ser.write('X\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0'.encode('utf-8'))
            print("Cleared flags")

        elif desired_action == 'C':
            ser.write('C\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0'.encode('utf-8'))
            print("Cleared device memory")

        elif desired_action in 'BF':
            datetime_utc_now = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp())
            if desired_action == 'F':
                deferral_period = (future_utc_dt - datetime_utc_now).seconds / 8
            else:
                deferral_period = 0
            command_string =  desired_action.encode('utf-8') +                              \
                              datetime_utc_now.strftime("%Y%m%d%H%M%S").encode('utf-8') +   \
                              'L'.encode('utf-8') +                                         \
                              (deferral_period).to_bytes(length=2, byteorder='big') +       \
                              logging_interval.to_bytes(length=2, byteorder='big')      # 2 bytes, total = 20
            ser.write(command_string)
            print(command_string)
            log_event("Logger %s (%05d) begin logging. Deferral: %d Interval: %d" % (mcu_serial, local_label, deferral_period, logging_interval))


        elif desired_action == 'S':
            if logger_status == 'I':
                command_string = desired_action.encode('utf-8') +                       \
                                 (new_label).to_bytes(length=2, byteorder='big') +      \
                                 '\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0'.encode('utf-8')
                ser.write(command_string)
                print(command_string)
                new_label += 1
            else:
                print("You can only change label on Idle loggers.")