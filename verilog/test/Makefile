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

CROP_L ?= 55
CROP_T ?= 40
CROP_R ?= 72
CROP_B ?= 70
export CROP_L CROP_T CROP_R CROP_B
EXTRA_ARGS += -GTOP_LEFT_X=$(CROP_L) -GTOP_LEFT_Y=$(CROP_T) \
              -GBOTTOM_RIGHT_X=$(shell echo $$(($(CROP_R)-1))) -GBOTTOM_RIGHT_Y=$(shell echo $$(($(CROP_B)-1)))

EXTRA_ARGS += --trace --timing -GWIDTH=$(WIDTH) -GHEIGHT=$(HEIGHT)

include $(shell cocotb-config --makefiles)/Makefile.sim