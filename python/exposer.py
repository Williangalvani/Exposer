import time
import sys
import struct
import serial

xrange = range


class TransparentLayer(object):
    serialExposer = None

    def __init__(self, serialExposer):
        self.serialExposer = serialExposer

    def __getattr__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]
        else:
            return self.serialExposer.getVar(item)

    def __setattr__(self, key, value):
        if key == "serialExposer":
            self.__dict__[key] = value
        else:
            self.serialExposer.setVar(key, value)

class SerialExposer:
    """
    Class implementing Exposer's protocol in Python
    """
    _WAITING_HEADER = 0     # '<'
    _WAITING_OPERATION = 1  # request_All, read, write
    _WAITING_TARGET = 2     # 0-255. variable register
    _WAITING_PAYLOAD = 3    # 0-255. data bytes to receive
    _WAITING_DATA = 4       # data itself
    _WAITING_CRC = 5

    _REQUEST_ALL = 33
    _WRITE = 34
    _READ = 35

    _dataBuffer = bytearray()
    _payloadSize = 0
    _payloadLeft = 0
    _crc = 0
    _status = _WAITING_HEADER
    _operation = 0
    _target = 0

    _types = ["_uint8_t",
              "_uint16_t",
              "_uint32_t",
              "_int8_t",
              "_int16_t",
              "_int32_t",
              "_float",
              "_string"]

    _variables = {}

    _messageBuffer = {}

    transparentLayer = None

    def __init__(self, port, baudrate=115200):
        """
        Instantiates a new SerialExposer
        :param port: (string) com port to connect to
        """
        self.ser = serial.Serial(port=port,
                                 baudrate=baudrate,
                                 timeout=0.01)
        self.byte_buffer = bytearray()
        self.transparentLayer = TransparentLayer(self)

    def _serialize8(self, a):
        """
        Adds a byte to the byte buffer
        :param a: byte-like value (int or char in [0, 255])
        :return:
        """
        if isinstance(a, int):
            a = chr(a)
        try:
            self.byte_buffer += a
        except TypeError:
            self.byte_buffer += bytearray([ord(a)])

    def _unpack(self, a, vtype):
        """
        Unpacks a larger variable into the appropriate number of bytes
        :param a: variable to unpack
        :param vtype: type of the variable
        :return: byte or array of bytes
        """

        if vtype == "_uint8_t":
            return a

        elif vtype == "_uint16_t":
            return [a & 0xFF, (a >> 8) & 0xFF]

        elif vtype == "_uint32_t":
            return [a & 0xFF, (a >> 8) & 0xFF, (a >> 16) & 0xFF, (a >> 24) & 0xFF]

        elif vtype == "_int8_t":
            if a < 0:
                a = abs(a)
                a = (~a & 0x00FF) + 1
            return a

        elif vtype == "_int16_t":
            if a < 0:
                a = abs(a)
                a = (~a & 0xFFFF) + 1
            return [a & 0xFF, (a >> 8) & 0xFF]

        elif vtype == "_int32_t":
            if a < 0:
                a = abs(a)
                a = (~a & 0xFFFFFFFF) + 1
            return [a & 0xFF, (a >> 8) & 0xFF, (a >> 16) & 0xFF, (a >> 24) & 0xFF]

        elif vtype == "_float":
            b = struct.pack('<f', a)
            try:
                return [b[i] for i in xrange(0, 4)]
            except TypeError:
                return [ord(b[i]) for i in xrange(0, 4)]

        elif vtype == "_string":
            return [b for b in a.encode("UTF-8")]
        return

    def _packu8(self, operation, target=0, data=[]):
        """
        Assembles the data into a formatted message with CRC, and sends it via serial.
        :param operation: desired operation (write, read, or request_all)
        :param target: (int) target variable index
        :param data: byte array of unpacked data
        :return: None
        """
        self.byte_buffer = bytearray()
        header = ord('<')
        self._serialize8(header)
        self._serialize8(operation)
        crc = header ^ operation

        self._serialize8(target)
        crc ^= target

        if type(data) is int:
            data = [data]

        size = len(data)

        self._serialize8(size)
        crc ^= size
        for item in data:
            try:
                crc ^= item
            except:
                crc ^= ord(item)

            self._serialize8(item)

        self._serialize8(crc)
        self.ser.write(self.byte_buffer)

    def _repack(self, data, varType):
        """
        Assembles array of data bytes into a variable of type varType
        :param data: bytearray of data
        :param varType: Variable type
        :return: Variable of type varType
        """
        if varType == "_uint8_t":
            return data
        elif varType == "_uint16_t":
            return data[0] + (data[1] << 8)
        elif varType == "_uint32_t":
            return data[0] + (data[1] << 8) + (data[2] << 16) + (data[3] << 24)
        elif varType == "_int8_t":
            if data > 127:
                data += -2 ** 8
            return data
        elif varType == "_int16_t":
            data = data[0] + (data[1] << 8)
            if data > 2**15 - 1:
                data += - 2 ** 16
            return data

        elif varType == "_int32_t":
            data = data[0] + (data[1] << 8) + (data[2] << 16) + (data[3] << 24)
            if data > 2 ** 31 - 1:
                data += - 2 ** 32
            return data

        elif varType == "_float":
            try:
                b = struct.unpack('<f', str(data))
            except TypeError:
                b = struct.unpack('<f', data)
            return b[0]
        elif varType == "_string":
            return data.decode("UTF-8")

    def _waitForMsg(self, op, target, timeout=0.2):
        """
        Waits for a specified message, or until timeout expires
        :param op: desired message operation
        :param target: desired message target
        :param timeout: time until timeout in seconds
        :return: received message data
        """
        self._messageBuffer.pop((op, target), None)
        start = time.time()
        while (op, target) not in self._messageBuffer.keys():
            for char in self.ser.readall():
                self._processByte(char)
            time.sleep(0.001)
            if (time.time() - start) > timeout:
                return None
        data = self._messageBuffer.pop((op, target), None)
        return self._repack(data, self._variables[target][1])

    def requestAll(self):
        """
        sends a REQUEST_ALL message
        :return: None
        """
        while len(self._variables) == 0:
            self._packu8(self._REQUEST_ALL)
            self._waitForMsg(self._REQUEST_ALL, 0)

    def getVarNames(self):
        """
        :return: List of all remote variable names, ordered accordingly to their indexes
        """
        return [a[1][0].decode("UTF-8") for a in self._variables.items()]

    def setVar(self, varname, value):
        """
        sends a WRITE message to set 'varname' to value 'value'
        :param varname: (string) name of the desired variable
        :param value: value to set on the variable
        :return: None
        """

        try:
            varname = varname.decode("UTF-8")
        except:
            pass

        for i, var in self._variables.items():
            name, typ = var
            try:
                name = name.decode("UTF-8")
            except:
                pass
            if name == varname:
                self._packu8(self._WRITE, i, self._unpack(value, typ))

    def getVar(self, varname):
        """
        Reads variable varname
        :param varname: name of variable to read
        :return: varname's value on the remote device
        """

        try:
            varname = varname.decode("UTF-8")
        except:
            pass

        for i, var in self._variables.items():
            name, typ = var
            try:
                name = name.decode("UTF-8")
            except:
                pass
            if name == varname:
                self._packu8(self._READ, i, [0])
                received = self._waitForMsg(self._READ, i)
                return received

    def _processMessage(self):
        """
        processes the received message
        :return:
        """
        operationNames = ["REQUEST ALL", "WRITE", "READ"]
        operationName = operationNames[self._operation - 33]

        if operationName == "REQUEST ALL":
            self._variables[self._target] = (self._dataBuffer[:-1], self._types[self._dataBuffer[-1]])

        if len(self._dataBuffer) == 1:
            self._messageBuffer[(self._operation, self._target)] = self._dataBuffer[0]
        else:
            self._messageBuffer[(self._operation, self._target)] = self._dataBuffer

    def var_iter(self):
        try:
            return self._variables.iteritems()
        except:
            return self._variables.items()

    def _processByte(self, char):
        """
        Processes a byte through the protocol
        :param char:
        :return:
        """
        if type(char) is not int:
            char = ord(char)

        if self._status == self._WAITING_HEADER:
            if char == ord('<'):
                self._status = self._WAITING_OPERATION
                self._crc = 0 ^ ord('<')
            else:
                pass

        elif self._status == self._WAITING_OPERATION:
            self._operation = char

            if self._operation in (self._REQUEST_ALL, self._READ, self._WRITE):
                self._status = self._WAITING_TARGET
                self._crc ^= self._operation
            else:
                print("bad operation!", self._operation)
                self._status = self._WAITING_HEADER

        elif self._status == self._WAITING_TARGET:
            self._target = char
            if self._target in range(50):  # bad validation
                self._status = self._WAITING_PAYLOAD
                self._crc ^= self._target

        elif self._status == self._WAITING_PAYLOAD:
            self._payloadSize = char
            self._payloadLeft = self._payloadSize

            self._dataBuffer = bytearray()
            self._crc ^= self._payloadSize
            self._status = self._WAITING_DATA

        elif self._status == self._WAITING_DATA:
            if self._payloadLeft > 0:
                self._dataBuffer += bytearray([char])
                self._crc ^= char
                self._payloadLeft -= 1
            if self._payloadLeft == 0:
                self._status = self._WAITING_CRC

        elif self._status == self._WAITING_CRC:
            if self._crc == char:
                self._processMessage()
            else:
                print("bad crc!", self._crc, ord(char))
            self._status = self._WAITING_HEADER



if __name__ == "__main__":

    testValues = {"_uint8_t": [0, 255],
                  "_uint16_t": [0, 2352],
                  "_uint32_t": [0, 2325],
                  "_int8_t": [-120, 0, -120],
                  "_int16_t": [-20000, 0, -20000],
                  "_int32_t": [-(2 ** 30), (2 ** 30), -30000],
                  "_float": [-0.16, 34.12],
                  "_string": ["batatadoce", "lorem ipsum dolor sit amet"]}

    errors = 0

    if len(sys.argv) == 2:
        port = sys.argv[1]
    else:
        port = "/dev/ttyUSB0"
    comm = SerialExposer(port)
    comm.requestAll()

    for key, value in comm.var_iter():
        print(key, value)

    for index, var in comm.var_iter():
        name, vartype = var
        varRange = testValues[vartype]

        for value in varRange:
            comm.setVar(name, value)
            received = comm.getVar(name)
            if vartype != "_string":
                print(((value - received) < 0.01), ", Type: ", vartype, "sent: ", value, "received: ", received, ", Bytes: ", comm._unpack(value, vartype))
                if (value - received) > 0.01:
                    errors += 1
            else:
                print(value, received)
                if value != received:
                    errors += 1
    exit(errors)
