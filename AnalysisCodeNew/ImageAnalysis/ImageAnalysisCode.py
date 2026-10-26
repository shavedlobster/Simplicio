# -*- coding: utf-8 -*-
"""
Created on Mon Sep  5 17:40:14 2022

@author: Sommer Lab
"""
import matplotlib.pyplot as plt
import numpy as np 
#import matplotlib.patches as patches
#import lmfit
#from lmfit import Parameters
import configparser 
#import rawpy
#import imageio 
import glob
from scipy.optimize import curve_fit
from scipy.ndimage import rotate
from scipy.ndimage import gaussian_filter1d
from scipy import signal
from skimage.filters import threshold_otsu
from scipy.ndimage import gaussian_filter
from scipy.ndimage import center_of_mass
from scipy import constants
import re
import os
import PIL
import datetime
import pandas as pd
from mpl_toolkits.axes_grid1 import make_axes_locatable
import pickle
import warnings
from scipy.signal import find_peaks, savgol_filter

from ImageAnalysis.ExperimentParameters import ExperimentParams

MASS = 9.9883414e-27

def GetDataLocation(date, DataPath=r'D:\Dropbox (Lehigh University)\Sommer Lab Shared\Data'):
    warnings.warn("GetDataLocation will be replaced with GetDayFolder(date, root= )", DeprecationWarning, stacklevel=2)
    return os.path.join(DataPath, datetime.datetime.strptime(date, '%m/%d/%Y').strftime('%Y/%m-%Y/%d %b %Y'))

def GetDayFolder(date, root=r'D:\Dropbox (Lehigh University)\Sommer Lab Shared\Data'):
    return os.path.join(root, datetime.datetime.strptime(date, '%m/%d/%Y').strftime('%Y/%m-%Y/%d %b %Y'))


def GetExamRange(examNum, examFrom=None, repetition=1):
    if examNum is None or examNum == 'all':
        return None, None
    
    examNum = examNum * repetition

    if examFrom is None:
        examFrom = -examNum
    else:
        examFrom = examFrom * repetition
        
    examUntil = examFrom + examNum
    if examUntil == 0:
        examUntil = None
    return examFrom, examUntil


def PlotArangeAndSize(imgNo, col_row_ratio=1.1, sizes_ratio=(3, 2)):
    '''
    Calculate the row and column numbers in a plot figure given the total image number. 
    col_row_ratio defines the approximate colNo : rwoNo, and 
    sizes_ratio defines the (x, y) sizes for each picture. 
    
    Parameters
    ----------
    imgNo : TYPE
        DESCRIPTION.
    col_row_ratio : TYPE, optional
        DESCRIPTION. The default is 1.1.
    sizes_ratio : TYPE, optional
        DESCRIPTION. The default is (3, 2).

    Returns
    -------
    TYPE
        DESCRIPTION.

    '''
    
    rowNo = round(imgNo**0.5 / col_row_ratio)
    if rowNo == 0:
        rowNo = 1
    colNo = int(np.ceil(imgNo / rowNo))
    
    if rowNo > colNo:
        rowNo, colNo = colNo, rowNo
    
    return (rowNo, colNo), (colNo*sizes_ratio[0], rowNo*sizes_ratio[1])


def AddCommonLabels(fig, xlabel='', ylabel='', 
                    fontsize=10, xpad=5, ypad=15, 
                    method=1):
    if method == 1:
        fig.add_subplot(111, frame_on=False)
        plt.tick_params(labelcolor="none", bottom=False, left=False )
        plt.xlabel(xlabel, fontsize=fontsize, xpad=5)
        plt.ylabel(ylabel, fontsize=fontsize, ypad=15)
        plt.tight_layout()
        
    if method == 2:
        fig.text(0.5, 0.04, xlabel, ha='center')
        fig.text(0.04, 0.5, ylabel, va='center', rotation='vertical')
        fig.tight_layout(rect=[0.05, 0.05, 1, 1])


def LoadConfigFile(dataFolder=".", configFileName='config.cfg',encoding="utf-8"): 
    config_file = dataFolder + "//" + configFileName
    config = configparser.ConfigParser()
    config.read(config_file,encoding=encoding)
    return config
    
def LoadTOF(dataFolder='.', TOF_filename='TOF_list.txt', units_of_tof='ms'):    
    tof_list = np.loadtxt(dataFolder + "//" + TOF_filename)
    return tof_list, units_of_tof 
    

# def loadRAW(filename):
#     with rawpy.imread(filename) as raw:
#         bayer = raw.raw_image
#         print(type(bayer))    
#     return bayer

def loadRAW(params, filename):
    file = open(filename,"rb")
    content = file.read()
    data_array = np.frombuffer(content, dtype = params.data_type)
    rows = 964
    cols = 1288
    print("max value: {}".format(np.max(data_array)))
    data_array = np.reshape(data_array, (rows, cols))
    return data_array


def loadSeriesRAW(params, picturesPerIteration=1 ,  data_folder= "."):
    file_names = glob.glob(os.path.join(data_folder,'*.raw'))
    number_of_pics = len(file_names)
    number_of_iterations = int(number_of_pics/picturesPerIteration)
    rows = 964
    cols = 1288
    image_array = np.zeros((number_of_iterations, picturesPerIteration, rows, cols))
    for iteration in range(number_of_iterations):
        for picture in range(picturesPerIteration):
            x = iteration*picturesPerIteration + picture
            filename = file_names[x]  
            image_array[iteration, picture,:,:] = loadRAW(params, filename)           
    return image_array


#filename must include full path and extension
def loadPGM(filename, file_encoding = 'binary'):
    if file_encoding == 'text':
        with open(filename, 'r') as f:
            filetype = f.readline()
            if filetype.strip() != "P2":
                raise Exception("wrong format, should be P2")
                             
            res = f.readline().split()
            cols = int(res[0])
            rows = int(res[1])
            
            # pixel_number = rows*cols            
            # maxval = f.readline()
            
            datastrings = f.read().split()
            data =list( map(int, datastrings))
            rows2discard = 2
            data = data[(cols*rows2discard):] # discard the first two rows
            rows = rows-rows2discard
            data_array = np.array(data)
            data_array = np.reshape(data_array, (rows,cols))
            #print("max value in image array = {}".format(np.max(data_array)))
    if file_encoding == 'binary':
        image = PIL.Image.open(filename)#, formats=["PGM"]))
        data_array = np.asarray(image, dtype=np.uint16)
        rows, cols = np.shape(data_array)
        rows2discard = 2
        data_array = data_array[rows2discard: , :]
    return data_array 



def loadFilesPGM(file_names, picturesPerIteration=1, background_file="", binsize=1, 
                 file_encoding = 'binary', return_fileTime=0):
    
    number_of_pics = len(file_names)
    number_of_iterations = int(number_of_pics/picturesPerIteration)

# read the background image into a 1d numpy array whose size is pixel_nimber
# width and height of the background images should be the same as the series of images 

    first_image = loadPGM(file_names[0], file_encoding = file_encoding)  
    rows, cols = np.shape(first_image)
    if background_file:
        #bg_filename = data_folder + "\\" + background_file_name   
        bg_data_array = loadPGM(background_file, file_encoding = file_encoding)
        
