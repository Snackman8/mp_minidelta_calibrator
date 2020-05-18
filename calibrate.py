# --------------------------------------------------
#    Imports
# --------------------------------------------------
import argparse
import curses
import logging
import math
from serial import Serial, PARITY_ODD, PARITY_NONE
import time
import pandas as pd

# --------------------------------------------------
#    GCode Device Class
# --------------------------------------------------
class GCode_Device():
    def __init__(self, ser):
        self._ser = ser
        self._inhibit_log = False
        self.run_gcode('M503')


    def run_gcode(self, gcode, *args):
        # sanity check
#        if gcode not in ('G00', 'G01', 'G28', 'G30', 'G90', 'M119', 'M31', 'M503', 'M665', 'M851'):
        if gcode not in ('G00', 'G28', 'G30', 'G90', 'M114', 'M119', 'M500', 'M503', 'M665', 'M666'):
            raise Exception('Unhandled gcode %s' % gcode)

        # construct the gcode
        s = ' '.join([gcode] + list(args))
        if not self._inhibit_log:
            logging.debug('running gcode: %s' % s.rstrip())
        self._ser.write(s + '\n')
        start_time = time.time()
        retval = None
        while True:
            s = self._ser.readline()
            if s:
                if not self._inhibit_log:
                    logging.debug('> ' + s.rstrip())
        
            if s.startswith('ok'):
                break
                
            # special handling for some gcodes
            if gcode == 'G30':
                # single point probe
                # return a float containing the z of the probe contact
                if s.startswith('Bed'):
                    retval = float(s.rpartition(':')[2].strip())
            if gcode == 'M114':
                retval = {}
                s = s.partition(' Count ')[0]
                for x in s.split(' '):
                    retval[x.split(':')[0]] = float(x.split(':')[1])
            if gcode == 'M119':
                # get endstop status
                # return a dictionary of end stop statuses
                # i.e. {'x_stop': 'open', 'y_stop': 'open', 'z_min': 'TRIGGERED', 'z_stop': 'open'}
                if retval is None:
                    retval = {}
                if ':' in s:
                    retval[s.split(':')[0].strip()] = s.split(':')[1].strip()
            if gcode == 'M503':
                # get the current machine state
                if retval is None:
                    retval = {}
                if s.startswith('echo:  '):
                    retval[s[7:].partition(' ')[0]] = s[7:].partition(' ')[2].strip().split(' ')                         
            if time.time() - start_time > 20:
                raise Exception('Error!  timeout')
        return retval

    def get_location(self):
        return self.run_gcode('M114')

    def get_settings(self):
        retval = {}
        d = self.run_gcode('M503')        
        for k,v in d.iteritems():
            retval[k] = {x[0]: float(x[1:]) for x in v}
        return retval


    def home(self):
        """ home the machine """
        self.run_gcode('G90')
        self.run_gcode('G28')
    
    def rapid(self, x=None, y=None, z=None, f=None):
        """ perform a rapid movement """
        args = []
        if x is not None:
            args.append('X%f ' % x)
        if y is not None:
            args.append('Y%f ' % y)
        if z is not None:
            args.append('Z%f ' % z)
        if f is not None:
            args.append('F%f ' % f)
        self.run_gcode('G00', *args)
    
    def probe(self, x, y, z_safe=20, samples=7, indent=''):
        """ perform a probe with multiple samples """
        results = []

        logging.info(indent + 'Probing at X%f Y%f' % (x, y))        
        self._inhibit_log = True
        self.rapid(z=z_safe)
        for _ in range (0, samples):
            self.rapid(x=x, y=y)
            z = self.run_gcode('G30')   # single point probe
            while self.run_gcode('M119')['z_min'] == 'TRIGGERED':
                z = z + 0.001
                self.rapid(z=z)
            logging.debug('    Sample: Z%0.2f' % z)        
            self.rapid(z=z + 1)
            results.append(z)
        self.rapid(z=z_safe)
        self._inhibit_log = False

        # remove outliers and find the mean
        sr = pd.Series(results)
        q = sr.quantile([0.25, 0.5, 0.75])
        sr2 = sr[(sr >= q[0.25]) & (sr <= q[0.75])]
        if not sr2.empty:
            z = sr[(sr >= q[0.25]) & (sr <= q[0.75])].mean().round(3)
        else:
            z = sr.mean()
        logging.info(indent + 'Probe result: %0.2f' % z)
        return z        


# --------------------------------------------------
#    Functions
# --------------------------------------------------
def init_logger(loglevel):
    level = logging.INFO
    if loglevel == 'ERROR':
        level = logging.ERROR
    if loglevel == 'WARN':
        level = logging.WARN
    if loglevel == 'INFO':
        level = logging.INFO
    if loglevel == 'DEBUG':
        level = logging.DEBUG
    logging.basicConfig(filename='calibrator.log', format='%(asctime)s - %(levelname)s - %(message)s', level=level)
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    logging.getLogger('').addHandler(console)
    logging.info('--------------------------------------------------')
    logging.info('--------------------------------------------------')
    logging.info('MP MiniDelta Calibrator Logger Initialzied')
    logging.info('--------------------------------------------------')
    logging.info('--------------------------------------------------')


