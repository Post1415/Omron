#Magellan.py V1.0.0 NB-IoT Playground Platform.
#Support Raspberry Pi
#NB-IoT with AT command

#Develop with coap protocol reference with https://tools.ietf.org/html/rfc7252

#Support post and get method only Magellan IoT Platform https://www.aismagellan.io

import sys
import serial
import time
from enum import Enum
import datetime
import binascii

#global variable
#success = 0
#failed = 0
#retransmit = 0


class msgtype(Enum):
    con = b'40'
    non_con = b'50'
    ack = b'60'
    rst = b'70'


class methodtype(Enum):
    EMPTY = b'00'
    GET = b'01'
    POST = b'02'
    PUT = b'03'
    DELETE = b'04'


class rsptype(Enum):
    CREATED = 65,
    DELETED = 66,
    VALID = 67,
    CHANGED = 68,
    CONTENT = 69,
    CONTINUE = 95,
    BAD_REQUEST = 128,
    FORBIDDEN = 131,
    NOT_FOUND = 132,
    METHOD_NOT_ALLOWED = 133,
    NOT_ACCEPTABLE = 134,
    REQUEST_ENTITY_INCOMPLETE = 136,
    PRECONDITION_FAILED = 140,
    REQUEST_ENTITY_TOO_LARGE = 141,
    UNSUPPORTED_CONTENT_FORMAT = 143,
    INTERNAL_SERVER_ERROR = 160,
    NOT_IMPLEMENTED = 161,
    BAD_GATEWAY = 162,
    SERVICE_UNAVAILABLE = 163,
    GATEWAY_TIMEOUT = 164,
    PROXY_NOT_SUPPORTED = 165


