import nxt
import math
import threading
import time
import sys
import os # for file paths for the g-code

b = None
mx = None
my = None
mz = None
bx = None
bz = None
c = None

try:
	b = nxt.find_one_brick(name="Jordan", method = nxt.Method(usb=True, bluetooth=True, device = True)) # , debug=True
	mx = nxt.Motor(b, nxt.PORT_A)
	my = nxt.Motor(b, nxt.PORT_B)
	mz = nxt.Motor(b, nxt.PORT_C)
	
	bx = nxt.Touch(b, nxt.PORT_1)
	bz = nxt.Touch(b, nxt.PORT_2)
	c = nxt.Color20(b, nxt.PORT_3)
	print("Connection Initialized")
except:
	print("Error connecting to the brick")

x_scalar = 1
y_scalar = 1

x_slop = 360*5 # the amount to go extra when changing direction
y_slop = 360*2.5

x_previous_direction = -1 # for slop tracking/accounting purposes
y_previous_direction = 0

coords = [0, 0, 1] # start at 0, 0, with the pen raised.
max_coords = (78000, 110000, 1) # these are safety margins, not where the paper is
paper_bounds = [0, 0] # we find these with the light sensor!
# direct width starting off paper: 70920 (moving right)
# width starting on paper: 74160 (moving left)
# width starting on paper: 70920 + (9 + 8) * 360 more (moving right)
# ^ that one equals 70920 + 6120 = 77040
# using the new lighting system:
# width starting off paper: 212 * 360 = 76320 (moving left)
# width starting off paper: 207 * 360 = 74520 (moving right)
# width starting on paper: 80640, moved 2520 degrees to get back onto the paper (moving left)
# width starting on paper: 81360, moved 2880 degrees to get back onto the paper (moving right)
# using the tacho, it was -83996 wide from the far edge of the paper to being zeroed
# let's figure out how far it is to the close edge of the paper by manually fuzzing it.
# 10 to start moving and then 11 to get to the paper, and one to check
# that put the tacho at -75279, the difference of the two is 8717, which is ~24.2*360
# call it 80036 wide? right around what everything else got

# height starting off paper: 71280 (moving down)
# height starting off paper: 71280 (moving up)
# height starting on paper: 73440 (moved 1440 onto the paper, moving down)
# height starting on paper: 73440 (moved 1080 onto the paper, moving up)
paper_dimensions = (77040, 71280)
inch_to_degrees = (9063.529411764706, 6480.0)
pen_light_offset = (35*360, 0) # if the light is at the edge of the paper, move this vector to get the pen where the light currently is
paper_brightness = 415
step_size = 360 # used for diagonal and circle lines

power_level_range = (40, 100)


# g-code interpretation settings:
g_code_scale = 4
add_paper_offsets_to_coords = True
g_code_additional_offset = [5000, 5000]


def zero_x():
	global x_previous_direction
	if bx.get_sample():
		# then run right until it's not pressed and a little extra so
		# that we can know which direction we last went
		mx.run(power=100 * x_scalar) # move right
		while bx.get_sample():
			pass
		time.sleep(1) # wait an extra bit so that we move further away
		mx.idle()
	# now actually zero it
	mx.run(power=-100 * x_scalar)
	while not bx.get_sample():
		pass # just wait for it to hit
	mx.brake()
	coords[0] = 0 # set the x coords!
	x_previous_direction = -1
	print("X axis zeroed")
	
def zero_z():
	# this is temporary because we don't have a z motor atm.
	#if not bz.get_sample():
	#    # then it's not already zeroed
	#    mz.run(power=80)
	#    while not bz.get_sample():
	#        pass # just wait for it to hit
	#    mz.idle()
	if not bz.get_sample():
		# then it's not already zeroed
		mz.run(power=100)
		while not bz.get_sample():
			pass # just wait for it to hit
		mz.idle()
	coords[2] = 1 # it's up!
	print("Z axis zeroed")

def pen_down():
	mz.run(power=-100)
	time.sleep(.25)
	mz.idle()
	coords[2] = 0

def pen_up():
	zero_z()

