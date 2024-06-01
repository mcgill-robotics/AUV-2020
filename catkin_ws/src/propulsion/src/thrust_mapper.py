#!/usr/bin/env python3

"""

Description: Thrust mapper node subscribes to effort topic, converts the wrench readings to forces, 
and then finally converts the forces to pwm signals and publishes them.

"""

import numpy as np
import rospy
from thrust_mapper_utils import *
from auv_msgs.msg import ThrusterForces, ThrusterMicroseconds
from geometry_msgs.msg import Wrench
import math

# distances in m
dx_1 = 0.397  # T1 -> T2
dx_2 = 0.395  # T7 -> T8, T5 -> T6
dy_1 = 0.514  # T6 -> T7, T5 -> T8
dy_2 = 0.779  # perpendicular T3 -> T4

Dx = 0.67
d_A3_x = 0.055
d_og_x = 23 / 49 * Dx
d_g3_x = (Dx - d_og_x) + d_A3_x  # perpendicular COM -> T3
d_g4_x = d_og_x + d_A3_x  # perpendicular COM -> T4

d_47_x = 0.15
d_g3_x = 0.46
d_g4_x = 0.32

d_g7_x = d_g4_x - d_47_x
d_g5_x = d_g3_x - d_47_x


T = np.matrix(
    [
        [-1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, -1.0, -1.0, -1.0, -1.0],
        [0.0, 0.0, 0.0, 0.0, -dx_2 / 2, dx_2 / 2, dx_2 / 2, -dx_2 / 2],
        [0.0, 0.0, 0.0, 0.0, dy_1 / 2, dy_1 / 2, -dy_1 / 2, -dy_1 / 2],
        [dx_1 / 2, -dx_1 / 2, dy_2 / 2, dy_2 / 2, 0.0, 0.0, 0.0, 0.0],
    ]
)


# T = np.matrix(
#         [[    -1.,     -1.,   0.,   0.,      0.,     0.,     0.,       0.],
#         [      0.,      0.,   1.,  -1.,      0.,     0.,     0.,       0.],
#         [      0.,      0.,   0.,   0.,     -1.,    -1.,    -1.,      -1.],
#         [      0.,      0.,   0.,   0., -dx_2/2, dx_2/2,  dx_2/2, -dx_2/2],
#         [      0.,      0.,   0.,   0.,  d_g5_x, d_g5_x, -d_g7_x, d_g7_x],
#         [  dx_1/2, -dx_1/2, d_g3_x, d_g4_x,      0.,     0.,      0.,      0.]]
#         )

# forces produced by T200 thruster at 14V (N)
MAX_FWD_FORCE = 4.52 * 9.81
MAX_BKWD_FORCE = -3.52 * 9.81

# Matrix representation of the system of equations representing the thrust to wrench conversion
# Ex: Force_X = (1)FRONT_LEFT_Thruster + (1)FRONT_RIGHTboard_Thrust

# matrix transformation wrench -> thrust
T_inv = np.linalg.pinv(T)
"""--------------------------------------------------"""
rospy.sleep(7.0)  # TODO: FIX - wait for 7 sec to sync with arduino?


def wrench_to_thrust(w):
    """
    A callback function that maps a Wrench into a force produced by T200 thruster at 14V (N)
    """
    a = np.array(
        [
            [w.force.x],
            [w.force.y],
            [w.force.z],
            [w.torque.x],
            [w.torque.y],
            [w.torque.z],
        ]
    )

    converted_w = np.matmul(T_inv, a)
    tf = ThrusterForces()

    tf.FRONT_LEFT = converted_w[0]
    tf.FRONT_RIGHT = converted_w[1]
    tf.BACK_LEFT = converted_w[2]
    tf.BACK_RIGHT = converted_w[3]
    tf.HEAVE_FRONT_LEFT = converted_w[4]
    tf.HEAVE_FRONT_RIGHT = converted_w[5]
    tf.HEAVE_BACK_LEFT = converted_w[6]
    tf.HEAVE_BACK_RIGHT = converted_w[7]

    # this is used by the sim
    pub_forces.publish(tf)

    # Convert forces to pwm signals and publish
    forces_to_pwm_publisher(tf)


