#!/usr/bin/env python3
import rospy
from substates.utility.controller import Controller
from auv_msgs.msg import ThrusterMicroseconds
from std_msgs.msg import Float64
import keyboard
import pickle

# forces produced by T200 thruster at 14V (N)
MAX_FWD_FORCE = 4.52 * 9.81
MAX_BKWD_FORCE = -3.52 * 9.81

reset_cmd = ThrusterMicroseconds([1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500])
rospy.init_node("joystick")
rospy.sleep(7)
x_pub = rospy.Publisher("/controls/force/global/x", Float64, queue_size=1)
y_pub = rospy.Publisher("/controls/force/global/y", Float64, queue_size=1)
z_pub = rospy.Publisher("/controls/force/global/z", Float64, queue_size=1)
roll_pub = rospy.Publisher("/controls/torque/roll", Float64, queue_size=1)
pitch_pub = rospy.Publisher("/controls/torque/pitch", Float64, queue_size=1)
yaw_pub = rospy.Publisher("/controls/torque/yaw", Float64, queue_size=1)


pub = rospy.Publisher("/propulsion/microseconds", ThrusterMicroseconds, queue_size=1)

controls = Controller(rospy.Time(0))


def reset_thrusters():
    pub.publish(reset_cmd)
    print("Safely shutting down thrusters")


RECORDING = []


def record_keyboard_state():
    global RECORDING
    keyboard_state = []
    if keyboard.is_pressed("esc"):
        keyboard_state.append("esc")
    if keyboard.is_pressed("w"):
        keyboard_state.append("w")
    if keyboard.is_pressed("s"):
        keyboard_state.append("s")
    if keyboard.is_pressed("a"):
        keyboard_state.append("a")
    if keyboard.is_pressed("d"):
        keyboard_state.append("d")
    if keyboard.is_pressed("q"):
        keyboard_state.append("q")
    if keyboard.is_pressed("e"):
        keyboard_state.append("e")
    if keyboard.is_pressed("o"):
        keyboard_state.append("o")
    if keyboard.is_pressed("u"):
        keyboard_state.append("u")
    if keyboard.is_pressed("i"):
        keyboard_state.append("i")
    if keyboard.is_pressed("k"):
        keyboard_state.append("k")
    if keyboard.is_pressed("j"):
        keyboard_state.append("j")
    if keyboard.is_pressed("l"):
        keyboard_state.append("l")
    if keyboard.is_pressed("r"):
        keyboard_state.append("r")
    RECORDING.append(keyboard_state)


def joystick(keyboard_state=None):
    desired_x_force = 0
    desired_y_force = 0
    desired_z_force = 0
    desired_x_torque = 0
    desired_y_torque = 0
    desired_z_torque = 0

    if keyboard_state is None:
        record_keyboard_state()
        keyboard_state = []

    current_force_amt = 0.5

    if keyboard.is_pressed("esc"):
        controls.kill()
        return False
    if keyboard.is_pressed("w") or "w" in keyboard_state:
        desired_x_force += current_force_amt * MAX_FWD_FORCE
    if keyboard.is_pressed("s") or "s" in keyboard_state:
        desired_x_force += current_force_amt * MAX_BKWD_FORCE
    if keyboard.is_pressed("a") or "a" in keyboard_state:
        desired_y_force += current_force_amt * MAX_FWD_FORCE
    if keyboard.is_pressed("d") or "d" in keyboard_state:
        desired_y_force += current_force_amt * MAX_BKWD_FORCE
    if keyboard.is_pressed("q") or "q" in keyboard_state:
        desired_z_force += current_force_amt * MAX_FWD_FORCE
    if keyboard.is_pressed("e") or "e" in keyboard_state:
        desired_z_force += current_force_amt * MAX_BKWD_FORCE
    if keyboard.is_pressed("o") or "o" in keyboard_state:
        desired_y_torque += current_force_amt * MAX_FWD_FORCE
    if keyboard.is_pressed("u") or "u" in keyboard_state:
        desired_y_torque += current_force_amt * MAX_BKWD_FORCE
    if keyboard.is_pressed("i") or "i" in keyboard_state:
        desired_y_torque += current_force_amt * MAX_FWD_FORCE
    if keyboard.is_pressed("k") or "k" in keyboard_state:
        desired_y_torque += current_force_amt * MAX_BKWD_FORCE
    if keyboard.is_pressed("j") or "j" in keyboard_state:
        desired_z_torque += current_force_amt * MAX_FWD_FORCE
    if keyboard.is_pressed("l") or "l" in keyboard_state:
        desired_z_torque += current_force_amt * MAX_BKWD_FORCE
    if keyboard.is_pressed("r") or "r" in keyboard_state:
        controls.rotateDeltaEuler([0, 0, 90])

    x_pub.publish(desired_x_force)
    y_pub.publish(desired_y_force)
    z_pub.publish(desired_z_force)
    roll_pub.publish(desired_x_torque)
    pitch_pub.publish(desired_y_torque)
    yaw_pub.publish(desired_z_torque)

    return True


print("NOTE: Launch controls.launch and propulsion.launch to use joystick.")

rospy.on_shutdown(reset_thrusters)

is_recording_res = input("Recording?")
is_recording = is_recording_res.lower() == "y"

print("SUBMERGING...")
controls.move([None, None, -0.75])
print("FLATTENING...")
controls.flatten()

print("\n\n\n")

print(" > R to make a 90 deg. YAW")
print(" > WASD for SURGE/SWAY")
print(" > Q/E for UP/DOWN")
print(" > IJKL for PITCH/YAW")
print(" > U/O for ROLL")
print(" > hold SPACE for max. force")
print(" > ESC to exit cleanly")

if is_recording:
    while not rospy.is_shutdown():
        stay_alive = joystick()
        rospy.sleep(0.01)
        if not stay_alive:
            break
    with open("keyboard_rec.pkl", "wb") as f:
        print("SAVING")
        pickle.dump(RECORDING, f)
    f.close() 
else:
    with open("keyboard_rec.pkl", "rb") as f:
        RECORDING = pickle.load(f)
    for keyboard_state in RECORDING:
        joystick(keyboard_state)
        rospy.sleep(0.01)

controls.kill()

# controls.freeze_pose()
# controls.freeze_position()
# controls.freeze_rotation()
# controls.move([0, 0, -2])
# controls.moveDeltaLocal([0, 0, -1])
# controls.rotate([1, 0, 0, 0])
# controls.rotateDelta([1, 0, 0, 0])
# controls.rotateEuler([0, 0, 180])
# controls.rotateDeltaEuler([0, 0, 180])