def is_over_paper():
	# return whether the light sensor is over paper
	return c.get_reflected_light(nxt.Type.COLORRED) >= paper_brightness

def find_paper_top():
	# assuming this is above the paper on the background then go down until it sees paper
	global y_previous_direction
	my.run(100*y_scalar)
	while not is_over_paper():
		pass
	my.brake()
	y_previous_direction = 1
	coords[1] = 0
	
def calculate_paper_bounds():
	# make sure to zero the x and z coords first!
	# this may set the y coordinate? I'm not quite sure at the moment
	# this assumes we're on a non-white background above the paper
	# when starting!
	# center yourself along the edge so we get a nice clean edge
	global y_previous_direction
	goto_simple(int(max_coords[0]/2), 0, 1)
	find_paper_top()
	print("Found top edge of paper")
	paper_bounds[1] = 0 + pen_light_offset[1] # for now just set the top to be at 0
	# now we've calcualted the top of the paper!
	goto_simple(int(max_coords[0]/2), 10000, 1)
	# now we keep going right until we don't see paper any more!
	x = coords[0]
	while is_over_paper():
		# move right a bit!
		x += 360
		goto_simple(x, 10000, 1)
	# now we know the max x coord of the paper! We should manually
	# test how big a sheet of paper is
	paper_bounds[0] = x - paper_dimensions[0] + pen_light_offset[0]
	print("Found paper bounds/offset: " + str(paper_bounds))

def continue_checking_side_bounds():
	# this is for if the sensor makes a mistake/goes over pen marks and doesn't find the actual edge
	x = coords[0]
	while is_over_paper():
		# move right a bit!
		x += 360
		goto_simple(x, 10000, 1)
	paper_bounds[0] = x - paper_dimensions[0] + pen_light_offset[0]
	print("Found paper bounds/offset: " + str(paper_bounds))
	
def measure_paper_width(motor, power_level, start_off_paper, step = 360):
	# use the light sensor to detect the paper dimensions and to help figure out slack
	# this is for manual calibration mainly
	# use whatever motor is passed in.
	# if it starts off the paper then it only goes in one direction
	# if it starts on the paper then it starts backwards and eventually
	# goes forwards once it leaves the paper
	measurement = 0
	if start_off_paper:
		# then we go forwards until we see the edge of the paper
		while c.get_reflected_light(nxt.Type.COLORRED) < paper_brightness:
			motor.turn(power_level, step)
		print("Found Paper")
	else:
		# then we go backwards until we're off the paper
		while c.get_reflected_light(nxt.Type.COLORRED) >= paper_brightness:
			while c.get_reflected_light(nxt.Type.COLORRED) >= paper_brightness:
				motor.turn(-power_level, step)
			print("Found a possible edge, waiting a second to see if it's correct")
			time.sleep(1)
		# then go back onto the edge
		while c.get_reflected_light(nxt.Type.COLORRED) < paper_brightness:
			while c.get_reflected_light(nxt.Type.COLORRED) < paper_brightness:
				motor.turn(power_level, step)
				measurement += step
			print("Found rising edge, waiting a second to see if it sticks")
			time.sleep(1)
		print("Found Paper")
		print("When returning to the paper it moved: " + str(measurement) + " degrees")
	print("Waiting 5 for inspection")
	time.sleep(5)
	while c.get_reflected_light(nxt.Type.COLORRED) >= paper_brightness:
		motor.turn(power_level, step)
		measurement += step
	print("Measured " + str(measurement) + " degrees")
	return measurement

def sign(i):
	if i < 0:
		return -1
	return 1

def lerp(a, b, t):
	return (b - a) * t + a

def handle_pen_height(z):
	if coords[2] != z:
		# then move the pen up or down!
		if z == 0:
			pen_down()
		elif z == 1:
			pen_up()
	coords[2] = z

