import serial
import sys
import traceback
from serial import *
from serial.threaded import *
import simulator
import pty
from simulator import MiniDeltaSimulator

class Calibrator(LineReader):
    def __init__(self):
        super(Calibrator, self).__init__()
        print 'INIT'
        self._gcode = None
        self._gcode_args = None
        self._busy = False
        self.TERMINATOR = '\n'
        self._ret_values = None
        self._clear_return_values()
#        self.__cmd__ = None

    def _clear_return_values(self):
        self._ret_values = {}

    @property
    def busy(self):
        return self._busy

    @property
    def return_values(self):
        return dict(self._ret_values)

    def run_gcode(self, gcode, *args):
        assert(self._busy == False)
        self._busy = True
        self._gcode = gcode
        self._gcode_args = args
        if gcode in ('G00', 'G01', 'G28', 'G30', 'M31', 'M503', 'M665', 'M851'):
            self._gcode_stop_condition = 'ok'
        else:
            raise Exception('Unhandled gcode %s' % gcode)
        print gcode
        print args
        s = ' '.join([gcode] + list(args))
        print "'%s'" %s
        self.write_line(s)
        while self._busy:
            time.sleep(0.01)
        print 'Done!'
                
#     def connection_made(self, transport):
#         super(Calibrator, self).connection_made(transport)
#         sys.stdout.write('port opened\n')
# #        self.write_line('hello world')
 
    def handle_line(self, data):
        sys.stdout.write('line received: {}\n'.format(repr(data)))
        if data.startswith('Bed '):
            self._ret_values['Bed_X'] = float(data[4:].split(' ')[1])
            self._ret_values['Bed_Y'] = float(data[4:].split(' ')[3])
            self._ret_values['Bed_Z'] = float(data[4:].split(' ')[5])
        if data.startswith('X:'):
            self._ret_values['X'] = float(data.split(' ')[0].partition(':')[2])
            self._ret_values['Y'] = float(data.split(' ')[1].partition(':')[2])
            self._ret_values['Z'] = float(data.split(' ')[2].partition(':')[2])
            self._ret_values['E'] = float(data.split(' ')[3].partition(':')[2])
            self._ret_values['count_X'] = float(data.split(' ')[6].partition(':')[2])
            self._ret_values['count_Y'] = float(data.split(' ')[8].partition(':')[2])
            self._ret_values['count_Z'] = float(data.split(' ')[10].partition(':')[2])
        if data == self._gcode_stop_condition:
            print 'stop condition detected'
            self._busy = False

#     def G28(self):
#         self._busy = True
#         self._set_gcode('G28')

def calibrate_endstops(ser):
    with ReaderThread(ser, Calibrator) as protocol:
        # clear the buffer in case we just started the printer
        protocol.run_gcode('M31')   # print time
        protocol.run_gcode('M31')   # print time
        
        # home, then find center bed height
        protocol.run_gcode('M665', 'X120', 'Y120', 'Z120')
        protocol.run_gcode('M665', 'R63.2')
        protocol.run_gcode('G28')
        protocol.run_gcode('G00', 'Z50')    
        protocol.run_gcode('G30')
    
        # set the probe height to be bed height + 10mm    
        protocol.run_gcode('M851', 'R%d' % (protocol.return_values['Bed_Z'] + 10))
    
        # probe the 3 points
        s = 'MOVING ENDSTOP DOWN WILL INCREASE Z\n'
        protocol.run_gcode('G00', 'X0', 'Y50')
        protocol.run_gcode('G30')
        s += '        %0.4f\n' % protocol.return_values['Bed_Z']
        s += '           |\n'
        protocol.run_gcode('G00', 'X0', 'Y0')
        protocol.run_gcode('G30')
        s += '        %0.4f\n' % protocol.return_values['Bed_Z']
        s += '       /       \\\n'
        protocol.run_gcode('G00', 'X-25', 'Y-43.3')
        protocol.run_gcode('G30')
        s += '%0.4f' % protocol.return_values['Bed_Z']
        protocol.run_gcode('G00', 'X25', 'Y-43.3')
        protocol.run_gcode('G30')
        s += '         %0.4f\n' % protocol.return_values['Bed_Z']        
        protocol.run_gcode('M503')
        return s

