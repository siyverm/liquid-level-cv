module Qxymultiply 
# (parameter int DATA_WIDTH=16, FRAC_BITS=8, WEIGHT_WIDTH=DATA_WIDTH, WEIGHT_FRAC_BITS=FRAC_BITS) (
    input clk, rst_n, en,
    input logic signed [DATA_WIDTH-1:0] input_reg, 
    input logic signed [WEIGHT_WIDTH-1:0] weight,
    output logic signed [DATA_WIDTH + WEIGHT_WIDTH-1:0] final_product
);

logic signed [DATA_WIDTH + WEIGHT_WIDTH-1:0] product;
logic signed [DATA_WIDTH + WEIGHT_WIDTH-1:0] product_out;
logic signed [DATA_WIDTH-1:0] a;
logic signed [WEIGHT_WIDTH-1:0] b;

always_ff @(posedge clk) begin
    if (!rst_n) begin
        a <= '0;
        b <= '0;
        product <= '0;
        product_out <= '0;
        final_product <= '0;
    end else if (en) begin
        a <= input_reg;
        b <= weight;
        product <= a * b;
        product_out <= product;
        final_product <= (product_out + (1 <<< (WEIGHT_FRAC_BITS-1))) >>> WEIGHT_FRAC_BITS;
    end
end
endmodule