def probe_endstops(gdev, z_safe=20, probe_center=True, samples=7, indent=''):
    """ probe the 3 endstop positions """
    retval = []
    radius = 50.0
    theta = math.pi / 2 + 2 * math.pi / 3     # tower 2  (should be first)     
    z = gdev.probe(math.cos(theta) * radius, math.sin(theta) * radius, samples=samples, indent=indent)
    retval.append(z)
    theta += 2 * math.pi / 3     # tower 3  (should be second)
    z = gdev.probe(math.cos(theta) * radius, math.sin(theta) * radius, samples=samples, indent=indent)
    retval.append(z)
    theta += 2 * math.pi / 3     # tower 1  (should be third)
    z = gdev.probe(math.cos(theta) * radius, math.sin(theta) * radius, samples=samples, indent=indent)
    retval.append(z)
    if probe_center:
        z = gdev.probe(0, 0, samples=samples, indent=indent)
        retval.append(z)
    gdev.rapid(z=z_safe)
    gdev.rapid(x=0, y=0)
    return retval


# --------------------------------------------------
#    Main
# --------------------------------------------------
CENTER_TOLERANCE = 0.05
ENDPOINT_TOLERANCE = 0.05

def recalibrate_probe_offset(gdev):
    try:
        # init
        stdscr = curses.initscr()    
        curses.noecho()
        
        # home
        stdscr.clear()
        stdscr.addstr('Please wait, homing the machine')
        gdev.home()
        gdev.rapid(z=30)
        stdscr.clear()
        
         
        stdscr.addstr('Press a / z to move the probe up / down 1mm\n')
        stdscr.addstr('Press s / x to move the probe up / down 0.1mm\n')
        stdscr.addstr('Press d / c to move the probe up / down 0.01mm\n')
        stdscr.addstr('Move nozzle to Z=0 and then press t to calibrate\n')
        stdscr.addstr('Press q to quit\n')
        m666_dirty = True
        while True:
            loc = gdev.get_location()
            stdscr.addstr(10, 0, 'Z: %0.2f' % (loc['Z']))
            if m666_dirty:
                settings = gdev.get_settings()
                stdscr.addstr(11, 0, 'M666 X:%0.2f Y:%0.2f Z:%0.2f' % (settings['M666']['X'], settings['M666']['Y'], settings['M666']['Z']))
                m666_dirty = False
            curses.flushinp()
            c = stdscr.getch()
            if c == ord('a'):
                gdev.rapid(z=loc['Z'] + 1.0)
            if c == ord('z'):
                gdev.rapid(z=loc['Z'] - 1.0)
            if c == ord('s'):
                gdev.rapid(z=loc['Z'] + 0.1)
            if c == ord('x'):
                gdev.rapid(z=loc['Z'] - 0.1)
            if c == ord('d'):
                gdev.rapid(z=loc['Z'] + 0.01)
            if c == ord('c'):
                gdev.rapid(z=loc['Z'] - 0.01)
            if c == ord('y'):
                gdev.run_gcode('M500')
            if c == ord('t'):
                settings = gdev.get_settings()
                gdev.run_gcode('M666', 'X%0.3f' % (float(settings['M666']['X']) + loc['Z']),
                                       'Y%0.3f' % (float(settings['M666']['Y']) + loc['Z']),
                                       'Z%0.3f' % (float(settings['M666']['Z']) + loc['Z']),)
                gdev.home()
                m666_dirty = True
            if c == ord('q'):
                break
    finally:
        curses.nocbreak()
        stdscr.keypad(0)
        curses.echo()
        curses.endwin()
    

def save_settings(gdev, args, dirty):
    if not args['dry_run']:
        if dirty:
            logging.info('Saving Settings')
            gdev.run_gcode('M500')
        else:
            logging.info('Not Saving Settings')
    

def run(args):
    # init the logger
    init_logger(args['loglevel'])

    # init variables
    dirty = False
    start_time = time.time()

    # stupid monoprice usb serial bug, must open in this sequence to make work reliably
    ser2 = Serial('/dev/ttyACM0', 115200, timeout=0.1, xonxoff=0, parity=PARITY_ODD)
    ser = Serial('/dev/ttyACM0', 115200, timeout=0.1, xonxoff=0, parity=PARITY_NONE)
    ser2.close()

    # create the gcode device 
    gdev = GCode_Device(ser)

    if args['recalibrate_probe_offset']:
        return recalibrate_probe_offset(gdev)

    if args['verification_only']:
        settings = gdev.get_settings()
        logging.info('M665: %s' % settings['M665'])
        logging.info('M666: %s' % settings['M666'])
        gdev.home()
        ezs = probe_endstops(gdev, samples=args['samples'])
        logging.info('TOWER 1:            %0.2f' % ezs[0])
        logging.info('TOWER 2:            %0.2f' % ezs[1])
        logging.info('TOWER 3:            %0.2f' % ezs[2])
        logging.info('CENTER:             %0.2f' % ezs[3])
        logging.info('FLATNESS DEVIATION: %0.2fmm' % (pd.Series(ezs).max() - pd.Series(ezs).min()))
        logging.info('Took %d seconds' % (time.time() - start_time))
        gdev.home()
        return
    
    if (not args['skip_endpoint_calibration'] or args['endpoint_calibration_only']) and not args['radius_calibration_only']:
        # begin calibrating endstops
        # take a test run with no offsets
        logging.info('Beginning endpoint calibration (max %d iterations, %d samples per point)' % (args['endpoint_iterations'], args['samples']))
        gdev.home()
        s0 = pd.Series([-5.0, -5.0, -5.0])
