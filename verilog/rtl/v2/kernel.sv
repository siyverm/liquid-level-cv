module kernel
    import model_pkg::*;
#(
    parameter int WIDTH = 1080,
    parameter int HEIGHT = 1920,
    parameter int PIXEL_WIDTH = 8,
    parameter int WEIGHT_SIZE = 4,
    parameter int WEIGHT_FRAC_BITS = 0,
    parameter int K = 3,
    parameter bit ABSOLUTE_OUTPUT = 0,
    parameter int TOP_LEFT_X = 0,
    parameter int TOP_LEFT_Y = 0,
    parameter int BOTTOM_RIGHT_X = WIDTH - 1,
    parameter int BOTTOM_RIGHT_Y = HEIGHT - 1,
    localparam int MULT_WIDTH = PIXEL_WIDTH + 1 + WEIGHT_SIZE,
    localparam int SUM_WIDTH = MULT_WIDTH + $clog2(K * K),
    localparam int TREE_LATENCY = adder_tree_block_latency(K * K, 2),
    localparam int PIPELINE_LATENCY = 2 + TREE_LATENCY,
    localparam logic [SUM_WIDTH-1:0] MAX_PIXEL =
        {{(SUM_WIDTH-PIXEL_WIDTH){1'b0}}, {PIXEL_WIDTH{1'b1}}}
)(
    input  logic clk,
    input  logic rst_n,
    input  logic en,
    input  logic input_valid,
    output logic input_ready,
    input  logic output_ready,
    output logic output_valid,
    input  logic image_start,
    output logic output_image_start,
    input  logic [PIXEL_WIDTH-1:0] pixel,
    input  logic signed [WEIGHT_SIZE-1:0] filter [0:K-1][0:K-1],
    output logic [PIXEL_WIDTH-1:0] out_pixel
);

    typedef enum logic [1:0] {CAPTURE, CALCULATE, DRAIN} state_t;
    state_t state;

    logic [PIXEL_WIDTH-1:0] frame [0:HEIGHT-1][0:WIDTH-1];
    integer capture_x;
    integer capture_y;
    integer calc_x;
    integer calc_y;

    logic [PIPELINE_LATENCY-1:0] valid_pipe;
    logic [PIPELINE_LATENCY-1:0] image_start_pipe;
    logic pipeline_advance;
    logic calculate_enable;
    logic signed [PIXEL_WIDTH:0] multiply_inputs [K*K];
    logic signed [MULT_WIDTH-1:0] products [K*K];
    logic signed [SUM_WIDTH-1:0] filtered_sum;
    logic signed [SUM_WIDTH:0] scaled_sum;

    assign output_valid = valid_pipe[PIPELINE_LATENCY-1];
    assign output_image_start = image_start_pipe[PIPELINE_LATENCY-1];
    assign input_ready = (state == CAPTURE) && en;
    assign pipeline_advance = en && (!output_valid || output_ready);
    assign calculate_enable = (state == CALCULATE) && pipeline_advance;

    always_comb begin : build_window
        integer sample_x;
        integer sample_y;
        for (int ky = 0; ky < K; ky++) begin
            for (int kx = 0; kx < K; kx++) begin
                sample_x = calc_x + kx - (K / 2);
                sample_y = calc_y + ky - (K / 2);
                if ((sample_x >= 0) && (sample_x < WIDTH) &&
                    (sample_y >= 0) && (sample_y < HEIGHT)) begin
                    multiply_inputs[ky*K+kx] =
                        $signed({1'b0, frame[sample_y][sample_x]});
                end else begin
                    multiply_inputs[ky*K+kx] = '0;
                end
            end
        end
    end

    for (genvar ky = 0; ky < K; ky++) begin : gen_row
        for (genvar kx = 0; kx < K; kx++) begin : gen_column
            localparam int INDEX = ky * K + kx;
            Qxymultiply #(
                .DATA_WIDTH(PIXEL_WIDTH + 1),
                .WEIGHT_WIDTH(WEIGHT_SIZE),
                .WEIGHT_FRAC_BITS(0)
            ) multiply (
                .clk(clk),
                .rst_n(rst_n),
                .en(pipeline_advance),
                .input_reg(multiply_inputs[INDEX]),
                .weight(filter[ky][kx]),
                .product_out(products[INDEX])
            );
        end
    end

    adder_tree_block #(
        .NUM(K * K),
        .DATA_WIDTH(MULT_WIDTH)
    ) sum_products (
        .clk(clk),
        .rst_n(rst_n),
        .en(pipeline_advance),
        .nums(products),
        .sum(filtered_sum)
    );

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state <= CAPTURE;
            capture_x <= 0;
            capture_y <= 0;
            calc_x <= TOP_LEFT_X;
            calc_y <= TOP_LEFT_Y;
            valid_pipe <= '0;
            image_start_pipe <= '0;
        end else begin
            if (pipeline_advance) begin
                valid_pipe[0] <= calculate_enable;
                image_start_pipe[0] <= calculate_enable &&
                    (calc_x == TOP_LEFT_X) && (calc_y == TOP_LEFT_Y);
                for (int stage = 1; stage < PIPELINE_LATENCY; stage++) begin
                    valid_pipe[stage] <= valid_pipe[stage-1];
                    image_start_pipe[stage] <= image_start_pipe[stage-1];
                end
            end

            case (state)
                CAPTURE: begin
                    if (input_valid && input_ready) begin
                        if (image_start) begin
                            frame[0][0] <= pixel;
                            capture_x <= (WIDTH == 1) ? 0 : 1;
                            capture_y <= 0;
                            if ((WIDTH == 1) && (HEIGHT == 1)) begin
                                state <= CALCULATE;
                                calc_x <= TOP_LEFT_X;
                                calc_y <= TOP_LEFT_Y;
                            end else if (WIDTH == 1) begin
                                capture_y <= 1;
                            end
                        end else begin
                            frame[capture_y][capture_x] <= pixel;
                            if (capture_x == WIDTH - 1) begin
                                capture_x <= 0;
                                if (capture_y == HEIGHT - 1) begin
                                    state <= CALCULATE;
                                    calc_x <= TOP_LEFT_X;
                                    calc_y <= TOP_LEFT_Y;
                                end else begin
                                    capture_y <= capture_y + 1;
                                end
                            end else begin
                                capture_x <= capture_x + 1;
                            end
                        end
                    end
                end

                CALCULATE: begin
                    if (calculate_enable) begin
                        if ((calc_x == BOTTOM_RIGHT_X) &&
                            (calc_y == BOTTOM_RIGHT_Y)) begin
                            state <= DRAIN;
                        end else if (calc_x == BOTTOM_RIGHT_X) begin
                            calc_x <= TOP_LEFT_X;
                            calc_y <= calc_y + 1;
                        end else begin
                            calc_x <= calc_x + 1;
                        end
                    end
                end

                DRAIN: begin
                    if (pipeline_advance && !(|valid_pipe)) begin
                        state <= CAPTURE;
                        capture_x <= 0;
                        capture_y <= 0;
                    end
                end

                default: state <= CAPTURE;
            endcase
        end
    end

    always_comb begin
        scaled_sum = $signed({filtered_sum[SUM_WIDTH-1], filtered_sum}) >>> WEIGHT_FRAC_BITS;
        if (ABSOLUTE_OUTPUT && (scaled_sum < 0)) begin
            scaled_sum = -scaled_sum;
        end

        if (scaled_sum < 0) begin
            out_pixel = '0;
        end else if ($unsigned(scaled_sum) > $unsigned({1'b0, MAX_PIXEL})) begin
            out_pixel = '1;
        end else begin
            out_pixel = scaled_sum[PIXEL_WIDTH-1:0];
        end
    end

    initial begin
        if ((WIDTH < 1) || (HEIGHT < 1)) $error("WIDTH and HEIGHT must be positive");
        if ((K < 1) || ((K % 2) == 0)) $error("K must be a positive odd number");
        if ((WEIGHT_FRAC_BITS < 0) || (WEIGHT_FRAC_BITS >= SUM_WIDTH)) begin
            $error("WEIGHT_FRAC_BITS must fit within SUM_WIDTH");
        end
        if ((TOP_LEFT_X < 0) || (TOP_LEFT_Y < 0) ||
            (BOTTOM_RIGHT_X >= WIDTH) || (BOTTOM_RIGHT_Y >= HEIGHT) ||
            (TOP_LEFT_X > BOTTOM_RIGHT_X) || (TOP_LEFT_Y > BOTTOM_RIGHT_Y)) begin
            $error("Crop coordinates must be an inclusive region inside the image");
        end
    end

endmodule
