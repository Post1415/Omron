#!/usr/bin/python
#
# python Environment Sensor Observer for Linux
#
# target device : OMRON Environment Sensor (2JCIE-BL01 & BU01) in Broadcaster mode
#
# require : python-bluez
#         : fluent-logger-python (when FLUENTD_FORWARD = True in configuration)
#               $ sudo pip install fluent-logger
#         : influxdb-python (when INFLUXDB_OUTPUT = True in configuration)
#               $ sudo pip install influxdb
#               $ sudo pip install --upgrade influxdb
#
# Note: Proper operation of this sample application is not guaranteed.

import sys
import os
import argparse
import requests
import socket
from datetime import date, timedelta
import threading
import struct
import time

import sensor_beacon as envsensor
import conf
import ble
import pandas as pd
import csv

from logging.handlers import TimedRotatingFileHandler

from Magellan import *

if conf.CSV_OUTPUT:
    import logging
    import csv_logger
if conf.FLUENTD_FORWARD:
    from fluent import sender
    from fluent import event
if conf.INFLUXDB_OUTPUT:
    from influxdb import InfluxDBClient

# constant
VER = 1.2

# ystem constant
GATEWAY = socket.gethostname()

# Global variables
influx_client = None
sensor_list = []
address = []
flag_update_sensor_status = False
token = ''
COMPANY_ID = 0x2D5


