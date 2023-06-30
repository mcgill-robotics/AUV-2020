#!/usr/bin/env python3

import rospy
from std_msgs.msg import Float64

class StateTracker:
    def __init__(self):
        self.x_pos_sub = rospy.Subscriber('state_x', Float64, self.updateX)
        self.y_pos_sub = rospy.Subscriber('state_y', Float64, self.updateY)
        self.z_pos_sub = rospy.Subscriber('state_z', Float64, self.updateZ)
        self.theta_x_sub = rospy.Subscriber('state_theta_x', Float64, self.updateThetaX)
        self.theta_y_sub = rospy.Subscriber('state_theta_y', Float64, self.updateThetaY)
        self.theta_z_sub = rospy.Subscriber('state_theta_z', Float64, self.updateThetaZ)
        self.theta_z_sub = rospy.Subscriber('pose', Float64, self.updatePose)
        self.x = None
        self.y = None
        self.z = None
        self.theta_x = None
        self.theta_y = None
        self.theta_z = None
        self.pose = None
    def updatePose(self,msg):
        self.pose = msg
    def updateX(self, msg):
        self.x = float(msg.data)
    def updateY(self, msg):
        self.y = float(msg.data)
    def updateZ(self, msg):
        self.z = float(msg.data)
    def updateThetaX(self, msg):
        self.theta_x = float(msg.data)
    def updateThetaY(self, msg):
        self.theta_y = float(msg.data)
    def updateThetaZ(self, msg):
        self.theta_z = float(msg.data)
    def stop(self):
        self.x_pos_sub.unregister()
        self.y_pos_sub.unregister()
        self.z_pos_sub.unregister()
        self.theta_x_sub.unregister()
        self.theta_y_sub.unregister()
        self.theta_z_sub.unregister()
