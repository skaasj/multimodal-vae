from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import numpy as np

import torch
from torch.autograd import Variable
from torchvision import datasets, transforms
from torchvision.utils import save_image

from train import load_checkpoint
from datasets import ATTR_IX_TO_KEEP, N_ATTRS
from datasets import ATTR_TO_IX_DICT, IX_TO_ATTR_DICT


def fetch_celeba_image(attr_str):
    # find an example of the image in our dataset
    train_loader = torch.utils.data.DataLoader(
        datasets.CelebAttributes(
            partition='train',
            image_transform=transforms.Compose([transforms.Scale(64),
                                                transforms.CenterCrop(64),
                                                transforms.ToTensor()])),
        batch_size=128, shuffle=False)
    # load all data into a single structure
    images, attrs = [], []
    for batch_idx, (image, attr) in enumerate(loader):
        images.append(image)
        labels.append(attr)
    images = torch.cat(images).cpu().numpy()
    attrs = torch.cat(attrs).cpu().numpy()
    # take all the ones where it's an image of the correct label
    attr_ix = ATTR_IX_TO_KEEP.index(ATTR_TO_IX_DICT[attr_str])
    images = images[attrs[:, attr_ix] == 1]
    # randomly choose one
    image = images[np.random.choice(np.arange(images.shape[0]))]
    image = torch.from_numpy(image).float() 
    image = image.unsqueeze(0)
    return Variable(image, volatile=True)


def fetch_celeba_attrs(attr_str):
    attrs = torch.zeros(N_ATTRS)
    attr_ix = ATTR_IX_TO_KEEP.index(ATTR_TO_IX_DICT[attr_str])
    attrs[attr_ix] = 1
    return Variable(attrs.unsqueeze(0), volatile=True)


if __name__ == "__main__":
    import os
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_path', type=str, help='path to trained model file')
    parser.add_argument('--n_samples', type=int, default=64, 
                        help='Number of images and texts to sample.')
    parser.add_argument('--condition_on_image', type=str, default=None,
                        help='If True, generate attrs conditioned on an image w/ attr')
    parser.add_argument('--condition_on_attrs', type=str, default=None, 
                        help='If True, generate images conditioned on an attr.')
    parser.add_argument('--cuda', action='store_true', default=False,
                        help='enables CUDA training')
    args = parser.parse_args()
    args.cuda = args.cuda and torch.cuda.is_available()

    # load trained model
    vae = load_checkpoint('./trained_models/model_best.pth.tar', use_cuda=args.cuda)
    vae.eval()
    if args.cuda:
        vae.cuda()

    # mode 1: unconditional generation
    if not args.condition_on_image and not args.condition_on_attrs:
        mu = Variable(torch.Tensor([0]))
        std = Variable(torch.Tensor([1]))
        if args.cuda:
            mu = mu.cuda()
            std = std.cuda()

    # mode 2: generate conditioned on image
    elif args.condition_on_image and not args.condition_on_attrs:
        image = fetch_celeba_image(args.condition_on_image)
        if args.cuda:
            image = image.cuda()
        mu, logvar = vae.image_encoder(image)
        std = logvar.mul(0.5).exp_()

    # mode 3: generate conditioned on attrs
    elif args.condition_on_attrs and not args.condition_on_image:
        attrs = fetch_celeba_attrs(args.condition_on_attrs)
        if args.cuda:
            attrs = attrs.cuda()
        mu, logvar = vae.attrs_encoder(attrs)
        std = logvar.mul(0.5).exp_()

    # mode 4: generate conditioned on image and attrs
    elif args.condition_on_attrs and args.condition_on_image:
        image = fetch_celeba_image(args.condition_on_image)
        attrs = fetch_celeba_attrs(args.condition_on_attrs)
        if args.cuda:
            image = image.cuda()
            attrs = attrs.cuda()
        image_mu, image_logvar = vae.image_encoder(image)
        attrs_mu, attrs_logvar = vae.attrs_encoder(attrs)
        mu = torch.stack((image_mu, attrs_mu), dim=0)
        logvar = torch.stack((image_logvar, attrs_logvar), dim=0)
        mu, logvar = vae.experts(mu, logvar)
        std = logvar.mul(0.5).exp_()

    # sample from uniform gaussian
    n_latents = vae.n_latents
    sample = Variable(torch.randn(args.n_samples, n_latents))
    if args.cuda:
        sample = sample.cuda()
    
    # sample from particular gaussian by multiplying + adding
    mu = mu.expand_as(sample)
    std = std.expand_as(sample)
    sample = sample.mul(std).add_(mu)

    # generate image and text
    image_recon = vae.image_decoder(sample).cpu().data
    attrs_recon = vae.attrs_decoder(sample).cpu().data

    if not os.path.isdir('./results'):
        os.mkdirs('./results')

    # save image samples to filesystem
    save_image(image_recon.view(args.n_samples, 3, 64, 64),
               './results/sample_image.png')

    # save text samples to filesystem
    sample_attrs = []
    for i in xrange(attrs_recon.size(0)):
        attrs = datasets.tensor_to_attributes(attrs_recon[i])
        sample_attrs.append(','.join(attrs))

    with open('./results/sample_attrs.txt', 'w') as fp:
        for attrs in sample_attrs:
            fp.write('%s\n' % attrs)
