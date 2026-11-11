module model 
    import model_pkg::*;
# (
    parameter int WIDTH=1080, HEIGHT=1920, PIXEL_WIDTH=8,
    parameter int TOP_LEFT_X=0, TOP_LEFT_Y=0, BOTTOM_RIGHT_X=WIDTH, BOTTOM_RIGHT_Y=HEIGHT // represents the crop coordinate indices (inclusive)
)(
    input clk, rst_n, en, 
    input image_start, output_ready,
    input logic [PIXEL_WIDTH-1:0] pixel [3], // Red, Green, Blue, 8 bit color format
    output int fill_percent
);

/*
Plan: data flow approach

One pixel gets streamed per clock cycle into the pixel input.

1. grayscale the image using a qxymultiply and adder: Gray = 0.299·R + 0.587·G + 0.114·B for each pixel.

build kernel module that takes in 1 pixel at a time, and has a ready signal per pixel input. image start and image end signal.
output is 1 pixel of the new image, as well as a ready signal per output. unchanged dimensions with padding if the kernel goes past the image.
- allows for float kernel values

2. kernel blur
3. kernel edge
4. for each row, take the median value, leading to a 1d array of values. multiply bottom values by a fraction to ignore bottom of cup.
5. Argmax: find index of the highest value. This is the water level height.
6. index/HEIGHT = fill percent, since image will be cropped so the bottom and top align with container

*/

logic signed [BOTTOM_LEFT_X:TOP_RIGHT_X][BOTTOM_LEFT_Y:TOP_RIGHT_Y][DATA_WIDTH-1:0] blurred_cropped_image;
logic signed [BOTTOM_LEFT_X + 1:TOP_RIGHT_X-1][BOTTOM_LEFT_Y + 1:TOP_RIGHT_Y-1][DATA_WIDTH-1:0] edge_conv2D_sum;
logic signed [BOTTOM_LEFT_X + 1:TOP_RIGHT_X-1][BOTTOM_LEFT_Y + 1:TOP_RIGHT_Y-1][DATA_WIDTH-1:0] edge_conv2D_sum_abs;

logic signed [0:K-1][0:K-1][WEIGHT_SIZE-1:0] blur_filter; //3 by 3 K
//hardcoding - change to variable later
assign blur_filter = '{
  '{ WEIGHT_SIZE'(1),  WEIGHT_SIZE'(1),  WEIGHT_SIZE'(1)  }, // Row 0
  '{ WEIGHT_SIZE'(1),  WEIGHT_SIZE'(1),  WEIGHT_SIZE'(1)  }, // Row 1
  '{ WEIGHT_SIZE'(1), WEIGHT_SIZE'(1), WEIGHT_SIZE'(1) }  // Row 2
};

kernel # (
    .WIDTH(WIDTH),
    .HEIGHT(HEIGHT),
    .FRAC_BITS(FRAC_BITS),
    .WEIGHT_SIZE(WEIGHT_SIZE),
    .WEIGHT_FRAC_BITS(WEIGHT_FRAC_BITS),
    .K(3),
    .BOTTOM_LEFT_X(BOTTOM_LEFT_X-1),
    .BOTTOM_LEFT_Y(BOTTOM_LEFT_Y-1),
    .TOP_RIGHT_X(TOP_RIGHT_X+1),
    .TOP_RIGHT_Y(TOP_RIGHT_Y+1)
)
blur (
    .clk(clk), 
    .rst_n(rst_n),
    .en(en),
    .image(image), 
    .filter(blur_filter), 
    .out(blurred_cropped_image)
);

logic signed [0:K-1][0:K-1][WEIGHT_SIZE-1:0] edge_filter; //3 by 3 K
//hardcoding - change to variable later
assign edge_filter = '{
  '{ WEIGHT_SIZE'(1),  WEIGHT_SIZE'(2),  WEIGHT_SIZE'(1)  }, // Row 0
  '{ WEIGHT_SIZE'(0),  WEIGHT_SIZE'(0),  WEIGHT_SIZE'(0)  }, // Row 1
  '{ WEIGHT_SIZE'(-1), WEIGHT_SIZE'(-2), WEIGHT_SIZE'(-1) }  // Row 2
};

kernel # (
    .WIDTH(TOP_RIGHT_X - BOTTOM_LEFT_X + 1),
    .HEIGHT(TOP_RIGHT_Y - BOTTOM_LEFT_Y + 1),
    .FRAC_BITS(FRAC_BITS),
    .WEIGHT_SIZE(WEIGHT_SIZE),
    .WEIGHT_FRAC_BITS(WEIGHT_FRAC_BITS),
    .K(3),
    .BOTTOM_LEFT_X(BOTTOM_LEFT_X),
    .BOTTOM_LEFT_Y(BOTTOM_LEFT_Y),
    .TOP_RIGHT_X(TOP_RIGHT_X),
    .TOP_RIGHT_Y(TOP_RIGHT_Y)
)
edge_detect (
    .clk(clk), 
    .rst_n(rst_n),
    .en(en),
    .image(blurred_cropped_image), 
    .filter(edge_filter), 
    .out(edge_conv2D_sum)
);

generate //applying the absolute value function so all edges are high positive values
    for (genvar i = BOTTOM_LEFT_X + 1; i < TOP_RIGHT_X; i++) begin: adder_x
        for (genvar j = BOTTOM_LEFT_Y + 1; j < TOP_RIGHT_Y; j++) begin: adder_y
            assign edge_conv2D_sum_abs[i][j] = (edge_conv2D_sum[i][j] < 0) ? -edge_conv2D_sum[i][j]: edge_conv2D_sum[i][j];
        end
    end
endgenerate

endmodule