def goto_simple(x, y, z):
	# this is used for calibration purposes mainly, it can't handle diagonals so really just don't use it
	global x_previous_direction
	global y_previous_direction
	min_x = min(x, max_coords[0])
	min_y = min(y, max_coords[1])
	# first change the z height to set drawing or not
	handle_pen_height(z)
	# then change x and y
	delta_x = min_x - coords[0]
	if sign(delta_x) != x_previous_direction:
		# then we should account for x slop!
		old_delta_x = delta_x
		delta_x -= x_previous_direction * x_slop
		print("Switching x direction accounting for slop: " + str(old_delta_x) + " => " + str(delta_x))
	mx.turn(x_scalar*sign(delta_x)*100, abs(delta_x))
	# now figure out the y delta
	delta_y = min_y - coords[1]
	if sign(delta_y) != y_previous_direction:
		# then we should account for y slop!
		old_delta_y = delta_y
		delta_y -= y_previous_direction * y_slop
		print("Switching y direction accounting for slop: " + str(old_delta_y) + " => " + str(delta_y))
	my.turn(y_scalar*sign(delta_y)*100, abs(delta_y))
	coords[0] = min_x
	coords[1] = min_y
	x_previous_direction = sign(delta_x)
	y_previous_direction = sign(delta_y)

#def goto_direct(x, y, z):
#    min_x = min(x, max_coords[0])
#    min_y = min(y, max_coords[1])
#    min_z = min(z, max_coords[2])
#    # first change the z height to set drawing or not
#    # not implemented because no z motor
#    # then for now change x and z
#    delta_x = min_x - coords[0]
#    #mx.turn(-sign(delta_x)*100, abs(delta_x))
#    delta_y = min_y - coords[1]
#    #my.turn(-sign(delta_y)*100, abs(delta_y))
#    total = abs(delta_x) + abs(delta_y)
#    angle = math.atan2(delta_y, delta_x)
#    c = math.cos(angle)
#    s = math.sin(angle)
#    x_power_level_trig = int(abs(lerp(power_level_range[0], power_level_range[1], abs(c))))
#    y_power_level_trig = int(abs(lerp(power_level_range[0], power_level_range[1], abs(s))))
#    
#    x_power_level = int(lerp(power_level_range[0], power_level_range[1], float(abs(delta_x))/total))
#    y_power_level = int(lerp(power_level_range[0], power_level_range[1], float(abs(delta_y))/total))
#    print("delta pos and power levels " + str(delta_x) + ", " + str(delta_y) + " => " + str(x_power_level) + ", " + str(y_power_level) + " => " + str(x_power_level_trig) + ", " + str(y_power_level_trig))
#
#    x_thread = threading.Thread(target=mx.turn, args=(-sign(delta_x)*x_power_level_trig, abs(delta_x)))
#    y_thread = threading.Thread(target=my.turn, args=(-sign(delta_y)*y_power_level_trig, abs(delta_y)))
#    
#    x_thread.start()
#    y_thread.start()
#    
#    x_thread.join()
#    y_thread.join()
#    
#    coords[0] = min_x
#    coords[1] = min_y
#    coords[2] = min_z

def convert_inches_to_degrees(x, y, z, scale = 1):
	nx = int(x * inch_to_degrees[0] * scale)
	ny = int(y * inch_to_degrees[1] * scale)
	nz = int(z)
	return [nx, ny, nz]
	
def handle_slop(dx, dy):
	# this tightens the gears etc. so that they're ready to move in the right direction if necessary
	global x_previous_direction
	global y_previous_direction
	if dx != 0:
		if sign(dx) != x_previous_direction:
			mx.turn(sign(dx) * x_scalar * 100, x_slop)
			x_previous_direction = sign(dx)
	if dy != 0:
		if sign(dy) != y_previous_direction:
			my.turn(sign(dy) * y_scalar * 100, y_slop)
			y_previous_direction = sign(dy)
	
