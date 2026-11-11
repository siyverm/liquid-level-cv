SIM = verilator
TOPLEVEL_LANG = verilog
TOPLEVEL = model
MODULE = comparing_models
SIM_BUILD = sim_build_model

WIDTH ?= 128
HEIGHT ?= 128
export MODEL_WIDTH = $(WIDTH)
export MODEL_HEIGHT = $(HEIGHT)

VERILOG_SOURCES = $(CURDIR)/../rtl/v1/model_pkg.sv \
                  $(CURDIR)/../rtl/v1/adder_tree_block.sv \
                  $(CURDIR)/../rtl/v1/Qxymultiply.sv \
                  $(CURDIR)/../rtl/v2/kernel.sv \
                  $(CURDIR)/../rtl/v2/model.sv

EXTRA_ARGS += --trace --timing -GWIDTH=$(WIDTH) -GHEIGHT=$(HEIGHT)

include $(shell cocotb-config --makefiles)/Makefile.sim