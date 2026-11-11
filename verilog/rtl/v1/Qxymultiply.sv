module Qxymultiply 
# (parameter int DATA_WIDTH=8, WEIGHT_WIDTH=DATA_WIDTH, WEIGHT_FRAC_BITS=0) (
    input clk, rst_n, en,
    input logic signed [DATA_WIDTH-1:0] input_reg, 
    input logic signed [WEIGHT_WIDTH-1:0] weight,
    output logic signed [DATA_WIDTH + WEIGHT_WIDTH-1:0] product_out
);
logic signed [DATA_WIDTH + WEIGHT_WIDTH-1:0] product;

always_ff @(posedge clk) begin
    if (!rst_n) begin
        product <= '0;
    end else if (en) begin
        product <= input_reg * weight;
        product_out <= product >>> WEIGHT_FRAC_BITS; // truncates decimal
    end
end
endmodule