# this part read the series of images, background corrects them, loads them into a 4D numpy array  
# outermost dimension's size is equal to the number of iterations, 
# 2nd outer dimensions size is number of pictures per iteration
# 3rd dimensions size is equal to the height of the images  
    image_array = np.zeros((number_of_iterations, picturesPerIteration, rows//binsize, cols//binsize))
    fileTime = []
    for iteration in range(number_of_iterations):
        for picture in range(picturesPerIteration):              
            x = iteration*picturesPerIteration + picture
            
            if picture == 0 and return_fileTime:
                fileTime.append( datetime.datetime.fromtimestamp( os.path.getctime(file_names[x]) ) )
                
            if x > 0:
                data_array_corrected = loadPGM(file_names[x], file_encoding = file_encoding)
            else:
                data_array_corrected = first_image
                
            if background_file:
                data_array_corrected -= bg_data_array
            
            if binsize > 1:
                data_array_corrected = rebin2(data_array_corrected, (binsize, binsize))
            
            image_array[iteration, picture,:,:] = data_array_corrected
    
    if return_fileTime:
        return image_array, fileTime
    else:
        return image_array

    
        
def rebin(arr, new_shape):
    shape = (new_shape[0], arr.shape[0] // new_shape[0],
             new_shape[1], arr.shape[1] // new_shape[1])
    return arr.reshape(shape).mean(-1).mean(1)

def rebin2(arr, bins):
    #this function throws away excess matrix elements
    new_shape = (arr.shape[0]//bins[0], arr.shape[1]//bins[1])
    return rebin(arr[:bins[0]*new_shape[0], :bins[1]*new_shape[1]], new_shape)



def loadSeriesPGM(picturesPerIteration=1 ,  data_folder= "." , background_file_name="", binsize=1, 
                  file_encoding = 'binary', examFrom=0, examUntil=None, return_fileTime=0):    
# to load a numbered series of FLIR .pgm images into a 4D numpy array
# filenames must be in this format: root+number.pgm. Number must start from 1 
# n_params is the number of embedded image information fields which are checked, values between 0 to 10, default 0 
# zero is black, maxval is white

    if examFrom:
        examFrom *= picturesPerIteration
    if examUntil:
        examUntil *= picturesPerIteration
        
    file_names = sorted(glob.glob(os.path.join(data_folder,'*.pgm')))[examFrom: examUntil]
    
    return loadFilesPGM(file_names, picturesPerIteration, background_file_name, 
                        binsize, file_encoding = file_encoding, 
                        return_fileTime = return_fileTime)






def FillFilePathsListFLIR(df, PPI=3):
    # the input df has two columns, 'FolderPath' and 'FirstImg'.
    
    df = df.set_index('FolderPath')
    folders = df.index.unique()
    
    fullFilePathsList = []
    
    for fo in folders:
        
        filenames = glob.glob1(fo, '*.pgm')
        filenames.sort()
        
        firstFilenames = df.loc[fo].FirstImg.values # All filenames in that folder 
        
        filenamesPicked = []
        for f in firstFilenames:
            Ind = filenames.index(f) # The index of the firstFilename among all filenames in the folder
            filenamesPicked.extend(filenames[Ind: Ind+PPI]) # Take the following filenames together.
        filepathsPicked = [ os.path.join(fo, ii) for ii in filenamesPicked ]
        
    fullFilePathsList.extend(filepathsPicked)        
            
    return fullFilePathsList


def loadSeriesPGMV2(imgPaths, file_encoding='binary'):
    
    imgs = []
    
    for p in imgPaths:
        imgs.append(loadPGM(p, file_encoding))
        
    return np.array(imgs) 

    
    
    
    
    
    
    
    


# to load a series of non-spooled Andor .dat images into a 4D numpy array
def LoadAndorSeries(params, root_filename, data_folder= "." , background_file_name= "background.dat"):
        """
        Parameters
        ----------
        params : ExperimentParams object
            Contains config, number_of_pixels, and other parameters    
        data_folder : string
            path to the folder with the spooled series data, and the background image
        background_file_name : string
            name of background image, assumed to be in the data_folder
       
        Returns
        -------
        4D array of integers giving the background-subtracted camera counts in each pixel.
        Format: images[iterationNumber, pictureNumber, row, col]
    
        """
        background_array = np.zeros(params.number_of_pixels)
        #Load background image into background_array
        if background_file_name:
            background_img = data_folder + "//" + background_file_name
            file=open(background_img,"rb")
            content=file.read()
            background_array = np.frombuffer(content, dtype=params.data_type)
            background_array = background_array[0:params.number_of_pixels]
            file.close()

        #read the whole kinetic series, bg correct, and load all images into a numpy array called image-array_correcpted
        image_array = np.zeros(shape = (1, params.number_of_pixels * params.number_of_pics))[0] 
        image_array_corrected = np.zeros(shape = (1, params.number_of_pixels * params.number_of_pics))[0]
        for x in range(params.number_of_pics): 
            filename = data_folder + "\\" + root_filename + str(x+1)+ ".dat"    
            file = open(filename,"rb")
            content = file.read()
            data_array = np.frombuffer(content, dtype=params.data_type)
            data_array = data_array[0:params.number_of_pixels]
            data_array_corrected = data_array - background_array 
            image_array[x*params.number_of_pixels: (x+1)*params.number_of_pixels] = data_array
            # print("max value before background subtraction = "+str(np.max(image_array)))
            image_array_corrected[x*params.number_of_pixels: (x+1)*params.number_of_pixels] = data_array_corrected
            #print("max value after background subtraction = "+str(np.max(image_array_corrected)))
            
        # reshape the total_image_array_corrected into a 4D array
        # outermost dimension's size is equal to the number of iterations, 
        # 2nd outer dimensions size is number of pictures per iteration
        # 3rd dimensions size is equal to the height of the images
        #print(params.number_of_iterations, params.picturesPerIteration, params.height, params.width)
        images = np.reshape(image_array_corrected,(params.number_of_iterations, params.picturesPerIteration, params.height, params.width))
        return images
    
def LoadVariableLog(path, timemode='ctime'):
    if not os.path.exists(path):
        print('Warning!!!\nThe path for variable logs does not exist, no logs were loded.')
        return None
        
    filenames = os.listdir(path)
    filenames.sort()
    
    variable_list = []
    
    for filename in filenames:
        variable_dict = {}
        
        if timemode == 'ctime':
            variable_dict['time'] = datetime.datetime.fromtimestamp( os.path.getctime(os.path.join(path,filename)) )
        if timemode == 'mtime':
            variable_dict['time'] = datetime.datetime.fromtimestamp( os.path.getmtime(os.path.join(path,filename)) )
        
        # datetime.datetime.strptime(filename, 'Variables_%Y_%m_%d_%H_%M_%S_0.txt')
        # print(parameter_dict['time'])
        with open( path + '/' + filename) as f:
            next(f)
            for line in f:
                key, val = line.strip().split(' = ')
                variable_dict[key.replace(' ', '_')] = float(val)
                
        variable_list.append(variable_dict)
        
    return pd.DataFrame(variable_list).set_index('time')
    
# def GetVariables(variables, timestamp, variableLog):
#     variableSeries = variableLog[ variableLog.time < timestamp ].iloc[-1]
    
#     return variableSeries[variables]


def VariableFilter(timestamps, variableLog, variableFilterList):    
    
    # return all( [ eval( 'variableLogItem.' + ii ) for ii in variableFilterList ] )
    
    filteredList = []
    for ii, tt in enumerate(timestamps):        
        satisfy = []                                                
        for jj in variableFilterList:
            # print(eval('variableLogItem.'+ii ))
            satisfy.append( eval('variableLog.loc[tt].' + jj.replace(' ','_')) ) 
            
        if not all(satisfy):
            filteredList.append(ii)
        
    return filteredList

def Filetime2Logtime(fileTime, variableLog, timeLowLim=1, timeUpLim=18):
    if variableLog is None:
        return []
    
    Index = variableLog.index
    logTimes = []
    for ii, t in enumerate(fileTime):
        logTime = Index[ Index <= t ][-1]        
        dt = (t - logTime).total_seconds()
        
        if dt > timeUpLim or dt < timeLowLim:
            print('Warning! The log is {:.2f} s earlier than the data file, potential mismatching!'.format(dt))
            
            if dt < timeLowLim:
                logTime = Index[ Index <= t ][-2]
                print('Picked the logfile earlier, the time interval is {:.2f} s'.format((t - logTime).total_seconds()))

        logTimes.append(logTime)
        
    return logTimes


def GetFilePaths(*paths, cam='zyl', picsPerIteration=3, examFrom=None, examUntil=None):
    '''
    Generate the list of filenames in the correct order and selected range
    used for loading Zyla images. 
    '''
    FilePaths = []
    
    if cam == 'zyl':
        filetype = '.dat'
    elif cam == 'cha':
        filetype = '.pgm'        
    else:
        raise ValueError('Camera setting not correct!\nCurrently support "zyl" and "cha".')
    
    for path in paths:
    
        filenames = glob.glob1(path, '*' + filetype)
        
        if cam == 'zyl':
            filenamesInd = [ ii[9::-1] for ii in filenames]
            indexedFilenames = list(zip(filenamesInd, filenames))
            indexedFilenames.sort()
            filepaths = [os.path.join(path, ii[1]) for ii in indexedFilenames]
        elif cam == 'cha':
            filenames.sort()
            filepaths = [os.path.join(path, ii) for ii in filenames]
        
        FilePaths.extend(filepaths)
    
    if examFrom:
        examFrom *= picsPerIteration
    if examUntil:
        examUntil *= picsPerIteration
        
    return FilePaths[examFrom: examUntil]

def FillFilePathList(firstImgPaths, picsPerIteration=4):
    
    fullList = []
    
    for p in firstImgPaths:
        folderPath, firstfname = p.replace('\\', '/').rsplit('/', 1)
        
        firstInd = int(firstfname[9::-1])
        fileInd = np.arange(firstInd, firstInd + picsPerIteration)
        
        paths = [ folderPath + '/' + '{:010d}'.format(ii)[::-1] + 'spool.dat' for ii in fileInd ]
        fullList.extend(paths)
    
    return fullList
    

def LoadSpooledSeriesV2(firstImgPaths, picturesPerIteration, metadata,                          
                        background_folder = ".",  background_file_name= ""):
    """
    Modified from LoadSpooledSeries, works with multiple folders. 
    
    Parameters
    ----------
    paths : string
        path to the folder with the spooled series data, and the background image
    background_file_name : string
        name of background image, assumed to be in the data_folder
       
    Returns
    -------
    4D array of integers giving the background-subtracted camera 
    in each pixel.
    Format: images[iterationNumber, pictureNumber, row, col]
    
    """
    
    # for path in paths:
    #     if not os.path.exists(path):
    #         raise Exception("Data folder not found:" + str(path).replace('\\', '/'))
    
    #     number_of_pics = len(glob.glob1(path,"*spool.dat"))
    #     if number_of_pics == 0:
    #         print('Warning!\n{}\ndoes not contain any data file!'.format(path.replace('\\', '/')))
    #     elif number_of_pics % picturesPerIteration:
    #         raise Exception('The number of data files in\n{}\nis not correct!'.format(path.replace('\\', '/')))
        
    #Load meta data
    height =int( metadata["data"]["AOIHeight"])
    width = int( metadata["data"]["AOIWidth"])
    pix_format = metadata["data"]["PixelEncoding"]
    if pix_format.lower() == "mono16":
        data_type=np.uint16
    else:
        raise Exception("Unknown pixel format " + pix_format)
    number_of_pixels = height*width
            
    #Get the filenames and select the range needed.
    filePaths = FillFilePathList(firstImgPaths, picsPerIteration=picturesPerIteration)
    
    number_of_pics = len(filePaths)        
    number_of_iterations = int(number_of_pics/picturesPerIteration)
    
    #Load background image into background_array
    if background_file_name:
        background_img = os.path.join(background_folder, background_file_name)
        file=open(background_img,"rb")
        content=file.read()
        background_array = np.frombuffer(content, dtype=data_type)
        background_array = background_array[0:number_of_pixels]
        file.close()
    #read the whole kinetic series, bg correct, and load all images into a numpy array called image-array_correcpted
    image_array = np.zeros(shape = (number_of_pixels * number_of_pics))
    
    print('Loading pictures: ', end='')
    for ind, filepath in enumerate(filePaths):
                
        with open(filepath, 'rb') as f:
            content = f.read()
            
        data_array = np.frombuffer(content, dtype=data_type)
        data_array = data_array[:number_of_pixels] # a spool file that is not bg corrected
        if background_file_name:
            data_array = data_array - background_array #spool file that is background corrected
        image_array[ind*number_of_pixels: (ind+1)*number_of_pixels] = data_array
        
        if ind % (10*picturesPerIteration) == 0:
            print('|', end='')
    print('\nFinish loading pictures, {} raw images loaded.'.format(ind+1))          
    
    # reshape the total_image_array_corrected into a 4D array
    # outermost dimension's size is equal to the number of iterations, 
    # 2nd outer dimensions size is number of pictures per iteration
    # 3rd dimensions size is equal to the height of the images
    #print(params.number_of_iterations, params.picturesPerIteration, params.height, params.width)
    return image_array.reshape(number_of_iterations, picturesPerIteration, height, width)
    
    
def LoadSpooledSeriesDesignatedFile(*filePaths, picturesPerIteration=3, 
                                    background_folder = ".",  background_file_name= ""):
        """
        Modified from LoadSpooledSeries, works with multiple folders. 
        
        Parameters
        ----------
        paths : string
            path to the folder with the spooled series data, and the background image
        background_file_name : string
            name of background image, assumed to be in the data_folder
       
        Returns
        -------
        4D array of integers giving the background-subtracted camera 
        in each pixel.
        Format: images[iterationNumber, pictureNumber, row, col]
    
        """
        

        # #Load meta data
        # metadata = LoadConfigFile(paths[0], "acquisitionmetadata.ini",encoding="utf-8-sig")
        # height =int( metadata["data"]["AOIHeight"])
        # width = int( metadata["data"]["AOIWidth"])
        # pix_format = metadata["data"]["PixelEncoding"]
        # if pix_format.lower() == "mono16":
        #     data_type=np.uint16
        # else:
        #     raise Exception("Unknown pixel format " + pix_format)
        # number_of_pixels = height*width
                
        # #Get the filenames and select the range needed.
        # filePaths = GetFilePaths(*paths, picsPerIteration=picturesPerIteration, 
        #                          examFrom=examFrom, examUntil=examUntil)
        # number_of_pics = len(filePaths)        
        # number_of_iterations = int(number_of_pics/picturesPerIteration)
        
        # #Load background image into background_array
        # if background_file_name:
        #     background_img = os.path.join(background_folder, background_file_name)
        #     file = open(background_img,"rb")
        #     content = file.read()
        #     background_array = np.frombuffer(content, dtype=data_type)
        #     background_array = background_array[0:number_of_pixels]
        #     file.close()
        # #read the whole kinetic series, bg correct, and load all images into a numpy array called image-array_correcpted
        # image_array = np.zeros(shape = (number_of_pixels * number_of_pics))
        
        # for ind, filepath in enumerate(filePaths):
                        
        #     file = open(filepath, "rb")
        #     content = file.read()
        #     data_array = np.frombuffer(content, dtype=data_type)
        #     data_array = data_array[:number_of_pixels] # a spool file that is not bg corrected
        #     if background_file_name:
        #         data_array = data_array - background_array #spool file that is background corrected
        #     image_array[ind*number_of_pixels: (ind+1)*number_of_pixels] = data_array            

        # # reshape the total_image_array_corrected into a 4D array
        # # outermost dimension's size is equal to the number of iterations, 
        # # 2nd outer dimensions size is number of pictures per iteration
        # # 3rd dimensions size is equal to the height of the images
        # #print(params.number_of_iterations, params.picturesPerIteration, params.height, params.width)
        # images = image_array.reshape(number_of_iterations, picturesPerIteration, height, width)
        
        # return images


def BuildCatalogue(*paths, cam='zyl',
                   picturesPerIteration=4, skipFirstImg=0, 
                   timemode='ctime', dirLevelAfterDayFolder=2, writetodrive=1):
    
    paths = [ii.replace('\\', '/') for ii in paths]    
    dayfolders = np.unique( [ii.rstrip('/').rsplit('/', dirLevelAfterDayFolder)[0] for ii in paths] ) # Get all folders for different days in provided paths.
    
    variableLog = []
    for ff in dayfolders:
        variablelogfolder = os.path.join(ff, 'Variable Logs')
        variableLog.append( LoadVariableLog(variablelogfolder,timemode=timemode) )
        
    if len(variableLog) == 0:
        raise ValueError('No variable logs were found!')
        
    variableLog = pd.concat(variableLog)
    
    catalogue = []
    for pp in paths:
        
        fistImgPath = GetFilePaths(pp, cam=cam)[::picturesPerIteration]
        
        fileTime = []
        for ff in fistImgPath:
            fileTime.append( datetime.datetime.fromtimestamp(os.path.getmtime(ff)) )            
        
        logTime = Filetime2Logtime(fileTime, variableLog)
        df = variableLog.loc[logTime]
        
        # fistImgPath = ['/'.join(ff.replace('\\', '/').rsplit('/', 2)[1:]) for ff in fistImgPath]
        # df.insert(0, 'FirstImg', fistImgPath)
        
        fistImgName = [ ff.replace('\\', '/').rsplit('/', 1)[-1] for ff in fistImgPath]
        df.insert(0, 'SkipFI', skipFirstImg)
        df.insert(0, 'PPI', picturesPerIteration)
        df.insert(0, 'FirstImg', fistImgName)
        
        # df.Lens_Position = 1.85

        if writetodrive:
            df.to_csv(os.path.join(pp, 'Catalogue.csv'))
            with open(os.path.join(pp, 'Catalogue.pkl'), 'wb') as f:
                pickle.dump(df, f)
        
        df['FolderPath'] = pp
        catalogue.append( df )
            
    return catalogue

    
def PreprocessZylaImg(*paths, examRange=[None, None], rotateAngle=0,
                      rowstart=10, rowend=-10, columnstart=10, columnend=-10, 
                      subtract_burntin=0, skipFirstImg='auto', showRawImgs=0,
                      filterLists=[], 
                      loadVariableLog=1, rebuildCatalogue=0,
                      dirLevelAfterDayFolder=2):
    '''
    Given paths to picture binary files, built catalogue if not exist, 
    '''

    paths = [ii.replace('\\', '/') for ii in paths]
    date = datetime.datetime.strptime( paths[0].split('/Andor')[0].rsplit('/',1)[-1], '%d %b %Y' )
    
    if skipFirstImg == 'auto':    
        if date > datetime.datetime(2024, 4, 3):
            skipFirstImg = 1
        else:
            skipFirstImg = 0

    PPI = 4 if (subtract_burntin or skipFirstImg) else 3
    firstFrame = 1 if (skipFirstImg and not subtract_burntin) else 0
    skipFirstImg = 1 if firstFrame else 0
    
    print('subtract burntin\t', subtract_burntin)
    print('skip firstImg\t\t', skipFirstImg)
    print('picture/iteration\t', PPI)
    print('first frame\t\t\t', firstFrame)
    
    N = 0
    pathNeedCatalogue = []
    catalogue = []
    
    for path in paths:
        if not os.path.exists(path):
            print("Warning! Data folder not found:" + str(path))
            continue
        
        number_of_pics = len(glob.glob1(path,"*spool.dat"))
        if number_of_pics == 0:
            print('Warning!\n{}\ndoes not contain any data file!'.format(path))
        elif number_of_pics % PPI:
            raise Exception('The number of data files in\n{}\nis not correct!'.format(path))
            
        cataloguePath = os.path.join(path, 'Catalogue.pkl')
        existCatalogue = os.path.exists(cataloguePath)
        
        if loadVariableLog and (rebuildCatalogue or not existCatalogue ):
            pathNeedCatalogue.append(path)
            
        elif existCatalogue:
            
            df = pd.read_pickle(cataloguePath)
            
            # If the lengh of the catalogue is different from the iteration number, determine if rebuild it or not.
            if (len(df) != (number_of_pics / PPI)):
                # If current time is 12 hours or 7 days later than the data were took, prevent auto rebuild the catalogue. 
                dt = datetime.datetime.now() - df.index[0]
                
                if (df.PPI[0] != PPI) or (df.SkipFI[0] != skipFirstImg):
                    if dt > pd.Timedelta(0.5, "d"):
                        raise ValueError('The input of subtract_burntin or skipFirstImg does not match the record!\nCorrect the input or set rebuildCatalogue to 1 to force rebuild the catalogue.')
                else:
                    if dt > pd.Timedelta(7, "d"):
                        raise ValueError('The number of files in {}\nis different from recorded, set rebuildCatalogue to 1 to force rebuild the catalogue.')
                # Rebuild the catalogue otherwise.        
                pathNeedCatalogue.append(path)
            # Add the folder path to the datalogue and load it.                
            else:
                df['FolderPath'] = path                
                catalogue.append( df )                
            
        N += number_of_pics        
    if N == 0:
        raise Exception('No data file was found in all provided folders!')
        
    if loadVariableLog and pathNeedCatalogue:        
        catalogue.extend( BuildCatalogue(*pathNeedCatalogue, picturesPerIteration=PPI, 
                                         skipFirstImg=skipFirstImg,
                                         dirLevelAfterDayFolder=dirLevelAfterDayFolder) )
        
    catalogue = DataFilter(pd.concat(catalogue), filterLists=filterLists)[examRange[0]: examRange[1]]
    
    if len(catalogue) == 0:
        raise ValueError('Len(Catalogue) is ZERO! No item satisfy the conditions!')
    
    firstImgPaths = catalogue[['FolderPath', 'FirstImg']].apply(lambda row: os.path.join(*row), axis=1).values
    
    rawImgs = LoadSpooledSeriesV2(firstImgPaths, 
                                  picturesPerIteration=PPI,              ####change PPI, add SkipFI
                                  # picturesPerIteration=catalogue.PPI, 
                                  metadata = LoadConfigFile(paths[0], "acquisitionmetadata.ini",encoding="utf-8-sig"))
    
    if showRawImgs:
        ShowImagesTranspose(rawImgs, uniformscale=False)
        
    opticalDensity = absImagingSimpleV2(rawImgs, firstFrame=firstFrame, correctionFactorInput=1.0,
                                        subtract_burntin=subtract_burntin, preventNAN_and_INF=True)
    
    folderNames = [ii.rsplit('/', 1)[-1] for ii in catalogue.FolderPath]    
    # catalogue = catalogue.drop('FolderPath', axis=1)
    catalogue.insert(0, 'Folder', folderNames)
    
    if rotateAngle:
        opticalDensity = rotate(opticalDensity, rotateAngle, axes=(1,2), reshape = False)
        print('\nColumnDensities rotated.\n')
        
    return opticalDensity[:, rowstart:rowend, columnstart:columnend], catalogue


def PreprocessAIAImgs(*paths, examRange=(None, None), rotateAngle=0,
                      ROI=None, showRawImgs=0, returnRawImgs=0,
                      expectedExposures=4):
    """Load Simplicio AIA sets and calculate their optical density.

    AIA files contain one complete acquisition set each. This loader stacks
    them as ``(set, exposure, row, column)``, matching the dimensional order
    used by the existing Zyla and Chameleon analysis functions.

    The Pixelfly sequence uses four exposures in this order::

        0. burn-in frame (discarded)
        1. probe with atoms
        2. probe without atoms
        3. dark/background

    Optional Cicero variables appended to each AIA file are returned as one
    row per acquisition in the catalogue DataFrame.
    """
    from ImageAnalysis.AIAReader import read_aia_record

    filePaths = []
    for path in paths:
        path = os.fspath(path)
        if os.path.isdir(path):
            filePaths.extend(sorted(glob.glob(os.path.join(path, '*.aia'))))
        elif path.lower().endswith('.aia') and os.path.isfile(path):
            filePaths.append(path)
        else:
            raise FileNotFoundError('AIA path not found: {}'.format(path))

    if not filePaths:
        raise FileNotFoundError('No .aia files were found in the supplied paths.')

    examFrom, examUntil = examRange
    filePaths = filePaths[examFrom:examUntil]
    if not filePaths:
        raise ValueError('The selected AIA examination range contains no files.')

    records = [read_aia_record(path) for path in filePaths]
    firstShape = records[0].pixels.shape

    if expectedExposures is not None and firstShape[0] != expectedExposures:
        raise ValueError(
            '{} contains {} exposures; expected {}.'.format(
                records[0].path, firstShape[0], expectedExposures))

    for record in records[1:]:
        if record.pixels.shape != firstShape:
            raise ValueError(
                '{} has shape {}; expected {}.'.format(
                    record.path, record.pixels.shape, firstShape))

    rawImgs = np.stack([record.pixels for record in records], axis=0)

    catalogueRows = []
    catalogueTimes = []
    for record in records:
        row = dict(record.sequence_variables)
        row.update({
            'File': record.path.name,
            'Folder': record.path.parent.name,
            'FolderPath': str(record.path.parent),
            'PPI': record.exposures,
            'FrameMode': 'discard-burnin',
        })
        catalogueRows.append(row)
        catalogueTimes.append(datetime.datetime.fromtimestamp(
            os.path.getmtime(record.path)))

    catalogue = pd.DataFrame(
        catalogueRows,
        index=pd.DatetimeIndex(catalogueTimes, name='AcquisitionTime'))

    if showRawImgs:
        ShowImagesTranspose(rawImgs, uniformscale=False)

    # Exposure zero burns in the camera and is discarded before analysis.
    opticalDensity = absImagingSimpleV2(
        rawImgs, firstFrame=1, correctionFactorInput=1.0,
        subtract_burntin=False, preventNAN_and_INF=True)

    if rotateAngle:
        opticalDensity = rotate(
            opticalDensity, rotateAngle, axes=(1, 2), reshape=False)
        print('\nOptical densities rotated.\n')

    if ROI is not None:
        opticalDensity = opticalDensity[
            :, ROI[0]:ROI[1], ROI[2]:ROI[3]]

    if returnRawImgs:
        return opticalDensity, catalogue, rawImgs
    return opticalDensity, catalogue


def PreprocessBinImgs(*paths, camera='zyla', 
                      examRange=[None, None], rotateAngle=0,
                      ROI = [10, -10, 10, -10],
                      subtract_burntin=0, skipFirstImg='auto', 
                      showRawImgs=0, returnRawImgs=0,
                      filterLists=[], 
                      loadVariableLog=1, rebuildCatalogue=0,
                      dirLevelAfterDayFolder=2):
    '''
    Given paths to picture binary files, built catalogue if not exist, 
    and then load the pictures and return optical densities. 
    '''
    
    paths = [ii.replace('\\', '/') for ii in paths] # Change the paths to Linux style.
    
    camera = camera.lower()
    if camera[0:3] == 'zyl':
        date = datetime.datetime.strptime( paths[0].split('/Andor')[0].rsplit('/',1)[-1], '%d %b %Y' ) # Get the date of the data from the path.
        filetype = '.dat'
        camera = 'zyl'

    elif camera[:3] == 'cha':
        date = datetime.datetime.strptime( paths[0].split('/FLIR')[0].rsplit('/',1)[-1], '%d %b %Y' ) # Get the date of the data from the path.
        filetype = '.pgm'
        camera = 'cha'
        
    else:
        raise ValueError('Camera setting not correct!\nCurrently support "Zyla" and "Chameleon".')
    
    if skipFirstImg == 'auto':
        if camera == 'cha':
            skipFirstImg = 0
        elif date > datetime.datetime(2024, 4, 3):
            skipFirstImg = 1
        else:
            skipFirstImg = 0

    PPI = 4 if (subtract_burntin or skipFirstImg) else 3
    firstFrame = 1 if (skipFirstImg and not subtract_burntin) else 0
    skipFirstImg = 1 if firstFrame else 0
    
    print('subtract burntin\t', subtract_burntin)
    print('skip firstImg\t\t', skipFirstImg)
    print('picture/iteration\t', PPI)
    print('first frame\t\t\t', firstFrame)
    
    # Deal with variable logs
    N = 0 # Totol number of images in all provided folders. 
    pathNeedCatalogue = []
    catalogue = []
    
    # Go throught the folders, examine if No of pictures are correct, and if buidling a catalogue is needed. 
    for path in paths:
        if not os.path.exists(path):
            print("Warning! Data folder not found:" + str(path))
            continue
        
        number_of_pics = len( glob.glob1(path, '*' + filetype) )
        if number_of_pics == 0:
            print('Warning!\n{}\ndoes not contain any data file!'.format(path))
        elif number_of_pics % PPI:
            raise Exception('The number of data files in\n{}\nis not correct!'.format(path))
            
        cataloguePath = os.path.join(path, 'Catalogue.pkl')
        existCatalogue = os.path.exists(cataloguePath)
        
        if loadVariableLog and (rebuildCatalogue or not existCatalogue): # If the catalogue not exist or need to be rebuilt, keep the path 
            pathNeedCatalogue.append(path)
            
        elif existCatalogue: # Load the catalogue otherwise.        
            df = pd.read_pickle(cataloguePath)
            
            # If the lengh of the catalogue is different from the iteration number, determine if rebuild it or not.
            if (len(df) != (number_of_pics / PPI)):
                # If current time is 12 hours or 7 days later than the data were took, prevent auto rebuild the catalogue. 
                dt = datetime.datetime.now() - df.index[0]
                
                if (df.PPI[0] != PPI) or (df.SkipFI[0] != skipFirstImg):
                    if dt > pd.Timedelta(0.5, "d"):
                        raise ValueError('The input of subtract_burntin or skipFirstImg does not match the record!\nCorrect the input or set rebuildCatalogue to 1 to force rebuild the catalogue.')
                else:
                    if dt > pd.Timedelta(7, "d"):
                        raise ValueError('The number of files in {}\nis different from recorded, set rebuildCatalogue to 1 to force rebuild the catalogue.')
                # Rebuild the catalogue otherwise.        
                pathNeedCatalogue.append(path)
            # Add the folder path to the datalogue and load it.                
            else:
                df['FolderPath'] = path                
                catalogue.append( df )                
            
        N += number_of_pics        
    if N == 0:
        raise Exception('No data file was found in all provided folders!')
        
    # Build the catalogue for the folders that need one, and append to the loaded ones.         
    if loadVariableLog and pathNeedCatalogue: 
        catalogue.extend( BuildCatalogue(*pathNeedCatalogue, cam=camera,
                                         picturesPerIteration=PPI, skipFirstImg=skipFirstImg,
                                         dirLevelAfterDayFolder=dirLevelAfterDayFolder) )
    
    catalogue = DataFilter(pd.concat(catalogue), filterLists=filterLists)[examRange[0]: examRange[1]]
    
    if len(catalogue) == 0:
        raise ValueError('Len(Catalogue) is ZERO! No item satisfy the conditions!')
    
    dfpaths = catalogue[['FolderPath', 'FirstImg']]

    if camera == 'zyl':
        firstImgPaths = dfpaths.apply(lambda row: os.path.join(*row), axis=1).values
        rawImgs = LoadSpooledSeriesV2(firstImgPaths, 
                                  picturesPerIteration=PPI,              ####change PPI, add SkipFI
                                  # picturesPerIteration=catalogue.PPI, 
                                  metadata = LoadConfigFile(paths[0], "acquisitionmetadata.ini",encoding="utf-8-sig"))
    elif camera == 'cha':        
        imgPaths = FillFilePathsListFLIR(dfpaths, PPI)        
        rawImgs = loadSeriesPGMV2(imgPaths, file_encoding='binary')
        rawImgs = rawImgs.reshape( -1, PPI, *rawImgs.shape[-2:] )            
    
    if showRawImgs:
        ShowImagesTranspose(rawImgs, uniformscale=False)
        
    opticalDensity = absImagingSimpleV2(rawImgs, firstFrame=firstFrame, correctionFactorInput=1.0,
                                        subtract_burntin=subtract_burntin, preventNAN_and_INF=True)
    
    folderNames = [ii.rsplit('/', 1)[-1] for ii in catalogue.FolderPath]    
    # catalogue = catalogue.drop('FolderPath', axis=1)
    catalogue.insert(0, 'Folder', folderNames)
    
    if rotateAngle:
        opticalDensity = rotate(opticalDensity, rotateAngle, axes=(1,2), reshape = False)
        print('\nColumnDensities rotated.\n')
        
    if returnRawImgs:
        return opticalDensity[:, ROI[0]: ROI[1], ROI[2]: ROI[3]], catalogue, rawImgs
    else:
        return opticalDensity[:, ROI[0]: ROI[1], ROI[2]: ROI[3]], catalogue



def DetectPeak2D(img, sigma=5, thr=0.7, doplot=0, usesmoothedimg=1):

    if sigma:
        imgFlted = gaussian_filter(img, sigma=sigma)
    else:
        imgFlted = img.copy()

    thr_ratio = thr
    thr = thr*(imgFlted.max() - imgFlted.min()) + imgFlted.min()

    if usesmoothedimg:
        imgthred = imgFlted.copy()
        imgthred[ imgFlted < thr ] = 0
    else:
        imgthred = img.copy()
        imgthred[ imgFlted < thr ] = 0

    center = center_of_mass(imgthred)

    if doplot:
        fig, axes = plt.subplots(1, 3, figsize=(15,10), sharex=True, sharey=True)
        fig.subplots_adjust(hspace=0.05, wspace=0.05)

        axes[0].imshow(img, cmap='gray')
        axes[0].plot(center[1], center[0], 'x')
        axes[0].text(0.01, 0.99, 'center = ({:.3f}, {:.3f})\nsigma = {:.3f}, thr = {:.3f}'.format(center[1], center[0], sigma, thr_ratio),
                     ha='left', va='top', transform=axes[0].transAxes,
                     bbox=dict(boxstyle="square", ec=(0,0,0), fc=(1,1,1), alpha=0.7) )

        axes[1].imshow(imgFlted, cmap='gray')
        axes[1].plot(center[1], center[0], 'x')

        axes[2].imshow(img, cmap='gray', alpha=1)
        axes[2].imshow(imgthred, cmap='autumn', alpha=(imgthred==0).astype(float)*0.2)
        axes[2].plot(center[1], center[0], 'x')

    return np.array(center)


def AutoCrop(imgs, sizes=[150, 150],
             sigma=5, thr=0.7,
             autosize=0, doplot=0):

    dimens = imgs.shape
    if len(dimens) == 2:
        imgs = imgs.reshape(1, *dimens)

    width, height = sizes
    output = np.full((len(imgs), 2*height+1, 2*width+1), np.nan)

    for ii, img in enumerate(imgs):
        y0, x0 = DetectPeak2D(img, sigma=sigma, thr=thr, doplot=0).astype(int)
        # if autosize:
        #     # do a fit to each image and estimate a size.
        output[ii] = np.pad( img, ((height, height), (width, width)), constant_values=np.nan )[ y0: y0+2*height+1, x0: x0+2*width+1 ]

    return output       


def SaveResultsDftoEachFolder(df, overwrite=0):
    
    paths = np.unique( df.FolderPath )
    
    for pp in paths:
        df1 = df[ df.FolderPath == pp ]
        resultsPath = os.path.join(pp, 'Results.pkl')
        
        if os.path.exists(resultsPath):            
            with open(resultsPath, 'rb') as f:
                df0 = pickle.load(f)
                
            intersection = df1.index.intersection(df0.index)
            
            if overwrite:
                df1 = pd.concat( [df0.drop(intersection), df1] )
            else:
                df1 = pd.concat( [df1.drop(intersection), df0] )            
        
        df1 = df1.sort_index()
        df1.to_csv( os.path.join(pp, 'Results.csv') )
        with open(resultsPath, 'wb' ) as f:
            pickle.dump(df1, f)
        print('Results saved to folder: {}.'.format(pp.replace('\\', '/').strip('/').rsplit('/', 1)[-1]))
        
def LoadDfResults(*paths):
    
    paths = [ii.replace('\\', '/') for ii in paths]
    
    dfs = []
    for pp in paths:
        resultsPath = os.path.join(pp, 'Results.pkl')
    
        if not os.path.exists(resultsPath):
            print("Warning! Results not found in folder:" + str(pp))
            continue
            
    
def FitColumnDensity(columnDensities, dx=1, mode='both', yFitMode='single', 
                     subtract_bg=1, Xsignal_feature='wide', Ysignal_feature='narrow'):
    
    popts = []
    bgs = []
    
    if mode.lower() == 'y' or mode.lower()=='both':
        CD1D = np.nansum(columnDensities, axis=2) * dx / 1e6**2
        
        poptsY = []
        bgsY = []
        
        print('Fitting y data: ', end='')
        for ii, ydata in enumerate(CD1D):
            if yFitMode.lower() == 'single':
                popt, bg = fitSingleGaussian(ydata, dx=dx,
                                             subtract_bg=subtract_bg, signal_feature=Ysignal_feature)
            elif yFitMode.lower() == 'multiple':                
                popt, _, bg = fitMultiGaussian(ydata, dx=dx, 
                                            subtract_bg=subtract_bg, signal_feature=Ysignal_feature, 
                                            fitbgDeg=3, amp=1, width=1, denoise=1, peakplot=1)                
            else: 
                raise ValueError("The yFitMode shoud be 'single' or 'multiple'.")
                
            poptsY.append(popt)
            bgsY.append(bg)
            
            if ii % 10 == 0:
                print('|', end='')
        print()
        popts.append(poptsY)
        bgs.append(bgsY)
        
    if mode.lower() == 'x' or mode.lower()=='both':        
        CD1D = np.nansum(columnDensities, axis=1) * dx / 1e6**2
        poptsX = []
        bgsX = []
        
        print('Fitting x data: ', end='')
        for ii, xdata in enumerate(CD1D):
            popt, bg = fitSingleGaussian(xdata, dx=dx,
                                         subtract_bg=0, signal_feature=Ysignal_feature)
            poptsX.append(popt)
            bgsX.append(bg)
            
            if ii % 10 == 0:
                print('|', end='')
        print()            
            
        popts.append(poptsX)
        bgs.append(bgsX)
    print('Finish fitting data.')
        
    return popts, bgs


def GetFileNames(data_folder, picsPerIteration=3, examFrom=None, examUntil=None):
    '''
    Generate the list of filenames in the correct order and selected range
    used for loading Zyla images. 
    '''
    filenames = glob.glob1(data_folder,"*spool.dat")
    filenamesInd = [ ii[6::-1] for ii in filenames]
    
    indexedFilenames = list(zip(filenamesInd, filenames))
    indexedFilenames.sort()
    
    filenames = [ii[1] for ii in indexedFilenames]
    
    if examFrom:
        examFrom *= picsPerIteration
    if examUntil:
        examUntil *= picsPerIteration
        
    return filenames[examFrom: examUntil]

def LoadSpooledSeries(params, data_folder= "." ,background_folder = ".",  background_file_name= "",
                      examFrom=None, examUntil=None, return_fileTime=0, timemode='ctime'):
        """
        Parameters
        ----------
        params : ExperimentParams object
            Contains picturesPerIteration    
        data_folder : string
            path to the folder with the spooled series data, and the background image
        background_file_name : string
            name of background image, assumed to be in the data_folder
       
        Returns
        -------
        4D array of integers giving the background-subtracted camera 
        in each pixel.
        Format: images[iterationNumber, pictureNumber, row, col]
    
        """
        if not os.path.exists(data_folder):
            raise Exception("Data folder not found:" + str(data_folder))
        #Load meta data
        metadata = LoadConfigFile(data_folder, "acquisitionmetadata.ini",encoding="utf-8-sig")
        height =int( metadata["data"]["AOIHeight"])
        width = int( metadata["data"]["AOIWidth"])
        pix_format = metadata["data"]["PixelEncoding"]
        if pix_format.lower() == "mono16":
            data_type=np.uint16
        else:
            raise Exception("Unknown pixel format " + pix_format)
        number_of_pixels = height*width
        
        number_of_pics = len(glob.glob1(data_folder,"*spool.dat"))
        picturesPerIteration = params.picturesPerIteration
        assert number_of_pics % picturesPerIteration == 0
        
        #Get the filenames and select the range needed.
        fileNames = GetFileNames(data_folder, picturesPerIteration, examFrom, examUntil)
        number_of_pics = len(fileNames)        
        number_of_iterations = int(number_of_pics/picturesPerIteration)

        background_array = np.zeros(number_of_pixels)
        #Load background image into background_array
        if background_file_name:
            background_img = background_folder + "//" + background_file_name
            file=open(background_img,"rb")
            content=file.read()
            background_array = np.frombuffer(content, dtype=data_type)
            background_array = background_array[0:number_of_pixels]
            file.close()
        #read the whole kinetic series, bg correct, and load all images into a numpy array called image-array_correcpted
        image_array =           np.zeros(shape = (number_of_pixels * number_of_pics))
        image_array_corrected = np.zeros(shape = (number_of_pixels * number_of_pics))
        fileTime = []
        
        for ind in range(number_of_pics): 
            
            filename = data_folder + "\\" + fileNames[ind] 
                
            if ind % picturesPerIteration == 0 and return_fileTime:
                
                if timemode == 'ctime':
                    fileTime.append( datetime.datetime.fromtimestamp( os.path.getctime(filename) ) )
                if timemode == 'mtime':
                    fileTime.append( datetime.datetime.fromtimestamp( os.path.getmtime(filename) ) )
                    
            file = open(filename,"rb")
            content = file.read()
            
            # with open(filename, 'rb') as f:
            #     content = f.read()

            data_array = np.frombuffer(content, dtype=data_type)
            data_array = data_array[0:number_of_pixels] # a spool file that is not bg corrected
            data_array_corrected = data_array - background_array #spool file that is background corrected
            image_array[ind*number_of_pixels: (ind+1)*number_of_pixels] = data_array
            # print("max value before background subtraction = "+str(np.max(data_array)))
            image_array_corrected[ind*number_of_pixels: (ind+1)*number_of_pixels] = data_array_corrected
            #print("max value after background subtraction = "+str(np.max(image_array_corrected)))
            

            
        # reshape the total_image_array_corrected into a 4D array
        # outermost dimension's size is equal to the number of iterations, 
        # 2nd outer dimensions size is number of pictures per iteration
        # 3rd dimensions size is equal to the height of the images
        #print(params.number_of_iterations, params.picturesPerIteration, params.height, params.width)
        images = np.reshape(image_array_corrected,(number_of_iterations, picturesPerIteration, height, width))
        
        if return_fileTime:
            return images, fileTime
        else:
            return images
    
def LoadFromSpooledSeries(params, iterationNum, data_folder= "." ,background_folder = ".",  background_file_name= ""):
        """
        Parameters
        ----------
        params : ExperimentParams object
            Contains picturesPerIteration    
        data_folder : string
            path to the folder with the spooled series data, and the background image
        background_file_name : string
            name of background image, assumed to be in the data_folder
       
        Returns
        -------
        4D array of integers giving the background-subtracted camera 
        in each pixel.
        Format: images[iterationNumber, pictureNumber, row, col]
    
        """
        number_of_pics = len(glob.glob1(data_folder,"*spool.dat"))
        if iterationNum == -1:
            numPicsDividesThree = int(np.floor(number_of_pics/3)*3)
            startNum = numPicsDividesThree-3
        else:
            startNum = iterationNum*params.picturesPerIteration
        numToLoad = params.picturesPerIteration
        #Load meta data
        metadata = LoadConfigFile(data_folder, "acquisitionmetadata.ini",encoding="utf-8-sig")
        height =int( metadata["data"]["AOIHeight"])
        width = int( metadata["data"]["AOIWidth"])
        pix_format = metadata["data"]["PixelEncoding"]
        if pix_format.lower() == "mono16":
            data_type=np.uint16
        else:
            raise Exception("Unknown pixel format " + pix_format)
        number_of_pixels = height*width
        picturesPerIteration = params.picturesPerIteration
        assert numToLoad % picturesPerIteration == 0
        number_of_iterations = int(numToLoad/picturesPerIteration)

        background_array = np.zeros(number_of_pixels)
        #Load background image into background_array
        if background_file_name:
            background_img = background_folder + "//" + background_file_name
            file=open(background_img,"rb")
            content=file.read()
            background_array = np.frombuffer(content, dtype=data_type)
            background_array = background_array[0:number_of_pixels]
            file.close()
        #read the whole kinetic series, bg correct, and load all images into a numpy array called image-array_correcpted
        image_array =           np.zeros(shape = (number_of_pixels * numToLoad))
        image_array_corrected = np.zeros(shape = (number_of_pixels * numToLoad))
        spool_number = '0000000000'
        for x in np.arange(startNum,startNum+numToLoad): 
            localIndex = x - startNum
            filename = data_folder + "\\"+ str(int(x))[::-1] + spool_number[0:(10-len(str(int(x))))]+"spool.dat"
            file = open(filename,"rb")
            content = file.read()
            data_array = np.frombuffer(content, dtype=data_type)
            data_array = data_array[0:number_of_pixels] # a spool file that is not bg corrected
            data_array_corrected = data_array - background_array #spool file that is background corrected
            image_array[localIndex*number_of_pixels: (localIndex+1)*number_of_pixels] = data_array
            # print("max value before background subtraction = "+str(np.max(data_array)))
            image_array_corrected[localIndex*number_of_pixels: (localIndex+1)*number_of_pixels] = data_array_corrected
            #print("max value after background subtraction = "+str(np.max(image_array_corrected)))
            
        # reshape the total_image_array_corrected into a 4D array
        # outermost dimension's size is equal to the number of iterations, 
        # 2nd outer dimensions size is number of pictures per iteration
        # 3rd dimensions size is equal to the height of the images
        #print(params.number_of_iterations, params.picturesPerIteration, params.height, params.width)
        images = np.reshape(image_array_corrected,(number_of_iterations, picturesPerIteration, height, width))
        return images    
    
    
    


def CountsToAtoms(params, counts):
    """
    Convert counts to atom number for fluorescence images
    
    Parameters
    ----------
    params : ExperimentParams object
        
    counts : array or number
        Camera counts from fluorescence image
        
    Returns
    -------
    Atom number (per pixel) array in same shape as input counts array

    """
    return  (4*np.pi*counts*params.camera.sensitivity)/(params.camera.quantum_eff*params.R_scat*params.t_exp*params.solid_angle)
    

def ShowImages3d(images,vmin=None,vmax=None):
    """
    Draws a grid of images

    Parameters
    ----------
    images : 3d Array

    """
    iterations, height, width = np.shape(images)
    #print(iterations,picturesPerIteration)
    #imax = np.max(images)
    #imin = np.min(images)
    MAX_COLS = 5
    ncols = min(MAX_COLS, iterations)
    nrows = int(np.ceil(iterations/ncols))
    fig =plt.figure()
    for it in range(iterations):
        #print(it)
        ax = plt.subplot(nrows,ncols,it+1)
        im = ax.imshow(images[it,:,:],cmap="gray",vmin = vmin, vmax=vmax)
        divider = make_axes_locatable(ax)
        cax = divider.append_axes('right', size='5%', pad=0.05)
        fig.colorbar(im, cax=cax, orientation='vertical')
    plt.tight_layout()
    plt.show()

def ShowImages(images):
    """
    Draws a grid of images

    Parameters
    ----------
    images : 4d Array

    """
    iterations, picturesPerIteration, height, width = np.shape(images)
    #print(iterations,picturesPerIteration)
    #imax = np.max(images)
    #imin = np.min(images)
    
    for it in range(iterations):
        for pic in range(picturesPerIteration):
            ax = plt.subplot(iterations, picturesPerIteration, it*picturesPerIteration + pic+1)
            ax.imshow(images[it,pic,:,:],cmap="gray")#,vmin = imin, vmax=imax)
    plt.tight_layout()
    plt.show()
    
def ShowImagesTranspose(images, logTime=None, variableLog=None,
                        variablesToDisplay=None, showTimestamp=False, 
                        uniformscale=False):
    """
    Draws a grid of images

    Parameters
    ----------
    images : 4d Array
    
    autoscale: boolean
        True: scale each image independently

    """
    
    iterations, picturesPerIteration, _, _ = images.shape
        
    if uniformscale:
        imax = images.max()
        imin = images.min()
    
    plt.rcParams.update({'font.size' : 8})
    
    fig, axs = plt.subplots(picturesPerIteration, iterations, figsize=(2.65*iterations, 2*picturesPerIteration), 
                            sharex=True, sharey=True, squeeze = False)
    plt.subplots_adjust(hspace=0.02, wspace=0.02)
    
    for it in range(iterations):
        for pic in range(picturesPerIteration):
            
            if uniformscale:                
                axs[pic, it].imshow(images[it,pic], cmap='gray', vmin = imin, vmax= imax)
            else:
                axs[pic, it].imshow(images[it,pic], cmap='gray')
                
            if variablesToDisplay is None or variableLog is None:
                axs[pic, it].text(0, 0, "iter #{}, pic #{}".format(it, pic), ha='left', va='top', 
                                  bbox=dict(boxstyle="square",ec=(0,0,0), fc=(1,1,1), alpha=0.7) )
            else:
                variablesToDisplay = [ii.replace(' ','_') for ii in variablesToDisplay]
                axs[pic, it].text(0,0, 
                                variableLog.loc[logTime[it]][variablesToDisplay].to_string(name=showTimestamp).replace('Name','Time'), 
                                fontsize=5, ha='left', va='top',
                                bbox=dict(boxstyle="square", ec=(0,0,0), fc=(1,1,1), alpha=0.7))
                
    fig.tight_layout()    
            

# simple, no analysis, list of pics => normalized
def ImageTotals(images):
    """
    
    ----------
    images : 4D array of images
    
    Returns
    -------
    2D Array of sums over the images

    """
    
    shape1 = np.shape(images)
    assert len(shape1) == 4, "input array must be 4D"
    
    shape2 = shape1[:-2]
    totals = np.zeros(shape2)
    
    for i in range(shape2[0]):
        for j in range(shape2[1]):
            totals[i,j] = np.sum(images[i,j,:,:])
    return totals
    
# def temp(images):    
#     atoms_x = np.zeros((params.number_of_pics, params.width))
#     atoms_y = np.zeros((params.number_of_pics, params.height))   
    
#     #Sum the columns of the region of interest to get a line trace of atoms as a function of x position
#     for i in range(params.number_of_iterations):
#         for j in range(params.picturesPerIteration) :
#             im_temp = images[i, j, params.ymin:params.ymax, params.xmin:params.xmax]
#             count_x = np.sum(im_temp,axis = 0) #sum over y direction/columns 
#             count_y = np.sum(im_temp,axis = 1) #sum over x direction/rows
#             atoms_x[i] = (4*np.pi*count_x*params.sensitivity)/(params.quantum_eff*params.R_scat*params.t_exp*params.solid_angle)
#             atoms_y[i] = (4*np.pi*count_y*params.sensitivity)/(params.quantum_eff*params.R_scat*params.t_exp*params.solid_angle)
#             print("num_atoms_vs_x in frame" , i, "is: {:e}".format(np.sum(atoms_x[i])))
#             print("num_atoms_vs_y in frame" , i, "is: {:e}".format(np.sum(atoms_y[i])))
    
#     if atoms_x != atoms_y:
#         print("atom count calculated along x and along y do NOT match")

#     atoms_x_max = max(atoms_x)
#     atoms_y_max = max(atoms_y)
#     atoms_max = max(atoms_x_max, atoms_y_max)        
    
#     return atoms_x, atoms_y, atoms_max        
#         #  output_array = np.array((number_of_iteration, outputPicsPerIteration, height, width)

def flsImaging(images, params=None, firstFrame=0, rowstart = 0, rowend = -1, columnstart =0, columnend = -1, subtract_burntin = False):
    '''
    Parameters
    ----------
    images : array
        4D array
    
    firstFrame : int
        which frame has the probe with atoms (earlier frames are thrown out)   
    '''
    if params:
        pixelsize=params.camera.pixelsize_microns*1e6
        magnification=params.magnification
    else:
        pixelsize=6.5e-6 #Andor Zyla camera
        magnification = 0.55 #75/125 (ideally) updated from 0.6 to 0.55 on 12/08/2022
    iteration, picsPerIteration, rows, cols = np.shape(images)
    columnDensities = np.zeros((iteration, rows, cols))
    Number_of_atoms = np.zeros((iteration))
    # subtracted = np.zeros((iteration, rows, cols))
    if params:
        pixelsize=params.camera.pixelsize_microns*1e6
        magnification=params.magnification
    else:
        pixelsize=6.5e-6 #Andor Zyla camera
        magnification = 0.55 #75/125 (ideally) updated from 0.6 to 0.55 on 12/08/2022    
    deltaX = pixelsize/magnification #pixel size in atom plane
    deltaY = deltaX
    for i in range(iteration):
        if (subtract_burntin):
            subtracted_array = images[i, firstFrame+1,:,:] - images[i, firstFrame,:,:]
        else:
            subtracted_array = images[i, firstFrame,:,:]
        columnDensities[i] = CountsToAtoms(params, subtracted_array)/deltaX/deltaY                                                                                       
        Number_of_atoms[i] = np.sum(columnDensities[i, rowstart:rowend, columnstart:columnend])*deltaX*deltaY
    return Number_of_atoms, columnDensities, deltaX, deltaY
   
     
#abs_img_data must be a 4d array
def absImagingSimple(abs_img_data, params=None, firstFrame=0, correctionFactorInput=1, 
                     rowstart=None, rowend=None, columnstart=None, columnend=None, subtract_burntin=False,
                     preventNAN_and_INF=True):
    """
    Assume that we took a picture of one spin state, then probe without atoms, then dark field
    In total, we assume three picture per iteration

    Parameters
    ----------
    images : array
        4D array
    
    firstFrame : int
        which frame has the probe with atoms (earlier frames are thrown out)
    Returns
    -------
    signal : array
        4D array, with one image per run of the experiment

    """
    iteration, picsPerIteration, rows, cols = np.shape(abs_img_data)
    
    ratio_array = np.zeros((iteration, rows, cols), dtype=np.float32)
    columnDensities = np.zeros((iteration, rows, cols))
    N_abs = np.zeros((iteration))
    Number_of_atoms = np.zeros((iteration))
    
    # if params:
    pixelsize=params.camera.pixelsize_microns*1e-6
    magnification=params.magnification
    # else:
    #     pixelsize=6.5e-6 #Andor Zyla camera
    #     magnification = 0.55 #75/125 (ideally) updated from 0.6 to 0.55 on 12/08/2022
        
    for i in range(iteration):
        # print("dimensions of the data for testing purposes:", np.shape(abs_img_data))
        # subtracted1 = abs_img_data[i,0,:,:] - abs_img_data[i,2,:,:]
        # subtracted2 = abs_img_data[i,1,:,:] - abs_img_data[i,2,:,:]
        if (subtract_burntin):
            subtracted1 = abs_img_data[i,firstFrame+1,:,:] - abs_img_data[i,firstFrame+0,:,:]  # with_atom - burnt_in
            subtracted2 = abs_img_data[i,firstFrame+2,:,:] - abs_img_data[i,firstFrame+3,:,:]  # no_atom - bg
        else:
            subtracted1 = abs_img_data[i,firstFrame+0,:,:] - abs_img_data[i,firstFrame+2,:,:]  # with_atom - bg
            subtracted2 = abs_img_data[i,firstFrame+1,:,:] - abs_img_data[i,firstFrame+2,:,:]  # no_atom - bg
        
        if (preventNAN_and_INF):
            #if no light in first image
            subtracted1[ subtracted1<= 0 ] = 1 
            subtracted2[ subtracted1<= 0 ] = 1
            
            #if no light in second image
            subtracted1[ subtracted2<= 0] = 1
            subtracted2[ subtracted2<= 0] = 1
            
        ratio = subtracted1 / subtracted2
        
        if correctionFactorInput:
            correctionFactor = correctionFactorInput
        else:
            correctionFactor = np.mean(ratio[-5:][:])
        
        # print("correction factor iteration", i+1, "=",correctionFactor)
        ratio /= correctionFactor #this is I/I0
        ratio_array[i] = ratio
        opticalDensity = -1 * np.log(ratio)
        N_abs[i] = np.sum(opticalDensity) 
        
        ###################
        # detuning = 2*np.pi*0 #how far from max absorption @231MHz. if the imaging beam is 230mhz then delta is -1MHz. unit is Hz
        # linewidth = 36.898e6 #units Hz
        # wavevector =2*np.pi/(671e-9) #units 1/m
        # cross_section = (3*np.pi / (wavevector**2)) * (1+(2*detuning/linewidth)**2)**-1 
        
        #####################
        cross_section = params.cross_section

        
        n2d = opticalDensity / cross_section
        #n2d[~np.isfinite(columnDensities)] = 0
        deltaX = pixelsize/magnification #pixel size in atom plane
        deltaY = deltaX
        Number_of_atoms[i] = np.sum(n2d[rowstart:rowend][columnstart:columnend]) * deltaX * deltaY
        # print("number of atoms iteration", i+1, ": ", Number_of_atoms[i]/1e6,"x10^6")
        columnDensities[i] = n2d
    
    print('Finish calculating columnDensities.')

    return Number_of_atoms, N_abs, ratio_array, columnDensities, deltaX, deltaY
    
    # iterations, picturesPerIteration, height, width = np.shape(images)
    
    # signal = np.zeros((iterations,1, height, width))
    
    # if picturesPerIteration==4:
    #     for i in range(iterations-1):
    #         # signal is column density along the imaging path
    #         signal[i,0,:,:] = (images[i,1,:,:] - images[i,3,:,:]) / (images[i,2,:,:] - images[i,3,:,:])
    # else:
    #     print("This spooled series does not have the correct number of exposures per iteration for Absorption Imaging")        
        
    # return signal
    
    
    
def absImagingSimpleV2(rawImgs, firstFrame=0, correctionFactorInput=1, 
                       rowstart=None, rowend=None, columnstart=None, columnend=None, 
                       subtract_burntin=False, preventNAN_and_INF=True):
    """
    Assume that we took a picture of one spin state, then probe without atoms, then dark field
    In total, we assume three picture per iteration

    Parameters
    ----------
    images : array
        4D array
    
    firstFrame : int
        which frame has the probe with atoms (earlier frames are thrown out)
    Returns
    -------
    signal : array
        4D array, with one image per run of the experiment

    """
    
    rawImgs = rawImgs.astype(np.float32)

    if subtract_burntin:
        subtracted1 = rawImgs[:, firstFrame+1, :, :] - rawImgs[:, firstFrame+0, :, :]  # with_atom - burnt_in
        subtracted2 = rawImgs[:, firstFrame+2, :, :] - rawImgs[:, firstFrame+3, :, :]  # no_atom - bg
    else:
        subtracted1 = rawImgs[:, firstFrame+0, :, :] - rawImgs[:, firstFrame+2, :, :]  # with_atom - bg
        subtracted2 = rawImgs[:, firstFrame+1, :, :] - rawImgs[:, firstFrame+2, :, :]  # no_atom - bg
    
    if preventNAN_and_INF:
        #set to 1 if no light in the first or second image 
        mask = (subtracted1 <= 0) # with_atom < 0
        subtracted1[ mask ] = 1
        
        mask = (subtracted2 <= 0) # no_aotm < 0
        subtracted1[ mask ] = 1
        subtracted2[ mask ] = 1
        
    ratio = subtracted1 / subtracted2
    
    if correctionFactorInput:
        correctionFactor = correctionFactorInput
    else:
        correctionFactor = np.mean(ratio[..., -5:, :])
    
    # print("correction factor iteration", i+1, "=",correctionFactor)
    ratio /= correctionFactor #this is I/I0
    opticalDensity = -1 * np.log(ratio)
    
    print('Finish calculating opticalDensity.')
    
    return opticalDensity



def integrate1D(array2D, dx=1, free_axis="y"):
    #free_axis is the axis that remains after integrating
    if free_axis == 'x':
        axis = 0
    elif free_axis == 'y':
        axis = 1
    array1D = np.sum(array2D, axis = axis)*dx
    return array1D


def Gaussian(x, amp, center, w, offset=0):
    return amp * np.exp(-0.5*(x-center)**2/w**2) + offset

def MultiGaussian(x, *params):
    L = len(params)        
    if  L % 3 != 1:
        raise ValueError('The number of parameters provided to MultiGaussian() besides x variable should be 3N+1, N is the number of Gaussian curves.')

    result = np.zeros(len(x))
    N = L//3
    
    for n in range(N):
        result += Gaussian(x, *params[n:-1:N])
        # print(params[n:-1:N])
    return result + params[-1]


def GaussianDistribution(x, mu, sigma):
    return np.exp( -(x-mu)**2 / (2*sigma**2) ) / ( sigma * np.sqrt(2*np.pi) )

def GaussianRing(r, r_mean, r_delta):
    # remove the 0 elements in r
    rp = r.copy()
    rp[r==0] = np.nan

    return GaussianDistribution(rp, r_mean, r_delta) / (2 * np.pi * rp)


def fitbg(data, signal_feature='narrow', signal_width=10, fitbgDeg=5): 
       
    datalength = len(data)
    signalcenter = data.argmax()
    datacenter = int(datalength/2)    
    xdata = np.arange(datalength)
    
    if signal_feature == 'wide':
        mask_hw = int(datalength/3)
        bg_mask = np.full(xdata.shape, True)
        bg_mask[signalcenter - mask_hw: signalcenter + mask_hw] = False  
        
        p = np.polyfit( xdata[bg_mask], data[bg_mask], deg=min(2, fitbgDeg) )        
        
    else:
        mask_hw = int(datalength/signal_width)
        bg_mask = np.full(xdata.shape, True)
        center_mask = bg_mask.copy()
        bg_mask[signalcenter - mask_hw: signalcenter + mask_hw] = False  
        center_mask[datacenter - mask_hw : datacenter + mask_hw] = False        
        bg_mask = bg_mask * center_mask
        bg_mask[:mask_hw] = True
        bg_mask[-mask_hw:] = True
        
        p = np.polyfit( xdata[bg_mask], data[bg_mask], deg=fitbgDeg )
    
    return np.polyval(p, xdata)
    
    
    
def fitgaussian1D(data , xdata=None, dx=1, doplot = False, 
                  subtract_bg=True, signal_feature='narrow', 
                  label="", title="", newfig=True, 
                  xlabel="", ylabel="", xscale_factor=1, legend=False,
                  yscale_factor=1):
    
    if subtract_bg:
        bg = fitbg(data, signal_feature=signal_feature) 
        originalData = data.copy()
        data = data - bg
        
        offset_g = 0
    else:
        offset_g = offset_g = min( data[:10].mean(), data[-10:].mean() )
    
    datalength = len(data)
    
    if xdata is None:
        xdata = np.arange( datalength )*dx  
        
    #initial guess:
    amp_g = data.max() - offset_g 
    center_g = xdata[ data.argmax() ]    
    w_g = ( data > (0.6*amp_g + offset_g) ).sum() * dx / 2
    
    guess = [amp_g, center_g, w_g, offset_g]
    
    try:
        popt, pcov = curve_fit(Gaussian, xdata, data, p0=guess, bounds=([-np.inf, -np.inf, 0, -np.inf],[np.inf]*4) )
    except Exception as e:
        print(e)
        return None  
 
    #      
    if doplot:
        if newfig:
            plt.figure()            
        if subtract_bg:                
            plt.plot(xdata*xscale_factor, originalData*yscale_factor, '.', label="{} data".format(label))
            plt.plot(xdata*xscale_factor, (Gaussian(xdata,*popt)+bg) * yscale_factor, label="{} fit".format(label))
            plt.plot(xdata*xscale_factor, bg*yscale_factor, '.', markersize=0.3)
            # ax.plot(xdata*xscale_factor, (Gaussian(xdata,*guess)+bg) * yscale_factor, label="{} fit".format(label))
        else:
            plt.plot(xdata*xscale_factor, data*yscale_factor, '.', label="{} data".format(label))
            plt.plot(xdata*xscale_factor, Gaussian(xdata,*popt) * yscale_factor, label="{} fit".format(label))

    if doplot:
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        if legend:
            plt.legend()
    return popt

def fitgaussian2(array, dx=1, do_plot = False, title="",xlabel1D="",ylabel1D="", vmax=None, 
                 xscale_factor=1, yscale_factor=1, legend=False, title2D="", new_figure=True,num_rows=1,row=0):
    if do_plot:
        plt.rcParams.update({'font.size' : 10})
        if new_figure:
            plt.figure(figsize=(8,1.9*num_rows))
        #plt.title(title)
        
    popts=[]
    for ind, ax in enumerate(["x","y"]):
        array1D = integrate1D(array,dx, free_axis=ax)
        if do_plot:
            plt.subplot(num_rows,3,ind+2 + 3*row)
        ylabel= ylabel1D if ind==0 else ""
        popt= fitgaussian1D(array1D, dx=dx, doplot=do_plot, label=ax, title=title+" vs "+ax, newfig=False,
                            xlabel=xlabel1D, ylabel=ylabel, xscale_factor=xscale_factor, 
                            yscale_factor=yscale_factor, legend=legend)
        popts.append(popt) 
    if do_plot:
        plt.subplot(num_rows,3,1+3*row)
        plt.imshow(array, cmap = 'jet',vmin=0,vmax=vmax)
        #plt.colorbar()
        plt.xlabel("pixels")
        plt.ylabel("pixels")
        plt.title(title2D)
        plt.tight_layout()
        
    return popts[0], popts[1]



def DetectPeaks(yy, xx=None, amp=1, width=3, denoise=0, doPlot=0):

    if xx is not None:
        x_unik = np.unique(xx)

        y_unik = []
        for x in x_unik:
            y_unik = xx[xx==x].mean()

        xx = x_unik
        yy = y_unik

    if denoise:
        yycopy = gaussian_filter1d(yy, 5)
    else:
        yycopy = yy.copy()

    # Determine the background with the otsu method and set to 0.
    # thr = threshold_otsu(yycopy)
    thr = 0.05 * (yy.max() - yy.min()) + yy.min()
    yycopy[yycopy < thr] = yy.min()

    peaks, properties = signal.find_peaks(yycopy, prominence=amp*0.01*(yycopy.max()-yycopy.min()), width=width)

    if xx is not None:
        peaks = xx[peaks]



    if doPlot:
        fig, ax = plt.subplots(1,1, layout='constrained')

        ymin = yy[peaks] - properties["prominences"]
        ymax = yy[peaks]
        amp = ymax - ymin
        xmin = properties["left_ips"]
        xmax = properties["right_ips"]
        width = (xmax - xmin) / 2
        ax.vlines(x=peaks, ymin=ymin, ymax=ymax, color = "C1")
        ax.hlines(y=properties["width_heights"], xmin=xmin, xmax=xmax, color = "C1")
        xx = np.arange(len(yy))
        ax.plot(xx, MultiGaussian(xx, *amp, *peaks, *width, yy.min()))
        ax.plot(yy, '--')
        ax.plot(yycopy, '.g')

    return peaks, properties


def fitSingleGaussian(data, xdata=None, dx=1, 
                      subtract_bg=0, signal_feature='wide', 
                      signal_width=10, fitbgDeg=5,
                                          ):
    
    if subtract_bg:
        bg = fitbg(data, signal_feature=signal_feature, signal_width=signal_width, fitbgDeg=fitbgDeg) 
        data = data - bg        
        offset = 0
    else:
        offset = min( data[:10].mean(), data[-10:].mean() )
        bg = None
        
    if xdata is None:
        xdata = np.arange( len(data) )
        
    #initial guess:
    amp = data.max() - offset
    center = xdata[ data.argmax() ]    
    w = ( data > (0.6*amp + offset) ).sum() / 2
    
    guess = [amp, center, w, offset]
    
    # if 1:
    #     plt.figure()
    #     plt.plot(xdata, data, '.')
    #     plt.plot(xdata, Gaussian(xdata,*guess))
    
    try:
        popt, _ = curve_fit(Gaussian, xdata, data, p0 = guess, bounds=([0, -np.inf, 0, -np.inf],[np.inf]*4) )
        
    except Exception as e:
        print(e)
        return None, None
    
    # if 1:
    #     plt.plot(xdata, Gaussian(xdata,*popt))
    
    popt[1:-1] *= dx
    

    
    return popt, bg
    

def fitMultiGaussian(data, xdata=None, dx=1, NoOfModel='auto', guess=[],
                     subtract_bg=0, signal_feature='wide', signal_width=10, fitbgDeg=5,
                     amp=1, width=3, denoise=0, peakplot=0):

    if subtract_bg:
        bg = fitbg(data, signal_feature=signal_feature, signal_width=signal_width, fitbgDeg=fitbgDeg)
        data = data - bg
        offset = 0
    else:
        offset = min( data[:10].mean(), data[-10:].mean() )
        bg = None

    if not guess:
        peaks, properties = DetectPeaks(data, xx=xdata, amp=amp, width=width, 
                                        denoise=denoise, doPlot=peakplot)
        
        #initial guess:
        amps = properties['width_heights'] + properties['prominences'] / 2
        widths = (properties['right_ips'] - properties['left_ips']) / 2

        N = len(peaks)
        # print(peaks)

        if NoOfModel != 'auto' and NoOfModel > N:
            D = NoOfModel - N
            N = NoOfModel
            amps = np.concatenate( (amps, [amps.mean()]*D) )
            peaks = np.concatenate( (peaks, [int(amps.mean()-20)]*D) )
            widths = np.concatenate( (widths, [int(widths.mean())]*D) )

        guess = [*amps, *peaks, *widths, offset]

    else:
        N = len(guess) // 3

    if xdata is None:
        xdata = np.arange( len(data) )

    try:
        # minamps = 0.1*(data.max()-data.min())
        minamps = 0
        popt, pcov = curve_fit(MultiGaussian, xdata, data, p0 = guess,
                            # bounds=([minamps]*N + [0]*N + [3]*N + [-np.inf], [np.inf]*(3*N+1))
                              )

    except Exception as e:
        print(e)
        return None, None, None

    popt[N:-1] *= dx

    return popt, pcov.diagonal()**0.5, bg


def fitgaussian1D_June2023(data , xdata=None, dx=1, doplot = False, ax=None, 
                           subtract_bg = True, signal_feature = 'wide', 
                           signal_width=10, fitbgDeg=5,
                           add_title = False, add_xlabel=False, add_ylabel=False, no_xticklabel=True,
                           label="", title="", newfig=True, xlabel="", ylabel="", 
                           xscale_factor=1, legend=False, yscale_factor=1):
    
    # datasmooth = gaussian_filter1d(data, 5)
    
    if subtract_bg:
        bg = fitbg(data, signal_feature=signal_feature, signal_width=signal_width, fitbgDeg=fitbgDeg) 
        originalData = data.copy()
        data = data - bg        
        offset_g = 0
    else:
        offset_g = min( data[:10].mean(), data[-10:].mean() )
    
    datalength = len(data)
    
    if xdata is None:
        xdata = np.arange( datalength ) * dx  
        
    #initial guess:
    amp_g = data.max() - offset_g
    center_g = xdata[ data.argmax() ]    
    w_g = ( data > (0.6*amp_g + offset_g) ).sum() * dx / 2
    
    guess = [amp_g, center_g, w_g, offset_g]
    
    try:
        popt, pcov = curve_fit(Gaussian, xdata, data, p0 = guess, bounds=([-np.inf, -np.inf, 0, -np.inf],[np.inf]*4) )
        
    except Exception as e:
        print(e)
        return None  
          
    if doplot:
        if subtract_bg:                
            ax.plot(xdata*xscale_factor, originalData*yscale_factor, '.', label="{} data".format(label))
            ax.plot(xdata*xscale_factor, (Gaussian(xdata,*popt)+bg) * yscale_factor, label="{} fit".format(label))
            ax.plot(xdata*xscale_factor, bg*yscale_factor, '.', markersize=0.3)
            ax.plot(xdata*xscale_factor, (Gaussian(xdata,*guess)+bg) * yscale_factor, label="{} fit".format(label))
        else:
            ax.plot(xdata*xscale_factor, data*yscale_factor, '.', label="{} data".format(label))
            ax.plot(xdata*xscale_factor, Gaussian(xdata,*popt) * yscale_factor, label="{} fit".format(label))
            ax.plot(xdata*xscale_factor, Gaussian(xdata,*guess) * yscale_factor, label="{} fit".format(label))
            
        ax.ticklabel_format(axis='both', style='sci', scilimits=(-3,3))
        ax.tick_params('y', direction='in', pad=-5)
        plt.setp(ax.get_yticklabels(), ha='left')
        
        if add_title:
            ax.set_title(title)
        if add_xlabel:
            ax.set_xlabel(xlabel)
        if add_ylabel:
            ax.set_ylabel(ylabel)            
        if no_xticklabel == True:
            ax.set_xticklabels([])
        if legend:
            ax.legend()
    return popt

#Modified from fitgaussian2, passing the handle for plotting in subplots. 
def fitgaussian2D(array, dx=1, do_plot=False, ax=None, fig=None, Ind=0, imgNo=1, 
                  subtract_bg = True, signal_feature = 'wide', 
                  signal_width=10, fitbgDeg=5,
                  vmax = None, vmin = 0,
                  title="", title2D="", 
                  xlabel1D="",ylabel1D="",
                  xscale_factor=1, yscale_factor=1, legend=False):
    
    add_title = False
    add_xlabel=False
    add_ylabel=False
    no_xticklabel=True
    
    if do_plot:
        if ax is None:#Create fig and ax if it is not passed.
            fig, ax = plt.subplots(1,3, figsize=(8,2))
            plt.rcParams.update({'font.size' : 10})
        else:
            plt.rcParams.update({'font.size' : 8})
        
        #Add colorbar
        im = ax[0].imshow(array, cmap = 'jet',vmin=vmin,vmax=vmax)
        if fig:
            divider = make_axes_locatable(ax[0])
            cax = divider.append_axes('right', size='3%', pad=0.05)
            fig.colorbar(im, cax=cax, orientation='vertical')
        
        if Ind == 0:
            ax[0].set_title(title2D)
            add_title = True            
        if Ind+1 == imgNo:
            ax[0].set_xlabel("pixels")
            add_xlabel = True
            no_xticklabel = False
        if Ind == int(imgNo/2):
            ax[0].set_ylabel("pixels")
            add_ylabel = True
        if no_xticklabel == True:
            ax[0].set_xticklabels([])
    else:
        ax = [None] * 3
        
    popts=[]
    for ind, axis in enumerate(["x","y"]):
        array1D = integrate1D(array, dx, free_axis=axis)        
        popt= fitgaussian1D_June2023(array1D, dx=dx, doplot=do_plot, ax=ax[ind+1], 
                                     subtract_bg = subtract_bg, signal_feature = signal_feature, 
                                     signal_width=signal_width, fitbgDeg=fitbgDeg,
                                     add_title = add_title, add_xlabel=add_xlabel, add_ylabel=add_ylabel, no_xticklabel=no_xticklabel,
                                     label=axis, title=title+" vs "+axis, newfig=False,
                                     xlabel=xlabel1D, ylabel=ylabel1D, xscale_factor=xscale_factor, 
                                     yscale_factor=yscale_factor, legend=legend)
        popts.append(popt) 
    return popts[0], popts[1]


def fitgaussian(array, params, do_plot = False, vmax = None,title="", 
                logTime=None, variableLog=None,
                count=None, variablesToDisplay=None, showTimestamp=False,
                save_column_density = False, column_density_xylim = None): 
    
    mag = params.magnification
    pixSize_um = params.camera.pixelsize_microns
    
    #np.sum(array, axis = 0) sums over rows, axis = 1 sums over columns
    rows = np.linspace(0, len(array), len(array))
    cols = np.linspace(0, len(array[0]), len(array[0]))
    row_sum = np.sum(array, axis = 0)  
    col_sum = np.sum(array, axis = 1)
    # print("rows = "+str(rows))
    # print("np.shape(array) = "+str(np.shape(array)))
    # print("np.shape(rows) = "+str(np.shape(rows)))
    # print("np.shape(cols) = "+str(np.shape(cols)))
    # print("np.shape(row_sum) = "+str(np.shape(row_sum)))
    # print("np.shape(col_sum) = "+str(np.shape(col_sum)))
    ampx = np.max(row_sum)
    centerx = np.argmax(row_sum)
    wx = len(rows)/3
    # offsetx = row_sum[0]
    ampy = np.max(col_sum)
    centery = np.argmax(col_sum)
    wy = len(cols)/120
    
    widthx, center_x, widthy, center_y = np.nan, np.nan, np.nan, np.nan
    try:
        poptx, pcovx = curve_fit(Gaussian, cols, row_sum, p0=[ampx, centerx, wx,0])
        widthx = abs(poptx[2])
        center_x = poptx[1]
        
    except RuntimeError as e:
        print(e)
        
    try:
        popty, pcovy = curve_fit(Gaussian, rows, col_sum, p0=[ampy, centery, wy,-1e13])
        widthy = abs(popty[2])
        center_y = popty[1]  
        
    except RuntimeError as e:
        print(e)


    widthx = widthx * pixSize_um / mag
    widthy = widthy * pixSize_um / mag


    if do_plot:
        #see the input array
        plt.rcParams.update({'font.size' : 10})
        plt.figure(figsize=(12,5))
        plt.subplot(121)
        if vmax == None:
            vmax = array.max()
        
        plt.imshow(array, cmap = 'jet',vmin=0,vmax=vmax)
        
        if variablesToDisplay and logTime:
            variablesToDisplay = [ii.replace(' ','_') for ii in variablesToDisplay]
            plt.text(0,0,
                     variableLog.loc[logTime[count]][variablesToDisplay].to_string(name=showTimestamp).replace('Name','Time'), 
                     fontsize=7, ha='left', va='top',
                     bbox=dict(boxstyle="square", ec=(0,0,0), fc=(1,1,1), alpha=0.9))
        
        if column_density_xylim == None:
            column_density_xylim = np.zeros(4)
            # column_density_xylim[1] = len(array[0])
            # column_density_xylim[3] = len(array)
            column_density_xylim[1], column_density_xylim[3] = array.shape[1::-1]
            
        print("column_density_xylim = "+str(column_density_xylim))
        column_density_xylim = np.array(column_density_xylim)
        if column_density_xylim[1] == -1:
                column_density_xylim[1] = len(array[0])
        if column_density_xylim[3] == -1:
                column_density_xylim[3] = len(array) 
        # plt.xlim(column_density_xylim[0], column_density_xylim[1])
        # plt.ylim(column_density_xylim[3], column_density_xylim[2])
        plt.title(title)
        plt.colorbar(pad = .1)
        if save_column_density:
            plt.savefig(title + ".png", dpi = 600)
        #plot the sum over columns
        #plt.figure()
        plt.subplot(122)
        #plt.title("col sum (fit in x direction)")
        plt.plot(cols, row_sum, label="data_vs_x")
        
        plt.xlabel("pixel index")
        plt.ylabel("sum over array values")
        #plot the sum over rows
        #plt.figure()
        #plt.title("row sum (fit in y direction)")
        plt.plot(rows, col_sum, label="data vs y")
        
        plt.xlabel("pixel index")
        plt.ylabel("sum over array values")
        plt.tight_layout()
        plt.legend()
    
        plt.plot(cols, Gaussian(cols, *[ampx, centerx, wx,0]), label="guess vs x")
        plt.plot(rows, Gaussian(rows, *[ampy, centery, wy,0]), label="guess vs y")  
        plt.legend()
        
        if not np.isnan(widthx):
            plt.plot(cols, Gaussian(cols, *poptx), label="fit vs x")
            plt.legend()
            plt.tight_layout()
        if not np.isnan(widthy):
            plt.plot(rows, Gaussian(rows, *popty), label="fit vs y")  
            plt.legend()
            plt.tight_layout()

        plt.tight_layout()
        
    return widthx, center_x, widthy, center_y






def AxesFit(img, center=None, sigma=1, doplot=0):

    if center:
        x0, y0 = center
    else:
        y0, x0 = DetectPeak2D(img, sigma=5, thr=0.7, doplot=0, usesmoothedimg=1)

    ly, lx = img.shape
    x = np.arange(lx) - x0
    y = np.arange(ly) - y0

    mask = GaussianDistribution(y, 0, sigma).reshape(-1, 1)
    xax = (img * mask).sum(axis=0)

    mask = GaussianDistribution(x, 0, sigma).reshape(1, -1)
    yax = (img * mask).sum(axis=1)

    xmax, ymax = xax.max(), yax.max()
    xwid = (xax > xmax/2).sum() / 2
    ywid = (yax > ymax/2).sum() / 2

    poptx, pcovx = curve_fit(Gaussian, x, xax, p0=[xax.max(), 0, xwid, 0])
    popty, pcovy = curve_fit(Gaussian, y, yax, p0=[yax.max(), 0, ywid, 0])

    if doplot:
        fig, axes = plt.subplots(1, 2, figsize=(10, 5))
        axes[0].plot(x, xax)
        axes[0].plot(x, Gaussian(x, *poptx))
        axes[1].plot(y, yax)
        axes[1].plot(y, Gaussian(y, *popty))

    return poptx[-2], popty[-2]



def AzimuthalAverage(img, radialRange=3, sigma=1, do_plot=0, plotRate=0.3):

    shape = img.shape
    y0, x0 = DetectPeak2D(img, sigma=5, thr=0.7, doplot=0, usesmoothedimg=1)

    a, b = AxesFit(img, center=(x0, y0))

    x = np.arange(shape[1]) - x0
    y = np.arange(shape[0]) - y0
    xx, yy = np.meshgrid(x, y)
    r = np.sqrt(xx**2 + (yy*a/b)**2)

    r_min = 3 * sigma
    r_max = min(radialRange*a, np.sqrt((shape[1]/2)**2 + (shape[0]*a/b/2)**2)-3*sigma)

    # Calculate the value at the center 
    mask = GaussianDistribution(xx, 0, sigma) * GaussianDistribution(yy, 0, sigma * b/a)
    result0 = (img * mask).sum() / mask.sum()
    # / (GaussianDistribution(xx, x0, sigma).sum() * GaussianDistribution(yy, y0, sigma * b/a).sum())
    # result0 = img[r<r_min].mean()

    result = [ result0 ]

    r_range = np.arange(r_min, r_max, 1)

    for rr in r_range:
        mask = GaussianRing(r, rr, sigma)
        img_masked = img * mask
        result.append( np.nansum(img_masked) / np.nansum(mask) )

        if do_plot and (np.random.rand() <= plotRate):
            fig, ax = plt.subplots(1, 1, figsize=(6, 4))
            ax.imshow(img, cmap='gray')
            alpha = np.nan_to_num(mask, nan=0) / np.nan_to_num(mask, nan=0).max()
            ax.imshow(mask, alpha=alpha, cmap='viridis')
            plt.show()

    return np.insert(r_range, 0, 0), np.array(result)




def plotRadialAtomDensity(r, y, dx=3.85, ax=None, linestyle='.', ms=3, addAxieLabel=1):

    # Input r is in the unit of pixel, convert to length in μm
    r = r * dx
    # Input y is in atom # per m^2, convert to # per μm^2
    y = y / 1e6**2
    
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(6, 4), layout='constrained')
    ax.plot(r, y, linestyle, ms=ms)
    if addAxieLabel:
        ax.set(xlabel='r (μm)', ylabel='atom/μm^2')    
    
    


def plotImgAndFitResult(imgs, popts, bgs=[], imgs2=None, 
                        filterLists=[],
                        fitFunc=MultiGaussian, axlist=['y', 'x'], dx=1,
                        plotRate=1, plotPWindow=5, figSizeRate=1, fontSizeRate=1, 
                        uniformscale=0, addColorbar=1,
                        variableLog=None, variablesToDisplay=[], logTime=None, showTimestamp=False,
                        textLocationY=1, textVA='bottom', 
                        xlabel=['pixels', 'position (µm)', 'position (µm)'],
                        ylabel=['pixels', '1d density (atoms/µm)', ''],
                        title=[], sharex='col', sharey='col',
                        rcParams={'font.size': 10, 'xtick.labelsize': 9, 'ytick.labelsize': 9}): 
    
    rcParams0 = plt.rcParams # Store the original plt params
    plt.rcParams.update({'image.cmap': 'jet'})

    
    axDict = {'x': 0, 'y':1}

    N = len(popts)
    
    if filterLists:
        variableLog, items = DataFilter(variableLog, imgs, *popts, *bgs, logTime, imgs2, filterLists=filterLists)
        imgs, popts, bgs, logTime, imgs2 = items[0], items[1: N+1], items[N+1:], items[-2], items[-1]
    if imgs2 is not None:
        imgShow = imgs2
        if not title:
            title=['Optical Density', '1D density vs ', '1D density vs ']
    else:
        imgShow = imgs
        if not title:
            title=['Column Density', '1D density vs ', '1D density vs ']

    imgNo = len(imgs)    
    
    if plotRate < 1:
        mask = np.random.rand(imgNo) < plotRate
        imgs = imgs[mask]
        imgShow = imgShow[mask]
        imgNo = mask.sum()
        
        popts = list(popts)
        for n in range(N):
            popts[n] = np.array(popts[n])[mask]
            if bgs and bgs[0] is not None:
                bgs[n] = np.array(bgs[n])[mask]            
    
    oneD_imgs = []
    xx = []
    xxfit = []
        
    if variablesToDisplay and logTime is None:
        logTime = variableLog.index
    
    for n in range(N): # loop through the axes provided
        oneD = np.nansum(imgs, axis=axDict[axlist[n]] + 1 ) * dx / 1e6**2 # dx is in micron
        L = len(oneD[0]) # the length of the x-axis of the 1-D plot
        oneD_imgs.append(oneD)
        xx.append(np.arange(0, L) * dx)
        xxfit.append(np.arange(0, L, 0.1) * dx)
        title[n+1] += axlist[n]
        
    if uniformscale:
        # vmax = imgShow.max()
        vmax = uniformscale
    else:
        vmax = None
        
    for ind in range(imgNo):
        #Creat figures
        plotInd = ind % plotPWindow
        if plotInd == 0:
            plotNo = min(plotPWindow, imgNo-ind)
            fig, axes = plt.subplots(plotNo , N+1, figsize=(figSizeRate*3*(N+1), figSizeRate*1.5*plotNo), 
                                     squeeze = False, sharex=sharex, sharey=sharey, layout="constrained")
            for n in range(N+1):
                axes[-1, n].set_xlabel(xlabel[n])
                axes[int(plotNo/2), n].set_ylabel(ylabel[n])
                axes[0, n].set_title(title[n])
        
        #Plot the Images
        im = axes[plotInd, 0].imshow(imgShow[ind], vmin=0, vmax=vmax)
        if addColorbar:
            divider = make_axes_locatable(axes[plotInd, 0])
            cax = divider.append_axes('right', size='3%', pad=0.05)
            fig.colorbar(im, cax=cax, orientation='vertical')
               
        for n in range(N):
            axes[plotInd, n+1].plot(xx[n], oneD_imgs[n][ind], '.', markersize=3)
            if popts[n][ind] is not None:
                if bgs is not None and bgs[n] is not None and bgs[n][0] is not None:
                    axes[plotInd, n+1].plot(xx[n], fitFunc(xx[n], *popts[n][ind]) + bgs[n][ind])
                    axes[plotInd, n+1].plot(xx[n], bgs[n][ind], '.', markersize=0.3)
                else:
                    axes[plotInd, n+1].plot(xxfit[n], fitFunc(xxfit[n], *popts[n][ind]))
            
            
            axes[plotInd, n+1].ticklabel_format(axis='both', style='sci', scilimits=(-3,3))
            axes[plotInd, n+1].tick_params('y', direction='in', pad=-5)
            plt.setp(axes[plotInd, n+1].get_yticklabels(), ha='left')
            
        if variablesToDisplay and variableLog is not None:
                        
            variablesToDisplay = [ii.replace(' ','_') for ii in variablesToDisplay]
            
#             print('='*20)
#             print(variableLog.loc[logTime[ind]][variablesToDisplay])
#             print('='*20)
            
            axes[plotInd,0].text(-0.05, textLocationY, 
                            variableLog.loc[logTime[ind]][variablesToDisplay].to_string(name=showTimestamp).replace('Name','Time'), 
                            fontsize=5*fontSizeRate, ha='left', va=textVA, transform=axes[plotInd,0].transAxes, 
                            bbox=dict(boxstyle="square", ec=(0,0,0), fc=(1,1,1), alpha=0.7))
        
    plt.rcParams = rcParams0 # Revert the plt params 



def AnalyseFittingResults(poptsList, ax=['Y', 'X'], logTime=None, 
                          columns=['center', 'width', 'atomNumber']):
    
    resutsList = []
    for ii, popts in enumerate(poptsList):    
        results = []
        for p in popts:
            center, width, atomNumber = [np.nan] * 3
            
            if p is not None:
                N = len(p) // 3
                amp = p[0:N]
                center = p[N:2*N]
                width = p[2*N:3*N]
                atomNumber = (amp * width * (2*np.pi)**0.5).sum()
                if N == 1:
                    center = center[0]
                    width = width[0]               
                    # amp = amp[0]
    
            results.append([center, width, atomNumber])
        
        # columns =         
        resutsList.append( pd.DataFrame(results, index=logTime, columns=[ax[ii].upper() + jj for jj in columns]) )

    return pd.concat(resutsList, axis=1).rename_axis('time')


def fit2Lines(x, ys, xMean, y1Mean, y2Mean, pointsForGuess=3):
    mergingPoint = ( np.array([ len(ii) for ii in ys ]) < 2 ).argmax()
    if mergingPoint > 0 and mergingPoint < pointsForGuess:
        pointsForGuess = mergingPoint
        
    # Initial guess
    x1 = xMean[:pointsForGuess]
    p1 = np.poly1d( np.polyfit(x1, y1Mean[:pointsForGuess], deg=1) )
    p2 = np.poly1d( np.polyfit(x1, y2Mean[:pointsForGuess], deg=1) )
    
    x1 = []
    y1 = []
    y2 = []
    for ii in range(len(x)):
        if len( ys[ii] ) < 2:
            continue
        
        xi = x[ii]
        yi1, yi2 = ys[ii]
        pi1, pi2 = p1(xi), p2(xi)
        
        d1 = max(abs(yi1-pi1), abs(yi2-pi2)) 
        d2 = max(abs(yi1-pi2), abs(yi2-pi1)) 
        
        if d2 < d1:
            yi1, yi2 = yi2, yi1
        
        x1.append(xi)
        y1.append(yi1)
        y2.append(yi2)
    
    
    p1 = np.poly1d( np.polyfit(x1, y1, deg=1) )
    p2 = np.poly1d( np.polyfit(x1, y2, deg=1) )
    
    if abs(p1[0]) > abs(p2[0]):
        p1, p2 = p2, p1
        y1, y2 = y2, y1
    return p1, p2, y1, y2

def odtMisalign(df,
                rcParams={'font.size': 10, 'xtick.labelsize': 9, 'ytick.labelsize': 9}): 
    plt.rcParams.update(rcParams)
    df = df.sort_values(by='ODT_Misalign')
    
    xx = df.center_Basler.values
    df = df.join([df.Ycenter.apply(min).rename('y1'), df.Ycenter.apply(max).rename('y2')])

    dfMean = df.groupby('ODT_Misalign').mean()
    dfStd = df.groupby('ODT_Misalign').std(ddof=0)

    xxMean = dfMean.center_Basler.values
    y1Mean = dfMean.y1.values
    y2Mean = dfMean.y2.values
    
    p1, p2, y1group, y2group = fit2Lines(xx, df.Ycenter.values, xxMean, y1Mean, y2Mean )
    root = np.roots(p1 - p2)[0]

    df = df.join( pd.DataFrame({'y1group': y1group, 'y2group': y2group} , index=df.index), rsuffix='r' )
    dfMean = df.groupby('ODT_Misalign').mean()
    dfStd = df.groupby('ODT_Misalign').std(ddof=0)

    xxfit = np.arange(xx.min(), xx.max())
    fig, ax = plt.subplots(1,1, figsize=(8,6), layout="constrained")
    N = 5
    ax.plot(xxfit, np.polyval(p1, xxfit), label='first pass')
    ax.plot(xxfit, np.polyval(p2, xxfit), label='second pass')
    ax.errorbar(dfMean.center_Basler, dfMean.y1group, N*dfStd.y1group, N*dfStd.center_Basler, ls='', color='r')
    ax.errorbar(dfMean.center_Basler, dfMean.y2group, N*dfStd.y2group, N*dfStd.center_Basler, ls='', color='r')
    ax.text(0.05,0.01, 'First pass y = {:.2f}\n'.format(np.mean(y1group))
            + 'Cross at   x = {:.2f}\n'.format(root)
            + 'std for x: {}\n'.format(np.round(dfStd.center_Basler.values, 2))
            + 'std for y: {}\n'.format(np.round(dfStd.y1group.values, 2))
            + '               {}\n'.format(np.round(dfStd.y2group.values, 2)), 
            va='bottom', transform=ax.transAxes, fontsize=8)
    ax.set_xlabel('Position On Basler Camera')
    ax.set_ylabel('Position On Zyla Camera')
    ax.legend()
    print('Coordinates for aligning:\n{:.3f}, {:.3f}'.format(np.mean(y1group), root))
    
def odtAlign(df, expYcenter, expCenterBasler, repetition=1, 
             rcParams={'font.size': 10, 'xtick.labelsize': 9, 'ytick.labelsize': 9}): 
    plt.rcParams.update(rcParams)
    df = df.reset_index()
    dfMean = df.groupby(df.index//repetition).mean()
    dfStd = df.groupby(df.index//repetition).std(ddof=0) 
    
    cols = ['Ycenter', 'YatomNumber', 'center_Basler', 'Ywidth']
    
    x = dfMean.index
    y = dfMean[cols]
    yErr = dfStd[cols]

    expected = [expYcenter, None, expCenterBasler, None]
    fig, axes = plt.subplots(2, 2, figsize=(10,6), sharex=True, layout="constrained")
        
    for ii, ax in enumerate(axes.flatten()):
        ax.errorbar(x, y[cols[ii]], yErr[cols[ii]])
        ax.set_ylabel(y[cols[ii]].name)
        if cols[ii] == 'YatomNumber':
            formatstr = '{:.2e}\n'
        else: 
            formatstr = '{:.2f}\n'
        ax.text(0.01,0.98, 'Latest value:    ' + formatstr.format(y[cols[ii]].iloc[-1]), 
                va='top', transform=ax.transAxes)
        ax.text(0.01,0.9, 'Average Value: ' + formatstr.format(y[cols[ii]].mean()),
                va='top', transform=ax.transAxes)        
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-3,5))
        if expected[ii]:
            ax.axhline(y=expected[ii], ls='--', color='g')
            yrange = max(2*y[cols[ii]].std(ddof=0), 1.5 * np.abs(expected[ii] - y[cols[ii]].iloc[-1]))
            ax.set(ylim=[expected[ii]-yrange, expected[ii]+yrange])

   

def CalculateFromZyla(dayFolderPath, dataFolders, variableLog=None, 
                      repetition=1, examNum=None, examFrom=None, 
                      plotRate=0.2, plotPWindow=5, uniformscale=0, 
                      variablesToDisplay=[], variableFilterList=None, 
                      showTimestamp=False, pictureToHide=None,
                      subtract_bg=True, signal_feature='narrow', signal_width=10,
                      rowstart=30, rowend=-30, columnstart=30, columnend=-30,
                      angle_deg= 2, #rotates ccw
                      subtract_burntin=0, 
                      lengthFactor=1e-6
                      ):    
    
    dataFolderPaths = [ os.path.join(dayFolderPath, f) for f in dataFolders ]
    examFrom, examUntil = GetExamRange(examNum, examFrom, repetition)
    
    picturesPerIteration = 4 if subtract_burntin else 3    
    params = ExperimentParams(t_exp = 10e-6, picturesPerIteration= picturesPerIteration, cam_type = "zyla")
    images_array = None
    NoOfRuns = []
    
    for ff in dataFolderPaths:
        if images_array is None:
            images_array, fileTime = LoadSpooledSeries(params = params, data_folder = ff, 
                                                                       return_fileTime=1)
            NoOfRuns.append(len(fileTime))
        else:
            _images_array, _fileTime = LoadSpooledSeries(params = params, data_folder = ff, 
                                                                           return_fileTime=1)
            images_array = np.concatenate([images_array, _images_array], axis=0)
            fileTime = fileTime + _fileTime
            NoOfRuns.append(len(_fileTime))
    
    images_array = images_array[examFrom: examUntil]
    fileTime = fileTime[examFrom: examUntil]
    
    dataFolderindex = []
    [ dataFolderindex.extend([dataFolders[ii].replace(' ','_')] * NoOfRuns[ii]) for ii in range(len(NoOfRuns)) ]
    dataFolderindex = dataFolderindex[examFrom: examUntil]
    
    logTime = Filetime2Logtime(fileTime, variableLog)
        
    if variableFilterList and variableLog is not None:    
        filteredList = VariableFilter(logTime, variableLog, variableFilterList)
        images_array = np.delete(images_array, filteredList, 0)
        dataFolderindex = np.delete(dataFolderindex, filteredList, 0)
        logTime = np.delete(logTime, filteredList, 0)
            
    if pictureToHide:
        images_array = np.delete(images_array, pictureToHide, 0)
        dataFolderindex = np.delete(dataFolderindex, pictureToHide, 0)
        if logTime:
            logTime = np.delete(logTime, pictureToHide, 0)
    
    # ImageAnalysisCode.ShowImagesTranspose(images_array)
    Number_of_atoms, N_abs, ratio_array, columnDensities, deltaX, deltaY = absImagingSimple(images_array, 
                    firstFrame=0, correctionFactorInput=1.0,  
                    subtract_burntin=subtract_burntin, preventNAN_and_INF=True)
    
    imgNo = len(columnDensities)
    print('{} images loaded.'.format(imgNo))
        
    results = []
    
    #Generate the list for plot based on the total image # and the set ploting ratio
    plotList = np.arange(imgNo)[np.random.rand(imgNo) < plotRate]
    plotNo = len(plotList)
    plotInd = 0
    
    axs = [None] 
    axRowInd = 0
    axRowNo = None
    
    if uniformscale:
        vmax = columnDensities.max()
        vmin = columnDensities.min()
    else:
        vmax = None
        vmin = 0
   
    for ind in range(imgNo):
        
        # do_plot = 1 if ind in plotList else 0
        
        if ind in plotList:
            do_plot = 1
        else: do_plot = 0
        
        if do_plot:
            axRowInd = plotInd % plotPWindow #The index of axes in one figure
            if axRowInd == 0:
                # if ind//plotPWindow>0:
                #     fig.tight_layout()
                axRowNo = min(plotPWindow, plotNo-plotInd) #The number of rows of axes in one figure
                fig, axs = plt.subplots(axRowNo , 3, figsize=(3*3, 1.8*axRowNo), squeeze = False, layout="constrained")
                # plt.subplots_adjust(hspace=0.14, wspace=0.12)
            plotInd += 1
            
        rotated_ = rotate(columnDensities[ind], angle_deg, reshape = False)[rowstart:rowend,columnstart:columnend]
        # rotated_=columnDensities[ind]
        if ind==0: #first time
            rotated_columnDensities =np.zeros((imgNo, *np.shape(rotated_)))
        rotated_columnDensities[ind] = rotated_
    
        #preview:
        dx=params.camera.pixelsize_meters/params.magnification
        
        popt0, popt1 = fitgaussian2D(rotated_columnDensities[ind], dx=dx, 
                                                      do_plot = do_plot, ax=axs[axRowInd], Ind=axRowInd, imgNo=axRowNo,
                                                      subtract_bg = subtract_bg, signal_feature = signal_feature, signal_width=signal_width,
                                                      vmax = vmax, vmin = vmin,
                                                      title="1D density", title2D="column density",
                                                      xlabel1D="position (µm)", ylabel1D="1d density (atoms/µm)",                                                  
                                                      xscale_factor=1/lengthFactor, yscale_factor=lengthFactor)
        
        if do_plot and variableLog is not None:
            variablesToDisplay = [ii.replace(' ','_') for ii in variablesToDisplay]
            axs[axRowInd,0].text(0,1,
                                 'imgIdx = {}'.format(ind) + '\n'
                            + variableLog.loc[logTime[ind]][variablesToDisplay].to_string(name=showTimestamp).replace('Name','Time'), 
                            fontsize=5, ha='left', va='top', transform=axs[axRowInd,0].transAxes, 
                            bbox=dict(boxstyle="square", ec=(0,0,0), fc=(1,1,1), alpha=0.7))
                
        if popt0 is None:
            center_x, width_x, atomNumberX = [np.nan] * 3
        else:            
            amp_x, center_x, width_x, _ = popt0
            atomNumberX = amp_x * width_x * (2*np.pi)**0.5            
        if popt1 is None:
            center_y, width_y, atomNumberY = [np.nan] * 3
        else:                    
            amp_y, center_y, width_y, _ = popt1
            atomNumberY = amp_y * width_y * (2*np.pi)**0.5
        
        convert = 1e6
        results.append([center_y*convert, width_y*convert, atomNumberY, 
                        center_x*convert, width_x*convert, atomNumberX])
            
    df = pd.DataFrame(results, index=logTime,
                      columns=['Ycenter', 'Ywidth', 'AtomNumber', 'Xcenter', 'Xwidth', 'AtomNumberX'
                               ]
                      ).rename_axis('time')
    df.insert(0, 'Folder', dataFolderindex)
    
    if variableLog is not None:
        # variableLog = variableLog.loc[logTime]
        df = df.join(variableLog)
    
    return df


def DataFilter(dfInfo, *otheritems, filterLists=[]):   
    '''
    
    Parameters
    ----------
    info : TYPE
        DESCRIPTION.
    *filterLists : list of strings
        Lists of the filter conditions. Each condition should be in the form of 
        'ColumName+operator+value'. No spaces around the operator. Condtions
        will be conbined by logic or, and filters in different lists will be 
        conbined by logic and. 
    imgs : TYPE, optional
        DESCRIPTION. The default is None.

    Returns
    -------
    TYPE
        DESCRIPTION.

    '''
    # If the len of Lists is 0, return the input data.
    if len(filterLists) == 0:
        if otheritems:
            return dfInfo, otheritems
        else:
            return dfInfo
    
    masks = []
    # Loop through the Lists.
    for fltlist in filterLists:
        if len(fltlist) == 0:
            continue
        
        # For flts in one list, use logic and to the results and appedn to masks. 
        maskAnd = []
        for flt in fltlist:              
            maskAnd.append(eval( '(dfInfo.' + flt.replace(' ', '_') + ').values' ))   
                
        for mask in maskAnd[1:]:
            maskAnd[0] &= mask
        masks.append(maskAnd[0])
        
    # If the len of masks if 0, return the input data.        
    if len(masks) == 0:
        if otheritems:
            return dfInfo, otheritems
        else:
            return dfInfo
    
    # Take logic or among the masks. 
    # masks = masks.values() # Convert masks from df to np array.

    for mask in masks[1:]:
        masks[0] |= mask
    
    # Apply the mask to the other items if any. 
    if otheritems:
        otheritems = list(otheritems)
        for ii, item in enumerate(otheritems):
            if item is not None:
                try:
                    otheritems[ii] = np.array(item)[masks[0]]
                except:
                    # otheritems[ii] = np.array(item, dtype=object)[masks[0]]
                    otheritems[ii] = [item[jj] for jj in range(len(item)) if masks[0][jj]]
            
        return dfInfo[masks[0]], otheritems
    else:
        return dfInfo[masks[0]]



def FilterByOr(df, filterLists):
    
    masks = []
    for flts in filterLists:
        masklist = []
        for flt in flts:
            masklist.append(eval( 'df.' + flt.replace(' ', '_') ))   
           
        if len(masklist) > 1:
            for mask in masklist[1:]:
                masklist[0] |= mask
        masks.append(masklist[0])
        
    if len(masks) > 1:
        for mask in masks[1:]:
            mask[0] &= mask
    return df[ mask[0] ]



def PlotFromDataCSV(df, xVariable, yVariable, filterLists=[],
                    groupby=None, groupbyX=0, iterateVariable=None,
                    do_fit = 0,
                    figSize=1, legend=1, legendLoc=0,
                    threeD=0, viewElev=30, viewAzim=-45):
    '''
    

    Parameters
    ----------
    df : DataFrame
        Pandas dataframe from CalculateFromZyla or loaded from a saved data file.
    xVariable : str
        The name of the variable to be plotted as the x axis. It should be the 
        name of a column of the dataframe.
    yVariable : str
        The name of the variable to be plotted as the y axis. It should be the 
        name of a column of the dataframe.
    groupby : str, default: None
        The name of a dataframe column. If it is assigned, the data points will be
        averaged based on the values of this column, and the plot will be an
        errorbar plot.
    groupbyX : boolean, default: 0
        The name of a dataframe column. If it is true, the data points will be
        averaged based for each x value, and the plot will be an errorbar plot.
    iterateVariable : str, default: None
        The name of a dataframe column. If it is assigned, the plot will be divided
        into different groups based on the values of this column.        
    filterByAnd : list of strings, default: []
        A list of the filter conditions. Each condition should be in the form of 
        'ColumName+operator+value'. No spaces around the operator. Different condtions
        will be conbined by logic and. 
    filterByOr : list of strings, default: []
        A list of the filter conditions. Each condition should be in the form of 
        'ColumName+operator+value'. No spaces around the operator. Different condtions
        will be conbined by logic or. 
    filterByOr2 : list of strings, default: []
        The same as filterByOr, but a logical and will be performed for the 
        results of filterByOr2 and filterByOr.    
    threeD : boolean, default: 0
        Plot a 3-D line plot if set to True. 
    viewElev : float, default: 30
        The elevation angle of the 3-D plot. 
    viewAzim : float, default: -45
        The azimuthal angle of the 3-D plot. 

    Raises
    ------
    FileNotFoundError
        DESCRIPTION.

    Returns
    -------
    fig, ax.

    '''
    
    warnings.warn("PlotFromDataCSV will retire, use PlotResults!", DeprecationWarning, stacklevel=2)
        
    # if not os.path.exists(filePath):
    #     raise FileNotFoundError("The file does not exist!")
    
    # df = pd.read_csv(filePath)
    df = df[ ~np.isnan(df[yVariable]) ]
    df = DataFilter(df, filterLists=filterLists)
    
    columnlist = [xVariable, yVariable]
    
    if iterateVariable:
        iterateVariable.replace(' ', '_')
        iterable = df[iterateVariable].unique()
        iterable.sort()
        columnlist.append(iterateVariable)
    else:
        iterable = [None]
        threeD = 0
    
    if groupby == xVariable or groupbyX:
        groupbyX = 1  
        groupby = xVariable
    if groupby and not groupbyX:
        groupby.replace(' ', '_')
        columnlist.append(groupby)
    
    if threeD:
        fig, ax = plt.subplots(figsize=(9*figSize, 9*figSize), subplot_kw=dict(projection='3d'), layout='constrained')
        ax.view_init(elev=viewElev, azim=viewAzim)
    else:
        fig, ax = plt.subplots(figsize=(10*figSize, 8*figSize), layout='constrained')
    
    for ii in iterable:
        if ii is None:
            dfii = df[columnlist]
        else:
            dfii = df[columnlist][ (df[iterateVariable]==ii) ]
        
        label = '{} = {}'.format(iterateVariable, ii)
            
        if do_fit:                
            xdata = dfii[xVariable]
            p = np.polyfit(xdata, dfii[yVariable], 1)
            xx = np.linspace(xdata.min(), xdata.max(), 30)
            ax.plot(xx, np.polyval(p, xx), '.', ms=2)
            # ax.text(0.02, 0.99, 
            #           'slope: {:.3e}'.format(p[0]),
            #           ha='left', va='top', transform=ax.transAxes)
            print(label + ', slope {}'.format(p[0]))

            label += ', slope: {:.3e}'.format(p[0])
            


            
        if groupby:
            dfiimean = dfii.groupby(groupby).mean()
            dfiistd = dfii.groupby(groupby).std(ddof=0)
            
            yMean = dfiimean[yVariable]
            yStd = dfiistd[yVariable]
            
            if groupbyX:
                xMean = dfiimean.index
                xStd = None
            else:
                xMean = dfiimean[xVariable]
                xStd = dfiistd[xVariable]
            
            if threeD:
                ax.plot3D( [ii]*len(xMean), xMean, yMean, label=label)                
            else:
                ax.errorbar(xMean, yMean, yStd, xStd, capsize=3, label=label) 
                #plt.scatter(xMean, yMean, s=8)
        else:
            ax.plot( dfii[xVariable], dfii[yVariable], '.', label=label)
            
    if threeD:
        ax.set(xlabel=iterateVariable, ylabel=xVariable, zlabel=yVariable)
        ax.ticklabel_format(axis='z', style='sci', scilimits=(-3,3))
    else:
        ax.set(xlabel=xVariable, ylabel=yVariable)
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-3,3))
    if iterateVariable and legend:
        plt.legend(loc=legendLoc)
    plt.show()
    
    return fig, ax


def PlotResults(df, xVariable, yVariable, filterLists=[],
                groupby=None, groupbyX=0, iterateVariable=None,
                do_fit = 0,
                figSize=1, legend=1, legendLoc=0,
                threeD=0, viewElev=30, viewAzim=-45):
    '''
    

    Parameters
    ----------
    df : DataFrame
        Pandas dataframe from CalculateFromZyla or loaded from a saved data file.
    xVariable : str
        The name of the variable to be plotted as the x axis. It should be the 
        name of a column of the dataframe.
    yVariable : str
        The name of the variable to be plotted as the y axis. It should be the 
        name of a column of the dataframe.
    groupby : str, default: None
        The name of a dataframe column. If it is assigned, the data points will be
        averaged based on the values of this column, and the plot will be an
        errorbar plot.
    groupbyX : boolean, default: 0
        The name of a dataframe column. If it is true, the data points will be
        averaged based for each x value, and the plot will be an errorbar plot.
    iterateVariable : str, default: None
        The name of a dataframe column. If it is assigned, the plot will be divided
        into different groups based on the values of this column.        
    filterByAnd : list of strings, default: []
        A list of the filter conditions. Each condition should be in the form of 
        'ColumName+operator+value'. No spaces around the operator. Different condtions
        will be conbined by logic and. 
    filterByOr : list of strings, default: []
        A list of the filter conditions. Each condition should be in the form of 
        'ColumName+operator+value'. No spaces around the operator. Different condtions
        will be conbined by logic or. 
    filterByOr2 : list of strings, default: []
        The same as filterByOr, but a logical and will be performed for the 
        results of filterByOr2 and filterByOr.    
    threeD : boolean, default: 0
        Plot a 3-D line plot if set to True. 
    viewElev : float, default: 30
        The elevation angle of the 3-D plot. 
    viewAzim : float, default: -45
        The azimuthal angle of the 3-D plot. 

    Raises
    ------
    FileNotFoundError
        DESCRIPTION.

    Returns
    -------
    fig, ax.

    '''
    
        
    # if not os.path.exists(filePath):
    #     raise FileNotFoundError("The file does not exist!")
    
    # df = pd.read_csv(filePath)
    df = df[ ~np.isnan(df[yVariable]) ]
    df = DataFilter(df, filterLists=filterLists)
    
    columnlist = [xVariable, yVariable]
    
    if iterateVariable:
        iterateVariable.replace(' ', '_')
        iterable = df[iterateVariable].unique()
        iterable.sort()
        columnlist.append(iterateVariable)
    else:
        iterable = [None]
        threeD = 0
    
    if groupby == xVariable or groupbyX:
        groupbyX = 1  
        groupby = xVariable
    if groupby and not groupbyX:
        groupby.replace(' ', '_')
        columnlist.append(groupby)
    
    if threeD:
        fig, ax = plt.subplots(figsize=(9*figSize, 9*figSize), subplot_kw=dict(projection='3d'), layout='constrained')
        ax.view_init(elev=viewElev, azim=viewAzim)
    else:
        fig, ax = plt.subplots(figsize=(10*figSize, 8*figSize), layout='constrained')
    
    for ii in iterable:
        if ii is None:
            dfii = df[columnlist]
        else:
            dfii = df[columnlist][ (df[iterateVariable]==ii) ]
        
        label = '{} = {}'.format(iterateVariable, ii)
            
        if do_fit:                
            xdata = dfii[xVariable]
            p = np.polyfit(xdata, dfii[yVariable], 1)
            xx = np.linspace(xdata.min(), xdata.max(), 30)
            ax.plot(xx, np.polyval(p, xx), '.', ms=2)
            # ax.text(0.02, 0.99, 
            #           'slope: {:.3e}'.format(p[0]),
            #           ha='left', va='top', transform=ax.transAxes)
            print(label + ', slope {}'.format(p[0]))

            label += ', slope: {:.3e}'.format(p[0])
            


            
        if groupby:
            dfiimean = dfii.groupby(groupby).mean()
            dfiistd = dfii.groupby(groupby).std(ddof=0)
            
            yMean = dfiimean[yVariable]
            yStd = dfiistd[yVariable]
            
            if groupbyX:
                xMean = dfiimean.index
                xStd = None
            else:
                xMean = dfiimean[xVariable]
                xStd = dfiistd[xVariable]
            
            if threeD:
                ax.plot3D( [ii]*len(xMean), xMean, yMean, label=label)                
            else:
                ax.errorbar(xMean, yMean, yStd, xStd, capsize=3, label=label, marker='o') 
                #plt.scatter(xMean, yMean, s=8)
        else:
            ax.plot( dfii[xVariable], dfii[yVariable], '.', label=label)
            
    if threeD:
        ax.set(xlabel=iterateVariable, ylabel=xVariable, zlabel=yVariable)
        ax.ticklabel_format(axis='z', style='sci', scilimits=(-3,3))
    else:
        ax.set(xlabel=xVariable, ylabel=yVariable)
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-3,3))
    if iterateVariable and legend:
        plt.legend(loc=legendLoc)
    plt.show()
    
    return fig, ax

    