def pair_motors(power_level, x, y, z):
	# this will calculate and move the motors correctly to get diagonal lines etc.
	dx = x - coords[0]
	dy = y - coords[1]
	if dx == 0 and dy == 0:
		handle_pen(z)
		return # already there!
	# handle the pen
	handle_pen_height(z)
	handle_slop(dx, dy) # this also handles setting the previous directions for slop in the future
	# now we're ready to calculate the ratio between them
	larger = dx
	smaller = dy
	larger_motor = mx
	smaller_motor = my
	larger_scalar = x_scalar
	smaller_scalar = y_scalar
	power_level = abs(power_level)
	if abs(dx) < abs(dy):
		# then swap them!
		larger = dy
		smaller = dx
		larger_motor = my
		smaller_motor = mx
		larger_scalar = y_scalar
		smaller_scalar = x_scalar
	# now we need to calculate the ratio of movement
	ratio = abs(smaller / larger)
	if ratio == 0:
		# then one of the motors isn't moving at all, only move the larger one which actually moves
		l_thread = threading.Thread(target=lead_motor, args=(larger_motor, sign(larger)*larger_scalar*power_level, abs(larger)))
		l_thread.start()
		l_thread.join()
	elif abs(ratio) == 1:
		# then it's a straight diagonal line which we can handle with two lead motors
		x_thread = threading.Thread(target=lead_motor, args=(mx, sign(dx)*x_scalar*power_level, abs(dx)))
		y_thread = threading.Thread(target=lead_motor, args=(my, sign(dy)*y_scalar*power_level, abs(dy)))
	
		x_thread.start()
		y_thread.start()
	
		x_thread.join()
		y_thread.join()
	else:
		# it's a weird line...
		l_thread = threading.Thread(target=lead_motor, args=(larger_motor, sign(larger)*larger_scalar*power_level, abs(larger)))
		s_thread = threading.Thread(target=follow_motor, args=(smaller_motor, larger_motor, larger_motor.get_tacho(), ratio, sign(smaller)*smaller_scalar*power_level, abs(smaller)))
		# follow_motor(motor_to_control, motor_to_watch, initial_watched_tacho, ratio, power_level, distance):
		
		#x_thread = threading.Thread(target=lead_motor, args=(mx, sign(dx)*x_scalar*100, abs(dx)))
		#w_thread = threading.Thread(target=test_listen_to_tacho_thread, args=(mx, mx.get_tacho(), sign(dx)*x_scalar*100, abs(dx)))
		#y_thread = threading.Thread(target=lead_motor, args=(my, sign(dy)*y_scalar*100, abs(delta_y)))
	
		l_thread.start()
		s_thread.start()
		#y_thread.start()
	
		l_thread.join()
		s_thread.join()
		#y_thread.join() 
	coords[0] = x
	coords[1] = y
		
def lead_motor(motor_to_control, power_level, distance):
	# this just moves the motor as normal
	motor_to_control.turn(power_level, distance)

def test_listen_to_tacho_thread(motor_to_watch, initial_tacho, power_level, distance):
	for i in range(100):
		print("Read tacho to be " + str(motor_to_watch.get_tacho()))
		sys.stdout.flush()
		#yield
	delta = motor_to_watch.get_tacho().__dict__["rotation_count"] - initial_tacho.__dict__["rotation_count"]
	goal_delta = sign(power_level) * distance
	print("Curr Delta: " + str(delta) + " goal delta " + str(goal_delta))
	sys.stdout.flush()

"""
motor_to_control -- the motor that this function will drive, the follower motor
motor_to_watch -- the lead motor that this function will follow
initial_watched_tacho -- a tacho reading of the watched motor taken before it starts moving
ratio -- smaller_distance/larger_distance -- used for calculating when to move
power_level -- should be signed in the direction of movement, probably 100 or -100
distance -- always positive, the number of degrees of movement
"""
def follow_motor(motor_to_control, motor_to_watch, initial_watched_tacho, ratio, power_level, distance):
	# this function is used to drive this motor slower than the other motor to create a diagonal line
	# this function will just wait until the other motor will make progress and then continue
	if distance == 0:
		return # we've made it! no more movement
	start = initial_watched_tacho.__dict__["rotation_count"]
	current = initial_watched_tacho.__dict__["rotation_count"]
	curr_watched_delta = 0
	# here we just go and keep checking until it gets there I guess?
	moved_distance = 0
	is_final_step = (distance - moved_distance) <= step_size * 2 # if you have less then two steps to go then just move all the way
	#print("Starting follow motor. Distance is: " + str(distance) +" Is Final Step: " + str(is_final_step))
	#sys.stdout.flush()
	while moved_distance < distance:
		# while we still have more distance to move, check how far the other motor has moved!
		current = motor_to_watch.get_tacho().__dict__["rotation_count"]
		curr_watched_delta = abs(current - start)
		to_move = curr_watched_delta * ratio - moved_distance
		if abs(to_move) > step_size:
			#print("to_move > step_size: " + str(to_move) +" Is Final Step: " + str(is_final_step))
			#sys.stdout.flush()
			# then take a step!
			# first check if we should just move all the way to the end though
			if is_final_step:
				# then just move all the way
				motor_to_control.turn(power_level, distance - moved_distance)
				moved_distance = distance
			else:
				# not the final step so move the step size
				motor_to_control.turn(power_level, step_size)
				moved_distance += step_size
				# then update the is_final_step value to see if the next step will be the final step
				is_final_step = (distance - moved_distance) <= step_size * 2

