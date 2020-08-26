# -*- coding: utf-8 -*-
"""Base GAN 3D GPU.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1zfvPBgARWuIFnTgl6et18Txt8ptiiRI2
"""

import numpy as np
import os
import gzip, shutil
import nibabel as nib
import time
import random

import torch
from torch.utils.data import Dataset

import torch.nn.functional as F
from torch import nn as nn
from torch.autograd import Variable
from torch.nn import MSELoss, SmoothL1Loss, L1Loss

nobackup = '/nobackup/sc19rw/Train/'
nobackup_models = '/nobackup/sc19rw/Models/'
home = '/home/home01/sc19rw/'

"""## Data collection"""

def get_random_crop(img,cropx,cropy,cropz):
    x,y,z = img.shape
    startx = random.randint(0,(x-cropx))
    starty = random.randint(0,(y-cropy))
    startz = random.randint(0,(z-cropz))
    return startx, starty, startz

MRI_ids = np.load(home+"MRI_ids.npz") #make sure you use the .npz!
MRI_ids = MRI_ids['arr_0']

import pandas as pd
import random


root = nobackup

data = {
    'image_id': MRI_ids,
    't1_path': [root + MRI_id + "_t1_norm"+ ".nii" for MRI_id in MRI_ids],
    't1ce_path': [root + MRI_id + "_t1ce_norm" + ".nii" for MRI_id in MRI_ids],
    'flair_path': [root + MRI_id + "_flair_norm" + ".nii" for MRI_id in MRI_ids],
    't2_path': [root + MRI_id + "_t2_norm" + ".nii" for MRI_id in MRI_ids],
    'seg_path': [root + MRI_id + "_seg" + ".nii" for MRI_id in MRI_ids],
}

data_df = pd.DataFrame(data, columns=['image_id', 't1_path', 't1ce_path', 'flair_path', 't2_path', 'seg_path'])

class BRATS_DATA_CROPPED(Dataset):
    """ BRATS custom dataset compatible with torch.utils.data.DataLoader. """
    
    def __init__(self, df, transform=None):
        self.df = df
        self.transform = transform

    def __getitem__(self, index):

        MRI_id = self.df['image_id'][index] 
        t1_path = self.df['t1_path'][index]
        t1ce_path = self.df['t1ce_path'][index]
        flair_path = self.df['flair_path'][index]
        t2_path = self.df['t2_path'][index]
        seg_path = self.df['seg_path'][index]

        seg_map = nib.load(seg_path)
        affine = seg_map.affine

        seg_map = seg_map.get_fdata()

        cropx,cropy,cropz = 128, 128, 128
        startx,starty,startz = get_random_crop(seg_map, cropx,cropy,cropz)

        t1_MRI = nib.load(t1_path).get_fdata()[startx:startx+cropx,starty:starty+cropy,startz:startz+cropz].reshape(1, cropx,cropy,cropz)
        t1ce_MRI = nib.load(t1ce_path).get_fdata()[startx:startx+cropx,starty:starty+cropy,startz:startz+cropz].reshape(1, cropx,cropy,cropz)
        flair_MRI = nib.load(flair_path).get_fdata()[startx:startx+cropx,starty:starty+cropy,startz:startz+cropz].reshape(1, cropx,cropy,cropz)
        t2_MRI = nib.load(t2_path).get_fdata()[startx:startx+cropx,starty:starty+cropy,startz:startz+cropz].reshape(1, cropx,cropy,cropz)
        seg_map = seg_map[startx:startx+cropx,starty:starty+cropy,startz:startz+cropz].reshape(1, cropx,cropy,cropz)

        
        input_tensor = np.concatenate((t1_MRI, t1ce_MRI, flair_MRI, t2_MRI), axis=0) 
     

        return input_tensor, seg_map, affine, MRI_id

    def __len__(self):
        return len(self.df)

