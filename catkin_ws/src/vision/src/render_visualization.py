#!/usr/bin/env python3

import rospy
from visualization_msgs.msg import Marker
from geometry_msgs.msg import Point, Quaternion
import tf
from std_msgs.msg import Float64
from auv_msgs.msg import VisionObjectArray
from auv_msgs.msg import DeadReckonReport
from geometry_msgs.msg import Wrench, Quaternion
import numpy as np
import math
from scipy.spatial.transform import Rotation

def setup():
    global auv_marker
    # Create a marker message
    auv_marker = Marker()
    auv_marker.header.frame_id = "world"  # Set the frame ID according to your setup
    auv_marker.ns = "visualization"
    auv_marker.id = marker_id
    auv_marker.type = Marker.SPHERE
    auv_marker.action = Marker.ADD
    # Set the mesh file path
    # marker.mesh_resource = "package://vision/src/visualization/auv.stl"
    # Set the position, orientation, and scale
    auv_marker.pose.position = Point(0, 0, 0)
    auv_marker.pose.orientation = Quaternion(0, 0, 0, 1)
    auv_marker.scale.x = 0.9
    auv_marker.scale.y = 0.3
    auv_marker.scale.z = 0.3
    # Set the color (optional)
    auv_marker.color.r = 1.0
    auv_marker.color.g = 1.0
    auv_marker.color.b = 1.0
    auv_marker.color.a = 0.8
    # Publish the marker
    auv_pub.publish(auv_marker)
    addHeading(0,0,0,1,0,0,auv_pub.publish,(1,0,0))# 1 - AUV x direction
    addHeading(0,0,0,0,1,0,auv_pub.publish,(0,1,0))# 2 - AUV y direction
    addHeading(0,0,0,0,0,1,auv_pub.publish,(0,0,1))# 3 - AUV z direction
    addHeading(0,0,0,1,0,0,auv_pub.publish,(1,1,1))# 4 - World x direction
    addHeading(0,0,0,0,1,0,auv_pub.publish,(0,0,0))# 5 - World y direction
    addHeading(0,0,0,0,0,1,auv_pub.publish,(0.5,0.5,0.5))# 6 - World z direction
    addHeading(0,0,0,1,0,0,auv_pub.publish,(1,0,1))# 7 - DVL x direction
    addHeading(0,0,0,0,1,0,auv_pub.publish,(1,1,0))# 8 - DVL y direction
    addHeading(0,0,0,0,0,1,auv_pub.publish,(0,1,1))# 9 - DVL z direction
    addLabel(0,0,1,"Surge:0\nSway:0\nHeave:0\nRoll:0\nPitch:0\nYaw:0",auv_pub.publish,0.15) # 10 - effort
    addHeading(-1000,0,0,1,0,0,auv_pub.publish,(1,1,1)) # 11 - setpoint x axis
    addHeading(-1000,0,0,0,1,0,auv_pub.publish,(1,1,1)) # 12 - setpoint y axis
    addHeading(-1000,0,0,0,0,1,auv_pub.publish,(1,1,1)) # 13 - setpoint z axis

    for gt in groundTruths:
        addMapMarkers(gt[0],gt[1],gt[2],gt[3],gt[4],gt[5],(1,1,1))

def objectDetectCb(msg):
    #spawn blue spheres object detections
    for obj in msg.array:
        #NOTE: if performance becomes an issue, publish a marker array with all markers at once
        add_detection_marker(obj.x, obj.y, obj.z)

def objectMapCb(msg):
    global updates
    updates += 1
    if updates >= update_map_every:
        updates = 0
    else:
        return
    global object_map_markers
    #spawn red spheres and text (for label, object-specific info) on objects in map
    for map_marker in object_map_markers:
        map_marker.action = Marker.DELETE
        map_pub.publish(map_marker)
        rospy.sleep(0.01)
    object_map_markers = []
    for obj in msg.array:
        addMapMarkers(obj.label, obj.x, obj.y, obj.z, obj.theta_z, obj.extra_field)
    