#        settings = gdev.get_settings()
#        s0 = pd.Series([settings['M666']['X'], settings['M666']['Y'], settings['M666']['Z']])
        verifying = False
        for i in range(0, args['endpoint_iterations']):
            logging.info('    #%d - Trying M666 X%0.3f Y%0.3f Z%0.3f' % (i, s0[0], s0[1], s0[2]))
            gdev.run_gcode('M666', 'X%0.3f' % s0[0], 'Y%0.3f' % s0[1], 'Z%0.3f' % s0[2])
            gdev.home()
            ezs = probe_endstops(gdev, probe_center=False, samples=args['samples'], indent='        ')
            logging.info('        E1=%0.2f    E2=%0.2f    E3=%0.2f    DEVIATION=%0.2f' % (ezs[0], ezs[1], ezs[2], (pd.Series(ezs[0:3]).max() - pd.Series(ezs[0:3]).min())))

            # check if we need to enter verification phase
            if (pd.Series(ezs[0:3]).max() - pd.Series(ezs[0:3]).min()) <= ENDPOINT_TOLERANCE:
                if verifying:
                    logging.info('        VERIFICATION COMPLETE!')
                    break
                else:
                    verifying = True
                    logging.info('        BEGINNING VERIFICATION RUN')
            else:
                if verifying:
                    logging.info('        VERIFICATION FAILED - CONTINUING CALIBRATION')                    
                    verifying = False            
                # only use the tower probe results
                s1 = pd.Series(ezs[0:3])
                s0 = s0 + (s1 - s1[2])
        dirty = True
        if args['endpoint_calibration_only']:
            save_settings(gdev, args, True)
            gdev.home()
            return

    if not args['skip_radius_calibration'] or args['radius_calibration_only']:
        logging.info('Beginning radius calibration (max %d iterations, %d samples per point)' % (args['radius_iterations'], args['samples']))
        # r = 63.2
        r = 62.850
        i = 0
        verifying = False
        # maximum of 10 iterations
        gdev.home()
        while i < args['radius_iterations']:
            logging.info('    #%d - Trying M665 R%0.3f' % (i, r))
            gdev.run_gcode('M665', 'R%0.3f' % r)
            gdev.home()
            ezs = probe_endstops(gdev, samples=args['samples'], indent='        ')
            logging.info('        DEVIATION=%0.2f' % (abs(pd.Series(ezs[0:3]).mean() - ezs[3])))
            # do not adjust if we are within tolerances
            if abs(pd.Series(ezs[0:3]).mean() - ezs[3]) <= CENTER_TOLERANCE:
                if verifying:
                    logging.info('        VERIFICATION COMPLETE!')
                    break
                else:
                    verifying = True
                    logging.info('        BEGINNING VERIFICATION RUN')
            else:
                if verifying:
                    logging.info('        VERIFICATION FAILED - CONTINUING CALIBRATION')                    
                    verifying = False            
                # subtract the center probe result from the mean of the tower probes
                r = r + (pd.Series(ezs[0:3]).mean() - ezs[3]) * 1.5
            # increment the counter
            i = i + 1            
        dirty = True
        if args['radius_calibration_only']:
            save_settings(gdev, args, True)
            gdev.home()
            return
    
    # save settings
    save_settings(gdev, args, dirty)
    gdev.home()

    # exit
    logging.info('Took %d seconds' % (time.time() - start_time))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--recalibrate-probe-offset', help='change the probe offset for a calibrated machine', action='store_true')
    parser.add_argument('--dry-run', help='do not save results into 3d printer EEPROM', action='store_true')
    parser.add_argument('--endpoint-calibration-only', help='only perform endpoint calibration', action='store_true')
    parser.add_argument('--endpoint-iterations', help='max number of iterations to use when calibrating endpoints', type=int, default=10)
    parser.add_argument('--loglevel', help='level for logger', default='INFO')
    parser.add_argument('--radius-calibration-only', help='only perform radius calibration', action='store_true')
    parser.add_argument('--radius-iterations', help='max number of iterations to use when calibrating radius', type=int, default=10)
    parser.add_argument('--samples', help='number of samples to take at each probe point', type=int, default=7)
    parser.add_argument('--skip-endpoint-calibration', help='do not perform endpoint calibration', action='store_true')
    parser.add_argument('--skip-radius-calibration', help='do not perform radius calibration', action='store_true')
    parser.add_argument('--verification-only', help='only perform a verification run to check existing calibration', action='store_true')
    args = parser.parse_args()
    run(vars(args))
