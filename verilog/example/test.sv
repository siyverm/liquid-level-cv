module test1 # (parameter int PIXEL_DATAWIDTH) (
    input logic [32-1:0] a,
    input logic [32-1:0] b,
    output logic [32-1:0] out
);

assign out = a + b;

endmodule

module testbench ();

logic [32-1:0] a;
logic [32-1:0] b;
logic [32-1:0] out;

test1 #(.PIXEL_DATAWIDTH(32)) module1 (.a(a), .b(b), .out(out));

initial begin
    // Setup VCD dump
    $dumpfile("waveform.vcd"); // Name of the VCD file to generate
    $dumpvars(0, testbench);    // Dump all variables in the testbench module and below

    a = 7;
    b = 8;

    #100

    $display("Time %0t: out = %b", $time, out);

    #10

    a = 15;
    b = 15;

    #100

    $display("Time %0t: out = %b", $time, out);
    
    $finish; // Good practice to end the simulation
end

endmodule