class Magellan():
    msgtypeDict = {'40': 'confirmation', '50': 'non confirmation', '60': 'acknowleage', '70': 'reset'}
    methodtypeDict = {'00': 'EMPTY', '01': 'GET', '02': 'POST', '03': 'PUT', '04': 'DELETE'}
    rsptypeDict = {'41': 'CREATED',
                   '42': 'DELETED',
                   '43': 'VALID',
                   '44': 'CHANGED',
                   '45': 'CONTENT',
                   '5f': 'CONTINUE',
                   '80': 'BAD_REQUEST',
                   '83': 'FORBIDDEN',
                   '84': 'NOT_FOUND',
                   '85': 'METHOD_NOT_ALLOWED',
                   '86': 'NOT_ACCEPTABLE',
                   '88': 'REQUEST_ENTITY_INCOMPLETE',
                   '8c': 'PRECONDITION_FAILED',
                   '8d': 'REQUEST_ENTITY_TOO_LARGE',
                   '8f': 'UNSUPPORTED_CONTENT_FORMAT',
                   'a0': 'INTERNAL_SERVER_ERROR',
                   'a1': 'NOT_IMPLEMENTED',
                   'a2': 'BAD_GATEWAY',
                   'a3': 'SERVICE_UNAVAILABLE',
                   'a4': 'GATEWAY_TIMEOUT',
                   'a5': 'PROXY_NOT_SUPPORTED',
                   '00': 'EMPTY',
                   '01': 'GET',
                   '02': 'POST',
                   '03': 'PUT',
                   '04': 'DELETE'}

    def __init__(self):
        print('================= AIS NB-IoT Shield Magellan IoT Platform =================')
        print('=============================== For Magellan ==============================')
        self.ser = serial.Serial()
        self.coapServer = '103.20.205.85'
        self.coapPort = 5683

    def read_data_line(self):
        end = False
        rsp_AT = b''
        list_result = []

        while not end:
            if self.ser.inWaiting() > 0:
                rsp_AT = self.ser.readline()
                if rsp_AT != b'\r\n':
                    list_result.append(rsp_AT.decode('utf-8', 'ignore').replace('\r\n', ''))
                    if rsp_AT == b'OK\r\n' or rsp_AT == b'ERROR\r\n' or rsp_AT == b'+CGATT:1\r\n' \
                            or rsp_AT == b'+CGATT:0\r\n':
                        end = True
            else:
                break

        return rsp_AT

    def cmd_expect_resp(self, cmd, resp, error, timeout=1, wait_text=''):
        now = time.time()
        future = now + timeout
        print_time = now
        rsp = False
        err = False
        self.ser.write(cmd)
        while True:
            data = self.read_data_line()
            if wait_text != '' and time.time() > print_time + 1:
                print_time = time.time()
            if data == resp:
                rsp = True
                err = False
                break
            elif data == error:
                rsp = False
                err = True
                break
            else:
                pass

            if time.time() > future:
                break

        return rsp, err

    def begin(self, port, baud):
        self.ser.port = port
        self.ser.baudrate = baud

        try:
            if not self.ser.isOpen():
                print('>>Open serial port')
                self.ser.open()
            else:
                print('>>>port is opened!')
        except IOError:
            print('***Port Error!')
            pass

                            
        print('>Test AT')
        complete, Error = self.cmd_expect_resp(b'AT\r\n', b'OK\r\n', b'ERROR\r\n', 1)
        if complete:
            print('>>OK\n')
        elif Error:
            print('>>Error AT cmd\n')
        else:
            for x in range(10):
                        print('>Test AT')
                        complete, Error = self.cmd_expect_resp(b'AT\r\n', b'OK\r\n', b'ERROR\r\n', 1)
                        if complete:
                            print('>>OK\n')
                        elif Error:
                            print('>>Error AT cmd\n')
                        else:
                            print('>>F\n')
            sys.exit(1)
            return
        
        print('>>>Reboot Module')
        complete, Error = self.cmd_expect_resp(b'AT+NRB\r\n', b'OK\r\n', b'ERROR\r\n', 5)
        if complete:
            print('>>>>OK\n')
        elif Error:
            print('>>>>Error Reboot\n')
            sys.exit(1)
            return

        time.sleep(5)
        print('>Set Phone Functionality')
        complete, Error = self.cmd_expect_resp(b'AT+CFUN=1\r\n', b'OK\r\n', b'ERROR\r\n', 5)
        if complete:
            print('>>>OK\n')
            pass
        elif Error:
            print('>>>Error Set phone functionality\n')
            sys.exit(1)
            return
        time.sleep(5)

        print('>Config network parameter')
        complete, Error = self.cmd_expect_resp(b'AT+NCONFIG=AUTOCONNECT,TRUE\r\n', b'OK\r\n', b'ERROR\r\n', 1)
        if complete:
            print('>>>OK\n')
        elif Error:
            print('>>>Error Config parameter\n')
            sys.exit(1)
            return
        
        time.sleep(5)

        while True:
            x = 0
            attach = False
            print('>Command attach network')
            while not attach:
                complete, Error = self.cmd_expect_resp(b'AT+CGATT=1\r\n', b'OK\r\n', b'ERROR\r\n', 1)
                if complete:
                    print('>>>OK\n')
                    attach = True
                elif Error:
                    print('>>>Error can not attach network\n')
                    attach = False
                
            while attach:
                time.sleep(5)
                print('>>Connecting')
                complete, Error = self.cmd_expect_resp(b'AT+CGATT?\r\n', b'+CGATT:1\r\n', b'+CGATT:0\r\n', 1, '.')
                if complete:
                    print('>>>Done\n')
                    break
                elif Error:
                    print('>>>Error Timeout attach network')
                    attach = False

            if attach:
                break
            else:
                print('>>>>Restart attach!\n')

        time.sleep(5)
        print('>>Create socket')
        complete, Error = self.cmd_expect_resp(b'AT+NSOCR=DGRAM,17,5684,1\r\n', b'OK\r\n', b'ERROR\r\n')
        if complete:
            print('>>>Ready for send data\n')
        elif Error:
            print('>>>Error can not create socket\n')
            return

    def packmsg(self, coapserver, port, coaptype, method, msgID, token, payload):
        mid = "%4.4x" % (msgID)
        hexasciiToken = ''.join(r'{0:x}'.format(ord(c)) for c in token)
        hexPayloadascii = ''.join(r'{0:x}'.format(ord(d)) for d in payload)

        if len(token) > 13:
            option_len = len(token) - 13
            LOW_option = "%2.2x" % (option_len)
            HI_option = "0d"
            path = HI_option + LOW_option
            option_path = path.encode("utf-8")
        else:
            option_len = len(token)
            path = "%2.2x" % (option_len)
            option_path = path.encode("utf-8")

        if coaptype == msgtype.ack or coaptype == msgtype.rst:
            msg = coaptype.value + \
                  method.value + \
                  mid.encode("utf-8")
        else:
            msg = coaptype.value + \
                  method.value + \
                  mid.encode("utf-8") + \
                  b'b54e42496f54' + \
                  option_path + \
                  hexasciiToken.encode("utf-8") + \
                  b'ff' + \
                  hexPayloadascii.encode("utf-8")

        if int(len(msg)/ 2) <= 512 :
            AT_msg = b'AT+NSOST=0' + \
                     b',' + \
                     coapserver.encode("utf-8") + \
                     b',' + \
                     str(port).encode("utf-8") + \
                     b',' + \
                     str(int(len(msg) / 2)).encode("utf-8") + \
                     b',' + \
                     msg
            return AT_msg

        else:
            print('Error payload more than 512')
            sys.exit(1)

    def send(self, coaptype, method, token, payload, retransmit, re_msgID):
        now = datetime.datetime.now()
        byte1 = str(now.minute)
        byte2 = str(now.second)
        if retransmit:
            Message_ID = re_msgID
        else:
            Message_ID = int(byte1 + byte2)
        AT_send = self.packmsg(self.coapServer, self.coapPort, coaptype, method, Message_ID, token, payload) + b'\r\n'
        self.ser.write(AT_send)
        return Message_ID

    def splitCount(self, s, count):
        # return [''.join(x) for x in zip(*[list(s[z::count]) for z in range(count)])]
        return [s[i:i+count] for i in range(0, len(s), count)]
    def unpack(self, rspdata, send_msgID, send_token):
        rcv_rsp = False
        print()
        print('Response from server')

        mid = rspdata[2] + rspdata[3]

        if len(rspdata) > 4:
            if rspdata[4].lower() == 'ff':
                hexPayload = ''.join(rspdata[5:])
                payload = binascii.unhexlify(hexPayload).decode('utf8')
                print ">>", payload, "\n"

        if self.msgtypeDict[rspdata[0]] == 'confirmation':
            self.send(msgtype.ack, methodtype.EMPTY, send_token, '', False, 0)
            AT_response = self.read_data_line()
            if b'OK' in AT_response:
                print('confirmation ack')
            elif b'ERROR' in AT_response:
                print('AT ERROR')
        elif self.msgtypeDict[rspdata[0]] == 'non confirmation':
            rcv_rsp = True
        elif self.msgtypeDict[rspdata[0]] == 'acknowleage':
            if send_msgID == int(mid, 16):
                rcv_rsp = True
        elif self.msgtypeDict[rspdata[0]] == 'reset':
            rcv_rsp = True

        return rcv_rsp

    def post(self, token, payload):
        previous = time.time()
        now = time.time()
        print 'Sent Messages : ', 
        print datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        rsp_AT = b''
        end = False
        flag_rcv = False
        flag_retransmit = False
        flag_send = False
        #global success, failed, retransmit
        msgID = 0
        wait_time = [2, 4, 8, 16, 32]

        self.ser.flushInput()

        for i in range(0, 5):
            if flag_rcv:
                break
            else:
                if flag_send:
                    flag_retransmit = True

            if flag_retransmit:
                #retransmit += 1
                self.send(msgtype.con, methodtype.POST, token, payload, flag_retransmit, msgID)
                #print('retransmit :' , retransmit)
            else:
                #success += 1
                msgID = self.send(msgtype.con, methodtype.POST, token, payload, False, 0)
                flag_send = True

            while True:
                if self.ser.inWaiting() > 0:
                    char = self.ser.read()
                    if char == b'\r' or char == b'\n':
                        end = True
                    else:
                        rsp_AT = rsp_AT + char

                if end:
                    str_rsp_AT = rsp_AT.decode("utf-8")
                    if '0,' + self.coapServer in str_rsp_AT:
                        rsp_payload = str_rsp_AT.split(',')
                        rsp = self.splitCount(rsp_payload[4], 2)
                        flag_rcv = self.unpack(rsp, msgID, token)
                    elif 'OK' in str_rsp_AT:
                        if time.time() > (previous + 0.5):
                            self.ser.write(b'AT+NSORF0,512\r\n')
                    elif '+NSONMI' in str_rsp_AT:
                        # self.ser.write(b'AT+NSORF=0,100\r\n')
                        rsp_payloadRF = str_rsp_AT.split(',')
                        rsp_payloadRFCommand = 'AT+NSORF=0,' + rsp_payloadRF[1] + '\r\n'
                        self.ser.write(rsp_payloadRFCommand.encode())
                    end = False
                    rsp_AT = b''

                if time.time() > (now + wait_time[i]):
                    now = time.time()
                    break
                elif flag_rcv:
                    #print('success :' , success)
                    print '---------------------- END ------------------------'
                    break
        if not flag_rcv:
            #failed += 1
            print 'Timeout!!'
            #print('failed :' , failed)           
            print '---------------------- END ------------------------'

    def close(self):
        self.ser.close()