def addSphere(x,y,z,scale,pub,color):
    global marker_id
    # Create a marker message
    detection_marker = Marker()
    detection_marker.header.frame_id = "world"  # Set the frame ID according to your setup
    detection_marker.ns = "visualization"
    marker_id += 1
    detection_marker.id = marker_id
    detection_marker.type = Marker.SPHERE
    detection_marker.action = Marker.ADD
    # Set the position, orientation, and scale
    detection_marker.pose.position = Point(x,y,z)
    detection_marker.pose.orientation = Quaternion(0, 0, 0, 1)
    detection_marker.scale.x = scale
    detection_marker.scale.y = scale
    detection_marker.scale.z = scale
    # Set the color (optional)
    detection_marker.color.r = color[0]
    detection_marker.color.g = color[1]
    detection_marker.color.b = color[2]
    detection_marker.color.a = 0.9
    # Publish the marker
    pub(detection_marker)

def addCustomObject(marker_type,pos,rot,scale,pub,color):
    global marker_id
    # Create a marker message
    custom_marker = Marker()
    custom_marker.header.frame_id = "world"  # Set the frame ID according to your setup
    custom_marker.ns = "visualization"
    marker_id += 1
    custom_marker.id = marker_id
    custom_marker.type = marker_type
    custom_marker.action = Marker.ADD
    # Set the position, orientation, and scale
    custom_marker.pose.position = Point(pos[0],pos[1],pos[2])
    custom_marker.pose.orientation = Quaternion(*tf.transformations.quaternion_from_euler(rot[0],rot[1],rot[2]))
    custom_marker.scale.x = scale[0]
    custom_marker.scale.y = scale[1]
    custom_marker.scale.z = scale[2]
    # Set the color (optional)
    custom_marker.color.r = color[0]
    custom_marker.color.g = color[1]
    custom_marker.color.b = color[2]
    custom_marker.color.a = color[3]
    # Publish the marker
    pub(custom_marker)

def addHeading(x,y,z,vec_x,vec_y,vec_z,pub,color,override_id=None):
    global marker_id
    # Create a marker message for first heading
    heading_marker = Marker()
    heading_marker.header.frame_id = "world"  # Set the frame ID according to your setup
    heading_marker.ns = "visualization"
    if override_id is None:
        marker_id += 1
        heading_marker.id = marker_id
    else:
        heading_marker.id = override_id
    heading_marker.type = Marker.ARROW
    heading_marker.action = Marker.ADD
    x_offset, y_offset, z_offset = [vec_x,vec_y,vec_z] / np.linalg.norm([vec_x,vec_y,vec_z])
    heading_marker.points = [Point(x,y,z), Point(x+0.55*x_offset,y+0.55*y_offset,z+0.55*z_offset)]
    heading_marker.pose.orientation = Quaternion(0, 0, 0, 1)
    heading_marker.scale.x = 0.035
    heading_marker.scale.y = 0.06
    heading_marker.scale.z = 0.035
    # Set the color (optional)
    heading_marker.color.r = color[0]
    heading_marker.color.g = color[1]
    heading_marker.color.b = color[2]
    heading_marker.color.a = 1.0
    # Publish the marker
    pub(heading_marker)