def parse_events(sock, loop_count=10):
    global sensor_list
    global address
    pkt = sock.recv(255)
    
    # Raw avertise packet data from Bluez scan
    # Packet Type (1byte) + BT Event ID (1byte) + Packet Length (1byte) +
    # BLE sub-Event ID (1byte) + Number of Advertising reports (1byte) +
    # Report type ID (1byte) + BT Address Type (1byte) + BT Address (6byte) +
    # Data Length (1byte) + Data ((Data Length)byte) + RSSI (1byte)
    #
    # Packet Type = 0x04
    # BT Event ID = EVT_LE_META_EVENT = 0x3E (BLE events)
    # (All LE commands result in a metaevent, specified by BLE sub-Event ID)
    # BLE sub-Event ID = {
    #                       EVT_LE_CONN_COMPLETE = 0x01
    #                       EVT_LE_ADVERTISING_REPORT = 0x02
    #                       EVT_LE_CONN_UPDATE_COMPLETE = 0x03
    #                       EVT_LE_READ_REMOTE_USED_FEATURES_COMPLETE = 0x04
    #                       EVT_LE_LTK_REQUEST = 0x05
    #                     }
    # Number of Advertising reports = 0x01 (normally)
    # Report type ID = {
    #                       LE_ADV_IND = 0x00
    #                       LE_ADV_DIRECT_IND = 0x01
    #                       LE_ADV_SCAN_IND = 0x02
    #                       LE_ADV_NONCONN_IND = 0x03
    #                       LE_ADV_SCAN_RSP = 0x04
    #                   }
    # BT Address Type = {
    #                       LE_PUBLIC_ADDRESS = 0x00
    #                       LE_RANDOM_ADDRESS = 0x01
    #                    }
    # Data Length = 0x00 - 0x1F
    # * Maximum Data Length of an advertising packet = 0x1F

    #Check Token file exists
    #Get TokenKey from user
    if os.path.exists("/home/pi/Downloads/Token.csv"):
        token = read_token_csv()
        parsed_packet = ble.hci_le_parse_response_packet(pkt)

        if "bluetooth_le_subevent_name" in parsed_packet and \
                (parsed_packet["bluetooth_le_subevent_name"]
                    == 'EVT_LE_ADVERTISING_REPORT'):       
        
            if debug:
                for report in parsed_packet["advertising_reports"]:
                    print "----------------------------------------------------"
                    print "Found BLE device:", report['peer_bluetooth_address']
                    print "Raw Advertising Packet:"
                    print ble.packet_as_hex_string(pkt, flag_with_spacing=True,
                                                    flag_force_capitalize=True)
                    print ""
                    for k, v in report.items():
                        if k == "payload_binary":
                            continue
                        print "\t%s: %s" % (k, v)
                    print ""

            for report in parsed_packet["advertising_reports"]:
                if (ble.verify_beacon_packet(report)):
                    sensor = envsensor.SensorBeacon(
                        report["peer_bluetooth_address_s"],
                        ble.classify_beacon_packet(report),
                        GATEWAY,
                        report["payload_binary"])
                
                    index = find_sensor_in_list(sensor, sensor_list)
                    address.append(sensor.bt_address)
                
                    lock = threading.Lock()
                    lock.acquire()
                    
                    if (index != -1):  # BT Address found in sensor_list
                        if sensor.check_diff_seq_num(sensor_list[index]):
                           handling_data(sensor)
                        sensor.update(sensor_list[index])
                    else:  # new SensorBeacon
                        sensor_list.append(sensor)
                        handling_data(sensor)
                        
                    lock.release()
                    
                    if debug:
                        if index == -1:
                            pass
                    
                        else:
                            id = read_csv(sensor)
                            print ("\t--- sensor data ---")
                        
                            #Send data to Magellan
                            if id == 0:            
                                payload = '"temperature":' + sensor.debug_print()[0] + ', "humidity":' + sensor.debug_print()[1] + ', "light":' + sensor.debug_print()[2] + ', "uv":' + sensor.debug_print()[3] + ', "pressure":' + sensor.debug_print()[4] + ', "noise":' + sensor.debug_print()[5] + ', "di":' + sensor.debug_print()[6] + ', "heat":' + sensor.debug_print()[7] + ', "ax":' + sensor.debug_print()[8] + ', "ay":' + sensor.debug_print()[9] +  ', "az":' + sensor.debug_print()[10] + ', "etvoc":' + sensor.debug_print()[11] +  ', "eco2":' + sensor.debug_print()[12] + ', "si":' + sensor.debug_print()[13] + ', "pga":' + sensor.debug_print()[14] + ', "seismic":' + sensor.debug_print()[15] +  ', "vibinfo":' + sensor.debug_print()[16] + ', "battery":' + sensor.debug_print()[17] +  ', "rssi":' + sensor.debug_print()[18] + ', "distance":' + sensor.debug_print()[19] + ', "bt_address":' + sensor.debug_print()[20] + ', "sensor_type":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload + '}')
                    
                            elif id == 1:            
                                payload1 = '"temperature1":' + sensor.debug_print()[0] + ', "humidity1":' + sensor.debug_print()[1] + ', "light1":' + sensor.debug_print()[2] + ', "uv1":' + sensor.debug_print()[3] + ', "pressure1":' + sensor.debug_print()[4] + ', "noise1":' + sensor.debug_print()[5] + ', "di1":' + sensor.debug_print()[6] + ', "heat1":' + sensor.debug_print()[7] + ', "ax1":' + sensor.debug_print()[8] + ', "ay1":' + sensor.debug_print()[9] +  ', "az1":' + sensor.debug_print()[10] + ', "etvoc1":' + sensor.debug_print()[11] +  ', "eco2_1":' + sensor.debug_print()[12] + ', "si1":' + sensor.debug_print()[13] + ', "pga1":' + sensor.debug_print()[14] + ', "seismic1":' + sensor.debug_print()[15] +  ', "vibinfo1":' + sensor.debug_print()[16] + ', "battery1":' + sensor.debug_print()[17] +  ', "rssi1":' + sensor.debug_print()[18] + ', "distance1":' + sensor.debug_print()[19] + ', "bt_address1":' + sensor.debug_print()[20] + ', "sensor_type1":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload1 + '}')

                            elif id == 2:            
                                payload2 = '"temperature2":' + sensor.debug_print()[0] + ', "humidity2":' + sensor.debug_print()[1] + ', "light2":' + sensor.debug_print()[2] + ', "uv2":' + sensor.debug_print()[3] + ', "pressure2":' + sensor.debug_print()[4] + ', "noise2":' + sensor.debug_print()[5] + ', "di2":' + sensor.debug_print()[6] + ', "heat2":' + sensor.debug_print()[7] + ', "ax2":' + sensor.debug_print()[8] + ', "ay2":' + sensor.debug_print()[9] +  ', "az2":' + sensor.debug_print()[10] + ', "etvoc2":' + sensor.debug_print()[11] +  ', "eco2_2":' + sensor.debug_print()[12] + ', "si2":' + sensor.debug_print()[13] + ', "pga2":' + sensor.debug_print()[14] + ', "seismic2":' + sensor.debug_print()[15] +  ', "vibinfo2":' + sensor.debug_print()[16] + ', "battery2":' + sensor.debug_print()[17] +  ', "rssi2":' + sensor.debug_print()[18] + ', "distance2":' + sensor.debug_print()[19] + ', "bt_address2":' + sensor.debug_print()[20] + ', "sensor_type2":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload2 + '}')
                            
                            elif id == 3:            
                                payload3 = '"temperature3":' + sensor.debug_print()[0] + ', "humidity3":' + sensor.debug_print()[1] + ', "light3":' + sensor.debug_print()[2] + ', "uv3":' + sensor.debug_print()[3] + ', "pressure3":' + sensor.debug_print()[4] + ', "noise3":' + sensor.debug_print()[5] + ', "di3":' + sensor.debug_print()[6] + ', "heat3":' + sensor.debug_print()[7] + ', "ax3":' + sensor.debug_print()[8] + ', "ay3":' + sensor.debug_print()[9] +  ', "az3":' + sensor.debug_print()[10] + ', "etvoc3":' + sensor.debug_print()[11] +  ', "eco2_3":' + sensor.debug_print()[12] + ', "si3":' + sensor.debug_print()[13] + ', "pga3":' + sensor.debug_print()[14] + ', "seismic3":' + sensor.debug_print()[15] +  ', "vibinfo3":' + sensor.debug_print()[16] + ', "battery3":' + sensor.debug_print()[17] +  ', "rssi3":' + sensor.debug_print()[18] + ', "distance3":' + sensor.debug_print()[19] + ', "bt_address3":' + sensor.debug_print()[20] + ', "sensor_type3":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload3 + '}')
                            
                            elif id == 4:            
                                payload4 = '"temperature4":' + sensor.debug_print()[0] + ', "humidity4":' + sensor.debug_print()[1] + ', "light4":' + sensor.debug_print()[2] + ', "uv4":' + sensor.debug_print()[3] + ', "pressure4":' + sensor.debug_print()[4] + ', "noise4":' + sensor.debug_print()[5] + ', "di4":' + sensor.debug_print()[6] + ', "heat4":' + sensor.debug_print()[7] + ', "ax4":' + sensor.debug_print()[8] + ', "ay4":' + sensor.debug_print()[9] +  ', "az4":' + sensor.debug_print()[10] + ', "etvoc4":' + sensor.debug_print()[11] +  ', "eco2_4":' + sensor.debug_print()[12] + ', "si4":' + sensor.debug_print()[13] + ', "pga4":' + sensor.debug_print()[14] + ', "seismic4":' + sensor.debug_print()[15] +  ', "vibinfo4":' + sensor.debug_print()[16] + ', "battery4":' + sensor.debug_print()[17] +  ', "rssi4":' + sensor.debug_print()[18] + ', "distance4":' + sensor.debug_print()[19] + ', "bt_address4":' + sensor.debug_print()[20] + ', "sensor_type4":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload4 + '}')
                            
                            elif id == 5:            
                                payload5 = '"temperature5":' + sensor.debug_print()[0] + ', "humidity5":' + sensor.debug_print()[1] + ', "light5":' + sensor.debug_print()[2] + ', "uv5":' + sensor.debug_print()[3] + ', "pressure5":' + sensor.debug_print()[4] + ', "noise5":' + sensor.debug_print()[5] + ', "di5":' + sensor.debug_print()[6] + ', "heat5":' + sensor.debug_print()[7] + ', "ax5":' + sensor.debug_print()[8] + ', "ay5":' + sensor.debug_print()[9] +  ', "az5":' + sensor.debug_print()[10] + ', "etvoc5":' + sensor.debug_print()[11] +  ', "eco2_5":' + sensor.debug_print()[12] + ', "si5":' + sensor.debug_print()[13] + ', "pga5":' + sensor.debug_print()[14] + ', "seismic5":' + sensor.debug_print()[15] +  ', "vibinfo5":' + sensor.debug_print()[16] + ', "battery5":' + sensor.debug_print()[17] +  ', "rssi5":' + sensor.debug_print()[18] + ', "distance5":' + sensor.debug_print()[19] + ', "bt_address5":' + sensor.debug_print()[20] + ', "sensor_type5":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload5 + '}')
                            
                            elif id == 6:            
                                payload6 = '"temperature6":' + sensor.debug_print()[0] + ', "humidity6":' + sensor.debug_print()[1] + ', "light6":' + sensor.debug_print()[2] + ', "uv6":' + sensor.debug_print()[3] + ', "pressure6":' + sensor.debug_print()[4] + ', "noise6":' + sensor.debug_print()[5] + ', "di6":' + sensor.debug_print()[6] + ', "heat6":' + sensor.debug_print()[7] + ', "ax6":' + sensor.debug_print()[8] + ', "ay6":' + sensor.debug_print()[9] +  ', "az6":' + sensor.debug_print()[10] + ', "etvoc6":' + sensor.debug_print()[11] +  ', "eco2_6":' + sensor.debug_print()[12] + ', "si6:' + sensor.debug_print()[13] + ', "pga6":' + sensor.debug_print()[14] + ', "seismic6":' + sensor.debug_print()[15] +  ', "vibinfo6":' + sensor.debug_print()[16] + ', "battery6":' + sensor.debug_print()[17] +  ', "rssi6":' + sensor.debug_print()[18] + ', "distance6":' + sensor.debug_print()[19] + ', "bt_address6":' + sensor.debug_print()[20] + ', "sensor_type6":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload6 + '}')
                            
                            elif id == 7:            
                                payload7 = '"temperature7":' + sensor.debug_print()[0] + ', "humidity7":' + sensor.debug_print()[1] + ', "light7":' + sensor.debug_print()[2] + ', "uv7":' + sensor.debug_print()[3] + ', "pressure7":' + sensor.debug_print()[4] + ', "noise7":' + sensor.debug_print()[5] + ', "di7":' + sensor.debug_print()[6] + ', "heat7":' + sensor.debug_print()[7] + ', "ax7":' + sensor.debug_print()[8] + ', "ay7":' + sensor.debug_print()[9] +  ', "az7":' + sensor.debug_print()[10] + ', "etvoc7":' + sensor.debug_print()[11] +  ', "eco2_7":' + sensor.debug_print()[12] + ', "si7":' + sensor.debug_print()[13] + ', "pga7":' + sensor.debug_print()[14] + ', "seismic7":' + sensor.debug_print()[15] +  ', "vibinfo7":' + sensor.debug_print()[16] + ', "battery7":' + sensor.debug_print()[17] +  ', "rssi7":' + sensor.debug_print()[18] + ', "distance7":' + sensor.debug_print()[19] + ', "bt_address7":' + sensor.debug_print()[20] + ', "sensor_type7":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload7 + '}')
                            
                            elif id == 8:            
                                payload8 = '"temperature8":' + sensor.debug_print()[0] + ', "humidity8":' + sensor.debug_print()[1] + ', "light8":' + sensor.debug_print()[2] + ', "uv8":' + sensor.debug_print()[3] + ', "pressure8":' + sensor.debug_print()[4] + ', "noise8":' + sensor.debug_print()[5] + ', "di8":' + sensor.debug_print()[6] + ', "heat8":' + sensor.debug_print()[7] + ', "ax8":' + sensor.debug_print()[8] + ', "ay8":' + sensor.debug_print()[9] +  ', "az8":' + sensor.debug_print()[10] + ', "etvoc8":' + sensor.debug_print()[11] +  ', "eco2_8":' + sensor.debug_print()[12] + ', "si8":' + sensor.debug_print()[13] + ', "pga8":' + sensor.debug_print()[14] + ', "seismic8":' + sensor.debug_print()[15] +  ', "vibinfo8":' + sensor.debug_print()[16] + ', "battery8":' + sensor.debug_print()[17] +  ', "rssi8":' + sensor.debug_print()[18] + ', "distance8":' + sensor.debug_print()[19] + ', "bt_address8":' + sensor.debug_print()[20] + ', "sensor_type8":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload8 + '}')
                            
                            elif id == 9:            
                                payload9 = '"temperature9":' + sensor.debug_print()[0] + ', "humidity9":' + sensor.debug_print()[1] + ', "light9":' + sensor.debug_print()[2] + ', "uv9":' + sensor.debug_print()[3] + ', "pressure9":' + sensor.debug_print()[4] + ', "noise9":' + sensor.debug_print()[5] + ', "di9":' + sensor.debug_print()[6] + ', "heat9":' + sensor.debug_print()[7] + ', "ax9":' + sensor.debug_print()[8] + ', "ay9":' + sensor.debug_print()[9] +  ', "az9":' + sensor.debug_print()[10] + ', "etvoc9":' + sensor.debug_print()[11] +  ', "eco2_9":' + sensor.debug_print()[12] + ', "si9":' + sensor.debug_print()[13] + ', "pga9":' + sensor.debug_print()[14] + ', "seismic9":' + sensor.debug_print()[15] +  ', "vibinfo9":' + sensor.debug_print()[16] + ', "battery9":' + sensor.debug_print()[17] +  ', "rssi9":' + sensor.debug_print()[18] + ', "distance9":' + sensor.debug_print()[19] + ', "bt_address9":' + sensor.debug_print()[20] + ', "sensor_type9":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload9 + '}')
                            
                            elif id == 10:            
                                payload10 = '"temperatur10":' + sensor.debug_print()[0] + ', "humidity10":' + sensor.debug_print()[1] + ', "light10":' + sensor.debug_print()[2] + ', "uv10":' + sensor.debug_print()[3] + ', "pressure10":' + sensor.debug_print()[4] + ', "noise10":' + sensor.debug_print()[5] + ', "di10":' + sensor.debug_print()[6] + ', "heat10":' + sensor.debug_print()[7] + ', "ax10":' + sensor.debug_print()[8] + ', "ay10":' + sensor.debug_print()[9] +  ', "az10":' + sensor.debug_print()[10] + ', "etvoc10":' + sensor.debug_print()[11] +  ', "eco2_10":' + sensor.debug_print()[12] + ', "si10":' + sensor.debug_print()[13] + ', "pga10":' + sensor.debug_print()[14] + ', "seismic10":' + sensor.debug_print()[15] +  ', "vibinfo10":' + sensor.debug_print()[16] + ', "battery10":' + sensor.debug_print()[17] +  ', "rssi10":' + sensor.debug_print()[18] + ', "distance10":' + sensor.debug_print()[19] + ', "bt_address10":' + sensor.debug_print()[20] + ', "sensor_type10":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload10 + '}')
                            
                            elif id == 11:            
                                payload11 = '"temperatur11":' + sensor.debug_print()[0] + ', "humidity11":' + sensor.debug_print()[1] + ', "light11":' + sensor.debug_print()[2] + ', "uv11":' + sensor.debug_print()[3] + ', "pressure11":' + sensor.debug_print()[4] + ', "noise11":' + sensor.debug_print()[5] + ', "di11":' + sensor.debug_print()[6] + ', "heat11":' + sensor.debug_print()[7] + ', "ax11":' + sensor.debug_print()[8] + ', "ay11":' + sensor.debug_print()[9] +  ', "az11":' + sensor.debug_print()[10] + ', "etvoc11":' + sensor.debug_print()[11] +  ', "eco2_11":' + sensor.debug_print()[12] + ', "si11":' + sensor.debug_print()[13] + ', "pga11":' + sensor.debug_print()[14] + ', "seismic11":' + sensor.debug_print()[15] +  ', "vibinfo11":' + sensor.debug_print()[16] + ', "battery11":' + sensor.debug_print()[17] +  ', "rssi11":' + sensor.debug_print()[18] + ', "distance11":' + sensor.debug_print()[19] + ', "bt_address11":' + sensor.debug_print()[20] + ', "sensor_type11":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload11 + '}')
                            
                            elif id == 12:            
                                payload12 = '"temperatur12":' + sensor.debug_print()[0] + ', "humidity12":' + sensor.debug_print()[1] + ', "light12":' + sensor.debug_print()[2] + ', "uv12":' + sensor.debug_print()[3] + ', "pressure12":' + sensor.debug_print()[4] + ', "noise12":' + sensor.debug_print()[5] + ', "di12":' + sensor.debug_print()[6] + ', "heat12":' + sensor.debug_print()[7] + ', "ax12":' + sensor.debug_print()[8] + ', "ay12":' + sensor.debug_print()[9] +  ', "az12":' + sensor.debug_print()[10] + ', "etvoc12":' + sensor.debug_print()[11] +  ', "eco2_12":' + sensor.debug_print()[12] + ', "si12":' + sensor.debug_print()[13] + ', "pga12:' + sensor.debug_print()[14] + ', "seismic12":' + sensor.debug_print()[15] +  ', "vibinfo12":' + sensor.debug_print()[16] + ', "battery12":' + sensor.debug_print()[17] +  ', "rssi12":' + sensor.debug_print()[18] + ', "distance12":' + sensor.debug_print()[19] + ', "bt_address12":' + sensor.debug_print()[20] + ', "sensor_type12":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload12 + '}')
                            
                            elif id == 13:            
                                payload13 = '"temperatur13":' + sensor.debug_print()[0] + ', "humidity13":' + sensor.debug_print()[1] + ', "light13":' + sensor.debug_print()[2] + ', "uv13":' + sensor.debug_print()[3] + ', "pressure13":' + sensor.debug_print()[4] + ', "noise13":' + sensor.debug_print()[5] + ', "di13":' + sensor.debug_print()[6] + ', "heat13":' + sensor.debug_print()[7] + ', "ax13":' + sensor.debug_print()[8] + ', "ay13":' + sensor.debug_print()[9] +  ', "az13":' + sensor.debug_print()[10] + ', "etvoc13":' + sensor.debug_print()[11] +  ', "eco2_13":' + sensor.debug_print()[12] + ', "si13":' + sensor.debug_print()[13] + ', "pga13":' + sensor.debug_print()[14] + ', "seismic13":' + sensor.debug_print()[15] +  ', "vibinfo13":' + sensor.debug_print()[16] + ', "battery13":' + sensor.debug_print()[17] +  ', "rssi13":' + sensor.debug_print()[18] + ', "distance13":' + sensor.debug_print()[19] + ', "bt_address13":' + sensor.debug_print()[20] + ', "sensor_type13":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload13 + '}')
                            
                            elif id == 14:            
                                payload14 = '"temperatur14":' + sensor.debug_print()[0] + ', "humidity14":' + sensor.debug_print()[1] + ', "light14":' + sensor.debug_print()[2] + ', "uv14":' + sensor.debug_print()[3] + ', "pressure14":' + sensor.debug_print()[4] + ', "noise14":' + sensor.debug_print()[5] + ', "di14":' + sensor.debug_print()[6] + ', "heat14":' + sensor.debug_print()[7] + ', "ax14":' + sensor.debug_print()[8] + ', "ay14":' + sensor.debug_print()[9] +  ', "az14":' + sensor.debug_print()[10] + ', "etvoc14":' + sensor.debug_print()[11] +  ', "eco2_14":' + sensor.debug_print()[12] + ', "si14":' + sensor.debug_print()[13] + ', "pga14":' + sensor.debug_print()[14] + ', "seismic14":' + sensor.debug_print()[15] +  ', "vibinfo14":' + sensor.debug_print()[16] + ', "battery14":' + sensor.debug_print()[17] +  ', "rssi14":' + sensor.debug_print()[18] + ', "distance14":' + sensor.debug_print()[19] + ', "bt_address14":' + sensor.debug_print()[20] + ', "sensor_type14":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload14 + '}')
                            
                            elif id == 15:            
                                payload15 = '"temperatur15":' + sensor.debug_print()[0] + ', "humidity15":' + sensor.debug_print()[1] + ', "light15":' + sensor.debug_print()[2] + ', "uv15":' + sensor.debug_print()[3] + ', "pressure15":' + sensor.debug_print()[4] + ', "noise15":' + sensor.debug_print()[5] + ', "di15":' + sensor.debug_print()[6] + ', "heat15":' + sensor.debug_print()[7] + ', "ax15":' + sensor.debug_print()[8] + ', "ay15":' + sensor.debug_print()[9] +  ', "az15":' + sensor.debug_print()[10] + ', "etvoc15":' + sensor.debug_print()[11] +  ', "eco2_15":' + sensor.debug_print()[12] + ', "si15":' + sensor.debug_print()[13] + ', "pga15":' + sensor.debug_print()[14] + ', "seismic15":' + sensor.debug_print()[15] +  ', "vibinfo15":' + sensor.debug_print()[16] + ', "battery15":' + sensor.debug_print()[17] +  ', "rssi15":' + sensor.debug_print()[18] + ', "distance15":' + sensor.debug_print()[19] + ', "bt_address15":' + sensor.debug_print()[20] + ', "sensor_type15":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload15 + '}')
                            
                            elif id == 16:            
                                payload16 = '"temperatur16":' + sensor.debug_print()[0] + ', "humidity16":' + sensor.debug_print()[1] + ', "light16":' + sensor.debug_print()[2] + ', "uv16":' + sensor.debug_print()[3] + ', "pressure16":' + sensor.debug_print()[4] + ', "noise16":' + sensor.debug_print()[5] + ', "di16":' + sensor.debug_print()[6] + ', "heat16":' + sensor.debug_print()[7] + ', "ax16":' + sensor.debug_print()[8] + ', "ay16":' + sensor.debug_print()[9] +  ', "az16":' + sensor.debug_print()[10] + ', "etvoc16":' + sensor.debug_print()[11] +  ', "eco2_16":' + sensor.debug_print()[12] + ', "si16":' + sensor.debug_print()[13] + ', "pga16":' + sensor.debug_print()[14] + ', "seismic16":' + sensor.debug_print()[15] +  ', "vibinfo16":' + sensor.debug_print()[16] + ', "battery16":' + sensor.debug_print()[17] +  ', "rssi16":' + sensor.debug_print()[18] + ', "distance16":' + sensor.debug_print()[19] + ', "bt_address16":' + sensor.debug_print()[20] + ', "sensor_type16":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload16 + '}')
                            
                            elif id == 17:            
                                payload17 = '"temperatur17":' + sensor.debug_print()[0] + ', "humidity17":' + sensor.debug_print()[1] + ', "light17":' + sensor.debug_print()[2] + ', "uv17":' + sensor.debug_print()[3] + ', "pressure17":' + sensor.debug_print()[4] + ', "noise17":' + sensor.debug_print()[5] + ', "di17":' + sensor.debug_print()[6] + ', "heat17":' + sensor.debug_print()[7] + ', "ax17":' + sensor.debug_print()[8] + ', "ay17":' + sensor.debug_print()[9] +  ', "az17":' + sensor.debug_print()[10] + ', "etvoc17":' + sensor.debug_print()[11] +  ', "eco2_17":' + sensor.debug_print()[12] + ', "si17":' + sensor.debug_print()[13] + ', "pga17":' + sensor.debug_print()[14] + ', "seismic17":' + sensor.debug_print()[15] +  ', "vibinfo17":' + sensor.debug_print()[16] + ', "battery17":' + sensor.debug_print()[17] +  ', "rssi17":' + sensor.debug_print()[18] + ', "distance17":' + sensor.debug_print()[19] + ', "bt_address17":' + sensor.debug_print()[20] + ', "sensor_type17":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload17 + '}')
                            
                            elif id == 18:            
                                payload18 = '"temperatur18":' + sensor.debug_print()[0] + ', "humidity18":' + sensor.debug_print()[1] + ', "light18":' + sensor.debug_print()[2] + ', "uv18":' + sensor.debug_print()[3] + ', "pressure18":' + sensor.debug_print()[4] + ', "noise18":' + sensor.debug_print()[5] + ', "di18":' + sensor.debug_print()[6] + ', "heat18":' + sensor.debug_print()[7] + ', "ax18":' + sensor.debug_print()[8] + ', "ay18":' + sensor.debug_print()[9] +  ', "az18":' + sensor.debug_print()[10] + ', "etvoc18":' + sensor.debug_print()[11] +  ', "eco2_18":' + sensor.debug_print()[12] + ', "si18":' + sensor.debug_print()[13] + ', "pga18":' + sensor.debug_print()[14] + ', "seismic18":' + sensor.debug_print()[15] +  ', "vibinfo18":' + sensor.debug_print()[16] + ', "battery18":' + sensor.debug_print()[17] +  ', "rssi18":' + sensor.debug_print()[18] + ', "distance18":' + sensor.debug_print()[19] + ', "bt_address18":' + sensor.debug_print()[20] + ', "sensor_type18":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload18 + '}')
                            
                            elif id == 19:            
                                payload19 = '"temperatur19":' + sensor.debug_print()[0] + ', "humidity19":' + sensor.debug_print()[1] + ', "light19":' + sensor.debug_print()[2] + ', "uv19":' + sensor.debug_print()[3] + ', "pressure19":' + sensor.debug_print()[4] + ', "noise19":' + sensor.debug_print()[5] + ', "di19":' + sensor.debug_print()[6] + ', "heat19":' + sensor.debug_print()[7] + ', "ax19":' + sensor.debug_print()[8] + ', "ay19":' + sensor.debug_print()[9] +  ', "az19":' + sensor.debug_print()[10] + ', "etvoc19":' + sensor.debug_print()[11] +  ', "eco2_19":' + sensor.debug_print()[12] + ', "si19":' + sensor.debug_print()[13] + ', "pga19":' + sensor.debug_print()[14] + ', "seismic19":' + sensor.debug_print()[15] +  ', "vibinfo19":' + sensor.debug_print()[16] + ', "battery19":' + sensor.debug_print()[17] +  ', "rssi19":' + sensor.debug_print()[18] + ', "distance19":' + sensor.debug_print()[19] + ', "bt_address19":' + sensor.debug_print()[20] + ', "sensor_type19":' + sensor.debug_print()[21]
                                magel.post(token, \
                                                '{' + payload19 + '}')
                            
                    else:
                        pass
            else:
                pass
        else:
            pass
    return


