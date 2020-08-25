import numpy as np
import torch

print('Enter model to check (UNET/GAN/AGAN:')
model_type = input()

print('Enter nbr of epochs to check:')
nbr_epochs = int(input())

if model_type == 'UNET':
  model = 'base_Unet_Test'
if model_type == 'GAN':
  model = 'base_GAN_test'
if model_type == 'AGAN':
  model = 'base_GAN_A_Test'


checkpoint = torch.load('/nobackup/sc19rw/Models/' + model + '_checkpoint.pth.tar', map_location={'cuda:0': 'cpu'})
test_dice_loss_list = checkpoint['test_dice_loss_list']


EMA = []

alpha = 2 / (total_epoch + 1)

for i in range(total_epoch):
  if i == 0:
    EMA.append(test_dice_loss_list[i])
  else:
    new_EMA = alpha*test_dice_loss_list[i] + (1-alpha)*EMA[i-1]
    EMA.append(new_EMA)


if EMA[total_epoch-nbr_epochs] > EMA[total_epoch-1]:
  print("Keep training")
else:
  print("Finished Training")


