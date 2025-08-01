"""
[pipeline]
TODO: describe module functionality.
"""

import numpy as np 
import cv2 

def enhance_heightmap (img_8bit :np .ndarray ,config :dict )->np .ndarray :
    img =np .uint16 (img_8bit )*257 
    cfg =config .get ('enhancement',{})

    power =cfg .get ('z_curve_power',1.0 )
    if power !=1.0 :
        img =z_curve (img ,power )

    if cfg .get ('flatten_background',False ):
        cutoff =cfg .get ('background_cutoff',0.2 )
        img =flatten_background (img ,cutoff )

    sigma =cfg .get ('blur_sigma',0.0 )
    if sigma >0.0 :
        img =gaussian_blur (img ,sigma )

    if cfg .get ('edge_boost',False ):
        weight =cfg .get ('edge_boost_weight',0.3 )
        img =edge_boost (img ,weight )

    if cfg .get ('auto_normalize',False ):
        img =normalize_16bit (img )

    return img 

def normalize_16bit (img :np .ndarray )->np .ndarray :
    min_val =img .min ()
    max_val =img .max ()
    if max_val ==min_val :
        return img 
    norm =(img -min_val )/(max_val -min_val )
    return np .uint16 (norm *65535 )

def z_curve (img :np .ndarray ,power :float =0.7 )->np .ndarray :
    norm =img /65535.0 
    remapped =np .clip (norm **power ,0 ,1 )
    return np .uint16 (remapped *65535 )

def flatten_background (img :np .ndarray ,cutoff :float =0.2 )->np .ndarray :
    norm =img /65535.0 
    flat =np .clip ((norm -cutoff )/(1 -cutoff ),0 ,1 )
    return np .uint16 (flat *65535 )

def gaussian_blur (img :np .ndarray ,sigma :float =1.0 )->np .ndarray :
    ksize =max (3 ,int (6 *sigma )|1 )
    return cv2 .GaussianBlur (img ,(ksize ,ksize ),sigmaX =sigma )

def edge_boost (img :np .ndarray ,weight :float =0.3 )->np .ndarray :
    img_f32 =img .astype (np .float32 )
    laplacian =cv2 .Laplacian (img_f32 ,cv2 .CV_32F ,ksize =3 )
    boosted =img_f32 +(laplacian *weight )
    return np .clip (boosted ,0 ,65535 ).astype (np .uint16 )

def apply_z_scale (img :np .ndarray ,z_scale_mm :float =-2.5 )->np .ndarray :
    return (img /65535.0 )*z_scale_mm 