class BRATS_DATA(Dataset):
    """ BRATS custom dataset compatible with torch.utils.data.DataLoader. """
    
    def __init__(self, df, transform=None):
        self.df = df
        self.transform = transform

    def __getitem__(self, index):

        MRI_id = self.df['image_id'][index] 
        t1_path = self.df['t1_path'][index]
        t1ce_path = self.df['t1ce_path'][index]
        flair_path = self.df['flair_path'][index]
        t2_path = self.df['t2_path'][index]
        seg_path = self.df['seg_path'][index]

        seg_map = nib.load(seg_path)
        affine = seg_map.affine

        t1_MRI = nib.load(t1_path).get_fdata()[:].reshape(1,240,240,155)
        t1ce_MRI = nib.load(t1ce_path).get_fdata()[:].reshape(1,240,240,155)
        flair_MRI = nib.load(flair_path).get_fdata()[:].reshape(1,240,240,155)
        t2_MRI = nib.load(t2_path).get_fdata()[:].reshape(1,240,240,155)
        seg_map = seg_map.get_fdata()[:].reshape(1,240,240,155)

        
        input_tensor = np.concatenate((t1_MRI, t1ce_MRI, flair_MRI, t2_MRI), axis=0) 
     

        return input_tensor, seg_map, affine, MRI_id

    def __len__(self):
        return len(self.df)

train_split = 0.8 # Defines the ratio of train/test data.

train_size = round(len(data_df)*train_split)
test_size = round(len(data_df)*(1-train_split))

dataset_train = BRATS_DATA_CROPPED(
    df=data_df[:train_size].reset_index(drop=True),
)

dataset_test = BRATS_DATA_CROPPED(
    df=data_df[-test_size:].reset_index(drop=True),
)

dataset_total = BRATS_DATA( #used to get the final segmentations
    df=data_df[:len(data_df)].reset_index(drop=True),
)

"""##Data Augmentation"""

from batchgenerators.dataloading.data_loader import DataLoaderBase
from batchgenerators.transforms.abstract_transforms import Compose
from batchgenerators.dataloading.single_threaded_augmenter import SingleThreadedAugmenter
from batchgenerators.transforms.spatial_transforms import SpatialTransform_2
from batchgenerators.transforms.spatial_transforms import SpatialTransform
from batchgenerators.transforms.spatial_transforms import MirrorTransform
from batchgenerators.transforms.color_transforms import GammaTransform

class DataLoader(DataLoaderBase): #SlimDataLoaderBase 
    def __init__(self, data, BATCH_SIZE=1, num_batches=None, seed=False):
        super(DataLoader, self).__init__(data, BATCH_SIZE, num_batches, seed) 
        # data is now stored in self._data.
        self.index = 0
        self.batch_size = BATCH_SIZE
    
    def generate_train_batch(self):
        currentindex = self.index
        self.index += 1
        if self.index % len(self._data)  == 0:
          self.index = 0

        data = self._data[self.index][0].reshape(self.batch_size, 4, 128, 128, 128)   #.numpy()
        seg = self._data[self.index][1].reshape(self.batch_size, 1, 128, 128, 128)

        return {'data':data, 'seg':seg, 'affine':self._data[self.index][2], 'MRI_ID':self._data[self.index][3]}

batchgen = DataLoader(dataset_train, 1, len(dataset_train), False) #Basic data loader without augmentation

my_transforms = [] #define all augmentation techniques to be applied

spatial_transform = SpatialTransform(
            dataset_train[0][0][0].shape, dataset_train[0][0][0].shape,
            do_elastic_deform=True,
            alpha=(0., 175.), sigma=(10., 13.),       
            do_rotation=True,
            angle_x=(- 5 / 360. * 2 * np.pi, 5 / 360. * 2 * np.pi),
            angle_y=(- 5 / 360. * 2 * np.pi, 5 / 360. * 2 * np.pi),
            angle_z=(- 5 / 360. * 2 * np.pi, 5 / 360. * 2 * np.pi),
            do_scale=True, scale=(0.9, 1.02),
            border_mode_data='constant', border_cval_data=0,
            border_mode_seg='constant', border_cval_seg=0,
            order_seg=1, order_data=3,
            random_crop=False,
            p_el_per_sample=0.1, p_rot_per_sample=0.1, p_scale_per_sample=0.1)


