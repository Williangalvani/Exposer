from exposer import SerialExposer # Imports the communication module

# Instantiate a "SerialExposer" object named "comm"
comm = SerialExposer("/tmp/simavr-uart0")

# Setup phase, this requests all the variable names and types to the other side
comm.requestAll()

# This will print all of the received variable names
print(comm.getVarNames())

# Equivalent to "testuint8 = 0;"
comm.setVar("testuint8",18)

# Equivalent to "testuint8 = 0;"
print(comm.getVar("testuint8"))

remote = comm.transparentLayer

remote.testuint8 = 15
print(remote.testuint8)