def stop_all_motors():
	mx.idle()
	my.idle()
	mz.idle()

def test_run_g_code(string, run=False):
	# the string is g-code, each line is a new instruction
	run = run and b != None # you can only actually run this script if we have a brick located!
	lines = string.split("\n")
	lines = [x.split(";")[0].strip() for x in lines] # ignore all the comments
	lines = [x for x in lines if len(x) > 0]
	# print(lines)
	goal_x = 0
	goal_y = 0
	goal_z = 0
	max_degree_coords = [-math.inf, -math.inf, -math.inf]
	min_degree_coords = [math.inf, math.inf, math.inf]
	absolute_positioning = True # False = relative, True = absolute
	for line in lines:
		# interpret the command!
		if len(line) == 0:
			continue
		command = line.split(" ")
		if len(command) == 0:
			continue
		# figure out what the command is!
		code = command[0].lower()
		for c in command:
			c = c.lower()
			if c[0] == "x":
				goal_x = float(c[1:])
			if c[0] == "y":
				goal_y = float(c[1:])
			if c[0] == "z":
				goal_z = float(c[1:])
		scaled_coords = convert_inches_to_degrees(goal_x, goal_y, goal_z, g_code_scale)
		if add_paper_offsets_to_coords:
			scaled_coords[0] += paper_bounds[0]
			scaled_coords[1] += paper_bounds[1]
		scaled_coords[0] += g_code_additional_offset[0]
		scaled_coords[1] += g_code_additional_offset[1]
		
		# here keep track of the max coords for test runs:
		for i in range(len(max_degree_coords)):
			max_degree_coords[i] = max(max_degree_coords[i], scaled_coords[i])
			min_degree_coords[i] = min(min_degree_coords[i], scaled_coords[i])
		
		# then actually check and run the commands!
		if code == "g0" or code == "g00":
			# then it's rapid movement
			print("G0", scaled_coords)
			if run:
				pair_motors(100, scaled_coords[0], scaled_coords[1], scaled_coords[2])
		elif code == "g1" or code == "g01":
			# then we're moving the head for an operation, which for us is identical to rapid movement
			print("G1", scaled_coords)
			if run:
				pair_motors(100, scaled_coords[0], scaled_coords[1], scaled_coords[2])
	print("Max Degree Coords", str(max_degree_coords))
	print("Min Degree Coords", str(min_degree_coords))
		
		
def open_test_gcode_file(file = "test_files/JOutside.gcode"):
	script_path = sys.argv[0]
	dir_path = os.path.dirname(script_path)
	full_path = os.path.join(dir_path, file)
	f = open(full_path)
	l = f.read()
	return l
		

# general setup for a drawing:
# put it so the y axle is over the top edge of the paper, and the light sensor is over the backdrop in order to detect the edge
if b != None:
	pass
	# zero_x()
	# zero_z() # make sure the pen is up obviously
	# calculate_paper_bounds() # now it'll figure out where the paper actually is using the light sensor
	#continue_checking_side_bounds() # use this if it stops early due to an error or it going over pen marks or something
	# then it should know where the paper is and where the coordinates are and be all set! Hopefully!
	# I reccomend using http://jscut.org/jscut.html to convert SVGs to g-code

s = open_test_gcode_file()
test_run_g_code(s)