def temperature_model(t, w0, T):
    #I define the constants explicitly since this function is passed to curve fit
    kB = 1.38e-23 #Boltzmann's constant
    m = 9.988341e-27 #Li-6 mass in kg    
    t0 = 0
    model = w0*np.sqrt(   1 +       (kB/m)*abs(T)*(t-t0)**2/(w0**2)   )
    # model = w0*np.sqrt((kb*T*(t-t0)**2)/(m*w0**2))
    return model

# def temperature_fit(params, widths_array, tof_array,label="",do_plot=False, ax=None):
#     #Inputs: params object, widths in meters, times in seconds
#     #Optional: label like "x" or "y"
    
#     min_time = min(tof_array)
#     max_time = max(tof_array)
#     min_width = min(widths_array)
#     max_width = max(widths_array)
    
#     #remove Nans and Infs
#     good_indexes = np.isfinite(widths_array)
#     tof_array = tof_array[good_indexes]
#     widths_array = widths_array[good_indexes]
    
#     w0guess = min_width
#     slope = (max_width-min_width)/(max_time-min_time)
#     Tguess = (slope)**2*params.m/params.kB 
#     popt, pcov = curve_fit(temperature_model, tof_array, widths_array, p0 = [w0guess, Tguess])
#     times_fit = np.linspace(min_time, max_time, 100)
#     widths_fit = temperature_model(times_fit, popt[0], popt[1])
    
