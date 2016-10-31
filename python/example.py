from exposer import SerialExposer # Imports the communication module
import sys

if len(sys.argv) == 2:
    port = sys.argv[1]
else:
    print("Port not specified, using default port /dev/ttyACM0")
    port = "/dev/ttyACM0"

# Instantiate a "SerialExposer" object named "comm"
comm = SerialExposer(port)

# Requests all registered variables, ordered by their indexes
comm.requestAll()

# This prints all of the received variable names
print(comm.getVarNames())

# Equivalent to running "testuint8 = 18;" on the arduino
comm.setVar("testuint8",18)

# Reads the variable "testuint8" and prints it's value
print(comm.getVar("testuint8"))