my_transforms.append(spatial_transform)
my_transforms.append(MirrorTransform(axes=(0, 1, 2)))
my_transforms.append(GammaTransform(gamma_range=(0.7, 1.), invert_image=False, per_channel=True, p_per_sample=0.1))

all_transforms = Compose(my_transforms)

train_loader = SingleThreadedAugmenter(batchgen, all_transforms) #data loader for training, applying on the fly transformation

# add other data loaders
test_loader = torch.utils.data.DataLoader(
    dataset_test,
    batch_size=1, 
    shuffle=False,
    num_workers=0,
)

full_loader = torch.utils.data.DataLoader(
    dataset_total,
    batch_size=1, 
    shuffle=False,
    num_workers=0,
)

"""## Building Model"""

class UNet(nn.Module):
    def contracting_block(self, in_channels, out_channels, kernel_size=3):
        block = torch.nn.Sequential(
                    torch.nn.Conv3d(kernel_size=kernel_size, in_channels=in_channels, out_channels=out_channels, padding=1),
                    torch.nn.LeakyReLU(), 
                    torch.nn.InstanceNorm3d(out_channels), 
                    torch.nn.Conv3d(kernel_size=kernel_size, in_channels=out_channels, out_channels=out_channels, padding=1),
                    torch.nn.LeakyReLU(),
                    torch.nn.InstanceNorm3d(out_channels),
                )
        return block
    
    def expansive_block(self, in_channels, mid_channel, out_channels, kernel_size=3):
            block = torch.nn.Sequential(
                    torch.nn.Conv3d(kernel_size=kernel_size, in_channels=in_channels, out_channels=mid_channel, padding=1),
                    torch.nn.LeakyReLU(),
                    torch.nn.InstanceNorm3d(mid_channel),
                    torch.nn.Conv3d(kernel_size=kernel_size, in_channels=mid_channel, out_channels=mid_channel, padding=1),
                    torch.nn.LeakyReLU(),
                    torch.nn.InstanceNorm3d(mid_channel),
                    torch.nn.ConvTranspose3d(in_channels=mid_channel, out_channels=out_channels, kernel_size=3, stride=2, padding=1, output_padding=1)
                    )
            return  block
    
    def bottleneck_block(self):
           block = torch.nn.Sequential(   #put this properly before
                            torch.nn.Conv3d(kernel_size=3, in_channels=120, out_channels=240, padding=1),
                            torch.nn.LeakyReLU(),
                            torch.nn.InstanceNorm3d(240),
                            torch.nn.Conv3d(kernel_size=3, in_channels=240, out_channels=120, padding=1),
                            torch.nn.LeakyReLU(),
                            torch.nn.InstanceNorm3d(120),
                            torch.nn.ConvTranspose3d(in_channels=120, out_channels=120, kernel_size=3, stride=2, padding=1, output_padding=1)
                            )
           return block

    def final_block(self, in_channels, mid_channel, out_channels, kernel_size=3):
            block = torch.nn.Sequential(
                    torch.nn.Conv3d(kernel_size=kernel_size, in_channels=in_channels, out_channels=mid_channel, padding=1),
                    torch.nn.LeakyReLU(),
                    torch.nn.InstanceNorm3d(mid_channel),
                    torch.nn.Conv3d(kernel_size=kernel_size, in_channels=mid_channel, out_channels=mid_channel, padding=1),
                    torch.nn.LeakyReLU(),
                    torch.nn.InstanceNorm3d(mid_channel),
                    torch.nn.Conv3d(kernel_size=kernel_size, in_channels=mid_channel, out_channels=out_channels, padding=1),
                    #torch.nn.LeakyReLU(),
                    torch.nn.Sigmoid(),
                    )
            return  block
    
    def __init__(self):
        super(UNet, self).__init__()       
        #Encode
        self.conv_encode1 = self.contracting_block(in_channels=4, out_channels=15)
        self.conv_maxpool1 = torch.nn.MaxPool3d(kernel_size=2)
        self.conv_encode2 = self.contracting_block(15, 30)
        self.conv_maxpool2 = torch.nn.MaxPool3d(kernel_size=2)
        self.conv_encode3 = self.contracting_block(30, 60)
        self.conv_maxpool3 = torch.nn.MaxPool3d(kernel_size=2)
        self.conv_encode4 = self.contracting_block(60, 120)
        self.conv_maxpool4 = torch.nn.MaxPool3d(kernel_size=2)
        # Bottleneck
        self.bottleneck = self.bottleneck_block()
        # Decode
        self.conv_decode4 = self.expansive_block(240, 120, 60)
        self.conv_decode3 = self.expansive_block(120, 60, 30)
        self.conv_decode2 = self.expansive_block(60, 30, 15)
        self.final_layer = self.final_block(30, 15, 1)
        
    
    def forward(self, input_tensor):
        # Encode
        encode_block1 = self.conv_encode1(input_tensor)
        encode_pool1 = self.conv_maxpool1(encode_block1)
        encode_block2 = self.conv_encode2(encode_pool1)
        encode_pool2 = self.conv_maxpool2(encode_block2)
        encode_block3 = self.conv_encode3(encode_pool2)
        encode_pool3 = self.conv_maxpool3(encode_block3)
        encode_block4 = self.conv_encode4(encode_pool3)
        encode_pool4 = self.conv_maxpool4(encode_block4)
        # Bottleneck
        bottleneck1 = self.bottleneck(encode_pool4)
        # Decode
        if bottleneck1.size()[4] != encode_block4.size()[4]:
            bottleneck1 = F.pad(bottleneck1, pad=(1, 0), mode='constant', value=0)
        decode_block4 = self.conv_decode4(torch.cat((bottleneck1, encode_block4), 1))
        
        if decode_block4.size()[4] != encode_block3.size()[4]:
            decode_block4 = F.pad(decode_block4, pad=(1, 0), mode='constant', value=0)
        decode_block3 = self.conv_decode3(torch.cat((decode_block4, encode_block3), 1))
        
        if decode_block3.size()[4] != encode_block2.size()[4]:
            decode_block3 = F.pad(decode_block3, pad=(1, 0), mode='constant', value=0)
        decode_block2 = self.conv_decode2(torch.cat((decode_block3, encode_block2), 1))
        
        if decode_block2.size()[4] != encode_block1.size()[4]:
            decode_block2 = F.pad(decode_block2, pad=(1, 0), mode='constant', value=0)
        final_layer = self.final_layer(torch.cat((decode_block2, encode_block1), 1))
        return  final_layer

