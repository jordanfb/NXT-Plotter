G20         ; Set units to inches
G90         ; Absolute positioning
G1 Z1 F100      ; Move to clearance level

;
; Operation:    0
; Name:         
; Type:         Pocket
; Paths:        1
; Direction:    Conventional
; Cut Depth:    1
; Pass Depth:   1
; Plunge rate:  5
; Cut rate:     40
;

; Path 0
; Rapid to initial position
G1 X0.4350 Y0.3182 F100
G1 Z1.0000
; plunge
G1 Z0.0000 F5
; cut
G1 X0.3669 Y0.3224 F40
G1 X0.3416 Y0.4015
G1 X0.4429 Y0.5024
G1 X0.4350 Y0.3182
G1 X0.4827 Y0.2652
G1 X0.3297 Y0.2746
G1 X0.2847 Y0.4153
G1 X0.4984 Y0.6283
G1 X0.4827 Y0.2652
G1 X0.5305 Y0.2122
G1 X0.2925 Y0.2268
G1 X0.2277 Y0.4292
G1 X0.5539 Y0.7542
G1 X0.5305 Y0.2122
G1 X0.5782 Y0.1591
G1 X0.2553 Y0.1790
G1 X0.1708 Y0.4430
G1 X0.6094 Y0.8801
G1 X0.5782 Y0.1591
G1 X0.6260 Y0.1061
G1 X0.2181 Y0.1312
G1 X0.1139 Y0.4569
G1 X0.6649 Y1.0060
G1 X0.6260 Y0.1061
G1 X0.6737 Y0.0530
G1 X0.1809 Y0.0834
G1 X0.0569 Y0.4707
G1 X0.7204 Y1.1318
G1 X0.6737 Y0.0530
G1 X0.7215 Y-0.0000
G1 X0.1437 Y0.0355
G1 X0.0000 Y0.4846
G1 X0.7759 Y1.2577
G1 X0.7215 Y-0.0000
; Retract
G1 Z1.0000 F100

; Return to 0,0
G0 X0 Y0 F100
M2