#     if (do_plot):
#         #plot the widths vs. position
#         if ax is None:
#             plt.figure(figsize=(3,2))
#             plt.title("{} T = {:.2f} uK".format(label, popt[1]*1e6))
#             plt.xlabel("Time of flight (ms)")
#             plt.ylabel("width of atom cloud (um)")
#             plt.scatter(1e3*tof_array, 1e6*widths_array)
#             plt.plot(1e3*times_fit, 1e6*widths_fit)
#             plt.tight_layout()
#         else:
#             ax.set(title="{} T = {:.3g} uK".format(label, popt[1]*1e6), 
#                    xlabel='Time of flight (ms)',
#                    ylabel="width of atom cloud (um)")
#             ax.scatter(1e3*tof_array, 1e6*widths_array)
#             ax.plot(1e3*times_fit, 1e6*widths_fit)
#         # if data_folder:
#         #     plt.savefig(data_folder+r'\\'+"temperature x.png", dpi = 500)
    
#     return tof_array, times_fit, widths_fit, popt, pcov

def temperature_fit(params, widths_array, tof_array, label="", do_plot=False, ax=None):
    good_indexes = np.isfinite(widths_array)
    tof_array = tof_array[good_indexes]
    widths_array = widths_array[good_indexes]
   
    w0guess = min(widths_array)
    slope = (max(widths_array)-min(widths_array))/(max(tof_array)-min(tof_array))
    Tguess = (slope)**2 * params.m / params.kB
   
    popt, pcov = curve_fit(temperature_model, tof_array, widths_array, p0=[w0guess, Tguess])
    perr = np.sqrt(np.diag(pcov))

    # fit arrays
    times_fit = np.linspace(min(tof_array), max(tof_array), 100)
    widths_fit = temperature_model(times_fit, *popt)
   
    if do_plot:
        plot_df = pd.DataFrame({'tof': tof_array, 'width': widths_array})
        stats = plot_df.groupby('tof')['width'].agg(['mean', 'std']).reset_index()
       
        ax.errorbar(stats['tof']*1e3, stats['mean']*1e6, yerr=stats['std']*1e6,
                    fmt='o', capsize=3, color='black', ecolor='gray', markersize=4)
        ax.plot(times_fit*1e3, widths_fit*1e6, color='red', lw=1.2)
       
        ax.set_title(f"$T = {popt[1]*1e6:.2f} \pm {perr[1]*1e6:.2f}$ $\mu$K", fontsize=10)
        ax.set(xlabel='TOF (ms)', ylabel="Width ($\mu$m)")
   
    return tof_array, times_fit, widths_fit, popt, pcov, perr

 