def forces_to_pwm_publisher(forces_msg):
    """
    Publish pwm signals
    """
    pwm_arr = [None] * 8
    pwm_arr[ThrusterMicroseconds.FRONT_LEFT] = force_to_pwm(
        forces_msg.FRONT_LEFT, MAX_FWD_FORCE, MAX_BKWD_FORCE
    )
    pwm_arr[ThrusterMicroseconds.FRONT_RIGHT] = force_to_pwm(
        forces_msg.FRONT_RIGHT, MAX_FWD_FORCE, MAX_BKWD_FORCE
    )
    pwm_arr[ThrusterMicroseconds.BACK_LEFT] = force_to_pwm(
        forces_msg.BACK_LEFT, MAX_FWD_FORCE, MAX_BKWD_FORCE
    )
    pwm_arr[ThrusterMicroseconds.BACK_RIGHT] = force_to_pwm(
        forces_msg.BACK_RIGHT, MAX_FWD_FORCE, MAX_BKWD_FORCE
    )
    pwm_arr[ThrusterMicroseconds.HEAVE_FRONT_LEFT] = force_to_pwm(
        forces_msg.HEAVE_FRONT_LEFT, MAX_FWD_FORCE, MAX_BKWD_FORCE
    )
    pwm_arr[ThrusterMicroseconds.HEAVE_FRONT_RIGHT] = force_to_pwm(
        forces_msg.HEAVE_FRONT_RIGHT, MAX_FWD_FORCE, MAX_BKWD_FORCE
    )
    pwm_arr[ThrusterMicroseconds.HEAVE_BACK_LEFT] = force_to_pwm(
        forces_msg.HEAVE_BACK_LEFT, MAX_FWD_FORCE, MAX_BKWD_FORCE
    )
    pwm_arr[ThrusterMicroseconds.HEAVE_BACK_RIGHT] = force_to_pwm(
        forces_msg.HEAVE_BACK_RIGHT, MAX_FWD_FORCE, MAX_BKWD_FORCE
    )

    # TODO - these are temporary precautionary measures and may result in unwanted dynamics
    # so as not to trip individual fuse (limit current draw)

    thruster_lower_limit = rospy.get_param("thruster_PWM_lower_limit")
    thruster_upper_limit = rospy.get_param("thruster_PWM_upper_limit")

    for i in range(len(pwm_arr)):
        if pwm_arr[i] > thruster_upper_limit:
            pwm_arr[i] = thruster_upper_limit
            print("INDIVIDUAL FUSE EXCEEDED: T", i + 1)
        elif pwm_arr[i] < thruster_lower_limit:
            pwm_arr[i] = thruster_lower_limit
            print("INDIVIDUAL FUSE EXCEEDED: T", i + 1)

    pwm_msg = ThrusterMicroseconds(pwm_arr)
    pub_us.publish(pwm_msg)


# turns off the thursters when the node dies
def shutdown():
    msg = ThrusterMicroseconds([1500] * 8)
    pub_us.publish(msg)


# sends the arming signal to the thursters upon startup
def re_arm():
    rospy.sleep(1)
    msg1 = ThrusterMicroseconds([1500] * 8)
    msg2 = ThrusterMicroseconds([1540] * 8)

    pub_us.publish(msg1)
    rospy.sleep(0.5)
    pub_us.publish(msg2)
    rospy.sleep(0.5)
    pub_us.publish(msg1)


if __name__ == "__main__":
    rospy.init_node("thrust_mapper")
    pub_us = rospy.Publisher(
        "/propulsion/microseconds", ThrusterMicroseconds, queue_size=1
    )
    pub_forces = rospy.Publisher("/propulsion/forces", ThrusterForces, queue_size=1)
    rospy.Subscriber("/controls/effort", Wrench, wrench_to_thrust)
    rospy.on_shutdown(shutdown)
    re_arm()
    rospy.spin()
