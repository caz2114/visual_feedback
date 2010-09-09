#!/usr/bin/env python

##    @package snapshotter
#    This module provides basic functionality for taking a 'snapshot' of an image, and either pulling it for OpenCV
#   information, or saving it

import roslib
import sys
roslib.load_manifest("passive_shape")
import rospy
from numpy import *
import pyflann
import math
import cv
import os.path
import pickle
import Geometry2D
import Vector2D
import Models
import annotator

SHOW_CONTOURS = True
SHOW_UNSCALED_MODEL = False
SHOW_SCALED_MODEL = False
SHOW_POINTS = False
SHOW_ITER = False
SYMM_OPT = True
SHOW_SYMM_MODEL = False
SHOW_OPT = False
SAVE_ITERS = False
SAVE = True
SAVE_MODEL = True
FINE_TUNE = False
SHOW_FITTED = False


INV_CONTOUR = True
CONTOURS_ONLY = False
NEAREST_EDGE = 0.0

AMAZON_THRESH = 250
TABLE_THRESH = 105

ANNOTATE = True

class PassiveShapeMaker:
    def __init__(self,corrected_filepath,corrected_modelpath):
        self.slider_pos = AMAZON_THRESH
        self.load_model(corrected_modelpath)
        image_raw = cv.LoadImage(corrected_filepath,cv.CV_LOAD_IMAGE_COLOR)
        self.model.set_image(image_raw)
        self.image_gray = cv.LoadImage(corrected_filepath,cv.CV_LOAD_IMAGE_GRAYSCALE)
        self.image_raw = image_raw
        image_hsv = cv.CloneImage(image_raw)
        cv.CvtColor(image_raw,image_hsv,cv.CV_RGB2HSV)
        self.flann = pyflann.FLANN()
        self.dist_fxn = l2_norm
        hue = cv.CreateImage(cv.GetSize(image_hsv),8,1)
        sat = cv.CreateImage(cv.GetSize(image_hsv),8,1)
        val = cv.CreateImage(cv.GetSize(image_hsv),8,1)
        trash = cv.CreateImage(cv.GetSize(image_hsv),8,1)
        cv.Split(image_hsv,hue,None,None,None)
        self.image = hue
        cv.NamedWindow("Source",1)
        cv.NamedWindow("Result",1)
        cv.ShowImage("Source",image_raw)
        cv.CreateTrackbar( "Threshold", "Result", self.slider_pos, 255, self.process_image )
        if ANNOTATE:
            self.anno_path = corrected_filepath[0:len(corrected_filepath)-4]+"_classified.anno"
        if SAVE_MODEL:
            self.save_model_path = corrected_filepath[0:len(corrected_filepath)-4]+"_classified.pickle"
        self.process_image(self.slider_pos)
        if SAVE:
            savepath = corrected_filepath[0:len(corrected_filepath)-4]+"_classified.png"
            cv.SaveImage(savepath,self.image2)
            return
        
        cv.WaitKey(0)
    
        cv.DestroyWindow("Source")
        cv.DestroyWindow("Result")   
        
    def load_model(self,filepath):
        self.model = pickle.load(open(filepath))
        if self.model.illegal():
            print "MODEL IS ILLEGAL"
            return
        #self.model = modelClass.vertices_full()
        
    def save_model(self,model):
        model_dest = open(self.save_model_path,'w')
        pickle.dump(model,model_dest)
        model_dest.close()
        
    def get_model_contour(self):
        return self.model.vertices_full()
        
    def get_dense_model_contour(self):
        return self.model.vertices_dense(constant_length=False,density=20)
        
    def process_image(self,thresh):
        storage = cv.CreateMemStorage(0)
        
        self.image1 = cv.CloneImage( self.image )
        self.image3 = cv.CloneImage( self.image )
        self.image4 = cv.CloneImage( self.image_gray)
        self.image2 = cv.CloneImage( self.image_raw )
        cv.Threshold( self.image, self.image1, thresh, 255, cv.CV_THRESH_BINARY )
        cv.Threshold( self.image_gray, self.image3, thresh, 255, cv.CV_THRESH_BINARY_INV )
        cv.Threshold( self.image_gray, self.image4, thresh, 255, cv.CV_THRESH_BINARY )
        #self.image2 = cv.CloneImage( self.image1 )
        #cv.Canny(self.image,self.image1,thresh*0.1,thresh*1.5)
        contour_reg = cv.FindContours   ( self.image1, storage,
                                    cv.CV_RETR_LIST, cv.CV_CHAIN_APPROX_NONE, (0,0))
        contour_inv = cv.FindContours   ( self.image3, storage,
                                    cv.CV_RETR_LIST, cv.CV_CHAIN_APPROX_NONE, (0,0))
        contour_gray = cv.FindContours   ( self.image4, storage,
                                    cv.CV_RETR_LIST, cv.CV_CHAIN_APPROX_NONE, (0,0))
        #contour_hue = min([contour_reg,contour_inv],key=lambda c: len(c))
        #contour = min([contour_hue,contour_gray],key=lambda c: len(c))
        
        max_length = 0
        max_contour = None
        if INV_CONTOUR:
            contours = [contour_inv]
        else:
            contours = [contour_reg,contour_gray]
        for contour in contours:
            while contour != None:
                length = area(contour)   
                if length > max_length and not self.image_edge(contour):
                    max_length = length
                    max_contour = contour
                    print "Replaced with %f"%length
                contour = contour.h_next()
        if max_contour == None:
            print "Couldn't find any contours"
            return
        else:
            print area(max_contour)
        shape_contour = max_contour
        if SHOW_CONTOURS:
            cv.DrawContours(self.image2,shape_contour,cv.CV_RGB(255,0,0),cv.CV_RGB(255,0,0),0,1,8,(0,0))
        if CONTOURS_ONLY:
            cv.ShowImage("Result",self.image2)
            return
        #cv.ShowImage("Result",self.image2)
        #return
        (real_center,real_top,real_theta,real_scale) = self.get_principle_info(shape_contour)
        #self.model = translate_poly(rotate_poly(shape_contour,-0.2,real_center),(500,500)) ##FIXME
        if SHOW_UNSCALED_MODEL:
            self.model.draw_to_image(self.image2,cv.CV_RGB(0,0,255))
            cv.ShowImage("Result",self.image2)
            return
        (model_center,model_top,model_theta,model_scale) = self.get_principle_info(self.get_model_contour())
        displ = displacement(model_center,real_center)
        if SHOW_POINTS:
            self.highlight_pt(real_center,cv.CV_RGB(200,200,200))
            self.highlight_pt(real_top,cv.CV_RGB(200,200,200))
        if SHOW_POINTS:
            self.highlight_pt(model_center,cv.CV_RGB(0,0,0))
            self.highlight_pt(model_top,cv.CV_RGB(0,0,0))
        print model_theta
        print real_theta
        angle = model_theta - real_theta
        print angle
        #angle = 0 #FIXME
        scale = real_scale/float(model_scale)
        model_trans = translate_poly(self.get_model_contour(),displ)
        model_rot = rotate_poly(model_trans,-1*angle,real_center)
        #scale = 1 #FIXME
        model_scaled = scale_poly(model_rot,scale,real_center)
        
        (model_center,model_top,model_theta,model_scale) = self.get_principle_info(model_scaled)
        if SHOW_POINTS:
            self.highlight_pt(model_center,cv.CV_RGB(128,128,128))
            self.highlight_pt(model_top,cv.CV_RGB(128,128,128))
        
        #Do the same to the actual model
        self.model.translate(displ)
        self.model.rotate(-1*angle,real_center)
        self.model.scale(scale,real_center)
        
 
        if SHOW_SCALED_MODEL:
            self.model.draw_to_image(self.image2,cv.CV_RGB(0,0,255))
            print "With penalty of: %f"%self.model.structural_penalty()
            cv.ShowImage("Result",self.image2)
            cv.WaitKey()
  
        #Energy calculation
        print "Energy is: %f"%self.energy_fxn(self.model,shape_contour)
        print "Shape contour has %d points"%(len(shape_contour))
        sparse_shape_contour = self.make_sparse(shape_contour,1000)
            
        #Optimize
        
        if SYMM_OPT:
            new_model_symm = black_box_opt(model=self.model,contour=shape_contour,energy_fxn=self.energy_fxn,num_iters = 3,delta=25.0,epsilon = 0.01) 
        else:
            new_model_symm = self.model    
        if SHOW_SYMM_MODEL:
            new_model_symm.draw_to_image(img=self.image2,color=cv.CV_RGB(0,255,0))
        model=new_model_symm.make_asymm()
        new_model_asymm = black_box_opt(model=model,contour=shape_contour,energy_fxn=self.energy_fxn,num_iters=100,delta=model.preferred_delta(),exploration_factor=1.5,fine_tune=FINE_TUNE)
        final_model = new_model_asymm
        #new_model_free = black_box_opt(model=new_model_asymm.free(),contour=shape_contour,energy_fxn = self.energy_fxn,num_iters=50,delta=5.0,exploration_factor=1.5)  
        #final_model = new_model_free
        final_model.draw_to_image(img=self.image2,color=cv.CV_RGB(255,0,255))
        nearest_pts = []
        for vert in final_model.vertices_full():
            nearest_pt = min(shape_contour,key=lambda pt: distance(pt,vert))
            self.highlight_pt(nearest_pt,cv.CV_RGB(255,255,255))
            nearest_pts.append(nearest_pt)
        if SHOW_FITTED:
            fitted_model = Models.Point_Model_Contour_Only_Asymm(*nearest_pts)
            fitted_model.draw_to_image(img=self.image2,color=cv.CV_RGB(0,255,255))
        if ANNOTATE:
            annotator.write_anno(nearest_pts,self.anno_path)
        if SAVE_MODEL:
            if SHOW_FITTED:
                self.save_model(fitted_model)
            else:
                final_model.set_image(None)
                self.save_model(final_model)
        if SAVE:
            return
        cv.ShowImage("Result",self.image2)
        return
        
    def energy_fxn(self,model,contour):
        model_dist_param = 0.5
        contour_dist_param = 0.5
        sparse_contour = self.make_sparse(contour,1000)
        num_model_pts = 30*len(model.sides())
        extra_sparse_contour = self.make_sparse(contour,num_model_pts)
        model_contour = model.vertices_dense(constant_length=False,density=30)
        nn_model = self.nearest_neighbors_fast(model_contour,sparse_contour)
        model_dist_energy = sum([self.dist_fxn(dist) for dist in nn_model]) / float(len(nn_model))
        #Normalize
        model_dist_energy /= float(self.dist_fxn(max(self.image2.width,self.image2.height)))

        nn_contour = self.nearest_neighbors_fast(extra_sparse_contour,model_contour)
        contour_dist_energy = sum([self.dist_fxn(dist) for dist in nn_contour]) / float(len(nn_contour))
        #Normalize
        contour_dist_energy /= float(self.dist_fxn(max(self.image2.width,self.image2.height)))
        
        
        energy = model_dist_param * model_dist_energy + contour_dist_param * contour_dist_energy
        
        #if model.illegal():
        #    energy = 1.0
        penalty = model.structural_penalty()
        #print "Penalty is %f"%penalty
        
        energy += penalty
        
        return energy
        

        
    def nearest_neighbors_slow(self,model_contour,sparse_contour):
        nn = []
        for vert in model_contour:
            nearest_pt = min(sparse_contour,key=lambda pt: distance(pt,vert))
            nn.append(distance(vert,nearest_pt))
        return nn
        
    def nearest_neighbors_fast(self,model_contour,sparse_contour):
        model_arr = array(model_contour)
        contour_arr = array(sparse_contour)
        result,dists = self.flann.nn(sparse_contour,model_contour, num_neighbors=1,algorithm="kmeans",branching=32, iterations=7, checks=16);
        return [sqrt(dist) for dist in dists]
        
    def image_edge(self,contour):
        width = self.image.width
        height = self.image.height
        for (x,y) in contour:
            if x < NEAREST_EDGE:
                return True
            if x > width - NEAREST_EDGE:
                return True
            if y < NEAREST_EDGE:
                return True
            if y > height - NEAREST_EDGE:
                return True
        return False
        
    def highlight_pt(self,pt,color=None):
        if color == None:
            color = cv.CV_RGB(128,128,128)
        cv.Circle(self.image2,pt,5,color,3)
    
    
    def get_principle_info(self,shape):
        """
        storage2 = cv.CreateMemStorage(0)
        bounding = cv.MinAreaRect2(shape,storage2)
        #(x, y, width, height) = bounding
        #center_x = x + width/2
        #center_y = y + width/2
        #center_x = avg([x for (x,y) in shape_contour])
        #center_y = avg([y for (x,y) in shape_contour])
        center = (bounding[0])
        """
        moments = cv.Moments(shape,0)
        center = get_center(moments)
        self.moments = moments
        
        theta = get_angle(moments)
        (top_pt,scale) = self.get_top(shape,center,theta)
        #scale = distance(center,top_pt)
        print "Scale = %s"%scale
        return(center,top_pt,theta,scale)
        
    def get_top(self,shape,center,theta):
        pt = center
        EPSILON = 1.0
        angle = theta
        scale = 0
        print "ANGLE = %s"%angle
        #If initially outside, go twice
        if(cv.PointPolygonTest(shape,pt,0) <= 0):
            while(cv.PointPolygonTest(shape,pt,0) <= 0):
                (x,y) = pt
                new_x = x + EPSILON*sin(angle)
                new_y = y - EPSILON*cos(angle)
                pt = (new_x,new_y)
                scale += EPSILON
        while(cv.PointPolygonTest(shape,pt,0) > 0):
            (x,y) = pt
            new_x = x + EPSILON*sin(angle)
            new_y = y - EPSILON*cos(angle)
            pt = (new_x,new_y)
            scale += EPSILON
        return (pt,scale)
        
    def make_sparse(self,contour,num_pts = 1000):
        sparsity = int(math.ceil(len(contour) / float(num_pts)))
        sparse_contour = []
        for i,pt in enumerate(contour):
            if i%sparsity == 0:
                sparse_contour.append(pt)
        return sparse_contour