def thermometry(params, images, tof_array, do_plot = False, data_folder = None):
    widthsx = np.zeros(len(images))
    widthsy = np.zeros(len(images))
    #fill arrays for widths in x and y directions
    for index, image in enumerate(images):
        widthsx[index], x, widthsy[index], y  = fitgaussian(image)
        widthsx[index] = widthsx[index]*params.camera.pixelsize_meters/params.magnification
        widthsy[index] = widthsy[index]*params.camera.pixelsize_meters/params.magnification
        if index == 0:
            print("widthx = "+str(widthsx[index]*1e6)+" um")
            print("widthy = "+str(widthsy[index]*1e6)+" um")
    #these plots will still show even if the fit fails, but the plot underneath the fit will not     
    # if (do_plot):
    #     plt.figure()
    #     plt.xlabel("Time of flight (ms)")
    #     plt.ylabel("1/e^2 width x of atom cloud (uncalibrated units)")
    #     plt.scatter(tof_array, widthsx)
        
    #     plt.figure()
    #     plt.xlabel("Time of flight (ms)")
    #     plt.ylabel("1/e^2 width y of atom cloud (uncalibrated units)")
    #     plt.scatter(tof_array, widthsy)        
        
    fitx_array, plotx_array, fitx, poptx, pcovx = temperature_fit(params, widthsx, tof_array)
    fity_array, ploty_array, fity, popty, pcovy = temperature_fit(params, widthsy, tof_array)
    if (do_plot):
        #plot the widths vs. position along x direction
        plt.figure()
        plt.title("Temperature fit x, T = {} uK".format(poptx[1]*1e6))
        plt.xlabel("Time of flight (ms)")
        plt.ylabel("width of atom cloud (um)")
        plt.scatter(1e3*tof_array, 1e6*widthsx)
        plt.plot(1e3*plotx_array, 1e6*temperature_model(plotx_array, *poptx))   
        if data_folder:
            plt.savefig(data_folder+r'\\'+"temperature x.png", dpi = 500)
        #plot the widths vs. position along y direction
        plt.figure()
        plt.title("Temperature Fit y, T = {} µK".format(popty[1]*1e6))
        plt.xlabel("Time of Flight (ms)")
        plt.ylabel("Width of Atom Cloud (µm)")
        plt.scatter(1e3*tof_array, 1e6*widthsy)
        plt.plot(1e3*ploty_array, 1e6*temperature_model(ploty_array, *popty)) 
        if data_folder:
            plt.savefig(data_folder+r'\\'+"temperature y.png", dpi = 500)        
    return poptx, pcovx, popty, pcovy
   
