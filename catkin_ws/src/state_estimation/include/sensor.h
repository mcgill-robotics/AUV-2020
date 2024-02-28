#ifndef SENSOR
#define SENSOR

#include <tf2/LinearMath/Quaternion.h>
#include <tf2/LinearMath/Vector3.h>
#include <tf2_ros/transform_listener.h>
#include "ros/ros.h"
#include "tf2/LinearMath/Transform.h"

class Sensor {
    public:
        Sensor(std::string name);
        virtual ~Sensor();
        std::string sensor_name;
        bool is_active(void);
        double depth;
    protected:
        double prev_depth;
        ros::Time last_unique_state_time;
        ros::Time last_error_message_time;
        ros::Duration time_before_considered_inactive;
        void update_last_state(void);
        virtual void set_prev_state(void) = 0;
        virtual bool has_different_data(void) = 0;
        virtual bool has_valid_data(void) = 0;
        tf2_ros::Buffer* tfBuffer;
        tf2_ros::TransformListener* tfListener;
};

#endif