# data handling
def handling_data(sensor):
    if conf.INFLUXDB_OUTPUT:
        sensor.upload_influxdb(influx_client)
    if conf.FLUENTD_FORWARD:
        sensor.forward_fluentd(event)
    if conf.CSV_OUTPUT:
        log.info(sensor.csv_format())
        
# check timeout sensor and update flag
def eval_sensor_state():
    global flag_update_sensor_status
    global sensor_list
    nowtick = datetime.datetime.now()
    for sensor in sensor_list:
        if (sensor.flag_active):
            pastSec = (nowtick - sensor.tick_last_update).total_seconds()
            if (pastSec > conf.INACTIVE_TIMEOUT_SECONDS):
                if debug:
                    print "timeout sensor : " + sensor.bt_address
                sensor.flag_active = False
    flag_update_sensor_status = True
    timer = threading.Timer(conf.CHECK_SENSOR_STATE_INTERVAL_SECONDS,
                            eval_sensor_state)
    timer.setDaemon(True)
    timer.start()


def print_sensor_state():
    print "----------------------------------------------------"
    print ("sensor status : %s (Intvl. %ssec)" % (datetime.datetime.today(),
           conf.CHECK_SENSOR_STATE_INTERVAL_SECONDS))
    for sensor in sensor_list:
        print " " + sensor.bt_address, ": %s :" % sensor.sensor_type, \
            ("ACTIVE" if sensor.flag_active else "DEAD"), \
            "(%s)" % sensor.tick_last_update
    print ""


