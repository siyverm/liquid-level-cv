module model
    import model_pkg::*;
#(
    parameter int WIDTH = 128,
    parameter int HEIGHT = 128,
    parameter int PIXEL_WIDTH = 8,
    parameter int TOP_LEFT_X = 0,
    parameter int TOP_LEFT_Y = 0,
    parameter int BOTTOM_RIGHT_X = WIDTH - 1,
    parameter int BOTTOM_RIGHT_Y = HEIGHT - 1,
    parameter int WEIGHT_SIZE = 11,
    parameter int WEIGHT_FRAC_BITS = 8,
    parameter int BOTTOM_WEIGHT_PERCENT = 20,
    localparam int CROP_WIDTH = BOTTOM_RIGHT_X - TOP_LEFT_X + 1,
    localparam int CROP_HEIGHT = BOTTOM_RIGHT_Y - TOP_LEFT_Y + 1,
    localparam int TOTAL_PIXELS = WIDTH * HEIGHT,
    localparam int GRAY_WEIGHT_WIDTH = 9,
    localparam int GRAY_PRODUCT_WIDTH = PIXEL_WIDTH + 1 + GRAY_WEIGHT_WIDTH,
    localparam int GRAY_SUM_WIDTH = GRAY_PRODUCT_WIDTH + $clog2(3),
    localparam int GRAY_TREE_LATENCY = adder_tree_block_latency(3, 2),
    localparam int GRAY_LATENCY = 1 + GRAY_TREE_LATENCY,
    localparam int WEIGHT_SCALE = 1 << WEIGHT_FRAC_BITS,
    localparam int BLUR_BASE_WEIGHT = WEIGHT_SCALE / 9,
    localparam int BLUR_REMAINDER = WEIGHT_SCALE % 9,
    localparam int HIST_COUNT_WIDTH = (CROP_WIDTH < 2) ? 1 : $clog2(CROP_WIDTH + 1),
    localparam int LOW_MEDIAN_INDEX = (CROP_WIDTH - 1) / 2,
    localparam int HIGH_MEDIAN_INDEX = CROP_WIDTH / 2,
    localparam int BOTTOM_ROWS =
        (CROP_HEIGHT * BOTTOM_WEIGHT_PERCENT + 99) / 100,
    localparam int BOTTOM_START_ROW = CROP_HEIGHT - BOTTOM_ROWS
)(
    input  logic clk,
    input  logic rst_n,
    input  logic en, // A pixel is accepted when en and input_ready are both high.
    input  logic image_start,
    input  logic output_ready,
    input  logic [PIXEL_WIDTH-1:0] pixel [0:2],
    output logic input_ready,
    output logic done,
    output logic [31:0] fill_percent // Unsigned Q8.8 fraction: row index / crop height.
);

    logic signed [PIXEL_WIDTH:0] gray_channels [0:2];
    logic signed [GRAY_WEIGHT_WIDTH-1:0] gray_weights [0:2];
    logic signed [GRAY_PRODUCT_WIDTH-1:0] gray_products [0:2];
    logic signed [GRAY_SUM_WIDTH-1:0] gray_sum;
    logic [GRAY_LATENCY:0] gray_valid_pipe;
    logic [GRAY_LATENCY:0] gray_start_pipe;
    logic gray_advance;
    logic gray_output_valid;
    logic gray_input_ready;
    logic [PIXEL_WIDTH-1:0] gray_pixel;
    integer accepted_pixels;

    logic signed [WEIGHT_SIZE-1:0] blur_filter [0:2][0:2];
    logic signed [WEIGHT_SIZE-1:0] edge_filter [0:2][0:2];

    logic blur_input_ready;
    logic blur_output_valid;
    logic blur_output_ready;
    logic blur_output_start;
    logic [PIXEL_WIDTH-1:0] blur_pixel;

    logic edge_input_ready;
    logic edge_output_valid;
    logic edge_output_ready;
    logic edge_output_start;
    logic [PIXEL_WIDTH-1:0] edge_pixel;

    typedef enum logic {COLLECT_ROW, SCAN_HISTOGRAM} profile_state_t;
    profile_state_t profile_state;
    logic [HIST_COUNT_WIDTH-1:0] histogram [0:255];
    integer row_x;
    integer row_y;
    integer scan_value;
    integer cumulative_count;
    logic low_median_found;
    logic [7:0] low_median_value;
    logic [7:0] best_score;
    integer best_row;
    logic result_valid;

    logic [7:0] median_value;
    logic [7:0] weighted_score;
    integer scan_next_count;
    integer median_low_value;

    assign done = result_valid;
    assign gray_output_valid = gray_valid_pipe[GRAY_LATENCY];
    assign gray_advance = en && (!gray_output_valid || blur_input_ready);
    assign input_ready = gray_advance && (accepted_pixels < TOTAL_PIXELS) && !result_valid;
    assign gray_input_ready = input_ready && en;
    assign blur_output_ready = en && edge_input_ready;
    assign edge_output_ready = en && (profile_state == COLLECT_ROW) && !result_valid;
    assign gray_pixel = PIXEL_WIDTH'(gray_sum >>> 8);

    always_comb begin
        scan_next_count = cumulative_count + int'(histogram[scan_value]);
        median_low_value = low_median_found ? int'(low_median_value) : scan_value;
        median_value = 8'((median_low_value + scan_value) / 2);
        if (row_y >= BOTTOM_START_ROW) weighted_score = median_value >> 1;
        else weighted_score = median_value;
    end

    always_comb begin
        gray_channels[0] = $signed({1'b0, pixel[0]});
        gray_channels[1] = $signed({1'b0, pixel[1]});
        gray_channels[2] = $signed({1'b0, pixel[2]});
    end

    assign gray_weights[0] = 9'sd77;
    assign gray_weights[1] = 9'sd150;
    assign gray_weights[2] = 9'sd29;

    for (genvar channel = 0; channel < 3; channel++) begin : gray_multiply
        Qxymultiply #(
            .DATA_WIDTH(PIXEL_WIDTH + 1),
            .WEIGHT_WIDTH(GRAY_WEIGHT_WIDTH),
            .WEIGHT_FRAC_BITS(0)
        ) multiply (
            .clk(clk),
            .rst_n(rst_n),
            .en(gray_advance),
            .input_reg(gray_channels[channel]),
            .weight(gray_weights[channel]),
            .product_out(gray_products[channel])
        );
    end

    adder_tree_block #(
        .NUM(3),
        .DATA_WIDTH(GRAY_PRODUCT_WIDTH)
    ) gray_adder (
        .clk(clk),
        .rst_n(rst_n),
        .en(gray_advance),
        .nums(gray_products),
        .sum(gray_sum)
    );

    for (genvar coefficient = 0; coefficient < 9; coefficient++) begin : blur_coefficients
        localparam bit EXTRA_WEIGHT =
            (WEIGHT_FRAC_BITS == 8)
                ? ((coefficient == 1) || (coefficient == 3) ||
                   (coefficient == 5) || (coefficient == 7))
                : (coefficient < BLUR_REMAINDER);
        localparam int COEFFICIENT_VALUE =
            (WEIGHT_FRAC_BITS == 8)
                ? (EXTRA_WEIGHT ? 29 : 28)
                : (BLUR_BASE_WEIGHT + int'(EXTRA_WEIGHT));
        assign blur_filter[coefficient / 3][coefficient % 3] =
            WEIGHT_SIZE'(COEFFICIENT_VALUE);
    end

    assign edge_filter = '{
        '{WEIGHT_SIZE'(WEIGHT_SCALE), WEIGHT_SIZE'(WEIGHT_SCALE * 2), WEIGHT_SIZE'(WEIGHT_SCALE)},
        '{WEIGHT_SIZE'(0),             WEIGHT_SIZE'(0),                WEIGHT_SIZE'(0)},
        '{WEIGHT_SIZE'(-WEIGHT_SCALE), WEIGHT_SIZE'(-WEIGHT_SCALE * 2), WEIGHT_SIZE'(-WEIGHT_SCALE)}
    };

    kernel #(
        .WIDTH(WIDTH),
        .HEIGHT(HEIGHT),
        .PIXEL_WIDTH(PIXEL_WIDTH),
        .WEIGHT_SIZE(WEIGHT_SIZE),
        .WEIGHT_FRAC_BITS(WEIGHT_FRAC_BITS),
        .K(3)
    ) blur (
        .clk(clk),
        .rst_n(rst_n),
        .en(en),
        .input_valid(gray_output_valid && en),
        .input_ready(blur_input_ready),
        .output_ready(blur_output_ready),
        .output_valid(blur_output_valid),
        .image_start(gray_start_pipe[GRAY_LATENCY]),
        .output_image_start(blur_output_start),
        .pixel(gray_pixel),
        .filter(blur_filter),
        .out_pixel(blur_pixel)
    );

    kernel #(
        .WIDTH(WIDTH),
        .HEIGHT(HEIGHT),
        .PIXEL_WIDTH(PIXEL_WIDTH),
        .WEIGHT_SIZE(WEIGHT_SIZE),
        .WEIGHT_FRAC_BITS(WEIGHT_FRAC_BITS),
        .K(3),
        .ABSOLUTE_OUTPUT(1'b1),
        .TOP_LEFT_X(TOP_LEFT_X),
        .TOP_LEFT_Y(TOP_LEFT_Y),
        .BOTTOM_RIGHT_X(BOTTOM_RIGHT_X),
        .BOTTOM_RIGHT_Y(BOTTOM_RIGHT_Y)
    ) edge_detect (
        .clk(clk),
        .rst_n(rst_n),
        .en(en),
        .input_valid(blur_output_valid && en),
        .input_ready(edge_input_ready),
        .output_ready(edge_output_ready),
        .output_valid(edge_output_valid),
        .image_start(blur_output_start),
        .output_image_start(edge_output_start),
        .pixel(blur_pixel),
        .filter(edge_filter),
        .out_pixel(edge_pixel)
    );

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            gray_valid_pipe <= '0;
            gray_start_pipe <= '0;
            accepted_pixels <= 0;
        end else begin
            if (gray_advance) begin
                gray_valid_pipe[0] <= gray_input_ready;
                gray_start_pipe[0] <= gray_input_ready && image_start;
                for (int stage = 1; stage <= GRAY_LATENCY; stage++) begin
                    gray_valid_pipe[stage] <= gray_valid_pipe[stage-1];
                    gray_start_pipe[stage] <= gray_start_pipe[stage-1];
                end
            end

            if (result_valid && output_ready && en) begin
                accepted_pixels <= 0;
            end else if (gray_input_ready) begin
                if (image_start) accepted_pixels <= 1;
                else accepted_pixels <= accepted_pixels + 1;
            end
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            profile_state <= COLLECT_ROW;
            row_x <= 0;
            row_y <= 0;
            scan_value <= 0;
            cumulative_count <= 0;
            low_median_found <= 1'b0;
            low_median_value <= '0;
            best_score <= '0;
            best_row <= 0;
            result_valid <= 1'b0;
            fill_percent <= '0;
            histogram <= '{default:'0};
        end else begin
            if (result_valid && output_ready && en) begin
                result_valid <= 1'b0;
                profile_state <= COLLECT_ROW;
                row_x <= 0;
                row_y <= 0;
                best_score <= '0;
                best_row <= 0;
            end

            if (edge_output_valid && edge_output_ready) begin
                histogram[edge_pixel] <= histogram[edge_pixel] + 1'b1;
                if (edge_output_start) begin
                    row_x <= 0;
                    row_y <= 0;
                end
                if (row_x == CROP_WIDTH - 1) begin
                    row_x <= 0;
                    scan_value <= 0;
                    cumulative_count <= 0;
                    low_median_found <= 1'b0;
                    profile_state <= SCAN_HISTOGRAM;
                end else begin
                    row_x <= row_x + 1;
                end
            end

            if ((profile_state == SCAN_HISTOGRAM) && en) begin
                if (!low_median_found && (LOW_MEDIAN_INDEX < scan_next_count)) begin
                    low_median_found <= 1'b1;
                    low_median_value <= 8'(scan_value);
                end

                if (HIGH_MEDIAN_INDEX < scan_next_count) begin
                    histogram <= '{default:'0};

                    if ((row_y == 0) || (weighted_score > best_score)) begin
                        best_score <= weighted_score;
                        best_row <= row_y;
                    end

                    if (row_y == CROP_HEIGHT - 1) begin
                        if ((row_y == 0) || (weighted_score > best_score)) begin
                            fill_percent <= (row_y * 256) / CROP_HEIGHT;
                        end else begin
                            fill_percent <= (best_row * 256) / CROP_HEIGHT;
                        end
                        result_valid <= 1'b1;
                        profile_state <= COLLECT_ROW;
                        row_y <= 0;
                    end else begin
                        row_y <= row_y + 1;
                        profile_state <= COLLECT_ROW;
                    end

                    scan_value <= 0;
                    cumulative_count <= 0;
                    low_median_found <= 1'b0;
                end else if (scan_value == 255) begin
                    histogram <= '{default:'0};
                    if ((row_y == 0) || (weighted_score > best_score)) begin
                        best_score <= weighted_score;
                        best_row <= row_y;
                    end
                    if (row_y == CROP_HEIGHT - 1) begin
                        if ((row_y == 0) || (weighted_score > best_score)) begin
                            fill_percent <= (row_y * 256) / CROP_HEIGHT;
                        end else begin
                            fill_percent <= (best_row * 256) / CROP_HEIGHT;
                        end
                        result_valid <= 1'b1;
                        profile_state <= COLLECT_ROW;
                        row_y <= 0;
                    end else begin
                        row_y <= row_y + 1;
                        profile_state <= COLLECT_ROW;
                    end
                    scan_value <= 0;
                    cumulative_count <= 0;
                    low_median_found <= 1'b0;
                end else begin
                    cumulative_count <= scan_next_count;
                    scan_value <= scan_value + 1;
                end
            end
        end
    end

    initial begin
        if ((WIDTH < 1) || (HEIGHT < 1)) $error("WIDTH and HEIGHT must be positive");
        if ((TOP_LEFT_X < 0) || (TOP_LEFT_Y < 0) ||
            (BOTTOM_RIGHT_X >= WIDTH) || (BOTTOM_RIGHT_Y >= HEIGHT) ||
            (TOP_LEFT_X > BOTTOM_RIGHT_X) || (TOP_LEFT_Y > BOTTOM_RIGHT_Y)) begin
            $error("Crop coordinates must be an inclusive region inside the image");
        end
        if ((BOTTOM_WEIGHT_PERCENT < 0) || (BOTTOM_WEIGHT_PERCENT > 100)) begin
            $error("BOTTOM_WEIGHT_PERCENT must be from 0 through 100");
        end
        if (WEIGHT_SIZE < WEIGHT_FRAC_BITS + 3) begin
            $error("WEIGHT_SIZE must represent the Q-format edge coefficient +/-2");
        end
    end

endmodule