def addMapMarkers(label,x,y,z,in_theta_z,in_extra_field,color=(1,0,0)):
    global marker_id
    if in_extra_field == -1234.5: extra_field = -1
    else: extra_field = in_extra_field
    if in_theta_z == -1234.5: theta_z = 0
    else: theta_z = in_theta_z
    addSphere(x, y, z, 0.1, publishToMap, color)
    if label == "Lane Marker": #LANE MARKER
        heading1 = eulerAngleToUnitVector(0,90,theta_z)
        heading2 = eulerAngleToUnitVector(0,90,extra_field)
        addHeading(x,y,z,heading1[0],heading1[1],heading1[2],publishToMap,color)
        addHeading(x,y,z,heading2[0],heading2[1],heading2[2],publishToMap,color)
        addLabel(x,y,z,"Lane Marker",publishToMap)
    elif label == "Gate": #GATE TASK
        addCustomObject(Marker.CUBE,[x,y,z],(0,0,theta_z*math.pi/180),[0.1,3,1.5],publishToMap,[color[0],color[1],color[2],0.4])
        addLabel(x,y,z,"Gate (left: " + str("None" if extra_field < 0 else ("earth" if extra_field > 0.5 else "abydos")) + ")",publishToMap)
    elif label == "Buoy": #BUOY TASK
        addCustomObject(Marker.CUBE,[x,y,z],(0,0,theta_z*math.pi/180),[0.1,1.2,1.2],publishToMap,[color[0],color[1],color[2],0.4])
        addLabel(x,y,z,"Buoy",publishToMap)
    elif label == "Octagon Table": # OCTAGON TABLE
        addCustomObject(Marker.CUBE,[x,y,z],(0,0,theta_z*math.pi/180),[1.2,1.2,1.2],publishToMap,[color[0],color[1],color[2],0.4])
        addLabel(x,y,z,"Octagon Table" ,publishToMap)
    elif label == "Earth Symbol": #EARTH SYMBOL
        addCustomObject(Marker.CUBE,[x,y,z],(0,0,theta_z*math.pi/180),[0.01,0.2,0.2],publishToMap,[color[0],color[1],color[2],0.4])
        addLabel(x,y,z,"Earth",publishToMap)
    elif label == "Abydos Symbol": #ABYDOS SYMBOL
        addCustomObject(Marker.CUBE,[x,y,z],(0,0,theta_z*math.pi/180),[0.01,0.2,0.2],publishToMap,[color[0],color[1],color[2],0.4])
        addLabel(x,y,z,"Abydos",publishToMap)

def addLabel(x,y,z,text,pub,scale=0.25,override_id=None):
    global marker_id
    # Create a Marker message
    text_marker = Marker()
    text_marker.header.frame_id = "world"
    text_marker.ns = "visualization"
    text_marker.type = Marker.TEXT_VIEW_FACING
    text_marker.action = Marker.ADD
    if override_id is None:
        marker_id += 1
        text_marker.id = marker_id
    else:
        text_marker.id = override_id

    if scale == 0.25:
        text_marker.color.r = 1.0
        text_marker.color.g = 1.0
        text_marker.color.b = 1.0
        text_marker.color.a = 1.0
    else:
        text_marker.color.r = 0.0
        text_marker.color.g = 0.0
        text_marker.color.b = 0.0
        text_marker.color.a = 1.0

    # Set the position of the text marker
    text_marker.pose.position = Point(x,y,z+0.5)

    # Set the orientation of the text marker (identity quaternion)
    text_marker.pose.orientation.w = 1.0

    # Set the scale of the text marker (size in x, y, z)
    text_marker.scale.x = scale  # Modify with the desired scale of the text
    text_marker.scale.y = scale
    text_marker.scale.z = scale

    # Set the text value
    text_marker.text = text

    # Publish the Marker message
    pub(text_marker)

def transformToWorldVector(vector, euler_angles):
    # Convert Euler angles to a rotation matrix
    rotation = Rotation.from_euler('xyz', euler_angles, degrees=False)
    rotation_matrix = rotation.as_matrix()
    # Transform the direction vector to global coordinates
    transformed_direction = np.matmul(rotation_matrix, vector)
    return transformed_direction.tolist()

def eulerAngleToUnitVector(x,y,z):
    # Convert Euler angles to radians
    roll_rad = math.radians(x)
    pitch_rad = math.radians(y)
    yaw_rad = math.radians(z)

    # Calculate the direction cosine matrix (DCM)
    cos_roll = math.cos(roll_rad)
    sin_roll = math.sin(roll_rad)
    cos_pitch = math.cos(pitch_rad)
    sin_pitch = math.sin(pitch_rad)
    cos_yaw = math.cos(yaw_rad)
    sin_yaw = math.sin(yaw_rad)

    # Define the DCM elements
    vec = [sin_roll * sin_yaw + cos_roll * cos_yaw * sin_pitch,
        cos_roll * sin_pitch * sin_yaw - cos_yaw * sin_roll,
        cos_pitch * cos_roll]
    
    return vec

