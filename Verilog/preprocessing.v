// =============================================================================
// Liquid-level preprocessing on an FPGA
//
// What this replaces in Python (run_model_crop.py + making_model.predict):
//     cropped = frame[y1:y2, x1:x2]                       # crop_image_fixed
//     blur    = cv2.GaussianBlur(cropped, (15, 15), 0)
//     gray    = cv2.cvtColor(blur, cv2.COLOR_BGR2GRAY)
//     model.predict(gray[None, :, :, None])               # input shape (1, H, W, 1)
//
// The output is bit-exact with that Python code (checked by tb_preprocess.v).
//
// Block diagram (revised):
//
//   [Camera + demosaic IP]  RGB pixel stream, 1 pixel per clock enable
//          |
//          v
//   [crop_rgb]    keep only pixels inside the crop box
//          |      (no resizer: the model is built at the crop size W x H)
//          v
//   [gauss15]     15x15 Gaussian blur on R, G and B, OpenCV's integer kernel
//          |
//          v
//   [rgb2gray]    OpenCV's integer gray formula
//          |      (no ap_fixed step: every value stays an integer 0..255)
//          v
//   [pack32]      4 gray pixels per 32-bit word, for the 32-bit DMA / CPU bus
//          |
//          v
//   32-bit stream = model input, in raster order (= flattened (1,H,W,1) tensor)
//          |      byte 0 of each word is the leftmost pixel, so in memory the
//          |      bytes land in normal raster order (little-endian CPU).
//          |      (no FIFO needed: nothing here ever stalls the camera)
//          v
//   [Sobel + ReLU model] -> [row median] -> [weights] -> [argmax] -> fill %
//
// The blur runs before the gray conversion, same as Python. Doing gray first
// would save 2/3 of the line-buffer memory, but the +-1 rounding differences
// changed the detected liquid level in about 1 of 4 test crops.
//
// Timing requirements (pixel clock = clk, s_valid marks real pixels):
//   - each camera row (pixels + blanking) must last at least W + 16 clocks
//   - after the last crop row, at least 8 * (W + 15) clocks must pass before
//     the next frame starts (rows below the crop + vertical blanking).
//   'overrun' goes high if either is violated.
// =============================================================================


// -----------------------------------------------------------------------------
// Top level: camera RGB stream in, model-input gray stream out
// -----------------------------------------------------------------------------
module preprocess_top #(
    parameter X0 = 0,    // crop box left edge, in camera pixels
    parameter Y0 = 0,    // crop box top edge
    parameter W  = 64,   // crop width  (= model input width), multiple of 4
    parameter H  = 64    // crop height (= model input height)
)(
    input  wire       clk,
    input  wire       rst,

    // camera stream (one pixel when s_valid = 1)
    input  wire       s_valid,
    input  wire       s_sof,      // first pixel of a frame
    input  wire       s_eol,      // last pixel of a row
    input  wire [7:0] s_r,
    input  wire [7:0] s_g,
    input  wire [7:0] s_b,

    // model input stream (AXI4-Stream video style, 32-bit)
    output wire [31:0] m_tdata,   // 4 gray pixels {x+3, x+2, x+1, x}, each 0..255
    output wire        m_tvalid,
    output wire        m_tuser,   // 1 on the word holding pixel (0,0)
    output wire        m_tlast,   // 1 on the last word of each row
    output wire        overrun    // timing requirement broken (sticky)
);
    wire        c_valid, c_sof, c_eol;
    wire [23:0] c_rgb;
    wire        b_valid, b_sof, b_eol;
    wire [23:0] b_rgb;
    wire        g_valid, g_sof, g_eol;
    wire [7:0]  g_gray;

    crop_rgb #(.X0(X0), .Y0(Y0), .W(W), .H(H)) u_crop (
        .clk(clk), .rst(rst),
        .s_valid(s_valid), .s_sof(s_sof), .s_eol(s_eol), .s_rgb({s_r, s_g, s_b}),
        .m_valid(c_valid), .m_sof(c_sof), .m_eol(c_eol), .m_rgb(c_rgb)
    );

    gauss15 #(.W(W), .H(H), .CH(3)) u_blur (
        .clk(clk), .rst(rst),
        .s_valid(c_valid), .s_sof(c_sof), .s_eol(c_eol), .s_px(c_rgb),
        .m_valid(b_valid), .m_sof(b_sof), .m_eol(b_eol), .m_px(b_rgb),
        .overrun(overrun)
    );

    rgb2gray u_gray (
        .clk(clk), .rst(rst),
        .s_valid(b_valid), .s_sof(b_sof), .s_eol(b_eol), .s_rgb(b_rgb),
        .m_valid(g_valid), .m_sof(g_sof), .m_eol(g_eol), .m_gray(g_gray)
    );

    pack32 #(.W(W)) u_pack (
        .clk(clk), .rst(rst),
        .s_valid(g_valid), .s_sof(g_sof), .s_eol(g_eol), .s_gray(g_gray),
        .m_tdata(m_tdata), .m_tvalid(m_tvalid), .m_tuser(m_tuser), .m_tlast(m_tlast)
    );