def thermometry1D(params, columnDensities, tof_array, thermometry_axis="x", 
                  do_plot = False, save_folder = None, reject_negative_width=False,
                  newfig=True):
    #1. Find cloud size (std dev) vs time
    widths=[]
    times=[]
    numbers=[]
    dx = params.camera.pixelsize_meters/params.magnification
    for index, density2D in enumerate(columnDensities):
        density1D = integrate1D(density2D, dx=dx, free_axis=thermometry_axis)
        xdata = np.arange(np.shape(density1D)[0])*dx
        popt_gauss  = fitgaussian1D(density1D,xdata,dx=dx, doplot=True, xlabel=thermometry_axis, ylabel="density")
        if popt_gauss is not None: #fit succeeded
            if popt_gauss[2] >0 or not reject_negative_width:
                w = abs(popt_gauss[2])
                widths.append(w)
                times.append(tof_array[index])
                numbers.append(popt_gauss[0]* w*(2*np.pi)**0.5 ) #amp  = N/(w*(2*np.pi)**0.5)
    numbers=np.array(numbers)
    widths=np.array(widths)
    times=np.array(times)       
    #2. Fit to a model to find temperature    
    # fitx_array, plotx_array, fit, popt, pcov = temperature_fit(params, widths, times)
    try:
        tof_array, times_fit, widths_fit, popt, pcov = temperature_fit(params, widths, times)
    except RuntimeError:
        popt = None
        pcov = None
        
    if (do_plot):
        #plot the widths vs. time
        if newfig:
            plt.figure()
        plt.rcParams.update({'font.size': 14})
        AxesAndTitleFont = 20
        if popt is not None:
            plt.title("{0}: T = {1:.2f} µK".format(thermometry_axis, popt[1]*1e6), fontsize = AxesAndTitleFont)
            plt.plot(1e3*times_fit, 1e6*widths_fit, color = 'blue', zorder =1)
        plt.xlabel("Time of Flight (ms)", fontsize = AxesAndTitleFont)
        plt.ylabel("Std. dev (µm)", fontsize = AxesAndTitleFont)
        plt.scatter(tof_array/1e-3, widths/1e-6, color = 'red', zorder = 2)
        
        
        plt.tight_layout()
        if save_folder:
            plt.savefig(save_folder+r'\\'+"temperature {}.png".format(thermometry_axis), dpi = 300)
        # plt.figure()
        # plt.plot(1e3*tof_array, numbers,'o')
        # plt.xlabel("Time of flight (ms)")
        # plt.ylabel("Atom number")
        # plt.title("Atom Number {}".format(thermometry_axis))
        plt.tight_layout()
        if save_folder:
            plt.savefig(save_folder+r'\\'+"atom number {}.png".format(thermometry_axis), dpi = 300)
    return popt, pcov

    
