`timescale 1ns / 1ps

module cache_controller2 (
    input              clk,
    input              rst_n,

    // CPU interface
    input              req_valid,
    input              req_rw,        // 0 = read, 1 = write
    input      [31:0]  req_addr,
    input      [31:0]  req_wdata,

    output reg         resp_valid,
    output reg [31:0]  resp_rdata,

    // Memory interface
    output reg         mem_req_valid,
    output reg         mem_req_rw,    // 0 = read, 1 = write
    output reg [31:0]  mem_addr,
    output reg [31:0]  mem_wdata,

    input              mem_ready,
    input      [31:0]  mem_rdata
);

    // =========================
    // STATE DEFINITIONS
    // =========================
    localparam IDLE         = 4'd0;
    localparam TAG_LOOKUP   = 4'd1;
    localparam READ_HIT     = 4'd2;
    localparam WRITE_HIT    = 4'd3;
    localparam MISS_HANDLE  = 4'd4;
    localparam WRITEBACK    = 4'd5;
    localparam ALLOCATE     = 4'd6;
    localparam REFILL       = 4'd7;
    localparam RESPOND      = 4'd8;

    reg [3:0] state, next_state;

    // =========================
    // CACHE METADATA (simple)
    // =========================
    reg        valid;
    reg        dirty;
    reg [19:0] tag;
    reg [31:0] data;

    wire [19:0] req_tag;
    assign req_tag = req_addr[31:12];

    // =========================
    // STATE REGISTER
    // =========================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state <= IDLE;
        else
            state <= next_state;
    end

    // =========================
    // NEXT STATE LOGIC (IF-ELSE)
    // =========================
    always @(*) begin
        next_state = state;

        if (state == IDLE) begin
            if (req_valid)
                next_state = TAG_LOOKUP;
        end

        else if (state == TAG_LOOKUP) begin
            if (valid && (tag == req_tag)) begin
                if (req_rw == 1'b0)
                    next_state = READ_HIT;
                else
                    next_state = WRITE_HIT;
            end else begin
                next_state = MISS_HANDLE;
            end
        end

        else if (state == READ_HIT) begin
            next_state = RESPOND;
        end

        else if (state == WRITE_HIT) begin
            next_state = RESPOND;
        end

        else if (state == MISS_HANDLE) begin
            if (valid && dirty)
                next_state = WRITEBACK;
            else
                next_state = ALLOCATE;
        end

        else if (state == WRITEBACK) begin
            if (mem_ready)
                next_state = ALLOCATE;
        end

        else if (state == ALLOCATE) begin
            if (mem_ready)
                next_state = REFILL;
        end

        else if (state == REFILL) begin
            next_state = RESPOND;
        end

        else if (state == RESPOND) begin
            next_state = IDLE;
        end
    end

    // =========================
    // OUTPUT + DATAPATH LOGIC
    // =========================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid         <= 0;
            dirty         <= 0;
            tag           <= 0;
            data          <= 0;

            resp_valid    <= 0;
            resp_rdata    <= 0;

            mem_req_valid <= 0;
            mem_req_rw    <= 0;
            mem_addr      <= 0;
            mem_wdata     <= 0;
        end else begin
            // Default outputs every cycle
            resp_valid    <= 0;
            mem_req_valid <= 0;

            if (state == READ_HIT) begin
                resp_rdata <= data;
            end

            else if (state == WRITE_HIT) begin
                data  <= req_wdata;
                dirty <= 1;
            end

            else if (state == WRITEBACK) begin
                mem_req_valid <= 1;
                mem_req_rw    <= 1; // write
                mem_addr      <= {tag, 12'b0};
                mem_wdata     <= data;
            end

            else if (state == ALLOCATE) begin
                mem_req_valid <= 1;
                mem_req_rw    <= 0; // read
                mem_addr      <= req_addr;
            end

            else if (state == REFILL) begin
                tag   <= req_tag;
                valid <= 1;

                if (req_rw) begin
                    data  <= req_wdata;
                    dirty <= 1;
                end else begin
                    data  <= mem_rdata;
                    dirty <= 0;
                end
            end

            else if (state == RESPOND) begin
                resp_valid <= 1;

                if (!req_rw)
                    resp_rdata <= data;
            end
        end
    end

endmodule
