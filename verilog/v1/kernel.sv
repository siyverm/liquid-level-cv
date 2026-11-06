`include "Qxxmultiply.sv"
`include "adder_tree_block.sv"

module kernel # (
    parameter int WIDTH, HEIGHT, DATA_WIDTH, FRAC_BITS, WEIGHT_SIZE, WEIGHT_FRAC_BITS, K,
    parameter int BOTTOM_LEFT_X, BOTTOM_LEFT_Y, TOP_RIGHT_X, TOP_RIGHT_Y, // represents the crop coordinate indices
    localparam int MULT_WIDTH = DATA_WIDTH + WEIGHT_SIZE,
    localparam int SUM_WIDTH = MULT_WIDTH + $clog2(K**2)
)(
    input clk, rst_n, en,
    input logic signed [0:WIDTH-1][0:HEIGHT-1][DATA_WIDTH-1:0] image,
    input logic signed [0:K-1][0:K-1][WEIGHT_SIZE-1:0] filter,
    output logic signed [BOTTOM_LEFT_X + 1:TOP_RIGHT_X-1][BOTTOM_LEFT_Y + 1:TOP_RIGHT_Y-1][DATA_WIDTH-1:0] out;
);

logic signed [BOTTOM_LEFT_X + 1:TOP_RIGHT_X-1][BOTTOM_LEFT_Y + 1:TOP_RIGHT_Y-1][0:K-1][0:K-1][MULT_WIDTH-1:0] mult_out;
logic signed [BOTTOM_LEFT_X + 1:TOP_RIGHT_X-1][BOTTOM_LEFT_Y + 1:TOP_RIGHT_Y-1][SUM_WIDTH-1:0] conv2D_sum;

generate // multiply blocks
    for (genvar i = BOTTOM_LEFT_X + 1; i < TOP_RIGHT_X; i++) begin: mult_x
        for (genvar j = BOTTOM_LEFT_Y + 1; j < TOP_RIGHT_Y; j++) begin: mult_y
            for (genvar filter_i = 0; filter_i < K; filter_i++) begin: filter_x
                for (genvar filter_j = 0; filter_j < K; filter_j++) begin: filter_y
                    Qxymultiply #(
                        .DATA_WIDTH(DATA_WIDTH), 
                        .FRAC_BITS(FRAC_BITS), 
                        .WEIGHT_WIDTH(WEIGHT_WIDTH), 
                        .WEIGHT_FRAC_BITS(WEIGHT_FRAC_BITS)
                        ) 
                    multiply_block (
                        .clk(clk), 
                        .rst_n(rst_n),
                        .en(en),
                        .input_reg(image[i][j]), 
                        .weight(filter[filter_i][filter_j]), 
                        .final_product(mult_out[i][j][filter_i][filter_j])
                    );
                end
            end
        end
    end
endgenerate

generate //adder blocks
    for (genvar i = BOTTOM_LEFT_X + 1; i < TOP_RIGHT_X; i++) begin: adder_x
        for (genvar j = BOTTOM_LEFT_Y + 1; j < TOP_RIGHT_Y; j++) begin: adder_y
            adder_tree_block # (
                .NUM(K**2), // 9 for a 3x3 kernel
                .DATA_WIDTH(MULT_WIDTH)
                ) 
            adder_tree (
                .clk(clk), 
                .rst_n(rst_n),
                .en(en),
                .nums(mult_out[i][j]),
                .sum(conv2D_sum[i][j])
            );
        end
    end
endgenerate

generate //applying clamp
    for (genvar i = BOTTOM_LEFT_X + 1; i < TOP_RIGHT_X; i++) begin: clamp_x
        for (genvar j = BOTTOM_LEFT_Y + 1; j < TOP_RIGHT_Y; j++) begin: clamp_y
            assign out[i][j] = clamp(conv2D_sum[i][j], DATA_WIDTH);
        end
    end
endgenerate


function automatic int clamp(int signed a, int data_width);
    int maximumVal = (1 <<< (data_width - 1)) - 1;
    int minimumVal = -(1 <<< (data_width - 1));
    if (a > maximumVal) return maximumVal;
    else if (a < minimumVal) return minimumVal;
    else return a;
endfunction
endmodule