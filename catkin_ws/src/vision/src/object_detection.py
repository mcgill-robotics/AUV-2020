#!/usr/bin/env python3

import rospy
import numpy as np
import torch
import ast
from cv_bridge import CvBridge
from ultralytics import YOLO

from object_detection_utils import *
from lane_marker_measure import measure_lane_marker

from auv_msgs.msg import VisionObject, VisionObjectArray
from sensor_msgs.msg import Image





def is_vision_ready(camera_id):
    # Only predict if cameras_image_count has not reached detect_every yet.
    global cameras_image_count
    cameras_image_count[camera_id] += 1
    if cameras_image_count[camera_id] <= detect_every:
        return False
    # Reset cameras_image_count.
    cameras_image_count[camera_id] = 0

    states[camera_id].pause()
    current_states = {
        "position": states[camera_id].position,
        "q": states[camera_id].q_auv,
        "theta_z": states[camera_id].theta_z,
    }
    for v in current_states.values():
        if v is None:
            print("State information missing. Skipping detection.")
            print(current_states)
            states[camera_id].resume()
            return False
    if camera_id == 1 and states[camera_id].point_cloud is None:
        print("Point cloud not yet published.")
        states[camera_id].resume()
        return False
    return True


def detection_frame(image, detections, camera_id):
    # Initialize empty array for object detection frame message.
    detection_frame_array = []
    image_h, image_w, _ = image.shape
    # Nested for loops get all predictions made by model.
    for detection in detections:
        boxes = detection.boxes.cpu().numpy() if is_cuda_available else detection.boxes.numpy()
        for box in boxes:
            conf = float(list(box.conf)[0])
            # Only consider prediction if confidence is at least min_prediction_confidence.
            if conf < min_prediction_confidence:
                if print_debug_info:
                    print(
                        "Confidence too low for camera {} ({}%)".format(
                            camera_id, conf * 100
                        )
                    )
                continue

            bbox = list(box.xywh[0])
            cls_id = int(list(box.cls)[0])
            global_class_name = class_names[camera_id][cls_id]
            # Add bbox visualization to image.
            debug_image = visualize_bbox(
                debug_image, bbox, global_class_name + " " + str(conf * 100) + "%"
            )

            # Initialize a new detection frame object.
            detectionFrame = VisionObject()
            pred_obj_x, pred_obj_y, pred_obj_x = 0, 0, 0
            extra_field, theta_z = None, None

            if camera_id == 0: # Down camera.
                if global_class_name == "Lane Marker":
                    headings, center, debug_image = measure_lane_marker(
                        image, bbox, debug_image
                    )
                    if None not in headings:
                        bbox = center
                        heading_auv = [0, 0]
                        for i in range(2):
                            offset = 270 if headings[i] + down_cam_yaw_offset < -90 else -90
                            heading_auv[i] = states[camera_id].theta_z + headings[i] + offset
                        theta_z = heading_auv[0] + down_cam_yaw_offset
                        extra_field = heading_auv[1] + down_cam_yaw_offset
                    pred_obj_x, pred_obj_y, pred_obj_z = get_object_position_down_camera(
                        bbox[0], bbox[1], image_h, image_w, lane_marker_top_z
                    )
                elif global_class_name == "Octagon Table":
                    pred_obj_x, pred_obj_y, pred_obj_z = get_object_position_down_camera(
                        bbox[0], bbox[1], image_h, image_w, octagon_table_top_z
                    )
                elif global_class_name == "Bins":
                    # @TO-DO: Add Bins implementation to vision. 
                    continue
            else: # Forward camera.
                if global_class_name == "Octagon Table":
                    pred_obj_x, pred_obj_y, pred_obj_z = get_object_position_front_camera(bbox)
                elif global_class_name == "Gate":
                    pred_obj_x, pred_obj_y, pred_obj_z = get_object_position_front_camera(bbox)
                    theta_z = measure_angle(bbox)
                elif global_class_name == "Buoy":
                    pred_obj_x, pred_obj_y, pred_obj_z = get_object_position_front_camera(bbox)
                    
            detectionFrame.label = global_class_name
            detectionFrame.confidence = conf
            detectionFrame.x = pred_obj_x
            detectionFrame.y = pred_obj_y
            detectionFrame.z = pred_obj_z
            detectionFrame.theta_z = theta_z
            detectionFrame.extra_field = extra_field

            # Add the detection frame to the array.
            detection_frame_array.append(detectionFrame)

    return detection_frame_array

