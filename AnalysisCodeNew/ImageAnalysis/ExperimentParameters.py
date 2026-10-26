# -*- coding: utf-8 -*-
"""
Created on Fri Feb  9 12:29:25 2024

@author: Sommer Lab
"""
import numpy as np
import datetime

class AndorZyla: # Andor Zyla 5.5  
    def __init__(self):
        self.quantum_eff = .62 #Andor Zyla 
        self.sensitivity = .45
        self.pixelsize_microns =  6.5
        self.pixelsize_meters = self.pixelsize_microns*1e-6
        
class FLIRchameleon: #FLIR Chameleon3 CM3-U3-13S2M  
    def __init__(self):
        self.quantum_eff = .50 
        self.sensitivity = .45 # numbers need to be updated
        self.pixelsize_microns  = 3.75
        self.pixelsize_meters = self.pixelsize_microns*1e-6

class PCOPixelfly: # pco.pixelfly 1.4 USB
    def __init__(self, binning=1):
        if int(binning) != binning or binning < 1:
            raise ValueError('Pixelfly binning must be a positive integer.')

        self.binning = int(binning)
        self.quantum_eff = .62
        self.native_pixelsize_microns = 6.45
        self.pixelsize_microns = self.native_pixelsize_microns * self.binning
        self.pixelsize_meters = self.pixelsize_microns * 1e-6

class ImagingSystem:
    def __init__(self, magnification, objective_distance, aperture_radius):
        self.magnification= magnification
        cos_theta = objective_distance/np.sqrt(aperture_radius**2+objective_distance**2)
        self.solid_angle = 2*np.pi*(1-cos_theta)

def getImagingSystemByDate(date_mdy, axis, debug=0):
    """
    Parameters
    ----------
    date_mdy : string
        Date on which experiment was performed
    axis : string
        "top" or "side"
    Returns
    -------
    An ImagingSystem object
    """
    data_date = datetime.datetime.strptime(date_mdy,"%m/%d/%Y")    
    date1 = "2/8/2024" # Change the lenses for the side imaging, the magnification changed from 0.553 to 1.69
    date2 = '11/12/2024' # change lens for top imaging, magnification 0.6 -> 1.8
    
    if axis.lower() == "side":
        if data_date > datetime.datetime.strptime(date1,"%m/%d/%Y"):#changed side imaging lenses
            if debug:
                print("\tNew side imaging")
            #NOTE: magnification is precisely calibrated. But numerical aperture variables are approximate!
            return ImagingSystem(magnification = 1.69, objective_distance=200, aperture_radius=24.0/2)
        else: #Old standard side imaging
            if debug:
                print("\tOld side imaging")
            return ImagingSystem(magnification = 0.553, objective_distance=300, aperture_radius=48.3/2)
        
    elif axis.lower() == "top":
        if True:
            if data_date > datetime.datetime.strptime(date2,"%m/%d/%Y"):
                if debug:
                    print('\tNew top imaging')
                magnification = 1.8
                
            else:
                if debug:
                    print('\tOld top imaging')
                magnification = 0.6
            
            aperture_radius =  1.5 #in mm, the radius of the iris placed at the lens directly after the chamber where the MOT starts to get blocked
            objective_distance = 125.00 # in mm
            return ImagingSystem(magnification, objective_distance, aperture_radius)
        
        
def CrossSection(axis='side'):
    
    detuning = 2*np.pi*0 #how far from max absorption @231MHz. if the imaging beam is 230mhz then delta is -1MHz. unit is Hz
    linewidth = 36.898e6 #units Hz
    wavevector = 2*np.pi/(671e-9) #units 1/m
    cross_section = (6*np.pi / (wavevector**2)) * (1+(2*detuning/linewidth)**2)**-1

    if axis == 'top':
        return cross_section
    
    elif axis == 'side':    
        cross_section = 1/2 * cross_section
        return cross_section
    
    else: 
        raise ValueError('The cross section is not set!')
        