class Discriminator(nn.Module):
    def contracting_block(self, in_channels, out_channels, kernel_size=3):
        block = torch.nn.Sequential(
                    torch.nn.Conv3d(kernel_size=kernel_size, in_channels=in_channels, out_channels=out_channels, padding=1),
                    torch.nn.LeakyReLU(), 
                    torch.nn.InstanceNorm3d(out_channels), 
                    torch.nn.Conv3d(kernel_size=kernel_size, in_channels=out_channels, out_channels=out_channels, padding=1),
                    torch.nn.LeakyReLU(),
                    torch.nn.InstanceNorm3d(out_channels),
                )
        return block
    
    def __init__(self):
        super(Discriminator, self).__init__()       
        self.conv_encode1 = self.contracting_block(in_channels=5, out_channels=15)
        self.conv_maxpool1 = torch.nn.MaxPool3d(kernel_size=2)
        self.conv_encode2 = self.contracting_block(15, 30)
        self.conv_maxpool2 = torch.nn.MaxPool3d(kernel_size=2)
        self.conv_encode3 = self.contracting_block(30, 60)
        self.conv_maxpool3 = torch.nn.MaxPool3d(kernel_size=2)
        self.conv_encode4 = self.contracting_block(60, 120)
        self.conv_maxpool4 = torch.nn.MaxPool3d(kernel_size=2)
        self.final_layer1 = torch.nn.Conv3d(kernel_size=3, in_channels=120, out_channels=240, padding=1)
        self.final_layer2 = torch.nn.Conv3d(kernel_size=3, in_channels=240, out_channels=1, padding=1)
        self.final_activation = torch.nn.Sigmoid()
    
    def forward(self, input_tensor):
        encode_block1 = self.conv_encode1(input_tensor)
        encode_pool1 = self.conv_maxpool1(encode_block1)
        encode_block2 = self.conv_encode2(encode_pool1)
        encode_pool2 = self.conv_maxpool2(encode_block2)
        encode_block3 = self.conv_encode3(encode_pool2)
        encode_pool3 = self.conv_maxpool3(encode_block3)
        encode_block4 = self.conv_encode4(encode_pool3)
        encode_pool4 = self.conv_maxpool4(encode_block4)
        output = self.final_layer1(encode_pool4)
        output = self.final_layer2(output)
        output = self.final_activation(output)

        return  output

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
device

