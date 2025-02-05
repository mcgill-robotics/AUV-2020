#!/usr/bin/env python3


import rclpy
from rclpy import Duration
from rclpy.clock import Clock
from rclpy.node import Node
from rclpy.action import ActionServer
from rclpy.action.server import ServerGoalHandle
from rclpy.action.server import GoalResponse, CancelResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from servers.base_server import BaseServer
from std_msgs.msg import Bool
import actionlib
from auv_msgs.msg import StateQuaternionAction
from geometry_msgs.msg import Quaternion
import numpy as np
import quaternion


class StateQuaternionServer(BaseServer):
    def __init__(self, node_name_used):
        super().__init__(node_name_used)
        self.goal_handle_ : ServerGoalHandle = None #initializing a goal handle that can be used later

        self.server = ActionServer(
            self,
            StateQuaternionAction,
            "/controls/server/state",
            StateQuaternionAction,
            execute_cb=self.callback,
            goal_callback = self.goal_callback,
            cancel_callback=self.cancel_callback,
            execute_callback= self.execute_callback,
            callback_group=ReentrantCallbackGroup()
        )

        self.previous_goal_quat = None
        self.previous_goal_x = None
        self.previous_goal_y = None
        self.previous_goal_z = None
        self.goal_id = 0
        self.clock = Clock()

        self.enable_quat_sub = rclpy.create_subscription(
            Bool, "/controls/pid/quat/enable", self.quat_enable_cb
        )
        self.enable_x_sub = rclpy.create_subscription(
            Bool, "/controls/pid/x/enable", self.x_enable_cb
        )
        self.enable_y_sub = rclpy.create_subscription(
            Bool, "/controls/pid/y/enable", self.y_enable_cb
        )
        self.enable_z_sub = rclpy.create_subscription(
            Bool, "/controls/pid/z/enable", self.z_enable_cb
        )

        

    def x_enable_cb(self, data):
        if data.data == False:
            self.previous_goal_x = None

    def y_enable_cb(self, data):
        if data.data == False:
            self.previous_goal_y = None

    def z_enable_cb(self, data):
        if data.data == False:
            self.previous_goal_z = None

    def quat_enable_cb(self, data):
        if data.data == False:
            self.previous_goal_quat = None

    def goal_callback(self, goal_request: EffortAction.Goal):  
        # abort previous goal when getting new goal
        if self.goal_handle_ is not None and self.goal_handle_.is_active:
            self.goal_handle_.abort()
        return GoalResponse.ACCEPT

    def execute_callback(self, goal_handle: ServerGoalHandle):
        self.get_logger().info("\n\nQuaternion Server got goal:\n", goal_handle)
        self.goal_id += 1
        my_goal = self.goal_id
        self.cancelled = False
        self.goal = goal_handle
        if self.pose is not None:
            goal_position = [
                self.goal.pose.position.x,
                self.goal.pose.position.y,
                self.goal.pose.position.z,
            ]
            goal_quat = np.quaternion(
                self.goal.pose.orientation.w,
                self.goal.pose.orientation.x,
                self.goal.pose.orientation.y,
                self.goal.pose.orientation.z,
            )
            if self.goal.local.data:
                goal_position = self.local_to_global(goal_position)
            if self.goal.displace.data:
                goal_position, goal_quat = self.get_goal_after_displace(
                    goal_position, goal_quat
                )

            if self.goal.do_x.data:
                self.previous_goal_x = goal_position[0]
                self.pub_x_enable.publish(Bool(True))
                self.pub_surge.publish(0)
                self.pub_sway.publish(0)
                self.pub_x_pid.publish(goal_position[0])
            elif self.previous_goal_x is not None:
                goal_position[0] = self.previous_goal_x
                self.pub_x_enable.publish(Bool(True))
                self.pub_surge.publish(0)
                self.pub_sway.publish(0)
                self.pub_x_pid.publish(goal_position[0])
            else:
                goal_position[0] = None

            if self.goal.do_y.data:
                self.previous_goal_y = goal_position[1]
                self.pub_y_enable.publish(Bool(True))
                self.pub_surge.publish(0)
                self.pub_sway.publish(0)
                self.pub_y_pid.publish(goal_position[1])
            elif self.previous_goal_y is not None:
                goal_position[1] = self.previous_goal_y
                self.pub_y_enable.publish(Bool(True))
                self.pub_surge.publish(0)
                self.pub_sway.publish(0)
                self.pub_y_pid.publish(goal_position[1])
            else:
                goal_position[1] = None

            if self.goal.do_z.data:
                self.pub_z_enable.publish(Bool(True))

                safe_goal = max(
                    min(goal_position[2], rclpy.get_param("max_safe_goal_depth")),
                    rclpy.get_param("min_safe_goal_depth"),
                )
                if safe_goal != goal_position[2]:
                    self.get_logger().info(
                        "WARN: Goal changed from {}m to {}m for safety.".format(
                            goal_position[2], safe_goal
                        )
                    )
                self.previous_goal_z = safe_goal
                goal_position[2] = safe_goal
                self.pub_heave.publish(0)
                self.pub_z_pid.publish(safe_goal)
            elif self.previous_goal_z is not None:
                goal_position[2] = self.previous_goal_z
                self.pub_z_enable.publish(Bool(True))
                self.pub_heave.publish(0)
                self.pub_z_pid.publish(goal_position[2])
            else:
                goal_position[2] = None

            if self.goal.do_quaternion.data:
                self.previous_goal_quat = goal_quat
                self.pub_quat_enable.publish(Bool(True))
                goal_msg = Quaternion()
                goal_msg.w = goal_quat.w
                goal_msg.x = goal_quat.x
                goal_msg.y = goal_quat.y
                goal_msg.z = goal_quat.z
                self.pub_quat_pid.publish(goal_msg)
            elif self.previous_goal_quat is not None:
                goal_quat = self.previous_goal_quat
                self.pub_quat_enable.publish(Bool(True))
                goal_msg = Quaternion()
                goal_msg.w = goal_quat.w
                goal_msg.x = goal_quat.x
                goal_msg.y = goal_quat.y
                goal_msg.z = goal_quat.z
                self.pub_quat_pid.publish(goal_msg)
            else:
                goal_quat = None

            time_to_settle = rclpy.get_param("time_to_settle")
            settle_check_loop_time = 1.0 / rclpy.get_param("settle_check_rate")

            settled = False
            while (
                not settled
                and not self.cancelled
                and my_goal == self.goal_id
                and rclpy.ok()
            ):
                start = self.clock().now()
                while (
                    not self.cancelled
                    and my_goal == self.goal_id
                    and self.check_status(
                        goal_position,
                        goal_quat,
                        self.goal.do_x.data,
                        self.goal.do_y.data,
                        self.goal.do_z.data,
                        self.goal.do_quaternion.data,
                    )
                    and rclpy.ok()
                ):

                    if self.clock().now() - start > time_to_settle:
                        settled = True
                        self.get_logger().info("settled")
                        break
                    self.get_clock().sleep_for(Duration(seconds=5))
                    
        else:
            self.get_logger().info("FAILURE, STATE SERVER DOES NOT HAVE A POSE")

        if not self.cancelled and my_goal == self.goal_id:
            self.server.set_succeeded()

    def local_to_global(self, goal_position):
        pivot_quat = (
            self.previous_goal_quat
            if self.previous_goal_quat is not None
            else self.body_quat
        )
        global_goal = (
            pivot_quat
            * np.quaternion(0, goal_position[0], goal_position[1], goal_position[2])
            * pivot_quat.inverse()
        )
        return [global_goal.x, global_goal.y, global_goal.z]

    def get_goal_after_displace(self, goal_position_delta, goal_quat_delta):
        pivot_x = (
            self.previous_goal_x
            if self.previous_goal_x is not None
            else self.pose.position.x
        )
        pivot_y = (
            self.previous_goal_y
            if self.previous_goal_y is not None
            else self.pose.position.y
        )
        pivot_z = (
            self.previous_goal_z
            if self.previous_goal_z is not None
            else self.pose.position.z
        )
        pivot_quat = (
            self.previous_goal_quat
            if self.previous_goal_quat is not None
            else self.body_quat
        )

        goal_position = [
            pivot_x + goal_position_delta[0],
            pivot_y + goal_position_delta[1],
            pivot_z + goal_position_delta[2],
        ]
        goal_quat = pivot_quat * goal_quat_delta
        return goal_position, goal_quat

    def check_status(self, goal_position, goal_quaternion, do_x, do_y, do_z, do_quat):

        tolerance_position = rclpy.get_param("pid_positional_tolerance")
        tolerance_quat_w = rclpy.get_param("pid_quaternion_w_tolerance")

        if goal_position[0] is not None:
            pos_x_error = self.calculatePosError(self.pose.position.x, goal_position[0])
            if abs(pos_x_error) > tolerance_position:
                return False
        if goal_position[1] is not None:
            pos_y_error = self.calculatePosError(self.pose.position.y, goal_position[1])
            if abs(pos_y_error) > tolerance_position:
                return False
        if goal_position[2] is not None:
            pos_z_error = self.calculatePosError(self.pose.position.z, goal_position[2])
            if abs(pos_z_error) > tolerance_position:
                return False
        if goal_quaternion is not None:
            quat_error = self.calculateQuatError(self.body_quat, goal_quaternion)
            if abs(quat_error.w) < tolerance_quat_w:
                return False

        return True

    def calculatePosError(self, pos1, pos2):
        return abs(pos1 - pos2)

    def calculateQuatError(self, q1, q2):
        return q1.inverse() * q2
