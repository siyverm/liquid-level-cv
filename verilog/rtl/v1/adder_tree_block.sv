module adder_tree_block 
    import model_pkg::*;
# (
    parameter int NUM = 10, DATA_WIDTH = 8, DEPTH=-1, MAX_ADDS=2,
    localparam int SUM_WIDTH = DATA_WIDTH + $clog2(NUM)
    ) (
    input clk, rst_n, en,
    input logic signed [DATA_WIDTH-1:0] nums [NUM],
    output logic signed [SUM_WIDTH-1:0] sum
);
parameter int depth = (DEPTH >= 0) ? DEPTH: adder_tree_block_latency(NUM, MAX_ADDS);
logic signed [SUM_WIDTH-1:0] total;

if (NUM < MAX_ADDS || (NUM == MAX_ADDS && depth == 1)) begin: base_case
    always_comb begin
        total = '0;
        foreach(nums[i]) begin
            total += nums[i];
        end
    end
    always_ff @(posedge clk) begin
        if (!rst_n) sum <= '0;
        else if (en) sum <= total;
    end
end else begin: recursion
    localparam int default_slice_width = NUM / MAX_ADDS;
    localparam int remainder_count = NUM % MAX_ADDS;

    // Amortize the extra remainder additions by increasing the slice width by 1 remainder times
    localparam remainder_slice_width = default_slice_width + 1;

    logic signed [SUM_WIDTH-1:0] sub_sums [MAX_ADDS]; // SUM_WIDTH is actually bigger than what is necessary here

    for (genvar i = 0; i < MAX_ADDS; i++) begin: inst_recurs

        localparam int start_index = (i < remainder_count)
            ? i * remainder_slice_width
            : remainder_count * remainder_slice_width + (i - remainder_count) * default_slice_width;

        localparam int end_index = start_index +
            ((i < remainder_count) ? remainder_slice_width : default_slice_width) - 1;
        logic signed [DATA_WIDTH + $clog2(end_index - start_index + 1)-1:0] w;
        adder_tree_block # (.NUM(end_index - start_index + 1), .DATA_WIDTH(DATA_WIDTH), .DEPTH(depth - 1), .MAX_ADDS(MAX_ADDS)) 
        subAdder1 (
            .clk(clk),
            .en(en),
            .rst_n(rst_n), 
            .nums(nums[start_index:end_index]), 
            .sum(w)
        );
        assign sub_sums[i] = SUM_WIDTH'(w);
    end

    always_comb begin
        total = '0;
        foreach(sub_sums[i]) begin
            total += sub_sums[i];
        end
    end
    always_ff @(posedge clk) begin
        if (!rst_n) sum <= '0;
        else if (en) sum <= total;
    end
end

endmodule