class DiceLoss(nn.Module):
    def __init__(self, weight=None, size_average=True):
        super(DiceLoss, self).__init__()

    def forward(self, inputs, targets, smooth=1):
        
        #comment out if your model contains a sigmoid or equivalent activation layer
        #inputs = torch.sigmoid(inputs)       
        
        #flatten label and prediction tensors
        inputs = inputs.contiguous().view(-1)
        targets = targets.contiguous().view(-1)
        
        intersection = (inputs * targets).sum()                            
        dice = (2.*intersection + smooth)/(inputs.sum() + targets.sum() + smooth)  
        
        return 1 - dice

class GeneralizedDiceLoss(nn.Module):
  """
        Generalized Dice;
        Copy from: https://github.com/wolny/pytorch-3dunet/blob/6e5a24b6438f8c631289c10638a17dea14d42051/unet3d/losses.py#L75
        paper: https://arxiv.org/pdf/1707.03237.pdf
        tf code: https://github.com/NifTK/NiftyNet/blob/dev/niftynet/layer/loss_segmentation.py#L279
  """
  def __init__(self, epsilon=1e-5, weight=None, ignore_index=None, sigmoid_normalization=True):
    super(GeneralizedDiceLoss, self).__init__()
    self.epsilon = epsilon
    self.register_buffer('weight', weight)
    self.ignore_index = ignore_index
    if sigmoid_normalization:
      self.normalization = nn.Sigmoid()
    else:
      self.normalization = nn.Softmax(dim=1)

  def forward(self, input, target):
    # get probabilities from logits
    #input = self.normalization(input)

    assert input.size() == target.size(), "'input' and 'target' must have the same shape"

    # mask ignore_index if present
    if self.ignore_index is not None:
        mask = target.clone().ne_(self.ignore_index)
        mask.requires_grad = False

        input = input * mask
        target = target * mask

    input = input.contiguous().view(-1)
    target = target.contiguous().view(-1)

    target = target.float()
    target_sum = target.sum(-1)
    class_weights = Variable(1. / (target_sum * target_sum).clamp(min=self.epsilon), requires_grad=False)

    intersect = (input * target).sum(-1) * class_weights
    if self.weight is not None:
        weight = Variable(self.weight, requires_grad=False)
        intersect = weight * intersect
    intersect = intersect.sum()

    denominator = ((input + target).sum(-1) * class_weights).sum()

    return 1. - 2. * intersect / denominator.clamp(min=self.epsilon)

"""## Training

Dont forget to change model number
"""

model_number = 'base_GAN_3D'  #CHANGE MODEL VERSION HERE

##CHANGE HERE TO LOAD UNET MODELS##
LOAD_MODEL = False #HERE


