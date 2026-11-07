package model_pkg;
    function automatic int adder_tree_block_latency(int num, int max_adds);
        // Num levels = latency = ceil(log_{max_adds}(num))
        // Use while loop to avoid floating point silent errors
        int latency = 0;
        int MAX_WIDTH = 1;
        while (MAX_WIDTH < num) begin
            MAX_WIDTH = MAX_WIDTH * max_adds;
            latency++;
        end
        return (latency < 1) ? 1 : latency; // Minimum latency of 1
    endfunction
  endpackage