# --------------------------------------------------
#    Main
# --------------------------------------------------
x = MiniDeltaSimulator()
x.start()
ser = x.get_serial()
#ser = Serial('/dev/ttyACM0', 115200, timeout=1, xonxoff=0)
retval = calibrate_endstops(ser)
print '----'
print retval
# #ser = Serial('/dev/ttyACM0', 115200, timeout=1, xonxoff=0)
# 
# # ser.write('M31\r')
# # while True:
# #     c = ser.read(1)
# #     print c, hex(ord(c))
# 
# with ReaderThread(ser, Calibrator) as protocol:
#     # clear the buffer in case we just started the printer
#     protocol.run_gcode('M31')   # print time
#     protocol.run_gcode('M31')   # print time
#     
#     # home, then find center bed height
#     protocol.run_gcode('M665', 'X120', 'Y120', 'Z120')
#     protocol.run_gcode('G28')
#     protocol.run_gcode('G00', 'Z50')    
#     protocol.run_gcode('G30')
# 
#     # set the probe height to be bed height + 10mm    
#     protocol.run_gcode('M851', 'R%d' % (protocol.return_values['Bed_Z'] + 10))
# 
#     # probe the 3 points
#     s = ''
#     protocol.run_gcode('G00', 'X0', 'Y50')
#     protocol.run_gcode('G30')
#     s += '        ' + str(protocol.return_values['Bed_Z']) + '\n'
#     s += '           |\n'
#     protocol.run_gcode('G00', 'X0', 'Y0')
#     protocol.run_gcode('G30')
#     s += '        ' + str(protocol.return_values['Bed_Z']) + '\n'
#     s += '       /       \\\n'
#     protocol.run_gcode('G00', 'X-25', 'Y-43.3')
#     protocol.run_gcode('G30')
#     s += str(protocol.return_values['Bed_Z'])
#     protocol.run_gcode('G00', 'X25', 'Y-43.3')
#     protocol.run_gcode('G30')
#     s += '         ' + str(protocol.return_values['Bed_Z']) + '\n'
#     
# #     # calibrate end stops by probing the 3 triangle points
# #     protocol.run_gcode('G01', 'X0', 'Y0', 'Z10')
# #     
# #     # home
# #     protocol.run_gcode('G28')
#         
# # #    protocol.write_line('G28')
# #     while protocol.busy:
# #         time.sleep(1)
# #         print protocol.busy
# 
# print 'OUT!'
x.stop()    

#time.sleep(60)


#s_name = simulator.start_simulator()

# master, slave = pty.openpty()
# m_name = os.ttyname(master)
# print m_name
# s_name = os.ttyname(slave)
# print s_name
# 
# 
# print s_name
# ser = serial.Serial(s_name, timeout=1)
# #ser2 = serial.Serial(m_name, timeout=1)
# fd = os.fdopen(master, "wb")
# fd2 = os.fdopen(master, "rb")
# while True:
#     
#     print 'A'
#     fd.write(b'X\n')
#     fd.flush()
#     print 'B'
#     x = ser.read()
#     print len(x)
#     ser.write('Z')
#     print fd2.read(1)

# #ser = serial.serial_for_url('loop://', baudrate=115200, timeout=1)
# with ReaderThread(ser, PrintLines) as protocol:
#     with ReaderThread(ser2, PrintLines) as protocol2:
#         while True:
#             print 'S'
#             protocol.write_line('hello\r\n')
#             time.sleep(2)
# 
# 
# def create_virtual_serial_port_pair():
#     def worker(masterFRA, masterFWA, masterFRB, masterFWB):
#         
#     masterA, slaveA = pty.openpty()
#     masterFRA = os.fdopen(masterA, 'rb')
#     masterFWA = os.fdopen(masterA, 'wb')
#     masterB, slaveB = pty.openpty()
#     masterFRB = os.fdopen(masterB, 'rb')
#     masterFWB = os.fdopen(masterB, 'wb')
# 
#     
# 
#     return os.ttyname(slaveA), os.ttyname(slaveB) 