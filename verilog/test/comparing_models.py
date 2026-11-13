import cv2
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
import os

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]      # verilog/test/ -> verilog/ -> repo root
sys.path.append(str(REPO / "model_keras"))
sys.path.append(str(REPO))                       # for preprocessing.py

from making_model import predict, make_model
from fill_percentage import predict_volume1
from preprocessing import crop_image_fixed

IMGPATHS = "testImges/resized_128/483b0763-107e-4b1e-afc6-bdd983f9dd49_1.jpg"
MODELPATH = ""

FRAC_BITS = 8
TOLERANCE = 0.02

def load_image(path, width, height, resize = True):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if (resize):
        img = cv2.resize(img, (width, height))
    print (img.shape)
    return img

async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.en.value = 1
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await Timer(1, "ns")
    dut.rst_n.value = 1

@cocotb.test()
async def compare_outputs(dut):

    await setup(dut)
    dut.image_start.value = 1

    img = load_image(IMGPATHS, 128, 128, False)
    CROP_BOX = tuple(int(os.environ[k]) for k in ("CROP_L", "CROP_T", "CROP_R", "CROP_B"))
    cropped, _ = crop_image_fixed(img, (CROP_BOX))

    model = make_model(cropped.shape[1], cropped.shape[0])
    prediction = predict(model, cropped)

    percentage = predict_volume1(prediction[:, 0])


    for row in img:
        for pixel in row:
            blue, green, red = pixel[0], pixel[1], pixel[2]  # cv2 loads as BGR
            dut.pixel[0].value = int(red)
            dut.pixel[1].value = int(green)
            dut.pixel[2].value = int(blue)
            await RisingEdge(dut.clk)
            if (dut.image_start.value == 1) :
                dut.image_start.value = 0

    rtlResult = await wait_for_result(dut)
    rtl_fill = 1 - rtlResult / 2**FRAC_BITS

    print(f"KERAS PREDICTION: {percentage * 100:.3f} %")
    print(f"HARDWARE PREDICTION: {rtl_fill * 100:.3f} %")

    assert abs(percentage - rtl_fill) <= TOLERANCE


async def wait_for_result (dut, timeout_cycles=100_000) :
    for _ in range (timeout_cycles) :
        await RisingEdge(dut.clk)
        if dut.done.value == 1:
            break
    else :
        raise TimeoutError("RTL never asserted done")
    await Timer(1, "ns")
    return dut.fill_percent.value.integer