def publish_breadcrumb(marker):
    global breadcrumb_markers
    breadcrumb_markers.append(marker)
    auv_pub.publish(marker)

def add_breadcrumb(x,y,z):
    global breadcrumb_markers
    if len(breadcrumb_markers) >= max_breadcrumbs:
        breadcrumb_marker = breadcrumb_markers.pop(0)
        breadcrumb_marker.pose.position = Point(x,y,z)
        publish_breadcrumb(breadcrumb_marker)
    else:
        addSphere(x,y,z,0.02,publish_breadcrumb,(1,0,0))

def publish_detection_marker(marker):
    global detection_markers
    detection_markers.append(marker)
    detection_pub.publish(marker)

def add_detection_marker(x,y,z):
    global detection_markers
    if len(detection_markers) >= max_detection_markers:
        detection_marker = detection_markers.pop(0)
        detection_marker.pose.position = Point(x,y,z)
        publish_detection_marker(detection_marker)
    else:
        addSphere(x,y,z,0.075,publish_detection_marker,(0,1,0))

def updateAUVThetaX(msg):
    global auv_marker
    roll, pitch, yaw = tf.transformations.euler_from_quaternion([auv_marker.pose.orientation.x, auv_marker.pose.orientation.y, auv_marker.pose.orientation.z, auv_marker.pose.orientation.w])
    new_quaternion = Quaternion(*tf.transformations.quaternion_from_euler(float(msg.data)*math.pi/180, pitch, yaw))
    auv_marker.pose.orientation = new_quaternion
    auv_pub.publish(auv_marker)
    updateReferenceFrames()
def updateAUVThetaY(msg):
    global auv_marker
    roll, pitch, yaw = tf.transformations.euler_from_quaternion([auv_marker.pose.orientation.x, auv_marker.pose.orientation.y, auv_marker.pose.orientation.z, auv_marker.pose.orientation.w])
    new_quaternion = Quaternion(*tf.transformations.quaternion_from_euler(roll, float(msg.data)*math.pi/180, yaw))
    auv_marker.pose.orientation = new_quaternion
    auv_pub.publish(auv_marker)
    updateReferenceFrames()
def updateAUVThetaZ(msg):
    global auv_marker
    roll, pitch, yaw = tf.transformations.euler_from_quaternion([auv_marker.pose.orientation.x, auv_marker.pose.orientation.y, auv_marker.pose.orientation.z, auv_marker.pose.orientation.w])
    new_quaternion = Quaternion(*tf.transformations.quaternion_from_euler(roll, pitch, float(msg.data)*math.pi/180))
    auv_marker.pose.orientation = new_quaternion
    auv_pub.publish(auv_marker)
    updateReferenceFrames()
def updateAUVX(msg):
    global auv_marker
    auv_marker.pose.position = Point(float(msg.data), auv_marker.pose.position.y, auv_marker.pose.position.z)  # Set the desired position
    add_breadcrumb(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z)
    auv_pub.publish(auv_marker)
    updateReferenceFrames()
    addLabel(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z+1, "Surge:{}\nSway:{}\nHeave:{}\nRoll:{}\nPitch:{}\nYaw:{}".format(currentEffort["surge"], currentEffort["sway"], currentEffort["heave"], currentEffort["roll"], currentEffort["pitch"], currentEffort["yaw"]),auv_pub.publish,0.15,override_id=10)
def updateAUVY(msg):
    global auv_marker
    auv_marker.pose.position = Point(auv_marker.pose.position.x, float(msg.data), auv_marker.pose.position.z)  # Set the desired position 
    add_breadcrumb(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z)
    auv_pub.publish(auv_marker)
    updateReferenceFrames()
    addLabel(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z+1,"Surge:{}\nSway:{}\nHeave:{}\nRoll:{}\nPitch:{}\nYaw:{}".format(currentEffort["surge"], currentEffort["sway"], currentEffort["heave"], currentEffort["roll"], currentEffort["pitch"], currentEffort["yaw"]),auv_pub.publish,0.15,override_id=10)