endmodule


// -----------------------------------------------------------------------------
// Pack 4 gray pixels into one 32-bit word. The first pixel of each group goes
// in bits [7:0]. Rows must be a multiple of 4 pixels, so words never span rows.
// -----------------------------------------------------------------------------
module pack32 #(
    parameter W = 64     // row length, multiple of 4
)(
    input  wire        clk,
    input  wire        rst,
    input  wire        s_valid,
    input  wire        s_sof,
    input  wire        s_eol,
    input  wire [7:0]  s_gray,
    output reg  [31:0] m_tdata,
    output reg         m_tvalid,
    output reg         m_tuser,
    output reg         m_tlast
);
    initial begin
        if (W % 4 != 0) begin
            $display("pack32: W must be a multiple of 4");
            $finish;
        end
    end

    reg [1:0]  n;        // pixels held so far in this word
    reg [23:0] hold;     // pixels 0..2 of the word being built
    reg        sof_hold; // word being built starts the frame

    // a start of frame or the pixel after an end of row always begins a word
    wire [1:0] idx = s_sof ? 2'd0 : n;

    always @(posedge clk) begin
        if (rst) begin
            n        <= 0;
            sof_hold <= 0;
            m_tvalid <= 0;
            m_tuser  <= 0;
            m_tlast  <= 0;
        end else begin
            m_tvalid <= 1'b0;
            if (s_valid) begin
                if (idx == 2'd3) begin
                    m_tdata  <= {s_gray, hold};
                    m_tvalid <= 1'b1;
                    m_tuser  <= sof_hold;
                    m_tlast  <= s_eol;
                    n        <= 0;
                end else begin
                    hold[idx*8 +: 8] <= s_gray;
                    if (idx == 2'd0)
                        sof_hold <= s_sof;
                    // a row that ends mid-word can't happen when W % 4 == 0;
                    // if it does, drop the partial word and resync
                    n <= s_eol ? 2'd0 : idx + 1'b1;
                end
            end
        end
    end
endmodule


// -----------------------------------------------------------------------------
// Crop: pass only the W x H pixels inside the box, with new frame/row flags.
// Same as Python's frame[Y0:Y0+H, X0:X0+W].
// -----------------------------------------------------------------------------
module crop_rgb #(
    parameter X0 = 0,
    parameter Y0 = 0,
    parameter W  = 64,
    parameter H  = 64
)(
    input  wire        clk,
    input  wire        rst,
    input  wire        s_valid,
    input  wire        s_sof,
    input  wire        s_eol,
    input  wire [23:0] s_rgb,
    output reg         m_valid,
    output reg         m_sof,
    output reg         m_eol,
    output reg  [23:0] m_rgb
);
    reg  [11:0] x, y;     // position of the next camera pixel
    reg         synced;   // seen a start of frame since reset

    // position of the pixel arriving now
    wire [11:0] cx = s_sof ? 12'd0 : x;
    wire [11:0] cy = s_sof ? 12'd0 : y;

    wire in_box = (cx >= X0) && (cx < X0 + W) && (cy >= Y0) && (cy < Y0 + H);

    always @(posedge clk) begin
        if (rst) begin
            x       <= 0;
            y       <= 0;
            synced  <= 0;
            m_valid <= 0;
            m_sof   <= 0;
            m_eol   <= 0;
        end else begin
            m_valid <= 1'b0;
            if (s_valid) begin
                if (s_sof)
                    synced <= 1'b1;

                if (s_eol) begin
                    x <= 0;
                    y <= cy + 1'b1;
                end else begin
                    x <= cx + 1'b1;
                    y <= cy;
                end

                if (in_box && (synced || s_sof)) begin
                    m_valid <= 1'b1;
                    m_rgb   <= s_rgb;
                    m_sof   <= (cx == X0) && (cy == Y0);
                    m_eol   <= (cx == X0 + W - 1);
                end
            end
        end
    end
endmodule


// -----------------------------------------------------------------------------
// RGB -> gray, bit-exact with OpenCV 4.x cv2.COLOR_BGR2GRAY on 8-bit images:
//     gray = (9798*R + 19235*G + 3735*B + 16384) >> 15
// -----------------------------------------------------------------------------
module rgb2gray (
    input  wire        clk,  // pixel clock
    input  wire        rst,  // synchronous reset  
    input  wire        s_valid,  // pixel is present on the clock
    input  wire        s_sof,  // start of frame
    input  wire        s_eol,  // end of line
    input  wire [23:0] s_rgb,      // {R, G, B} declares a 24 bit vector that is equivalent of having 24 separate wires (8 wires per color value)
    output reg         m_valid,
    output reg         m_sof,
    output reg         m_eol,
    output reg  [7:0]  m_gray
);
    wire [23:0] acc = 24'd9798  * s_rgb[23:16] +
                      24'd19235 * s_rgb[15:8]  +
                      24'd3735  * s_rgb[7:0]   + 24'd16384;

    always @(posedge clk) begin
        if (rst) begin
            m_valid <= 0;
            m_sof   <= 0;
            m_eol   <= 0;
        end else begin
            m_valid <= s_valid;
            m_sof   <= s_valid && s_sof;
            m_eol   <= s_valid && s_eol;
            m_gray  <= acc[22:15];
        end
    end
endmodule


// -----------------------------------------------------------------------------
// 15x15 Gaussian blur on CH 8-bit channels, bit-exact with
// cv2.GaussianBlur(img, (15, 15), 0).
//
// OpenCV's integer kernel (sigma = 2.6), same on both axes, sums to 256:
//     1 3 6 12 20 30 36 40 36 30 20 12 6 3 1
// out = (sum over 15x15 of kv*kh*pixel + 32768) >> 16, for each channel
//
// Borders use BORDER_REFLECT_101 (OpenCV's default): row -1 -> row 1,
// row -2 -> row 2, and the same for columns.
//
// How it works:
//   Write side: each incoming row goes into one lane of a 16-row circular
//   line buffer (row k -> lane k mod 16). One RAM word holds the same column
//   of all 16 rows, so a single read gives a whole column.
//
//   Read side: once row r+7 has arrived, output row r is produced by scanning
//   the line buffer. The 15 rows it needs (r-7..r+7, reflected at the top and
//   bottom) are picked by lane; the column order is reflected too
//   (7,6,..,1,0,1,..,W-1,W-2,..,W-8), so the horizontal filter is a plain
//   15-tap filter with no edge cases.
//
//   Pipeline: read RAM -> pick 15 rows -> vertical sum -> 15-tap horizontal
//   sum -> round.
// -----------------------------------------------------------------------------
module gauss15 #(
    parameter W  = 64,   // row length, 8..2000
    parameter H  = 64,   // rows per frame, 8..2000
    parameter CH = 3     // 8-bit channels per pixel
)(
    input  wire          clk,
    input  wire          rst,
    input  wire          s_valid,
    input  wire          s_sof,
    input  wire          s_eol,
    input  wire [PW-1:0] s_px,
    output reg           m_valid,
    output reg           m_sof,
    output reg           m_eol,
    output reg  [PW-1:0] m_px,
    output reg           overrun
);
    localparam PW   = 8 * CH;    // bits per pixel
    localparam QEND = W + 13;    // last index of a reflected row scan (W + 14 reads)

    initial begin
        if (W < 8 || H < 8 || W > 2000 || H > 2000) begin
            $display("gauss15: W and H must be between 8 and 2000");
            $finish;
        end
    end

    // kernel weight for tap i (0..14)
    function [5:0] K;
        input [3:0] i;
        reg   [3:0] k;
        begin
            k = (i < 7) ? i : 4'd14 - i;
            case (k)
                0: K = 1;   1: K = 3;   2: K = 6;   3: K = 12;
                4: K = 20;  5: K = 30;  6: K = 36;  default: K = 40;
            endcase
        end
    endfunction

    // ---------------- write side: 16-row circular line buffer ----------------
    reg  [16*PW-1:0] lb [0:W-1];
    reg  [11:0]      wr_row;      // rows fully received this frame
    reg  [11:0]      wr_col;

    wire [11:0] in_row  = s_sof ? 12'd0 : wr_row;
    wire [11:0] in_col  = s_sof ? 12'd0 : wr_col;
    wire [15:0] lane_we = s_valid ? (16'd1 << in_row[3:0]) : 16'd0;

    // one always block per lane, so tools infer a byte-write-enable RAM
    genvar g;
    generate
        for (g = 0; g < 16; g = g + 1) begin : lane
            always @(posedge clk)
                if (lane_we[g])
                    lb[in_col][g*PW +: PW] <= s_px;
        end
    endgenerate

    // ---------------- read side: scan control ----------------
    reg        scanning;
    reg [11:0] q;                 // position in the reflected column order
    reg [11:0] r;                 // output row being produced (H = frame done)
    reg [3:0]  lane_sel [0:14];   // lane holding each of the 15 rows for row r

    wire start = !scanning && (r < H) &&
                 ((wr_row >= r + 8) || (wr_row == H)) &&
                 !(s_valid && s_sof);

    integer d, m;

    always @(posedge clk) begin
        if (rst) begin
            wr_row   <= 0;
            wr_col   <= 0;
            r        <= H;
            q        <= 0;
            scanning <= 0;
            overrun  <= 0;
        end else begin
            // count incoming rows and columns
            if (s_valid) begin
                if (s_eol) begin
                    wr_col <= 0;
                    wr_row <= in_row + 1'b1;
                end else begin
                    wr_col <= in_col + 1'b1;
                    wr_row <= in_row;
                end
                // starting row k overwrites row k-16, which rows up to k-9 still need
                if (in_col == 0 && r + 8 < in_row)
                    overrun <= 1'b1;
            end

            if (s_valid && s_sof) begin
                // new frame: the previous one must be fully processed
                if (scanning || r != H)
                    overrun <= 1'b1;
                r        <= 0;
                scanning <= 0;
            end else if (start) begin
                // pick rows r-7..r+7, reflected into 0..H-1
                for (d = 0; d < 15; d = d + 1) begin
                    m = r;
                    m = m + d - 7;
                    if (m < 0)
                        m = -m;
                    else if (m > H - 1)
                        m = 2 * (H - 1) - m;
                    lane_sel[d] <= m[3:0];
                end
                q        <= 0;
                scanning <= 1'b1;
            end else if (scanning) begin
                q <= q + 1'b1;
                if (q == QEND) begin
                    scanning <= 1'b0;
                    r        <= r + 1'b1;
                end
            end
        end
    end

    // column to read for scan position q: 7,6,..,1, 0,1,..,W-1, W-2,..,W-8
    wire [11:0] rd_col = (q < 7)     ? (12'd7 - q) :
                         (q < W + 7) ? (q - 12'd7) :
                                       (2 * W + 5 - q);

    reg [16*PW-1:0] rdata;
    always @(posedge clk)
        rdata <= lb[rd_col];

    // ---------------- filter pipeline ----------------
    reg            v1, v2, v3;
    reg  [11:0]    q1, q2, q3;
    reg  [11:0]    r1, r2, r3;
    reg  [PW-1:0]  tap [0:14];    // the 15 rows of one column
    reg  [16*CH-1:0] sr [0:14];   // last 15 vertical sums (sr[0] = newest)
    reg  [16*CH-1:0] vsum;        // vertical sum, 16 bits per channel
    reg  [PW-1:0]  rounded;       // finished pixel, 8 bits per channel
    reg  [15:0]    vs;
    reg  [23:0]    hs;

    integer c, i;
    always @* begin
        for (c = 0; c < CH; c = c + 1) begin
            vs = 0;
            hs = 0;
            for (i = 0; i < 15; i = i + 1) begin
                vs = vs + K(i) * tap[i][c*8 +: 8];
                hs = hs + K(i) * sr[i][c*16 +: 16];
            end
            vsum[c*16 +: 16] = vs;
            hs = hs + 24'd32768;            // round to nearest
            rounded[c*8 +: 8] = hs[23:16];
        end
    end

    integer j;
    always @(posedge clk) begin
        if (rst) begin
            v1      <= 0;
            v2      <= 0;
            v3      <= 0;
            m_valid <= 0;
            m_sof   <= 0;
            m_eol   <= 0;
        end else begin
            // stage 1: RAM word for scan position q is in rdata
            v1 <= scanning;  q1 <= q;   r1 <= r;

            // stage 2: pick the 15 rows out of the 16 lanes
            v2 <= v1;        q2 <= q1;  r2 <= r1;
            for (j = 0; j < 15; j = j + 1)
                tap[j] <= rdata[lane_sel[j]*PW +: PW];

            // stage 3: vertical sum, shifted into the horizontal window
            v3 <= v2;        q3 <= q2;  r3 <= r2;
            if (v2) begin
                sr[0] <= vsum;
                for (j = 1; j < 15; j = j + 1)
                    sr[j] <= sr[j-1];
            end

            // stage 4: horizontal sum and rounding. Output column x = q3 - 14.
            m_valid <= v3 && (q3 >= 14);
            m_px    <= rounded;
            m_sof   <= v3 && (q3 == 14) && (r3 == 0);
            m_eol   <= v3 && (q3 == QEND);
        end
    end
endmodule