def black_box_opt(model,contour, energy_fxn,delta = 0.1, num_iters = 100, epsilon = 0.001,exploration_factor=1.5,fine_tune=False,num_fine_tunes=0):
    #epsilon = delta / 100.0
    epsilon = 0.001
    score = -1 * energy_fxn(model,contour)
    print "Initial score was %f"%score
    params = model.params()
    deltas = [delta for p in params]
    if(SHOW_OPT):
        cv.NamedWindow("Optimizing")
    for it in range(num_iters):
        print "Starting iteration number %d"%it
        for i in range(len(params)):
            #print "Updating param number: %d"%i
            new_params = list(params)
            new_params[i] += deltas[i]
            new_score = -1 * energy_fxn(model.from_params(new_params),contour)
            if new_score > score:
                params = new_params
                score = new_score
                deltas[i] *= exploration_factor
            else:
                deltas[i] *= -1
                new_params = list(params)
                new_params[i] += deltas[i]
                new_score = -1 * energy_fxn(model.from_params(new_params),contour)
                if new_score > score:
                    params = new_params
                    score = new_score
                    deltas[i] *= exploration_factor  
                else:
                    deltas[i] *= 0.5
        print "Current best score is %f"%score
        if(SHOW_OPT):
            img = cv.CloneImage(model.image)
            model.from_params(params).draw_to_image(img,cv.CV_RGB(255,0,0))
            if SAVE_ITERS:
                cv.SaveImage("iter_%d.png"%it,img)
            cv.ShowImage("Optimizing",img)
            cv.WaitKey(50)
        if max([abs(d) for d in deltas]) < epsilon:
            print "BREAKING"
            break
    if fine_tune:
        print "FINE_TUNING"
        return black_box_opt(model.from_params(params),contour,energy_fxn,delta,num_iters,epsilon*10,exploration_factor*2,fine_tune=False)
    return model.from_params(params)
        