def updateAUVZ(msg):
    global auv_marker
    auv_marker.pose.position = Point(auv_marker.pose.position.x, auv_marker.pose.position.y, float(msg.data))  # Set the desired position
    add_breadcrumb(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z)
    auv_pub.publish(auv_marker)
    updateReferenceFrames()
    addLabel(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z+1,"Surge:{}\nSway:{}\nHeave:{}\nRoll:{}\nPitch:{}\nYaw:{}".format(currentEffort["surge"], currentEffort["sway"], currentEffort["heave"], currentEffort["roll"], currentEffort["pitch"], currentEffort["yaw"]),auv_pub.publish,0.15,override_id=10)

def updateReferenceFrames():
    global auv_marker
    auv_euler_angles = tf.transformations.euler_from_quaternion([auv_marker.pose.orientation.x, auv_marker.pose.orientation.y, auv_marker.pose.orientation.z, auv_marker.pose.orientation.w])
    dir_x = transformToWorldVector([1,0,0],auv_euler_angles)
    dir_y = transformToWorldVector([0,1,0],auv_euler_angles)
    dir_z = transformToWorldVector([0,0,1],auv_euler_angles)
    dvl_dir_x = transformToWorldVector([1,0,0],dvl_euler_angles)
    dvl_dir_y = transformToWorldVector([0,1,0],dvl_euler_angles)
    dvl_dir_z = transformToWorldVector([0,0,1],dvl_euler_angles)
    addHeading(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z,dir_x[0],dir_x[1],dir_x[2],auv_pub.publish,(1,0,0),override_id=1)
    addHeading(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z,dir_y[0],dir_y[1],dir_y[2],auv_pub.publish,(0,1,0),override_id=2)
    addHeading(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z,dir_z[0],dir_z[1],dir_z[2],auv_pub.publish,(0,0,1),override_id=3)
    addHeading(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z,1,0,0,auv_pub.publish,(1,1,1),override_id=4)
    addHeading(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z,0,1,0,auv_pub.publish,(0,0,0),override_id=5)
    addHeading(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z,0,0,1,auv_pub.publish,(0.5,0.5,0.5),override_id=6)
    addHeading(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z,dvl_dir_x[0],dvl_dir_x[1],dvl_dir_x[2],auv_pub.publish,(1,0,1),override_id=7)
    addHeading(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z,dvl_dir_y[0],dvl_dir_y[1],dvl_dir_y[2],auv_pub.publish,(1,1,0),override_id=8)
    addHeading(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z,dvl_dir_z[0],dvl_dir_z[1],dvl_dir_z[2],auv_pub.publish,(0,1,1),override_id=9)

def dvlDataCb(msg):
    global dvl_euler_angles
    dvl_euler_angles = [float(msg.roll)*math.pi/180, float(msg.pitch)*math.pi/180, float(msg.yaw)*math.pi/180]
    updateReferenceFrames()

def effortCb(msg):
    global currentEffort
    currentEffort["surge"] = msg.force.x
    currentEffort["sway"] = msg.force.y
    currentEffort["heave"] = msg.force.z
    currentEffort["roll"] = msg.torque.x
    currentEffort["pitch"] = msg.torque.y
    currentEffort["yaw"] = msg.torque.z
    addLabel(auv_marker.pose.position.x,auv_marker.pose.position.y,auv_marker.pose.position.z+1,"Surge:{}\nSway:{}\nHeave:{}\nRoll:{}\nPitch:{}\nYaw:{}".format(currentEffort["surge"], currentEffort["sway"], currentEffort["heave"], currentEffort["roll"], currentEffort["pitch"], currentEffort["yaw"]),auv_pub.publish,0.15,override_id=10)

def setpointXCb(msg):
    global current_setpoint
    current_setpoint[0] = msg.data
    updateSetpointMarker()