with torch.no_grad(): #THIS MEANS NEED TO CREATE NEW NOTEBOOK EVERYTIME WANT TO CREATE NEW MODEL TO PRESERVE ARCHITECTURE
  UNet = UNet().to(device)
  Discriminator = Discriminator().to(device)

optimizer_Unet = torch.optim.Adam(UNet.parameters(), lr=0.0001)
optimizer_Dis = torch.optim.Adam(Discriminator.parameters(), lr=0.0001)

if LOAD_MODEL == True:
  checkpoint = torch.load(nobackup_models + model_number +'_checkpoint.pth.tar')
  first_epoch = checkpoint['epoch']
  train_dice_loss_list = checkpoint['train_dice_loss_list']
  test_dice_loss_list = checkpoint['test_dice_loss_list']
  train_loss_list = checkpoint['train_loss_list']
  test_loss_list = checkpoint['test_loss_list']
  UNet.load_state_dict(checkpoint['UNet'])
  Discriminator.load_state_dict(checkpoint['Dis'])
  optimizer_Unet.load_state_dict(checkpoint['optimizer_Unet'])
  optimizer_Dis.load_state_dict(checkpoint['optimizer_Dis'])

else:
  first_epoch = 0
  train_dice_loss_list = []
  test_dice_loss_list = []
  train_loss_list = []
  test_loss_list = []

def save_checkpoint(state, filename=model_number):
    full_path = nobackup_models + filename +'_checkpoint.pth.tar'
    torch.save(state, full_path)

#criterion_Dice = DiceLoss() #try new
criterion_Dice = GeneralizedDiceLoss() 
criterion_Dis = torch.nn.MSELoss()


def train_discriminator(input_tensor_axial, real_seg_axial, isreal, isfake):
    optimizer_Dis.zero_grad() #reset
    optimizer_Unet.zero_grad() 
        
    fake_seg_axial = UNet(input_tensor_axial) #get predicted segmentation

    pred_real = Discriminator(torch.cat((real_seg_axial, input_tensor_axial), 1)) #get discriminator predictions for both real and fake segmentation
    pred_fake = Discriminator(torch.cat((fake_seg_axial, input_tensor_axial), 1))

    loss_real = criterion_Dis(pred_real, isreal) #get loss values for both real and fake segmentation
    loss_fake = criterion_Dis(pred_fake, isfake) 

    loss_Dis_element = 0.5 * (loss_real + loss_fake) #total loss for discriminator   

    loss_Dis_element.backward() #Dis loss
    optimizer_Dis.step() #Optimise discriminator

    #CLEAN UP
    loss_Dis_element.detach()  
    loss_real.detach()
    loss_fake.detach()
    del fake_seg_axial
    
def train_Unet(input_tensor_axial, real_seg_axial, isreal, isfake, lambda_val):
    optimizer_Unet.zero_grad() 
    optimizer_Dis.zero_grad() 
        
    fake_seg_axial = UNet(input_tensor_axial) #get predicted segmentation
    pred_fake = Discriminator(torch.cat((fake_seg_axial, input_tensor_axial), 1)) #Get new generator output (can be deleted and use previous)

    loss_dice = criterion_Dice(fake_seg_axial, real_seg_axial) #Get dice loss for Unet
    loss_fake = criterion_Dis(pred_fake, isreal) #Get descriminator loss for Unet

    loss_Unet_element = loss_fake + lambda_val * loss_dice #Total UNet loss
      
    loss_Unet_element.backward() 
    
    optimizer_Unet.step() #Optimise Unet 
      
    loss_Unet_element.detach()  
    loss_dice.detach()
    loss_fake.detach()
     
    return float(loss_dice), float(loss_Unet_element)