def multiVariableThermometry(df, *variables, fitXVar='TOF', fitYVar='Ywidth',
                             atomNum='YatomNumber', sigma1='Xwidth', sigma2='Ywidth', sigma3='Ywidth',
                             do_plot=1, add_Text=1):
    '''
    Parameters
    ----------
    df : TYPE
        DESCRIPTION.
    *variables : strings
        The variables changed during the measurement. Accept multiple variables. 
    fitXVar : TYPE, optional
        The x-axis for the plot. The default is 'TOF' for thermometry measurement.
    fitYVar : TYPE, optional
        DESCRIPTION. The default is 'Ywidth'.
    atomNum : TYPE, optional
        DESCRIPTION. The default is 'YatomNumber'.
    sigma1 : TYPE, optional
        The width of the atom clould along the 1st axis. The default is 'Xwidth'.
    sigma2 : TYPE, optional        
        The width of the atom clould along the 2nd axis. The default is 'Ywidth'.
    sigma3 : TYPE, optional
        The width of the atom clould along the 3rd axis. The default is 'Ywidth'.
    do_plot : TYPE, optional
        DESCRIPTION. The default is 1.
    add_Text : TYPE, optional
        DESCRIPTION. The default is 1.

    Returns
    -------
    None.

    '''
        
    params = ExperimentParams( t_exp = 10e-6, picturesPerIteration= 4, cam_type = "zyla")
    df = df.select_dtypes(include=np.number)
    
    dfmean = df.groupby(list(variables) + [fitXVar]).mean()
    
    df1 = dfmean[fitYVar].unstack()    

    if do_plot:
        runNo = []
        for ii in range(df1.index.nlevels):
            runNo.append(len(df1.index.get_level_values(ii).unique()))
            
        runNo = np.prod( runNo )

        arrange, sizes = PlotArangeAndSize(runNo)
        fig, axes = plt.subplots(*arrange,
                                 # figsize=sizes,
                                 layout='constrained', squeeze = False,
                                 sharex=True, sharey=True)
        axes = axes.flatten()
        
    T = []
    # A = []
    
    for ii, (ind, item) in enumerate( df.groupby(list(variables)) ):
        
        ax = axes[ii] if do_plot else None
        # print('=====', ii)

        # print('=====', item)
        _,_,_,popt,_= temperature_fit(params,
                                      item[fitYVar]*1e-6, 
                                      item[fitXVar]*1e-3, 
                                      do_plot=1, ax=ax)
        
        if do_plot and add_Text:
            ax.text(0.03, 0.95, '{}\n= {}'.format(variables, tuple(round(x,3) for x in ind)), ha='left', va='top', transform=ax.transAxes)
            # ax.text(0, 20, 'T (uK): {:.3f}'.format(popt[1]*1e6), ha='left', va='top')

        T.append( popt[1] )
        # A.append( list( item[ item[fitXVar] == item[fitXVar].min() ][atomNum] ) )
    
    df1['T (K)'] = T
    # df1['AtomNum'] = A
        
    df2 = dfmean.reset_index(level=fitXVar)
    df2 = df2[df2[fitXVar] == df2[fitXVar].min()]
    
    Amean = df2[atomNum]
    s1 = df2[sigma1] * 2**0.5 / 1e6
    s2 = df2[sigma2] / 1e6
    s3 = df2[sigma3] / 1e6
    
#     print(PhaseSpaceDensity(a, s1, s2, s3, df1.T))
    df1['AtomNum'] = Amean
    df1['PSD'] = PhaseSpaceDensity(Amean, s1, s2, s3, df1['T (K)'])
    df1['Size1'] = s1
    df1['Size2'] = s2

    return df1

    
def PhaseSpaceDensity(atomNum, sigma1, sigma2, sigma3, T):
    waveLengthCubed = constants.h**3 / (2 * np.pi * 9.9883414e-27 * constants.k * T)**1.5
    
    # assume ellipsoidal volume in ODT
    Vol = 4/3 * np.pi * sigma1 * sigma2 * sigma3
    # return  waveLengthCubed * atomNum / (sigma1 * sigma2 * sigma3 * (2*np.pi)**1.5)
    return  waveLengthCubed * atomNum / Vol




def exponential(x, a, tau, c):
    return a * np.exp(-x/tau) + c    

def fit_exponential(xdata, ydata ,dx=1, doplot = False, label="", title="", 
                    newfig=True, xlabel="",ylabel="", offset = None, legend=False):
    

    #fit for the parameters a , b, c
    a = max(ydata) - min(ydata)
    tau = (max(xdata)-min(xdata))/2
    c = min(ydata)
    xfit = np.linspace(min(xdata),max(xdata), 1000)
    
    if offset is None:
        func = exponential
        guess= [a,tau,c]
        label = 'fit: a=%5.3f, tau=%5.3f, c=%5.3f'
    else:
        func = lambda x,a,tau: exponential(x,a,tau,offset)
        guess = [a,tau]
        label = 'fit: a=%5.2e\n tau=%5.3e\n c={:.2e} (Fixed)'.format(offset)
        
    popt, pcov = curve_fit(func, xdata, ydata, p0=guess, maxfev=5000)       

    #poptarray([2.56274217, 1.37268521, 0.47427475])
    plt.figure()
    plt.plot(xdata, ydata,'o')
    plt.plot(xfit, func(xfit, *popt), 'r-', label= label % tuple(popt))

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if legend:
        plt.legend()
    plt.tight_layout()
    plt.show()
    return popt, pcov
    
    
def twobodyloss(t, k, c):
    return (k*t+c)**-1    

def fit_2bodyloss(xdata, ydata ,dx=1, doplot = False, label="", title="", 
                    newfig=True, xlabel="",ylabel="", offset = None):
    

    #fit for the parameters a , b, c
    k = 2 / (max(xdata)-min(xdata))
    c = max(ydata)
    xfit = np.linspace(min(xdata),max(xdata), 1000)
    
    if offset is None:
        func = twobodyloss
        guess= [k,c]
        label = 'fit: k=%5.3f, c=%5.3f'
    else:
        func = lambda t,k,c: twobodyloss(t,k,offset)
        guess = [k,c]
        label = 'fit: k=%5.3f, c={:.3f} (Fixed)'.format(offset)
        
    popt, pcov = curve_fit(func, xdata, ydata, p0=guess)       
    
    #poptarray([2.56274217, 1.37268521, 0.47427475])
    plt.plot(xfit, func(xfit, *popt), 'r-', label= label % tuple(popt))

    plt.xlabel('Time (seconds)')
    plt.ylabel('Number of atoms')
    plt.legend()
    plt.show()    
    



def CircularMask(array, centerx = None, centery = None, radius = None):
    rows, cols = array.shape[-2:]
    
    if centerx == None:
        centerx = int(cols/2)
    if centery == None:
        centery = int(rows/2)
    if radius == None:
        radius = min(centerx, centery, cols-centerx, rows-centery)
    y, x = np.ogrid[-centery:rows-centery, -centerx:cols-centerx]
    mask = x*x + y*y <= radius*radius
    
    arraycopy = array.copy()
    arraycopy[..., ~mask] = 0
    
    return arraycopy, arraycopy.max()

def Plot_2Dscan(df, scanVar1, scanVar2, dependentVar):
   
    fig, ax = plt.subplots(figsize=(8,6))
   
    for val2, group in df.groupby(scanVar2):
        # ax.scatter(group[scanVar1], group[dependentVar], marker='o', label=f'{scanVar2}={val2}')
        ax.plot(group[scanVar1], group[dependentVar], 'o', label=f'{scanVar2}={val2:.2f}')

       
    ax.set_xlabel(scanVar1)
    ax.set_ylabel(dependentVar)
    ax.legend()

#%% Maximilliano
from PIL import Image

def CheckFile(file):
    if isinstance(file, str) and file.endswith('.png'):  
        arr = np.array(Image.open(file).convert('L'))
        
    elif isinstance(file, np.ndarray):
        arr = file
        
    elif isinstance(file, str) and file.endswith('.raw'):
        temp = np.fromfile(file, dtype = np.uint8)
        arr = np.reshape(temp, (2160,3840)) # Basler dart resolution
        
    elif isinstance(file, str) and file.endswith('.pgm'):
        img = Image.open(file)
        arr = np.asarray(img, dtype=np.uint16)
        rows, cols = np.shape(arr)
        rows2discard = 2
        arr = arr[rows2discard:, :]    
    else:
        raise ValueError(f"Unsupported file type or input: {file}")
    
    return arr



def GetImages(dataPath_list, camera, ROI, metadata=None):
    
    imgs = []
    
    if camera == 'Andor':
        # for Andor files, remove first 40 bytes
        headerbytes = 40
        height = metadata[0]
        width = metadata[1]
        
        binFile = [f for f in dataPath_list if f.lower().endswith('.dat')]
        
        for path in binFile:
            with open(path, 'rb') as f:
                f.seek(headerbytes)
                img_data = np.frombuffer(f.read(), dtype=np.uint16)
            
            expectedsize = height*width
            if img_data.size != expectedsize:
                raise ValueError(f'has {img_data.size} pixels, but expected {expectedsize}')
    
            imgArr = img_data.reshape((height,width))
            imgArr = imgArr[ROI[0]:ROI[1], ROI[2]:ROI[3]]
            
            imgs.append(imgArr)
            
    else:
        for file in dataPath_list:
            imgArr = CheckFile(file)
            imgArr = imgArr[ROI[0]:ROI[1], ROI[2]:ROI[3]]

            imgs.append(imgArr)

    return imgs



def GetFullFilePaths(dataPath_list):

    fullpath = []
    for folder in dataPath_list:
        folder = folder+'/'
        
        for filename in os.listdir(folder):
            
            path = folder+filename
            fullpath.append(path)
    
    return fullpath


def ExtractMetaData(filePaths):

    metaFile = next( (f for f in filePaths if f.lower().endswith('.ini')), None)
    
    if metaFile is None:
        raise FileNotFoundError('No metadata file found')
        return None
        
    
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(metaFile, encoding='utf-8-sig')
    
    
    height = int(config['data']['AOIHeight'])
    width = int(config['data']['AOIWidth'])
    pixFormat = config['data']['PixelEncoding']
    if pixFormat.lower() == 'mono16':
        dataType = np.uint16
    
    pixNumber = height*width
    
    return height, width, pixNumber, pixFormat, dataType


def Rotate(image_arr, deg):
    import cv2

    height, width = image_arr.shape[:2]
    
    center = (width / 2, height / 2)
    
    rotationMatrix = cv2.getRotationMatrix2D(center, deg, 1.0)
    rotated = cv2.warpAffine(image_arr, rotationMatrix, (width, height))
    
    return rotated, rotationMatrix


def Gauss1D(x,xc,sigX,A, offset):
    G = A * np.exp(-2 * (x-xc)**2 / sigX**2) + offset
    return G


