import serial
import sys
import traceback
from serial import *
from serial.threaded import *
import simulator
import pty
from simulator import MiniDeltaSimulator
import logging
import time
import math

#DELTA_RADIUS = 62.6
SIMULATED = False

class Calibrator(LineReader):
    def __init__(self):
        super(Calibrator, self).__init__()
        self.TERMINATOR = '\n'
        
        self._busy = False
        self._gcode = None
        self._gcode_args = None
        self._logger = None
        self._ret_values = None
        
        self._clear_return_values()

    def _clear_return_values(self):
        self._ret_values = {}

    @property
    def busy(self):
        return self._busy

#     def set_logger(self, logger):
#         self._logger = logger

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
        
        s = ' '.join([gcode] + list(args))
#        if self._logger:
#            self._logger.DEBUG('running gcode: %s' % s)
        logging.debug('running gcode: %s' % s)
        self.write_line(s)
        while self._busy:
            time.sleep(0.01)
#         if self._logger:
#             self._logger.DEBUG('return values: %s' % self._ret_values)
        logging.debug('return values: %s' % self._ret_values)
                
    def handle_line(self, data):
        logging.debug('> %s' % repr(data))
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
            logging.debug('stop condition detected')
            self._busy = False

def calibrate_endstops(ser, protocol, delta_radius):
        logging.info('Calibrating Endstops...\n')
        
        # clear the buffer in case we just started the printer
        protocol.run_gcode('M31')   # print time
        protocol.run_gcode('M31')   # print time
        
        # home, then find center bed height
        protocol.run_gcode('M665', 'X120', 'Y120', 'Z120')
        protocol.run_gcode('M665', 'R%f' % delta_radius)
        protocol.run_gcode('G28')
        protocol.run_gcode('G00', 'Z50')    
        protocol.run_gcode('G30')
    
        # set the probe height to be bed height + 3mm    
        protocol.run_gcode('M851', 'R%d' % (protocol.return_values['Bed_Z'] + 3))
    
        # probe the 3 points
        s = 'ENDPOINT CALIBRATION RESULTS\nMOVING ENDSTOP DOWN WILL INCREASE Z\n'
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
        logging.info('\n%s\n' % s)
        
        # stop
#        protocol.stop()
        return s

def calibrate_bed(ser, protocol, delta_radius):
#    with ReaderThread(ser, Calibrator) as protocol:

        logging.info('Calibrating Bed...\n')
        
        # clear the buffer in case we just started the printer
        protocol.run_gcode('M31')   # print time
        protocol.run_gcode('M31')   # print time
        
        # home, then find center bed height
        protocol.run_gcode('M665', 'X120', 'Y120', 'Z120')
        protocol.run_gcode('M665', 'R%f' % delta_radius)
        protocol.run_gcode('G28')
        protocol.run_gcode('G00', 'Z50')    
        protocol.run_gcode('G30')
    
        # set the probe height to be bed height + 3mm    
        protocol.run_gcode('M851', 'R%d' % (protocol.return_values['Bed_Z'] + 3))

        # probe the bed
        invert_x = False
        s = 'X,Y,Z\n'
        logging.info(s)
        for y in range (-50, 60, 10):
            for x in range(-50, 60, 10):
                if math.sqrt(x * x + y * y) < 55:
                    xx = x
                    if invert_x:
                        xx = -xx
                    protocol.run_gcode('G00', 'X%d' % xx, 'Y%d' % y)
                    protocol.run_gcode('G30')                    
                    z = protocol.return_values['Bed_Z']
                    ss = '%d, %d, %f' % (xx, y, z)
                    logging.info(ss)
                    s = s + ss + '\n'
            invert_x = not invert_x                    
        return s

def init_logger():
    logging.basicConfig(filename='calibrator.log', format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)
    logging.info('--------------------------------------------------')
    logging.info('--------------------------------------------------')
    logging.info('MP MiniDelta Calibrator Logger Initialzied')
    logging.info('--------------------------------------------------')
    logging.info('--------------------------------------------------')

# --------------------------------------------------
#    Main
# --------------------------------------------------
init_logger()

x = MiniDeltaSimulator()
x.start()
ser = x.get_serial()
if not SIMULATED:
    ser = Serial('/dev/ttyACM0', 115200, timeout=1, xonxoff=0)

with ReaderThread(ser, Calibrator) as protocol:
    for dr in range(620, 640):
        # set delta radius
        delta_radius = dr / 10.0
        logging.info('Calibrating for delta radius %f' % delta_radius)

        # calibrate end stops
        start_time = time.time()
        retval = calibrate_endstops(ser, protocol, delta_radius)
        f = open('output_endstops_%d%s.txt' % (delta_radius * 100, '_simulated' if SIMULATED else ''), 'w')
        f.write(retval)
        f.close()
        logging.info('Calibrating Endstops took %f seconds\n' % (time.time() - start_time))
        
        start_time = time.time()
        retval = calibrate_bed(ser, protocol, delta_radius)
        f = open('bed_%d%s.csv' % (delta_radius * 100, '_simulated' if SIMULATED else ''), 'w')
        f.write(retval)
        f.close()
        logging.info('Calibrating Bed took %f seconds\n' % (time.time() - start_time))

x.stop()
