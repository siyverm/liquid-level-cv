module kernel_test_wrapper (
    input logic clk,
    input logic rst_n,
    input logic input_valid,
    output logic input_ready,
    input logic output_ready,
    output logic output_valid,
    input logic image_start,
    output logic output_image_start,
    input logic [7:0] pixel,
    input logic [35:0] weight_bus,
    output logic [7:0] out_pixel
);
    logic signed [3:0] filter [0:2][0:2];

    for (genvar y = 0; y < 3; y++) begin : set_filter_rows
        for (genvar x = 0; x < 3; x++) begin : set_filter_columns
            assign filter[y][x] = weight_bus[((y * 3 + x) * 4) +: 4];
        end
    end

    kernel #(
        .WIDTH(4),
        .HEIGHT(3),
        .K(3),
        .TOP_LEFT_X(0),
        .TOP_LEFT_Y(0),
        .BOTTOM_RIGHT_X(2),
        .BOTTOM_RIGHT_Y(1)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .en(1'b1),
        .input_valid(input_valid),
        .input_ready(input_ready),
        .output_ready(output_ready),
        .output_valid(output_valid),
        .image_start(image_start),
        .output_image_start(output_image_start),
        .pixel(pixel),
        .filter(filter),
        .out_pixel(out_pixel)
    );
endmodule
