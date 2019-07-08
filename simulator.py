import fcntl
import os
import pty
import serial
import time
from threading import Thread

DELAY = 0.001

class MiniDeltaSimulator:
    def __init__(self):
        self._abort = False
        self._buffer = ''
        self._master = None
        self._masterf = None
        self._running = False
        self._serial = None
        self._thread = None

    def _fread(self):
        # attempt to read
        try:
            return self._masterf.read()
        except IOError, e:
            if e.errno == 11:
                return None
            else:
                raise (e)
    
    def _fwrite(self, s):
        # attempt to write
        retries = 100
        while retries > 0:
            try:
                self._masterf.write(s)
                break
            except IOError, e:
                if e.errno == 11 and retries > 0:
                    retries = retries - 1
                    time.sleep(0.001)
                    continue
                else:
                    raise (e)

    def _fwrited(self, s):
        self._fwrite(s + '\n')
        time.sleep(DELAY)

    def _openpty_nonblocking(self):
        # open the pty
        self._master, slave = pty.openpty()
        
        # open the master as non-blocking
        self._masterf = os.fdopen(self._master, "wrb", 0)    
        flags = fcntl.fcntl(self._masterf, fcntl.F_GETFL)
        assert flags>=0
        flags = fcntl.fcntl(self._masterf, fcntl.F_SETFL , flags | os.O_NONBLOCK)
    
        # create serial port for the slave
        self._serial = serial.Serial(os.ttyname(slave), timeout=1)

    def _process_buffer(self):
        # check if command is ready
        if '\n' not in self._buffer:
            return
        
        # parse the command
        cmd, _, self._buffer = self._buffer.partition('\n')
        if cmd == 'G00':
            self._fwrited('echo:busy: processing')
            self._fwrited('ok')            
        if cmd == 'G28':
            self._fwrited('echo:busy: processing')
            self._fwrited('echo:busy: processing')
            self._fwrited('ok')
        elif cmd == 'G30':
            self._fwrited('echo:busy: processing')
            self._fwrited('echo:busy: processing')
            self._fwrited('echo:busy: processing')
            self._fwrited('echo:busy: processing')
            self._fwrited('Bed X: 0.00000 Y: 0.00000 Z: 2.00829')
            self._fwrited('X:0.00000 Y:0.00000 Z:25.60000 E:0.00000 Count x :7353 y :7353 z :7353')
            self._fwrited('ok')
        elif cmd =='M31':
            self._fwrited('echo:Print time: 0s')
            self._fwrited('ok')
        elif cmd =='M665':
            self._fwrited('ok')
        else:
            self._fwrited('echo:Unknown command: "%s"' % cmd)
            self._fwrited('ok')
            

    def _thread_worker(self):
        while not self._abort:
            # see if command is ready
            r = self._fread()
            if r:
                self._buffer += r
            self._process_buffer()
#             
#             self._fwrite('MASTER_SEND')
#             print 's ', self._serial.read()
#             self._serial.write('SLAVE_SEND')
#             print 'm', self._fread()
        self._running = False

    def get_serial(self):
        return self._serial
    
    def stop(self):
        self._abort = True
        while self._running:
            time.sleep(0.001)
    
    def start(self):
        if self._running:
            self.stop()
        self._running = True
        self._abort = False
        self._openpty_nonblocking()
        self._thread = Thread(target=self._thread_worker, args=())
        self._thread.start()
