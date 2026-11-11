module kernel 
    import model_pkg::*;
# (
    parameter int WIDTH=1080, HEIGHT=1920, PIXEL_WIDTH=8, WEIGHT_SIZE=4, WEIGHT_FRAC_BITS=0, K=3,
    parameter int TOP_LEFT_X=0, TOP_LEFT_Y=0, BOTTOM_RIGHT_X=WIDTH, BOTTOM_RIGHT_Y=HEIGHT, // represents the crop coordinate indices
    localparam int MULT_WIDTH = PIXEL_WIDTH + WEIGHT_SIZE,
    localparam int SUM_WIDTH = MULT_WIDTH + $clog2(K**2),
    localparam int WIDTH_BITS = $clog2(WIDTH),
    localparam int HEIGHT_BITS = $clog2(HEIGHT),
    localparam int CROPPED_WIDTH = BOTTOM_RIGHT_X-TOP_LEFT_X+1,
    localparam int CROPPED_HEIGHT = BOTTOM_RIGHT_Y-TOP_LEFT_Y+1,
    localparam int CROPPED_WIDTH_BITS = $clog2(CROPPED_WIDTH),
    localparam int CROPPED_HEIGHT_BITS = $clog2(CROPPED_HEIGHT),
    localparam int START_CALC = K / 2
)(
    input clk, rst_n, en, 
    input input_ready, output_ready, input_image_start, output_image_start,
    input logic [PIXEL_WIDTH-1:0] pixel, //grayscaled
    input logic signed [WEIGHT_SIZE-1:0] filter [0:K-1][0:K-1],
    output logic signed [PIXEL_WIDTH-1:0] out [TOP_LEFT_X:BOTTOM_RIGHT_X][TOP_LEFT_Y:BOTTOM_RIGHT_Y]
);

logic [WIDTH_BITS-1:0] im_x;
logic [HEIGHT_BITS-1:0] im_y;
logic [PIXEL_WIDTH-1:0] image [WIDTH][HEIGHT];

always_ff @(posedge clk) begin
    if (!rst_n) begin
        im_x <= 0;
        im_y <= 0;
    end else if (en) begin
        if (input_image_start) begin
            image[0][0] <= pixel;
            im_x <= 1;
            im_y <= 0;
        end else if (input_ready) begin
            image[im_x][im_y] <= pixel;

            if (im_x < WIDTH-1) begin
                im_x <= im_x + 1;
            end else begin
                im_x <= 0;
                im_y <= im_y + 1;
            end
        end
    end
end

// wait for the cropped portiob to be ready

logic [CROPPED_WIDTH_BITS-1:0] cf_x;
logic [CROPPED_HEIGHT_BITS-1:0] cf_y;
logic [PIXEL_WIDTH-1:0] cropped_filtered [CROPPED_WIDTH][CROPPED_HEIGHT];

always_ff @(posedge clk) begin
    if (!rst_n) begin
        im_x <= 0;
        im_y <= 0;
    end else if (en) begin
        if (im_y >= START_CALC && im_x >= START_CALC) begin
            im_x <= 0;
            im_y <= 0;
        end
    end
end
endmodule