def train_GAN(num_epochs, do_validation, lambda_val = 5):
  isreal = torch.Tensor(np.ones((8,8,8)).reshape(1, 1, 8, 8, 8)).to(device)
  isfake = torch.Tensor(np.zeros((8,8,8)).reshape(1, 1, 8, 8, 8)).to(device)
  for epoch in range(num_epochs): #train the model THIS IS TO BE USED WHEN THE ARRAYS CANNOT FIT IN MEMORY
    trainloss = 0
    testloss = 0
    traindiceloss = 0
    testdiceloss = 0

    print("NEW EPOCH")
    for patient, data in enumerate(train_loader): #ONLY TESTED WITH BATCH SIZE 1
      input_tensor_axial = torch.from_numpy(data['data']).to(device)
      real_seg_axial = torch.from_numpy(data['seg']).to(device)

      #TRAIN DISCRIMINATOR
      train_discriminator(input_tensor_axial, real_seg_axial, isreal, isfake)
      
      #TRAIN UNET   
      loss_dice, loss_Unet_element = train_Unet(input_tensor_axial, real_seg_axial, isreal, isfake, lambda_val)

      traindiceloss += float(loss_dice)
      trainloss += float(loss_Unet_element)


    print("\n Train total loss: " + str(trainloss/(train_size)))
    print("Train Dice loss: " + str(traindiceloss/(train_size))) 
    train_dice_loss_list.append(traindiceloss/(train_size))
    train_loss_list.append(trainloss/(train_size))


    #VALIDATION 
    if do_validation == True:
      with torch.no_grad():
        for patient, (input_tensor, seg_map, affine, MRI_ID) in enumerate(test_loader): #ONLY WORKS WITH BATCH SIZE 1
          input_tensor_axial = input_tensor.to(device).float() #get input slice
          real_seg_axial = seg_map.to(device).float() #get corresponding segmentation slice
        
          fake_seg_axial = UNet(input_tensor_axial) #get predicted segmentation
          pred_fake = Discriminator(torch.cat((fake_seg_axial, input_tensor_axial), 1))

          loss_dice = criterion_Dice(fake_seg_axial, real_seg_axial)
          loss_fake = criterion_Dis(pred_fake, isfake)

          loss_Unet = loss_fake + lambda_val * loss_dice

          testloss += float(loss_Unet)
          testdiceloss += float(loss_dice)   
        print("Test loss: " + str(testloss/(test_size)))
        print("Test Dice loss: " + str(testdiceloss/(test_size))) 
        test_dice_loss_list.append(testdiceloss/(test_size))
        test_loss_list.append(testloss/(test_size))

    print(" ")

num_epochs = 50
train_GAN(num_epochs, do_validation=True)

save_checkpoint({
            'epoch': first_epoch+num_epochs,
            'UNet': UNet.state_dict(),
            'Dis': Discriminator.state_dict(),
            'train_dice_loss_list': train_dice_loss_list,
            'test_dice_loss_list': test_dice_loss_list,
            'train_loss_list': train_loss_list,
            'test_loss_list': test_loss_list,
            'optimizer_Unet' : optimizer_Unet.state_dict(),
            'optimizer_Dis' : optimizer_Dis.state_dict()
            }
            )

"""##Post processing"""

def get_short_id(long_id):
  short_id = ""
  for i in range(len(long_id)-5): #ignore the first 4 characters
    if long_id[i+4] == '/':
      return short_id
    else:
      short_id += long_id[i+4]

def save_results():
  newpath = nobackup_models + model_number + '_Results'
  if not os.path.exists(newpath):
    os.makedirs(newpath)
  with torch.no_grad():
    for patient, (input_tensor, seg_map, affine, MRI_ID) in enumerate(full_loader):
      print(patient, end = ' ')
      seg_3D = get_seg_wrapper(input_tensor).detach().cpu()

      ID = get_short_id(MRI_ID[0])
      ni_img = nib.Nifti1Image(seg_3D.numpy(), affine.reshape(4, 4))
      nib.save(ni_img, newpath + '/' + ID + '.nii.gz')

def get_seg_wrapper(input_tensor):
  with torch.no_grad():
    input_tensor_axial = input_tensor.float().to(device) #change this
    return UNet(input_tensor_axial)

finalize = False #CHANGE HERE

if finalize == True:
  save_results()