def setpointYCb(msg):
    global current_setpoint
    current_setpoint[1] = msg.data
    updateSetpointMarker()

def setpointZCb(msg):
    global current_setpoint
    current_setpoint[2] = msg.data
    updateSetpointMarker()

def setpointQuatCb(msg):
    global current_setpoint
    current_setpoint[3] = [msg.x, msg.y, msg.z, msg.w]
    updateSetpointMarker()

def updateSetpointMarker():
    setpoint_euler_angles = tf.transformations.euler_from_quaternion([current_setpoint[3][0], current_setpoint[3][1], current_setpoint[3][2], current_setpoint[3][3]])
    dir_x = transformToWorldVector([1,0,0],setpoint_euler_angles)
    dir_y = transformToWorldVector([0,1,0],setpoint_euler_angles)
    dir_z = transformToWorldVector([0,0,1],setpoint_euler_angles)
    addHeading(current_setpoint[0],current_setpoint[1],current_setpoint[2],dir_x[0],dir_x[1],dir_x[2],auv_pub.publish,(1,0.8,0),override_id=11)
    addHeading(current_setpoint[0],current_setpoint[1],current_setpoint[2],dir_y[0],dir_y[1],dir_y[2],auv_pub.publish,(1,0.8,0),override_id=12)
    addHeading(current_setpoint[0],current_setpoint[1],current_setpoint[2],dir_z[0],dir_z[1],dir_z[2],auv_pub.publish,(1,0.8,0),override_id=13)


rospy.init_node('render_visualization')

auv_pub = rospy.Publisher('visualization/auv', Marker, queue_size=999)
detection_pub = rospy.Publisher('visualization/detection', Marker, queue_size=999)
map_pub = rospy.Publisher('visualization/map', Marker, queue_size=999)

print("Waiting 10 seconds so RViz can launch...")
# rospy.sleep(10)
print("Starting visualization!")

dvl_euler_angles = [0,0,0]
breadcrumb_markers = []
max_breadcrumbs = 500
detection_markers = []
max_detection_markers = 50
object_map_markers = []
current_setpoint = [0,0,0,[0,0,0,1]]
marker_id = 0

update_map_every = 5
updates = 0

groundTruths = [
    #add objects here, format is [label,x,y,z,theta_z,extra_field]
]

currentEffort = {"surge":0, "sway":0, "heave":0, "roll":0, "pitch":0, "yaw":0}

def publishToMap(marker):
    global object_map_markers
    object_map_markers.append(marker)
    map_pub.publish(marker)

setup()

x_pos_sub = rospy.Subscriber('/state/x', Float64, updateAUVX)
y_pos_sub = rospy.Subscriber('/state/y', Float64, updateAUVY)
z_pos_sub = rospy.Subscriber('/state/z', Float64, updateAUVZ)
theta_x_sub = rospy.Subscriber('/state/theta/x', Float64, updateAUVThetaX)
theta_y_sub = rospy.Subscriber('/state/theta/y', Float64, updateAUVThetaY)
theta_z_sub = rospy.Subscriber('/state/theta/z', Float64, updateAUVThetaZ)
obj_sub = rospy.Subscriber('vision/viewframe_detection', VisionObjectArray, objectDetectCb)
map_sub = rospy.Subscriber('vision/object_map', VisionObjectArray, objectMapCb)
sub_effort = rospy.Subscriber('/controls/effort', Wrench, effortCb)
dvl_sub = rospy.Subscriber('/sensors/dvl/pose', DeadReckonReport, dvlDataCb)

x_setpoint_sub = rospy.Subscriber('x_setpoint', Float64, setpointXCb)
y_setpoint_sub = rospy.Subscriber('y_setpoint', Float64, setpointYCb)
z_setpoint_sub = rospy.Subscriber('z_setpoint', Float64, setpointZCb)
quat_setpoint_sub = rospy.Subscriber('/controls/quaternion_pid/setpoint', Quaternion, setpointQuatCb)


rospy.spin()