def vision_cb(raw_image, camera_id):
    if not is_vision_ready(camera_id):
        return
    
    # Convert image to cv2.
    image = bridge.imgmsg_to_cv2(raw_image, "bgr8")
    debug_image = np.copy(image)
    states[camera_id].bgr_image = np.copy(image)

    # Run model on image.
    detections = model[camera_id].predict(
        image, device=device, verbose=print_debug_info
    )

    detection_frame_array = detection_frame(image, detections, camera_id)
    
# Callback is called when a new image is received.
# 1. Runs the model on new image.
# 2. Publishes detection frame. 
# 3. Generates/publishes visualization of predictions.
def detect_on_image(raw_image, camera_id):
    for obj in detection_frame_array:
        obj.x = obj.x if obj.x is not None else NULL_PLACEHOLDER
        obj.theta_z = obj.theta_z if obj.theta_z is not None else NULL_PLACEHOLDER
        obj.extra_field = (
            obj.extra_field if obj.extra_field is not None else NULL_PLACEHOLDER
        )

    detection_frame_array = clean_detections(detection_frame_array)

    if len(detection_frame_array) > 0:
        # Create object detection frame message and publish it.
        detection_frame_arrayMsg = VisionObjectArray()
        detection_frame_arrayMsg.array = detection_frame_array
        pub_viewframe_detection.publish(detection_frame_arrayMsg)

    # Convert visualization image to sensor_msg image and 
    # publish it to corresponding cameras visualization topic.
    debug_image = bridge.cv2_to_imgmsg(debug_image, "bgr8")
    pubs_visualisation[camera_id].publish(debug_image)
    states[camera_id].resume()


if __name__ == "__main__":
    rospy.init_node("object_detection")

    print_debug_info = rospy.get_param("log_model_prediction_info", False)
    NULL_PLACEHOLDER = rospy.get_param("NULL_PLACEHOLDER")

    min_prediction_confidence = rospy.get_param("min_prediction_confidence")
    
    pool_depth = rospy.get_param("pool_depth")
    octagon_table_height = rospy.get_param("octagon_table_height")
    lane_marker_height = rospy.get_param("lane_marker_height")
    lane_marker_top_z = pool_depth + lane_marker_height
    octagon_table_top_z = pool_depth + octagon_table_height
    down_cam_yaw_offset = rospy.get_param("down_cam_yaw_offset")

    # Run the model every _ frames received (to not eat up too much RAM).
    detect_every = rospy.get_param("object_detection_frame_interval")  

    down_cam_model_file = rospy.get_param("down_cam_model_file")
    front_cam_model_file = rospy.get_param("front_cam_model_file")

    model = [YOLO(down_cam_model_file), YOLO(front_cam_model_file)]

    is_cuda_available = torch.cuda.is_available() 
    if not is_cuda_available:
        rospy.logwarn("CUDA is not available! YOLO inference will run on CPU.")
        device = "cpu"
    else:
        device = 0
        for m in model:
            m.to(torch.device("cuda"))

    # One array per camera, name index should be class id.
    class_names = [  
        ast.literal_eval(rospy.get_param("down_cam_class_name_mappings")),
        ast.literal_eval(rospy.get_param("front_cam_class_name_mappings"))
    ]

    # Count for number of images received per camera.
    cameras_image_count = [0, 0]

    pubs_visualisation = [
        rospy.Publisher("/vision/down_cam/detection", Image, queue_size=1),
        rospy.Publisher("/vision/front_cam/detection", Image, queue_size=1),
    ]
    pub_viewframe_detection = rospy.Publisher("/vision/viewframe_detection", VisionObjectArray, queue_size=1)

    bridge = CvBridge()

    # The int argument is used to index debug publisher, model, class names, and cameras_image_count.
    rospy.Subscriber("/vision/down_cam/image_raw", Image, detect_on_image, 0),
    rospy.Subscriber("/vision/front_cam/color/image_raw", Image, detect_on_image, 1),
    
    rospy.spin()