def l2_norm(val):
    return val**2
    
def l1_norm(val):
    return abs(val)
    
def drop_off(fxn,limit):
    return lambda val: fxn(min(val,limit))   

def slack(fxn,limit):
    return lambda val: fxn(max(val,limit)-limit)

def avg(lst):
    return float(sum(lst))/len(lst)
    
def displacement(pt1,pt2):
    (x_1,y_1) = pt1
    (x_2,y_2) = pt2
    return (x_2-x_1,y_2-y_1)
    
def translate_pt(pt,trans):
    (x,y) = pt
    (x_displ,y_displ) = trans
    (x_t,y_t) = (x+x_displ,y+y_displ)
    return (x_t,y_t)

def translate_poly(poly,trans):
    return [translate_pt(pt,trans) for pt in poly]

def rotate_pt(pt,angle,origin=(0,0)):
    (x,y) = pt
    (x_o,y_o) = origin
    (x_n,y_n) = (x-x_o,y-y_o)
    off_rot_x = x_n*cos(angle) - y_n*sin(angle)
    off_rot_y = y_n*cos(angle) + x_n*sin(angle)
    rot_x = off_rot_x + x_o
    rot_y = off_rot_y + y_o
    return (rot_x,rot_y)

def rotate_poly(poly,angle,origin=(0,0)):
    return [rotate_pt(pt,angle,origin) for pt in poly]

