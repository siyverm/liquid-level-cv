SIM = verilator
TOPLEVEL_LANG = verilog
TOPLEVEL = Qxymultiply
MODULE = test_qxymultiply

# Parameters: override on the command line, e.g. make DATA_WIDTH=8 FRAC_BITS=4
DATA_WIDTH ?= 16
FRAC_BITS ?= 8
WEIGHT_WIDTH ?= $(DATA_WIDTH)
WEIGHT_FRAC_BITS ?= $(FRAC_BITS)
export DATA_WIDTH FRAC_BITS WEIGHT_WIDTH WEIGHT_FRAC_BITS

VERILOG_SOURCES = $(CURDIR)/../rtl/v1/Qxymultiply.sv

COMPILE_ARGS += -GDATA_WIDTH=$(DATA_WIDTH) -GFRAC_BITS=$(FRAC_BITS) \
                -GWEIGHT_WIDTH=$(WEIGHT_WIDTH) -GWEIGHT_FRAC_BITS=$(WEIGHT_FRAC_BITS)
EXTRA_ARGS += --trace --timing

include $(shell cocotb-config --makefiles)/Makefile.sim