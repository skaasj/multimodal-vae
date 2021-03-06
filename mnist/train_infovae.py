from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import sys
import shutil

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.autograd import Variable
from torchvision import datasets, transforms
from torchvision.utils import save_image

from model import InfoVAE
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
    n_latents = checkpoint['n_latents']
    vae = InfoVAE(n_latents=n_latents)
    vae.load_state_dict(checkpoint['state_dict'])
    
    if use_cuda:
        vae.cuda()

    return vae


def loss_function(recon_x, x, z):
    batch_size = z.size(0)
    NLL = torch.mean(torch.pow(recon_x - x, 2))
    # Compare the generated z with true samples from a standard Gaussian
    # and compute their MMD distance
    true_samples = torch.normal(torch.zeros(batch_size, args.n_latents),
                                torch.ones(batch_size, args.n_latents))
    if z.is_cuda:
        true_samples = true_samples.cuda()
        true_samples = Variable(true_samples)
    MMD = compute_mmd(true_samples, z)
    return NLL + MMD


def compute_kernel(x, y):
    """Apply Gaussian kernel to the i-th vector of x and j-th vector of y.

    :param x: torch.Tensor (x_size, dim)
    :param y: torch.Tensor (y_size, dim)
    """
    x_size, y_size, dim = x.size(0), y.size(0), x.size(1)
    tiled_x = x.unsqueeze(1).expand(x_size, y_size, dim)
    tiled_y = y.unsqueeze(0).expand(x_size, y_size, dim)
    return torch.exp(-torch.mean(torch.pow(tiled_x - tiled_y, 2), dim=2) / float(dim))


def compute_mmd(x, y):
    """Compute maximum mean discrepancy."""
    x_kernel = compute_kernel(x, x)
    y_kernel = compute_kernel(y, y)
    xy_kernel = compute_kernel(x, y)
    return torch.mean(x_kernel) + torch.mean(y_kernel) - 2 * torch.mean(xy_kernel)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_latents', type=int, default=20,
                        help='size of the latent embedding')
    parser.add_argument('--batch_size', type=int, default=128, metavar='N',
                        help='input batch size for training (default: 128)')
    parser.add_argument('--epochs', type=int, default=20, metavar='N',
                        help='number of epochs to train (default: 20)')
    parser.add_argument('--lr', type=float, default=1e-3, metavar='LR',
                        help='learning rate (default: 1e-3)')
    parser.add_argument('--log_interval', type=int, default=10, metavar='N',
                        help='how many batches to wait before logging training status')
    parser.add_argument('--cuda', action='store_true', default=False,
                        help='enables CUDA training')
    args = parser.parse_args()
    args.cuda = args.cuda and torch.cuda.is_available()

    # create loaders for MNIST
    train_loader = torch.utils.data.DataLoader(
        datasets.MNIST('./data', train=True, download=True,
                       transform=transforms.ToTensor()),
        batch_size=args.batch_size, shuffle=True)
    test_loader = torch.utils.data.DataLoader(
        datasets.MNIST('./data', train=False, download=True,
                       transform=transforms.ToTensor()),
        batch_size=args.batch_size, shuffle=True)


    vae = InfoVAE(n_latents=args.n_latents)
    if args.cuda:
        vae.cuda()

    optimizer = optim.Adam(vae.parameters(), lr=args.lr)


    def train(epoch):
        vae.train()
        loss_meter = AverageMeter()

        for batch_idx, (data, _) in enumerate(train_loader):
            if args.cuda:
                data = data.cuda()
            data = Variable(data)
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

        print('====> Epoch: {}\tLoss: {:.4f}'.format(epoch, loss_meter.avg))


    def test():
        vae.eval()
        test_loss = 0

        for batch_idx, (data, _) in enumerate(test_loader):
            if args.cuda:
                data = data.cuda()
            data = Variable(data)
            
            recon_data, z = vae(data)
            loss = loss_function(recon_data, data, z)                
            test_loss += loss.data[0]

        test_loss /= len(test_loader)
        print('====> Test Epoch\tLoss: {:.4f}'.format(test_loss))
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
        save_image(sample.view(64, 1, 28, 28),
                   './results/infovae/sample_epoch%d.png' % epoch)