def scale_pt(pt,amt,origin=(0,0)):
    (x,y) = pt
    (x_o,y_o) = origin
    (x_n,y_n) = (x-x_o,y-y_o)
    (x_ns,y_ns) = (amt*x_n,amt*y_n)
    (x_s,y_s) = (x_ns+x_o,y_ns+y_o)
    return (x_s,y_s)

def scale_poly(poly,amt,origin=(0,0)):
    return [scale_pt(pt,amt,origin) for pt in poly]

def distance(pt1,pt2):
    (x_1,y_1) = pt1
    (x_2,y_2) = pt2
    return sqrt((x_1 - x_2)**2 + (y_1 - y_2)**2)
    
def get_angle(moments):
    mu11 = cv.GetCentralMoment(moments,1,1)
    mu20 = cv.GetCentralMoment(moments,2,0)
    mu02 = cv.GetCentralMoment(moments,0,2)
    return 1/2.0 * arctan( (2 * mu11 / float(mu20 - mu02)))
    
def get_center(moments):
    m00 = cv.GetSpatialMoment(moments,0,0)
    m10 = cv.GetSpatialMoment(moments,1,0)
    m01 = cv.GetSpatialMoment(moments,0,1)
    x = float(m10) / m00
    y = float(m01) / m00
    return (x,y)
    
def area(contour):
    if contour == None:
        return 0.0
    ar = abs(cv.ContourArea(contour))
    return ar
    

    
    
    
    
    
def main(args):
    corrected_filepath = args[0]
    corrected_modelpath = args[1]
    #corrected_filepath = os.path.expanduser(filepath)
    print corrected_filepath
    psm = PassiveShapeMaker(corrected_filepath,corrected_modelpath)
    return
    
if __name__ == '__main__':
    args = sys.argv[1:]
    try:
        main(args)
    except rospy.ROSInterruptException: pass