#  Utility function ###
def return_number_packet(pkt):
    myInteger = 0
    multiple = 256
    for c in pkt:
        myInteger += struct.unpack("B", c)[0] * multiple
        multiple = 1
    return myInteger


def return_string_packet(pkt):
    myString = ""
    for c in pkt:
        myString += "%02x" % struct.unpack("B", c)[0]
    return myString


def find_sensor_in_list(sensor, List):
    index = -1
    count = 0
    for i in List:
        if sensor.bt_address == i.bt_address:
           index = count
           break
        else:
            count += 1
    
    return index

#Crete csv file
def write_csv():
    x = -1
    count = 0
    n = 0
    num = 0
    filelog = csv.writer(open("/home/pi/omron_sensor/envsensor-observer-py/envsensor-observer-py/bt_address.csv", "w"), delimiter=',', quoting=csv.QUOTE_NONE)
    
    filelog.writerow(["Address", "Id"])
    for i in sensor_list:
        if i.bt_address == address:
           x = count
           n += 1
        if i.bt_address == "" and n == 0:
           i.bt_address = address
           break
        filelog.writerow([str(i.bt_address), num])
        num += 1
    
#Read csv file to sort address
def read_csv(sensor):
    if not os.path.isfile("/home/pi/omron_sensor/envsensor-observer-py/envsensor-observer-py/bt_address.csv"):
        write_csv()
    else:
        df = pd.read_csv("/home/pi/omron_sensor/envsensor-observer-py/envsensor-observer-py/bt_address.csv")
        input = sensor.bt_address
        if df[df['Address'] == input].empty:
            for i in range(len(df)):
                num = i + 1
            df.loc[df.index.max()+1] = [input, num]
            df.to_csv("/home/pi/omron_sensor/envsensor-observer-py/envsensor-observer-py/bt_address.csv", index=False)
        id = df[df['Address'] == input].Id.values[0]
        return id

