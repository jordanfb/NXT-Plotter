G20         ; Set units to inches
G90         ; Absolute positioning
G1 Z1 F100      ; Move to clearance level

;
; Operation:    0
; Name:         
; Type:         Engrave
; Paths:        1
; Direction:    Conventional
; Cut Depth:    1
; Pass Depth:   1
; Plunge rate:  5
; Cut rate:     40
;

; Path 0
; Rapid to initial position
G1 X0.0595 Y1.5699 F100
G1 Z1.0000
; plunge
G1 Z0.0000 F5
; cut
G1 X0.0447 Y1.3393 F40
G1 X0.7217 Y1.2798
G1 X0.7143 Y0.2902
G1 X0.4464 Y0.1339
G1 X0.2753 Y0.2827
G1 X0.2083 Y0.5952
G1 X0.0000 Y0.6101
G1 X0.1116 Y0.1711
G1 X0.4092 Y-0.0000
G1 X0.7515 Y0.1116
G1 X0.9003 Y0.4911
G1 X0.9301 Y1.3244
G1 X1.5030 Y1.2798
G1 X1.4955 Y1.4881
G1 X0.0595 Y1.5699
G1 X0.0595 Y1.5699
; Retract
G1 Z1.0000 F100

; Return to 0,0
G0 X0 Y0 F100
M2
