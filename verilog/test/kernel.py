import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge


WIDTH = 4
HEIGHT = 3
CROP_WIDTH = 3
CROP_HEIGHT = 2


async def send_frame(dut, pixels):
    for index, value in enumerate(pixels):
        await FallingEdge(dut.clk)
        dut.input_valid.value = 1
        dut.image_start.value = int(index == 0)
        dut.pixel.value = value
        while True:
            if int(dut.input_ready.value):
                await RisingEdge(dut.clk)
                break
            await RisingEdge(dut.clk)
            await FallingEdge(dut.clk)

    await FallingEdge(dut.clk)
    dut.input_valid.value = 0
    dut.image_start.value = 0


async def receive_frame(dut, expected_count):
    pixels = []
    starts = []
    cycle = 0
    while len(pixels) < expected_count and cycle < 200:
        await FallingEdge(dut.clk)
        ready = int(cycle % 3 != 1)
        dut.output_ready.value = ready
        if int(dut.output_valid.value) and ready:
            pixels.append(int(dut.out_pixel.value))
            starts.append(int(dut.output_image_start.value))
        await RisingEdge(dut.clk)
        cycle += 1

    assert len(pixels) == expected_count, "timed out waiting for filtered frame"
    assert starts == [1] + [0] * (expected_count - 1)
    return pixels


def neighborhood_sums(pixels, weights):
    image_result = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            total = 0
            for ky in range(3):
                for kx in range(3):
                    sx = x + kx - 1
                    sy = y + ky - 1
                    if 0 <= sx < WIDTH and 0 <= sy < HEIGHT:
                        total += pixels[sy * WIDTH + sx] * weights[ky][kx]
            image_result.append(max(0, min(255, total)))
    return [
        image_result[y * WIDTH + x]
        for y in range(CROP_HEIGHT)
        for x in range(CROP_WIDTH)
    ]


def pack_filter(weights):
    packed = 0
    for y in range(3):
        for x in range(3):
            packed |= (weights[y][x] & 0xF) << ((y * 3 + x) * 4)
    return packed


@cocotb.test()
async def test_cropped_convolution_stream(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    dut.input_valid.value = 0
    dut.image_start.value = 0
    dut.output_ready.value = 0
    dut.pixel.value = 0
    blur = [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
    dut.weight_bus.value = pack_filter(blur)
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1

    first = list(range(1, WIDTH * HEIGHT + 1))
    await send_frame(dut, first)
    actual = await receive_frame(dut, CROP_WIDTH * CROP_HEIGHT)
    assert actual == neighborhood_sums(first, blur)

    identity = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
    dut.weight_bus.value = pack_filter(identity)
    second = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90]
    await send_frame(dut, second)
    actual = await receive_frame(dut, CROP_WIDTH * CROP_HEIGHT)
    assert actual == [
        second[y * WIDTH + x]
        for y in range(CROP_HEIGHT)
        for x in range(CROP_WIDTH)
    ]

    negative_center = [[0, 0, 0], [0, -1, 0], [0, 0, 0]]
    dut.weight_bus.value = pack_filter(negative_center)
    await send_frame(dut, second)
    actual = await receive_frame(dut, CROP_WIDTH * CROP_HEIGHT)
    assert actual == [0] * (CROP_WIDTH * CROP_HEIGHT)

    double_center = [[0, 0, 0], [0, 2, 0], [0, 0, 0]]
    dut.weight_bus.value = pack_filter(double_center)
    saturated = [200] * (WIDTH * HEIGHT)
    await send_frame(dut, saturated)
    actual = await receive_frame(dut, CROP_WIDTH * CROP_HEIGHT)
    assert actual == [255] * (CROP_WIDTH * CROP_HEIGHT)
