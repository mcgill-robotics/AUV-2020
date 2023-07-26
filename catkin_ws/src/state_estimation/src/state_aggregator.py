#!/usr/bin/env python3

import rospy
import numpy as np
import quaternion
from tf import transformations

from geometry_msgs.msg import Point, Pose, Quaternion, Vector3
from sbg_driver.msg import SbgEkfQuat
from std_msgs.msg import Empty, Float64
from auv_msgs.msg import DeadReckonReport
from sbg_driver.msg import SbgImuData

DEG_PER_RAD = 180/np.pi
RAD_PER_DEG = np.pi/180

'''
Note on variable naming conventions used in this file:

Broadly speaking, a name indicates what frame is being measured
as well as relative to what frame the measurement is done. 

<type>_<target_frame>_<reference_frame>

Rotations:
    Ex: q_auv_global should be read as:
        "a quaternion representing the AUV frame relative to the
        global frame" 
            or 
        "a quaternion that takes the basis vectors of the global frame
        into the basis vectors of the AUV frame"

    the same rotation can be expressed in euler angles
    or as a quaternion:

    q_auv_global = np.quaternion(0.707, 0.707, 0, 0) # w, x, y, z
    euler_auv_global = np.array([180, 0, 0]) # roll/pitch/yaw in degrees

Positions:
    Ex: pos_dvl_dvlref should be read as:
        "the position of dvl frame according to the dvlref frame"
            or
        "a vector emanating from the origin of dvlref frame, pointing
        to the origin of dvl frame, as seen in the dvlref frame"

    If a vector is described as: pos_<frame1>_<frame2>_<frame3>
    the (origins of) first two frames represent the endpoint and 
    start-point of the vector, <frame3> represents the frame from which 
    this vector is viewed

    Ex: pos_dvl_dvlref_global should be read as:
        "a vector emanating from the origin of dvlref frame, pointing
        to the origin of dvl frame, as seen in the global frame"

    *Notice, a variable described as pos_dvl_dvlref is implicitly 
    viewed in dvlref frame. 

Mounting positions/rotations are described similarly, to 
highlight that these entities are static based on the mounting 
of sensors on the auv the postfix '_mount' is used after
<target_frame>

    Ex: pos_dvl_mount_auv should be read as:
    "The position vector from AUV frame to dvl frame
    (viewed from AUV frame)"
    here, 'mount' is not a reference frame

We also keep track of q_auv_global/pos_auv_global
according to several sensors, so the position
according to the depth sensor data, and imu data are stored in:
    pos_auv_global__fromds
    pos_auv_global__fromimu

This is done to disambiguate from pos_auv_global_dvl
which could be taken to mean "vector from
global to auv, as seen in dvl frame"

'''


