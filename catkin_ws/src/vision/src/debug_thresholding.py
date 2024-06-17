#!/usr/bin/env python3

import cv2
import rospy
import lane_marker_measure
from cv_bridge import CvBridge
from sensor_msgs.msg import Image


# callback when an image is received
def threshold_image(raw_img):
    global are_publishers_registered
    global downscale_pub
    global blur1_pub
    global tol_pub
    global blur2_pub
    global thresh_pub
    # convert image to cv2
    if not rospy.get_param("debug_lane_marker_thresholding"):
        if are_publishers_registered:
            downscale_pub.unregister()
            blur1_pub.unregister()
            tol_pub.unregister()
            blur2_pub.unregister()
            thresh_pub.unregister()
            del downscale_pub
            del blur1_pub
            del tol_pub
            del blur2_pub
            del thresh_pub
    else:
        if not are_publishers_registered:
            downscale_pub = rospy.Publisher(
                "vision/debug/lane_marker_downscale", Image, queue_size=1
            )
            blur1_pub = rospy.Publisher(
                "vision/debug/lane_marker_blur1", Image, queue_size=1
            )
            tol_pub = rospy.Publisher(
                "vision/debug/lane_marker_tolerance", Image, queue_size=1
            )
            blur2_pub = rospy.Publisher(
                "vision/debug/lane_marker_blur2", Image, queue_size=1
            )
            thresh_pub = rospy.Publisher(
                "vision/debug/lane_marker_threshold", Image, queue_size=1
            )
            are_publishers_registered = True
        img = bridge.imgmsg_to_cv2(raw_img, "bgr8")
        lane_marker_measure.thresholdRed(
            img, downscale_pub, blur1_pub, tol_pub, blur2_pub, thresh_pub
        )


if __name__ == "__main__":
    # bridge is used to convert sensor_msg images to cv2
    bridge = CvBridge()
    rospy.init_node("debug_thresholding")
    are_publishers_registered = False
    downscale_pub = None
    blur1_pub = None
    tol_pub = None
    blur2_pub = None
    thresh_pub = None
    sub = rospy.Subscriber("vision/down_cam/cropped", Image, threshold_image)

    rospy.spin()
