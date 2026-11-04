// Testbench for test.v (preprocess_top).
// Plays a camera frame from sim/frame_rgb.hex with row and frame blanking,
// and checks every output pixel against sim/expected_gray.hex.
//
//   python gen_preprocess_test.py
//   iverilog -g2005 -I sim -o sim/tb.vvp tb_preprocess.v test.v
//   vvp sim/tb.vvp
`timescale 1ns / 1ps

module tb_preprocess;
    `include "tb_params.vh"

    reg clk = 0;
    always #5 clk = ~clk;

    reg       rst = 1;
    reg       s_valid = 0, s_sof = 0, s_eol = 0;
    reg [7:0] s_r = 0, s_g = 0, s_b = 0;

    wire [31:0] m_tdata;         // 4 pixels per word, leftmost in [7:0]
    wire       m_tvalid, m_tuser, m_tlast, overrun;

    preprocess_top #(.X0(X0), .Y0(Y0), .W(CW), .H(CH)) dut (
        .clk(clk), .rst(rst),
        .s_valid(s_valid), .s_sof(s_sof), .s_eol(s_eol),
        .s_r(s_r), .s_g(s_g), .s_b(s_b),
        .m_tdata(m_tdata), .m_tvalid(m_tvalid), .m_tuser(m_tuser),
        .m_tlast(m_tlast), .overrun(overrun)
    );

    reg [23:0] frame    [0:FW*FH-1];
    reg [7:0]  expected [0:CW*CH-1];

    // ---------------- camera ----------------
    integer f, x, y;
    initial begin
        $readmemh("sim/frame_rgb.hex", frame);
        $readmemh("sim/expected_gray.hex", expected);

        repeat (5) @(posedge clk);
        rst <= 0;
        repeat (5) @(posedge clk);

        for (f = 0; f < NFRAMES; f = f + 1) begin
            for (y = 0; y < FH; y = y + 1) begin
                for (x = 0; x < FW; x = x + 1) begin
                    @(posedge clk);
                    s_valid <= 1;
                    s_sof   <= (x == 0 && y == 0);
                    s_eol   <= (x == FW - 1);
                    {s_r, s_g, s_b} <= frame[y*FW + x];
                end
                @(posedge clk);
                s_valid <= 0; s_sof <= 0; s_eol <= 0;
                repeat (HBLANK - 1) @(posedge clk);
            end
            repeat (VBLANK * (FW + HBLANK)) @(posedge clk);
        end

        repeat (100) @(posedge clk);
        report;
        $finish;
    end

    // ---------------- checker ----------------
    integer n = 0;               // pixel index within the current output frame
    integer frames_done = 0;
    integer errors = 0;
    integer flag_errors = 0;
    integer k;

    always @(posedge clk) begin
        if (m_tvalid) begin
            if (m_tuser) begin
                if (n != 0 && n != CW*CH) begin
                    $display("ERROR: start of frame after %0d pixels", n);
                    flag_errors = flag_errors + 1;
                end
                n = 0;
            end
            if (n >= CW*CH) begin
                $display("ERROR: extra pixel after a full frame");
                flag_errors = flag_errors + 1;
            end else begin
                for (k = 0; k < 4; k = k + 1)
                    if (m_tdata[k*8 +: 8] !== expected[n+k]) begin
                        if (errors < 10)
                            $display("ERROR: frame %0d pixel (x=%0d, y=%0d): got %0d, expected %0d",
                                     frames_done, (n+k) % CW, (n+k) / CW,
                                     m_tdata[k*8 +: 8], expected[n+k]);
                        errors = errors + 1;
                    end
                if (m_tuser !== (n == 0) || m_tlast !== (n % CW == CW - 4)) begin
                    if (flag_errors < 10)
                        $display("ERROR: tuser/tlast wrong at pixel %0d", n);
                    flag_errors = flag_errors + 1;
                end
                n = n + 4;
                if (n == CW*CH)
                    frames_done = frames_done + 1;
            end
        end
    end

    task report;
        begin
            $display("--------------------------------------------");
            $display("frames out: %0d of %0d", frames_done, NFRAMES);
            $display("pixel errors: %0d, tuser/tlast errors: %0d, overrun: %0d",
                     errors, flag_errors, overrun);
            if (frames_done == NFRAMES && errors == 0 && flag_errors == 0 && !overrun)
                $display("PASS");
            else
                $display("FAIL");
        end
    endtask
endmodule