#Read csv file for get tokenkey
def read_token_csv():
    df = pd.read_csv("/home/pi/Downloads/Token.csv")
    token = df['TokenKey'].values[0]
    return token

# init fluentd interface
def init_fluentd():
    sender.setup(conf.FLUENTD_TAG, host=conf.FLUENTD_ADDRESS,
                 port=conf.FLUENTD_PORT)


# create database on influxdb
def create_influx_database():
    v = "q=CREATE DATABASE " + conf.FLUENTD_INFLUXDB_DATABASE + "\n"
    uri = ("http://" + conf.FLUENTD_INFLUXDB_ADDRESS + ":" +
           conf.FLUENTD_INFLUXDB_PORT_STRING + "/query")
    r = requests.get(uri, params=v)
    if debug:
        print "-- create database : " + str(r.status_code)


# command line argument
def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', help='debug mode',
                        action='store_true')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + str(VER))
    args = parser.parse_args()
    return args



# main function
if __name__ == "__main__":
    
    magel = Magellan()
    magel.begin('/dev/ttyUSB0', 9600)
    
    try:
        flag_scanning_started = False

        # process command line arguments
        debug = False
        args = arg_parse()
        if args.debug:
            debug = True

        # reset bluetooth functionality
        try:
            if debug:
                print "-- reseting bluetooth device"
            ble.reset_hci()
            if debug:
                print "-- reseting bluetooth device : success"
        except Exception as e:
            print "error enabling bluetooth device"
            print str(e)
            sys.exit(1)

        # initialize cloud (influxDB) output interface
        try:
            if conf.INFLUXDB_OUTPUT:
                if debug:
                    print "-- initialize influxDB interface"
                influx_client = InfluxDBClient(conf.INFLUXDB_ADDRESS,
                                               conf.INFLUXDB_PORT,
                                               conf.INFLUXDB_USER,
                                               conf.INFLUXDB_PASSWORD,
                                               conf.INFLUXDB_DATABASE)
                influx_client.create_database(conf.INFLUXDB_DATABASE)
                if debug:
                    print "-- initialize influxDB interface : success"
        except Exception as e:
            print "error initializing influxDB output interface"
            print str(e)
            sys.exit(1)

        # initialize fluentd forwarder
        try:
            if conf.FLUENTD_FORWARD:
                if debug:
                    print "-- initialize fluentd"
                init_fluentd()
                # create database when using influxDB through fluentd.
                if conf.FLUENTD_INFLUXDB:
                    create_influx_database()
                if debug:
                    print "-- initialize fluentd : success"
        except Exception as e:
            print "error initializing fluentd forwarder"
            print str(e)
            sys.exit(1)

        # initialize csv output interface
        try:
            if conf.CSV_OUTPUT:
                if debug:
                    print "-- initialize csv logger"

                if not os.path.isdir(conf.CSV_DIR_PATH):
                    os.makedirs(conf.CSV_DIR_PATH)
                csv_path = conf.CSV_DIR_PATH + "/env_sensor_log.csv"
                # create time-rotating log handler
                loghndl = csv_logger.CSVHandler(csv_path, 'midnight', 1)
                form = '%(message)s'
                logFormatter = logging.Formatter(form)
                loghndl.setFormatter(logFormatter)

                # create logger
                log = logging.getLogger('CSVLogger')
                loghndl.configureHeaderWriter(envsensor.csv_header(), log)
                log.addHandler(loghndl)
                log.setLevel(logging.INFO)
                log.info(envsensor.csv_header())

                if debug:
                    print "-- initialize csv logger : success"
        except Exception as e:
            print "error initializing csv output interface"
            print str(e)
            sys.exit(1)

        # initialize bluetooth socket
        try:
            if debug:
                print "-- open bluetooth device"
            sock = ble.bluez.hci_open_dev(conf.BT_DEV_ID)
            if debug:
                print "-- ble thread started"
        except Exception as e:
            print "error accessing bluetooth device: ", str(conf.BT_DEV_ID)
            print str(e)
            sys.exit(1)

        # set ble scan parameters
        try:
            if debug:
                print "-- set ble scan parameters"
            ble.hci_le_set_scan_parameters(sock)
            if debug:
                print "-- set ble scan parameters : success"
        except Exception as e:
            print "failed to set scan parameter!!"
            print str(e)
            sys.exit(1)

        # start ble scan
        try:
            if debug:
                print "-- enable ble scan"
            ble.hci_le_enable_scan(sock)
            if debug:
                print "-- ble scan started"
        except Exception as e:
            print "failed to activate scan!!"
            print str(e)
            sys.exit(1)

        flag_scanning_started = True
        print "envsensor_observer : complete initialization"
        print ""

        # activate timer for sensor status evaluation
        timer = threading.Timer(conf.CHECK_SENSOR_STATE_INTERVAL_SECONDS,
                                eval_sensor_state)
        timer.setDaemon(True)
        timer.start()

        # preserve old filter setting
        old_filter = sock.getsockopt(ble.bluez.SOL_HCI,
                                     ble.bluez.HCI_FILTER, 14)
        # perform a device inquiry on bluetooth device #0
        # The inquiry should last 8 * 1.28 = 10.24 seconds
        # before the inquiry is performed, bluez should flush its cache of
        # previously discovered devices
        flt = ble.bluez.hci_filter_new()
        ble.bluez.hci_filter_all_events(flt)
        ble.bluez.hci_filter_set_ptype(flt, ble.bluez.HCI_EVENT_PKT)
        sock.setsockopt(ble.bluez.SOL_HCI, ble.bluez.HCI_FILTER, flt)

        while True:
            
            # parse ble event
            parse_events(sock)
            if flag_update_sensor_status:
                print_sensor_state()
                flag_update_sensor_status = False
                
        

    except Exception as e:
        print "Exception: " + str(e)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if flag_scanning_started:
            # restore old filter setting
            sock.setsockopt(ble.bluez.SOL_HCI, ble.bluez.HCI_FILTER,
                            old_filter)
            ble.hci_le_disable_scan(sock)
        print "Exit"
        
    magel.close()