def FitGaussian(gaussImageFile, graph=True, graphOption='Wide'):
    
    beam = CheckFile(gaussImageFile)
    Ny, Nx = beam.shape
    x_index = np.linspace(0, Nx-1, Nx)
    y_index = np.linspace(0, Ny-1, Ny)
    
    max_index = np.unravel_index(np.argmax(beam), beam.shape)
    max_x, max_y = max_index

    vert = beam[:, max_y]
    horiz = beam[max_x, :]
    
    sigGuess = 40
    offset = 0
    
    guessX = [max_y, sigGuess, np.max(horiz), offset]
    paramX,_ = curve_fit(Gauss1D, x_index, horiz, p0=guessX)
    paramX[1] = np.abs(paramX[1]) # ensure positive width
    x_fit1 = np.linspace(0, Nx-1, 5000)
    y_fit1 = Gauss1D(x_fit1, paramX[0], paramX[1], paramX[2], paramX[3])

    guessY = [max_x, sigGuess, np.max(vert), offset]
    paramY,_ = curve_fit(Gauss1D, y_index, vert, p0=guessY)
    paramY[1] = np.abs(paramY[1])
    x_fit2 = np.linspace(0,Ny-1, 5000)
    y_fit2 = Gauss1D(x_fit2, paramY[0], paramY[1], paramY[2], paramY[3])
    
    centerX = int(paramX[0])
    centerY = int(paramY[0])
            
    if graph:
        fig, ax = plt.subplots(1,3)
        
        ax[1].plot(x_fit1, y_fit1,'r',linewidth=3)
        ax[1].scatter(x_index, horiz, s=20)
        ax[1].set_title('Fit vs. X')
        
        text_x = f"x0 = {int(paramX[0])} \nσ = {paramX[1]:.2f} px \nA = {paramX[2]:.2f}"
        ax[1].text(0.35, 0.95, text_x, transform=ax[1].transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(facecolor='white', alpha=0.8))
        
        ax[2].plot(x_fit2,y_fit2,'r',linewidth=3)
        ax[2].scatter(y_index, vert, s=20)
        ax[2].set_title('Fit vs. Y')
        
        text_y = f"y0 = {int(paramY[0])} \nσ = {paramY[1]:.2f} px \nA = {paramY[2]:.2f}"
        ax[2].text(0.05, 0.95, text_y, transform=ax[2].transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(facecolor='white', alpha=0.8))
        
        if graphOption == 'Narrow':
            
            ax[1].set_xlim(paramX[0]-4*paramX[1], paramX[0]+4*paramX[1])
            ax[2].set_xlim(paramY[0]-4*paramY[1], paramY[0]+4*paramY[1])
            
            ax[0].imshow(beam, extent=[paramX[0]-1, 
                                       paramX[0]+1, 
                                       paramY[0]-1, 
                                       paramY[0]+1])
        else:
            # ax[0].imshow(beam*-1,cmap='binary')
            ax[0].imshow(beam,cmap='jet')
        
        ax[0].set_title('Image')        
    return paramX, paramY


def FitGaussianWaist(stats, colsForAnalysis, doPlot=True):
    
    
    def w_z(z, w0, z0):
        zR = np.pi * w0**2 / 1064e-9
        return w0 * np.sqrt(1 + ((z - z0) / zR)**2)
    
    popts = []
    pcovs = []
    
    # assumes distances in mm, waist in um
    for col in colsForAnalysis:
        z = stats['Distance'].values
        w_meas = stats[col+'_mean'].values
        w_err = stats[col+'_std'].values
        
        p0 = [min(w_meas), z[np.argmin(w_meas)]]
        
        popt, pcov = curve_fit(w_z, z, w_meas, p0=p0, sigma=w_err, absolute_sigma=True)
        popts.append(popt)
        pcovs.append(pcov)
        
        w0_fit, z0_fit = popt
        perr = np.sqrt(np.diag(pcov))
        
        if doPlot:
            z_fit = np.linspace(min(z), max(z), 1000)
            fig, ax = plt.subplots(figsize=(4,3))
            ax.errorbar(z*1e3, w_meas*1e6, yerr=w_err*1e6, fmt='o', capsize=3)
            ax.plot(z_fit*1e3, w_z(z_fit, *popt)*1e6, 'r-')
            ax.set_xlabel('Distance (mm)')
            ax.set_ylabel(col+' (μm)')
            ax.text(0.3, 0.85, f'w0={w0_fit*1e6:.2f} μm\nz0={z0_fit*1e3:.2f} mm', transform=ax.transAxes, bbox=dict(facecolor='white'))
            plt.tight_layout()
    
    return popts, pcovs
            
            
def RecognizeCommonPhrase(dataPathList, repetition):
    
    # pattern_both = re.compile(r'(?:(\d+(?:\.\d+)?)\s*mm).*?power\s*(\d+)$', re.IGNORECASE)
    pattern_both = re.compile(r"(?:(\d+(?:\.\d+)?)\s*mm).*?power\s*(\d+(?:\.\d+)?)$", re.IGNORECASE)

    

    pattern_distance_only = re.compile(r'(\d+(?:\.\d+)?)\s*mm', re.IGNORECASE)

    conditions = []
    values = []
    distances = []

    for name in dataPathList:
        basename = os.path.basename(name)

        match_both = pattern_both.search(basename)
        match_dist = pattern_distance_only.search(basename)

        if match_both:
            distance = float(match_both.group(1))
            value = float(match_both.group(2))
            condition = re.sub(pattern_both, '', basename).strip()
        elif match_dist:
            distance = float(match_dist.group(1))
            value = np.nan
            condition = re.sub(pattern_distance_only, '', basename).strip()
        else:
            distance = np.nan
            value = np.nan
            condition = basename.strip()

        conditions.extend([condition] * repetition)
        values.extend([value] * repetition)
        distances.extend([distance] * repetition)
    
    return conditions, values, distances


def multi_gaussian_sum(x, *params):
    # params = [A1, mu1, sigma1, offset1, A2, mu2, sigma2, offset2 ...]
    n = len(params) // 4
    y = np.zeros_like(x, dtype=float)
    
    for i in range(n):
        A = params[4*i]
        mu = params[4*i + 1]
        sigma = params[4*i + 2]
        offset = params[4*i + 3]
        y += A * np.exp(-(x - mu)**2 / (2 * sigma**2)) + offset
    
    return y


def GetSlices(ImageArray):
    max_index = np.unravel_index(np.argmax(ImageArray), ImageArray.shape)
    max_x, max_y = max_index

    vertSlice = ImageArray[:, max_y]
    horizSlice = ImageArray[max_x, :]
    
    return horizSlice, vertSlice



def Plot_2Dscan_Errbars(df, scanVar1, scanVar2, dependentVar, depVarScale=1):
    '''
    Description
    -----------
    Plots with error bars the dependentVar vs scanVar1 for each value of scanVar2 given
    '''
    fig,ax = plt.subplots(figsize=(5,4))
   
    stats = df.groupby([scanVar1, scanVar2])[dependentVar].agg(['mean','std']).reset_index()
   
    for val2, group in stats.groupby(scanVar2):
        ax.errorbar(group[scanVar1], group['mean']*depVarScale, yerr=group['std'],
                    marker='o', label=f'{scanVar2}={val2:.2f}', capsize=3)
   
    ax.set_xlabel(scanVar1)
    ax.set_ylabel(dependentVar)
    # ax.legend(loc='upper right')
    ax.legend()
    ax.grid(True,alpha=0.3)
    plt.tight_layout()



def FilterDataframe(df, col1, threshold, col2=None):
    
    condition = np.abs(df[col1]) <= threshold
    
    if col2 is not None:
        condition = condition & (df[col2] <= threshold)
    
    return df[condition]


# def saveResultsDF(results, dayfolder):
    
#     parentPath = os.path.join(dayfolder, 'Andor')
    
#     for folder_name, subDF in results['zyla'].groupby('Folder'):
#         pkl_path = os.path.join(parentPath, folder_name, 'results.pkl')
#         subDF.to_pickle(pkl_path)


def saveResultsDF(df, dayfolder, save_pickle=False, save_csv=True):
    """
    Saves each folder's subset of a DataFrame into its folder,
    asks user before saving or overwriting.
    """
    
    parentPath = os.path.join(dayfolder, 'Andor')

    for folder_name, subDF in df.groupby('Folder'):

        # Ask if results should be saved
        print(f"\nFolder: {folder_name}")
        choice = input("Do you want to save results for this folder? (y/n): ").strip().lower()

        if choice != "y":
            print("Skipping...")
            continue

        # Make sure the folder exists
        os.makedirs(folder_name, exist_ok=True)

        # PICKLE
        if save_pickle:
            pkl_path = os.path.join(parentPath, folder_name, "results.pkl")

            # Check if file exists
            if os.path.exists(pkl_path):
                overwrite = input(f"{pkl_path} already exists. Overwrite? (y/n): ").strip().lower()
                if overwrite != "y":
                    print("Not overwriting.")
                else:
                    subDF.to_pickle(pkl_path)
                    print(f"Saved: {pkl_path}")
            else:
                subDF.to_pickle(pkl_path)
                print(f"Saved: {pkl_path}")

        # CSV
        if save_csv:
            csv_path = os.path.join(parentPath, folder_name, "results.csv")

            if os.path.exists(csv_path):
                overwrite = input(f"{csv_path} already exists. Overwrite? (y/n): ").strip().lower()
                if overwrite != "y":
                    print("Not overwriting.")
                else:
                    subDF.to_csv(csv_path, index=False)
                    print(f"Saved: {csv_path}")
            else:
                subDF.to_csv(csv_path, index=False)
                print(f"Saved: {csv_path}")
                
                

def PhaseSpaceDensity_AspectRatio(atomNum, sigmaY, aspectRatio, T):
    waveLengthCubed = constants.h**3 / (2 * np.pi * MASS * constants.k * T)**1.5
    
    s1 = sigmaY
    s2 = sigmaY
    s3 = sigmaY * 2**0.5  / aspectRatio # account for 45-degree angle, apply aspect ratio
    Vol = 4/3 * np.pi * s1 * s2 * s3
    return waveLengthCubed * atomNum / Vol
    
    return waveLengthCubed * atomNum / (Vol * (2*np.pi))


def AtomDensity3D_Ellipsoid(atomNum, width1, width2, widthUnit='um'):
    '''

    Parameters
    ----------
    atomNum : TYPE
        DESCRIPTION.
    width1 : apply this width once, e.g. Xwidth in for the ODT
    width2 : apply this width twice for hidden dimension, e.g. Ywidth for ODT

    Returns
    -------
    n_cm3 : TYPE
        DESCRIPTION.
    '''
    
    if widthUnit == 'um':
        width1 = width1 * 1e-6
        width2 = width2 * 1e-6
    
    vol = 4/3 * np.pi * width1 * width2 * width2
    n = atomNum / vol
    n_cm3 = n / 1e6 # density in cubic cm
    return n_cm3
   


def AtomDensity_AddToDF(df, cloudType='ODT'):
    
    Xwidth = df['Xwidth'] * 1e-6
    Ywidth = df['Ywidth'] * 1e-6
    AtomNum = df['YatomNumber']
    
    if cloudType == 'ODT':
        width1 = Xwidth
        width2 = Ywidth
    else:
        width1 = Ywidth
        width2 = Xwidth
    
    n = AtomDensity3D_Ellipsoid(AtomNum, width1, width2, widthUnit='m')
    
    df_new = pd.concat([df, n], axis=1)
    df_new = df_new.rename(columns={0:'Density cm3'})
    
    return df_new


def FermiEnergy_fromDensity(n_cm3, energy_unit='uK'):
    
    # assume n in cubic cm
    n_m3 = n_cm3 * 1e6
    
    # assume only one spin state is being imaged
    kF = (6 * np.pi**2 * n_m3)**(1/3)
    
    eF = (constants.hbar)**2 * kF**2 / (2*MASS)
    
    if energy_unit == 'J':
        return eF
    elif energy_unit == 'K':
        return eF / constants.Boltzmann
    elif energy_unit == 'uK':
        return eF / constants.Boltzmann * 1e6
    

def FermiEnergy_AddToDF(df, unit='uK'):
    
    # assume dataframe includes density in cm-3
    n_cm3 = df['Density cm3']
    eF = FermiEnergy_fromDensity(n_cm3, energy_unit=unit)
    eF = eF.rename(f'Fermi Energy {unit}')
    
    df_new = pd.concat([df, eF], axis=1)
    
    return df_new



def multiVariableThermometry_v2(df, *variables, fitXVar='TOF', fitYVar='Ywidth',
                             atomNum='YatomNumber', sigma1='Xwidth', sigma2='Ywidth', sigma3='Ywidth',
                             do_plot=1, add_Text=1):
   
    params = ExperimentParams(t_exp=10e-6, picturesPerIteration=4, cam_type="zyla")
   
    # Calculate means and standard deviations for error propagation
    df_numeric = df.select_dtypes(include=np.number)
    grouped = df_numeric.groupby(list(variables) + [fitXVar])
    dfmean = grouped.mean()
    dfstd = grouped.std()
   
    df1 = dfmean[fitYVar].unstack()    

    if do_plot:
        runNo = 1
        for var in variables:
            runNo *= df[var].nunique()

        arrange, _ = PlotArangeAndSize(runNo)
       
        # Smaller plot sizes for better fit on screen
        fig_width = arrange[1] * 3.5  
        fig_height = arrange[0] * 3.0
       
        fig, axes = plt.subplots(*arrange,
                                 figsize=(fig_width, fig_height),
                                 layout='constrained', squeeze=False,
                                 sharex=True, sharey=True)
        axes = axes.flatten()
       
    T_list = []
    T_err_list = []
   
    for ii, (ind, item) in enumerate(df.groupby(list(variables))):
        ax = axes[ii] if do_plot else None
        if not isinstance(ind, tuple): ind = (ind,)

        # Restored the full return signature
        res = temperature_fit(params,
                              item[fitYVar]*1e-6,
                              item[fitXVar]*1e-3,
                              do_plot=do_plot, ax=ax)
       
        # Unpack: tof_array, times_fit, widths_fit, popt, pcov, perr
        popt, perr = res[3], res[5]
       
        T_list.append(popt[1])
        T_err_list.append(perr[1])
       
        if do_plot and add_Text:
            label_text = "\n".join([f"{var} = {val:.2f}" for var, val in zip(variables, ind)])
            ax.text(0.05, 0.95, label_text, ha='left', va='top',
                    transform=ax.transAxes, fontsize=9,
                    bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # Prepare data for PSD and Error Propagation
    df1['T (K)'] = T_list
    df1['T error (K)'] = T_err_list
   
    # Filter for minimum TOF values
    df2_mean = dfmean.reset_index(level=fitXVar)
    df2_mean = df2_mean[df2_mean[fitXVar] == 0]
   
    df2_std = dfstd.reset_index(level=fitXVar)
    df2_std = df2_std[df2_std[fitXVar] == 0]
   
    
    # if 'Density cm3' in 
    
    # Value assignment
    # Assuming shape of ODT on Andor camera
    N, T = df2_mean[atomNum], df1['T (K)']
    s1 = df2_mean[sigma1] * 2**0.5 / 1e6
    s2 = df2_mean[sigma2] / 1e6
    s3 = df2_mean[sigma3] / 1e6
   
    # Error assignment (using std at min TOF)
    dN, dT = df2_std[atomNum], df1['T error (K)']
    ds1 = df2_std[sigma1] * 2**0.5 / 1e6
    ds2 = df2_std[sigma2] / 1e6
    ds3 = df2_std[sigma3] / 1e6
   
    # PSD Calculation
    psd_values = PhaseSpaceDensity(N, s1, s2, s3, T)
    # aspectRatio = 0.12
    # psd_values = PhaseSpaceDensity_AspectRatio(N, s2, aspectRatio, T)
    df1['PSD'] = psd_values
   
    # Error Propagation Formula for PSD
    # rel_err = sqrt( (dN/N)^2 + (ds1/s1)^2 + (ds2/s2)^2 + (ds3/s3)^2 + (1.5 * dT/T)^2 )
    rel_err_sq = (dN/N)**2 + (ds1/s1)**2 + (ds2/s2)**2 + (ds3/s3)**2 + (1.5 * dT/T)**2
    df1['PSD error'] = psd_values * np.sqrt(rel_err_sq)

    df1['AtomNum'] = N
    df1['Size1'] = s1
    df1['Size2'] = s2

    return df1




def fit_exponential_v2(df, timeVar='wait', atomNumVar='YatomNumber', offset=None, doPlot=1):
    
    atomNum_avg = df.groupby(timeVar)[atomNumVar].mean().reset_index()[atomNumVar]
    atomNum_std = df.groupby(timeVar)[atomNumVar].std().reset_index()[atomNumVar]
    
    time = df.groupby(timeVar)[atomNumVar].mean().reset_index()[timeVar]

    #fit for the parameters a , b, c
    A = max(atomNum_avg) - min(atomNum_avg)
    Tau = (max(time)-min(time))/2
    C = min(atomNum_avg)
    xfit = np.linspace(min(time),max(time), 5000)
    
    if offset is not None:
        func = exponential
        guess= [A, Tau, C]
        label = 'fit: a=%5.3f, tau=%5.3f, c=%5.3f'
    else:
        func = lambda x,a,tau: exponential(x,a,tau,0)
        guess = [A, Tau]
        label = ' A=%5.2e\n$ \\tau$=%5.3e\n C=0 (Fixed)'
            
    popt, pcov = curve_fit(func, time, atomNum_avg, p0=guess, maxfev=5000, sigma=atomNum_std)       
    perr = np.sqrt(np.diag(pcov))

    if doPlot:
        plt.figure(figsize=(4.5, 3.5))
        
        plt.errorbar(time, atomNum_avg, yerr=atomNum_std, fmt='-o', color='k', capsize=3)
        
        plt.plot(xfit, func(xfit, *popt), 'r-', label= label % tuple(popt), color='r')
        plt.xlabel(timeVar + ' (ms)')
        plt.ylabel(atomNumVar)
        plt.title(f'$\\tau$ = {popt[1]/1e3:.3f} $\pm$ {perr[1]/1e3:.3f} s')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
    
    return popt, perr



def ExtractGaussianCenter_Basler(paths_bas, ROI, doPlot=False):
    
    fullpath_bas = GetFullFilePaths(paths_bas)

    imgs_basler = GetImages(fullpath_bas, 'Basler', ROI, None)

    df = pd.DataFrame(columns=['Xcenter', 'Ycenter', 'Xwidth', 'Ywidth', 'Xamp', 'Yamp'])

    Xcenters = []; Ycenters = []; Xwidths = []; Ywidths = []; Xamps = []; Yamps = []

    for image_arr in imgs_basler:
        
        paramX, paramY = FitGaussian(image_arr, doPlot, 'Wide')
        
        Xcenter = paramX[0]
        Xwidth = paramX[1]
        
        Ycenter = paramY[0]
        Ywidth = paramY[1]
        
        Xcenters.append(Xcenter); Ycenters.append(Ycenter)
        Xwidths.append(Xwidth); Ywidths.append(Ywidth)
        Xamps.append(paramX[2]); Yamps.append(paramY[2])
            
    df['Xcenter'] = Xcenters; df['Ycenter'] = Ycenters
    df['Xwidth'] = Xwidths; df['Ywidth'] = Ywidths
    df['Xamp'] = Xamps; df['Yamp'] = Yamps 
    
    return df



# 
def FitColumnDensity_MultiGaussianY(columnDensities, dx=1, centersOnly=False, doPlot=True):
    
    popts = [];
    centers = []
    
    # fit along Y
    CD1D = np.nansum(columnDensities, axis=2) * dx / 1e6**2    
    
    for ii, ydata in enumerate(CD1D):
            
        xdata = np.arange(len(ydata))
        smoothed = savgol_filter(ydata, window_length=29, polyorder=2)
        
        # assuming two peaks
        peaks, props = find_peaks(
            smoothed,
            height = np.max(smoothed)*0.2,
            # distance=20
        )
        
        if len(peaks) == 2:
            
            guess_a1, guess_a2 = ydata[peaks]
            guess_c1, guess_c2 = peaks
            guess_sigma = 10
            guess_offset = 0
            
            guess = [guess_a1, guess_c1, guess_sigma, guess_offset, guess_a2, guess_c2, guess_sigma, guess_offset]
            
            popt, pcov = curve_fit(multi_gaussian_sum, xdata, ydata, p0=guess)
            
            popts.append(popt)
            centers.append(np.array([popt[1], popt[5]]))
            
            if doPlot:
                x_fit = np.linspace(xdata[0], xdata[-1], len(xdata)*3)
                
                plt.figure()
                plt.plot(xdata, ydata)
                plt.plot(x_fit, multi_gaussian_sum(x_fit, *popt))
                plt.tight_layout()
        
        else:
            print('-----------')
            print(f'Incorrect peak number detected ({len(peaks)})')
            print('-----------')
            
        
    if centersOnly:
        return centers   
    else:
        return popts


def ID_misaligned_beams(centers):
    """Automatically identifies stationary first pass and moving second pass from pair coordinates
    by finding the peak candidate that minimizes variance across all images.
    """
    all_peaks = np.concatenate(centers)

    best_seed = None
    min_std = float("inf")

    # Evaluate each fitted peak across all images as a potential candidate for first pass
    for candidate in all_peaks:
        trajectory = [
            pair[np.argmin(np.abs(pair - candidate))] for pair in centers
        ]
        std = np.std(trajectory)
        if std < min_std:
            min_std = std
            best_seed = candidate

    # Separate first pass and second pass using the optimal seed
    pass1 = []
    pass2 = []
    for pair in centers:
        b1_idx = np.argmin(np.abs(pair - best_seed))
        pass1.append(pair[b1_idx])
        pass2.append(pair[1 - b1_idx])

    return np.array(pass1), np.array(pass2)