class State_Aggregator:
    def __init__(self):
        # global frame relative to NED (North-East-Down)
        self.q_global_ned = np.quaternion(0, 1, 0, 0) # inertial frame, will not change 

        # world frame relative to global
        self.pos_world_global = np.array([0.0, 0.0, 0.0])
        self.q_world_global = np.quaternion(1, 0, 0, 0)

        # angular velocity of AUV (AUV frame)
        self.w_auv = np.array([0.0, 0.0, 0.0])

        '''DVL'''
        # mount - dvl frame relative to AUV frame
        self.pos_dvl_mount_auv = np.array([0.0, 0.0, 0.0]) 
        # self.q_dvl_mount_auv = np.quaternion(1, 0, 0, 0) 
        self.q_dvl_mount_auv = np.quaternion(0, 0.3826834, 0.9238795, 0) # RPY [deg]: (180, 0, -135)

        # measurements in global frame
        self.pos_auv_global__fromdvl = None # np.array([0.0, 0.0, 0.0]) 
        self.q_auv_global__fromdvl = None # np.quaternion(1, 0, 0, 0) # w, x, y, z 

        # DVL measurements are with reference to its initial frame, keep track of orientation of dvl reference wrt global 
        self.pos_dvlref_global = None 
        self.q_dvlref_global = None 

        '''Depth Sensor'''
        # mount - position of depth sensor relative to AUV frame - Note: depth sensor gets data in terms of global frame directly
        self.pos_ds_mount_auv = np.array([0.0, 0.0, 0.0])

        # auv estimates in global frame
        self.pos_auv_global__fromds = None # np.array([0.0, 0.0, 0.0])

        '''IMU'''
        # mount - imu frame relative to AUV frame
        self.q_imu_mount_auv = np.quaternion(1, 0, 0, 0) # imu is rotated 180 degrees about z axis relative to AUV frame

        # auv estimates in global frame
        self.q_auv_global__fromimu = None # np.quaternion(1, 0, 0, 0) 

        # publishers
        self.pub_auv = rospy.Publisher('pose', Pose, queue_size=1)
        self.pub_world = rospy.Publisher('pose_world', Pose, queue_size=1)

        self.pub_x = rospy.Publisher('state_x', Float64, queue_size=1)
        self.pub_y = rospy.Publisher('state_y', Float64, queue_size=1)
        self.pub_z = rospy.Publisher('state_z', Float64, queue_size=1)
        self.pub_theta_x = rospy.Publisher('state_theta_x', Float64, queue_size=1)
        self.pub_theta_y = rospy.Publisher('state_theta_y', Float64, queue_size=1)
        self.pub_theta_z = rospy.Publisher('state_theta_z', Float64, queue_size=1)
        self.pub_w_auv = rospy.Publisher('angular_velocity', Vector3, queue_size=1)
        # TODO - publishers for each sensor for debugging

        # subscribers
        rospy.Subscriber("/dead_reckon_report",DeadReckonReport, self.dvl_cb)
        rospy.Subscriber("/sbg/imu_data", SbgImuData, self.imu_ang_vel_cb)
        rospy.Subscriber("/sbg/ekf_quat", SbgEkfQuat, self.imu_cb)
        rospy.Subscriber("/depth", Float64, self.depth_sensor_cb)

        rospy.Subscriber("/reset_state_full", Empty, self.reset_state_full_cb)
        rospy.Subscriber("/reset_state_planar", Empty, self.reset_state_planar_cb)


        '''
        The methods pos_auv_global, pos_auv_world, q_auv_global, q_auv_world, (and euler_auv_world)
        calculate these entities based on the current available sensor data. 

        Tracking these values as attributes may introduce bugs: ie. pos_world_global 
        is updated but not pos_auv_world leading to logic errors.

        This is avoided by recalculating pos_auv_world etc. any time it is needed
        '''

    def pos_auv_global(self):
        if self.pos_auv_global__fromdvl is None:
            return None
        
        pos_auv_global = np.zeros(3)
        pos_auv_global[0:2] = self.pos_auv_global__fromdvl[0:2]
        pos_auv_global[2] = self.pos_auv_global__fromdvl[2] # TODO - use depth sensor when working
        return pos_auv_global 


    def q_auv_global(self):
        return self.q_auv_global__fromimu 


    def pos_auv_world(self):
        if self.pos_auv_global() is None or self.q_auv_global() is None:
            return None

        # AUV position/offset from pos_world (vector as seen in global frame)
        pos_auv_world_global = self.pos_auv_global() - self.pos_world_global

        # position in world frame
        pos_auv_world = quaternion.rotate_vectors(self.q_world_global.inverse(), pos_auv_world_global)
        return pos_auv_world


    def q_auv_world(self):
        if self.q_auv_global() is None:
            return None

        q_auv_world = self.q_world_global.inverse()*self.q_auv_global()
        return q_auv_world 
        

    def euler_auv_world(self):
        '''
        The use of euler angles is for backward compatibility
        to publish data to state_theta_* topics
        '''
        if self.q_auv_world() is None:
            return None

        # calculate euler angles based on self.q_auv_world
        # *note* the tf.transformations module is used instead of
        # quaternion package because it gives the euler angles
        # as roll/pitch/yaw (XYZ) whereas the latter chooses
        # a different euler angle convention (ZYZ)
        # tf.transformations uses quaternion defined as [x, y, z, w]
        # whereas quaternion is ordered [w, x, y, z]
        q = self.q_auv_world()
        q = np.array([q.x, q.y, q.z, q.w])
        
        # rotations are applied to ‘s'tatic or ‘r’otating frame
        # we're just getting the first angle - this assumes
        # that the other angles are fixed 
        # TODO - these angles don't combine, only to be treated individually
        # theta = transformations.euler_from_quaternion(q, 'rxyz')
        # theta_x = theta[0]
        # theta_y = theta[1]
        # theta_z = theta[2]
        theta_x = transformations.euler_from_quaternion(q, 'rxyz')[0]
        theta_y = transformations.euler_from_quaternion(q, 'ryxz')[0]
        theta_z = transformations.euler_from_quaternion(q, 'rzyx')[0]

        # euler_from_quaternion returns 3-tuple of radians
        # convert to numpy array of degrees
        euler_auv_world = np.array([theta_x, theta_y, theta_z])*DEG_PER_RAD
        return euler_auv_world


    '''
    Callbacks for each type of sensor data
    '''

    def dvl_cb(self,data):
        # TODO - we need this to get the first knowledge of dvlref
        if self.q_auv_global() is None:
            return 

        # quaternion of DVL relative to the frame DVL was in when it last reset (dvlref)
        q_dvl_dvlref = transformations.quaternion_from_euler(data.roll*RAD_PER_DEG, data.pitch*RAD_PER_DEG, data.yaw*RAD_PER_DEG)
        q_dvl_dvlref = np.quaternion(q_dvl_dvlref[3], q_dvl_dvlref[0], q_dvl_dvlref[1], q_dvl_dvlref[2]) # transformations returns quaternion as nparray [w, x, y, z]

        # position of DVL relative to initial DVL frame (dvlref)
        pos_dvl_dvlref = np.array([data.x, data.y, data.z]) 

        # first dvl message - figure out the location of the dvlref frame
        if self.q_dvlref_global is None:
            print("reset dvlref_global")
            self.q_dvlref_global = self.q_auv_global()*self.q_dvl_mount_auv

            # find pos_dvlref_global accounting for dvl mounting position - uses current auv_global position
            # (without previous dvl readings for xy this might be <0, 0, -0.75>)
            # x,y are arbitrary choice since there is no way to locate dvl relative to global prior to having xy
            pos_dvl_auv_global = quaternion.rotate_vectors(self.q_auv_global(), self.pos_dvl_mount_auv)
            pos_dvl_dvlref_global = quaternion.rotate_vectors(self.q_dvlref_global, pos_dvl_dvlref)
            self.pos_dvlref_global = self.pos_auv_global() + pos_dvl_auv_global - pos_dvl_dvlref_global

        # quaternion of AUV in global frame
        q_dvl_global = self.q_dvlref_global*q_dvl_dvlref
        self.q_auv_global__fromdvl = q_dvl_global*self.q_dvl_mount_auv.inverse()

        # position of AUV in global frame
        pos_dvl_global = quaternion.rotate_vectors(self.q_dvlref_global, pos_dvl_dvlref)
        pos_dvl_auv_global = quaternion.rotate_vectors(self.q_auv_global(), self.pos_dvl_mount_auv)
        self.pos_auv_global__fromdvl = pos_dvl_global - pos_dvl_auv_global 

        # TODO - uncomment to check frame consistency
        q_dvlref_auv = self.q_dvl_mount_auv*q_dvl_dvlref.inverse()
        print("euler_dvl_dvlref", data.roll, data.pitch, data.yaw)
        print("q_dvl_dvlref", 2*np.arccos(q_dvl_dvlref.w)*DEG_PER_RAD)
        print("q_dvlref_global", 2*np.arccos(self.q_dvlref_global.w)*DEG_PER_RAD)
        print("q_dvl_global", 2*np.arccos(q_dvl_global.w)*DEG_PER_RAD)
        print("q_auv_global", 2*np.arccos(self.q_auv_global().w)*DEG_PER_RAD)
        print("----------------------")


    def imu_ang_vel_cb(self, data):
        # angular velocity vector relative to imu frame 
        w_imu = np.array([data.gyro.x, data.gyro.y, data.gyro.z])

        # anuglar velocity vector relative to AUV frame 
        self.w_auv = quaternion.rotate_vectors(self.q_imu_mount_auv, w_imu)


    def imu_cb(self, imu_msg):
        # quaternion of imu in NED frame
        q_imu_ned = imu_msg.quaternion
        q_imu_ned = np.quaternion(q_imu_ned.w, q_imu_ned.x, q_imu_ned.y, q_imu_ned.z) 

        # quaternion of AUV in global frame
        # sensor is mounted, may be oriented differently from AUV axes
        q_imu_global = self.q_global_ned.inverse()*q_imu_ned
        self.q_auv_global__fromimu = q_imu_global*self.q_imu_mount_auv.inverse()


    def depth_sensor_cb(self, depth_msg):
        # position (z) of depth sensor in global frame
        pos_ds_global = np.array([0.0, 0.0, depth_msg.data]) # depth data being negative -> underwater 

        # vector from auv to depth sensor expressed in global frame
        pos_ds_auv_global = quaternion.rotate_vectors(self.q_auv_global(), self.pos_ds_mount_auv)

        # TODO - accordance between pos from dvl and pos from depth sensor (assume global z=0 at surface?)
        # position (z) of AUV in global frame 
        # Note: x, y may not be zero (due to positional diff. between sensor and AUV center of mass)
        # this is of little consequence as the x,y values from depth sensor are not used
        self.pos_auv_global__fromds = pos_ds_global - pos_ds_auv_global 


    '''
    Methods to alter the world frame relative to the global frame. 

    The world frame for-all-intents-and-purposes can be treated as the global (inertial) 
    frame. However, it may be useful to change the world frame at the beginning of the 
    run to align the axes with the geometry of the pool, this makes it more clear which 
    direction are the x/y axes

    It may be a bit dangerous changing the world frame during the run 
    as this might fuck with what the PIDs are doing - care is required
    '''

    def reset_state_full_cb(self, _):
        '''
        Snaps the world frame to the AUV frame (position + orientation)
        '''
        # new world position is current AUV position in global frame
        self.pos_world_global = self.pos_auv_global()

        # new world quaternion is q_auv in global frame
        self.q_world_global = self.q_auv_global()


    def reset_state_planar_cb(self, _):
        ''' 
        Snaps world frame to AUV x/y position (z constant)
        and similar orientation - except keeping the same (global) x-y plane 

        - this method is a bit hackish 
        and should only be used when the orientation of the AUV 
        is aproximately only yaw relative to global frame, 
        it may give unwanted results at other extreme orientations
        '''
        # new world position is x, y - current AUV position, z - same as previous world frame, in global frame
        self.pos_world_global[0:2] = self.pos_auv_global()[0:2] # do not change z

        # new world quaternion is yaw rotation of AUV in global frame
        q = self.q_auv_global()
        q_auv_global = np.array([q.x, q.y, q.z, q.w])
        theta_z = transformations.euler_from_quaternion(q_auv_global, 'szyx')[0]
        q_world_global = transformations.quaternion_from_euler(0, 0, theta_z)
        self.q_world_global = np.quaternion(q_world_global[3], q_world_global[0], q_world_global[1], q_world_global[2])


    def update_state(self, _):
        pos_auv_world = self.pos_auv_world()
        q_auv_world = self.q_auv_world()
        euler_auv_world = self.euler_auv_world()

        # TODO - more precise when missing data
        if pos_auv_world is None or q_auv_world is None:
            return

        # publish AUV pose (relative to world)
        position = Point(x=pos_auv_world[0], y=pos_auv_world[1], z=pos_auv_world[2]) 
        orientation = Quaternion(x=q_auv_world.x, y=q_auv_world.y, z=q_auv_world.z, w=q_auv_world.w)
        pose = Pose(position, orientation)
        self.pub_auv.publish(pose)

        # publish individual degrees of freedom
        self.pub_x.publish(pos_auv_world[0])
        self.pub_y.publish(pos_auv_world[1])
        self.pub_z.publish(pos_auv_world[2])

        # publish world pose (relative to global)
        position = Point(x=self.pos_world_global[0], y=self.pos_world_global[1], z=self.pos_world_global[2]) 
        orientation = Quaternion(x=self.q_world_global.x, y=self.q_world_global.y, z=self.q_world_global.z, w=self.q_world_global.w)
        pose = Pose(position, orientation)
        self.pub_world.publish(pose)

        # backwards compatibility
        self.pub_theta_x.publish(euler_auv_world[0])
        self.pub_theta_y.publish(euler_auv_world[1])
        self.pub_theta_z.publish(euler_auv_world[2])

        w_auv = Vector3(self.w_auv[0], self.w_auv[1], self.w_auv[2])
        self.pub_w_auv.publish(w_auv)


if __name__ == '__main__':
    rospy.init_node('state_aggregator')
    sa = State_Aggregator()
    timer = rospy.Timer(rospy.Duration(0.1), sa.update_state)
    rospy.on_shutdown(timer.shutdown)
    rospy.spin()
