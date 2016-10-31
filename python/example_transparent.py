from exposer import SerialExposer # Imports the communication module
import sys

if len(sys.argv) == 2:
    port = sys.argv[1]
else:
    print("Port not specified, using default port /dev/ttyACM0")
    port = "/dev/ttyACM0"

# Instantiate a "SerialExposer" object named "comm"
comm = SerialExposer(port)
comm.requestAll()

# Transparent Mode, enables an easier interface to use
remote = comm.transparentLayer

# Equivalent to "testuint8 = 18;"
remote.testuint8 = 18

# Reads and prints testuint8's value
print(remote.testuint8)