class ExperimentParams:
    def __init__(self, date="2/8/2024", config=None, t_exp=10e-6, picturesPerIteration=None, axis="side", cam_type = "zyla", binning=1):
        """        
        Parameters
        ----------
        config : dictionary
            Contents of Andor Solis configuration file (discontinued using this)
        picturesPerIteration : int
            How many pictures does Cicero take in each iteration? (typically 2 or 3) The default is 1.
        """
        self.t_exp = t_exp
        if cam_type.lower() == "zyla":
            #input parameters from config file
            self.picturesPerIteration = picturesPerIteration
            self.config =  config
            if config:            
                #self.number_of_pics = int(config['Acquisition']['NumberinKineticSeries'])
                #print("number_of_pics = "+str(self.number_of_pics))
                #assert self.number_of_pics % picturesPerIteration == 0, "Number of pictures should be a multiple of picturesPerIteration" # checks for error
                #self.number_of_iterations = int(self.number_of_pics / picturesPerIteration)
                
                self.height1 = int(config['FullImage']['VerticalEnd']) - int(config['FullImage']['VerticalStart']) + 1
                self.width1 = int(config['FullImage']['HorizontalEnd']) - int(config['FullImage']['HorizontalStart']) + 1 
                self.bin_horizontal = int(config['FullImage']['HorizontalBin'])
                self.bin_vertical = int(config['FullImage']['VerticalBin'])
                
                # image height, width and range after binning
                self.height = int(self.height1/self.bin_vertical)
                self.width = int(self.width1/self.bin_horizontal)
                self.xmin=int(0)  #origin placed at zero by python
                self.ymin=int(0)  #origin placed at zero by python
                self.xmax=self.width-1
                self.ymax=self.height-1 
                self.number_of_pixels = self.height*self.width
                print(self.height)
                print(self.width)
                print(self.number_of_pixels)
                if not t_exp:
                    self.t_exp = float(config['Acquisition']['ExposureTime'])   
            self.camera=AndorZyla()
            self.data_type = np.int16
        elif cam_type.lower() == "chameleon":
            self.camera = FLIRchameleon()
            self.data_type = np.int16
        elif cam_type.lower() in ("pixelfly", "pco", "pco.pixelfly 1.4 usb"):
            self.picturesPerIteration = picturesPerIteration
            self.camera = PCOPixelfly(binning=binning)
            self.data_type = np.uint16
        else:
            raise ValueError('Unknown camera type: {}'.format(cam_type))
        self.ready_to_save = 'true'
        
        P_MOT_beam = 14e-3 #power per MOT beam, roughly 1/4 of what goes into octopus
        self.andor_pixel_size = 1/(22.2e3) #obtained from measurement of magnification using ambient light
        r_beam = .01 #meters
        I1 = 2*P_MOT_beam/(np.pi*r_beam**2)
        I = 6*I1
        Isat = 25 #W/m^2
        self.s = I/Isat
        self.k = (671e-9)
        self.gamma = 36.898e6
        self.delta = 26e6*2*np.pi
        self.R_scat = self.gamma*.5*self.s/(1+self.s+(2*self.delta/self.gamma)**2)
        self.kB = 1.380649e-23 #Boltzmann's constant
        self.m = 9.9883414e-27 #Li-6 mass in kg
        self.cross_section = CrossSection(axis)
        
        imgSys = getImagingSystemByDate(date, axis)
        self.magnification = imgSys.magnification
        self.solid_angle = imgSys.solid_angle
        self.imagingSystem = imgSys
        
        # if axis == "side":
        #     aperture_radius =  48.3/2 #in mm, the radius of the iris placed at the lens directly after the chamber where the MOT starts to get blocked
        #     f=300 #mm
        #     cos_theta = f/np.sqrt(aperture_radius**2+f**2)
        #     self.solid_angle = 2*np.pi*(1-cos_theta)
        #     self.magnification = 0.553 #
        # elif axis == "top":
        #     self.magnification = 0.6 #subject to change...
        #     aperture_radius =  1.5 #in mm, the radius of the iris placed at the lens directly after the chamber where the MOT starts to get blocked
        #     f = 125.00 # in mm
        #     cos_theta = f/np.sqrt(aperture_radius**2+f**2)
        #     self.solid_angle = 2*np.pi*(1-cos_theta)
