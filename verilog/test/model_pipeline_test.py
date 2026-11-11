import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


WIDTH = int(os.environ.get("MODEL_WIDTH", "128"))
HEIGHT = int(os.environ.get("MODEL_HEIGHT", "128"))
BOTTOM_WEIGHT_PERCENT = 20


def make_test_image(transition_row):
    image = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            if y < transition_row:
                row.append((28 + x % 5, 42 + x % 3, 60 + x % 7))
            else:
                row.append((210 - x % 5, 190 - x % 3, 165 - x % 7))
        image.append(row)
    return image


def reference_fill(image):
    height = len(image)
    width = len(image[0])

    gray = [
        [
            (77 * red + 150 * green + 29 * blue) >> 8
            for red, green, blue in row
        ]
        for row in image
    ]

    blur_weights = ((28, 29, 28), (29, 28, 29), (28, 29, 28))
    blurred = [[0] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            total = 0
            for ky in range(3):
                for kx in range(3):
                    sx = x + kx - 1
                    sy = y + ky - 1
                    if 0 <= sx < width and 0 <= sy < height:
                        total += gray[sy][sx] * blur_weights[ky][kx]
            blurred[y][x] = min(255, total >> 8)

    edge_weights = ((1, 2, 1), (0, 0, 0), (-1, -2, -1))
    profile = []
    for y in range(height):
        edge_row = []
        for x in range(width):
            total = 0
            for ky in range(3):
                for kx in range(3):
                    sx = x + kx - 1
                    sy = y + ky - 1
                    if 0 <= sx < width and 0 <= sy < height:
                        total += blurred[sy][sx] * edge_weights[ky][kx]
            edge_row.append(min(255, abs(total)))
        edge_row.sort()
        profile.append((edge_row[(width - 1) // 2] + edge_row[width // 2]) // 2)

    bottom_rows = (height * BOTTOM_WEIGHT_PERCENT + 99) // 100
    bottom_start = height - bottom_rows
    weighted_profile = [
        (value >> 1) if y >= bottom_start else value
        for y, value in enumerate(profile)
    ]
    peak_row = max(range(height), key=weighted_profile.__getitem__)
    return (peak_row * 256) // height


async def send_image(dut, image):
    dut.en.value = 1
    for y, row in enumerate(image):
        for x, (red, green, blue) in enumerate(row):
            await FallingEdge(dut.clk)
            dut.pixel[0].value = red
            dut.pixel[1].value = green
            dut.pixel[2].value = blue
            dut.image_start.value = int((x == 0) and (y == 0))
            while not int(dut.input_ready.value):
                await RisingEdge(dut.clk)
                await FallingEdge(dut.clk)
            await RisingEdge(dut.clk)

    await FallingEdge(dut.clk)
    dut.image_start.value = 0


async def wait_for_result(dut):
    for _ in range(100_000):
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
        if int(dut.done.value):
            return int(dut.fill_percent.value)
    raise TimeoutError("RTL did not produce a fill estimate")


@cocotb.test()
async def compare_model_pipeline(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.en.value = 0
    dut.rst_n.value = 0
    dut.image_start.value = 0
    dut.output_ready.value = 0
    for channel in range(3):
        dut.pixel[channel].value = 0

    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1

    image = make_test_image(HEIGHT // 2)
    expected_fill = reference_fill(image)
    await send_image(dut, image)
    actual_fill = await wait_for_result(dut)
    assert actual_fill == expected_fill, (
        f"RTL fill Q8.8 value {actual_fill} differs from reference {expected_fill}"
    )

    for _ in range(4):
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
        assert int(dut.done.value) == 1, "result valid must remain asserted until accepted"
        assert int(dut.fill_percent.value) == expected_fill

    await FallingEdge(dut.clk)
    dut.output_ready.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    assert int(dut.done.value) == 0

    await FallingEdge(dut.clk)
    dut.output_ready.value = 0
    second_image = make_test_image(HEIGHT // 3)
    second_expected = reference_fill(second_image)
    await send_image(dut, second_image)
    second_actual = await wait_for_result(dut)
    assert second_actual == second_expected, (
        f"second RTL fill Q8.8 value {second_actual} differs from "
        f"reference {second_expected}"
    )
