from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import shutil
import sys
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.autograd import Variable
from torchvision import datasets, transforms
from torchvision.utils import save_image

from model import InfoVAE
from model import compute_mmd
from train import AverageMeter


def save_checkpoint(state, is_best, folder='./', filename='checkpoint.pth.tar'):
    torch.save(state, os.path.join(folder, filename))
    if is_best:
        shutil.copyfile(os.path.join(folder, filename),
                        os.path.join(folder, 'model_best.pth.tar'))


def load_checkpoint(file_path, use_cuda=False):
    """Return EmbedNet instance"""
    if use_cuda:
        checkpoint = torch.load(file_path)
    else:
        checkpoint = torch.load(file_path,
                                map_location=lambda storage, location: storage)

    vae = InfoVAE(n_latents=checkpoint['n_latents'])
    vae.load_state_dict(checkpoint['state_dict'])
    
    return vae


def loss_function(recon_x, x, z):
    batch_size = z.size(0)
    BCE = F.binary_cross_entropy(recon_x, x)
    # Compare the generated z with true samples from a standard Gaussian
    # and compute their MMD distance
    true_samples = torch.normal(torch.zeros(batch_size, args.n_latents),
                                torch.ones(batch_size, args.n_latents))
    if z.is_cuda:
        true_samples = true_samples.cuda()
        true_samples = Variable(true_samples)
    MMD = compute_mmd(true_samples, z)
    return BCE + MMD


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_latents', type=int, default=100,
                        help='size of the latent embedding (default: 100)')
    parser.add_argument('--batch_size', type=int, default=128, metavar='N',
                        help='input batch size for training (default: 128)')
    parser.add_argument('--epochs', type=int, default=10, metavar='N',
                        help='number of epochs to train (default: 10)')
    parser.add_argument('--lr', type=float, default=1e-4, metavar='LR',
                        help='learning rate (default: 1e-4)')
    parser.add_argument('--log_interval', type=int, default=10, metavar='N',
                        help='how many batches to wait before logging training status (default: 10)')
    parser.add_argument('--cuda', action='store_true', default=False,
                        help='enables CUDA training')
    args = parser.parse_args()
    args.cuda = args.cuda and torch.cuda.is_available()

    if not os.path.isdir('./trained_models'):
        os.makedirs('./trained_models')

    if not os.path.isdir('./trained_models/infovae'):
        os.makedirs('./trained_models/infovae')

    if not os.path.isdir('./results'):
        os.makedirs('./results')

    if not os.path.isdir('./results/infovae'):
        os.makedirs('./results/infovae')

    transform_train = transforms.Compose([transforms.Scale(32),
                                          transforms.CenterCrop(32),
                                          transforms.ToTensor()])
    transform_test = transforms.Compose([transforms.Scale(32),
                                         transforms.CenterCrop(32),
                                         transforms.ToTensor()])
 
    train_loader = torch.utils.data.DataLoader(
        datasets.CocoCaptions('./data/coco/train2014', 
                              './data/coco/annotations/captions_train2014.json',
                              transform=transform_train),
        batch_size=args.batch_size, shuffle=True)
    test_loader = torch.utils.data.DataLoader(
        datasets.CocoCaptions('./data/coco/val2014', 
                              './data/coco/annotations/captions_val2014.json',
                              transform=transform_test),
        batch_size=args.batch_size, shuffle=True)

    vae = InfoVAE(n_latents=args.n_latents)
    if args.cuda:
        vae.cuda()

    optimizer = optim.Adam(vae.parameters(), lr=args.lr)


    def train(epoch):
        vae.train()
        loss_meter = AverageMeter()

        for batch_idx, (data, _) in enumerate(train_loader):
            data = Variable(data)
            if args.cuda:
                data = data.cuda()
            optimizer.zero_grad()
            recon_data, z = vae(data)
            loss = loss_function(recon_data, data, z)
            loss_meter.update(loss.data[0], len(data))            
            loss.backward()
            optimizer.step()
            if batch_idx % args.log_interval == 0:
                print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                    epoch, batch_idx * len(data), len(train_loader.dataset),
                    100. * batch_idx / len(train_loader), loss_meter.avg))

        print('====> Epoch: {} Average loss: {:.4f}'.format(epoch, loss_meter.avg))


    def test():
        vae.eval()
        test_loss = 0
        for i, (data, _) in enumerate(test_loader):
            if args.cuda:
                data = data.cuda()
            data = Variable(data, volatile=True)
            recon_data, z = vae(data)
            test_loss += loss_function(recon_data, data, z).data[0]

        test_loss /= len(test_loader)
        print('====> Test set loss: {:.4f}'.format(test_loss))
        return test_loss


    best_loss = sys.maxint
    for epoch in range(1, args.epochs + 1):
        train(epoch)
        loss = test()

        is_best = loss < best_loss
        best_loss = min(loss, best_loss)

        save_checkpoint({
            'state_dict': vae.state_dict(),
            'best_loss': best_loss,
            'n_latents': args.n_latents,
            'optimizer' : optimizer.state_dict(),
        }, is_best, folder='./trained_models/infovae')

        sample = Variable(torch.randn(64, args.n_latents))
        if args.cuda:
           sample = sample.cuda()

        sample = vae.decode(sample).cpu().data
        save_image(sample.view(64, 3, 32, 32),
                   './results/infovae/sample_epoch%d.png' % epoch)
