#!/usr/bin/env python

##    @package visual_feedback_utils
# Provides functionality for contour finding and thresholding in both realtime (green) and stored (white) images

import roslib
import sys
roslib.load_manifest("visual_feedback_utils")
import rospy
from numpy import *
import pyflann
import math
import cv
import Geometry2D
import Vector2D
import Models
import tf
from geometry_msgs.msg import PointStamped
from image_processor_node import ImageProcessor
from shape_fitting_utils import *
import image_geometry

(WHITE_BG,GREEN_BG) = range(2)
MODE = WHITE_BG

def threshold(image,bg_mode,filter_pr2,crop_rect,cam_info=None,listener=None):
    image_hsv = cv.CloneImage(image)
    cv.CvtColor(image,image_hsv,cv.CV_RGB2HSV)
    image_hue = cv.CreateImage(cv.GetSize(image_hsv),8,1)
    image_gray = cv.CreateImage(cv.GetSize(image_hsv),8,1)
    cv.CvtColor(image,image_gray,cv.CV_RGB2GRAY)
    cv.Split(image_hsv,image_hue,None,None,None)
    image_thresh = cv.CloneImage(image_gray)
    if bg_mode==GREEN_BG:
        upper_thresh = cv.CloneImage(image_hue)
        lower_thresh = cv.CloneImage(image_hue)
        black_thresh = cv.CloneImage(image_hue)
        cv.Threshold( image_hue, upper_thresh, 80, 255, cv.CV_THRESH_BINARY) #was 75
        cv.Threshold( image_hue, lower_thresh, 30, 255, cv.CV_THRESH_BINARY_INV)
        cv.Threshold( image_gray, black_thresh, 1, 255, cv.CV_THRESH_BINARY)
        #Filter out the green band of the hue
        cv.Or(upper_thresh,lower_thresh,image_thresh)
        #Filter out pure black, for boundaries in birdseye
        cv.And(image_thresh, black_thresh, image_thresh)
        
    elif bg_mode==WHITE_BG:
        cv.Threshold(image_gray, image_thresh, 250,255, cv.CV_THRESH_BINARY_INV)
        
    if crop_rect:
        (x,y,width,height) = crop_rect
        for j in range(image_thresh.height):
            for i in range(x):
                image_thresh[j,i] = 0
            for i in range(x + width,image_thresh.width):
                image_thresh[j,i] = 0
        for i in range(image_thresh.width):
            for j in range(y):
                image_thresh[j,i] = 0
            for j in range(y+height,image_thresh.height):
                image_thresh[j,i] = 0
    
    
    if filter_pr2:
        #Filter out grippers
        cam_frame = cam_info.header.frame_id
        now = rospy.Time.now()
        for link in ("l_gripper_l_finger_tip_link","r_gripper_l_finger_tip_link"):
            listener.waitForTransform(cam_frame,link,now,rospy.Duration(10.0))
            l_grip_origin = PointStamped()
            l_grip_origin.header.frame_id = link
            l_grip_in_camera = listener.transformPoint(cam_frame,l_grip_origin)
            camera_model = image_geometry.PinholeCameraModel()
            camera_model.fromCameraInfo(cam_info)
            (u,v) = camera_model.project3dToPixel((l_grip_in_camera.point.x,l_grip_in_camera.point.y,l_grip_in_camera.point.z))
            if link[0] == "l":
                x_range = range(0,u)
            else:
                x_range = range(u,image_thresh.width)
            if 0 < u < image_thresh.width and 0 < v < image_thresh.height:
                for x in x_range:
                    for y in range(0,image_thresh.height):
                        image_thresh[y,x] = 0.0
                        
    return image_thresh
    
def get_contour_from_thresh(image_thresh):
    storage = cv.CreateMemStorage(0)
    contour = cv.FindContours (image_thresh, storage, cv.CV_RETR_LIST, cv.CV_CHAIN_APPROX_NONE, (0,0))
    max_length = 0
    max_contour = None
    while contour != None:
        length = abs(cv.ContourArea(contour)   )
        if length > max_length:
            max_length = length
            max_contour = contour
            print "Replaced with %f"%length
        contour = contour.h_next()
    if max_contour == None:
        print "Couldn't find any contours"
        return None
    else:
        return max_contour
    
def get_contour(image,bg_mode=WHITE_BG,filter_pr2=False,crop_rect=None,cam_info=None,listener=None):
    image_thresh = threshold(image,bg_mode,filter_pr2,crop_rect,cam_info,listener)
    return get_contour_from_thresh(image_thresh)
    
 #x = 4 w = 629 y = 144, h = 329